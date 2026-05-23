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


class TestFetchPassBugFixes:
    """Regression tests for the three bugs fixed in _fetch_pass /
    _background_score_fetch."""

    def _make_responses(self, pattern: list):
        """Build a list of mock httpx.Response objects from a status-code list."""
        import httpx as _httpx

        resps = []
        for code in pattern:
            if code == 200:
                r = _httpx.Response(200, json={"score": 10, "max_score": 24})
            else:
                r = _httpx.Response(code)
            resps.append(r)
        return resps

    # ── Bug 1: scattered failures must appear in retry_ids ────────────────
    def test_scattered_failures_returned_for_retry(self):
        """Non-consecutive failures must be included in retry_ids (Bug 1)."""
        from routers.scores import _fetch_pass

        # Pattern: FAIL, OK, FAIL, OK, OK — no consecutive 5 failures
        responses = self._make_responses([500, 200, 500, 200, 200])
        scores: dict = {}
        with patch("routers.scores.httpx.get", side_effect=responses), \
             patch("routers.scores._write_partial"), \
             patch("routers.scores.time.sleep"):
            retry_ids, rate_limited = _fetch_pass(
                ["A", "B", "C", "D", "E"], scores, {}, "2026-01-01", 1, 5
            )

        assert rate_limited is False
        assert "A" in retry_ids   # first scattered failure
        assert "C" in retry_ids   # second scattered failure
        assert "B" not in retry_ids
        assert "D" not in retry_ids
        assert "E" not in retry_ids

    def test_all_success_returns_empty_retry(self):
        """All-success pass must return empty retry list and rate_limited=False."""
        from routers.scores import _fetch_pass

        responses = self._make_responses([200, 200, 200])
        scores: dict = {}
        with patch("routers.scores.httpx.get", side_effect=responses), \
             patch("routers.scores._write_partial"), \
             patch("routers.scores.time.sleep"):
            retry_ids, rate_limited = _fetch_pass(
                ["A", "B", "C"], scores, {}, "2026-01-01", 1, 3
            )

        assert retry_ids == []
        assert rate_limited is False

    def test_five_consecutive_failures_triggers_rate_limit(self):
        """Five consecutive failures must set rate_limited=True."""
        from routers.scores import _fetch_pass

        responses = self._make_responses([500, 500, 500, 500, 500])
        scores: dict = {}
        with patch("routers.scores.httpx.get", side_effect=responses), \
             patch("routers.scores._write_partial"), \
             patch("routers.scores.time.sleep"):
            retry_ids, rate_limited = _fetch_pass(
                ["A", "B", "C", "D", "E"], scores, {}, "2026-01-01", 1, 5
            )

        assert rate_limited is True
        assert set(retry_ids) == {"A", "B", "C", "D", "E"}

    # ── Bug 2: force=True must not pre-load stale scores ──────────────────
    def test_force_true_starts_with_empty_scores(self):
        """force=True must not carry stale scores from a previous file (Bug 2)."""
        import tempfile, json, os
        from pathlib import Path
        from routers import scores as scores_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            scores_dir = Path(tmpdir)
            old_file = scores_dir / "2026-04-01.json"
            old_file.write_text(json.dumps({
                "date": "2026-04-01",
                "generated_at": "2026-04-01T03:00:00+08:00",
                "scores": {"2330": {"score": 0, "max_score": 24}},
            }), encoding="utf-8")

            original_dir = scores_mod.SCORES_DIR
            scores_mod.SCORES_DIR = scores_dir
            try:
                # With force=True the background fetch must start with scores={}
                # so the stale 0 is not carried forward.
                captured = {}

                def fake_fetch_pass(pending, scores, *args, **kwargs):
                    captured["initial_scores"] = dict(scores)
                    return [], False

                with patch("routers.scores._fetch_pass", side_effect=fake_fetch_pass), \
                     patch("routers.scores._write_metrics"), \
                     patch("routers.scores._fetch_lock"):
                    scores_mod._is_fetching = True
                    scores_mod._background_score_fetch("tok", ["2330"], force=True)
            finally:
                scores_mod.SCORES_DIR = original_dir

            assert captured.get("initial_scores") == {}, (
                "force=True should start with empty scores, got stale data"
            )

    # ── Bug 3: metrics succeeded must reflect only newly scored stocks ─────
    def test_metrics_succeeded_counts_only_new_scores(self):
        """succeeded metric must equal newly scored stocks, not total in dict (Bug 3)."""
        import tempfile, json
        from pathlib import Path
        from routers import scores as scores_mod

        written_metrics = {}

        def capture_metrics(today, *, attempted, succeeded, failed, **kw):
            written_metrics.update({"attempted": attempted, "succeeded": succeeded, "failed": failed})

        def fake_fetch_pass(pending, scores, *args, **kwargs):
            # Simulate scoring 2 out of 3 stocks
            scores["2330"] = {"score": 10, "max_score": 24}
            scores["2317"] = {"score": 8, "max_score": 24}
            return ["2454"], False   # 2454 failed

        with tempfile.TemporaryDirectory() as tmpdir:
            original_dir = scores_mod.SCORES_DIR
            scores_mod.SCORES_DIR = Path(tmpdir)
            try:
                with patch("routers.scores._fetch_pass", side_effect=fake_fetch_pass), \
                     patch("routers.scores._write_metrics", side_effect=capture_metrics), \
                     patch("routers.scores._fetch_lock"), \
                     patch("routers.scores.time.sleep"):
                    scores_mod._is_fetching = True
                    scores_mod._background_score_fetch(
                        "tok", ["2330", "2317", "2454"], force=True
                    )
            finally:
                scores_mod.SCORES_DIR = original_dir

        assert written_metrics["attempted"] == 3
        assert written_metrics["succeeded"] == 2   # only newly scored
        assert written_metrics["failed"] == 1
