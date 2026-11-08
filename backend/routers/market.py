"""
market.py — read-only analytics over the crawler's daily_bars / inst_flows.

  GET /api/stocks/{stock_id}/history   price + MA + institutional history
  GET /api/market/trend                breadth + sector rotation
  GET /api/market/backtest             technical setup validation
  GET /api/market/alert-counts         buy-score distribution + risk-rule hit history

These tables are created and owned by crawler/signals.py (and
crawler/score_summary.py for alert-counts); a missing table means
"not computed yet", so every route degrades to its empty state. Market results
change once per trading day, so they are memoized until the bars change — cheap
enough for the embedded host, where the full scan would otherwise run per request.
See SPEC.md.
"""

import hashlib
import json
import os
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import get_db
from models.stock import SectorMap
from services import market_analytics as ma

router = APIRouter()

CACHE_TTL_SECONDS = int(os.getenv("SIGNALS_CACHE_TTL_SECONDS", "60"))
BACKTEST_HORIZONS = (5, 20, 60)
MAX_BARS = 260

_memo: dict = {"fingerprint": None, "results": {}}
# uvicorn runs these routes in a threadpool. One lock keeps a request that started
# before a crawler commit from storing stale results over fresh ones, and stops
# parallel first requests from each scanning every bar on the embedded host.
_memo_lock = threading.Lock()


def clear_cache() -> None:
    with _memo_lock:
        _memo["fingerprint"] = None
        _memo["results"] = {}


def _json(request: Request, payload: dict):
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    etag = f'W/"{digest}"'
    headers = {"ETag": etag, "Cache-Control": f"public, max-age={CACHE_TTL_SECONDS}"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)


def _rows(db: Session, sql: str, **params) -> list:
    """Query a crawler-owned table; a missing table reads as empty.

    Only a missing table: a locked database must surface as an error, or an empty
    result would be memoized as if the market had no data.
    """
    try:
        return db.execute(text(sql), params).all()
    except OperationalError as exc:
        db.rollback()
        if "no such table" not in str(exc).lower():
            raise
        return []


def _fingerprint(db: Session):
    bars = _rows(db, "SELECT MAX(date), COUNT(*) FROM daily_bars")
    flows = _rows(db, "SELECT MAX(date) FROM inst_flows")
    if not bars or not bars[0][1]:
        return None
    return bars[0][0], bars[0][1], flows[0][0] if flows else None


def _load_bars(db: Session) -> dict:
    out: dict[str, list] = {}
    for stock_id, day, close, volume in _rows(
        db, "SELECT stock_id, date, close, volume FROM daily_bars ORDER BY stock_id, date"
    ):
        if close is not None and close > 0:
            out.setdefault(stock_id, []).append((day, close, volume))
    return out


def _load_flows(db: Session) -> dict:
    out: dict[str, list] = {}
    for stock_id, day, foreign, trust in _rows(
        db, "SELECT stock_id, date, foreign_net, trust_net FROM inst_flows ORDER BY stock_id, date"
    ):
        out.setdefault(stock_id, []).append((day, (foreign or 0) + (trust or 0)))
    return out


def _memoized(db: Session, key: tuple, compute) -> dict | None:
    """compute(bars) cached until the bars change; None when there are no bars."""
    fingerprint = _fingerprint(db)
    if fingerprint is None:
        return None
    with _memo_lock:
        if _memo["fingerprint"] != fingerprint:
            _memo["fingerprint"] = fingerprint
            _memo["results"] = {}
        if key not in _memo["results"]:
            _memo["results"][key] = compute(_load_bars(db))
        return _memo["results"][key]


