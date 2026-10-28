"""
test_signals.py — daily 籌碼 / 技術 signals (crawler/signals.py)

Pure computation (compute_signal) plus DB-level behaviour on an in-memory SQLite:
bar upsert, FinMind backfill (resumable, cooldown), flow backfill, rebuild,
completeness check and pruning.
"""

import os
import sys
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import signals
from signals import compute_signal
from sources.finmind_client import FinMindError

TRADE = "2026-10-23"


def _dates(n, end=TRADE):
    """n consecutive weekday dates ending at `end` (ascending)."""
    d = date.fromisoformat(end)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(out))


def _bars(closes, volumes=None, end=TRADE):
    ds = _dates(len(closes), end)
    volumes = volumes or [1000] * len(closes)
    return list(zip(ds, closes, volumes))


def _flows(nets, end=TRADE):
    """nets: list of (foreign, trust) ascending."""
    ds = _dates(len(nets), end)
    return [(d, f, t) for d, (f, t) in zip(ds, nets)]


class TestComputeSignal:
    def test_moving_averages(self):
        closes = list(range(1, 61))          # 1..60
        s = compute_signal(_bars(closes), [], TRADE)
        assert s["close"] == 60
        assert s["ma20"] == pytest.approx(sum(range(41, 61)) / 20)
        assert s["ma60"] == pytest.approx(sum(range(1, 61)) / 60)

    def test_ma_null_when_history_short(self):
        s = compute_signal(_bars([10.0] * 30), [], TRADE)
        assert s["ma20"] == 10.0
        assert s["ma60"] is None
        assert s["high_52w"] is None
        assert s["pct_from_52w_high"] is None

    def test_volume_ratio_uses_previous_five_days(self):
        vols = [100, 100, 100, 100, 100, 250]
        s = compute_signal(_bars([10.0] * 6, vols), [], TRADE)
        assert s["avg_volume_5d"] == 100
        assert s["vol_ratio"] == pytest.approx(2.5)

    def test_volume_ratio_null_with_under_six_bars(self):
        s = compute_signal(_bars([10.0] * 5), [], TRADE)
        assert s["avg_volume_5d"] is None
        assert s["vol_ratio"] is None

    def test_52w_high_from_last_240_closes(self):
        closes = [200.0] + [100.0] * 238 + [150.0, 90.0]   # 241 bars; 200 falls outside window
        s = compute_signal(_bars(closes), [], TRADE)
        assert s["high_52w"] == 150.0
        assert s["pct_from_52w_high"] == pytest.approx(-40.0)

    def test_price_fields_null_when_no_bar_on_trade_date(self):
        s = compute_signal(_bars([10.0] * 30, end="2026-10-22"), _flows([(1, 1)] * 5), TRADE)
        assert s["close"] is None and s["ma20"] is None and s["vol_ratio"] is None
        assert s["inst_net_5d"] == 10   # flows are still valid

    def test_institutional_net_and_streak(self):
        nets = [(-5, 0), (3, 1), (2, 2), (1, 0), (4, -1), (2, 3)]   # daily nets -5,4,4,1,3,5
        s = compute_signal(_bars([10.0] * 6), _flows(nets), TRADE)
        assert s["inst_net_5d"] == (4 + 4 + 1 + 3 + 5)
        assert s["inst_streak"] == 5
        assert s["foreign_net_1d"] == 2
        assert s["trust_net_1d"] == 3

    def test_negative_streak(self):
        nets = [(5, 0), (-1, 0), (-2, -1)]
        s = compute_signal(_bars([10.0] * 6), _flows(nets), TRADE)
        assert s["inst_streak"] == -2
        assert s["inst_net_5d"] is None   # fewer than 5 days

    def test_zero_latest_net_breaks_streak(self):
        s = compute_signal(_bars([10.0] * 6), _flows([(3, 0), (2, -2)]), TRADE)
        assert s["inst_streak"] == 0

    def test_inst_fields_null_when_trade_date_flows_missing(self):
        s = compute_signal(_bars([10.0] * 6), _flows([(1, 1)] * 6, end="2026-10-22"), TRADE)
        assert s["inst_net_5d"] is None
        assert s["inst_streak"] is None
        assert s["foreign_net_1d"] is None

    def test_returns_none_without_any_data(self):
        assert compute_signal([], [], TRADE) is None


# ── DB-level ────────────────────────────────────────────────────────────────

@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    with sessionmaker(bind=engine)() as s:
        signals.ensure_tables(s)
        yield s


class FakeClient:
    def __init__(self, n_bars=250, fail=None):
        self.calls = []
        self.n_bars = n_bars
        self.fail = fail or {}

    def fetch_stock_price(self, stock_id, start_date, end_date, timeout=30.0):
        self.calls.append(stock_id)
        if stock_id in self.fail:
            raise self.fail[stock_id]
        ds = _dates(self.n_bars, end=end_date.isoformat())
        return pd.DataFrame({
            "date": pd.to_datetime(ds),
            "close": [100.0] * len(ds),
            "Trading_Volume": [5000] * len(ds),
        })


def _count(session, table, where="1=1", **params):
    return session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), params).scalar()


