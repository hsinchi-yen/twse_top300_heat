from datetime import datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.stock import StockRank, SectorMap
from services.ranker import SECTORS

router = APIRouter()

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(16, 30)


def _is_market_open() -> bool:
    now = datetime.now(tz=TZ_TAIPEI).time()
    return MARKET_OPEN <= now <= MARKET_CLOSE


@router.get("/stocks/top100")
def get_top100(
    mode: str = Query(default="volume", pattern="^(volume|turnover)$"),
    db: Session = Depends(get_db),
):
    today = datetime.now(tz=TZ_TAIPEI).strftime("%Y-%m-%d")

    # Fetch all stocks for today
    stocks = db.query(StockRank).filter(StockRank.date == today).all()

    # Sort by mode
    if mode == "volume":
        stocks.sort(key=lambda s: s.volume_rank or 9999)
    else:
        stocks.sort(key=lambda s: s.turnover_rank or 9999)

    # Take top 100
    top100 = stocks[:100]

    # Build sector map lookup
    sector_lookup: dict[str, str] = {
        row.stock_id: row.sector
        for row in db.query(SectorMap).all()
    }

    # Group by sector
    sector_groups: dict[str, list] = {s: [] for s in SECTORS}
    sector_groups["其他"] = []

    for stock in top100:
        sector = sector_lookup.get(stock.stock_id, "其他")
        if sector not in sector_groups:
            sector = "其他"
        sector_groups[sector].append({
            "stock_id": stock.stock_id,
            "name": stock.name,
            "rank": stock.volume_rank if mode == "volume" else stock.turnover_rank,
            "volume": stock.volume,
            "turnover_rate": stock.turnover_rate,
            "price_change_pct": stock.price_change_pct,
            "color_tier": stock.color_tier,
        })

    sectors_out = [
        {"name": name, "stocks": stocks_list}
        for name, stocks_list in sector_groups.items()
        if stocks_list  # skip empty sectors
    ]

    return {
        "mode": mode,
        "date": today,
        "market_open": _is_market_open(),
        "updated_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        "sectors": sectors_out,
    }
