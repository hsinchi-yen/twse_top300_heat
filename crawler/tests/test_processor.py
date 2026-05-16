"""
test_processor.py — /tdd tests for crawler processor.py
"""

import pytest
from processor import merge_and_rank


@pytest.fixture
def twse():
    return [
        {"stock_id": "2330", "name": "台積電", "volume": 50000, "price_change_pct": 2.0},
        {"stock_id": "2317", "name": "鴻海",   "volume": 80000, "price_change_pct": -6.0},
    ]


@pytest.fixture
def tpex():
    return [
        {"stock_id": "6488", "name": "環球晶", "volume": 20000, "price_change_pct": 3.5},
        {"stock_id": "3711", "name": "日月光", "volume": 30000, "price_change_pct": -0.5},
    ]


@pytest.fixture
def issue_shares():
    return {
        "2330": 25900000000,
        "2317": 13900000000,
        "6488": 283000000,
        "3711": 7600000000,
    }


class TestMergeAndRank:

    def test_merges_twse_and_tpex(self, twse, tpex, issue_shares):
        result = merge_and_rank(twse, tpex, issue_shares)
        ids = {r["stock_id"] for r in result}
        assert {"2330", "2317", "6488", "3711"}.issubset(ids)

    def test_twse_overrides_tpex_on_same_stock_id(self, issue_shares):
        twse = [{"stock_id": "2330", "name": "台積電(TWSE)", "volume": 9999, "price_change_pct": 1.0}]
        tpex = [{"stock_id": "2330", "name": "台積電(TPEX)", "volume": 1111, "price_change_pct": 0.5}]
        result = merge_and_rank(twse, tpex, issue_shares)
        stock = next(r for r in result if r["stock_id"] == "2330")
        assert stock["name"] == "台積電(TWSE)"
        assert stock["volume"] == 9999

    def test_volume_rank_highest_volume_is_rank_1(self, twse, tpex, issue_shares):
        result = merge_and_rank(twse, tpex, issue_shares)
        鴻海 = next(r for r in result if r["stock_id"] == "2317")
        assert 鴻海["volume_rank"] == 1

    def test_turnover_rate_formula(self, issue_shares):
        """週轉率 = volume / issue_shares × 100"""
        twse = [{"stock_id": "2330", "name": "台積電", "volume": 2590000, "price_change_pct": 0.0}]
        result = merge_and_rank(twse, [], issue_shares)
        stock = result[0]
        expected = round(2590000 / 25900000000 * 100, 4)
        assert stock["turnover_rate"] == pytest.approx(expected, rel=1e-4)

    def test_turnover_rate_zero_when_no_issue_shares(self, twse):
        result = merge_and_rank(twse, [], {})
        for r in result:
            assert r["turnover_rate"] == 0.0

    def test_color_tier_deep_red_above_5pct(self, issue_shares):
        twse = [{"stock_id": "2330", "name": "台積電", "volume": 1000, "price_change_pct": 7.0}]
        result = merge_and_rank(twse, [], issue_shares)
        assert result[0]["color_tier"] == "deep_red"

    def test_color_tier_deep_green_below_neg5pct(self, issue_shares):
        twse = [{"stock_id": "2317", "name": "鴻海", "volume": 1000, "price_change_pct": -6.0}]
        result = merge_and_rank(twse, [], issue_shares)
        assert result[0]["color_tier"] == "deep_green"

    def test_all_records_have_required_fields(self, twse, tpex, issue_shares):
        result = merge_and_rank(twse, tpex, issue_shares)
        required = {"stock_id", "name", "volume", "turnover_rate",
                    "price_change_pct", "color_tier", "volume_rank", "turnover_rank"}
        for r in result:
            assert required.issubset(r.keys()), f"Missing fields in {r}"

    def test_empty_inputs_returns_empty(self):
        assert merge_and_rank([], [], {}) == []

    def test_turnover_rank_small_stock_can_outrank_large(self, issue_shares):
        """小股票發行股數少，週轉率可高於大股票"""
        twse = [
            {"stock_id": "2330", "name": "台積電", "volume": 1000000, "price_change_pct": 0.0},
            {"stock_id": "6488", "name": "環球晶", "volume": 100000, "price_change_pct": 0.0},
        ]
        result = merge_and_rank(twse, [], issue_shares)
        環球晶 = next(r for r in result if r["stock_id"] == "6488")
        台積電 = next(r for r in result if r["stock_id"] == "2330")
        # 環球晶發行股數少很多，週轉率應高於台積電
        assert 環球晶["turnover_rate"] > 台積電["turnover_rate"]
        assert 環球晶["turnover_rank"] < 台積電["turnover_rank"]
