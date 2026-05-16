"""
twse.py — TWSE OpenAPI client

外部行為：
  fetch_twse_daily() -> list[dict]
  每筆回傳 {stock_id, name, volume, price_change_pct}
"""

from __future__ import annotations
import logging
import random
import time

import requests

TWSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TwseHeatBot/1.0)",
    "Accept": "application/json",
}

logger = logging.getLogger(__name__)


def fetch_twse_daily() -> list[dict]:
    """
    取得 TWSE 全市場當日成交資料。
    回傳欄位: stock_id, name, volume, price_change_pct
    """
    time.sleep(random.uniform(1.0, 3.0))
    try:
        resp = requests.get(TWSE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
        return _parse(raw)
    except Exception as exc:
        logger.error("TWSE fetch failed: %s", exc)
        return []


def _parse(raw: list[dict]) -> list[dict]:
    result = []
    for row in raw:
        try:
            volume = int(str(row.get("Volume", "0")).replace(",", "") or "0")
            open_price = float(str(row.get("OpeningPrice", "0")).replace(",", "") or "0")
            close_price = float(str(row.get("ClosingPrice", "0")).replace(",", "") or "0")
            pct = ((close_price - open_price) / open_price * 100) if open_price else 0.0
            result.append({
                "stock_id": str(row.get("Code", "")).strip(),
                "name": str(row.get("Name", "")).strip(),
                "volume": volume,
                "price_change_pct": round(pct, 2),
            })
        except (ValueError, ZeroDivisionError):
            continue
    return [r for r in result if r["stock_id"]]
