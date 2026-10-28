"""
signals.py — GET /api/signals

Serves the crawler's nightly 籌碼 / 技術 indicators from stock_signals (table
created and owned by crawler/signals.py; a missing table means "not computed
yet"). above_ma20 / above_ma60 are derived here, null-safe. See SPEC.md.
"""

import hashlib
import json
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import get_db

router = APIRouter()

CACHE_TTL_SECONDS = int(os.getenv("SIGNALS_CACHE_TTL_SECONDS", "60"))

_FIELDS = [
    "close", "avg_volume_5d", "vol_ratio", "ma20", "ma60", "high_52w", "pct_from_52w_high",
    "inst_net_5d", "inst_streak", "foreign_net_1d", "trust_net_1d",
]
_EMPTY = {"date": "", "generated_at": "", "signals": {}}


def _above(close, ma):
    if close is None or ma is None:
        return None
    return close > ma


def _build(db: Session) -> dict:
    try:
        rows = db.execute(text(
            f"SELECT stock_id, date, generated_at, {', '.join(_FIELDS)} FROM stock_signals"
        )).mappings().all()
    except OperationalError:
        db.rollback()
        return dict(_EMPTY)
    if not rows:
        return dict(_EMPTY)

    signals = {}
    for r in rows:
        s = {f: r[f] for f in _FIELDS}
        s["above_ma20"] = _above(s["close"], s["ma20"])
        s["above_ma60"] = _above(s["close"], s["ma60"])
        signals[r["stock_id"]] = s
    return {
        "date": max(r["date"] or "" for r in rows),
        "generated_at": max(r["generated_at"] or "" for r in rows),
        "signals": signals,
    }


@router.get("/signals")
def get_signals(request: Request, db: Session = Depends(get_db)):
    payload = _build(db)
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    etag = f'W/"{digest}"'
    headers = {"ETag": etag, "Cache-Control": f"public, max-age={CACHE_TTL_SECONDS}"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=payload, headers=headers)
