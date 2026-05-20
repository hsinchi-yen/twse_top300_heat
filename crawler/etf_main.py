"""
etf_main.py — Standalone ETF crawler with APScheduler

Schedule:
  - 09:05 daily (Mon-Fri): fetch daily prices, NAV, outstanding units from TWSE
  - 16:05 daily (Mon-Fri): refresh after market close (final NAV + prices)
  - 08:50 daily (Mon-Fri): refresh Yahoo asset scale (slow-changing, daily once)

Asset scale from Yahoo is fetched once per day (slow-changing).
TWSE data is fetched at open + close.

Usage:
  python etf_main.py            # blocking scheduler
  python etf_main.py --once     # single run (for testing)
"""

from __future__ import annotations
import argparse
import logging
import os
import random
import time as _time
from datetime import datetime, time

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from zoneinfo import ZoneInfo

from sources.etf_twse  import fetch_etf_daily, fetch_etf_nav, fetch_etf_outstanding_units
from sources.etf_yahoo import fetch_etf_asset_scale
from sources.yahoo     import fetch_yahoo_quotes
from etf_processor     import merge_etf_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/twse_heat.db")
TZ_TAIPEI    = ZoneInfo("Asia/Taipei")
MARKET_CLOSE = time(13, 30)
ETF_KEEP_DAYS = int(os.getenv("ETF_KEEP_DAYS", "90"))

engine  = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)

# Cache Yahoo asset scale for the day (expensive scrape)
_asset_scale_cache: dict[str, float] = {}
_asset_scale_date: str = ""


