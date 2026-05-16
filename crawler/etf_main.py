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
from etf_processor     import merge_etf_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/twse_heat.db")
TZ_TAIPEI    = ZoneInfo("Asia/Taipei")
MARKET_CLOSE = time(13, 30)

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
                    asset_scale=excluded.asset_scale,
                    outstanding_units=excluded.outstanding_units,
                    volume=excluded.volume,
                    turnover_rate=excluded.turnover_rate,
                    close_price=excluded.close_price,
                    price_change_pct=excluded.price_change_pct,
                    nav=excluded.nav,
                    premium_discount=excluded.premium_discount,
                    portfolio_turnover=excluded.portfolio_turnover,
                    color_tier=excluded.color_tier,
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

    date_to_store = trading_date or today
    asset_map = _get_asset_scale(today)

    records = merge_etf_data(daily, outstanding_map, nav_map, asset_map)
    logger.info("ETF merged: %d records for %s", len(records), date_to_store)

    with Session() as session:
        _upsert(session, records, date_to_store)

    logger.info("ETF crawl done: %d records upserted for %s", len(records), date_to_store)


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

    scheduler = BlockingScheduler(timezone=TZ_TAIPEI)

    # Morning crawl: 09:05 (after market opens)
    scheduler.add_job(
        etf_crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=9, minute=5,
        kwargs={"is_closing": False},
        id="etf_open",
        misfire_grace_time=120,
        jitter=15,
    )

    # Closing crawl: 16:05 (final NAV published ~16:00)
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

    # Yahoo asset scale refresh: 08:50 daily
    scheduler.add_job(
        asset_scale_refresh_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8, minute=50,
        id="etf_asset_scale",
        misfire_grace_time=120,
    )

    logger.info("ETF crawler scheduler started. Jobs: open@09:05, close@16:05, asset_scale@08:50")
    scheduler.start()
