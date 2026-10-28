"""
buy_score.py — Daily buy score batch fetcher (native computation)

Computes buy scores for tracked stocks directly via the local engine
(sources/buy_score_engine.py → FinMind), with no dependency on any external
HTTP service. Results are written to a dated JSON file under SCORES_DIR (shared
volume with backend).

Rate-limit strategy (分時 + 額度耗盡續抓):
  - REQUEST_DELAY seconds between stocks; the engine also staggers each FinMind
    dataset call by BUY_SCORE_FETCH_DELAY.
  - When FinMind quota is exhausted (FinMindError, HTTP 402) the batch raises
    QuotaExhaustedMidBatch; the CALLER (main.py) persists remaining stock IDs to
    .score_resume and reschedules via the watch job after QUOTA_WAIT_S (default 1 h).
    This is file-based and process-restart-resilient — no cycle count limit.
  - A stock whose data all fails to fetch (no analyzable criterion) is NOT
    persisted as a misleading 0/24 — it returns None (frontend shows N/A).
"""

import json
import logging
import math
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
# How long to wait after quota exhaustion before resuming (default: 1 hour).
# The wait is now managed externally (file-based) so this constant is used by
# the caller (main.py) rather than by batch_fetch_scores itself.
QUOTA_WAIT_S = float(os.getenv("BUY_SCORE_QUOTA_WAIT_S", "3600"))


class QuotaExhaustedMidBatch(Exception):
    """Raised by batch_fetch_scores when FinMind quota is hit mid-batch.

    remaining_ids: stocks not yet scored (quota-hit stock + all subsequent).
    scored:        scores accumulated before the quota hit.

    The caller should persist remaining_ids to disk and retry after QUOTA_WAIT_S
    seconds so the process can resume even after a container restart.
    """

    def __init__(self, remaining_ids: list[str], scored: dict):
        self.remaining_ids = remaining_ids
        self.scored = scored
        super().__init__(
            f"FinMind quota exhausted — {len(remaining_ids)} stocks remaining"
        )
MAX_KEEP_DAYS = 7

# Live recompute-progress for the current run. The dated JSON always carries the
# full 600-stock baseline during a force refresh, so the frontend cannot infer
# progress from it; this file reports how far the *current* job has advanced.
SCORE_PROGRESS_FLAG = SCORES_DIR / ".score_progress"


def write_progress(done: int, total: int) -> None:
    """Atomically record current-run progress for the backend/frontend to read."""
    try:
        SCORES_DIR.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "done": done,
            "total": total,
            "updated_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        })
        tmp = SCORES_DIR / ".score_progress.tmp"
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(SCORE_PROGRESS_FLAG)
    except Exception:
        pass


def clear_progress() -> None:
    """Remove the progress file once a run finishes (or is no longer active)."""
    SCORE_PROGRESS_FLAG.unlink(missing_ok=True)