def _ensure_table() -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS etf_ranks (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                etf_id            TEXT NOT NULL,
                name              TEXT NOT NULL,
                date              TEXT NOT NULL,
                etf_type          TEXT DEFAULT '國內股',
                tracking_index    TEXT DEFAULT '',
                management_fee    REAL,
                asset_scale       REAL,
                outstanding_units REAL,
                volume            INTEGER,
                turnover_rate     REAL,
                close_price       REAL,
                price_change_pct  REAL,
                nav               REAL,
                premium_discount  REAL,
                portfolio_turnover REAL,
                color_tier        TEXT DEFAULT 'neutral',
                turnover_rank     INTEGER,
                asset_scale_rank  INTEGER,
                UNIQUE(etf_id, date)
            )
        """))
        # Add portfolio_turnover to existing tables that predate this column
        try:
            conn.execute(text("ALTER TABLE etf_ranks ADD COLUMN portfolio_turnover REAL"))
        except Exception:
            pass  # column already exists
        conn.commit()


def _upsert(session, records: list[dict], date: str) -> None:
    for r in records:
        session.execute(
            text("""
                INSERT INTO etf_ranks
                    (etf_id, name, date, etf_type, tracking_index, management_fee,
                     asset_scale, outstanding_units, volume, turnover_rate,
                     close_price, price_change_pct, nav, premium_discount,
                     portfolio_turnover, color_tier, turnover_rank, asset_scale_rank)
                VALUES
                    (:etf_id, :name, :date, :etf_type, :tracking_index, :management_fee,
                     :asset_scale, :outstanding_units, :volume, :turnover_rate,
                     :close_price, :price_change_pct, :nav, :premium_discount,
                     :portfolio_turnover, :color_tier, :turnover_rank, :asset_scale_rank)
                ON CONFLICT(etf_id, date) DO UPDATE SET
                    etf_type=excluded.etf_type,
                    tracking_index=excluded.tracking_index,
                    management_fee=excluded.management_fee,
                    portfolio_turnover=excluded.portfolio_turnover,
                    color_tier=excluded.color_tier,
                    close_price=COALESCE(excluded.close_price, etf_ranks.close_price),
                    price_change_pct=COALESCE(excluded.price_change_pct, etf_ranks.price_change_pct),
                    volume=COALESCE(excluded.volume, etf_ranks.volume),
                    outstanding_units=COALESCE(excluded.outstanding_units, etf_ranks.outstanding_units),
                    turnover_rate=COALESCE(excluded.turnover_rate, etf_ranks.turnover_rate),
                    nav=COALESCE(excluded.nav, etf_ranks.nav),
                    premium_discount=COALESCE(excluded.premium_discount, etf_ranks.premium_discount),
                    asset_scale=COALESCE(excluded.asset_scale, etf_ranks.asset_scale),
                    turnover_rank=excluded.turnover_rank,
                    asset_scale_rank=excluded.asset_scale_rank
            """),
            {**r, "date": date},
        )
    session.commit()


def _get_asset_scale(today: str) -> dict[str, float]:
    global _asset_scale_cache, _asset_scale_date
    if _asset_scale_date == today and _asset_scale_cache:
        logger.info("Using cached Yahoo asset scale (%d records)", len(_asset_scale_cache))
        return _asset_scale_cache
    asset_map = fetch_etf_asset_scale()
    if asset_map:
        _asset_scale_cache = asset_map
        _asset_scale_date  = today
    return _asset_scale_cache


def etf_crawl_job(is_closing: bool = False) -> None:
    now   = datetime.now(tz=TZ_TAIPEI)
    today = now.strftime("%Y-%m-%d")

    if not is_closing and now.time() > MARKET_CLOSE:
        logger.info("Market closed, skipping intraday ETF crawl")
        return

    logger.info("ETF crawl started (closing=%s)", is_closing)

    daily, trading_date = fetch_etf_daily()
    if not daily:
        logger.warning("No ETF daily data from TWSE; skipping.")
        return

    _time.sleep(random.uniform(1.5, 3.0))
    nav_map = fetch_etf_nav()

    _time.sleep(random.uniform(1.5, 3.0))
    outstanding_map = fetch_etf_outstanding_units()

    # ── Yahoo Finance fallback（盤中 TWSE 資料尚未更新今日）─────────────────
    # 與 main.py 相同機制：TWSE 資料日期 < 今日 → 用 Yahoo 取得即時 ETF 報價
    etf_is_stale = bool(trading_date and trading_date < today)
    if etf_is_stale:
        logger.info(
            "TWSE ETF stale (%s < %s): fetching Yahoo Finance intraday fallback.",
            trading_date, today,
        )
        # yahoo.py 需要 stock_id 欄位，將 etf_id 對應過去
        proxy = [{"stock_id": r["etf_id"], "name": r["name"], "volume": r.get("volume", 0)} for r in daily]
        yahoo_records, yahoo_date = fetch_yahoo_quotes(proxy)
        if yahoo_records:
            yahoo_by_id = {r["stock_id"]: r for r in yahoo_records}
            for r in daily:
                ya = yahoo_by_id.get(r["etf_id"])
                if ya:
                    r["volume"]           = ya["volume"]
                    r["close_price"]      = ya["close_price"]
                    r["price_change_pct"] = ya["price_change_pct"]
            date_to_store = yahoo_date or today
            logger.info("Yahoo Finance ETF OK: %d updated, date=%s", len(yahoo_records), date_to_store)
        else:
            logger.warning("Yahoo Finance ETF failed; using stale TWSE data (date=%s).", trading_date)
            date_to_store = trading_date or today
    else:
        date_to_store = trading_date or today

    asset_map = _get_asset_scale(today)

    records = merge_etf_data(daily, outstanding_map, nav_map, asset_map)
    logger.info("ETF merged: %d records for %s", len(records), date_to_store)

    with Session() as session:
        _upsert(session, records, date_to_store)

    logger.info("ETF crawl done: %d records upserted for %s", len(records), date_to_store)


def prune_old_etf_ranks(keep_days: int = ETF_KEEP_DAYS) -> None:
    """Delete etf_ranks rows older than keep_days distinct trading dates."""
    with Session() as session:
        result = session.execute(
            text("""
                SELECT date FROM etf_ranks
                GROUP BY date
                ORDER BY date DESC
                LIMIT 1 OFFSET :offset
            """),
            {"offset": keep_days},
        ).fetchone()
        if not result:
            return
        cutoff = result[0]
        deleted = session.execute(
            text("DELETE FROM etf_ranks WHERE date <= :cutoff"),
            {"cutoff": cutoff},
        ).rowcount
        session.commit()
    if deleted:
        logger.info("Pruned %d etf_rank rows older than %s", deleted, cutoff)


def asset_scale_refresh_job() -> None:
    """Refresh Yahoo asset scale cache at market open."""
    today = datetime.now(tz=TZ_TAIPEI).strftime("%Y-%m-%d")
    global _asset_scale_cache, _asset_scale_date
    logger.info("Refreshing Yahoo ETF asset scale...")
    asset_map = fetch_etf_asset_scale()
    if asset_map:
        _asset_scale_cache = asset_map
        _asset_scale_date  = today
        logger.info("Asset scale refreshed: %d records", len(asset_map))
    else:
        logger.warning("Yahoo asset scale refresh returned empty; using previous cache.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    _ensure_table()

    if args.once:
        logger.info("Single-run mode")
        etf_crawl_job(is_closing=True)
        raise SystemExit(0)

    # 啟動時立即抓取最新資料，避免容器重啟後要等到下一個 cron 才有資料
    logger.info("Performing startup ETF fetch to load latest available data...")
    try:
        etf_crawl_job(is_closing=True)
    except Exception as exc:
        logger.error("Startup ETF fetch failed (non-fatal): %s", exc)

    scheduler = BlockingScheduler(timezone=TZ_TAIPEI)

    # 盤中：09:00-12:59 每分鐘一次（與 main.py 相同機制）
    scheduler.add_job(
        etf_crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-12",
        minute="*",
        kwargs={"is_closing": False},
        id="etf_intraday",
        misfire_grace_time=120,
        jitter=10,
    )

    # 盤中延伸：13:00-13:30 每分鐘一次
    scheduler.add_job(
        etf_crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=13,
        minute="0-30",
        kwargs={"is_closing": False},
        id="etf_intraday_1330",
        misfire_grace_time=120,
        jitter=10,
    )

    # 收盤後最終一次：16:05（NAV 約 16:00 公布）
    scheduler.add_job(
        etf_crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16, minute=5,
        kwargs={"is_closing": True},
        id="etf_close",
        misfire_grace_time=180,
        jitter=20,
    )

    # Yahoo 資產規模每日 08:50 更新一次（變動緩慢）
    scheduler.add_job(
        asset_scale_refresh_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8, minute=50,
        id="etf_asset_scale",
        misfire_grace_time=120,
    )

    # 每月1日 02:30 修剪舊 ETF 歷史資料（保留 ETF_KEEP_DAYS 交易日）
    scheduler.add_job(
        prune_old_etf_ranks,
        trigger="cron",
        day=1,
        hour=2, minute=30,
        id="etf_prune",
        misfire_grace_time=86400,
    )

    logger.info(
        "ETF crawler scheduler started. Intraday: 09:00-13:30 every 60s, "
        "close@16:05, asset_scale@08:50, prune@01-02:30"
    )
    scheduler.start()
