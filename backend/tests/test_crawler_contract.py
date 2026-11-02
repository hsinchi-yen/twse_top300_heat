"""
test_crawler_contract.py — end-to-end across the crawler/backend seam.

The backend reads tables and JSON the crawler owns, so a drift there would pass
both suites' unit tests and fail only in production. Here the crawler's real
storage code writes and the real API reads, the way the two containers share
/app/data. Skipped where the crawler's dependencies are not installed.
"""

import importlib
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

pytest.importorskip("pandas")

# Appended, not prepended: `main` must keep resolving to the backend.
sys.path.append(str(Path(__file__).resolve().parents[2] / "crawler"))

from main import app  # noqa: E402
from database import SessionLocal  # noqa: E402
from models.stock import SectorMap  # noqa: E402
from routers import market, scores as scores_api  # noqa: E402

crawler_signals = importlib.import_module("signals")
crawler_scores = importlib.import_module("sources.buy_score")

client = TestClient(app)
STOCKS = [f"S{i}" for i in range(6)]
DAYS = 130


def trading_days(n):
    out, d = [], date(2026, 1, 1)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _clean():
    with SessionLocal() as db:
        for table in ("daily_bars", "inst_flows", "stock_signals", "signal_backfill"):
            db.execute(text(f"DROP TABLE IF EXISTS {table}"))
        db.query(SectorMap).delete()
        db.commit()
    market.clear_cache()


@pytest.fixture
def pipeline():
    """One nightly pass through the crawler's own storage functions."""
    _clean()
    days = trading_days(DAYS)
    with SessionLocal() as db:
        crawler_signals.ensure_tables(db)
        for j, day in enumerate(days):
            crawler_signals.upsert_bars(db, day, [
                {"stock_id": sid, "close_price": 100 * 1.002 ** j + i, "volume": 1_000_000 + j}
                for i, sid in enumerate(STOCKS)
            ], set(STOCKS))
        for day in days[-6:]:
            crawler_signals.upsert_flows(db, day, {
                sid: {"foreign_net": 100, "trust_net": 20, "dealer_net": -5} for sid in STOCKS
            })
        crawler_signals.rebuild_signals(db, STOCKS, days[-1], f"{days[-1]}T03:05:00+08:00")
        for sid in STOCKS:
            db.add(SectorMap(stock_id=sid, sector="半導體"))
        db.commit()
    yield days
    _clean()


class TestNightlyTablesReachTheApi:
    def test_signals(self, pipeline):
        body = client.get("/api/signals").json()
        assert body["date"] == pipeline[-1]
        assert set(body["signals"]) == set(STOCKS)
        assert body["signals"]["S0"]["inst_streak"] == 6
        assert body["signals"]["S0"]["inst_net_5d"] == 600
        assert body["signals"]["S0"]["above_ma20"] is True

    def test_history_shows_what_the_crawler_stored(self, pipeline):
        body = client.get("/api/stocks/S0/history").json()
        assert body["date"] == pipeline[-1]
        assert len(body["bars"]) == DAYS
        assert [f["date"] for f in body["flows"]] == pipeline[-6:]
        assert body["flows"][-1]["dealer_net"] == -5

    def test_chart_averages_agree_with_card_signals(self, pipeline):
        """The panel's MA line and the card's 站上月線 must describe the same number."""
        signal = client.get("/api/signals").json()["signals"]["S2"]
        bar = client.get("/api/stocks/S2/history").json()["bars"][-1]
        assert bar["ma20"] == signal["ma20"]
        assert bar["ma60"] == signal["ma60"]
        assert bar["close"] == signal["close"]

    def test_market_trend(self, pipeline):
        body = client.get("/api/market/trend").json()
        assert body["date"] == pipeline[-1]
        assert body["universe"] == len(STOCKS)
        assert body["breadth"][-1]["advancers"] == len(STOCKS)
        assert body["sectors"][0]["name"] == "半導體"
        assert body["sectors"][0]["inst_net_5d"] == 3600   # 6 stocks × 5 days × 120

    def test_backtest(self, pipeline):
        body = client.get("/api/market/backtest").json()
        assert body["date"] == pipeline[-1]
        assert body["periods"] >= 2
        assert body["baseline"]["win_rate"] == 100.0

    def test_analytics_refresh_after_the_next_nightly_run(self, pipeline):
        client.get("/api/market/trend")
        next_day = "2027-01-04"
        with SessionLocal() as db:
            crawler_signals.upsert_bars(db, next_day, [
                {"stock_id": sid, "close_price": 150, "volume": 1000} for sid in STOCKS
            ], set(STOCKS))
        assert client.get("/api/market/trend").json()["date"] == next_day

    def test_pruned_history_is_still_served(self, pipeline, monkeypatch):
        monkeypatch.setattr(crawler_signals, "BAR_KEEP_DAYS", 100)
        monkeypatch.setattr(crawler_signals, "INST_KEEP_DAYS", 3)
        with SessionLocal() as db:
            crawler_signals.prune(db)
        body = client.get("/api/stocks/S0/history").json()
        assert len(body["bars"]) == 100
        assert len(body["flows"]) == 3


