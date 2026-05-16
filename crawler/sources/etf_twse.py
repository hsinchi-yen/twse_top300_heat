"""
etf_twse.py — TWSE ETF data fetcher

Fetches from two TWSE OpenAPI endpoints:
  1. STOCK_DAY_ALL — daily prices + volume for all securities (ETF filter applied)
  2. TWD4U         — ETF NAV (淨值) per unit

ETF identification: stock_id starts with '0' OR is 6+ chars (e.g. 006208, 00878)
"""

from __future__ import annotations
import logging
import random
import time

import requests

TWSE_DAILY_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_NAV_URL   = "https://openapi.twse.com.tw/v1/exchangeReport/TWD4U"

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

logger = logging.getLogger(__name__)


def _http_get(url: str, timeout: int = 15, max_retries: int = 3) -> list:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        time.sleep(random.uniform(1.0, 2.5))
        headers = {"User-Agent": random.choice(_UA_POOL), "Accept": "application/json"}
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = (2 ** attempt) * random.uniform(2.0, 4.0)
                logger.warning("TWSE ETF attempt %d/%d failed: %s. Retry in %.1fs",
                               attempt + 1, max_retries, exc, wait)
                time.sleep(wait)
    logger.error("TWSE ETF fetch failed after %d attempts: %s", max_retries, last_exc)
    return []


def _is_etf(stock_id: str) -> bool:
    """
    ETF identifiers on TWSE:
      - 4-char starting with '0'  (e.g. 0050, 0056)
      - 5-char starting with '0'  (e.g. 00878, 00929)
      - 6-char numeric             (e.g. 006208, 00679B treated as ≥5 starting with 0)
      - 6-char with trailing letter (e.g. 00981A, 00632R)
    Rule: starts with '0' AND length ≥ 4, OR length ≥ 6
    """
    if not stock_id:
        return False
    if stock_id[0] == '0' and len(stock_id) >= 4:
        return True
    if len(stock_id) >= 6:
        return True
    return False


def fetch_etf_daily() -> tuple[list[dict], str | None]:
    """
    Returns (records, trading_date).
    Each record: {etf_id, name, volume, close_price, price_change_pct}
    """
    raw = _http_get(TWSE_DAILY_URL)
    trading_date = _extract_trading_date(raw)
    records = _parse_daily(raw)
    logger.info("TWSE ETF daily: %d ETF records, date=%s", len(records), trading_date)
    return records, trading_date


def _extract_trading_date(raw: list) -> str | None:
    if not raw:
        return None
    date_raw = str(raw[0].get("Date", "")).strip().replace("/", "")
    if len(date_raw) == 7 and date_raw.isdigit():
        try:
            roc = int(date_raw[:3])
            m   = int(date_raw[3:5])
            d   = int(date_raw[5:7])
            return f"{roc + 1911:04d}-{m:02d}-{d:02d}"
        except ValueError:
            pass
    return None


def _parse_daily(raw: list[dict]) -> list[dict]:
    result = []
    for row in raw:
        stock_id = str(row.get("Code", "")).strip()
        if not _is_etf(stock_id):
            continue
        try:
            volume      = int(str(row.get("TradeVolume", "0")).replace(",", "") or "0")
            close_price = float(str(row.get("ClosingPrice", "0")).replace(",", "") or "0")
            change      = float(str(row.get("Change", "0")).replace(",", "").replace("+", "") or "0")
            yesterday   = close_price - change
            pct         = round((change / yesterday * 100), 2) if yesterday > 0 else 0.0
            result.append({
                "etf_id":           stock_id,
                "name":             str(row.get("Name", "")).strip(),
                "volume":           volume,
                "close_price":      close_price,
                "price_change_pct": pct,
            })
        except (ValueError, ZeroDivisionError):
            continue
    return result


def fetch_etf_nav() -> dict[str, float]:
    """
    Returns {etf_id: nav_per_unit} from TWSE TWD4U endpoint.
    NAV is used to compute premium/discount vs close_price.
    """
    raw = _http_get(TWSE_NAV_URL)
    nav_map: dict[str, float] = {}
    for row in raw:
        etf_id = str(row.get("ETFid", "") or row.get("Code", "")).strip()
        if not etf_id:
            continue
        try:
            nav = float(str(row.get("NAV", "0")).replace(",", "") or "0")
            if nav > 0:
                nav_map[etf_id] = nav
        except ValueError:
            continue
    logger.info("TWSE ETF NAV: %d records", len(nav_map))
    return nav_map


def fetch_etf_outstanding_units() -> dict[str, float]:
    """
    Returns {etf_id: outstanding_units} from TWSE fund_list endpoint.
    Outstanding units needed for turnover_rate = volume / outstanding_units * 100.
    Falls back gracefully if endpoint unavailable.
    """
    url = "https://openapi.twse.com.tw/v1/ETF/fund_list"
    raw = _http_get(url)
    units_map: dict[str, float] = {}
    for row in raw:
        etf_id = str(row.get("ETFid", "") or row.get("Code", "")).strip()
        if not etf_id:
            continue
        try:
            # field name varies by API version
            units_raw = (
                row.get("OutstandingUnits")
                or row.get("Units")
                or row.get("IssuedUnits")
                or "0"
            )
            units = float(str(units_raw).replace(",", "") or "0")
            if units > 0:
                units_map[etf_id] = units
        except ValueError:
            continue
    logger.info("TWSE ETF outstanding units: %d records", len(units_map))
    return units_map
