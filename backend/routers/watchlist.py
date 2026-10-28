"""
watchlist.py — 自選股 GET / PUT / DELETE /api/watchlist

Single-user, LAN deployment (no auth, same as the other routes). Each item
embeds a `quote` from the latest trading date in stock_ranks so the frontend can
render stocks outside the 600 display pool. See SPEC.md.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.stock import StockRank, SectorMap
from models.watchlist import WatchlistItem
from routers.stocks import _latest_data_date

router = APIRouter()

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
WATCHLIST_MAX = int(os.getenv("WATCHLIST_MAX", "30"))


class WatchlistUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=500)


def _quotes(db: Session, stock_ids: list[str]) -> dict[str, dict]:
    if not stock_ids:
        return {}
    rows = (
        db.query(
            StockRank.stock_id,
            StockRank.name,
            StockRank.volume_rank.label("rank"),
            StockRank.volume,
            StockRank.turnover_rate,
            StockRank.price_change_pct,
            StockRank.color_tier,
            StockRank.close_price,
            SectorMap.sector,
        )
        .outerjoin(SectorMap, SectorMap.stock_id == StockRank.stock_id)
        .filter(StockRank.date == _latest_data_date(db), StockRank.stock_id.in_(stock_ids))
        .all()
    )
    return {
        r.stock_id: {
            "stock_id": r.stock_id,
            "name": r.name,
            "rank": r.rank,
            "volume": r.volume,
            "turnover_rate": r.turnover_rate,
            "price_change_pct": r.price_change_pct,
            "color_tier": r.color_tier,
            "close_price": r.close_price,
            "sector": r.sector or "其他",
        }
        for r in rows
    }


def _item(row: WatchlistItem, quote: dict | None) -> dict:
    return {"stock_id": row.stock_id, "note": row.note, "added_at": row.added_at, "quote": quote}


@router.get("/watchlist")
def list_watchlist(db: Session = Depends(get_db)):
    rows = db.query(WatchlistItem).order_by(WatchlistItem.added_at.asc()).all()
    quotes = _quotes(db, [r.stock_id for r in rows])
    return {"items": [_item(r, quotes.get(r.stock_id)) for r in rows]}


@router.put("/watchlist/{stock_id}")
def put_watchlist(
    stock_id: str,
    body: WatchlistUpdate | None = Body(default=None),
    db: Session = Depends(get_db),
):
    quote = _quotes(db, [stock_id]).get(stock_id)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"{stock_id} not found on latest trading date")

    row = db.get(WatchlistItem, stock_id)
    if row is None:
        if db.query(WatchlistItem).count() >= WATCHLIST_MAX:
            raise HTTPException(status_code=409, detail=f"watchlist is full (max {WATCHLIST_MAX})")
        row = WatchlistItem(
            stock_id=stock_id,
            note="",
            added_at=datetime.now(tz=TZ_TAIPEI).isoformat(timespec="microseconds"),
        )
        db.add(row)
    if body is not None and body.note is not None:
        row.note = body.note
    db.commit()
    return _item(row, quote)


@router.delete("/watchlist/{stock_id}", status_code=204)
def delete_watchlist(stock_id: str, db: Session = Depends(get_db)):
    row = db.get(WatchlistItem, stock_id)
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=204)
