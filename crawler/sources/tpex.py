"""
tpex.py — TPEX (上櫃) OpenAPI client

外部行為：
  fetch_tpex_daily() -> list[dict]
  每筆回傳 {stock_id, name, volume, price_change_pct}

防護策略：同 twse.py（UA 輪換 + retry + backoff）
"""

from __future__ import annotations
import logging
import random
import time

import requests

TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

logger = logging.getLogger(__name__)


def _http_get(url: str, timeout: int = 15, max_retries: int = 3) -> list:
    """帶 retry / exponential backoff 的 GET 請求。"""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        time.sleep(random.uniform(1.0, 3.0))
        headers = {
            "User-Agent": random.choice(_UA_POOL),
            "Accept": "application/json",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = (2 ** attempt) * random.uniform(2.0, 4.0)
                logger.warning("TPEX attempt %d/%d failed: %s. Retrying in %.1fs",
                               attempt + 1, max_retries, exc, wait)
                time.sleep(wait)
    logger.error("TPEX fetch failed after %d attempts: %s", max_retries, last_exc)
    return []


def fetch_tpex_daily() -> list[dict]:
    """
    取得 TPEX 上櫃全市場當日成交資料。
    回傳欄位: stock_id, name, volume, price_change_pct
    """
    raw = _http_get(TPEX_URL)
    return _parse(raw)


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
                "close_price": closing,
                "price_change_pct": round(pct, 2),
            })
        except (ValueError, ZeroDivisionError):
            continue

    # 一般上櫃股票代號：4 位純數字且不以 0 開頭（1000-9999）
    # ETF 為 6 位或 4 位以 0 開頭，皆排除
    return [r for r in result
            if len(r["stock_id"]) == 4
            and r["stock_id"].isdigit()
            and r["stock_id"][0] != "0"]
