"""
finmind.py — 發行股數 & 類股資料（週轉率計算用）

Primary source for shares: TWSE OpenAPI t187ap03_L (上市公司基本資料)
Primary source for industry: FinMind SDK taiwan_stock_info()

Both results are memory-cached and cleared daily by daily_reset_job().
"""

from __future__ import annotations
import logging
import os
import random
import time

import requests

logger = logging.getLogger(__name__)

TWSE_COMPANY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_SHARES_CACHE: dict[str, int] = {}
_INDUSTRY_CACHE: dict[str, str] = {}


def fetch_issue_shares() -> dict[str, int]:
    """
    取得所有股票的發行股數。回傳 {stock_id: issue_shares}
    """
    global _SHARES_CACHE
    if _SHARES_CACHE:
        return _SHARES_CACHE

    _SHARES_CACHE = _fetch_shares_from_twse()
    logger.info("Issue shares loaded: %d stocks", len(_SHARES_CACHE))
    return _SHARES_CACHE


def fetch_industry_categories() -> dict[str, str]:
    """
    取得所有股票的產業類別。回傳 {stock_id: industry_category}
    使用 FinMind taiwan_stock_info() 涵蓋上市+上櫃共 ~4100 支股票。
    """
    global _INDUSTRY_CACHE
    if _INDUSTRY_CACHE:
        return _INDUSTRY_CACHE

    try:
        from FinMind.data import DataLoader
        token = os.getenv("FINMIND_TOKEN", "")
        dl = DataLoader()
        if token:
            dl.login_by_token(token)
        info = dl.taiwan_stock_info()
        result: dict[str, str] = {}
        for _, row in info.iterrows():
            sid = str(row.get("stock_id", "")).strip()
            cat = str(row.get("industry_category", "") or "").strip()
            if sid and cat and cat != "nan":
                result[sid] = cat
        _INDUSTRY_CACHE = result
        logger.info("Industry categories loaded: %d stocks", len(_INDUSTRY_CACHE))
    except Exception as exc:
        logger.error("FinMind industry fetch failed: %s", exc)
        _INDUSTRY_CACHE = {}

    return _INDUSTRY_CACHE


def _fetch_shares_from_twse() -> dict[str, int]:
    """從 TWSE t187ap03_L 取得上市公司發行股數。"""
    time.sleep(random.uniform(1.0, 2.5))
    headers = {
        "User-Agent": random.choice(_UA_POOL),
        "Accept": "application/json",
    }
    try:
        resp = requests.get(TWSE_COMPANY_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("TWSE shares fetch failed: %s", exc)
        return {}

    result: dict[str, int] = {}
    for row in data:
        stock_id = str(row.get("公司代號", "")).strip()
        shares_str = str(row.get("已發行普通股數或TDR原股發行股數", "0")).replace(",", "").strip()
        if not stock_id:
            continue
        try:
            shares = int(shares_str)
            if shares > 0:
                result[stock_id] = shares
        except ValueError:
            continue

    logger.info("TWSE t187ap03_L: %d listed companies with share data", len(result))
    return result


def clear_cache() -> None:
    """每日重置 cache（供排程使用）。"""
    global _SHARES_CACHE, _INDUSTRY_CACHE
    _SHARES_CACHE = {}
    _INDUSTRY_CACHE = {}
    logger.info("Shares and industry cache cleared.")
