"""
scores.py — GET /api/scores

Serves buy scores from the most recent JSON file written by the crawler's
score_job (runs monthly). When cache is absent and a FinMind token is
supplied via X-FinMind-Token header, triggers a background fetch via
StockAnalysisDashBoard.

Background fetch writes partial results every BATCH_WRITE_SIZE stocks so the
frontend sees scores filling in progressively rather than waiting for completion.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
SCORES_DIR = Path(os.getenv("SCORES_DIR", "/app/data/buy_scores"))
METRICS_DIR = Path(os.getenv("METRICS_DIR", "/app/data/metrics"))
STOCK_ANALYSIS_URL = os.getenv("STOCK_ANALYSIS_URL", "http://host.docker.internal:18000")
BACKGROUND_DELAY = float(os.getenv("BUY_SCORE_BACKGROUND_DELAY", "1.2"))
REQUEST_TIMEOUT = float(os.getenv("BUY_SCORE_TIMEOUT", "30.0"))
CACHE_MAX_AGE_DAYS = int(os.getenv("BUY_SCORE_CACHE_MAX_AGE_DAYS", "30"))
BATCH_WRITE_SIZE = int(os.getenv("BUY_SCORE_BATCH_WRITE_SIZE", "50"))
# Candidate pool: configurable but hard-capped to prevent runaway token cost.
SCORE_CANDIDATE_LIMIT = min(int(os.getenv("SCORE_CANDIDATE_LIMIT", "480")), 1000)
# Exponential backoff: base 15 min, doubles each retry, max 2 h.
RATE_LIMIT_BASE_WAIT_S = int(os.getenv("BUY_SCORE_RATE_LIMIT_BASE_WAIT_S", "900"))
RATE_LIMIT_MAX_RETRIES = int(os.getenv("BUY_SCORE_MAX_RETRIES", "3"))
_RATE_LIMIT_THRESHOLD = 5

# Memory cache keyed by file mtime: {"mtime": float, "payload": dict}
_cache: dict = {}
_is_fetching: bool = False
_fetch_lock = threading.Lock()


def _load() -> dict:
    """Load scores from the most recent JSON file.

    Memory-cached by file mtime — auto-refreshes when the file is updated.
    Returns {} when no valid file exists or the newest is older than CACHE_MAX_AGE_DAYS.
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


def _write_partial(scores: dict, today: str) -> None:
    """Atomically write current accumulated scores to today's JSON file."""
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": today,
        "generated_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
        "scores": scores,
    }
    path = SCORES_DIR / f"{today}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _write_metrics(
    today: str,
    *,
    attempted: int,
    succeeded: int,
    failed: int,
    retries: int,
    elapsed_s: float,
    total_stocks: int,
) -> None:
    """Append a daily token cost record to METRICS_DIR/YYYY-MM-DD.json."""
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        coverage = round(succeeded / total_stocks, 4) if total_stocks else 0.0
        record = {
            "date": today,
            "recorded_at": datetime.now(tz=TZ_TAIPEI).isoformat(),
            "attempted": attempted,
            "succeeded": succeeded,
            "failed": failed,
            "retries": retries,
            "coverage": coverage,
            "elapsed_s": round(elapsed_s, 1),
        }
        path = METRICS_DIR / f"{today}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(
            "Metrics written: attempted=%d succeeded=%d failed=%d retries=%d "
            "coverage=%.1f%% elapsed=%.0fs",
            attempted, succeeded, failed, retries, coverage * 100, elapsed_s,
        )
    except Exception as exc:
        logger.warning("Failed to write metrics: %s", exc)


