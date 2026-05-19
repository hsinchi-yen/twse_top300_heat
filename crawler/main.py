"""
main.py — Crawler APScheduler entry point

排程邏輯（台股交易時間 09:00-13:30）：
    - 盤中：每 60 秒觸發（低 jitter），超過 13:30 自動 skip
    - 收盤後：16:00 執行最終一次（is_closing=True），之後不再拉取
    - 每日 08:55 重置 cache、刷新 sector_map
"""

import logging
import os
import random
import time as _time
from datetime import datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from sources.twse import fetch_twse_daily
from sources.tpex import fetch_tpex_daily
from sources.yahoo import fetch_yahoo_quotes
from sources.finmind import fetch_issue_shares, fetch_industry_categories, clear_cache
from sources.buy_score import batch_fetch_scores, write_scores
from processor import merge_and_rank

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/twse_heat.db")
TZ_TAIPEI = ZoneInfo("Asia/Taipei")
MARKET_CLOSE = time(13, 30)
MIN_VALID_RECORDS = int(os.getenv("MIN_VALID_RECORDS", "80"))

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


def _upsert(session, records: list[dict], date: str) -> None:
    for r in records:
        session.execute(
            text("""
                INSERT INTO stock_ranks
                    (stock_id, name, date, volume, close_price, turnover_rate,
                     price_change_pct, color_tier, volume_rank, turnover_rank)
                VALUES
                    (:stock_id, :name, :date, :volume, :close_price, :turnover_rate,
                     :price_change_pct, :color_tier, :volume_rank, :turnover_rank)
                ON CONFLICT(stock_id, date) DO UPDATE SET
                    volume=excluded.volume,
                    close_price=excluded.close_price,
                    turnover_rate=excluded.turnover_rate,
                    price_change_pct=excluded.price_change_pct,
                    color_tier=excluded.color_tier,
                    volume_rank=excluded.volume_rank,
                    turnover_rank=excluded.turnover_rank
            """),
            {**r, "date": date, "close_price": r.get("close_price", 0.0)},
        )
    session.commit()


def _ensure_sectors(session, industry: dict[str, str]) -> None:
    """
    首次呼叫時將 FinMind 類股資訊批次寫入 sector_map。
    使用 ON CONFLICT DO NOTHING 保留 seed.py 的自訂題材標籤。
    """
    if not industry:
        return
    count = session.execute(text("SELECT COUNT(*) FROM sector_map")).scalar() or 0
    if count >= 500:
        return  # 已充分填充，跳過

    logger.info("Populating sector_map with industry categories (%d stocks)...", len(industry))
    for stock_id, cat in industry.items():
        session.execute(
            text("""
                INSERT INTO sector_map (stock_id, sector)
                VALUES (:stock_id, :sector)
                ON CONFLICT(stock_id) DO NOTHING
            """),
            {"stock_id": stock_id, "sector": cat},
        )
    session.commit()
    new_count = session.execute(text("SELECT COUNT(*) FROM sector_map")).scalar()
    logger.info("Sector map now has %d entries.", new_count)


def refresh_sector_map_job() -> None:
    """
    將 FinMind 類股資訊刷新至 sector_map，與盤中價格抓取解耦。
    """
    logger.info("Refreshing sector_map from FinMind industry categories...")
    industry = fetch_industry_categories()
    if not industry:
        logger.warning("Industry categories unavailable, skip sector_map refresh.")
        return

    with Session() as session:
        _ensure_sectors(session, industry)


