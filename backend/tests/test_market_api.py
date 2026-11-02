"""
test_market_api.py — contract + integration tests for the read-only analytics
endpoints. Seeds the crawler-owned tables in the shared temp SQLite, then drives
every route through the real app, the way the frontend does.
"""

import json
import threading
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from main import app
from database import SessionLocal
from models.stock import SectorMap, StockRank
from routers import market, scores

client = TestClient(app)

BARS_DDL = """CREATE TABLE IF NOT EXISTS daily_bars (
    stock_id TEXT NOT NULL, date TEXT NOT NULL, close REAL, volume INTEGER,
    PRIMARY KEY (stock_id, date))"""
FLOWS_DDL = """CREATE TABLE IF NOT EXISTS inst_flows (
    stock_id TEXT NOT NULL, date TEXT NOT NULL,
    foreign_net INTEGER, trust_net INTEGER, dealer_net INTEGER,
    PRIMARY KEY (stock_id, date))"""


def weekdays(n):
    out, d = [], date(2025, 1, 1)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _drop():
    with SessionLocal() as db:
        db.execute(text("DROP TABLE IF EXISTS daily_bars"))
        db.execute(text("DROP TABLE IF EXISTS inst_flows"))
        db.query(SectorMap).delete()
        db.query(StockRank).delete()
        db.commit()
    market.clear_cache()


@pytest.fixture
def tables():
    _drop()
    with SessionLocal() as db:
        db.execute(text(BARS_DDL))
        db.execute(text(FLOWS_DDL))
        db.commit()
    yield
    _drop()


def seed(stocks=6, days=100, step=0.002, sector="半導體"):
    dates = weekdays(days)
    with SessionLocal() as db:
        rows = [
            {"s": f"S{i}", "d": d, "c": round(100 * (1 + step) ** j, 4), "v": 1000 + j}
            for i in range(stocks) for j, d in enumerate(dates)
        ]
        db.execute(text("INSERT INTO daily_bars VALUES (:s, :d, :c, :v)"), rows)
        for i in range(stocks):
            db.add(SectorMap(stock_id=f"S{i}", sector=sector))
        db.commit()
    return dates


def seed_flows(stock_id, dates, foreign=100, trust=20, dealer=-5):
    with SessionLocal() as db:
        db.execute(
            text("INSERT INTO inst_flows VALUES (:s, :d, :f, :t, :x)"),
            [{"s": stock_id, "d": d, "f": foreign, "t": trust, "x": dealer} for d in dates],
        )
        db.commit()


