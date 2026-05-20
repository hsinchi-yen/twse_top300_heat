"""
test_scores_api.py — TDD API contract tests for GET /api/scores
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app

client = TestClient(app)

SAMPLE_PAYLOAD = {
    "date": "2026-05-19",
    "generated_at": "2026-05-19T16:15:00+08:00",
    "scores": {
        "2330": {"score": 18, "max_score": 24},
        "2317": {"score": 12, "max_score": 24},
        "2454": {"score": 0,  "max_score": 24},
    },
}

EMPTY_PAYLOAD = {}


class TestScoresEndpointShape:
    def test_returns_200(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            resp = client.get("/api/scores")
        assert resp.status_code == 200

    def test_content_type_is_json(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            resp = client.get("/api/scores")
        assert "application/json" in resp.headers["content-type"]

    def test_response_has_scores_key(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            data = client.get("/api/scores").json()
        assert "scores" in data

    def test_response_has_date_key(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            data = client.get("/api/scores").json()
        assert "date" in data


class TestScoresEndpointData:
    def test_scores_contains_expected_stock_ids(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            data = client.get("/api/scores").json()
        assert "2330" in data["scores"]
        assert "2317" in data["scores"]

    def test_score_entry_has_score_field(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            entry = client.get("/api/scores").json()["scores"]["2330"]
        assert "score" in entry

    def test_score_entry_has_max_score_field(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            entry = client.get("/api/scores").json()["scores"]["2330"]
        assert "max_score" in entry

    def test_score_values_are_correct(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            entry = client.get("/api/scores").json()["scores"]["2330"]
        assert entry["score"] == 18
        assert entry["max_score"] == 24

    def test_score_of_zero_is_not_treated_as_missing(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            entry = client.get("/api/scores").json()["scores"]["2454"]
        assert entry["score"] == 0

    def test_date_value_is_correct(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            data = client.get("/api/scores").json()
        assert data["date"] == "2026-05-19"


class TestScoresEndpointFallback:
    def test_empty_scores_when_no_cache(self):
        with patch("routers.scores._load", return_value=EMPTY_PAYLOAD):
            data = client.get("/api/scores").json()
        assert data["scores"] == {}

    def test_empty_date_when_no_cache(self):
        with patch("routers.scores._load", return_value=EMPTY_PAYLOAD):
            data = client.get("/api/scores").json()
        assert data["date"] == ""

    def test_still_returns_200_when_no_cache(self):
        with patch("routers.scores._load", return_value=EMPTY_PAYLOAD):
            resp = client.get("/api/scores")
        assert resp.status_code == 200

    def test_response_has_fetching_false_when_cache_exists(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            data = client.get("/api/scores").json()
        assert data.get("fetching") is False

    def test_fetching_true_when_no_cache_and_token_provided(self):
        with patch("routers.scores._load", return_value=EMPTY_PAYLOAD):
            with patch("routers.scores._is_fetching", False):
                with patch("routers.scores._background_score_fetch"):
                    with patch("routers.scores._get_stock_ids", return_value=["2330", "2317"]):
                        data = client.get(
                            "/api/scores",
                            headers={"X-FinMind-Token": "test-token"},
                        ).json()
        assert data.get("fetching") is True

    def test_fetching_false_when_no_token_no_cache(self):
        with patch("routers.scores._load", return_value=EMPTY_PAYLOAD):
            with patch("routers.scores._is_fetching", False):
                data = client.get("/api/scores").json()
        assert data.get("fetching") is False

    def test_cache_hit_ignores_token(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD):
            data = client.get(
                "/api/scores",
                headers={"X-FinMind-Token": "some-token"},
            ).json()
        assert data["scores"] == SAMPLE_PAYLOAD["scores"]
        assert data.get("fetching") is False