@router.get("/stocks/{stock_id}/history")
def stock_history(
    stock_id: str,
    request: Request,
    days: int = Query(default=MAX_BARS, ge=20, le=MAX_BARS),
    db: Session = Depends(get_db),
):
    rows = _rows(
        db, "SELECT date, close, volume FROM daily_bars WHERE stock_id = :s ORDER BY date", s=stock_id
    )
    closes = [r[1] for r in rows]
    ma20 = ma.moving_average(closes, ma.MA_SHORT)
    ma60 = ma.moving_average(closes, ma.MA_LONG)
    bars = [
        {"date": r[0], "close": r[1], "volume": r[2], "ma20": m20, "ma60": m60}
        for r, m20, m60 in zip(rows, ma20, ma60)
    ][-days:]
    flows = [
        {"date": r[0], "foreign_net": r[1], "trust_net": r[2], "dealer_net": r[3]}
        for r in _rows(
            db,
            "SELECT date, foreign_net, trust_net, dealer_net FROM inst_flows WHERE stock_id = :s ORDER BY date",
            s=stock_id,
        )
    ]
    return _json(request, {
        "stock_id": stock_id,
        "date": bars[-1]["date"] if bars else "",
        "bars": bars,
        "flows": flows,
    })


@router.get("/market/trend")
def market_trend(
    request: Request,
    days: int = Query(default=60, ge=20, le=120),
    db: Session = Depends(get_db),
):
    def compute(bars: dict) -> dict:
        sectors = {r.stock_id: r.sector for r in db.query(SectorMap.stock_id, SectorMap.sector).all()}
        return {
            "date": max((rows[-1][0] for rows in bars.values() if rows), default=""),
            "universe": len(bars),
            "breadth": ma.breadth_series(bars, days),
            "sectors": ma.sector_rotation(bars, sectors, _load_flows(db)),
        }

    payload = _memoized(db, ("trend", days), compute)
    return _json(request, payload or {"date": "", "universe": 0, "breadth": [], "sectors": []})


@router.get("/market/backtest")
def market_backtest(
    request: Request,
    horizon: int = Query(default=20),
    db: Session = Depends(get_db),
):
    if horizon not in BACKTEST_HORIZONS:
        raise HTTPException(status_code=422, detail=f"horizon must be one of {BACKTEST_HORIZONS}")
    payload = _memoized(db, ("backtest", horizon), lambda bars: ma.backtest(bars, horizon))
    return _json(request, payload or {
        "date": "", "horizon": horizon, "periods": 0, "baseline": None, "setups": [],
    })


@router.get("/market/alert-counts")
def market_alert_counts(
    request: Request,
    days: int = Query(default=120, ge=5, le=400),
    db: Session = Depends(get_db),
):
    """Buy-score distribution and risk-rule hit counts per scoring date (crawler-owned).

    Small tables read directly: at most 400 rows plus their alert counts.
    """
    summary_rows = _rows(db, """
        SELECT date, scored, median, p10, p90, bins, partial FROM score_summary_daily
        ORDER BY date DESC LIMIT :days""", days=days)
    if not summary_rows:
        return _json(request, {"date": "", "summary": [], "alerts": []})
    summary_rows = list(reversed(summary_rows))
    dates = [r[0] for r in summary_rows]
    scored = {r[0]: r[1] for r in summary_rows}
    summary = [{"date": r[0], "scored": r[1], "median": r[2], "p10": r[3], "p90": r[4],
                "bins": json.loads(r[5]), "partial": bool(r[6])} for r in summary_rows]

    hits: dict[str, dict[str, int]] = {}
    for day, name, count in _rows(
        db, "SELECT date, name, count FROM score_alert_daily WHERE date >= :start", start=dates[0]
    ):
        hits.setdefault(name, {})[day] = count
    alerts = []
    for name in sorted(hits):
        counts = [hits[name].get(d, 0) for d in dates]   # no hits that day = 0, not a gap
        shares = [round(c / scored[d] * 100, 1) if scored[d] else None for c, d in zip(counts, dates)]
        alerts.append({"name": name, "counts": counts, "shares": shares})
    return _json(request, {"date": dates[-1], "summary": summary, "alerts": alerts})
