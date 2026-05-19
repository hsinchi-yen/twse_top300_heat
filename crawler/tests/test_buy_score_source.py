"""
test_buy_score_source.py — TDD unit tests for crawler/sources/buy_score.py
"""

import json
import sys
import os

import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources.buy_score import (
    fetch_buy_score,
    batch_fetch_scores,
    write_scores,
    load_latest_scores,
)


class TestFetchBuyScore:
    def test_returns_score_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "score": 18,
            "max_score": 24,
            "signal": "buy",
            "recommendation": "scale_in",
        }
        with patch("sources.buy_score.requests.get", return_value=mock_resp):
            result = fetch_buy_score("2330")
        assert result == {"score": 18, "max_score": 24}

    def test_returns_none_on_404(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("sources.buy_score.requests.get", return_value=mock_resp):
            result = fetch_buy_score("9999")
        assert result is None

    def test_returns_none_on_connection_error(self):
        with patch("sources.buy_score.requests.get", side_effect=ConnectionError("refused")):
            result = fetch_buy_score("2330")
        assert result is None

    def test_returns_none_on_timeout(self):
        import requests as req
        with patch("sources.buy_score.requests.get", side_effect=req.exceptions.Timeout()):
            result = fetch_buy_score("2330")
        assert result is None

    def test_calls_correct_url(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"score": 10, "max_score": 24}
        with patch("sources.buy_score.STOCK_ANALYSIS_URL", "http://test-host:9000"):
            with patch("sources.buy_score.requests.get", return_value=mock_resp) as mock_get:
                fetch_buy_score("2330")
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert call_url == "http://test-host:9000/api/stocks/2330/buy_score"


class TestBatchFetchScores:
    def test_collects_successful_scores(self):
        side_effects = {"2330": {"score": 18, "max_score": 24}, "2317": None, "2454": {"score": 20, "max_score": 24}}

        def _mock(sid):
            return side_effects[sid]

        with patch("sources.buy_score.fetch_buy_score", side_effect=_mock):
            with patch("sources.buy_score.time.sleep"):
                result = batch_fetch_scores(["2330", "2317", "2454"])

        assert "2330" in result
        assert "2454" in result
        assert "2317" not in result  # None → skipped

    def test_returns_empty_when_all_fail(self):
        with patch("sources.buy_score.fetch_buy_score", return_value=None):
            with patch("sources.buy_score.time.sleep"):
                result = batch_fetch_scores(["0000", "1111"])
        assert result == {}

    def test_sleeps_between_requests(self):
        with patch("sources.buy_score.fetch_buy_score", return_value={"score": 1, "max_score": 24}):
            with patch("sources.buy_score.time.sleep") as mock_sleep:
                batch_fetch_scores(["2330", "2317", "2454"])
        # N stocks → N-1 sleeps
        assert mock_sleep.call_count == 2

    def test_no_sleep_for_single_stock(self):
        with patch("sources.buy_score.fetch_buy_score", return_value={"score": 1, "max_score": 24}):
            with patch("sources.buy_score.time.sleep") as mock_sleep:
                batch_fetch_scores(["2330"])
        assert mock_sleep.call_count == 0

    def test_returns_empty_for_empty_input(self):
        result = batch_fetch_scores([])
        assert result == {}


class TestWriteScores:
    def test_creates_json_file(self, tmp_path):
        scores_dir = tmp_path / "buy_scores"
        with patch("sources.buy_score.SCORES_DIR", scores_dir):
            write_scores({"2330": {"score": 18, "max_score": 24}}, "2026-05-19")
        assert (scores_dir / "2026-05-19.json").exists()

    def test_written_structure_is_correct(self, tmp_path):
        scores_dir = tmp_path / "buy_scores"
        with patch("sources.buy_score.SCORES_DIR", scores_dir):
            write_scores({"2330": {"score": 18, "max_score": 24}}, "2026-05-19")
        data = json.loads((scores_dir / "2026-05-19.json").read_text(encoding="utf-8"))
        assert data["date"] == "2026-05-19"
        assert "generated_at" in data
        assert data["scores"]["2330"]["score"] == 18
        assert data["scores"]["2330"]["max_score"] == 24

    def test_prunes_files_beyond_max_keep(self, tmp_path):
        scores_dir = tmp_path / "buy_scores"
        scores_dir.mkdir()
        # pre-create 8 old files
        for i in range(1, 9):
            (scores_dir / f"2026-04-{i:02d}.json").write_text("{}", encoding="utf-8")
        with patch("sources.buy_score.SCORES_DIR", scores_dir):
            with patch("sources.buy_score.MAX_KEEP_DAYS", 7):
                write_scores({}, "2026-05-19")
        remaining = list(scores_dir.glob("*.json"))
        assert len(remaining) == 7

    def test_returns_path_of_written_file(self, tmp_path):
        scores_dir = tmp_path / "buy_scores"
        with patch("sources.buy_score.SCORES_DIR", scores_dir):
            path = write_scores({}, "2026-05-19")
        assert path.name == "2026-05-19.json"


class TestLoadLatestScores:
    def test_returns_empty_when_dir_missing(self, tmp_path):
        with patch("sources.buy_score.SCORES_DIR", tmp_path / "nonexistent"):
            result = load_latest_scores()
        assert result == {}

    def test_returns_most_recent_file(self, tmp_path):
        scores_dir = tmp_path / "buy_scores"
        scores_dir.mkdir()
        (scores_dir / "2026-05-18.json").write_text(
            json.dumps({"date": "2026-05-18", "scores": {"2330": {"score": 15, "max_score": 24}}}),
            encoding="utf-8",
        )
        (scores_dir / "2026-05-19.json").write_text(
            json.dumps({"date": "2026-05-19", "scores": {"2330": {"score": 18, "max_score": 24}}}),
            encoding="utf-8",
        )
        with patch("sources.buy_score.SCORES_DIR", scores_dir):
            result = load_latest_scores()
        assert result["date"] == "2026-05-19"

    def test_skips_corrupt_files_and_returns_next(self, tmp_path):
        scores_dir = tmp_path / "buy_scores"
        scores_dir.mkdir()
        (scores_dir / "2026-05-19.json").write_text("{{invalid}}", encoding="utf-8")
        (scores_dir / "2026-05-18.json").write_text(
            json.dumps({"date": "2026-05-18", "scores": {}}), encoding="utf-8"
        )
        with patch("sources.buy_score.SCORES_DIR", scores_dir):
            result = load_latest_scores()
        assert result["date"] == "2026-05-18"

    def test_returns_empty_when_all_corrupt(self, tmp_path):
        scores_dir = tmp_path / "buy_scores"
        scores_dir.mkdir()
        (scores_dir / "2026-05-19.json").write_text("{{bad}}", encoding="utf-8")
        with patch("sources.buy_score.SCORES_DIR", scores_dir):
            result = load_latest_scores()
        assert result == {}
