"""
scores.py — GET /api/scores

Serves buy scores from the most recent JSON file written by the crawler's
score_job. Score computation lives entirely in the crawler (native FinMind
engine); the backend only reads the shared JSON and, on force refresh, signals
the crawler via a flag file on the shared /app/data volume.

Contract:
  - GET /api/scores            → newest scores + {"fetching": <in progress?>}
  - GET /api/scores?force=true → write force-refresh flag for the crawler, then
                                 return current scores + {"fetching": true}
"""

import json
import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

SCORES_DIR = Path(os.getenv("SCORES_DIR", "/app/data/buy_scores"))
CACHE_MAX_AGE_DAYS = int(os.getenv("BUY_SCORE_CACHE_MAX_AGE_DAYS", "30"))

# Coordination flags shared with the crawler (see crawler/main.py).
FORCE_REFRESH_FLAG = SCORES_DIR / ".force_refresh"
SCORING_IN_PROGRESS_FLAG = SCORES_DIR / ".scoring_in_progress"

# Memory cache keyed by file mtime: {"mtime": float, "payload": dict}
_cache: dict = {}


def _load() -> dict:
    """Load scores from the most recent JSON file.

    Memory-cached by file mtime — auto-refreshes when the crawler rewrites the
    file (including progressive partial writes). Returns {} when no valid file
    exists or the newest is older than CACHE_MAX_AGE_DAYS.
    """
    global _cache

    if not SCORES_DIR.exists():
        return {}

    files = sorted(SCORES_DIR.glob("*.json"), reverse=True)
    if not files:
        return {}

    newest = files[0]
    mtime = newest.stat().st_mtime

    if (time.time() - mtime) / 86400 > CACHE_MAX_AGE_DAYS:
        return {}

    if _cache.get("mtime") == mtime:
        return _cache["payload"]

    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            payload = {
                "date": raw.get("date", ""),
                "generated_at": raw.get("generated_at", ""),
                "scores": raw.get("scores", {}),
            }
            _cache = {"mtime": mtime, "payload": payload}
            logger.info("Loaded buy scores from %s (%d stocks)", f.name, len(payload["scores"]))
            return payload
        except Exception as exc:
            logger.warning("Skipping corrupt scores file %s: %s", f, exc)

    return {}


def _is_fetching() -> bool:
    """True while the crawler is running (or has been asked to run) a refresh."""
    return SCORING_IN_PROGRESS_FLAG.exists() or FORCE_REFRESH_FLAG.exists()


def _request_force_refresh() -> None:
    """Write the force-refresh flag the crawler polls for (every minute)."""
    try:
        SCORES_DIR.mkdir(parents=True, exist_ok=True)
        FORCE_REFRESH_FLAG.write_text(str(time.time()), encoding="utf-8")
        logger.info("Force refresh requested — wrote %s", FORCE_REFRESH_FLAG)
    except Exception as exc:
        logger.warning("Failed to write force-refresh flag: %s", exc)


@router.get("/scores")
def get_scores(request: Request, force: bool = False):
    """Return buy scores. Computation is owned by the crawler.

    force=true signals the crawler to recompute all stocks; it does NOT block —
    the frontend polls /api/scores and picks up partial results as the crawler
    rewrites the JSON. Token is no longer required here (the crawler uses its own
    FINMIND_TOKEN); the X-FinMind-Token header is accepted but ignored.
    """
    if force and not _is_fetching():
        _request_force_refresh()

    data = _load()
    fetching = _is_fetching()

    if data:
        return JSONResponse(content={**data, "fetching": fetching})

    return JSONResponse(content={"date": "", "scores": {}, "fetching": fetching})
