"""
test_ranker.py — /tdd: RED → GREEN tests for ranker.py

Tests only external behavior — not implementation details.
"""

import pytest
from services.ranker import compute_color_tier, compute_ranks


class TestComputeColorTier:
    """5-tier color mapping boundary tests."""

    def test_above_5pct_is_deep_red(self):
        assert compute_color_tier(6.0) == "deep_red"

    def test_exactly_5pct_is_deep_red(self):
        assert compute_color_tier(5.0) == "deep_red"

    def test_between_1_and_5_is_light_red(self):
        assert compute_color_tier(3.0) == "light_red"

    def test_exactly_1pct_is_light_red(self):
        assert compute_color_tier(1.0) == "light_red"

    def test_zero_is_neutral(self):
        assert compute_color_tier(0.0) == "neutral"

    def test_just_below_1pct_is_neutral(self):
        assert compute_color_tier(0.99) == "neutral"

    def test_just_above_neg_1pct_is_neutral(self):
        assert compute_color_tier(-0.99) == "neutral"

    def test_exactly_neg_1pct_is_light_green(self):
        assert compute_color_tier(-1.0) == "light_green"

    def test_between_neg_1_and_neg_5_is_light_green(self):
        assert compute_color_tier(-3.0) == "light_green"

    def test_exactly_neg_5pct_is_light_green(self):
        assert compute_color_tier(-5.0) == "light_green"

    def test_below_neg_5pct_is_deep_green(self):
        assert compute_color_tier(-6.0) == "deep_green"

    def test_limit_down_10pct_is_deep_green(self):
        assert compute_color_tier(-10.0) == "deep_green"

    def test_limit_up_10pct_is_deep_red(self):
        assert compute_color_tier(10.0) == "deep_red"


class TestComputeRanks:
    """Volume and turnover ranking tests."""

    @pytest.fixture
    def sample_records(self):
        return [
            {"stock_id": "2330", "name": "台積電", "volume": 50000, "turnover_rate": 0.5, "price_change_pct": 2.0},
            {"stock_id": "2317", "name": "鴻海",   "volume": 80000, "turnover_rate": 1.2, "price_change_pct": -6.0},
            {"stock_id": "2454", "name": "聯發科", "volume": 30000, "turnover_rate": 0.8, "price_change_pct": 0.5},
        ]

    def test_volume_rank_highest_volume_is_rank_1(self, sample_records):
        result = compute_ranks(sample_records)
        鴻海 = next(r for r in result if r["stock_id"] == "2317")
        assert 鴻海["volume_rank"] == 1

    def test_volume_rank_lowest_volume_is_last(self, sample_records):
        result = compute_ranks(sample_records)
        聯發科 = next(r for r in result if r["stock_id"] == "2454")
        assert 聯發科["volume_rank"] == 3

    def test_turnover_rank_highest_turnover_is_rank_1(self, sample_records):
        result = compute_ranks(sample_records)
        鴻海 = next(r for r in result if r["stock_id"] == "2317")
        assert 鴻海["turnover_rank"] == 1

    def test_turnover_rank_differs_from_volume_rank(self, sample_records):
        result = compute_ranks(sample_records)
        聯發科 = next(r for r in result if r["stock_id"] == "2454")
        # 成交量 rank 3, 但週轉率 rank 2
        assert 聯發科["volume_rank"] == 3
        assert 聯發科["turnover_rank"] == 2

    def test_color_tier_attached_to_all_records(self, sample_records):
        result = compute_ranks(sample_records)
        assert all("color_tier" in r for r in result)

    def test_color_tier_correct_for_deep_green(self, sample_records):
        result = compute_ranks(sample_records)
        鴻海 = next(r for r in result if r["stock_id"] == "2317")
        assert 鴻海["color_tier"] == "deep_green"

    def test_color_tier_correct_for_light_red(self, sample_records):
        result = compute_ranks(sample_records)
        台積電 = next(r for r in result if r["stock_id"] == "2330")
        assert 台積電["color_tier"] == "light_red"

    def test_empty_records_returns_empty(self):
        assert compute_ranks([]) == []

    def test_single_record_gets_rank_1_for_both(self):
        records = [{"stock_id": "2330", "name": "台積電", "volume": 100, "turnover_rate": 1.0, "price_change_pct": 0.0}]
        result = compute_ranks(records)
        assert result[0]["volume_rank"] == 1
        assert result[0]["turnover_rank"] == 1
