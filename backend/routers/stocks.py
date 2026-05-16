from datetime import datetime, time
import hashlib
import json
import os
import time as time_mod
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from database import get_db
from models.stock import StockRank, SectorMap

router = APIRouter()

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(13, 30)   # 台股正式交易時間 09:00-13:30
CACHE_TTL_SECONDS = float(os.getenv("TOP100_CACHE_TTL_SECONDS", "3"))
_TOP100_CACHE: dict[tuple[str, int, str], tuple[float, dict, str]] = {}


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
    request: Request,
    mode: str = Query(default="volume", pattern="^(volume|turnover)$"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query_date = _latest_data_date(db)
    cache_key = (mode, limit, query_date)
    now_ts = time_mod.monotonic()
    cached = _TOP100_CACHE.get(cache_key)
    if cached and now_ts - cached[0] <= CACHE_TTL_SECONDS:
        _, cached_payload, cached_etag = cached
        if request.headers.get("if-none-match") == cached_etag:
            return Response(
                status_code=304,
                headers={
                    "ETag": cached_etag,
                    "Cache-Control": f"public, max-age={int(CACHE_TTL_SECONDS)}",
                },
            )
        return JSONResponse(
            content=cached_payload,
            headers={
                "ETag": cached_etag,
                "Cache-Control": f"public, max-age={int(CACHE_TTL_SECONDS)}",
            },
        )

    rank_col = StockRank.volume_rank if mode == "volume" else StockRank.turnover_rank

    ranked_rows = (
        db.query(
            StockRank.stock_id,
            StockRank.name,
            rank_col.label("rank"),
            StockRank.volume,
            StockRank.turnover_rate,
            StockRank.price_change_pct,
            StockRank.color_tier,
            StockRank.close_price,
            SectorMap.sector,
        )
        .outerjoin(SectorMap, SectorMap.stock_id == StockRank.stock_id)
        .filter(StockRank.date == query_date)
        .order_by(func.coalesce(rank_col, 9999).asc())
        .limit(limit)
        .all()
    )

    # Dynamic grouping — accept any sector name from sector_map (industry or custom theme)
    sector_groups: dict[str, list] = {}

    for row in ranked_rows:
        sector = row.sector or "其他"
        if sector not in sector_groups:
            sector_groups[sector] = []
        sector_groups[sector].append({
            "stock_id": row.stock_id,
            "name": row.name,
            "rank": row.rank,
            "volume": row.volume,
            "turnover_rate": row.turnover_rate,
            "price_change_pct": row.price_change_pct,
            "color_tier": row.color_tier,
            "close_price": row.close_price,
        })

    sectors_out = [
        {"name": name, "stocks": stocks_list}
        for name, stocks_list in sector_groups.items()
        if stocks_list
    ]

    etag_payload = {
        "mode": mode,
        "date": query_date,
        "market_open": _is_market_open(),
        "sectors": sectors_out,
    }
    etag_hash = hashlib.sha1(
        json.dumps(etag_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    etag_value = f'W/"{etag_hash}"'

    if request.headers.get("if-none-match") == etag_value:
        return Response(
            status_code=304,
            headers={
                "ETag": etag_value,
                "Cache-Control": f"public, max-age={int(CACHE_TTL_SECONDS)}",
            },
        )

    payload = {
        "mode": mode,
        "date": query_date,
        "market_open": etag_payload["market_open"],
        "updated_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        "sectors": sectors_out,
    }

    _TOP100_CACHE[cache_key] = (now_ts, payload, etag_value)
    if len(_TOP100_CACHE) > 16:
        # Keep cache size bounded for long-lived embedded processes.
        oldest_key = min(_TOP100_CACHE.items(), key=lambda item: item[1][0])[0]
        _TOP100_CACHE.pop(oldest_key, None)

    return JSONResponse(
        content=payload,
        headers={
            "ETag": etag_value,
            "Cache-Control": f"public, max-age={int(CACHE_TTL_SECONDS)}",
        },
    )
