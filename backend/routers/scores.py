"""
scores.py — GET /api/scores

Serves buy scores from the most recent JSON file written by the crawler's
score_job (runs at 16:05 on trading days). Falls back gracefully to an
empty response when no scores file is present.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
SCORES_DIR = Path(os.getenv("SCORES_DIR", "/app/data/buy_scores"))

# Memory cache invalidated daily: {"loaded_date": str, "payload": dict}
_cache: dict = {}


def _load() -> dict:
    """Load scores from the most recent JSON file. Cached per calendar day."""
    global _cache

    today = datetime.now(tz=TZ_TAIPEI).strftime("%Y-%m-%d")
    if _cache.get("loaded_date") == today:
        return _cache["payload"]

    if not SCORES_DIR.exists():
        return {}

    for f in sorted(SCORES_DIR.glob("*.json"), reverse=True):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            payload = {
                "date": raw.get("date", ""),
                "generated_at": raw.get("generated_at", ""),
                "scores": raw.get("scores", {}),
            }
            _cache = {"loaded_date": today, "payload": payload}
            logger.info("Loaded buy scores from %s (%d stocks)", f.name, len(payload["scores"]))
            return payload
        except Exception as exc:
            logger.warning("Skipping corrupt scores file %s: %s", f, exc)

    return {}


@router.get("/scores")
def get_scores():
    """Return all buy scores from the most recent crawler cache file."""
    data = _load()
    if not data:
        return JSONResponse(content={"date": "", "scores": {}})
    return JSONResponse(content=data)
