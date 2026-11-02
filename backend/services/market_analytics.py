"""
market_analytics.py — breadth, sector rotation and technical-setup validation.

Pure functions over plain data so they can be tested without a database. All
inputs are unadjusted closes from the crawler's daily_bars:

    bars_by_stock: {stock_id: [(date, close, volume), ...]}  ascending by date

The universe is today's most-traded names, so every historical figure here is
survivorship-biased; the frontend discloses that. Closes are not dividend
adjusted. Thin data yields None, never a number. See SPEC.md.
"""

from statistics import median

DAILY_LIMIT = 0.11        # beyond ±10% limit + rounding → corporate action, not a return
MIN_BREADTH_SAMPLE = 20   # below this a percentage says more about the sample than the market
MIN_SECTOR_STOCKS = 3
MIN_PERIOD_MEMBERS = 5
MA_SHORT = 20
MA_LONG = 60
HIGH_WINDOW = 120         # ≈ half a year of trading days
FLOW_WINDOW = 5
OTHER_SECTOR = "其他"


def moving_average(closes: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    running = 0.0
    for i, close in enumerate(closes):
        running += close
        if i >= window:
            running -= closes[i - window]
        out.append(round(running / window, 2) if i >= window - 1 else None)
    return out


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1)


def breadth_series(bars_by_stock: dict, days: int) -> list[dict]:
    calendar = sorted({row[0] for rows in bars_by_stock.values() for row in rows})
    window = calendar[-days:]
    if not window:
        return []
    previous_day = {d: calendar[i - 1] for i, d in enumerate(calendar) if i}
    tally = {
        d: {"up": 0, "down": 0, "flat": 0, "ret_sum": 0.0, "ret_n": 0,
            "ma20_n": 0, "ma20_above": 0, "ma60_n": 0, "ma60_above": 0}
        for d in window
    }

    for rows in bars_by_stock.values():
        closes = [row[1] for row in rows]
        ma20 = moving_average(closes, MA_SHORT)
        ma60 = moving_average(closes, MA_LONG)
        for i, (day, close, _volume) in enumerate(rows):
            t = tally.get(day)
            if t is None:
                continue
            if ma20[i] is not None:
                t["ma20_n"] += 1
                t["ma20_above"] += close > ma20[i]
            if ma60[i] is not None:
                t["ma60_n"] += 1
                t["ma60_above"] += close > ma60[i]
            # Same-stock move between consecutive market days only: a suspension
            # gap or a corporate action is not a daily return.
            if i == 0 or rows[i - 1][0] != previous_day.get(day):
                continue
            ret = close / closes[i - 1] - 1
            if abs(ret) > DAILY_LIMIT:
                continue
            t["up"] += ret > 0
            t["down"] += ret < 0
            t["flat"] += ret == 0
            t["ret_sum"] += ret
            t["ret_n"] += 1

    series = []
    index = 100.0
    for i, day in enumerate(window):
        t = tally[day]
        if i and t["ret_n"]:
            index *= 1 + t["ret_sum"] / t["ret_n"]
        series.append({
            "date": day,
            "advancers": t["up"],
            "decliners": t["down"],
            "unchanged": t["flat"],
            "pct_above_ma20": _pct(t["ma20_above"], t["ma20_n"]) if t["ma20_n"] >= MIN_BREADTH_SAMPLE else None,
            "pct_above_ma60": _pct(t["ma60_above"], t["ma60_n"]) if t["ma60_n"] >= MIN_BREADTH_SAMPLE else None,
            "ew_index": round(index, 2),
        })
    return series


def _clean_path(closes: list[float]) -> bool:
    """False if any single move exceeds the daily limit: that is a corporate action.

    Checked bar by bar because the size of a window says nothing here: a 20% stock
    dividend (-16.7% in a day) is small for 60 days, while five limit-downs (-41%)
    are a real loss that must stay in.
    """
    return all(abs(b / a - 1) <= DAILY_LIMIT for a, b in zip(closes, closes[1:]))


