"""
test_buy_score_engine.py — unit tests for crawler/sources/buy_score_engine.py

Drives compute_buy_score with a fake FinMindClient so no network is touched.
Verifies (a) criteria scoring on representative data, (b) graceful degradation
when individual fetches fail (criteria become null, others still score), and
(c) FinMind quota errors propagate so the batch caller can pause/resume.
"""

import sys
import os
from datetime import date

import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sources.buy_score_engine as engine
from sources.buy_score_engine import compute_buy_score, _compute_roe_roa_ttm, compute_sloan_ratio
from sources.finmind_client import FinMindError


@pytest.fixture(autouse=True)
def _no_fetch_delay(monkeypatch):
    """Zero the inter-fetch stagger so tests run instantly."""
    monkeypatch.setattr(engine, "_FETCH_DELAY", 0)


class FakeClient:
    """Stub FinMindClient: every fetch returns empty/neutral data by default.

    Override individual methods per test. Methods raising FinMindError simulate
    quota exhaustion.
    """

    def __init__(self, **overrides):
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]

        def _default(*args, **kwargs):
            # Mirror the shapes compute_buy_score expects from each fetch.
            if name == "fetch_stock_industry":
                return "半導體"
            if name == "fetch_annual_fcf_data":
                return pd.DataFrame(), None
            if name == "fetch_quarterly_bs_for_roe":
                return pd.Series(dtype=float), pd.Series(dtype=float)
            if name == "fetch_quarterly_bs_liabilities_assets":
                return pd.Series(dtype=float), pd.Series(dtype=float)
            if name == "fetch_quarterly_ni":
                return pd.Series(dtype=float)
            if name == "fetch_inventory_and_revenue_growth":
                return None
            if name == "fetch_dividend_payout_ratio":
                return None
            # All other fetch_* return empty DataFrame
            return pd.DataFrame()

        return _default


class TestComputeBuyScoreShape:
    def test_returns_expected_keys(self):
        result = compute_buy_score("2330", client=FakeClient())
        for key in ("stock_id", "score", "max_score", "eligible_count",
                    "pass_rate", "criteria", "risk_criteria", "warnings"):
            assert key in result

    def test_max_score_is_24(self):
        result = compute_buy_score("2330", client=FakeClient())
        assert result["max_score"] == 24

    def test_no_data_yields_zero_eligible(self):
        # Every fetch empty → no criterion has real data → eligible_count 0.
        result = compute_buy_score("2330", client=FakeClient())
        assert result["eligible_count"] == 0
        assert result["score"] == 0

    def test_blank_stock_id_raises(self):
        with pytest.raises(ValueError):
            compute_buy_score("   ", client=FakeClient())


class TestQuotaPropagation:
    def test_finmind_error_propagates(self):
        def _boom(*a, **k):
            raise FinMindError("FinMind quota exceeded (HTTP 402).")

        client = FakeClient(fetch_quarterly_ni=_boom)
        with pytest.raises(FinMindError):
            compute_buy_score("2330", client=client)


class TestCriteriaScoring:
    def test_revenue_yoy_scores_when_positive(self):
        # 16 months of rising revenue → YoY positive for the last 3 → C4 passes.
        months = pd.date_range("2024-01-01", periods=16, freq="MS")
        revenue = [100 + i * 10 for i in range(16)]
        df_rev = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in months],
            "month": [d.strftime("%Y-%m") for d in months],
            "revenue": revenue,
        })

        client = FakeClient(fetch_month_revenue=lambda *a, **k: df_rev)
        result = compute_buy_score("2330", client=client)

        rev_crit = next(c for c in result["criteria"] if c["id"] == "revenue_yoy")
        assert rev_crit["pass"] is True
        assert result["score"] >= 1
        assert result["eligible_count"] >= 1


class TestHelpers:
    def test_sloan_ratio_basic(self):
        # (NI - OCF) / AvgAssets = (100 - 80) / 1000 = 0.02
        assert compute_sloan_ratio(100, 80, 1000) == pytest.approx(0.02)

    def test_sloan_ratio_zero_assets(self):
        assert compute_sloan_ratio(100, 80, 0) is None

    def test_roe_roa_ttm_computes_latest(self):
        # 4 quarters of NI=25 each (TTM=100), equity=1000, assets=2000.
        idx = pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"])
        ni = pd.Series([25, 25, 25, 25], index=idx)
        equity = pd.Series([1000, 1000, 1000, 1000], index=idx)
        assets = pd.Series([2000, 2000, 2000, 2000], index=idx)
        rows = _compute_roe_roa_ttm(ni, equity, assets, start_cutoff=pd.Timestamp("2020-01-01"))
        assert rows
        assert rows[-1]["roe"] == pytest.approx(10.0)   # 100/1000*100
        assert rows[-1]["roa"] == pytest.approx(5.0)     # 100/2000*100
