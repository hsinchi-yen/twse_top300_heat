"""
test_signals_api.py — contract tests for GET /api/signals

stock_signals is created and owned by the crawler; tests create / drop it
themselves in the shared temp SQLite.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from main import app
from database import SessionLocal

client = TestClient(app)

DDL = """CREATE TABLE IF NOT EXISTS stock_signals (
    stock_id TEXT PRIMARY KEY, date TEXT, generated_at TEXT,
    close REAL, avg_volume_5d INTEGER, vol_ratio REAL,
    ma20 REAL, ma60 REAL, high_52w REAL, pct_from_52w_high REAL,
    inst_net_5d INTEGER, inst_streak INTEGER,
    foreign_net_1d INTEGER, trust_net_1d INTEGER)"""

ROW = {
    "stock_id": "2330", "date": "2026-10-23", "generated_at": "2026-10-24T03:05:00+08:00",
    "close": 1045.0, "avg_volume_5d": 41000000, "vol_ratio": 1.1,
    "ma20": 1010.5, "ma60": 1100.0, "high_52w": 1100.0, "pct_from_52w_high": -5.0,
    "inst_net_5d": 12500, "inst_streak": 3, "foreign_net_1d": 3200, "trust_net_1d": 400,
}


def _drop():
    with SessionLocal() as db:
        db.execute(text("DROP TABLE IF EXISTS stock_signals"))
        db.commit()


@pytest.fixture
def table():
    _drop()
    with SessionLocal() as db:
        db.execute(text(DDL))
        db.commit()
    yield
    _drop()


def _insert(**overrides):
    row = {**ROW, **overrides}
    cols = ", ".join(row)
    with SessionLocal() as db:
        db.execute(text(f"INSERT INTO stock_signals ({cols}) VALUES ({', '.join(':' + c for c in row)})"), row)
        db.commit()


class TestSignalsEndpoint:
    def test_empty_when_table_missing(self):
        _drop()
        resp = client.get("/api/signals")
        assert resp.status_code == 200
        assert resp.json() == {"date": "", "generated_at": "", "signals": {}}

    def test_empty_when_no_rows(self, table):
        assert client.get("/api/signals").json()["signals"] == {}

    def test_serves_row_with_derived_ma_flags(self, table):
        _insert()
        body = client.get("/api/signals").json()
        assert body["date"] == "2026-10-23"
        assert body["generated_at"] == "2026-10-24T03:05:00+08:00"
        s = body["signals"]["2330"]
        assert s["inst_streak"] == 3
        assert s["vol_ratio"] == 1.1
        assert s["above_ma20"] is True
        assert s["above_ma60"] is False
        assert "stock_id" not in s and "date" not in s

    def test_null_ma_gives_null_flag(self, table):
        _insert(ma60=None, ma20=None)
        s = client.get("/api/signals").json()["signals"]["2330"]
        assert s["above_ma20"] is None
        assert s["above_ma60"] is None
        assert s["ma60"] is None

    def test_null_close_gives_null_flags(self, table):
        _insert(close=None)
        s = client.get("/api/signals").json()["signals"]["2330"]
        assert s["above_ma20"] is None

    def test_etag_roundtrip(self, table):
        _insert()
        first = client.get("/api/signals")
        etag = first.headers["etag"]
        assert "max-age" in first.headers["cache-control"]
        again = client.get("/api/signals", headers={"If-None-Match": etag})
        assert again.status_code == 304
