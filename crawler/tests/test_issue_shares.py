"""
Issued-share counts behind turnover_rate.

TWSE t187ap03_L lists exchange companies only, so until the TPEx feed was added
every OTC stock (166 of the 600-stock pool on 2026-10-30) stored a turnover of
0.0. The TPEx row shape below is taken from the live feed on 2026-11-02.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources import finmind, tpex


TWSE_ROW = {"公司代號": "2330", "已發行普通股數或TDR原股發行股數": "25930380458"}
TPEX_ROW = {
    "Date": "1151101", "SecuritiesCompanyCode": "7704", "CompanyAbbreviation": "明遠精密",
    "Paidin.Capital.NTDollars": "337698040", "IssueShares": "33769804",
}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    finmind.clear_cache()
    monkeypatch.setattr(finmind.time, "sleep", lambda _: None)
    yield
    finmind.clear_cache()


def stub_sources(monkeypatch, twse=(TWSE_ROW,), otc=(TPEX_ROW,)):
    """Serves each company feed; a None feed fails the way the real clients do."""
    class Response:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            if self.body is None:
                raise RuntimeError("503")

        def json(self):
            return list(self.body)

    calls = []

    def fake_requests_get(url, headers=None, timeout=None):
        calls.append(url)
        return Response(twse)

    def fake_tpex_get(url):
        calls.append(url)
        return list(otc) if otc is not None else []

    monkeypatch.setattr(finmind.requests, "get", fake_requests_get)
    monkeypatch.setattr(tpex, "_http_get", fake_tpex_get)
    return calls


class TestFetchTpexIssueShares:
    def test_parses_issue_shares_by_company_code(self, monkeypatch):
        stub_sources(monkeypatch)
        assert tpex.fetch_tpex_issue_shares() == {"7704": 33769804}

    def test_tolerates_padding_and_thousands_separators(self, monkeypatch):
        stub_sources(monkeypatch, otc=[{"SecuritiesCompanyCode": " 6488 ", "IssueShares": " 1,234,567 "}])
        assert tpex.fetch_tpex_issue_shares() == {"6488": 1234567}

    @pytest.mark.parametrize("row", [
        {"SecuritiesCompanyCode": "1111", "IssueShares": "0"},
        {"SecuritiesCompanyCode": "1112", "IssueShares": ""},
        {"SecuritiesCompanyCode": "1113", "IssueShares": "N/A"},
        {"SecuritiesCompanyCode": "1114"},
        {"SecuritiesCompanyCode": "", "IssueShares": "100"},
    ])
    def test_skips_rows_without_a_usable_share_count(self, monkeypatch, row):
        stub_sources(monkeypatch, otc=[row])
        assert tpex.fetch_tpex_issue_shares() == {}

    def test_failed_feed_is_empty(self, monkeypatch):
        stub_sources(monkeypatch, otc=None)
        assert tpex.fetch_tpex_issue_shares() == {}


class TestFetchIssueShares:
    def test_covers_both_markets(self, monkeypatch):
        stub_sources(monkeypatch)
        assert finmind.fetch_issue_shares() == {"2330": 25930380458, "7704": 33769804}

    def test_twse_wins_when_a_stock_appears_in_both(self, monkeypatch):
        otc = [{"SecuritiesCompanyCode": "2330", "IssueShares": "1"}]
        stub_sources(monkeypatch, otc=otc)
        assert finmind.fetch_issue_shares()["2330"] == 25930380458

    def test_complete_result_is_cached_for_the_day(self, monkeypatch):
        calls = stub_sources(monkeypatch)
        finmind.fetch_issue_shares()
        fetched = len(calls)
        finmind.fetch_issue_shares()
        assert len(calls) == fetched

    def test_one_failed_market_still_serves_the_other_but_is_not_cached(self, monkeypatch):
        """A TPEx outage must not blank OTC turnover until the daily cache reset."""
        stub_sources(monkeypatch, otc=None)
        assert finmind.fetch_issue_shares() == {"2330": 25930380458}

        stub_sources(monkeypatch)
        assert finmind.fetch_issue_shares() == {"2330": 25930380458, "7704": 33769804}

    def test_twse_outage_keeps_otc(self, monkeypatch):
        stub_sources(monkeypatch, twse=None)
        assert finmind.fetch_issue_shares() == {"7704": 33769804}