class TestReadFailures:
    class LockedDb:
        def execute(self, *_args, **_kwargs):
            raise OperationalError("SELECT", {}, Exception("database is locked"))

        def rollback(self):
            pass

    def test_a_locked_database_is_not_mistaken_for_no_data(self):
        with pytest.raises(OperationalError):
            market._rows(self.LockedDb(), "SELECT 1")

    def test_a_missing_table_is_empty(self):
        with SessionLocal() as db:
            assert market._rows(db, "SELECT * FROM no_such_table_here") == []

    def test_a_failure_while_computing_memoizes_nothing(self, tables, monkeypatch):
        seed()
        monkeypatch.setattr(market, "_load_bars", lambda db: (_ for _ in ()).throw(RuntimeError("boom")))
        safe = TestClient(app, raise_server_exceptions=False)
        assert safe.get("/api/market/trend").status_code == 500
        monkeypatch.undo()
        assert client.get("/api/market/trend").json()["universe"] == 6

    def test_concurrent_first_requests_compute_once(self, tables, monkeypatch):
        seed()
        calls = []
        real = market.ma.breadth_series
        monkeypatch.setattr(market.ma, "breadth_series", lambda *a: calls.append(1) or real(*a))
        threads = [threading.Thread(target=client.get, args=("/api/market/trend",)) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert calls == [1]

    def test_changing_a_sector_refreshes_rotation(self, tables):
        seed()
        assert client.get("/api/market/trend").json()["sectors"][0]["name"] == "半導體"
        for i in range(6):
            assert client.put(f"/api/sectors/S{i}", json={"stock_id": f"S{i}", "sector": "金融"}).status_code == 200
        assert client.get("/api/market/trend").json()["sectors"][0]["name"] == "金融"


class TestStockHistory:
    def test_empty_when_tables_are_missing(self):
        _drop()
        resp = client.get("/api/stocks/2330/history")
        assert resp.status_code == 200
        assert resp.json() == {"stock_id": "2330", "date": "", "bars": [], "flows": []}

    def test_empty_for_unknown_stock(self, tables):
        seed()
        assert client.get("/api/stocks/9999/history").json()["bars"] == []

    def test_bars_are_ascending_with_moving_averages(self, tables):
        dates = seed(days=70)
        body = client.get("/api/stocks/S0/history").json()
        assert body["date"] == dates[-1]
        assert [b["date"] for b in body["bars"]] == dates
        assert body["bars"][18]["ma20"] is None
        assert body["bars"][19]["ma20"] is not None
        assert body["bars"][58]["ma60"] is None
        assert body["bars"][59]["ma60"] is not None
        assert set(body["bars"][-1]) == {"date", "close", "volume", "ma20", "ma60"}

    def test_window_does_not_null_out_the_moving_average(self, tables):
        seed(days=100)
        bars = client.get("/api/stocks/S0/history", params={"days": 20}).json()["bars"]
        assert len(bars) == 20
        assert bars[0]["ma60"] is not None

    def test_flows_are_included_ascending(self, tables):
        dates = seed()
        seed_flows("S0", dates[-3:])
        flows = client.get("/api/stocks/S0/history").json()["flows"]
        assert [f["date"] for f in flows] == dates[-3:]
        assert flows[0] == {"date": dates[-3], "foreign_net": 100, "trust_net": 20, "dealer_net": -5}

    def test_bars_survive_a_missing_flow_table(self, tables):
        seed()
        with SessionLocal() as db:
            db.execute(text("DROP TABLE inst_flows"))
            db.commit()
        body = client.get("/api/stocks/S0/history").json()
        assert body["bars"] and body["flows"] == []

    @pytest.mark.parametrize("days", [19, 261])
    def test_days_is_bounded(self, tables, days):
        assert client.get("/api/stocks/S0/history", params={"days": days}).status_code == 422

    def test_etag_roundtrip(self, tables):
        seed()
        first = client.get("/api/stocks/S0/history")
        again = client.get("/api/stocks/S0/history", headers={"If-None-Match": first.headers["etag"]})
        assert again.status_code == 304

    def test_does_not_shadow_top100(self, tables):
        assert client.get("/api/stocks/top100").status_code == 200


class TestMarketTrend:
    def test_empty_when_tables_are_missing(self):
        _drop()
        assert client.get("/api/market/trend").json() == {
            "date": "", "universe": 0, "breadth": [], "sectors": [],
        }

    def test_empty_when_tables_have_no_rows(self, tables):
        assert client.get("/api/market/trend").json()["breadth"] == []

    def test_serves_breadth_and_sectors(self, tables):
        dates = seed()
        body = client.get("/api/market/trend", params={"days": 20}).json()
        assert body["date"] == dates[-1]
        assert body["universe"] == 6
        assert len(body["breadth"]) == 20
        assert body["breadth"][0]["ew_index"] == 100.0
        assert body["breadth"][-1]["advancers"] == 6
        assert body["sectors"][0]["name"] == "半導體"
        assert body["sectors"][0]["inst_net_5d"] is None

    def test_sector_flows_join(self, tables):
        dates = seed()
        seed_flows("S0", dates[-5:])
        assert client.get("/api/market/trend").json()["sectors"][0]["inst_net_5d"] == 600

    def test_memoized_until_new_bars_arrive(self, tables, monkeypatch):
        dates = seed()
        client.get("/api/market/trend")
        calls = []
        real = market.ma.breadth_series
        monkeypatch.setattr(market.ma, "breadth_series", lambda *a: calls.append(1) or real(*a))
        client.get("/api/market/trend")
        assert calls == []
        with SessionLocal() as db:
            db.execute(text("INSERT INTO daily_bars VALUES ('S0', '2030-01-01', 200, 1000)"))
            db.commit()
        assert client.get("/api/market/trend").json()["date"] == "2030-01-01"
        assert calls == [1]

    @pytest.mark.parametrize("days", [19, 121])
    def test_days_is_bounded(self, days):
        assert client.get("/api/market/trend", params={"days": days}).status_code == 422

    def test_etag_roundtrip(self, tables):
        seed()
        first = client.get("/api/market/trend")
        assert "max-age" in first.headers["cache-control"]
        again = client.get("/api/market/trend", headers={"If-None-Match": first.headers["etag"]})
        assert again.status_code == 304


class TestBacktest:
    def test_empty_when_tables_are_missing(self):
        _drop()
        assert client.get("/api/market/backtest").json() == {
            "date": "", "horizon": 20, "periods": 0, "baseline": None, "setups": [],
        }

    def test_serves_setups(self, tables):
        dates = seed(stocks=8, days=120)
        body = client.get("/api/market/backtest").json()
        assert body["date"] == dates[-1]
        assert body["horizon"] == 20
        assert body["periods"] > 0
        assert body["baseline"]["win_rate"] == 100.0
        assert {s["key"] for s in body["setups"]} == {"trend_up", "breakout", "near_high", "pullback"}

    def test_horizon_changes_result(self, tables):
        seed(stocks=8, days=120)
        short = client.get("/api/market/backtest", params={"horizon": 5}).json()
        long = client.get("/api/market/backtest", params={"horizon": 60}).json()
        assert short["periods"] > long["periods"]

    @pytest.mark.parametrize("horizon", [1, 19, 250])
    def test_rejects_unsupported_horizon(self, horizon):
        assert client.get("/api/market/backtest", params={"horizon": horizon}).status_code == 422


@pytest.fixture
def score_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(scores, "SCORES_DIR", tmp_path)
    monkeypatch.setattr(scores, "_history_cache", {})
    return tmp_path


def write_score_file(directory, day, entries):
    (directory / f"{day}.json").write_text(
        json.dumps({"date": day, "generated_at": f"{day}T03:00:00+08:00", "scores": entries}),
        encoding="utf-8",
    )


class TestScoreHistory:
    ENTRY = {"score": 17, "max_score": 24, "eligible_count": 23, "pass_rate": 73.9,
             "signal": "buy", "signal_label": "可分批買進", "risk_score": 0}

    def test_empty_when_no_files(self, score_dir):
        assert client.get("/api/scores/2330/history").json() == {"stock_id": "2330", "points": []}

    def test_oldest_first_with_summary_fields_only(self, score_dir):
        write_score_file(score_dir, "2026-10-23", {"2330": {**self.ENTRY, "score": 18}})
        write_score_file(score_dir, "2026-10-22", {"2330": self.ENTRY})
        points = client.get("/api/scores/2330/history").json()["points"]
        assert [p["date"] for p in points] == ["2026-10-22", "2026-10-23"]
        assert points[1]["score"] == 18
        assert set(points[0]) == {"date", "score", "eligible_count", "pass_rate", "signal", "risk_score"}

    def test_skips_files_without_the_stock(self, score_dir):
        write_score_file(score_dir, "2026-10-22", {"2317": self.ENTRY})
        write_score_file(score_dir, "2026-10-23", {"2330": self.ENTRY})
        points = client.get("/api/scores/2330/history").json()["points"]
        assert [p["date"] for p in points] == ["2026-10-23"]

    def test_legacy_entry_has_null_fields(self, score_dir):
        write_score_file(score_dir, "2026-10-22", {"2330": {"score": 12, "max_score": 24}})
        point = client.get("/api/scores/2330/history").json()["points"][0]
        assert point["score"] == 12
        assert point["pass_rate"] is None and point["signal"] is None

    def test_corrupt_file_is_skipped(self, score_dir):
        write_score_file(score_dir, "2026-10-22", {"2330": self.ENTRY})
        (score_dir / "2026-10-23.json").write_text("{not json", encoding="utf-8")
        assert len(client.get("/api/scores/2330/history").json()["points"]) == 1

    def test_rewritten_file_is_picked_up(self, score_dir):
        path = score_dir / "2026-10-23.json"
        write_score_file(score_dir, "2026-10-23", {"2330": self.ENTRY})
        client.get("/api/scores/2330/history")
        write_score_file(score_dir, "2026-10-23", {"2330": {**self.ENTRY, "score": 20}})
        import os
        stat = path.stat()
        os.utime(path, (stat.st_atime, stat.st_mtime + 5))
        assert client.get("/api/scores/2330/history").json()["points"][0]["score"] == 20

    def test_cache_forgets_pruned_files(self, score_dir):
        write_score_file(score_dir, "2026-10-22", {"2330": self.ENTRY})
        write_score_file(score_dir, "2026-10-23", {"2330": self.ENTRY})
        client.get("/api/scores/2330/history")
        (score_dir / "2026-10-22.json").unlink()
        assert len(client.get("/api/scores/2330/history").json()["points"]) == 1
        assert len(scores._history_cache) == 1

    def test_does_not_shadow_detail_route(self, score_dir):
        assert client.get("/api/scores/2330").status_code == 404