def fetch_buy_score(stock_id: str, token: str | None = None) -> dict | None:
    """Compute buy score for one stock natively.

    Returns the summary entry (score, max_score, pass_rate, signal, risk_flags,
    pe, ...) plus a "detail" key holding criteria / risk_criteria, which
    write_scores splits into details/<date>.json. Returns None on failure.
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
    risk_criteria = result.get("risk_criteria") or []
    pe = result.get("pe") or {}
    return {
        "score": result.get("score"),
        "max_score": max_score,
        "fundamentals_uptrend": result.get("fundamentals_uptrend", False),
        "eligible_count": result.get("eligible_count"),
        "pass_rate": result.get("pass_rate"),
        "signal": result.get("signal"),
        "signal_label": result.get("signal_label"),
        "risk_score": result.get("risk_score", len(risk_criteria)),
        "risk_flags": [{"category": r.get("category"), "name": r.get("name")} for r in risk_criteria],
        "pe": {k: pe.get(k) for k in ("current", "median", "p25")},
        "detail": {
            "criteria": result.get("criteria") or [],
            "risk_criteria": risk_criteria,
        },
    }


def batch_fetch_scores(
    stock_ids: list[str],
    on_batch: Callable[[dict[str, dict]], None] | None = None,
    batch_size: int = 50,
    token: str | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, dict]:
    """Compute buy scores sequentially with REQUEST_DELAY pacing.

    On FinMindError (quota exhaustion): flushes accumulated progress via on_batch,
    then raises QuotaExhaustedMidBatch so the CALLER can persist the remaining
    stock IDs to disk and reschedule a resume after QUOTA_WAIT_S seconds.
    This keeps the function non-blocking and process-restart-resilient.

    on_batch: called with the full accumulated scores dict every batch_size
    successes and at the very end of the run (for incremental JSON persistence).
    """
    if not stock_ids:
        return {}

    token = token if token is not None else FINMIND_TOKEN
    scores: dict[str, dict] = {}
    total = len(stock_ids)

    for i, sid in enumerate(stock_ids):
        try:
            result = fetch_buy_score(sid, token=token)
        except FinMindError as exc:
            logger.warning(
                "buy_score quota exhausted at %s (%d/%d scored): %s",
                sid, len(scores), total, exc,
            )
            if on_batch is not None:
                on_batch(scores)
            remaining = [s for s in stock_ids[i:] if s not in scores]
            raise QuotaExhaustedMidBatch(remaining, scores) from exc

        if result is not None:
            scores[sid] = result
        logger.info("buy_score %d/%d  ok=%d  id=%s", i + 1, total, len(scores), sid)

        if on_progress is not None:
            on_progress(i + 1, total)

        if on_batch is not None and (len(scores) % batch_size == 0 or i == total - 1):
            on_batch(scores)

        if i < total - 1:
            time.sleep(REQUEST_DELAY)

    logger.info("batch_fetch_scores done: %d/%d stocks scored", len(scores), total)
    return scores


def _json_safe(obj):
    """Recursively coerce engine output to strict JSON.

    numpy scalars → Python numbers; NaN / ±Infinity → None. Browsers' JSON.parse
    and Starlette's JSONResponse (allow_nan=False) both reject non-finite floats.
    """
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            obj = obj.item()  # numpy scalar → Python scalar
        except Exception:
            return None
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def _details_dir() -> Path:
    # Resolved at call time so tests patching SCORES_DIR also redirect details.
    return SCORES_DIR / "details"


def _load_details_baseline(date: str) -> dict:
    """Details for `date` if present, else the newest details file (or {}).

    Partial writes merge new scores over a summary baseline that has no detail;
    this baseline lets carried-over stocks keep their previous detail.
    """
    d = _details_dir()
    if not d.exists():
        return {}
    dated = d / f"{date}.json"
    candidates = [dated] if dated.exists() else sorted(d.glob("*.json"), reverse=True)
    for f in candidates:
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def _atomic_write_json(path: Path, payload, indent: int | None = None) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=indent, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


def write_scores(scores: dict[str, dict], date: str) -> Path:
    """Write scores dict to SCORES_DIR/YYYY-MM-DD.json and prune old files.

    Each entry's optional "detail" is split into SCORES_DIR/details/<date>.json
    (written first, so a reader never sees a summary newer than its detail).
    """
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        sid: {k: v for k, v in entry.items() if k != "detail"}
        for sid, entry in scores.items()
    }
    new_details = {
        sid: entry["detail"] for sid, entry in scores.items()
        if isinstance(entry, dict) and entry.get("detail") is not None
    }
    details = {**_load_details_baseline(date), **new_details}
    details = {sid: d for sid, d in details.items() if sid in summary}
    if details:
        details_dir = _details_dir()
        details_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(details_dir / f"{date}.json", _json_safe(details))
        _prune_old(details_dir, MAX_KEEP_DAYS)

    payload = {
        "date": date,
        "generated_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        "scores": _json_safe(summary),
    }
    path = SCORES_DIR / f"{date}.json"
    _atomic_write_json(path, payload, indent=2)
    logger.info("Wrote buy scores: %d stocks (%d with detail) → %s", len(summary), len(details), path)
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
