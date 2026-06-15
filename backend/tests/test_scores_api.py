"""
test_scores_api.py — API contract tests for GET /api/scores

Score computation now lives entirely in the crawler; the backend only serves
the shared JSON and signals a force refresh via a flag file. These tests cover
the serving contract and the flag-file coordination.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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
        with patch("routers.scores._load", return_value=EMPTY_PAYLOAD), \
             patch("routers.scores._is_fetching", return_value=False):
            data = client.get("/api/scores").json()
        assert data["scores"] == {}

    def test_empty_date_when_no_cache(self):
        with patch("routers.scores._load", return_value=EMPTY_PAYLOAD), \
             patch("routers.scores._is_fetching", return_value=False):
            data = client.get("/api/scores").json()
        assert data["date"] == ""

    def test_still_returns_200_when_no_cache(self):
        with patch("routers.scores._load", return_value=EMPTY_PAYLOAD), \
             patch("routers.scores._is_fetching", return_value=False):
            resp = client.get("/api/scores")
        assert resp.status_code == 200

    def test_response_has_fetching_false_when_cache_exists(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD), \
             patch("routers.scores._is_fetching", return_value=False):
            data = client.get("/api/scores").json()
        assert data.get("fetching") is False

    def test_cache_hit_ignores_token(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD), \
             patch("routers.scores._is_fetching", return_value=False):
            data = client.get(
                "/api/scores",
                headers={"X-FinMind-Token": "some-token"},
            ).json()
        assert data["scores"] == SAMPLE_PAYLOAD["scores"]
        assert data.get("fetching") is False


class TestForceRefresh:
    """force=true signals the crawler via a flag file; it does not compute here."""

    def test_force_requests_refresh_when_idle(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD), \
             patch("routers.scores._is_fetching", return_value=False), \
             patch("routers.scores._request_force_refresh") as mock_req:
            resp = client.get("/api/scores?force=true")
        assert resp.status_code == 200
        mock_req.assert_called_once()

    def test_force_skipped_when_already_fetching(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD), \
             patch("routers.scores._is_fetching", return_value=True), \
             patch("routers.scores._request_force_refresh") as mock_req:
            data = client.get("/api/scores?force=true").json()
        mock_req.assert_not_called()
        assert data.get("fetching") is True

    def test_normal_get_does_not_request_refresh(self):
        with patch("routers.scores._load", return_value=SAMPLE_PAYLOAD), \
             patch("routers.scores._is_fetching", return_value=False), \
             patch("routers.scores._request_force_refresh") as mock_req:
            client.get("/api/scores")
        mock_req.assert_not_called()

    def test_request_force_refresh_writes_flag_file(self):
        from routers import scores as scores_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_dir = Path(tmpdir) / "buy_scores"
            with patch.object(scores_mod, "SCORES_DIR", scores_dir), \
                 patch.object(scores_mod, "FORCE_REFRESH_FLAG", scores_dir / ".force_refresh"):
                scores_mod._request_force_refresh()
                assert (scores_dir / ".force_refresh").exists()

    def test_is_fetching_reflects_progress_flag(self):
        from routers import scores as scores_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_dir = Path(tmpdir)
            progress = scores_dir / ".scoring_in_progress"
            force = scores_dir / ".force_refresh"
            with patch.object(scores_mod, "SCORING_IN_PROGRESS_FLAG", progress), \
                 patch.object(scores_mod, "FORCE_REFRESH_FLAG", force):
                assert scores_mod._is_fetching() is False
                progress.write_text("x", encoding="utf-8")
                assert scores_mod._is_fetching() is True


class TestStaleFlagRecovery:
    """An orphaned flag from a crashed run must not pin fetching=true forever."""

    def _make_flag(self, path: Path, age_seconds: float):
        path.write_text("x", encoding="utf-8")
        past = time.time() - age_seconds
        os.utime(path, (past, past))

    def test_fresh_in_progress_flag_reports_fetching(self):
        from routers import scores as scores_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            progress = Path(tmpdir) / ".scoring_in_progress"
            force = Path(tmpdir) / ".force_refresh"
            with patch.object(scores_mod, "SCORING_IN_PROGRESS_FLAG", progress), \
                 patch.object(scores_mod, "FORCE_REFRESH_FLAG", force), \
                 patch.object(scores_mod, "SCORING_FLAG_STALE_S", 10800):
                self._make_flag(progress, age_seconds=60)
                assert scores_mod._is_fetching() is True

    def test_stale_in_progress_flag_ignored(self):
        from routers import scores as scores_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            progress = Path(tmpdir) / ".scoring_in_progress"
            force = Path(tmpdir) / ".force_refresh"
            with patch.object(scores_mod, "SCORING_IN_PROGRESS_FLAG", progress), \
                 patch.object(scores_mod, "FORCE_REFRESH_FLAG", force), \
                 patch.object(scores_mod, "SCORING_FLAG_STALE_S", 10800):
                self._make_flag(progress, age_seconds=20000)
                assert scores_mod._is_fetching() is False

    def test_force_resumes_after_stale_flag(self):
        """With only a stale flag present, force=true must re-request a refresh."""
        from routers import scores as scores_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            scores_dir = Path(tmpdir)
            progress = scores_dir / ".scoring_in_progress"
            force = scores_dir / ".force_refresh"
            with patch.object(scores_mod, "SCORING_IN_PROGRESS_FLAG", progress), \
                 patch.object(scores_mod, "FORCE_REFRESH_FLAG", force), \
                 patch.object(scores_mod, "SCORING_FLAG_STALE_S", 10800), \
                 patch("routers.scores._load", return_value=SAMPLE_PAYLOAD), \
                 patch("routers.scores._request_force_refresh") as mock_req:
                self._make_flag(progress, age_seconds=20000)
                resp = client.get("/api/scores?force=true")
        assert resp.status_code == 200
        mock_req.assert_called_once()
