"""
twse.py — TWSE OpenAPI client

外部行為：
  fetch_twse_daily() -> list[dict]
  每筆回傳 {stock_id, name, volume, price_change_pct}

防護策略：
  - 隨機 User-Agent 輪換，降低被識別為 bot 的機率
  - Retry with exponential backoff（最多 3 次）
  - 每次請求前加 1-3 秒隨機 delay（polite crawling）
"""

from __future__ import annotations
import logging
import random
import time

import requests

TWSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

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
                logger.warning("TWSE attempt %d/%d failed: %s. Retrying in %.1fs",
                               attempt + 1, max_retries, exc, wait)
                time.sleep(wait)
    logger.error("TWSE fetch failed after %d attempts: %s", max_retries, last_exc)
    return []


def fetch_twse_daily() -> tuple[list[dict], str | None]:
    """
    取得 TWSE 全市場當日成交資料。
    回傳: (records, trading_date)
      records: list of {stock_id, name, volume, price_change_pct}
      trading_date: ISO date string (e.g. "2026-05-15"), or None if unavailable
    """
    raw = _http_get(TWSE_URL)
    trading_date = _extract_trading_date(raw)
    if trading_date:
        logger.info("TWSE trading date from API: %s", trading_date)
    return _parse(raw), trading_date


def _extract_trading_date(raw: list) -> str | None:
    """
    從 TWSE API 回應中取出交易日期。
    TWSE Date 欄位格式: "1150515" (民國 115 年 5 月 15 日)
    或含斜線 "115/05/15"。
    """
    if not raw:
        return None
    date_raw = str(raw[0].get("Date", "")).strip().replace("/", "")
    if len(date_raw) == 7 and date_raw.isdigit():
        try:
            roc_year = int(date_raw[:3])
            month    = int(date_raw[3:5])
            day      = int(date_raw[5:7])
            return f"{roc_year + 1911:04d}-{month:02d}-{day:02d}"
        except ValueError:
            pass
    return None


def _parse(raw: list[dict]) -> list[dict]:
    result = []
    for row in raw:
        try:
            # TWSE API field name is "TradeVolume" (in shares, not lots)
            volume = int(str(row.get("TradeVolume", "0")).replace(",", "") or "0")
            close_price = float(str(row.get("ClosingPrice", "0")).replace(",", "") or "0")
            change = float(str(row.get("Change", "0")).replace(",", "").replace("+", "") or "0")
            # pct = change / yesterday_close × 100; yesterday_close = close - change
            yesterday_close = close_price - change
            pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0.0
            result.append({
                "stock_id": str(row.get("Code", "")).strip(),
                "name": str(row.get("Name", "")).strip(),
                "volume": volume,
                "close_price": close_price,
                "price_change_pct": round(pct, 2),
            })
        except (ValueError, ZeroDivisionError):
            continue

    # 一般上市股票代號：4 位純數字且不以 0 開頭（1000-9999）
    # ETF 為 6 位（006201 等）或 4 位以 0 開頭（0050 等），皆排除
    return [r for r in result
            if len(r["stock_id"]) == 4
            and r["stock_id"].isdigit()
            and r["stock_id"][0] != "0"]