def _return_pct(rows: list, start_day: str | None) -> float | None:
    """Return % since start_day, or None without that bar / across a corporate action."""
    if start_day is None:
        return None
    window = [(day, close) for day, close, _volume in rows if day >= start_day]
    if not window or window[0][0] != start_day:
        return None
    closes = [close for _day, close in window]
    return (closes[-1] / closes[0] - 1) * 100 if _clean_path(closes) else None


def _median_or_none(values: list[float]) -> float | None:
    return round(median(values), 2) if len(values) >= MIN_SECTOR_STOCKS else None


def sector_rotation(bars_by_stock: dict, sector_of: dict, flows_by_stock: dict) -> list[dict]:
    """flows_by_stock: {stock_id: [(date, foreign_plus_trust_net), ...]} ascending."""
    calendar = sorted({row[0] for rows in bars_by_stock.values() for row in rows})
    latest = calendar[-1] if calendar else ""
    start_of = {h: calendar[-1 - h] if len(calendar) > h else None for h in (5, 20, 60)}
    flow_dates = sorted({row[0] for rows in flows_by_stock.values() for row in rows})
    recent_flow = set(flow_dates[-FLOW_WINDOW:])

    groups: dict[str, list] = {}
    for stock_id, rows in bars_by_stock.items():
        if not rows or rows[-1][0] != latest:
            continue
        sector = sector_of.get(stock_id) or OTHER_SECTOR
        if sector != OTHER_SECTOR:
            groups.setdefault(sector, []).append((stock_id, rows))

    out = []
    for sector, members in groups.items():
        if len(members) < MIN_SECTOR_STOCKS:
            continue
        returns = {h: [] for h in (5, 20, 60)}
        above = with_ma = 0
        net = None
        for stock_id, rows in members:
            for horizon, bucket in returns.items():
                value = _return_pct(rows, start_of[horizon])
                if value is not None:
                    bucket.append(value)
            closes = [row[1] for row in rows]
            ma20 = moving_average(closes, MA_SHORT)[-1]
            if ma20 is not None:
                with_ma += 1
                above += closes[-1] > ma20
            for day, value in flows_by_stock.get(stock_id, []):
                if day in recent_flow:
                    net = (net or 0) + value
        out.append({
            "name": sector,
            "count": len(members),
            "ret_5d": _median_or_none(returns[5]),
            "ret_20d": _median_or_none(returns[20]),
            "ret_60d": _median_or_none(returns[60]),
            "pct_above_ma20": _pct(above, with_ma) if with_ma >= MIN_SECTOR_STOCKS else None,
            "inst_net_5d": net,
        })
    out.sort(key=lambda r: (r["ret_20d"] is None, -(r["ret_20d"] or 0)))
    return out


# ── technical setup validation ───────────────────────────────────────────────

def _is_trend_up(close, ma20, ma60, _closes, _vols, _pos) -> bool:
    return close > ma20 and close > ma60


def _is_breakout(close, _ma20, ma60, closes, vols, pos) -> bool:
    average = sum(vols[pos - 5:pos]) / 5
    return average > 0 and vols[pos] / average >= 2 and close > closes[pos - 1] and close > ma60


def _is_near_high(close, _ma20, _ma60, closes, _vols, pos) -> bool:
    if pos + 1 < HIGH_WINDOW:
        return False
    return close >= 0.95 * max(closes[pos + 1 - HIGH_WINDOW:pos + 1])


def _is_pullback(close, ma20, ma60, _closes, _vols, _pos) -> bool:
    return close > ma60 and 0.95 * ma20 <= close < ma20


