"""
signals.py — 每日籌碼 + 技術／量能指標 → stock_signals (read by backend /api/signals)

Runs inside the nightly job (03:00 after a trading day, see main.nightly_job):
  1. backfill daily_bars from FinMind for universe stocks with short history
  2. upsert the trade date's bars from the official TWSE / TPEx close feeds
  3. fetch 三大法人 for trading dates missing in inst_flows (whole market per date)
  4. rebuild stock_signals for the universe, prune old bars / flows

Tables are created here (CREATE TABLE IF NOT EXISTS); the backend only reads
stock_signals. Insufficient history yields null fields — never a fallback 0.
"""

import logging
import math
import os
import random
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text

from sources.finmind_client import FinMindError

logger = logging.getLogger(__name__)

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
BAR_KEEP_DAYS = int(os.getenv("SIGNALS_BAR_KEEP_DAYS", "260"))
INST_KEEP_DAYS = int(os.getenv("SIGNALS_INST_KEEP_DAYS", "20"))
BACKFILL_DELAY = float(os.getenv("SIGNALS_BACKFILL_DELAY", "1.0"))

HIGH_WINDOW = 240              # ≈ 52 weeks of trading days
BACKFILL_MIN_BARS = 240        # fewer bars than this in the lookback → backfill
BACKFILL_LOOKBACK_DAYS = 380   # calendar days fetched / inspected for backfill
BACKFILL_COOLDOWN_DAYS = 30    # newly listed stocks: don't refetch every night

_DDL = [
    """CREATE TABLE IF NOT EXISTS daily_bars (
        stock_id TEXT NOT NULL, date TEXT NOT NULL, close REAL, volume INTEGER,
        PRIMARY KEY (stock_id, date))""",
    "CREATE INDEX IF NOT EXISTS ix_daily_bars_date ON daily_bars (date)",
    """CREATE TABLE IF NOT EXISTS inst_flows (
        stock_id TEXT NOT NULL, date TEXT NOT NULL,
        foreign_net INTEGER, trust_net INTEGER, dealer_net INTEGER,
        PRIMARY KEY (stock_id, date))""",
    "CREATE INDEX IF NOT EXISTS ix_inst_flows_date ON inst_flows (date)",
    """CREATE TABLE IF NOT EXISTS stock_signals (
        stock_id TEXT PRIMARY KEY, date TEXT, generated_at TEXT,
        close REAL, avg_volume_5d INTEGER, vol_ratio REAL,
        ma20 REAL, ma60 REAL, high_52w REAL, pct_from_52w_high REAL,
        inst_net_5d INTEGER, inst_streak INTEGER,
        foreign_net_1d INTEGER, trust_net_1d INTEGER)""",
    """CREATE TABLE IF NOT EXISTS signal_backfill (
        stock_id TEXT PRIMARY KEY, bars_at TEXT)""",
]

SIGNAL_FIELDS = [
    "close", "avg_volume_5d", "vol_ratio", "ma20", "ma60", "high_52w", "pct_from_52w_high",
    "inst_net_5d", "inst_streak", "foreign_net_1d", "trust_net_1d",
]


def ensure_tables(session) -> None:
    for ddl in _DDL:
        session.execute(text(ddl))
    session.commit()


# ── pure computation ─────────────────────────────────────────────────────────

def compute_signal(bars: list[tuple], flows: list[tuple], trade_date: str) -> dict | None:
    """bars: [(date, close, volume)] ascending; flows: [(date, foreign_net, trust_net)] ascending.

    Price fields need a bar ON trade_date; institutional fields need flows ON
    trade_date. Each window field is null until enough history exists.
    """
    out: dict = dict.fromkeys(SIGNAL_FIELDS)

    if bars and bars[-1][0] == trade_date:
        closes = [b[1] for b in bars]
        vols = [b[2] or 0 for b in bars]
        close = closes[-1]
        out["close"] = close
        if len(vols) >= 6:
            avg = sum(vols[-6:-1]) / 5
            out["avg_volume_5d"] = round(avg)
            out["vol_ratio"] = round(vols[-1] / avg, 2) if avg > 0 else None
        if len(closes) >= 20:
            out["ma20"] = round(sum(closes[-20:]) / 20, 2)
        if len(closes) >= 60:
            out["ma60"] = round(sum(closes[-60:]) / 60, 2)
        if len(closes) >= HIGH_WINDOW:
            high = max(closes[-HIGH_WINDOW:])
            out["high_52w"] = high
            out["pct_from_52w_high"] = round((close - high) / high * 100, 2) if high > 0 else None

    if flows and flows[-1][0] == trade_date:
        nets = [(f or 0) + (t or 0) for _, f, t in flows]
        out["foreign_net_1d"] = flows[-1][1]
        out["trust_net_1d"] = flows[-1][2]
        if len(nets) >= 5:
            out["inst_net_5d"] = sum(nets[-5:])
        sign = (nets[-1] > 0) - (nets[-1] < 0)
        streak = 0
        if sign:
            for n in reversed(nets):
                if (n > 0) - (n < 0) != sign:
                    break
                streak += 1
        out["inst_streak"] = streak * sign

    return out if any(v is not None for v in out.values()) else None


