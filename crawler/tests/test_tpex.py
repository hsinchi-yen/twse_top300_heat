"""
test_tpex.py — TPEx mainboard daily close feed parser.

Fixture is the live tpex_mainboard_daily_close_quotes row for 6488 on
2026-10-22. The feed reports volume as `TradingShares` and the move as
`Change` (there is no `TradeVolume` / `Yesterday`); reading the old names made
every 上櫃 stock volume 0 / change 0%, so none could rank into the display pool.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources.tpex import _parse

ROW_6488 = {
    "Date": "1151022", "SecuritiesCompanyCode": "6488", "CompanyName": "環球晶",
    "Close": "826.00", "Change": "-54.00 ", "Open": "896.00", "High": "898.00",
    "Low": "815.00", "Average": "852.03", "TradingShares": "10520541",
    "TransactionAmount": "8963825169", "TransactionNumber": "49523",
}


def test_volume_from_trading_shares():
    assert _parse([ROW_6488])[0]["volume"] == 10520541


def test_price_change_pct_from_close_and_change():
    # yesterday = 826 + 54 = 880 → -54 / 880 = -6.14%
    rec = _parse([ROW_6488])[0]
    assert rec["close_price"] == 826.0
    assert rec["price_change_pct"] == -6.14


def test_legacy_field_names_still_supported():
    legacy = {"SecuritiesCompanyCode": "6488", "CompanyName": "環球晶",
              "Close": "826", "Yesterday": "880", "TradeVolume": "1,000"}
    rec = _parse([legacy])[0]
    assert rec["volume"] == 1000
    assert rec["price_change_pct"] == -6.14


def test_unparseable_change_keeps_stock_with_zero_change():
    row = {**ROW_6488, "Change": "---"}
    rec = _parse([row])[0]
    assert rec["volume"] == 10520541
    assert rec["price_change_pct"] == 0.0


def test_etf_codes_still_excluded():
    assert _parse([{**ROW_6488, "SecuritiesCompanyCode": "00679B"}]) == []
