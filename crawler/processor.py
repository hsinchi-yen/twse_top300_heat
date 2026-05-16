"""
processor.py — 合併 TWSE + TPEX 資料，計算週轉率與排名

外部行為（測試對象）：
  merge_and_rank(twse_records, tpex_records, issue_shares) -> list[dict]
  回傳每筆含: stock_id, name, volume, turnover_rate, price_change_pct,
              color_tier, volume_rank, turnover_rank
"""

from __future__ import annotations


def _color_tier(pct: float) -> str:
    if pct >= 5.0:
        return "deep_red"
    if pct >= 1.0:
        return "light_red"
    if pct > -1.0:
        return "neutral"
    if pct >= -5.0:
        return "light_green"
    return "deep_green"


def merge_and_rank(
    twse_records: list[dict],
    tpex_records: list[dict],
    issue_shares: dict[str, int],
) -> list[dict]:
    """
    合併 TWSE + TPEX 資料，附加週轉率與雙排名。

    Args:
        twse_records: TWSE 當日資料 [{stock_id, name, volume, price_change_pct}]
        tpex_records: TPEX 當日資料 [{stock_id, name, volume, price_change_pct}]
        issue_shares: FinMind 股本 {stock_id: issue_shares}

    Returns:
        排名後的股票清單（所有股票，含 volume_rank, turnover_rank）
    """
    # 合併，TWSE 優先（同 stock_id 時 TWSE 覆蓋 TPEX）
    combined: dict[str, dict] = {}
    for r in tpex_records:
        combined[r["stock_id"]] = dict(r)
    for r in twse_records:
        combined[r["stock_id"]] = dict(r)

    records = list(combined.values())

    # 週轉率 = 成交量 / 發行股數 × 100
    for r in records:
        shares = issue_shares.get(r["stock_id"], 0)
        r["turnover_rate"] = round(r["volume"] / shares * 100, 4) if shares > 0 else 0.0
        r["color_tier"] = _color_tier(r.get("price_change_pct", 0.0))

    # Volume rank（降冪）
    by_vol = sorted(records, key=lambda r: r["volume"], reverse=True)
    for i, r in enumerate(by_vol, 1):
        r["volume_rank"] = i

    # Turnover rank（降冪）
    by_turn = sorted(records, key=lambda r: r["turnover_rate"], reverse=True)
    for i, r in enumerate(by_turn, 1):
        r["turnover_rank"] = i

    return records
