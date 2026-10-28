"""
test_watchlist_api.py — contract tests for /api/watchlist (GET / PUT / DELETE)

Uses the shared temp SQLite from conftest.py. Each test inserts its own
stock_ranks / sector_map rows and removes them afterwards so other suites that
read the "latest trading date" are unaffected.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from main import app
from database import SessionLocal

client = TestClient(app)

LATEST = "2026-10-23"
OLDER = "2026-10-22"


def _rank_row(stock_id, name, date, volume_rank, volume=1_000_000):
    return {
        "stock_id": stock_id, "name": name, "date": date, "volume": volume,
        "close_price": 100.0, "turnover_rate": 0.5, "price_change_pct": 1.2,
        "color_tier": "light_red", "volume_rank": volume_rank, "turnover_rank": volume_rank,
    }


@pytest.fixture
def market():
    """Latest date has 2330 / 2317 / 6488; 1234 only exists on an older date."""
    rows = [
        _rank_row("2330", "台積電", LATEST, 1),
        _rank_row("2317", "鴻海", LATEST, 2),
        _rank_row("6488", "環球晶", LATEST, 650),
        _rank_row("1234", "舊股", OLDER, 900),
    ]
    with SessionLocal() as db:
        for r in rows:
            db.execute(text("""
                INSERT INTO stock_ranks (stock_id, name, date, volume, close_price, turnover_rate,
                                         price_change_pct, color_tier, volume_rank, turnover_rank)
                VALUES (:stock_id, :name, :date, :volume, :close_price, :turnover_rate,
                        :price_change_pct, :color_tier, :volume_rank, :turnover_rank)
            """), r)
        db.execute(text("INSERT INTO sector_map (stock_id, sector) VALUES ('2330', '半導體')"))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(text("DELETE FROM stock_ranks WHERE date IN (:a, :b)"), {"a": LATEST, "b": OLDER})
        db.execute(text("DELETE FROM sector_map WHERE stock_id = '2330'"))
        db.execute(text("DELETE FROM watchlist"))
        db.commit()


class TestWatchlistGet:
    def test_empty(self, market):
        assert client.get("/api/watchlist").json() == {"items": []}

    def test_items_carry_quote_with_sector_and_rank(self, market):
        client.put("/api/watchlist/2330")
        item = client.get("/api/watchlist").json()["items"][0]
        assert item["stock_id"] == "2330"
        assert item["note"] == ""
        assert item["added_at"]
        q = item["quote"]
        assert q["name"] == "台積電"
        assert q["rank"] == 1
        assert q["close_price"] == 100.0
        assert q["sector"] == "半導體"

    def test_quote_for_stock_outside_display_pool(self, market):
        client.put("/api/watchlist/6488")
        q = client.get("/api/watchlist").json()["items"][0]["quote"]
        assert q["rank"] == 650
        assert q["sector"] == "其他"

    def test_quote_null_when_no_row_on_latest_date(self, market):
        with SessionLocal() as db:
            db.execute(text(
                "INSERT INTO watchlist (stock_id, note, added_at) VALUES ('1234', '', '2026-10-01T00:00:00+08:00')"
            ))
            db.commit()
        item = client.get("/api/watchlist").json()["items"][0]
        assert item["stock_id"] == "1234"
        assert item["quote"] is None

    def test_ordered_by_added_at(self, market):
        client.put("/api/watchlist/2317")
        client.put("/api/watchlist/2330")
        ids = [i["stock_id"] for i in client.get("/api/watchlist").json()["items"]]
        assert ids == ["2317", "2330"]


class TestWatchlistPut:
    def test_add_returns_item(self, market):
        resp = client.put("/api/watchlist/2330", json={"note": "等回測月線"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["stock_id"] == "2330"
        assert body["note"] == "等回測月線"
        assert body["quote"]["name"] == "台積電"

    def test_reput_without_body_keeps_note_and_added_at(self, market):
        first = client.put("/api/watchlist/2330", json={"note": "理由A"}).json()
        again = client.put("/api/watchlist/2330").json()
        assert again["note"] == "理由A"
        assert again["added_at"] == first["added_at"]

    def test_reput_with_note_replaces_note(self, market):
        client.put("/api/watchlist/2330", json={"note": "理由A"})
        again = client.put("/api/watchlist/2330", json={"note": "理由B"}).json()
        assert again["note"] == "理由B"

    def test_unknown_stock_is_404(self, market):
        assert client.put("/api/watchlist/9999").status_code == 404

    def test_stock_only_on_older_date_is_404(self, market):
        assert client.put("/api/watchlist/1234").status_code == 404

    def test_exceeding_max_is_409(self, market):
        with patch("routers.watchlist.WATCHLIST_MAX", 2):
            assert client.put("/api/watchlist/2330").status_code == 200
            assert client.put("/api/watchlist/2317").status_code == 200
            assert client.put("/api/watchlist/6488").status_code == 409

    def test_reput_existing_at_max_is_allowed(self, market):
        with patch("routers.watchlist.WATCHLIST_MAX", 1):
            client.put("/api/watchlist/2330")
            assert client.put("/api/watchlist/2330", json={"note": "x"}).status_code == 200

    def test_note_too_long_is_422(self, market):
        assert client.put("/api/watchlist/2330", json={"note": "x" * 501}).status_code == 422


class TestWatchlistDelete:
    def test_delete_existing(self, market):
        client.put("/api/watchlist/2330")
        resp = client.delete("/api/watchlist/2330")
        assert resp.status_code == 204
        assert client.get("/api/watchlist").json() == {"items": []}

    def test_delete_missing_is_204(self, market):
        assert client.delete("/api/watchlist/2330").status_code == 204