# ── storage ──────────────────────────────────────────────────────────────────

_UPSERT_BAR = text("""
    INSERT INTO daily_bars (stock_id, date, close, volume) VALUES (:s, :d, :c, :v)
    ON CONFLICT(stock_id, date) DO UPDATE SET close = excluded.close, volume = excluded.volume
""")


def upsert_bars(session, trade_date: str, records: list[dict], universe: set[str]) -> int:
    """records: official close feed rows {stock_id, close_price, volume} for trade_date."""
    rows = [
        {"s": r["stock_id"], "d": trade_date, "c": float(r["close_price"]), "v": int(r.get("volume") or 0)}
        for r in records
        if r.get("stock_id") in universe and (r.get("close_price") or 0) > 0
    ]
    if rows:
        session.execute(_UPSERT_BAR, rows)
    session.commit()
    return len(rows)


def upsert_flows(session, trade_date: str, flows: dict[str, dict]) -> int:
    rows = [
        {"s": sid, "d": trade_date, "f": v.get("foreign_net"), "t": v.get("trust_net"), "x": v.get("dealer_net")}
        for sid, v in flows.items()
    ]
    if rows:
        session.execute(text("""
            INSERT INTO inst_flows (stock_id, date, foreign_net, trust_net, dealer_net)
            VALUES (:s, :d, :f, :t, :x)
            ON CONFLICT(stock_id, date) DO UPDATE SET
                foreign_net = excluded.foreign_net, trust_net = excluded.trust_net,
                dealer_net = excluded.dealer_net
        """), rows)
    session.commit()
    return len(rows)


def backfill_bars(session, stock_ids: list[str], trade_date: str, client,
                  delay: float = BACKFILL_DELAY, sleep=time.sleep) -> int:
    """FinMind TaiwanStockPrice backfill for stocks with < BACKFILL_MIN_BARS recent bars.

    Commits per stock (resumable). A stock is retried at most once per
    BACKFILL_COOLDOWN_DAYS. FinMind quota error stops this run's backfill.
    """
    td = date.fromisoformat(trade_date)
    since = td - timedelta(days=BACKFILL_LOOKBACK_DAYS)
    cooldown = (td - timedelta(days=BACKFILL_COOLDOWN_DAYS)).isoformat()

    counts = dict(session.execute(text(
        "SELECT stock_id, COUNT(*) FROM daily_bars WHERE date >= :since GROUP BY stock_id"
    ), {"since": since.isoformat()}).all())
    marks = dict(session.execute(text("SELECT stock_id, bars_at FROM signal_backfill")).all())
    todo = [
        sid for sid in stock_ids
        if counts.get(sid, 0) < BACKFILL_MIN_BARS and not (marks.get(sid) and marks[sid] >= cooldown)
    ]
    if todo:
        logger.info("signals backfill: %d stocks need price history", len(todo))

    done = 0
    for i, sid in enumerate(todo):
        if i:
            sleep(delay)
        try:
            df = client.fetch_stock_price(sid, since, td)
        except FinMindError as exc:
            logger.warning("signals backfill stopped at %s (%d/%d): %s", sid, done, len(todo), exc)
            break
        except Exception as exc:
            logger.warning("signals backfill %s failed: %s", sid, exc)
            continue

        rows = []
        vols = df["Trading_Volume"] if "Trading_Volume" in df.columns else [0] * len(df)
        for d, c, v in zip(df["date"], df["close"], vols):
            if c is None or not math.isfinite(float(c)) or float(c) <= 0:
                continue
            vol = 0 if v is None or not math.isfinite(float(v)) else int(v)
            rows.append({"s": sid, "d": pd.Timestamp(d).strftime("%Y-%m-%d"), "c": float(c), "v": vol})
        if rows:
            session.execute(_UPSERT_BAR, rows)
        session.execute(text("""
            INSERT INTO signal_backfill (stock_id, bars_at) VALUES (:s, :d)
            ON CONFLICT(stock_id) DO UPDATE SET bars_at = excluded.bars_at
        """), {"s": sid, "d": trade_date})
        session.commit()
        done += 1
    return done