class TestBarsAndBackfill:
    def test_upsert_bars_only_for_given_universe(self, session):
        recs = [{"stock_id": "2330", "close_price": 1000.0, "volume": 9},
                {"stock_id": "9999", "close_price": 1.0, "volume": 1}]
        signals.upsert_bars(session, TRADE, recs, universe={"2330"})
        assert _count(session, "daily_bars") == 1

    def test_upsert_bars_ignores_zero_close(self, session):
        signals.upsert_bars(session, TRADE, [{"stock_id": "2330", "close_price": 0, "volume": 0}], universe={"2330"})
        assert _count(session, "daily_bars") == 0

    def test_backfill_fetches_short_history_and_marks(self, session):
        client = FakeClient()
        n = signals.backfill_bars(session, ["2330"], TRADE, client, delay=0)
        assert n == 1
        assert _count(session, "daily_bars", "stock_id='2330'") == 250
        assert _count(session, "signal_backfill", "stock_id='2330'") == 1

    def test_backfill_skips_stock_with_enough_history(self, session):
        client = FakeClient()
        signals.backfill_bars(session, ["2330"], TRADE, client, delay=0)
        client.calls.clear()
        signals.backfill_bars(session, ["2330"], TRADE, client, delay=0)
        assert client.calls == []

    def test_backfill_cooldown_for_short_listed_stock(self, session):
        client = FakeClient(n_bars=50)       # newly listed: FinMind only has 50 bars
        signals.backfill_bars(session, ["7777"], TRADE, client, delay=0)
        client.calls.clear()
        signals.backfill_bars(session, ["7777"], TRADE, client, delay=0)
        assert client.calls == []            # marker prevents daily refetch

    def test_backfill_quota_error_stops_and_leaves_rest_unmarked(self, session):
        client = FakeClient(fail={"2317": FinMindError("quota")})
        n = signals.backfill_bars(session, ["2330", "2317", "2454"], TRADE, client, delay=0)
        assert n == 1
        assert client.calls == ["2330", "2317"]
        assert _count(session, "signal_backfill") == 1

    def test_backfill_generic_error_skips_stock_only(self, session):
        client = FakeClient(fail={"2317": ValueError("bad")})
        n = signals.backfill_bars(session, ["2330", "2317", "2454"], TRADE, client, delay=0)
        assert n == 2
        assert _count(session, "signal_backfill", "stock_id='2317'") == 0


class TestFlowsAndRun:
    def _seed_bars(self, session, ids, n=30, end=TRADE):
        for d, c, v in _bars([10.0] * n, end=end):
            signals.upsert_bars(session, d, [{"stock_id": s, "close_price": c, "volume": v} for s in ids],
                                universe=set(ids))

    def test_missing_flow_dates_within_keep_window(self, session, monkeypatch):
        monkeypatch.setattr(signals, "INST_KEEP_DAYS", 5)
        self._seed_bars(session, ["2330"])
        assert signals.missing_flow_dates(session, TRADE) == _dates(5)
        signals.upsert_flows(session, TRADE, {"2330": {"foreign_net": 1, "trust_net": 0, "dealer_net": 0}})
        assert signals.missing_flow_dates(session, TRADE) == _dates(5)[:-1]

    def test_run_builds_signals_and_is_idempotent(self, session, monkeypatch):
        monkeypatch.setattr(signals, "INST_KEEP_DAYS", 5)
        self._seed_bars(session, ["2330", "2317"], n=29, end="2026-10-22")  # history; today's bar comes from the feed
        fetched = []

        def fetch_flows(d):
            fetched.append(d)
            return {"2330": {"foreign_net": 10, "trust_net": 5, "dealer_net": 0}}

        today = [{"stock_id": "2330", "close_price": 12.0, "volume": 3000},
                 {"stock_id": "2317", "close_price": 9.0, "volume": 1000}]
        summary = signals.run_signals(session, ["2330", "2317"], TRADE, today, fetch_flows,
                                      client=FakeClient(n_bars=0), sleep=lambda s: None)
        assert summary["signals"] == 2
        assert sorted(fetched) == _dates(5)
        row = session.execute(text("SELECT * FROM stock_signals WHERE stock_id='2330'")).mappings().one()
        assert row["date"] == TRADE
        assert row["close"] == 12.0
        assert row["inst_streak"] == 5
        assert row["vol_ratio"] == pytest.approx(3.0)
        assert signals.is_complete(session, TRADE)

        fetched.clear()
        again = signals.run_signals(session, ["2330", "2317"], TRADE, today, fetch_flows,
                                    client=FakeClient(n_bars=0), sleep=lambda s: None)
        assert again["skipped"] is True
        assert fetched == []

    def test_incomplete_when_trade_date_flows_unpublished(self, session, monkeypatch):
        monkeypatch.setattr(signals, "INST_KEEP_DAYS", 3)
        self._seed_bars(session, ["2330"], n=10)
        signals.run_signals(session, ["2330"], TRADE, [], lambda d: {},
                            client=FakeClient(n_bars=0), sleep=lambda s: None)
        assert not signals.is_complete(session, TRADE)
        row = session.execute(text("SELECT inst_streak FROM stock_signals WHERE stock_id='2330'")).one()
        assert row[0] is None

    def test_rebuild_replaces_previous_rows(self, session):
        self._seed_bars(session, ["2330", "2317"], n=10)
        signals.rebuild_signals(session, ["2330", "2317"], TRADE, "t1")
        signals.rebuild_signals(session, ["2330"], TRADE, "t2")
        assert _count(session, "stock_signals") == 1

    def test_prune_keeps_latest_trading_dates(self, session, monkeypatch):
        monkeypatch.setattr(signals, "BAR_KEEP_DAYS", 10)
        monkeypatch.setattr(signals, "INST_KEEP_DAYS", 3)
        self._seed_bars(session, ["2330"], n=15)
        for d in _dates(6):
            signals.upsert_flows(session, d, {"2330": {"foreign_net": 1, "trust_net": 1, "dealer_net": 1}})
        signals.prune(session)
        assert _count(session, "daily_bars") == 10
        assert _count(session, "inst_flows") == 3
