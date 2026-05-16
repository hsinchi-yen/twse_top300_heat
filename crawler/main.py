"""
main.py — Crawler APScheduler entry point

排程邏輯（台股交易時間 09:00-13:30）：
  - 盤中：每 10 分鐘觸發（±90 秒 jitter），超過 13:30 自動 skip
  - 收盤後：13:35 執行最終一次（is_closing=True），之後不再拉取
  - 每日 08:55 重置 cache、補充 sector_map
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
from sources.finmind import fetch_issue_shares, fetch_industry_categories, clear_cache
from processor import merge_and_rank

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/twse_heat.db")
TZ_TAIPEI = ZoneInfo("Asia/Taipei")
MARKET_CLOSE = time(13, 30)

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


def crawl_job(is_closing: bool = False) -> None:
    now = datetime.now(tz=TZ_TAIPEI)
    today = now.strftime("%Y-%m-%d")

    # 盤中 job：超過 13:30 自動 skip，收盤 job 不受此限
    if not is_closing and now.time() > MARKET_CLOSE:
        logger.info("Market closed at %s, skipping intraday crawl", now.strftime("%H:%M"))
        return

    logger.info("Crawl job started at %s (closing=%s)", now.isoformat(), is_closing)

    # 各來源間加入隨機延遲，降低被識別為 bot 的機率
    twse, trading_date = fetch_twse_daily()
    _time.sleep(random.uniform(3.0, 6.0))    # inter-source delay
    tpex = fetch_tpex_daily()
    _time.sleep(random.uniform(2.0, 4.0))
    issue_shares = fetch_issue_shares()

    records = merge_and_rank(twse, tpex, issue_shares)
    logger.info("Merged %d stocks", len(records))

    total_volume = sum(r.get("volume", 0) or 0 for r in records)
    if total_volume == 0:
        logger.warning("Total volume = 0 — non-trading data. Skipping DB write.")
        return

    # 優先使用 TWSE API 回應中的實際交易日期（週末時為週五）
    date_to_store = trading_date or today
    if date_to_store != today:
        logger.info("Storing under API trading date %s (scheduler date: %s)", date_to_store, today)

    # 取得類股資訊（第一次呼叫時自動從 FinMind 載入）
    industry = fetch_industry_categories()

    with Session() as session:
        _ensure_sectors(session, industry)
        _upsert(session, records, date_to_store)

    logger.info("Crawl job done. %d records upserted for %s.", len(records), date_to_store)


def daily_reset_job() -> None:
    clear_cache()
    logger.info("Cache cleared for new trading day.")


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone=TZ_TAIPEI)

    # 盤中：每 10 分鐘一次（±90 秒 jitter），超過 13:30 由 crawl_job 內部 skip
    scheduler.add_job(
        crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-13",
        minute="0,10,20,30,40,50",
        kwargs={"is_closing": False},
        id="crawl_intraday",
        misfire_grace_time=180,
        jitter=90,
    )

    # 收盤後最終一次：13:35
    scheduler.add_job(
        crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=13,
        minute=35,
        kwargs={"is_closing": True},
        id="crawl_close",
        misfire_grace_time=180,
        jitter=60,
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

    logger.info("Crawler scheduler started. Market hours: 09:00-13:30, poll every 10 min.")
    scheduler.start()