def _get_stock_ids(db: Session) -> List[str]:
    """Return stock_ids with volume_rank <= SCORE_CANDIDATE_LIMIT from the most recent DB date."""
    result = db.execute(
        text("""
            SELECT stock_id FROM stock_ranks
            WHERE date = (
                SELECT date FROM stock_ranks
                GROUP BY date HAVING SUM(volume) > 0
                ORDER BY date DESC LIMIT 1
            )
              AND volume_rank <= :limit
            ORDER BY volume_rank ASC
        """),
        {"limit": SCORE_CANDIDATE_LIMIT},
    )
    return [row[0] for row in result.fetchall()]


def _fetch_pass(
    pending: list,
    scores: dict,
    headers: dict,
    today: str,
    pass_num,
    total_original: int,
) -> tuple:
    """Single fetch pass over pending stock_ids.

    Returns (retry_ids, rate_limited):
    - retry_ids: ALL failed stock_ids this pass (scattered + consecutive).
    - rate_limited: True when 5+ consecutive failures triggered an early abort.

    Previously only rate-limit-triggered stocks were returned; scattered failures
    were silently dropped because a single success called failed_run.clear().
    Now all_failed is never cleared, so every failure surfaces for retry.
    """
    global _cache

    all_failed: list = []        # every failure — never cleared
    consecutive_fails: list = [] # consecutive streak only — cleared on success
    total = len(pending)

    for i, sid in enumerate(pending):
        url = f"{STOCK_ANALYSIS_URL}/api/stocks/{sid}/buy_score"
        try:
            resp = httpx.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                max_score = data.get("max_score")
                if max_score:
                    scores[sid] = {"score": data.get("score"), "max_score": max_score}
                consecutive_fails.clear()
            else:
                all_failed.append(sid)
                consecutive_fails.append(sid)
        except Exception as exc:
            logger.warning("buy_score %s: %s", sid, exc)
            all_failed.append(sid)
            consecutive_fails.append(sid)

        # Consecutive failure threshold → rate limit; abort pass early
        if len(consecutive_fails) >= _RATE_LIMIT_THRESHOLD:
            already_failed = set(all_failed)
            remaining = [s for s in pending[i + 1:] if s not in already_failed]
            retry_ids = all_failed + remaining
            logger.warning(
                "buy_score pass %s: rate limit after %d stocks (%d scored). "
                "Retry %d stocks after backoff.",
                pass_num, i + 1, len(scores), len(retry_ids),
            )
            _write_partial(scores, today)
            _cache = {}
            return retry_ids, True

        if (i + 1) % BATCH_WRITE_SIZE == 0 or i == total - 1:
            _write_partial(scores, today)
            _cache = {}
            logger.info(
                "buy_score pass %s — %d/%d processed, %d/%d scored",
                pass_num, i + 1, total, len(scores), total_original,
            )

        if i < total - 1:
            time.sleep(BACKGROUND_DELAY)

    return all_failed, False