def missing_flow_dates(session, trade_date: str) -> list[str]:
    """Latest INST_KEEP_DAYS trading dates (bar calendar ∪ trade_date) lacking inst_flows."""
    bar_dates = [r[0] for r in session.execute(text(
        "SELECT DISTINCT date FROM daily_bars WHERE date <= :d ORDER BY date DESC LIMIT :n"
    ), {"d": trade_date, "n": INST_KEEP_DAYS}).all()]
    wanted = sorted(set(bar_dates) | {trade_date}, reverse=True)[:INST_KEEP_DAYS]
    have = {r[0] for r in session.execute(text(
        "SELECT DISTINCT date FROM inst_flows WHERE date <= :d"
    ), {"d": trade_date}).all()}
    return sorted(d for d in wanted if d not in have)


def rebuild_signals(session, stock_ids: list[str], trade_date: str, generated_at: str) -> int:
    """Replace stock_signals with fresh rows for stock_ids (latest trade date only)."""
    universe = set(stock_ids)
    bars: dict[str, list] = {}
    for sid, d, c, v in session.execute(text(
        "SELECT stock_id, date, close, volume FROM daily_bars WHERE date <= :d ORDER BY stock_id, date"
    ), {"d": trade_date}):
        if sid in universe:
            bars.setdefault(sid, []).append((d, c, v))
    flows: dict[str, list] = {}
    for sid, d, f, t in session.execute(text(
        "SELECT stock_id, date, foreign_net, trust_net FROM inst_flows WHERE date <= :d ORDER BY stock_id, date"
    ), {"d": trade_date}):
        if sid in universe:
            flows.setdefault(sid, []).append((d, f, t))

    rows = []
    for sid in stock_ids:
        sig = compute_signal(bars.get(sid, []), flows.get(sid, []), trade_date)
        if sig is not None:
            rows.append({"stock_id": sid, "date": trade_date, "generated_at": generated_at, **sig})

    session.execute(text("DELETE FROM stock_signals"))
    if rows:
        cols = ["stock_id", "date", "generated_at", *SIGNAL_FIELDS]
        session.execute(text(
            f"INSERT INTO stock_signals ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})"
        ), rows)
    session.commit()
    return len(rows)


def prune(session) -> None:
    for table, keep in (("daily_bars", BAR_KEEP_DAYS), ("inst_flows", INST_KEEP_DAYS)):
        cutoff = session.execute(text(
            f"SELECT DISTINCT date FROM {table} ORDER BY date DESC LIMIT 1 OFFSET :k"
        ), {"k": keep}).scalar()
        if cutoff:
            deleted = session.execute(text(f"DELETE FROM {table} WHERE date <= :c"), {"c": cutoff}).rowcount
            logger.info("signals prune: %d %s rows <= %s", deleted, table, cutoff)
    session.commit()


def is_complete(session, trade_date: str) -> bool:
    """Signals rebuilt for trade_date AND that date's 三大法人 are stored."""
    latest = session.execute(text("SELECT MAX(date) FROM stock_signals")).scalar()
    flows = session.execute(text("SELECT 1 FROM inst_flows WHERE date = :d LIMIT 1"), {"d": trade_date}).first()
    return latest == trade_date and flows is not None


def run_signals(session, universe: list[str], trade_date: str, bar_records: list[dict],
                fetch_flows, client, sleep=time.sleep) -> dict:
    """One nightly pass. fetch_flows(date) -> {stock_id: {...}} ({} = not available)."""
    ensure_tables(session)
    if is_complete(session, trade_date):
        logger.info("signals: %s already complete — skip", trade_date)
        return {"skipped": True, "trade_date": trade_date}

    ids = list(dict.fromkeys(universe))
    # Backfill first so the official feed's bar for trade_date wins over FinMind's.
    backfilled = backfill_bars(session, ids, trade_date, client, sleep=sleep)
    bars = upsert_bars(session, trade_date, bar_records, set(ids))

    flow_dates = 0
    for i, d in enumerate(missing_flow_dates(session, trade_date)):
        if i:
            sleep(random.uniform(3.0, 5.0))
        flows = fetch_flows(d)
        if flows:
            upsert_flows(session, d, flows)
            flow_dates += 1

    generated_at = datetime.now(tz=TZ_TAIPEI).isoformat()
    n = rebuild_signals(session, ids, trade_date, generated_at)
    prune(session)
    summary = {"skipped": False, "trade_date": trade_date, "backfilled": backfilled,
               "bars": bars, "flow_dates": flow_dates, "signals": n}
    logger.info("signals done: %s", summary)
    return summary