SUMMARY = {
    "score": 18, "max_score": 24, "eligible_count": 23, "pass_rate": 78.3,
    "signal": "strong_buy", "signal_label": "建議買進", "risk_score": 0, "risk_flags": [],
    "fundamentals_uptrend": True, "pe": {"current": 20.0, "median": 25.0, "p25": 18.0},
}
DETAIL = {
    "criteria": [{"id": "roe", "label": "ROE", "weight": 2, "pass": True, "value": 20,
                  "value_label": "20%", "threshold": "> 12%", "warning": None}],
    "risk_criteria": [],
}


@pytest.fixture
def score_store(tmp_path, monkeypatch):
    monkeypatch.setattr(crawler_scores, "SCORES_DIR", tmp_path)
    monkeypatch.setattr(scores_api, "SCORES_DIR", tmp_path)
    monkeypatch.setattr(scores_api, "DETAILS_DIR", tmp_path / "details")
    monkeypatch.setattr(scores_api, "FORCE_REFRESH_FLAG", tmp_path / ".force_refresh")
    monkeypatch.setattr(scores_api, "SCORING_IN_PROGRESS_FLAG", tmp_path / ".scoring_in_progress")
    monkeypatch.setattr(scores_api, "SCORE_PROGRESS_FLAG", tmp_path / ".score_progress")
    monkeypatch.setattr(scores_api, "_cache", {})
    monkeypatch.setattr(scores_api, "_detail_cache", {})
    monkeypatch.setattr(scores_api, "_history_cache", {})
    return tmp_path


class TestScoreFilesReachTheApi:
    def test_summary_detail_and_history(self, score_store):
        crawler_scores.write_scores({"2330": {**SUMMARY, "score": 17, "detail": DETAIL}}, "2026-10-22")
        crawler_scores.write_scores({"2330": {**SUMMARY, "detail": DETAIL}}, "2026-10-23")

        summary = client.get("/api/scores").json()
        assert summary["date"] == "2026-10-23"
        assert summary["scores"]["2330"]["signal"] == "strong_buy"
        assert "detail" not in summary["scores"]["2330"]

        assert client.get("/api/scores/2330").json()["criteria"][0]["id"] == "roe"

        points = client.get("/api/scores/2330/history").json()["points"]
        assert [(p["date"], p["score"]) for p in points] == [("2026-10-22", 17), ("2026-10-23", 18)]
        assert points[1]["pass_rate"] == 78.3
        assert points[1]["signal"] == "strong_buy"

    def test_history_never_reads_the_details_directory(self, score_store):
        crawler_scores.write_scores({"2330": {**SUMMARY, "detail": DETAIL}}, "2026-10-23")
        assert (score_store / "details" / "2026-10-23.json").exists()
        assert len(client.get("/api/scores/2330/history").json()["points"]) == 1

    def test_history_follows_the_crawlers_retention(self, score_store):
        days = [f"2026-10-{d:02d}" for d in range(10, 20)]
        for day in days:
            crawler_scores.write_scores({"2330": dict(SUMMARY)}, day)
        points = client.get("/api/scores/2330/history").json()["points"]
        assert [p["date"] for p in points] == days[-crawler_scores.MAX_KEEP_DAYS:]
