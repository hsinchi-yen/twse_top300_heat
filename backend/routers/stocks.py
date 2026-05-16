from datetime import datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from database import get_db
from models.stock import StockRank, SectorMap

router = APIRouter()

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(13, 30)   # 台股正式交易時間 09:00-13:30


def _is_market_open() -> bool:
    now_dt = datetime.now(tz=TZ_TAIPEI)
    if now_dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return MARKET_OPEN <= now_dt.time() <= MARKET_CLOSE


def _latest_data_date(db: Session) -> str:
    """
    回傳 DB 中最近一個有實際交易資料（volume > 0）的日期。
    週末/假日會讀到上週五收盤資料；避免把週六的零值資料當成最新。
    """
    result = db.execute(
        text("""
            SELECT date FROM stock_ranks
            GROUP BY date
            HAVING MAX(volume) > 0
            ORDER BY date DESC
            LIMIT 1
        """)
    ).first()
    if result:
        return result[0]
    # Fallback：DB 中只有零值資料時，回傳最新日期（前端會顯示空狀態）
    latest = db.query(func.max(StockRank.date)).scalar()
    return latest or datetime.now(tz=TZ_TAIPEI).strftime("%Y-%m-%d")


@router.get("/stocks/top100")
def get_top100(
    mode: str = Query(default="volume", pattern="^(volume|turnover)$"),
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query_date = _latest_data_date(db)

    stocks = db.query(StockRank).filter(StockRank.date == query_date).all()

    if mode == "volume":
        stocks.sort(key=lambda s: s.volume_rank or 9999)
    else:
        stocks.sort(key=lambda s: s.turnover_rank or 9999)

    top_stocks = stocks[:limit]

    sector_lookup: dict[str, str] = {
        row.stock_id: row.sector
        for row in db.query(SectorMap).all()
    }

    # Dynamic grouping — accept any sector name from sector_map (industry or custom theme)
    sector_groups: dict[str, list] = {}

    for stock in top_stocks:
        sector = sector_lookup.get(stock.stock_id, "其他") or "其他"
        if sector not in sector_groups:
            sector_groups[sector] = []
        sector_groups[sector].append({
            "stock_id": stock.stock_id,
            "name": stock.name,
            "rank": stock.volume_rank if mode == "volume" else stock.turnover_rank,
            "volume": stock.volume,
            "turnover_rate": stock.turnover_rate,
            "price_change_pct": stock.price_change_pct,
            "color_tier": stock.color_tier,
            "close_price": stock.close_price,
        })

    sectors_out = [
        {"name": name, "stocks": stocks_list}
        for name, stocks_list in sector_groups.items()
        if stocks_list
    ]

    return {
        "mode": mode,
        "date": query_date,
        "market_open": _is_market_open(),
        "updated_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        "sectors": sectors_out,
    }