SETUPS = (
    ("trend_up", "站上月季線", _is_trend_up),
    ("breakout", "量增突破", _is_breakout),
    ("near_high", "近半年高", _is_near_high),
    ("pullback", "多頭回檔", _is_pullback),
)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def backtest(bars_by_stock: dict, horizon: int) -> dict:
    """Forward returns of the technical setups on non-overlapping signal dates.

    Entry is the close after the signal: signals publish overnight, so neither the
    signal day's close nor the gap that fired the signal could have been traded.
    """
    empty = {"date": "", "horizon": horizon, "periods": 0, "baseline": None, "setups": []}
    calendar = sorted({row[0] for rows in bars_by_stock.values() for row in rows})
    if len(calendar) <= horizon:
        return empty

    prepared = []
    for rows in bars_by_stock.values():
        closes = [row[1] for row in rows]
        prepared.append({
            "position": {row[0]: i for i, row in enumerate(rows)},
            "closes": closes,
            "volumes": [row[2] or 0 for row in rows],
        })

    results = {key: {"period_means": [], "excess": [], "beat": 0, "wins": 0, "samples": 0}
               for key, _, _ in SETUPS}
    baseline_means: list[float] = []
    baseline_wins = baseline_samples = 0

    for signal_index in range(len(calendar) - 2 - horizon, MA_LONG - 2, -horizon):
        signal_day = calendar[signal_index]
        entry_day = calendar[signal_index + 1]
        exit_day = calendar[signal_index + 1 + horizon]
        everyone: list[float] = []
        members: dict[str, list[float]] = {key: [] for key, _, _ in SETUPS}

        for stock in prepared:
            pos = stock["position"].get(signal_day)
            entry = stock["position"].get(entry_day)
            end = stock["position"].get(exit_day)
            if pos is None or entry is None or end is None or pos + 1 < MA_LONG:
                continue
            closes = stock["closes"]
            if not _clean_path(closes[entry:end + 1]):
                continue
            ret = closes[end] / closes[entry] - 1
            everyone.append(ret)
            close = closes[pos]
            ma20 = sum(closes[pos + 1 - MA_SHORT:pos + 1]) / MA_SHORT
            ma60 = sum(closes[pos + 1 - MA_LONG:pos + 1]) / MA_LONG
            for key, _label, is_member in SETUPS:
                if is_member(close, ma20, ma60, closes, stock["volumes"], pos):
                    members[key].append(ret)

        if len(everyone) < MIN_PERIOD_MEMBERS:
            continue
        base = _mean(everyone)
        baseline_means.append(base)
        baseline_wins += sum(r > 0 for r in everyone)
        baseline_samples += len(everyone)

        for key, rets in members.items():
            if len(rets) < MIN_PERIOD_MEMBERS:
                continue
            bucket = results[key]
            value = _mean(rets)
            bucket["period_means"].append(value)
            bucket["excess"].append(value - base)
            bucket["beat"] += value > base
            bucket["wins"] += sum(r > 0 for r in rets)
            bucket["samples"] += len(rets)

    if not baseline_means:
        return empty

    setups = []
    for key, label, _ in SETUPS:
        bucket = results[key]
        measured = bool(bucket["period_means"])
        setups.append({
            "key": key,
            "label": label,
            "periods": len(bucket["period_means"]),
            "beat_periods": bucket["beat"],
            "samples": bucket["samples"],
            "avg_ret": _round(_mean(bucket["period_means"]) * 100) if measured else None,
            "avg_excess": _round(_mean(bucket["excess"]) * 100) if measured else None,
            "win_rate": _round(bucket["wins"] / bucket["samples"] * 100) if measured else None,
            "worst_period_ret": _round(min(bucket["period_means"]) * 100) if measured else None,
        })

    return {
        "date": calendar[-1],
        "horizon": horizon,
        "periods": len(baseline_means),
        "baseline": {
            "avg_ret": _round(_mean(baseline_means) * 100),
            "win_rate": _round(baseline_wins / baseline_samples * 100),
        },
        "setups": setups,
    }
