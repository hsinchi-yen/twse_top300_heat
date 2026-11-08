"""
score_summary.py — daily history of the buy-score run (read by backend /api/market/alert-counts)

Score files are kept for 7 days only, so the market-level picture (how scores are
distributed, how many stocks trip each risk rule) is recorded here after every
scoring run. Many stocks tripping 千張大戶退場 at once means big holders are
distributing across the market, which the macro dashboard uses as a warning.

Pure summary + idempotent upsert: re-recording a date replaces it, so a resumed
quota-interrupted run simply overwrites its partial row.
"""

import json
import logging
import os
from collections import Counter

from sqlalchemy import text

logger = logging.getLogger(__name__)

KEEP_DAYS = int(os.getenv("SCORE_SUMMARY_KEEP_DAYS", "800"))
N_BINS = 10

_DDL = [
    """CREATE TABLE IF NOT EXISTS score_summary_daily (
        date TEXT PRIMARY KEY, scored INTEGER NOT NULL, median REAL, p10 REAL, p90 REAL,
        bins TEXT NOT NULL, partial INTEGER NOT NULL DEFAULT 0, generated_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS score_alert_daily (
        date TEXT NOT NULL, name TEXT NOT NULL, count INTEGER NOT NULL,
        PRIMARY KEY (date, name))""",
]


def ensure_tables(session) -> None:
    for ddl in _DDL:
        session.execute(text(ddl))
    session.commit()


def _quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated quantile of an ascending list (same as numpy's default)."""
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def summarize(scores: dict[str, dict]) -> dict | None:
    """Distribution of pass_rate and risk-rule hit counts; None when nothing is scored.

    Stocks with eligible_count == 0 are N/A, not 0 %, and are left out.
    """
    rates, alerts = [], Counter()
    for entry in scores.values():
        if not isinstance(entry, dict) or not entry.get("eligible_count"):
            continue
        rate = entry.get("pass_rate")
        if rate is None:
            continue
        rates.append(float(rate))
        for risk in entry.get("risk_criteria") or []:
            name = risk.get("name") if isinstance(risk, dict) else None
            if name:
                alerts[name] += 1
    if not rates:
        return None
    rates.sort()
    bins = [0] * N_BINS
    for r in rates:
        bins[min(int(r // (100 / N_BINS)), N_BINS - 1)] += 1
    return {
        "scored": len(rates),
        "median": round(_quantile(rates, 0.5), 1),
        "p10": round(_quantile(rates, 0.1), 1),
        "p90": round(_quantile(rates, 0.9), 1),
        "bins": bins,
        "alerts": dict(alerts),
    }


def record(session, date: str, scores: dict[str, dict], *, partial: bool = False,
           generated_at: str | None = None) -> bool:
    """Upsert one date's summary. Returns False (and writes nothing) when empty."""
    summary = summarize(scores)
    if summary is None:
        return False
    ensure_tables(session)
    session.execute(text("""
        INSERT OR REPLACE INTO score_summary_daily
            (date, scored, median, p10, p90, bins, partial, generated_at)
        VALUES (:date, :scored, :median, :p10, :p90, :bins, :partial, :generated_at)"""),
        {"date": date, "scored": summary["scored"], "median": summary["median"],
         "p10": summary["p10"], "p90": summary["p90"], "bins": json.dumps(summary["bins"]),
         "partial": int(partial), "generated_at": generated_at})
    session.execute(text("DELETE FROM score_alert_daily WHERE date = :date"), {"date": date})
    for name, count in summary["alerts"].items():
        session.execute(text("INSERT INTO score_alert_daily (date, name, count) VALUES (:d, :n, :c)"),
                        {"d": date, "n": name, "c": count})
    session.commit()
    prune(session)
    logger.info("score_summary: %s scored=%d median=%.1f alerts=%s partial=%s",
                date, summary["scored"], summary["median"], summary["alerts"], partial)
    return True


def prune(session, keep: int = KEEP_DAYS) -> None:
    cutoff = session.execute(text(
        "SELECT date FROM score_summary_daily ORDER BY date DESC LIMIT 1 OFFSET :k"),
        {"k": keep - 1}).fetchone()
    if cutoff is None:
        return
    for table in ("score_summary_daily", "score_alert_daily"):
        session.execute(text(f"DELETE FROM {table} WHERE date < :c"), {"c": cutoff[0]})
    session.commit()