def crawl_job(is_closing: bool = False) -> None:
    now = datetime.now(tz=TZ_TAIPEI)
    today = now.strftime("%Y-%m-%d")

    # 盤中 job：超過 13:30 自動 skip，收盤 job 不受此限
    if not is_closing and now.time() > MARKET_CLOSE:
        logger.info("Market closed at %s, skipping intraday crawl", now.strftime("%H:%M"))
        return

    logger.info("Crawl job started at %s (closing=%s)", now.isoformat(), is_closing)

    # 各來源間加入隨機延遲，降低被識別為 bot 的機率
    twse, twse_date = fetch_twse_daily()
    _time.sleep(random.uniform(1.0, 3.0))    # inter-source delay
    tpex, tpex_date = fetch_tpex_daily()
    _time.sleep(random.uniform(1.0, 3.0))
    issue_shares = fetch_issue_shares()

    if not twse and not tpex:
        logger.warning("Both TWSE and TPEX sources failed/empty. Keeping previous snapshot.")
        return
    if not twse:
        logger.warning("TWSE source empty, continuing with TPEX snapshot.")
    if not tpex:
        logger.warning("TPEX source empty, continuing with TWSE snapshot.")

    # ── 日期與主資料來源決策 ──────────────────────────────────────────
    # TWSE STOCK_DAY_ALL 通常在收盤後 1-2 小時才發布當日資料（盤中常見延遲）。
    # twse_date < today → 改用 Yahoo Finance 取得約 15 分鐘延遲的即時報價。
    # twse_date == today → TWSE 已更新，直接使用（官方收盤資料最權威）。
    twse_is_stale = bool(twse_date and twse_date < today)

    if twse_is_stale:
        logger.info(
            "TWSE stale (%s < %s): fetching Yahoo Finance as intraday fallback.",
            twse_date, today,
        )
        yahoo_records, yahoo_date = fetch_yahoo_quotes(twse)
        if yahoo_records:
            # Yahoo Finance 取得今日報價，TWSE 舊資料填補排名 500 以外的股票
            yahoo_by_id = {r["stock_id"]: r for r in yahoo_records}
            primary_records = [
                yahoo_by_id.get(r["stock_id"], r)  # 前500用Yahoo；其餘保留TWSE舊價
                for r in twse
            ]
            date_to_store = yahoo_date or today
            logger.info(
                "Yahoo Finance OK: %d updated + %d stale fill-ins, date=%s",
                len(yahoo_records), len(primary_records) - len(yahoo_records), date_to_store,
            )
        else:
            logger.warning("Yahoo Finance failed; using stale TWSE data (date=%s).", twse_date)
            primary_records = twse
            date_to_store = twse_date or today
    else:
        primary_records = twse
        date_to_store = twse_date or today

    if date_to_store != today:
        logger.info("Storing under trading date %s (scheduler date: %s)", date_to_store, today)

    records = merge_and_rank(primary_records, tpex, issue_shares)
    logger.info("Merged %d stocks", len(records))

    if len(records) < MIN_VALID_RECORDS and not is_closing:
        logger.warning(
            "Merged records too small (%d < %d). Skip overwrite to avoid degraded snapshot.",
            len(records),
            MIN_VALID_RECORDS,
        )
        return

    total_volume = sum(r.get("volume", 0) or 0 for r in records)
    if total_volume == 0:
        logger.warning("Total volume = 0 — non-trading data. Skipping DB write.")
        return

    with Session() as session:
        _upsert(session, records, date_to_store)

    logger.info("Crawl job done. %d records upserted for %s.", len(records), date_to_store)


def score_job() -> None:
    """Fetch buy scores for today's stocks and write to JSON cache.

    Runs at 16:05 — 5 minutes after the closing crawl — so StockAnalysisDashBoard
    has already cached today's scores, meaning no additional FinMind tokens are
    consumed by this call.
    """
    now = datetime.now(tz=TZ_TAIPEI)
    today = now.strftime("%Y-%m-%d")
    logger.info("score_job started at %s", now.isoformat())

    with Session() as session:
        rows = session.execute(
            text(
                "SELECT stock_id FROM stock_ranks WHERE date = :date "
                "ORDER BY volume_rank ASC LIMIT 300"
            ),
            {"date": today},
        ).fetchall()

    stock_ids = [r[0] for r in rows]
    if not stock_ids:
        logger.warning("score_job: no stocks in DB for %s, skipping", today)
        return

    logger.info("score_job: fetching scores for %d stocks", len(stock_ids))
    scores = batch_fetch_scores(stock_ids)
    write_scores(scores, today)
    logger.info("score_job done: %d/%d stocks scored", len(scores), len(stock_ids))


def daily_reset_job() -> None:
    clear_cache()
    refresh_sector_map_job()
    logger.info("Cache cleared for new trading day.")


if __name__ == "__main__":
    # 啟動時立即抓一次最新資料，避免容器重啟後要等到下個 cron trigger 才有資料。
    # is_closing=True 繞過盤中時間限制，週末 / 盤後均可執行（total_volume=0 保護仍有效）。
    logger.info("Performing startup fetch to load latest available data...")
    try:
        crawl_job(is_closing=True)
    except Exception as exc:
        logger.error("Startup fetch failed (non-fatal): %s", exc)

    scheduler = BlockingScheduler(timezone=TZ_TAIPEI)

    # 盤中：09:00-12:59 每分鐘一次
    scheduler.add_job(
        crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-12",
        minute="*",
        kwargs={"is_closing": False},
        id="crawl_intraday",
        misfire_grace_time=120,
        jitter=8,
    )

    # 盤中延伸：13:00-13:30 每分鐘一次
    scheduler.add_job(
        crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=13,
        minute="0-30",
        kwargs={"is_closing": False},
        id="crawl_intraday_1330",
        misfire_grace_time=120,
        jitter=8,
    )

    # 收盤後最終一次：16:00
    scheduler.add_job(
        crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=0,
        kwargs={"is_closing": True},
        id="crawl_close",
        misfire_grace_time=180,
        jitter=20,
    )

    # 每日 08:55 重置 cache
    scheduler.add_job(
        daily_reset_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8,
        minute=55,
        id="daily_reset",
    )

    # 收盤後 16:05 抓買入評分（StockAnalysisDashBoard 已快取，不耗 FinMind token）
    scheduler.add_job(
        score_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=5,
        id="score_daily",
        misfire_grace_time=300,
    )

    logger.info("Crawler scheduler started. Market hours: 09:00-13:30, poll every 60s.")
    scheduler.start()
