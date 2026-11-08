"""
test_alert_counts_api.py — /api/market/alert-counts across the crawler seam.

The crawler's real score_summary.record() writes the tables, the real API reads
them, as the two containers share /app/data in production.
"""

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

# Appended, not prepended: `main` must keep resolving to the backend.
sys.path.append(str(Path(__file__).resolve().parents[2] / "crawler"))

from main import app  # noqa: E402
from database import SessionLocal  # noqa: E402

score_summary = importlib.import_module("score_summary")
client = TestClient(app)


def entry(rate, risks=()):
    return {"pass_rate": rate, "eligible_count": 24,
            "risk_criteria": [{"name": n, "status": "warning"} for n in risks]}


def _drop():
    with SessionLocal() as db:
        db.execute(text("DROP TABLE IF EXISTS score_summary_daily"))
        db.execute(text("DROP TABLE IF EXISTS score_alert_daily"))
        db.commit()


@pytest.fixture
def recorded():
    _drop()
    with SessionLocal() as db:
        score_summary.record(db, "2026-11-04", {"a": entry(40.0, ["千張大戶退場"]), "b": entry(60.0)})
        score_summary.record(db, "2026-11-05", {"a": entry(40.0), "b": entry(60.0)})
        score_summary.record(db, "2026-11-06",
                             {"a": entry(40.0, ["千張大戶退場"]), "b": entry(60.0, ["千張大戶退場"]),
                              "c": entry(90.0, ["自由現金流轉負"]), "d": entry(10.0)}, partial=True)
    yield
    _drop()


def test_missing_tables_give_empty_state():
    _drop()
    res = client.get("/api/market/alert-counts")
    assert res.status_code == 200
    assert res.json() == {"date": "", "summary": [], "alerts": []}


def test_series_are_aligned_and_ascending(recorded):
    body = client.get("/api/market/alert-counts").json()
    assert body["date"] == "2026-11-06"
    assert [s["date"] for s in body["summary"]] == ["2026-11-04", "2026-11-05", "2026-11-06"]
    assert body["summary"][-1]["partial"] is True and body["summary"][0]["partial"] is False
    whale = next(a for a in body["alerts"] if a["name"] == "千張大戶退場")
    assert whale["counts"] == [1, 0, 2]                # a day without hits is 0, not missing
    assert whale["shares"] == [50.0, 0.0, 50.0]


def test_days_limits_recorded_dates(recorded):
    body = client.get("/api/market/alert-counts?days=5").json()
    assert len(body["summary"]) == 3
    assert client.get("/api/market/alert-counts?days=2").status_code == 422


def test_etag_round_trip(recorded):
    first = client.get("/api/market/alert-counts")
    again = client.get("/api/market/alert-counts", headers={"If-None-Match": first.headers["ETag"]})
    assert again.status_code == 304
