"""
test_institutional.py — parsers for whole-market 三大法人 daily reports.

Fixtures mirror the live payload shapes probed on 2026-10-22:
  TWSE rwd/zh/fund/T86 (named fields, shares) and
  TPEx www/zh-tw/insti/dailyTrade (generic 買進/賣出/買賣超 fields in 7 groups).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources.institutional import parse_twse_t86, parse_tpex_insti

T86_FIELDS = [
    "證券代號", "證券名稱",
    "外陸資買進股數(不含外資自營商)", "外陸資賣出股數(不含外資自營商)", "外陸資買賣超股數(不含外資自營商)",
    "外資自營商買進股數", "外資自營商賣出股數", "外資自營商買賣超股數",
    "投信買進股數", "投信賣出股數", "投信買賣超股數",
    "自營商買賣超股數",
    "自營商買進股數(自行買賣)", "自營商賣出股數(自行買賣)", "自營商買賣超股數(自行買賣)",
    "自營商買進股數(避險)", "自營商賣出股數(避險)", "自營商買賣超股數(避險)",
    "三大法人買賣超股數",
]
T86_2330 = ["2330", "台積電          ", "12,403,967", "25,098,593", "-12,694,626", "0", "0", "0",
            "1,370,000", "20,049", "1,349,951", "1,195,500", "190,854", "479,840", "-288,986",
            "1,592,141", "107,655", "1,484,486", "-10,149,175"]

TPEX_6488 = ["6488", "環球晶", "1,929,231", "4,028,737", "-2,099,506", "0", "0", "0",
             "1,929,231", "4,028,737", "-2,099,506", "4,000", "208,000", "-204,000",
             "45,000", "98,199", "-53,199", "614,015", "845,738", "-231,723",
             "659,015", "943,937", "-284,922", "-2,588,428"]


class TestParseTwseT86:
    def test_parses_foreign_trust_dealer_in_lots(self):
        flows = parse_twse_t86({"stat": "OK", "fields": T86_FIELDS, "data": [T86_2330]})
        assert flows["2330"] == {"foreign_net": -12695, "trust_net": 1350, "dealer_net": 1196}

    def test_locates_columns_by_field_name(self):
        # Reordered fields must still resolve by name, not by fixed index.
        order = [0, 1, 10, 4, 11] + [i for i in range(19) if i not in (0, 1, 10, 4, 11)]
        fields = [T86_FIELDS[i] for i in order]
        row = [T86_2330[i] for i in order]
        flows = parse_twse_t86({"stat": "OK", "fields": fields, "data": [row]})
        assert flows["2330"]["trust_net"] == 1350
        assert flows["2330"]["foreign_net"] == -12695

    def test_no_data_stat_returns_empty(self):
        assert parse_twse_t86({"stat": "很抱歉，沒有符合條件的資料!", "total": 0}) == {}

    def test_garbage_rows_skipped(self):
        bad = ["9999", "壞", "0", "0", "x"] + ["0"] * 14
        flows = parse_twse_t86({"stat": "OK", "fields": T86_FIELDS, "data": [bad, T86_2330]})
        assert list(flows) == ["2330"]


class TestFetchMarketInst:
    def test_merges_both_markets(self, monkeypatch):
        import sources.institutional as inst
        monkeypatch.setattr(inst, "fetch_twse_inst", lambda d: {"2330": {"foreign_net": 1}})
        monkeypatch.setattr(inst, "fetch_tpex_inst", lambda d: {"6488": {"foreign_net": 2}})
        assert set(inst.fetch_market_inst("2026-10-22", sleep=lambda s: None)) == {"2330", "6488"}

    def test_all_or_nothing_when_one_market_missing(self, monkeypatch):
        import sources.institutional as inst
        monkeypatch.setattr(inst, "fetch_twse_inst", lambda d: {"2330": {"foreign_net": 1}})
        monkeypatch.setattr(inst, "fetch_tpex_inst", lambda d: {})
        assert inst.fetch_market_inst("2026-10-22", sleep=lambda s: None) == {}


class TestParseTpexInsti:
    def test_parses_fixed_groups_in_lots(self):
        payload = {"stat": "ok", "date": "20261022", "tables": [{"data": [TPEX_6488]}, {}]}
        assert parse_tpex_insti(payload)["6488"] == {"foreign_net": -2100, "trust_net": -204, "dealer_net": -285}

    def test_short_rows_skipped(self):
        payload = {"stat": "ok", "tables": [{"data": [TPEX_6488[:10], TPEX_6488]}]}
        assert list(parse_tpex_insti(payload)) == ["6488"]

    def test_missing_tables_returns_empty(self):
        assert parse_tpex_insti({"stat": "ok", "tables": []}) == {}
        assert parse_tpex_insti({"stat": "error"}) == {}
