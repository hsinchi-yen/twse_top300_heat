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
from models.etf import ETFRank

router = APIRouter()

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
MARKET_OPEN  = time(9, 0)
MARKET_CLOSE = time(13, 30)
CACHE_TTL_SECONDS = float(os.getenv("ETF_CACHE_TTL_SECONDS", "60"))
_ETF_CACHE: dict[tuple[str, str], tuple[float, dict, str]] = {}


def _is_market_open() -> bool:
    now_dt = datetime.now(tz=TZ_TAIPEI)
    if now_dt.weekday() >= 5:
        return False
    return MARKET_OPEN <= now_dt.time() <= MARKET_CLOSE


def _latest_etf_date(db: Session) -> str:
    result = db.execute(
        text("""
            SELECT date FROM etf_ranks
            GROUP BY date
            HAVING MAX(volume) > 0
            ORDER BY date DESC
            LIMIT 1
        """)
    ).first()
    if result:
        return result[0]
    latest = db.query(func.max(ETFRank.date)).scalar()
    return latest or datetime.now(tz=TZ_TAIPEI).strftime("%Y-%m-%d")


@router.get("/etf")
def get_etf(
    request: Request,
    sort_by: str = Query(default="turnover", pattern="^(turnover|asset_scale)$"),
    limit: int = Query(default=300, ge=1, le=300),
    db: Session = Depends(get_db),
):
    query_date = _latest_etf_date(db)
    cache_key = (sort_by, query_date)
    now_ts = time_mod.monotonic()
    cached = _ETF_CACHE.get(cache_key)

    if cached and now_ts - cached[0] <= CACHE_TTL_SECONDS:
        _, cached_payload, cached_etag = cached
        if request.headers.get("if-none-match") == cached_etag:
            return Response(
                status_code=304,
                headers={"ETag": cached_etag,
                         "Cache-Control": f"public, max-age={int(CACHE_TTL_SECONDS)}"},
            )
        return JSONResponse(
            content=cached_payload,
            headers={"ETag": cached_etag,
                     "Cache-Control": f"public, max-age={int(CACHE_TTL_SECONDS)}"},
        )

    rank_col = ETFRank.turnover_rank if sort_by == "turnover" else ETFRank.asset_scale_rank

    rows = (
        db.query(ETFRank)
        .filter(ETFRank.date == query_date)
        .order_by(func.coalesce(rank_col, 9999).asc())
        .limit(limit)
        .all()
    )

    etfs_out = [
        {
            "etf_id":            r.etf_id,
            "name":              r.name,
            "etf_type":          r.etf_type,
            "tracking_index":    r.tracking_index,
            "management_fee":    r.management_fee,
            "asset_scale":       r.asset_scale,
            "outstanding_units": r.outstanding_units,
            "volume":            r.volume,
            "turnover_rate":     r.turnover_rate,
            "close_price":       r.close_price,
            "price_change_pct":  r.price_change_pct,
            "nav":               r.nav,
            "premium_discount":  r.premium_discount,
            "portfolio_turnover": r.portfolio_turnover,
            "color_tier":        r.color_tier,
            "turnover_rank":     r.turnover_rank,
            "asset_scale_rank":  r.asset_scale_rank,
        }
        for r in rows
    ]

    market_open = _is_market_open()
    etag_src = {
        "sort_by": sort_by,
        "date": query_date,
        "market_open": market_open,
        "etfs": etfs_out,
    }
    etag_hash = hashlib.sha1(
        json.dumps(etag_src, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    etag_value = f'W/"{etag_hash}"'

    if request.headers.get("if-none-match") == etag_value:
        return Response(
            status_code=304,
            headers={"ETag": etag_value,
                     "Cache-Control": f"public, max-age={int(CACHE_TTL_SECONDS)}"},
        )

    payload = {
        "sort_by":    sort_by,
        "date":       query_date,
        "market_open": market_open,
        "updated_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        "etfs":       etfs_out,
    }

    _ETF_CACHE[cache_key] = (now_ts, payload, etag_value)
    if len(_ETF_CACHE) > 8:
        oldest = min(_ETF_CACHE.items(), key=lambda x: x[1][0])[0]
        _ETF_CACHE.pop(oldest, None)

    return JSONResponse(
        content=payload,
        headers={"ETag": etag_value,
                 "Cache-Control": f"public, max-age={int(CACHE_TTL_SECONDS)}"},
    )
