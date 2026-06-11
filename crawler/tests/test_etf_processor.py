"""
test_etf_processor.py — Unit tests for ETF classification, ranking, and merge logic

Tests:
  - classify_etf_type: 8-type TWSE taxonomy (反向/槓桿/貨幣/債券/期貨/多資產/國外股/國內股)
  - compute_etf_ranks: turnover + asset_scale ranks assigned correctly
  - merge_etf_data: turnover_rate formula, premium/discount calc, None-safety
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from etf_processor import classify_etf_type, compute_etf_ranks, merge_etf_data, compute_color_tier


class TestClassifyEtfType:
    def test_stock_type_default(self):
        assert classify_etf_type("0050", "元大台灣50") == "國內股"

    def test_stock_type_numeric_id(self):
        assert classify_etf_type("006208", "富邦台灣50") == "國內股"

    def test_bond_type_by_id_suffix_B(self):
        assert classify_etf_type("00679B", "元大美債20年") == "債券"

    def test_bond_type_by_name(self):
        assert classify_etf_type("00937B", "台新ESG投資級債") == "債券"

    def test_commodity_type_by_id_suffix_U(self):
        assert classify_etf_type("00635U", "元大S&P黃金") == "期貨"

    def test_commodity_type_by_name_keyword(self):
        assert classify_etf_type("XYZZ", "某某原油ETF") == "期貨"

    def test_leveraged_by_id_suffix_L(self):
        assert classify_etf_type("00631L", "元大台灣50正2") == "槓桿"

    def test_inverse_by_id_suffix_R(self):
        assert classify_etf_type("00632R", "元大台灣50反1") == "反向"

    def test_leveraged_by_name_keyword(self):
        assert classify_etf_type("XXXX", "某某槓桿型基金") == "槓桿"

    def test_inverse_by_name_keyword(self):
        assert classify_etf_type("XXXX", "反向1倍ETF") == "反向"

    def test_money_market_by_name(self):
        # 貨幣 name check runs before the B-suffix bond rule → 貨幣 wins
        assert classify_etf_type("00864B", "中信貨幣市場型ETF") == "貨幣"

    def test_leveraged_takes_priority_over_bond(self):
        # ID ends with L but name contains 債 — 槓桿 should win
        assert classify_etf_type("00XYL", "某某債券正2ETF") == "槓桿"


class TestComputeColorTier:
    @pytest.mark.parametrize("pct,expected", [
        (6.0,  "deep_red"),
        (5.0,  "deep_red"),
        (2.0,  "light_red"),
        (1.0,  "light_red"),
        (0.0,  "neutral"),
        (-0.5, "neutral"),
        (-1.0, "light_green"),
        (-4.9, "light_green"),
        (-5.0, "light_green"),
        (-6.0, "deep_green"),
    ])
    def test_tier_boundaries(self, pct, expected):
        assert compute_color_tier(pct) == expected


class TestComputeEtfRanks:
    def _make_records(self):
        return [
            {"etf_id": "A", "turnover_rate": 0.5,  "asset_scale": 3000.0, "color_tier": "neutral"},
            {"etf_id": "B", "turnover_rate": 1.2,  "asset_scale": 1000.0, "color_tier": "neutral"},
            {"etf_id": "C", "turnover_rate": None,  "asset_scale": None,   "color_tier": "neutral"},
            {"etf_id": "D", "turnover_rate": 0.8,  "asset_scale": 5000.0, "color_tier": "neutral"},
        ]

    def test_turnover_rank_order(self):
        records = self._make_records()
        result = compute_etf_ranks(records)
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["B"]["turnover_rank"] == 1   # highest turnover
        assert by_id["D"]["turnover_rank"] == 2
        assert by_id["A"]["turnover_rank"] == 3
        assert by_id["C"]["turnover_rank"] == 4   # None is last

    def test_asset_scale_rank_order(self):
        records = self._make_records()
        result = compute_etf_ranks(records)
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["D"]["asset_scale_rank"] == 1   # largest scale
        assert by_id["A"]["asset_scale_rank"] == 2
        assert by_id["B"]["asset_scale_rank"] == 3
        assert by_id["C"]["asset_scale_rank"] == 4   # None is last

    def test_ranks_are_1_based(self):
        records = [
            {"etf_id": "X", "turnover_rate": 1.0, "asset_scale": 100.0, "color_tier": "neutral"},
        ]
        result = compute_etf_ranks(records)
        assert result[0]["turnover_rank"] == 1
        assert result[0]["asset_scale_rank"] == 1


class TestMergeEtfData:
    def _daily(self):
        return [
            {"etf_id": "0050", "name": "元大台灣50",
             "volume": 6720000, "close_price": 185.5, "price_change_pct": 1.23},
            {"etf_id": "00679B", "name": "元大美債20年",
             "volume": 450000, "close_price": 32.12, "price_change_pct": -0.56},
        ]

    def test_turnover_rate_formula(self):
        outstanding = {"0050": 1_680_000_000, "00679B": 450_000_000}
        result = merge_etf_data(self._daily(), outstanding, {}, {})
        by_id = {r["etf_id"]: r for r in result}
        # 6720000 / 1680000000 * 100 = 0.4000
        assert abs(by_id["0050"]["turnover_rate"] - 0.4) < 0.001

    def test_turnover_none_when_no_outstanding(self):
        result = merge_etf_data(self._daily(), {}, {}, {})
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["0050"]["turnover_rate"] is None

    def test_premium_positive_when_close_above_nav(self):
        nav = {"0050": 185.0}
        result = merge_etf_data(self._daily(), {}, nav, {})
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["0050"]["premium_discount"] > 0

    def test_discount_negative_when_close_below_nav(self):
        nav = {"00679B": 32.30}
        result = merge_etf_data(self._daily(), {}, nav, {})
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["00679B"]["premium_discount"] < 0

    def test_premium_none_when_no_nav(self):
        result = merge_etf_data(self._daily(), {}, {}, {})
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["0050"]["premium_discount"] is None

    def test_asset_scale_injected_from_yahoo(self):
        asset = {"0050": 3241.5}
        result = merge_etf_data(self._daily(), {}, {}, asset)
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["0050"]["asset_scale"] == 3241.5
        assert by_id["00679B"]["asset_scale"] is None

    def test_etf_type_classified(self):
        result = merge_etf_data(self._daily(), {}, {}, {})
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["0050"]["etf_type"]   == "國內股"
        assert by_id["00679B"]["etf_type"] == "債券"

    def test_color_tier_assigned(self):
        result = merge_etf_data(self._daily(), {}, {}, {})
        by_id = {r["etf_id"]: r for r in result}
        assert by_id["0050"]["color_tier"]   == "light_red"   # pct=1.23 → light_red
        assert by_id["00679B"]["color_tier"] == "neutral"     # pct=-0.56 → neutral

    def test_ranks_assigned_after_merge(self):
        outstanding = {"0050": 1_680_000_000, "00679B": 450_000_000}
        result = merge_etf_data(self._daily(), outstanding, {}, {})
        by_id = {r["etf_id"]: r for r in result}
        # 0050 turnover = 0.4, 00679B turnover = 0.1 → 0050 rank 1
        assert by_id["0050"]["turnover_rank"]   == 1
        assert by_id["00679B"]["turnover_rank"] == 2

    def test_cross_validate_turnover_rate_precision(self):
        """Cross-validation: manual calculation must match processor output."""
        outstanding = {"0050": 1_680_000_000}
        result = merge_etf_data(self._daily(), outstanding, {}, {})
        by_id = {r["etf_id"]: r for r in result}
        expected = round((6_720_000 / 1_680_000_000) * 100, 4)
        assert by_id["0050"]["turnover_rate"] == expected
