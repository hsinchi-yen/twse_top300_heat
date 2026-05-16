"""
etf_processor.py — merge TWSE + Yahoo data, classify ETF type, compute ranks

External behaviour (testable):
  classify_etf_type(etf_id, name) -> str
  compute_etf_ranks(records)      -> list[dict]
  merge_etf_data(daily, outstanding, nav_map, asset_map) -> list[dict]
"""

from __future__ import annotations
import re

# ── ETF static metadata (management fee + tracking index) ──────────────────
# Covers top 100 Taiwan ETFs; remaining ETFs get defaults.
_META: dict[str, dict] = {
    "0050":   {"fee": 0.32, "index": "台灣50指數"},
    "0056":   {"fee": 0.66, "index": "台灣高股息指數"},
    "006208": {"fee": 0.15, "index": "富邦台灣採樣50指數"},
    "00631L": {"fee": 1.00, "index": "臺灣50指數(2倍槓桿)"},
    "00632R": {"fee": 1.00, "index": "臺灣50指數(反向1倍)"},
    "00635U": {"fee": 0.34, "index": "S&P黃金ER指數"},
    "00642U": {"fee": 0.99, "index": "標普高盛原油ER指數"},
    "00679B": {"fee": 0.15, "index": "彭博巴克萊美國20+年期國債指數"},
    "00687B": {"fee": 0.20, "index": "彭博巴克萊20年以上美國公債指數"},
    "00720B": {"fee": 0.25, "index": "彭博巴克萊投資級公司債指數"},
    "00830":  {"fee": 0.45, "index": "費城半導體指數"},
    "00878":  {"fee": 0.25, "index": "MSCI台灣ESG永續高股息精選30指數"},
    "00881":  {"fee": 0.45, "index": "臺灣5G通訊ETF指數"},
    "00919":  {"fee": 0.25, "index": "台灣精選高息30指數"},
    "00929":  {"fee": 0.25, "index": "台灣科技優息指數"},
    "00940":  {"fee": 0.25, "index": "台灣價值高息指數"},
    "00981A": {"fee": 0.45, "index": "AI收益成長指數"},
}


def classify_etf_type(etf_id: str, name: str) -> str:
    """
    Classify ETF into: 股票型 / 債券型 / 商品型 / 槓桿/反向 / 貨幣市場

    Rules (order matters — more specific first):
      1. ID ends with L or R (or name has 正2/反1/槓桿/反向) → 槓桿/反向
      2. ID ends with B or name contains 債 / Bond           → 債券型
      3. ID ends with U or name contains 黃金/原油/商品/貴金屬 → 商品型
      4. Name contains 貨幣                                   → 貨幣市場
      5. Default                                              → 股票型
    """
    eid  = etf_id.upper()
    nlow = name

    if (eid.endswith('L') or eid.endswith('R')
            or any(kw in nlow for kw in ('正2', '反1', '槓桿', '反向'))):
        return "槓桿/反向"

    # 貨幣市場先於債券判斷：名稱含「貨幣」比 ID 後綴 B 更具體
    if '貨幣' in nlow:
        return "貨幣市場"

    if eid.endswith('B') or any(kw in nlow for kw in ('債', 'Bond', 'bond')):
        return "債券型"

    if eid.endswith('U') or any(kw in nlow for kw in ('黃金', '原油', '商品', '貴金屬', '白銀')):
        return "商品型"

    return "股票型"


def compute_color_tier(price_change_pct: float) -> str:
    if price_change_pct >= 5.0:  return "deep_red"
    if price_change_pct >= 1.0:  return "light_red"
    if price_change_pct > -1.0:  return "neutral"
    if price_change_pct >= -5.0: return "light_green"
    return "deep_green"


def merge_etf_data(
    daily: list[dict],
    outstanding_map: dict[str, float],
    nav_map: dict[str, float],
    asset_map: dict[str, float],
) -> list[dict]:
    """
    Merge TWSE daily prices with outstanding units, NAV, and Yahoo asset scale.
    Computes turnover_rate and premium_discount.
    Returns enriched records ready for compute_etf_ranks().
    """
    records = []
    for row in daily:
        etf_id = row["etf_id"]
        volume = row.get("volume", 0) or 0
        close  = row.get("close_price", 0.0) or 0.0
        pct    = row.get("price_change_pct", 0.0) or 0.0
        name   = row.get("name", "")

        outstanding = outstanding_map.get(etf_id, 0.0)
        nav         = nav_map.get(etf_id)
        asset_scale = asset_map.get(etf_id)

        turnover_rate = (
            round((volume / outstanding) * 100, 4)
            if outstanding > 0 else None
        )
        premium_discount = (
            round(((close - nav) / nav) * 100, 3)
            if nav and nav > 0 else None
        )

        meta          = _META.get(etf_id, {})
        etf_type      = classify_etf_type(etf_id, name)
        tracking_idx  = meta.get("index", "")
        mgmt_fee      = meta.get("fee")

        records.append({
            "etf_id":            etf_id,
            "name":              name,
            "etf_type":          etf_type,
            "tracking_index":    tracking_idx,
            "management_fee":    mgmt_fee,
            "asset_scale":       asset_scale,
            "outstanding_units": outstanding if outstanding > 0 else None,
            "volume":            volume,
            "turnover_rate":     turnover_rate,
            "close_price":       close,
            "price_change_pct":  pct,
            "nav":               nav,
            "premium_discount":  premium_discount,
            "color_tier":        compute_color_tier(pct),
            "turnover_rank":     None,
            "asset_scale_rank":  None,
        })

    return compute_etf_ranks(records)


def compute_etf_ranks(records: list[dict]) -> list[dict]:
    """
    Assigns turnover_rank (by turnover_rate desc, None last)
    and asset_scale_rank (by asset_scale desc, None last).
    Mutates records in place and returns them.
    """
    by_turnover = sorted(
        records,
        key=lambda r: (r["turnover_rate"] is None, -(r["turnover_rate"] or 0))
    )
    for i, r in enumerate(by_turnover, 1):
        r["turnover_rank"] = i

    by_scale = sorted(
        records,
        key=lambda r: (r["asset_scale"] is None, -(r["asset_scale"] or 0))
    )
    for i, r in enumerate(by_scale, 1):
        r["asset_scale_rank"] = i

    return records
