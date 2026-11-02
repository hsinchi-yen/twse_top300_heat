"""
test_nightly_job.py — 03:00 nightly job: runs only when a new trading day exists.

User requirement (2026-10-26): data need not be real-time; signals + buy-score
refresh run at 03:00 after a trading day; a day without a session triggers nothing.

Regression (found on production 2026-11-02): the gate compared the feed's date with
yesterday, but the TWSE OpenAPI feed publishes after 03:00 — on Saturday 03:00 it
still reports Thursday — so the job logged "not a trading day" and exited every night
for a week, leaving 0 signals and frozen scores. "New" means newer than the last date
processed, and these tests use the feed dates actually observed at 03:00.
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytest.importorskip("apscheduler")

import main

TZ = ZoneInfo("Asia/Taipei")
TUE_0300 = datetime(2026, 10, 27, 3, 0, tzinfo=TZ)
SAT_0300 = datetime(2026, 10, 31, 3, 0, tzinfo=TZ)
SUN_0300 = datetime(2026, 11, 1, 3, 0, tzinfo=TZ)
MON_0300 = datetime(2026, 11, 2, 3, 0, tzinfo=TZ)


@pytest.fixture
def calls(monkeypatch):
    order = []
    monkeypatch.setattr(main._time, "sleep", lambda s: None)
    monkeypatch.setattr(main, "signals_job", MagicMock(side_effect=lambda *a, **k: order.append("signals")))
    monkeypatch.setattr(main, "score_job", MagicMock(side_effect=lambda *a, **k: order.append("score")))
    return order


def _feeds(monkeypatch, twse_date, tpex_date=None, latest_rank_date=None, processed="2026-10-20"):
    monkeypatch.setattr(main, "_last_signal_date", lambda: processed)
    monkeypatch.setattr(main, "fetch_twse_daily", lambda: ([{"stock_id": "2330"}] if twse_date else [], twse_date))
    monkeypatch.setattr(main, "fetch_tpex_daily", lambda: ([], tpex_date if tpex_date is not None else twse_date))
    monkeypatch.setattr(main, "_latest_trade_date", lambda: latest_rank_date)


def test_runs_signals_then_score_for_a_new_trade_date(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-26", processed="2026-10-23")
    main.nightly_job(now=TUE_0300)
    assert calls == ["signals", "score"]
    assert main.signals_job.call_args.args[1] == "2026-10-26"


def test_a_feed_that_lags_the_calendar_still_runs(monkeypatch, calls):
    """Observed: Sat 03:00, Friday traded, the feed still reports Thursday."""
    _feeds(monkeypatch, "2026-10-29", processed="2026-10-28")
    main.nightly_job(now=SAT_0300)
    assert calls == ["signals", "score"]
    assert main.signals_job.call_args.args[1] == "2026-10-29"


def test_first_run_ever_processes_the_feed(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-30", processed=None)
    main.nightly_job(now=MON_0300)
    assert calls == ["signals", "score"]


def test_a_date_already_processed_does_nothing(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-30", processed="2026-10-30")
    main.nightly_job(now=SUN_0300)
    assert calls == []


def test_weekend_runs_once_for_friday_then_stops(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-30", processed="2026-10-29")
    main.nightly_job(now=SUN_0300)
    assert calls == ["signals", "score"]
    calls.clear()
    _feeds(monkeypatch, "2026-10-30", processed="2026-10-30")
    main.nightly_job(now=MON_0300)
    assert calls == []


def test_a_holiday_produces_no_new_date(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-23", processed="2026-10-23")
    main.nightly_job(now=TUE_0300)
    assert calls == []


def test_a_failed_signals_run_retries_next_night(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-26", processed="2026-10-23")
    monkeypatch.setattr(main, "signals_job", MagicMock(side_effect=RuntimeError("boom")))
    main.nightly_job(now=TUE_0300)
    assert calls == ["score"]
    main.signals_job.reset_mock()
    main.nightly_job(now=datetime(2026, 10, 28, 3, 0, tzinfo=TZ))   # still unprocessed
    main.signals_job.assert_called_once()


class TestLastSignalDate:
    @pytest.fixture
    def session(self, tmp_path, monkeypatch):
        engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")
        factory = sessionmaker(bind=engine)
        monkeypatch.setattr(main, "Session", factory)
        return factory

    def test_none_before_the_crawler_has_created_the_table(self, session):
        assert main._last_signal_date() is None

    def test_none_when_the_table_is_empty(self, session):
        with session() as s:
            s.execute(text("CREATE TABLE stock_signals (stock_id TEXT, date TEXT)"))
            s.commit()
        assert main._last_signal_date() is None

    def test_latest_processed_date(self, session):
        with session() as s:
            s.execute(text("CREATE TABLE stock_signals (stock_id TEXT, date TEXT)"))
            s.execute(text("INSERT INTO stock_signals VALUES ('A', '2026-10-29'), ('B', '2026-10-30')"))
            s.commit()
        assert main._last_signal_date() == "2026-10-30"


def test_falls_back_to_stock_ranks_when_twse_unreachable(monkeypatch, calls):
    _feeds(monkeypatch, None, tpex_date=None, latest_rank_date="2026-10-26")
    main.nightly_job(now=TUE_0300)
    assert "score" in calls


def test_no_run_when_twse_unreachable_and_ranks_stale(monkeypatch, calls):
    _feeds(monkeypatch, None, tpex_date=None, latest_rank_date="2026-10-23")
    main.nightly_job(now=TUE_0300)
    assert calls == []


def test_signals_failure_does_not_block_score(monkeypatch, calls):
    _feeds(monkeypatch, "2026-10-26", processed="2026-10-23")
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
