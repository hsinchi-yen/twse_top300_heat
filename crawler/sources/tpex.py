"""
tpex.py — TPEX (上櫃) OpenAPI client

外部行為：
  fetch_tpex_daily() -> list[dict]
  每筆回傳 {stock_id, name, volume, price_change_pct}
"""

from __future__ import annotations
import logging
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TZ_TAIPEI = ZoneInfo("Asia/Taipei")
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TwseHeatBot/1.0)",
    "Accept": "application/json",
}

logger = logging.getLogger(__name__)


def fetch_tpex_daily() -> list[dict]:
    """
    取得 TPEX 上櫃全市場當日成交資料。
    回傳欄位: stock_id, name, volume, price_change_pct
    """
    time.sleep(random.uniform(1.0, 3.0))
    today = datetime.now(tz=TZ_TAIPEI).strftime("%Y/%m/%d")
    try:
        resp = requests.get(TPEX_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
        return _parse(raw)
    except Exception as exc:
        logger.error("TPEX fetch failed: %s", exc)
        return []


def _parse(raw: list[dict]) -> list[dict]:
    result = []
    for row in raw:
        try:
            volume = int(str(row.get("TradeVolume", "0")).replace(",", "") or "0")
            yesterday = float(str(row.get("Yesterday", "0")).replace(",", "") or "0")
            closing = float(str(row.get("Close", "0")).replace(",", "") or "0")
            pct = ((closing - yesterday) / yesterday * 100) if yesterday else 0.0
            result.append({
                "stock_id": str(row.get("SecuritiesCompanyCode", "")).strip(),
                "name": str(row.get("CompanyName", "")).strip(),
                "volume": volume,
                "price_change_pct": round(pct, 2),
            })
        except (ValueError, ZeroDivisionError):
            continue
    return [r for r in result if r["stock_id"]]
