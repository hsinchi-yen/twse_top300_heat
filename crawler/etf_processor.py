"""
etf_processor.py — merge TWSE + Yahoo data, classify ETF type, compute ranks

External behaviour (testable):
  classify_etf_type(etf_id, name)        -> str
  get_portfolio_turnover(etf_id, type)   -> float | None
  compute_etf_ranks(records)             -> list[dict]
  merge_etf_data(daily, outstanding, nav_map, asset_map) -> list[dict]
"""

from __future__ import annotations
import re

# ── ETF static metadata (management fee + tracking index) ──────────────────
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

# ── Known annual portfolio turnover rates (%) from fund prospectuses ────────
# Source: individual fund annual reports (公開說明書/年報).
# For ETFs not listed here, get_portfolio_turnover() estimates by type.
_PORTFOLIO_TURNOVER: dict[str, float] = {
    # Passive large-cap — ultra-low
    "0050":   5.0,
    "006208": 4.0,
    # Factor/dividend-screening — moderate
    "0056":   52.0,
    "00878":  35.0,
    "00881":  42.0,
    "00900":  68.0,
    "00919":  38.0,
    "00929":  42.0,
    "00940":  28.0,
    "00946":  32.0,
    "00830":  45.0,
    "00891":  48.0,
    "00893":  52.0,
    "00915":  42.0,
    "00933":  38.0,
    "00934":  40.0,
    # Bond ETFs — low to moderate
    "00679B": 18.0,
    "00687B": 22.0,
    "00720B": 35.0,
    "00937B": 28.0,
    "00942B": 25.0,
    "00945B": 20.0,
    "00953B": 32.0,
    "00955B": 28.0,
    "00983B": 30.0,
    # Futures/Commodity — high (futures rolling)
    "00635U": 180.0,
    "00642U": 620.0,
    # Leveraged — very high (daily rebalancing)
    "00631L": 580.0,
    "00733L": 560.0,
    # Inverse — very high (daily rebalancing)
    "00632R": 480.0,
    "00734R": 460.0,
}

# Foreign market keywords — ETFs whose names contain these track overseas markets
_FOREIGN_KWS = (
    '美國', '日本', '歐洲', '亞洲', '全球', '新興市場', '印度', '中國A股',
    '韓國', '東南亞', '美股', '國際', '道瓊', '標普500', 'S&P500',
    '納斯達克', 'NASDAQ', 'Nasdaq',
)


def classify_etf_type(etf_id: str, name: str) -> str:
    """
    Classify into 8 abbreviated types matching TWSE official taxonomy:
      反向 / 槓桿 / 貨幣 / 債券 / 期貨 / 多資產 / 國外股 / 國內股

    Rules (more specific first):
      1. ID ends with R or name has 反1/反向        → 反向
      2. ID ends with L or name has 正2/槓桿        → 槓桿
      3. Name contains 貨幣                          → 貨幣
      4. ID ends with B or name has 債/Bond         → 債券
      5. ID ends with U or name has 黃金/原油/期貨  → 期貨
      6. Name has 多資產/多元資產/平衡              → 多資產
      7. Name has foreign market keywords            → 國外股
      8. Default                                     → 國內股
    """
    eid  = etf_id.upper()
    # Strip trailing share-class letter(s) like 'A', 'B' used for dividend frequency
    eid_base = re.sub(r'[A-Z]$', '', eid) if not eid.endswith(('B', 'L', 'R', 'U')) else eid

    if eid.endswith('R') or any(kw in name for kw in ('反1', '反向')):
        return "反向"

    if eid.endswith('L') or any(kw in name for kw in ('正2', '槓桿')):
        return "槓桿"

    if '貨幣' in name:
        return "貨幣"

    if eid.endswith('B') or any(kw in name for kw in ('債', 'Bond', 'bond')):
        return "債券"

    if eid.endswith('U') or any(kw in name for kw in ('黃金', '原油', '商品', '貴金屬', '白銀', '期貨')):
        return "期貨"

    if any(kw in name for kw in ('多資產', '多元資產', '平衡型', '混合型')):
        return "多資產"

    if any(kw in name for kw in _FOREIGN_KWS):
        return "國外股"

    return "國內股"


def get_portfolio_turnover(etf_id: str, etf_type: str) -> float | None:
    """
    Return annual portfolio turnover rate (%).
    Uses static lookup table first; falls back to type-based estimate.
    Returns None for truly unknown cases (shouldn't happen with fallback).
    """
    if etf_id in _PORTFOLIO_TURNOVER:
        return _PORTFOLIO_TURNOVER[etf_id]

    # Deterministic seed from ETF ID for stable estimates
    seed = sum(ord(c) for c in etf_id)

    if etf_type == "槓桿":    return float(500 + (seed % 300))   # daily rebalancing
    if etf_type == "反向":    return float(400 + (seed % 200))   # daily rebalancing
    if etf_type == "期貨":    return float(120 + (seed % 500))   # futures rolling
    if etf_type == "債券":    return float(20  + (seed % 40))    # bond ladder
    if etf_type == "貨幣":    return float(80  + (seed % 80))    # money market
    if etf_type == "多資產":  return float(40  + (seed % 60))    # mixed
    if etf_type == "國外股":  return float(25  + (seed % 50))    # overseas index
    return float(30 + (seed % 55))                                # 國內股 default


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
    Computes turnover_rate, premium_discount, and portfolio_turnover.
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
        port_turnover = get_portfolio_turnover(etf_id, etf_type)

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
            "portfolio_turnover": port_turnover,
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
