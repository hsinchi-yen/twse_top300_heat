"""
finmind.py — FinMind SDK wrapper（週轉率計算用）

外部行為：
  fetch_issue_shares() -> dict[stock_id, issue_shares]
  每日只需取一次，結果 cache 在記憶體。
"""

from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)

_CACHE: dict[str, int] = {}


def fetch_issue_shares() -> dict[str, int]:
    """
    從 FinMind 取得所有股票的發行股數（流通股數）。
    回傳 {stock_id: issue_shares}
    使用記憶體 cache，避免重複請求。
    """
    global _CACHE
    if _CACHE:
        return _CACHE

    token = os.getenv("FINMIND_TOKEN", "")
    try:
        from FinMind.data import DataLoader
        dl = DataLoader()
        if token:
            dl.login_by_token(token)
        info = dl.taiwan_stock_info()
        _CACHE = {
            str(row["stock_id"]): int(row.get("sharesList", 0) or 0)
            for _, row in info.iterrows()
            if row.get("sharesList")
        }
        logger.info("FinMind: loaded %d stock issue_shares", len(_CACHE))
    except Exception as exc:
        logger.error("FinMind fetch failed: %s", exc)
        _CACHE = {}

    return _CACHE


def clear_cache() -> None:
    """每日重置 cache（供排程使用）。"""
    global _CACHE
    _CACHE = {}
