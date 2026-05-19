"""
buy_score.py — Daily buy score batch fetcher

Fetches buy scores for all tracked stocks by proxying to StockAnalysisDashBoard
(/api/stocks/{stock_id}/buy_score). Results written to a dated JSON file under
SCORES_DIR (shared volume with backend). No FinMind tokens consumed here —
StockAnalysisDashBoard handles its own caching.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

STOCK_ANALYSIS_URL = os.getenv("STOCK_ANALYSIS_URL", "http://host.docker.internal:18000")
SCORES_DIR = Path(os.getenv("SCORES_DIR", "/app/data/buy_scores"))
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
TZ_TAIPEI = ZoneInfo("Asia/Taipei")
REQUEST_DELAY = float(os.getenv("BUY_SCORE_REQUEST_DELAY", "1.2"))
REQUEST_TIMEOUT = float(os.getenv("BUY_SCORE_TIMEOUT", "30.0"))
MAX_KEEP_DAYS = 7


def fetch_buy_score(stock_id: str) -> dict | None:
    """Fetch buy score for one stock from StockAnalysisDashBoard.

    Returns {"score": int, "max_score": int} or None on any failure.
    Passes FINMIND_TOKEN via X-FinMind-Token header if available.
    """
    url = f"{STOCK_ANALYSIS_URL}/api/stocks/{stock_id}/buy_score"
    headers = {}
    if FINMIND_TOKEN:
        headers["X-FinMind-Token"] = FINMIND_TOKEN
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "score": data.get("score"),
                "max_score": data.get("max_score"),
            }
        logger.warning("buy_score %s: HTTP %d", stock_id, resp.status_code)
        return None
    except Exception as exc:
        logger.warning("buy_score %s: %s", stock_id, exc)
        return None


def batch_fetch_scores(stock_ids: list[str]) -> dict[str, dict]:
    """Fetch buy scores for all stocks sequentially with REQUEST_DELAY between calls."""
    if not stock_ids:
        return {}

    scores: dict[str, dict] = {}
    total = len(stock_ids)
    for i, sid in enumerate(stock_ids):
        result = fetch_buy_score(sid)
        if result is not None:
            scores[sid] = result
        logger.info("buy_score %d/%d  ok=%d  id=%s", i + 1, total, len(scores), sid)
        if i < total - 1:
            time.sleep(REQUEST_DELAY)
    return scores


def write_scores(scores: dict[str, dict], date: str) -> Path:
    """Write scores dict to SCORES_DIR/YYYY-MM-DD.json and prune old files."""
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date,
        "generated_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        "scores": scores,
    }
    path = SCORES_DIR / f"{date}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote buy scores: %d stocks → %s", len(scores), path)
    _prune_old(SCORES_DIR, MAX_KEEP_DAYS)
    return path


def load_latest_scores() -> dict:
    """Return the most recent scores payload dict, or {} if none available."""
    if not SCORES_DIR.exists():
        return {}
    for f in sorted(SCORES_DIR.glob("*.json"), reverse=True):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _prune_old(directory: Path, keep: int) -> None:
    files = sorted(directory.glob("*.json"), reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
            logger.info("Pruned old buy scores: %s", old)
        except Exception:
            pass
