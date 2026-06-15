"""
test_buy_score_source.py — unit tests for crawler/sources/buy_score.py

Scores are now computed natively via sources.buy_score_engine.compute_buy_score
(no external HTTP). Tests mock compute_buy_score / fetch_buy_score accordingly.
"""

import json
import sys
import os

import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources.buy_score import (
    fetch_buy_score,
    batch_fetch_scores,
    write_scores,
    load_latest_scores,
    QuotaExhaustedMidBatch,
)
from sources.finmind_client import FinMindError


def _full_result(score, max_score=24, eligible=20):
    """Minimal engine payload with the fields fetch_buy_score reads."""
    return {
        "stock_id": "X",
        "score": score,
        "max_score": max_score,
        "eligible_count": eligible,
        "criteria": [],
    }


class TestFetchBuyScore:
    def test_returns_score_when_data_available(self):
        with patch("sources.buy_score.compute_buy_score", return_value=_full_result(18)):
            result = fetch_buy_score("2330")
        assert result == {"score": 18, "max_score": 24}

    def test_returns_none_when_no_analyzable_data(self):
        # eligible_count == 0 → every fetch failed; must NOT persist a misleading 0/24.
        with patch("sources.buy_score.compute_buy_score", return_value=_full_result(0, eligible=0)):
            result = fetch_buy_score("9999")
        assert result is None

    def test_returns_none_on_generic_exception(self):
        with patch("sources.buy_score.compute_buy_score", side_effect=ValueError("boom")):
            result = fetch_buy_score("2330")
        assert result is None

    def test_reraises_finmind_quota_error(self):
        with patch("sources.buy_score.compute_buy_score", side_effect=FinMindError("quota")):
            with pytest.raises(FinMindError):
                fetch_buy_score("2330")

    def test_passes_token_through(self):
        with patch("sources.buy_score.compute_buy_score", return_value=_full_result(10)) as mock_compute:
            fetch_buy_score("2330", token="tok-123")
        assert mock_compute.call_args.kwargs.get("token") == "tok-123"

    def test_zero_score_with_real_data_is_kept(self):
        # score 0 but eligible_count > 0 means real data said "fails everything" — keep it.
        with patch("sources.buy_score.compute_buy_score", return_value=_full_result(0, eligible=20)):
            result = fetch_buy_score("2454")
        assert result == {"score": 0, "max_score": 24}


class TestBatchFetchScores:
    def test_collects_successful_scores(self):
        side_effects = {
            "2330": {"score": 18, "max_score": 24},
            "2317": None,
            "2454": {"score": 20, "max_score": 24},
        }

        def _mock(sid, token=None):
            return side_effects[sid]

        with patch("sources.buy_score.fetch_buy_score", side_effect=_mock), \
             patch("sources.buy_score.time.sleep"):
            result = batch_fetch_scores(["2330", "2317", "2454"])

        assert "2330" in result
        assert "2454" in result
        assert "2317" not in result  # None → skipped (shows N/A)

    def test_returns_empty_when_all_fail(self):
        with patch("sources.buy_score.fetch_buy_score", return_value=None), \
             patch("sources.buy_score.time.sleep"):
            result = batch_fetch_scores(["0000", "1111"])
        assert result == {}

    def test_sleeps_between_requests(self):
        with patch("sources.buy_score.fetch_buy_score", return_value={"score": 1, "max_score": 24}), \
             patch("sources.buy_score.time.sleep") as mock_sleep:
            batch_fetch_scores(["2330", "2317", "2454"])
        # 3 stocks → N-1 = 2 inter-request sleeps
        assert mock_sleep.call_count == 2

    def test_no_sleep_for_single_stock(self):
        with patch("sources.buy_score.fetch_buy_score", return_value={"score": 1, "max_score": 24}), \
             patch("sources.buy_score.time.sleep") as mock_sleep:
            batch_fetch_scores(["2330"])
        assert mock_sleep.call_count == 0

    def test_returns_empty_for_empty_input(self):
        result = batch_fetch_scores([])
        assert result == {}

    def test_quota_exhaustion_raises_with_remaining_ids(self):
        """On FinMindError, batch raises QuotaExhaustedMidBatch with all unscored stocks."""
        calls = {"n": 0}

        def _mock(sid, token=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise FinMindError("quota exceeded")
            return {"score": 5, "max_score": 24}

        with patch("sources.buy_score.fetch_buy_score", side_effect=_mock), \
             patch("sources.buy_score.time.sleep"):
            with pytest.raises(QuotaExhaustedMidBatch) as exc_info:
                batch_fetch_scores(["A", "B"])

        exc = exc_info.value
        # A hit quota (first call), B not tried yet — both must be in remaining_ids.
        assert "A" in exc.remaining_ids
        assert "B" in exc.remaining_ids
        assert exc.scored == {}

    def test_quota_hit_preserves_prior_scores(self):
        """Scores accumulated before the quota hit are accessible in exc.scored."""
        def _mock(sid, token=None):
            if sid == "C":
                raise FinMindError("quota exceeded")
            return {"score": 5, "max_score": 24}

        with patch("sources.buy_score.fetch_buy_score", side_effect=_mock), \
             patch("sources.buy_score.time.sleep"):
            with pytest.raises(QuotaExhaustedMidBatch) as exc_info:
                batch_fetch_scores(["A", "B", "C", "D"])

        exc = exc_info.value
        assert exc.scored == {
            "A": {"score": 5, "max_score": 24},
            "B": {"score": 5, "max_score": 24},
        }
        assert "C" in exc.remaining_ids
        assert "D" in exc.remaining_ids
        assert "A" not in exc.remaining_ids
        assert "B" not in exc.remaining_ids


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
