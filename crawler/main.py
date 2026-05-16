"""
main.py — Crawler APScheduler entry point

排程邏輯：
  - 盤中（09:00-16:30 台灣時間）：每 60 秒執行一次
  - 收盤後 16:00：執行最終一次
"""

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from sources.twse import fetch_twse_daily
from sources.tpex import fetch_tpex_daily
from sources.finmind import fetch_issue_shares, clear_cache
from processor import merge_and_rank

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/twse_heat.db")
TZ_TAIPEI = ZoneInfo("Asia/Taipei")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


def _upsert(session, records: list[dict], date: str) -> None:
    for r in records:
        session.execute(
            text("""
                INSERT INTO stock_ranks
                    (stock_id, name, date, volume, turnover_rate, price_change_pct,
                     color_tier, volume_rank, turnover_rank)
                VALUES
                    (:stock_id, :name, :date, :volume, :turnover_rate, :price_change_pct,
                     :color_tier, :volume_rank, :turnover_rank)
                ON CONFLICT(stock_id, date) DO UPDATE SET
                    volume=excluded.volume,
                    turnover_rate=excluded.turnover_rate,
                    price_change_pct=excluded.price_change_pct,
                    color_tier=excluded.color_tier,
                    volume_rank=excluded.volume_rank,
                    turnover_rank=excluded.turnover_rank
            """),
            {**r, "date": date},
        )
    session.commit()


def crawl_job() -> None:
    now = datetime.now(tz=TZ_TAIPEI)
    today = now.strftime("%Y-%m-%d")
    logger.info("Crawl job started at %s", now.isoformat())

    twse = fetch_twse_daily()
    tpex = fetch_tpex_daily()
    issue_shares = fetch_issue_shares()

    records = merge_and_rank(twse, tpex, issue_shares)
    logger.info("Merged %d stocks", len(records))

    with Session() as session:
        _upsert(session, records, today)

    logger.info("Crawl job done. %d records upserted.", len(records))


def daily_reset_job() -> None:
    """每日 08:55 重置 FinMind cache，確保使用最新股本資料。"""
    clear_cache()
    logger.info("FinMind cache cleared for new trading day.")


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone=TZ_TAIPEI)

    # 每 60 秒執行（盤中 09:00-16:30）
    scheduler.add_job(
        crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-16",
        minute="*",
        second="0",
        id="crawl_intraday",
    )

    # 收盤後最終執行
    scheduler.add_job(
        crawl_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=35,
        id="crawl_close",
    )

    # 每日重置 cache
    scheduler.add_job(
        daily_reset_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8,
        minute=55,
        id="daily_reset",
    )

    logger.info("Crawler scheduler started.")
    scheduler.start()
