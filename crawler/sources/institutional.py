"""
institutional.py — 三大法人 whole-market daily reports (one request per market per date)

  上市 TWSE  rwd/zh/fund/T86?date=YYYYMMDD&selectType=ALLBUT0999&response=json
             named fields; columns located by field name
  上櫃 TPEx  www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=YYYY/MM/DD&response=json
             fields are generic 買進/賣出/買賣超 repeated in 7 fixed groups:
             外資(不含外資自營商) 2-4 · 外資自營商 5-7 · 外資合計 8-10 · 投信 11-13 ·
             自營商自行 14-16 · 自營商避險 17-19 · 自營商合計 20-22 · 三大法人 23
             (verified against the TPEx OpenAPI on 2026-10-22)

Both report shares; values are returned in 張 (shares / 1000, rounded).
Returns {stock_id: {foreign_net, trust_net, dealer_net}}; {} when the date has no
report yet (not published / holiday) or the request fails.
"""

import logging
import random
import time

import requests

logger = logging.getLogger(__name__)

TWSE_T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_INSTI_URL = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# TWSE T86 field names (fallback to the documented index if a name changes)
_T86_COLUMNS = {
    "foreign_net": ("外陸資買賣超股數(不含外資自營商)", 4),
    "trust_net": ("投信買賣超股數", 10),
    "dealer_net": ("自營商買賣超股數", 11),
}
_TPEX_COLUMNS = {"foreign_net": 4, "trust_net": 13, "dealer_net": 22}
_TPEX_MIN_COLS = 24


def _lots(value) -> int:
    return round(int(str(value).replace(",", "").strip()) / 1000)


def parse_twse_t86(payload: dict) -> dict[str, dict]:
    if not payload or payload.get("stat") != "OK":
        return {}
    fields = [str(f).strip() for f in payload.get("fields") or []]
    idx = {
        key: (fields.index(name) if name in fields else fallback)
        for key, (name, fallback) in _T86_COLUMNS.items()
    }
    out: dict[str, dict] = {}
    for row in payload.get("data") or []:
        try:
            out[str(row[0]).strip()] = {key: _lots(row[i]) for key, i in idx.items()}
        except (ValueError, IndexError, TypeError):
            continue
    return out


def parse_tpex_insti(payload: dict) -> dict[str, dict]:
    if not payload or str(payload.get("stat", "")).lower() != "ok":
        return {}
    tables = payload.get("tables") or []
    if not tables:
        return {}
    out: dict[str, dict] = {}
    for row in tables[0].get("data") or []:
        if len(row) < _TPEX_MIN_COLS:
            continue
        try:
            out[str(row[0]).strip()] = {key: _lots(row[i]) for key, i in _TPEX_COLUMNS.items()}
        except (ValueError, TypeError):
            continue
    return out


def _get_json(url: str, params: dict, timeout: int = 20, max_retries: int = 2) -> dict:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers={"User-Agent": _UA, "Accept": "application/json"},
                                timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(random.uniform(3.0, 6.0))
    logger.warning("institutional fetch failed %s %s: %s", url, params, last_exc)
    return {}


def fetch_twse_inst(trade_date: str) -> dict[str, dict]:
    """trade_date: 'YYYY-MM-DD'."""
    payload = _get_json(TWSE_T86_URL, {
        "date": trade_date.replace("-", ""), "selectType": "ALLBUT0999", "response": "json",
    })
    return parse_twse_t86(payload)


def fetch_tpex_inst(trade_date: str) -> dict[str, dict]:
    """trade_date: 'YYYY-MM-DD'."""
    payload = _get_json(TPEX_INSTI_URL, {
        "type": "Daily", "sect": "EW", "date": trade_date.replace("-", "/"), "response": "json",
    })
    return parse_tpex_insti(payload)


def fetch_market_inst(trade_date: str, sleep=time.sleep) -> dict[str, dict]:
    """Both markets for one date, politely spaced (TWSE throttles bursts).

    All-or-nothing: if either market is empty the date returns {} so it stays
    "missing" and is retried next run, instead of being stored half-filled.
    """
    twse = fetch_twse_inst(trade_date)
    sleep(random.uniform(3.0, 5.0))
    tpex = fetch_tpex_inst(trade_date)
    logger.info("三大法人 %s: TWSE %d + TPEx %d", trade_date, len(twse), len(tpex))
    if not twse or not tpex:
        return {}
    return {**twse, **tpex}
