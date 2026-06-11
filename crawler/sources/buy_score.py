"""
buy_score.py — Daily buy score batch fetcher (native computation)

Computes buy scores for tracked stocks directly via the local engine
(sources/buy_score_engine.py → FinMind), with no dependency on any external
HTTP service. Results are written to a dated JSON file under SCORES_DIR (shared
volume with backend).

Rate-limit strategy (分時 + 額度耗盡續抓):
  - REQUEST_DELAY seconds between stocks; the engine also staggers each FinMind
    dataset call by BUY_SCORE_FETCH_DELAY.
  - When FinMind quota is exhausted (FinMindError, HTTP 402) the batch writes
    the partial result, sleeps BUY_SCORE_QUOTA_WAIT_S (default 1 h), then resumes
    with only the still-unscored stocks. Repeats up to BUY_SCORE_QUOTA_MAX_CYCLES
    (default 24, ≈ one day).
  - A stock whose data all fails to fetch (no analyzable criterion) is NOT
    persisted as a misleading 0/24 — it returns None (frontend shows N/A) and is
    retried on the next quota cycle.
"""

import json
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sources.buy_score_engine import compute_buy_score
from sources.finmind_client import FinMindError

logger = logging.getLogger(__name__)

SCORES_DIR = Path(os.getenv("SCORES_DIR", "/app/data/buy_scores"))
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")
TZ_TAIPEI = ZoneInfo("Asia/Taipei")
REQUEST_DELAY = float(os.getenv("BUY_SCORE_REQUEST_DELAY", "1.2"))
# Quota-exhaustion resume: wait this long then continue with unscored stocks.
QUOTA_WAIT_S = float(os.getenv("BUY_SCORE_QUOTA_WAIT_S", "3600"))
QUOTA_MAX_CYCLES = int(os.getenv("BUY_SCORE_QUOTA_MAX_CYCLES", "24"))
MAX_KEEP_DAYS = 7


def fetch_buy_score(stock_id: str, token: str | None = None) -> dict | None:
    """Compute buy score for one stock natively.

    Returns {"score": int, "max_score": int} or None on failure.
    Raises FinMindError when FinMind quota is exhausted so the batch caller can
    pause and resume later — non-quota failures degrade to None.

    A result with no analyzable criterion (eligible_count == 0, i.e. every data
    fetch failed) is treated as a failure (None), not persisted as 0/24.
    """
    try:
        result = compute_buy_score(stock_id, token=token if token is not None else FINMIND_TOKEN)
    except FinMindError:
        raise
    except Exception as exc:
        logger.warning("buy_score %s: %s", stock_id, exc)
        return None

    max_score = result.get("max_score")
    if not max_score or result.get("eligible_count", 0) == 0:
        logger.info(
            "buy_score %s: no analyzable data (max_score=%s, eligible=%s) — skip",
            stock_id, max_score, result.get("eligible_count"),
        )
        return None
    return {"score": result.get("score"), "max_score": max_score}


def batch_fetch_scores(
    stock_ids: list[str],
    on_batch: Callable[[dict[str, dict]], None] | None = None,
    batch_size: int = 50,
    token: str | None = None,
) -> dict[str, dict]:
    """Compute buy scores for all stocks sequentially with REQUEST_DELAY pacing.

    Quota-aware: on FinMindError (HTTP 402) the current progress is flushed via
    on_batch, then the batch sleeps QUOTA_WAIT_S and resumes with the stocks not
    yet scored — up to QUOTA_MAX_CYCLES cycles.

    on_batch: optional callback invoked with the accumulated scores dict every
    batch_size successes (and at the end of each pass) for incremental persistence.
    """
    if not stock_ids:
        return {}

    token = token if token is not None else FINMIND_TOKEN
    scores: dict[str, dict] = {}
    total = len(stock_ids)

    for cycle in range(1, QUOTA_MAX_CYCLES + 1):
        pending = [sid for sid in stock_ids if sid not in scores]
        if not pending:
            break

        if cycle > 1:
            logger.info(
                "buy_score cycle %d/%d: resuming %d unscored stocks",
                cycle, QUOTA_MAX_CYCLES, len(pending),
            )

        quota_hit = False
        for i, sid in enumerate(pending):
            try:
                result = fetch_buy_score(sid, token=token)
            except FinMindError as exc:
                logger.warning(
                    "buy_score quota exhausted at %s (cycle %d, %d/%d scored): %s",
                    sid, cycle, len(scores), total, exc,
                )
                quota_hit = True
                break

            if result is not None:
                scores[sid] = result
            logger.info("buy_score %d/%d  ok=%d  id=%s", i + 1, len(pending), len(scores), sid)

            if on_batch is not None and (len(scores) % batch_size == 0 or i == len(pending) - 1):
                on_batch(scores)

            if i < len(pending) - 1:
                time.sleep(REQUEST_DELAY)

        # Flush whatever we have at the end of this pass.
        if on_batch is not None:
            on_batch(scores)

        if not quota_hit:
            # Full pass completed; any remaining stocks are non-quota failures
            # (shown as N/A) and are not retried.
            break

        if len([sid for sid in stock_ids if sid not in scores]) == 0:
            break

        logger.info(
            "buy_score: quota wait %.0fs before resuming (cycle %d/%d, %d/%d scored)",
            QUOTA_WAIT_S, cycle, QUOTA_MAX_CYCLES, len(scores), total,
        )
        time.sleep(QUOTA_WAIT_S)

    logger.info("batch_fetch_scores done: %d/%d stocks scored", len(scores), total)
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
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
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


def load_scores_for_date(date: str) -> dict:
    """Return the scores dict for a specific date, or {} if not available."""
    path = SCORES_DIR / f"{date}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("scores", {})
    except Exception:
        return {}


def _prune_old(directory: Path, keep: int) -> None:
    files = sorted(directory.glob("*.json"), reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
            logger.info("Pruned old buy scores: %s", old)
        except Exception:
            pass
