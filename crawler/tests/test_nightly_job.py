"""
test_nightly_job.py — 03:00 nightly job: runs only after a trading day.

User requirement (2026-10-26): data need not be real-time; signals + buy-score
refresh run at 03:00 the morning after each trading day; a weekday without a
session (holiday) triggers nothing.
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytest.importorskip("apscheduler")

import main

TZ = ZoneInfo("Asia/Taipei")
TUE_0300 = datetime(2026, 10, 27, 3, 0, tzinfo=TZ)   # morning after Mon 2026-10-26


@pytest.fixture
def calls(monkeypatch):
    order = []
    monkeypatch.setattr(main._time, "sleep", lambda s: None)
    monkeypatch.setattr(main, "signals_job", MagicMock(side_effect=lambda *a, **k: order.append("signals")))
    monkeypatch.setattr(main, "score_job", MagicMock(side_effect=lambda *a, **k: order.append("score")))
    return order


def _feeds(monkeypatch, twse_date, tpex_date=None, latest_rank_date=None):
    monkeypatch.setattr(main, "fetch_twse_daily", lambda: ([{"stock_id": "2330"}] if twse_date else [], twse_date))
    monkeypatch.setattr(main, "fetch_tpex_daily", lambda: ([], tpex_date if tpex_date is not None else twse_date))
    monkeypatch.setattr(main, "_latest_trade_date", lambda: latest_rank_date)


def test_runs_signals_then_score_after_trading_day(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-26")
    main.nightly_job(now=TUE_0300)
    assert calls == ["signals", "score"]
    args = main.signals_job.call_args.args
    assert args[1] == "2026-10-26"


def test_skips_after_non_trading_day(monkeypatch, calls):
    # Monday was a holiday → TWSE still reports Friday.
    _feeds(monkeypatch, "2026-10-23")
    main.nightly_job(now=TUE_0300)
    assert calls == []


def test_saturday_morning_after_friday_session(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-23")
    main.nightly_job(now=datetime(2026, 10, 24, 3, 0, tzinfo=TZ))
    assert calls == ["signals", "score"]


def test_monday_morning_does_nothing(monkeypatch, calls):
    # Sunday had no session; TWSE reports Friday.
    _feeds(monkeypatch, "2026-10-23")
    main.nightly_job(now=datetime(2026, 10, 26, 3, 0, tzinfo=TZ))
    assert calls == []


def test_falls_back_to_stock_ranks_when_twse_unreachable(monkeypatch, calls):
    _feeds(monkeypatch, None, tpex_date=None, latest_rank_date="2026-10-26")
    main.nightly_job(now=TUE_0300)
    assert "score" in calls


def test_no_run_when_twse_unreachable_and_ranks_stale(monkeypatch, calls):
    _feeds(monkeypatch, None, tpex_date=None, latest_rank_date="2026-10-23")
    main.nightly_job(now=TUE_0300)
    assert calls == []


def test_signals_failure_does_not_block_score(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-26")
    monkeypatch.setattr(main, "signals_job", MagicMock(side_effect=RuntimeError("boom")))
    main.nightly_job(now=TUE_0300)
    assert calls == ["score"]


def test_signals_job_skips_when_markets_disagree(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(main.signals, "run_signals", run)
    main.signals_job([], "2026-10-26", [], "2026-10-23")
    run.assert_not_called()


class TestScheduler:
    def _jobs(self):
        return {j.id: j for j in main.build_scheduler().get_jobs()}

    def test_nightly_job_daily_at_0300(self):
        job = self._jobs()["nightly"]
        trig = str(job.trigger)
        assert "hour='3'" in trig and "minute='0'" in trig
        assert "day_of_week" not in trig    # gate is the trading-day check, not the calendar

    def test_no_monthly_score_schedule(self):
        jobs = self._jobs()
        assert "score_monthly" not in jobs
        assert not any(j.func is main.score_job for j in jobs.values())

    def test_force_refresh_watch_still_scheduled(self):
        assert "force_refresh_watch" in self._jobs()


def test_score_job_is_single_flight(monkeypatch):
    inner = MagicMock()
    monkeypatch.setattr(main, "_score_job", inner)
    assert main._SCORE_LOCK.acquire(blocking=False)
    try:
        main.score_job(force=True)      # e.g. force refresh while nightly is scoring
    finally:
        main._SCORE_LOCK.release()
    inner.assert_not_called()
    main.score_job()
    inner.assert_called_once_with(False)


def test_resume_while_scoring_keeps_resume_state(monkeypatch):
    saved = MagicMock()
    monkeypatch.setattr(main, "_write_resume_state", saved)
    monkeypatch.setattr(main, "_resume_score_job_locked", MagicMock())
    assert main._SCORE_LOCK.acquire(blocking=False)
    try:
        main._resume_score_job(["2330"], "2026-10-27")
    finally:
        main._SCORE_LOCK.release()
    saved.assert_called_once_with(["2330"], "2026-10-27")
    main._resume_score_job_locked.assert_not_called()
