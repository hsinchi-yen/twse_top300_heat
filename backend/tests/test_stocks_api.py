"""
test_stocks_api.py — /tdd: API contract tests for GET /api/stocks/top100
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from main import app

client = TestClient(app)


def _make_stock(stock_id, name, volume_rank, turnover_rank, pct):
    m = MagicMock()
    m.stock_id = stock_id
    m.name = name
    m.date = "2026-05-16"
    m.volume = 1000 * (101 - volume_rank)
    m.turnover_rate = round(1.0 / turnover_rank, 4)
    m.price_change_pct = pct
    m.color_tier = "neutral"
    m.volume_rank = volume_rank
    m.turnover_rank = turnover_rank
    return m


@pytest.fixture
def mock_db_stocks():
    """100 mock stocks with distinct ranks."""
    return [_make_stock(str(2000 + i), f"股票{i}", i, 101 - i, 0.0) for i in range(1, 101)]


@pytest.fixture
def mock_db_sectors():
    from unittest.mock import MagicMock
    rows = []
    for i in range(1, 21):
        r = MagicMock()
        r.stock_id = str(2000 + i)
        r.sector = "半導體"
        rows.append(r)
    return rows


class TestTop100Endpoint:
    def test_returns_200(self):
        response = client.get("/api/stocks/top100?mode=volume")
        assert response.status_code == 200

    def test_response_has_required_top_level_keys(self):
        response = client.get("/api/stocks/top100?mode=volume")
        data = response.json()
        for key in ("mode", "date", "market_open", "updated_at", "sectors"):
            assert key in data, f"Missing key: {key}"

    def test_mode_volume_reflected_in_response(self):
        response = client.get("/api/stocks/top100?mode=volume")
        assert response.json()["mode"] == "volume"

    def test_mode_turnover_reflected_in_response(self):
        response = client.get("/api/stocks/top100?mode=turnover")
        assert response.json()["mode"] == "turnover"

    def test_invalid_mode_returns_422(self):
        response = client.get("/api/stocks/top100?mode=invalid")
        assert response.status_code == 422

    def test_sectors_is_a_list(self):
        response = client.get("/api/stocks/top100?mode=volume")
        assert isinstance(response.json()["sectors"], list)

    def test_each_sector_has_name_and_stocks(self):
        response = client.get("/api/stocks/top100?mode=volume")
        for sector in response.json()["sectors"]:
            assert "name" in sector
            assert "stocks" in sector
            assert isinstance(sector["stocks"], list)

    def test_each_stock_has_required_fields(self):
        response = client.get("/api/stocks/top100?mode=volume")
        for sector in response.json()["sectors"]:
            for stock in sector["stocks"]:
                for field in ("stock_id", "name", "rank", "volume", "turnover_rate", "price_change_pct", "color_tier"):
                    assert field in stock, f"Stock missing field: {field}"

    def test_market_open_is_boolean(self):
        response = client.get("/api/stocks/top100?mode=volume")
        assert isinstance(response.json()["market_open"], bool)

    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