def _background_score_fetch(token: str, stock_ids: List[str], force: bool = False) -> None:
    """Fetch scores with partial writes every BATCH_WRITE_SIZE stocks.

    force=False (default): pre-loads today's existing JSON and skips already-scored
    stocks so interrupted runs resume cleanly.
    force=True: starts from an empty scores dict so every stock is re-fetched fresh.
    Failed stocks surface as absent from the JSON (frontend shows N/A) rather than
    retaining stale scores from a previous run that may show misleading 0s.

    Rate-limit handling: on 5 consecutive non-200s, waits with exponential backoff
    (base RATE_LIMIT_BASE_WAIT_S * 2^(retry-1), max 2 h) then retries all failed
    stocks. Scattered individual failures (non-consecutive) are also tracked and
    included in the retry list — they are no longer silently dropped.
    After rate-limit retries are exhausted, any remaining individual failures get
    one short-wait retry before being given up as N/A.
    """
    global _is_fetching, _cache

    today = datetime.now(tz=TZ_TAIPEI).strftime("%Y-%m-%d")
    headers = {"X-FinMind-Token": token} if token else {}
    total = len(stock_ids)
    start_time = time.time()

    # force=True: start fresh — failed stocks become N/A, not stale 0s from old file.
    # force=False: resume from today's partial file so interrupted runs continue cleanly.
    scores: dict = {}
    if not force:
        today_file = SCORES_DIR / f"{today}.json"
        if today_file.exists():
            try:
                scores = json.loads(today_file.read_text(encoding="utf-8")).get("scores", {})
            except Exception:
                pass

    scored_before = len(scores)  # baseline: only count stocks newly scored this run

    pending = stock_ids if force else [sid for sid in stock_ids if sid not in scores]
    initial_pending = len(pending)

    if not pending:
        logger.info("Background fetch: all %d stocks already scored, skipping", total)
        with _fetch_lock:
            _is_fetching = False
        _cache = {}
        return

    logger.info(
        "Background fetch: %d/%d stocks pending (pre-loaded %d, force=%s)",
        initial_pending, total, scored_before, force,
    )

    retries_done = 0
    try:
        for attempt in range(1, RATE_LIMIT_MAX_RETRIES + 2):
            if attempt > 1:
                wait_s = min(RATE_LIMIT_BASE_WAIT_S * (2 ** (attempt - 2)), 7200)
                logger.info(
                    "buy_score retry %d/%d: waiting %ds before retrying %d stocks",
                    attempt - 1, RATE_LIMIT_MAX_RETRIES, wait_s, len(pending),
                )
                time.sleep(wait_s)
                retries_done += 1

            pending, rate_limited = _fetch_pass(pending, scores, headers, today, attempt, total)

            if not pending:
                break

            if not rate_limited:
                # Remaining stocks are scattered individual failures (not a rate-limit
                # event). Give them one short-wait retry before giving up.
                logger.info(
                    "buy_score: %d individual failures after pass %d, retrying shortly...",
                    len(pending), attempt,
                )
                time.sleep(BACKGROUND_DELAY * 3)
                pending, _ = _fetch_pass(pending, scores, headers, today, f"{attempt}b", total)
                break

        if pending:
            logger.warning(
                "buy_score: gave up on %d stocks after %d retries",
                len(pending), RATE_LIMIT_MAX_RETRIES,
            )

        logger.info("Background fetch complete: %d/%d stocks scored", len(scores), total)
    finally:
        elapsed = time.time() - start_time
        newly_scored = len(scores) - scored_before
        _write_metrics(
            today,
            attempted=initial_pending,
            succeeded=newly_scored,
            failed=max(initial_pending - newly_scored, 0),
            retries=retries_done,
            elapsed_s=elapsed,
            total_stocks=total,
        )
        with _fetch_lock:
            _is_fetching = False
        _cache = {}


@router.get("/scores")
def get_scores(
    request: Request,
    force: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Return buy scores. Token must be passed via X-FinMind-Token header (not query string).

    Auto-trigger: only when no scores exist at all.
    force=true: re-fetches all stocks fresh; old file is NOT deleted first —
    it is atomically replaced when the new data is ready (§3.4).
    """
    global _is_fetching, _cache

    token = request.headers.get("x-finmind-token", "")
    currently_fetching = _is_fetching

    if force and token and not currently_fetching:
        data = None  # bypass _load() so stale cache doesn't block fresh fetch
    else:
        data = _load()

    if data:
        return JSONResponse(content={**data, "fetching": currently_fetching})

    if token and not currently_fetching:
        with _fetch_lock:
            if not _is_fetching:
                stock_ids = _get_stock_ids(db)
                if stock_ids:
                    _is_fetching = True
                    currently_fetching = True
                    if background_tasks is not None:
                        background_tasks.add_task(
                            _background_score_fetch, token, stock_ids, force
                        )
                    else:
                        import threading as _t
                        _t.Thread(
                            target=_background_score_fetch,
                            args=(token, stock_ids, force),
                            daemon=True,
                        ).start()

    return JSONResponse(content={"date": "", "scores": {}, "fetching": currently_fetching})
