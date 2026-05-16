"""
ranker.py — 排名計算與 color_tier 判斷邏輯

外部行為（測試對象）：
- compute_color_tier(price_change_pct) -> str
- compute_ranks(records) -> list[dict]  (附帶 volume_rank, turnover_rank)
"""

from __future__ import annotations

SECTORS = ["AI", "散熱", "機器人", "重電", "航運", "PCB", "半導體"]

# 色階邊界（台股：漲=紅，跌=綠）
_COLOR_TIERS = [
    (5.0, "deep_red"),
    (1.0, "light_red"),
    (-1.0, "neutral"),
    (-5.0, "light_green"),
]


def compute_color_tier(price_change_pct: float) -> str:
    """
    將漲跌幅百分比對應至 5 段色階字串。

    >>> compute_color_tier(6.0)
    'deep_red'
    >>> compute_color_tier(3.0)
    'light_red'
    >>> compute_color_tier(0.0)
    'neutral'
    >>> compute_color_tier(-2.0)
    'light_green'
    >>> compute_color_tier(-6.0)
    'deep_green'
    """
    for threshold, tier in _COLOR_TIERS:
        if price_change_pct >= threshold:
            return tier
    return "deep_green"


def compute_ranks(records: list[dict]) -> list[dict]:
    """
    給定股票記錄清單（含 volume, turnover_rate），
    計算並附加 volume_rank 與 turnover_rank（1-based，越小越高）。

    records 欄位：stock_id, name, volume, turnover_rate, price_change_pct
    回傳：相同欄位 + volume_rank, turnover_rank, color_tier
    """
    # Volume rank
    by_volume = sorted(records, key=lambda r: r.get("volume", 0), reverse=True)
    for rank, record in enumerate(by_volume, start=1):
        record["volume_rank"] = rank

    # Turnover rank
    by_turnover = sorted(records, key=lambda r: r.get("turnover_rate", 0.0), reverse=True)
    for rank, record in enumerate(by_turnover, start=1):
        record["turnover_rank"] = rank

    # Color tier
    for record in records:
        record["color_tier"] = compute_color_tier(record.get("price_change_pct", 0.0))

    return records
