"""
test_score_summary.py — market-level history of the buy-score run.

The 8501 macro dashboard reads how many scored stocks trip 千張大戶退場 as a
distribution signal; score files only live 7 days, so this table is the history.
"""

import json
import os
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import score_summary


def entry(rate, eligible=24, risks=()):
    return {"pass_rate": rate, "eligible_count": eligible,
            "risk_criteria": [{"category": "籌碼排雷", "name": n, "status": "warning"} for n in risks]}


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    with sessionmaker(bind=engine)() as s:
        yield s


class TestSummarize:
    def test_distribution_and_alerts(self):
        scores = {
            "2330": entry(80.0, risks=["千張大戶退場"]),
            "2317": entry(50.0),
            "2454": entry(100.0, risks=["千張大戶退場", "自由現金流轉負"]),
            "1101": entry(0.0),
        }
        s = score_summary.summarize(scores)
        assert s["scored"] == 4
        assert s["median"] == 65.0
        assert s["bins"][0] == 1 and s["bins"][5] == 1 and s["bins"][8] == 1 and s["bins"][9] == 1
        assert s["alerts"] == {"千張大戶退場": 2, "自由現金流轉負": 1}

    def test_na_stocks_are_left_out_not_zero(self):
        scores = {"a": entry(60.0), "b": entry(0.0, eligible=0), "c": {"pass_rate": None, "eligible_count": 5}}
        assert score_summary.summarize(scores)["scored"] == 1

    def test_nothing_scored_is_none(self):
        assert score_summary.summarize({}) is None
        assert score_summary.summarize({"a": entry(0.0, eligible=0)}) is None


class TestRecord:
    def test_upsert_replaces_partial_row(self, session):
        assert score_summary.record(session, "2026-11-06", {"a": entry(40.0, risks=["千張大戶退場"])}, partial=True)
        assert score_summary.record(session, "2026-11-06", {"a": entry(40.0), "b": entry(60.0)})
        rows = session.execute(text("SELECT scored, partial FROM score_summary_daily")).fetchall()
        assert rows == [(2, 0)]
        alerts = session.execute(text("SELECT * FROM score_alert_daily")).fetchall()
        assert alerts == []          # the replaced run had no hits

    def test_empty_run_writes_nothing(self, session):
        assert score_summary.record(session, "2026-11-06", {}) is False
        score_summary.ensure_tables(session)
        assert session.execute(text("SELECT COUNT(*) FROM score_summary_daily")).scalar() == 0

    def test_bins_stored_as_json(self, session):
        score_summary.record(session, "2026-11-06", {"a": entry(55.0)})
        bins = session.execute(text("SELECT bins FROM score_summary_daily")).scalar()
        assert json.loads(bins)[5] == 1

    def test_prune_keeps_latest(self, session):
        for d in ("2026-11-03", "2026-11-04", "2026-11-05"):
            score_summary.record(session, d, {"a": entry(50.0, risks=["千張大戶退場"])})
        score_summary.prune(session, keep=2)
        dates = [r[0] for r in session.execute(text("SELECT date FROM score_summary_daily ORDER BY date"))]
        assert dates == ["2026-11-04", "2026-11-05"]
        assert session.execute(text("SELECT COUNT(*) FROM score_alert_daily WHERE date='2026-11-03'")).scalar() == 0


class TestScoreJobHook:
    def test_summary_failure_never_breaks_scoring(self, monkeypatch):
        pytest.importorskip("apscheduler")
        import main
        monkeypatch.setattr(main, "Session", MagicMock(side_effect=RuntimeError("db locked")))
        main._record_summary("2026-11-06", {"a": entry(50.0)})   # logs, does not raise
