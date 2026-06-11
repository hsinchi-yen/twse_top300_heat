"""
buy_score_engine.py — Native buy-score computation (買入評分卡 v3, 24 指標 + 排雷).

Ported from StockAnalysisDashBoard (api.py::buy_score) so this project no longer
proxies to an external HTTP service. Computes scores directly from FinMind via
the local FinMindClient (sources/finmind_client.py).

Public entry point:
    compute_buy_score(stock_id, token=None, client=None) -> dict

Returns the full payload (score / max_score / eligible_count / pass_rate /
criteria / risk_criteria / recommendation / signal …). Callers that only need
the totals read `score` and `max_score`.

Rate-limit behaviour: FinMind quota exhaustion surfaces as FinMindError (HTTP
402) raised from the client — callers should catch it to pause and resume later.
Per-dataset fetches are staggered by BUY_SCORE_FETCH_DELAY seconds.

Goodinfo (外資持股 C10 + 董監質押 R7) is OPT-IN via BUY_SCORE_GOODINFO_ENABLED
because scraping Goodinfo for hundreds of stocks risks an IP ban. When disabled
those two checks degrade to "無資料" (null) and do not affect the other 22.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

import pandas as pd

from sources.finmind_client import FinMindClient, FinMindError

logger = logging.getLogger(__name__)

# Seconds between FinMind dataset call-groups. Raise if FinMind starts stalling
# connections (read timeouts) during a full-pool crawl.
_FETCH_DELAY = float(os.environ.get("BUY_SCORE_FETCH_DELAY", "0.4"))

# Goodinfo is opt-in (ban risk). When disabled, GoodinfoClient is never imported.
_GOODINFO_ENABLED = os.environ.get("BUY_SCORE_GOODINFO_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
GoodinfoClient: Any = None
if _GOODINFO_ENABLED:
    try:
        from sources.goodinfo_client import GoodinfoClient as _GC
        GoodinfoClient = _GC
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Goodinfo enabled but import failed: %s", exc)
        GoodinfoClient = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_sloan_ratio(
    net_income_annual: float,
    operating_cf_annual: float,
    avg_total_assets: float,
) -> float | None:
    """Sloan Ratio (應計比率 / 盈餘品質): (NI - OperatingCF) / AvgTotalAssets."""
    if avg_total_assets == 0:
        return None
    return (net_income_annual - operating_cf_annual) / avg_total_assets


def _compute_roe_roa_ttm(
    ni_q: pd.Series,
    equity: pd.Series,
    assets: pd.Series,
    start_cutoff: pd.Timestamp,
) -> list[dict[str, Any]]:
    """Near-four-quarter (TTM) ROE / ROA — matches 財報狗 '近四季 ROE/ROA'."""
    quarter_dates = sorted(
        dt for dt in ni_q.index if not pd.isna(dt) and dt.month in {3, 6, 9, 12}
    )

    rows: list[dict[str, Any]] = []
    for i, dt in enumerate(quarter_dates):
        if i < 3:
            continue  # need 4 quarters for TTM
        if dt < start_cutoff:
            continue

        last4 = quarter_dates[i - 3 : i + 1]
        if (last4[-1] - last4[0]).days > 400:
            logger.warning("ROE/ROA: skipping %s — gap in quarterly data: %s", dt.date(), last4)
            continue

        ni_vals = [ni_q.get(d) for d in last4]
        if any(v is None or pd.isna(v) for v in ni_vals):
            continue
        ttm_ni = sum(float(v) for v in ni_vals)

        valid_eq = [float(v) for v in (equity.get(d) for d in last4) if v is not None and not pd.isna(v)]
        valid_as = [float(v) for v in (assets.get(d) for d in last4) if v is not None and not pd.isna(v)]
        if not valid_eq or not valid_as:
            continue

        avg_eq = sum(valid_eq) / len(valid_eq)
        avg_as = sum(valid_as) / len(valid_as)
        roe = round(ttm_ni / avg_eq * 100, 2) if avg_eq != 0 else None
        roa = round(ttm_ni / avg_as * 100, 2) if avg_as != 0 else None

        q_num = (dt.month - 1) // 3 + 1
        rows.append({
            "quarter": str(dt.date()),
            "quarter_label": f"{dt.year} Q{q_num}",
            "roe": roe,
            "roa": roa,
        })
    return rows


# Maps industry keyword → criterion IDs that are not applicable for that industry.
INDUSTRY_EXCLUSIONS: dict[str, list[str]] = {
    "金融保險": ["debt_ratio", "debt_ratio_strict", "equity_ratio"],
    "金融": ["debt_ratio", "debt_ratio_strict", "equity_ratio"],
    "銀行": ["debt_ratio", "debt_ratio_strict", "equity_ratio"],
    "保險": ["debt_ratio", "debt_ratio_strict", "equity_ratio"],
    "租賃": ["debt_ratio", "debt_ratio_strict", "equity_ratio"],
    "營建": ["dio"],
}


def _get_industry_exclusions(industry: str | None) -> set[str]:
    if not industry:
        return set()
    excluded: set[str] = set()
    for kw, cids in INDUSTRY_EXCLUSIONS.items():
        if kw in industry:
            excluded.update(cids)
    return excluded


def _criterion(
    cid: str,
    label: str,
    weight: int,
    passed: bool | None,
    value: float | str | None,
    value_label: str,
    threshold: str,
    warning: str | None = None,
    not_applicable: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": cid,
        "label": label,
        "weight": weight,
        "pass": None if not_applicable else passed,
        "value": value,
        "value_label": value_label,
        "threshold": threshold,
        "warning": warning,
    }
    if not_applicable:
        result["not_applicable"] = True
    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_buy_score(
    stock_id: str,
    token: str | None = None,
    client: FinMindClient | None = None,
) -> dict[str, Any]:
    """買入評分卡（24 指標 + 排雷）。

    Raises FinMindError when FinMind quota is exhausted (HTTP 402) so the batch
    caller can pause and resume. Individual dataset failures (other than quota)
    are caught per-section and degrade the affected criteria to "無資料".
    """
    import time

    sid = stock_id.strip()
    if not sid:
        raise ValueError("stock_id is required")

    if client is None:
        client = FinMindClient(api_key=token)

    today = date.today()
    warnings: list[str] = []
    criteria: list[dict[str, Any]] = []

    # ── Industry classification (for not_applicable exclusions) ──────────────
    industry: str | None = None
    try:
        industry = client.fetch_stock_industry(sid)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"industry_fetch: {exc}")
    excluded_criteria = _get_industry_exclusions(industry)

    fetch_start_ext = date(today.year - 4, today.month, 1)

    # ── Shared data fetching ─────────────────────────────────────────────────
    ni_q: pd.Series = pd.Series(dtype=float)
    equity_s: pd.Series = pd.Series(dtype=float)
    assets_s: pd.Series = pd.Series(dtype=float)
    try:
        ni_q = client.fetch_quarterly_ni(sid, fetch_start_ext, today)
        time.sleep(_FETCH_DELAY)
        equity_s, assets_s = client.fetch_quarterly_bs_for_roe(sid, fetch_start_ext, today)
        time.sleep(_FETCH_DELAY)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"roe_data: {exc}")

    fcf_rows: list[dict[str, Any]] = []
    try:
        df_fcf, _ = client.fetch_annual_fcf_data(sid, fetch_start_ext, today)
        time.sleep(_FETCH_DELAY)
        if not df_fcf.empty:
            fcf_rows = df_fcf.to_dict("records")
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"fcf_data: {exc}")

    liabilities_s: pd.Series = pd.Series(dtype=float)
    assets_debt_s: pd.Series = pd.Series(dtype=float)
    try:
        liabilities_s, assets_debt_s = client.fetch_quarterly_bs_liabilities_assets(sid, fetch_start_ext, today)
        time.sleep(_FETCH_DELAY)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"debt_data: {exc}")

    score = 0

    # ── C1: ROE (TTM) > 12%  [weight=2] ──────────────────────────────────────
    latest_roe: float | None = None
    latest_roa: float | None = None
    try:
        if not ni_q.empty and not equity_s.empty and not assets_s.empty:
            roe_rows = _compute_roe_roa_ttm(
                ni_q, equity_s, assets_s,
                start_cutoff=pd.Timestamp(fetch_start_ext),
            )
            if roe_rows:
                latest_roe = roe_rows[-1].get("roe")
                latest_roa = roe_rows[-1].get("roa")
    except Exception as exc:
        warnings.append(f"roe_calc: {exc}")

    c1_pass = latest_roe is not None and latest_roe > 12.0
    if c1_pass:
        score += 2
    criteria.append(_criterion(
        "roe", "ROE (TTM) > 12%", weight=2,
        passed=c1_pass if latest_roe is not None else None,
        value=latest_roe,
        value_label=f"{latest_roe:.1f}%" if latest_roe is not None else "無資料",
        threshold="> 12%",
        warning=None if latest_roe is not None else "ROE 資料不足",
    ))

    c1b_pass = latest_roe is not None and latest_roe > 15.0
    criteria.append(_criterion(
        "roe_strict", "ROE (TTM) > 15%", weight=1,
        passed=c1b_pass if latest_roe is not None else None,
        value=latest_roe,
        value_label=f"{latest_roe:.1f}%" if latest_roe is not None else "無資料",
        threshold="> 15%",
        warning=None if latest_roe is not None else "ROE 資料不足",
    ))

    c1c_pass = latest_roa is not None and latest_roa > 6.0
    criteria.append(_criterion(
        "roa", "ROA (TTM) > 6%", weight=1,
        passed=c1c_pass if latest_roa is not None else None,
        value=latest_roa,
        value_label=f"{latest_roa:.1f}%" if latest_roa is not None else "無資料",
        threshold="> 6%",
        warning=None if latest_roa is not None else "ROA 資料不足",
    ))

    # ── C2: 近 3 年至少 2 年 FCF > 0  [weight=2] ──────────────────────────────
    fcf_years_positive = 0
    fcf_years_checked = 0
    recent_fcf: list[dict[str, Any]] = []
    try:
        start_year = today.year - 3
        recent_fcf = [r for r in fcf_rows if r.get("year", 0) >= start_year and r.get("fcf") is not None]
        fcf_years_checked = len(recent_fcf)
        fcf_years_positive = sum(1 for r in recent_fcf if float(r["fcf"]) > 0)
    except Exception as exc:
        warnings.append(f"fcf_check: {exc}")

    c2_pass = fcf_years_checked >= 2 and fcf_years_positive >= 2
    if c2_pass:
        score += 2
    criteria.append(_criterion(
        "fcf", "近3年至少2年自由現金流 > 0", weight=2,
        passed=c2_pass if fcf_years_checked > 0 else None,
        value=fcf_years_positive,
        value_label=f"{fcf_years_positive}/{fcf_years_checked} 年正值" if fcf_years_checked > 0 else "無資料",
        threshold="3年內至少2年 > 0",
        warning=None if fcf_years_checked > 0 else "FCF 資料不足",
    ))

    c2b_value: float | None = None
    c2c_value: float | None = None
    try:
        if recent_fcf:
            recent_fcf_sorted = sorted(recent_fcf, key=lambda r: int(r.get("year", 0)))
            c2b_value = float(recent_fcf_sorted[-1]["fcf"])
            if len(recent_fcf_sorted) >= 3:
                c2c_value = c2b_value - (
                    float(recent_fcf_sorted[-2]["fcf"]) + float(recent_fcf_sorted[-3]["fcf"])
                ) / 2
    except Exception as exc:
        warnings.append(f"fcf_extra: {exc}")

    criteria.append(_criterion(
        "fcf_latest", "最近一年 FCF > 0", weight=1,
        passed=(c2b_value > 0) if c2b_value is not None else None,
        value=c2b_value,
        value_label=f"{c2b_value:,.0f}" if c2b_value is not None else "無資料",
        threshold="> 0",
        warning=None if c2b_value is not None else "FCF 資料不足",
    ))
    criteria.append(_criterion(
        "fcf_trend", "最近一年 FCF 高於前2年平均", weight=1,
        passed=(c2c_value > 0) if c2c_value is not None else None,
        value=c2c_value,
        value_label=f"{c2c_value:+,.0f}" if c2c_value is not None else "無資料",
        threshold="最近年 > 前2年平均",
        warning=None if c2c_value is not None else "FCF 年度資料不足（需 3 年）",
    ))

    # ── C3: 負債比 < 60%  [weight=2] ──────────────────────────────────────────
    latest_debt_ratio: float | None = None
    try:
        if not assets_debt_s.empty and not liabilities_s.empty:
            q_dates = sorted(dt for dt in assets_debt_s.index if dt.month in {3, 6, 9, 12})
            if q_dates:
                dt = q_dates[-1]
                a_val = assets_debt_s.get(dt)
                l_val = liabilities_s.get(dt)
                if a_val and not pd.isna(a_val) and float(a_val) > 0 and l_val is not None and not pd.isna(l_val):
                    latest_debt_ratio = round(float(l_val) / float(a_val) * 100, 2)
    except Exception as exc:
        warnings.append(f"debt_calc: {exc}")

    c3_pass = latest_debt_ratio is not None and latest_debt_ratio < 60.0
    criteria.append(_criterion(
        "debt_ratio", "負債比 < 60%", weight=2,
        passed=c3_pass if latest_debt_ratio is not None else None,
        value=latest_debt_ratio,
        value_label=f"{latest_debt_ratio:.1f}%" if latest_debt_ratio is not None else "無資料",
        threshold="< 60%",
        warning=None if latest_debt_ratio is not None else "負債比資料不足",
        not_applicable="debt_ratio" in excluded_criteria,
    ))
    criteria.append(_criterion(
        "debt_ratio_strict", "負債比 < 50%", weight=1,
        passed=(latest_debt_ratio < 50.0) if latest_debt_ratio is not None else None,
        value=latest_debt_ratio,
        value_label=f"{latest_debt_ratio:.1f}%" if latest_debt_ratio is not None else "無資料",
        threshold="< 50%",
        warning=None if latest_debt_ratio is not None else "負債比資料不足",
        not_applicable="debt_ratio_strict" in excluded_criteria,
    ))
    equity_ratio = (100.0 - latest_debt_ratio) if latest_debt_ratio is not None else None
    criteria.append(_criterion(
        "equity_ratio", "股東權益比 > 40%", weight=1,
        passed=(equity_ratio > 40.0) if equity_ratio is not None else None,
        value=equity_ratio,
        value_label=f"{equity_ratio:.1f}%" if equity_ratio is not None else "無資料",
        threshold="> 40%",
        warning=None if equity_ratio is not None else "資產負債資料不足",
        not_applicable="equity_ratio" in excluded_criteria,
    ))

    # ── C4: 月營收 YoY 3個月中至少2個月 > 0%  [weight=1] ──────────────────────
    rev_positive = 0
    rev_yoy_values: list[float] = []
    try:
        time.sleep(_FETCH_DELAY)
        fetch_rev_start = date(today.year - 2, today.month, 1)
        df_rev = client.fetch_month_revenue(sid, fetch_rev_start, today)
        if not df_rev.empty and len(df_rev) >= 15:
            df_rev = df_rev.sort_values("month").reset_index(drop=True)
            df_rev["revenue"] = pd.to_numeric(df_rev["revenue"], errors="coerce")
            df_rev["yoy"] = (df_rev["revenue"] / df_rev["revenue"].shift(12) - 1) * 100
            recent = df_rev.dropna(subset=["yoy"]).tail(3)
            rev_yoy_values = [round(float(v), 1) for v in recent["yoy"] if not pd.isna(v)]
            rev_positive = sum(1 for v in rev_yoy_values if v > 0)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"revenue_yoy: {exc}")

    c4_pass = rev_positive >= 2
    if c4_pass:
        score += 1
    yoy_str = " / ".join(f"{v:+.1f}%" for v in rev_yoy_values) if rev_yoy_values else "無資料"
    criteria.append(_criterion(
        "revenue_yoy", "月營收年增率 3個月中至少2個月 > 0%", weight=1,
        passed=c4_pass if rev_yoy_values else None,
        value=rev_positive,
        value_label=yoy_str,
        threshold="3個月中 ≥ 2個月 > 0%",
        warning=None if rev_yoy_values else "營收資料不足（需 15 個月以上）",
    ))

    rev_avg = round(sum(rev_yoy_values) / len(rev_yoy_values), 1) if rev_yoy_values else None
    rev_latest = rev_yoy_values[-1] if rev_yoy_values else None
    criteria.append(_criterion(
        "revenue_yoy_avg", "月營收 YoY 近3個月平均 > 5%", weight=1,
        passed=(rev_avg > 5.0) if rev_avg is not None else None,
        value=rev_avg,
        value_label=f"{rev_avg:+.1f}%" if rev_avg is not None else "無資料",
        threshold="> 5%",
        warning=None if rev_avg is not None else "營收資料不足",
    ))
    criteria.append(_criterion(
        "revenue_yoy_latest", "月營收 YoY 最新值 > 0%", weight=1,
        passed=(rev_latest > 0) if rev_latest is not None else None,
        value=rev_latest,
        value_label=f"{rev_latest:+.1f}%" if rev_latest is not None else "無資料",
        threshold="> 0%",
        warning=None if rev_latest is not None else "營收資料不足",
    ))

    # ── C5: EPS YoY 3季中至少2季 > 0%  [weight=1] ─────────────────────────────
    eps_positive = 0
    eps_yoy_values: list[float] = []
    df_eps: pd.DataFrame = pd.DataFrame()
    try:
        time.sleep(_FETCH_DELAY)
        df_eps = client.fetch_eps_trend(sid, fetch_start_ext, today)
        if not df_eps.empty:
            recent_eps = df_eps.dropna(subset=["eps_yoy"]).tail(3)
            eps_yoy_values = [round(float(v), 1) for v in recent_eps["eps_yoy"] if not pd.isna(v)]
            eps_positive = sum(1 for v in eps_yoy_values if v > 0)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"eps_yoy: {exc}")

    c5_pass = eps_positive >= 2
    if c5_pass:
        score += 1
    eps_str = " / ".join(f"{v:+.1f}%" for v in eps_yoy_values) if eps_yoy_values else "無資料"
    criteria.append(_criterion(
        "eps_yoy", "EPS YoY 3季中至少2季正成長", weight=1,
        passed=c5_pass if eps_yoy_values else None,
        value=eps_positive,
        value_label=eps_str,
        threshold="3季中 ≥ 2季 YoY > 0%",
        warning=None if eps_yoy_values else "EPS 資料不足",
    ))

    eps_avg = round(sum(eps_yoy_values) / len(eps_yoy_values), 1) if eps_yoy_values else None
    eps_latest = eps_yoy_values[-1] if eps_yoy_values else None
    criteria.append(_criterion(
        "eps_yoy_avg", "EPS YoY 近3季平均 > 5%", weight=1,
        passed=(eps_avg > 5.0) if eps_avg is not None else None,
        value=eps_avg,
        value_label=f"{eps_avg:+.1f}%" if eps_avg is not None else "無資料",
        threshold="> 5%",
        warning=None if eps_avg is not None else "EPS 資料不足",
    ))
    criteria.append(_criterion(
        "eps_yoy_latest", "EPS YoY 最新值 > 0%", weight=1,
        passed=(eps_latest > 0) if eps_latest is not None else None,
        value=eps_latest,
        value_label=f"{eps_latest:+.1f}%" if eps_latest is not None else "無資料",
        threshold="> 0%",
        warning=None if eps_latest is not None else "EPS 資料不足",
    ))

    # ── C6: |Sloan Ratio| < 0.15  [weight=1] ──────────────────────────────────
    sloan: float | None = None
    try:
        if not ni_q.empty and not assets_s.empty and fcf_rows:
            latest_year = today.year - 1
            annual_ni = sum(
                float(v) for dt, v in ni_q.items()
                if dt.year == latest_year and not pd.isna(v)
            )
            opcf_rows = [r for r in fcf_rows if r.get("year") == latest_year and r.get("operating_cf") is not None]
            if opcf_rows and annual_ni != 0:
                opcf = float(opcf_rows[0]["operating_cf"])
                asset_dates = sorted(dt for dt in assets_s.index if dt.year in {latest_year - 1, latest_year} and dt.month == 12)
                if len(asset_dates) >= 2:
                    avg_assets = (float(assets_s[asset_dates[0]]) + float(assets_s[asset_dates[-1]])) / 2
                elif asset_dates:
                    avg_assets = float(assets_s[asset_dates[-1]])
                else:
                    avg_assets = 0.0
                sloan = compute_sloan_ratio(annual_ni, opcf, avg_assets)
    except Exception as exc:
        warnings.append(f"sloan_ratio: {exc}")

    c6_pass = sloan is not None and abs(sloan) < 0.15
    if c6_pass:
        score += 1
    criteria.append(_criterion(
        "sloan_ratio", "|盈餘品質 Sloan Ratio| < 0.15", weight=1,
        passed=c6_pass if sloan is not None else None,
        value=round(sloan, 4) if sloan is not None else None,
        value_label=f"{sloan:.4f}" if sloan is not None else "無資料",
        threshold="< 0.15（絕對值）",
        warning=None if sloan is not None else "現金流或資產資料不足",
    ))

    # ── C7: 毛利率 / 營益率 / 淨利率近4季均值 ≥ 前4季均值  [weight=1 each] ─────
    gm_recent_avg = gm_prior_avg = None
    op_recent_avg = op_prior_avg = None
    nm_recent_avg = nm_prior_avg = None
    df_margins = pd.DataFrame()
    try:
        time.sleep(_FETCH_DELAY)
        df_margins = client.fetch_margin_ratios(sid, fetch_start_ext, today)
        if not df_margins.empty:
            valid_gm = df_margins.dropna(subset=["gross_margin"]).sort_values("quarter")
            if len(valid_gm) >= 8:
                recent4 = valid_gm.tail(4)["gross_margin"].tolist()
                prior4 = valid_gm.iloc[-8:-4]["gross_margin"].tolist()
                gm_recent_avg = round(sum(recent4) / len(recent4), 2)
                gm_prior_avg = round(sum(prior4) / len(prior4), 2)

            valid_op = df_margins.dropna(subset=["operating_margin"]).sort_values("quarter")
            if len(valid_op) >= 8:
                op_recent_avg = round(float(valid_op.tail(4)["operating_margin"].mean()), 2)
                op_prior_avg = round(float(valid_op.iloc[-8:-4]["operating_margin"].mean()), 2)

            valid_nm = df_margins.dropna(subset=["net_margin"]).sort_values("quarter")
            if len(valid_nm) >= 8:
                nm_recent_avg = round(float(valid_nm.tail(4)["net_margin"].mean()), 2)
                nm_prior_avg = round(float(valid_nm.iloc[-8:-4]["net_margin"].mean()), 2)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"gross_margin: {exc}")

    c7_pass = gm_recent_avg is not None and gm_prior_avg is not None and gm_recent_avg >= gm_prior_avg
    if c7_pass:
        score += 1
    gm_label = (
        f"近4Q {gm_recent_avg:.1f}% vs 前4Q {gm_prior_avg:.1f}%"
        if gm_recent_avg is not None and gm_prior_avg is not None else "無資料（需 8 季以上）"
    )
    criteria.append(_criterion(
        "gross_margin", "毛利率近4季均值 ≥ 前4季均值", weight=1,
        passed=c7_pass if gm_recent_avg is not None else None,
        value=gm_recent_avg, value_label=gm_label,
        threshold="近4Q avg ≥ 前4Q avg",
        warning=None if gm_recent_avg is not None else "毛利率資料不足（需 8 季）",
    ))
    criteria.append(_criterion(
        "operating_margin", "營業利益率近4季均值 ≥ 前4季均值", weight=1,
        passed=(op_recent_avg >= op_prior_avg) if op_recent_avg is not None and op_prior_avg is not None else None,
        value=op_recent_avg,
        value_label=(f"近4Q {op_recent_avg:.1f}% vs 前4Q {op_prior_avg:.1f}%" if op_recent_avg is not None and op_prior_avg is not None else "無資料"),
        threshold="近4Q avg ≥ 前4Q avg",
        warning=None if op_recent_avg is not None and op_prior_avg is not None else "營業利益率資料不足（需 8 季）",
    ))
    criteria.append(_criterion(
        "net_margin", "淨利率近4季均值 ≥ 前4季均值", weight=1,
        passed=(nm_recent_avg >= nm_prior_avg) if nm_recent_avg is not None and nm_prior_avg is not None else None,
        value=nm_recent_avg,
        value_label=(f"近4Q {nm_recent_avg:.1f}% vs 前4Q {nm_prior_avg:.1f}%" if nm_recent_avg is not None and nm_prior_avg is not None else "無資料"),
        threshold="近4Q avg ≥ 前4Q avg",
        warning=None if nm_recent_avg is not None and nm_prior_avg is not None else "淨利率資料不足（需 8 季）",
    ))

    # ── C8: 法人近10日/5日累計買超 > 0  [weight=1 each] ───────────────────────
    inst_10d_net: float | None = None
    inst_5d_net: float | None = None
    try:
        time.sleep(_FETCH_DELAY)
        inst_start = date(today.year, today.month, 1) - pd.DateOffset(months=1)
        inst_start_date = date(int(inst_start.year), int(inst_start.month), int(inst_start.day))
        df_inst = client.fetch_institutional_investors_buy_sell(sid, inst_start_date, today)
        if not df_inst.empty:
            relevant = df_inst[df_inst["name"].isin(["Foreign_Investor", "Investment_Trust"])]
            if not relevant.empty:
                daily_net = relevant.groupby("date")["net"].sum().sort_index()
                inst_10d_net = float(daily_net.tail(10).sum())
                inst_5d_net = float(daily_net.tail(5).sum())
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"inst_buy: {exc}")

    c8_pass = inst_10d_net is not None and inst_10d_net > 0
    if c8_pass:
        score += 1
    criteria.append(_criterion(
        "inst_buy", "法人近10日累計買超 > 0", weight=1,
        passed=c8_pass if inst_10d_net is not None else None,
        value=inst_10d_net,
        value_label=f"{inst_10d_net:+,.0f} 張" if inst_10d_net is not None else "無資料",
        threshold="外資+投信 10日合計 > 0",
        warning=None if inst_10d_net is not None else "法人資料無法取得",
    ))
    criteria.append(_criterion(
        "inst_buy_5d", "法人近5日累計買超 > 0", weight=1,
        passed=(inst_5d_net > 0) if inst_5d_net is not None else None,
        value=inst_5d_net,
        value_label=f"{inst_5d_net:+,.0f} 張" if inst_5d_net is not None else "無資料",
        threshold="外資+投信 5日合計 > 0",
        warning=None if inst_5d_net is not None else "法人資料無法取得",
    ))

    # ── C9: 目前P/E < 歷史中位數 / p25（近5年）  [weight=1 each] ──────────────
    current_per: float | None = None
    per_median: float | None = None
    per_p25: float | None = None
    try:
        time.sleep(_FETCH_DELAY)
        per_start = date(today.year - 5, today.month, 1)
        df_per = client.fetch_stock_per(sid, per_start, today)
        if not df_per.empty and "PER" in df_per.columns:
            valid_per = df_per[df_per["PER"].notna() & (df_per["PER"] > 0)].sort_values("date")
            if not valid_per.empty:
                current_per = float(valid_per.iloc[-1]["PER"])
                per_median = float(valid_per["PER"].median())
                per_p25 = float(valid_per["PER"].quantile(0.25))
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"pe_median: {exc}")

    c9_pass = current_per is not None and per_median is not None and current_per < per_median
    if c9_pass:
        score += 1
    per_label = (
        f"現值 {current_per:.1f}x vs 中位數 {per_median:.1f}x"
        if current_per is not None and per_median is not None else "無資料"
    )
    criteria.append(_criterion(
        "pe_median", "目前P/E < 歷史中位數（近5年）", weight=1,
        passed=c9_pass if current_per is not None else None,
        value=current_per, value_label=per_label,
        threshold="< p50 歷史中位數",
        warning=None if current_per is not None else "P/E 資料無法取得",
    ))
    criteria.append(_criterion(
        "pe_p25", "目前P/E < 歷史 25 分位數（近5年）", weight=1,
        passed=(current_per < per_p25) if current_per is not None and per_p25 is not None else None,
        value=current_per,
        value_label=(f"現值 {current_per:.1f}x vs p25 {per_p25:.1f}x" if current_per is not None and per_p25 is not None else "無資料"),
        threshold="< p25",
        warning=None if current_per is not None and per_p25 is not None else "P/E 資料無法取得",
    ))

    # ── C10: 外資持股3個月整體淨增  [weight=1]  (Goodinfo — opt-in) ───────────
    foreign_trend: list[float] = []
    df_sh: pd.DataFrame = pd.DataFrame()
    if GoodinfoClient is not None:
        try:
            gc = GoodinfoClient()
            df_sh = gc.fetch_shareholding_history(sid)
            if not df_sh.empty and "foreign_ratio" in df_sh.columns:
                df_sh = df_sh.copy()
                df_sh["date"] = pd.to_datetime(df_sh["date"], errors="coerce")
                df_sh = df_sh.dropna(subset=["date", "foreign_ratio"]).sort_values("date")
                df_sh["foreign_ratio"] = pd.to_numeric(df_sh["foreign_ratio"], errors="coerce")
                df_sh = df_sh.dropna(subset=["foreign_ratio"])
                recent3 = df_sh.tail(3)
                foreign_trend = [round(float(v), 2) for v in recent3["foreign_ratio"]]
        except Exception as exc:
            warnings.append(f"foreign_holding: {exc}")
    else:
        warnings.append("foreign_holding: Goodinfo 已停用（BUY_SCORE_GOODINFO_ENABLED）")

    c10_pass = len(foreign_trend) >= 2 and foreign_trend[-1] > foreign_trend[0]
    if c10_pass:
        score += 1
    fh_label = " → ".join(f"{v:.1f}%" for v in foreign_trend) if foreign_trend else "無資料"
    criteria.append(_criterion(
        "foreign_holding", "外資持股3個月整體淨增", weight=1,
        passed=c10_pass if foreign_trend else None,
        value=foreign_trend[-1] if foreign_trend else None,
        value_label=fh_label,
        threshold="近3個月整體上升（最新 > 最早）",
        warning=None if foreign_trend else "外資持股資料無法取得",
    ))

    # ── Scoring: not_applicable criteria excluded from pass_rate ──────────────
    passed_count = sum(1 for c in criteria if c.get("pass") is True)
    eligible_count = sum(1 for c in criteria if c.get("pass") is not None)
    score = passed_count
    max_score = len(criteria)
    pass_rate = round((passed_count / eligible_count) * 100, 1) if eligible_count > 0 else 0.0

    if pass_rate >= 75.0:
        recommendation, recommendation_label = "recommended_buy", "建議買進"
        signal, signal_label = "strong_buy", "建議買進"
    elif pass_rate >= 60.0:
        recommendation, recommendation_label = "scale_in", "可分批買進"
        signal, signal_label = "buy", "可分批買進"
    elif pass_rate >= 50.0:
        recommendation, recommendation_label = "watchlist", "觀察清單"
        signal, signal_label = "watch", "觀察清單"
    else:
        recommendation, recommendation_label = "not_recommended", "不建議買進"
        signal, signal_label = "neutral", "不建議買進"

    # ── Risk avoidance (排雷指標) ─────────────────────────────────────────────
    spread_df = pd.DataFrame()
    inv_data: dict[str, float] | None = None
    try:
        time.sleep(_FETCH_DELAY)
        spread_df = client.fetch_shareholding_spread(sid, fetch_start_ext, today)
    except FinMindError:
        raise
    except Exception as exc:
        _exc_msg = str(exc).lower()
        if "level is register" not in _exc_msg and "sponsor" not in _exc_msg and "user level" not in _exc_msg:
            warnings.append(f"shareholding_spread: {exc}")
    try:
        time.sleep(_FETCH_DELAY)
        inv_data = client.fetch_inventory_and_revenue_growth(sid, fetch_start_ext, today)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"inventory_growth: {exc}")

    liq_df_risk: pd.DataFrame = pd.DataFrame()
    try:
        time.sleep(_FETCH_DELAY)
        liq_df_risk = client.fetch_liquidity_ratios(sid, fetch_start_ext, today)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"liq_ratios_risk: {exc}")

    is_df_risk: pd.DataFrame = pd.DataFrame()
    try:
        time.sleep(_FETCH_DELAY)
        is_df_risk = client.fetch_financial_statements(sid, fetch_start_ext, today)
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"is_data_risk: {exc}")

    risk_criteria: list[dict[str, Any]] = []

    # 籌碼排雷：散戶增、大戶減
    if not spread_df.empty:
        try:
            latest_date = spread_df["date"].max()
            past_date = spread_df["date"].drop_duplicates().sort_values().iloc[-4] if len(spread_df["date"].unique()) >= 4 else spread_df["date"].min()
            whales = spread_df[spread_df["HoldingSharesLevel"] == "15"]
            wh_latest = whales[whales["date"] == latest_date]["percent"].sum() if not whales.empty else 0
            wh_past = whales[whales["date"] == past_date]["percent"].sum() if not whales.empty else 0
            retail = spread_df[spread_df["HoldingSharesLevel"].astype(int) <= 9]
            ret_latest = retail[retail["date"] == latest_date]["percent"].sum() if not retail.empty else 0
            ret_past = retail[retail["date"] == past_date]["percent"].sum() if not retail.empty else 0
            if (wh_past - wh_latest > 2.0) and (ret_latest > ret_past):
                risk_criteria.append({
                    "category": "籌碼排雷", "name": "千張大戶退場", "status": "warning",
                    "value_label": f"大戶 -{(wh_past - wh_latest):.1f}%",
                    "description": "大戶跑給散戶接，籌碼明顯凌亂",
                })
        except Exception:
            pass

    # 存貨異常排雷
    if inv_data is not None:
        try:
            inv_y = inv_data.get("inv_yoy", 0)
            rev_y = inv_data.get("rev_yoy", 0)
            if inv_y > 20 and (inv_y - rev_y > 20):
                risk_criteria.append({
                    "category": "存貨排雷", "name": "存貨飆升去化慢", "status": "warning",
                    "value_label": f"存貨 YoY {inv_y:.1f}%",
                    "description": f"存貨成長遠大於營收({rev_y:.1f}%)，恐面臨跌價損失風險",
                })
        except Exception:
            pass

    # 獲利排雷：FCF 轉負
    if c2b_value is not None and c2b_value < 0:
        risk_criteria.append({
            "category": "獲利排雷", "name": "自由現金流轉負", "status": "warning",
            "value_label": f"FCF = {c2b_value:.2f}",
            "description": "帳面有獲利但無現金流入，需注意應收帳款與存貨壓力",
        })

    # 估值排雷：PE 過高
    if per_median is not None and current_per is not None:
        try:
            if current_per > (per_median * 1.5):
                risk_criteria.append({
                    "category": "估值排雷", "name": "本益比過高", "status": "warning",
                    "value_label": f"PE {current_per:.1f} > Avg*1.5",
                    "description": "當前估值偏離歷史均值過大，應避免追高",
                })
        except Exception:
            pass

    # 品質排雷：Sloan 極差
    if sloan is not None and sloan > 0.25:
        risk_criteria.append({
            "category": "品質排雷", "name": "盈餘品質極度惡化", "status": "warning",
            "value_label": f"Sloan Ratio {sloan:.2f}",
            "description": "淨收益大幅來自非現金項目，虛盈實虧風險高",
        })

    # 配息陷阱：Payout > 100%
    payout_ratio_pct: float | None = None
    try:
        payout_ratio_raw = client.fetch_dividend_payout_ratio(sid, fetch_start_ext, today, years=5)
        if payout_ratio_raw is not None:
            payout_ratio_pct = float(payout_ratio_raw)
            if payout_ratio_pct <= 1.0:
                payout_ratio_pct *= 100.0
    except FinMindError:
        raise
    except Exception as exc:
        warnings.append(f"payout_ratio: {exc}")

    if payout_ratio_pct is not None and payout_ratio_pct > 100:
        risk_criteria.append({
            "category": "配息排雷", "name": "配發率超標", "status": "warning",
            "value_label": f"Payout {payout_ratio_pct:.1f}%",
            "description": "發放股利超過當期獲利，可能在消耗老本",
        })

    # R4: 連續虧損
    if not df_eps.empty:
        try:
            recent4 = df_eps.dropna(subset=["eps"]).sort_values("quarter").tail(4)
            negative_q = sum(1 for _, row in recent4.iterrows() if row["eps"] is not None and float(row["eps"]) < 0)
            if negative_q >= 2:
                risk_criteria.append({
                    "category": "財務惡化", "name": "連續虧損", "status": "warning",
                    "value_label": f"近4季 {negative_q} 季虧損",
                    "description": "近4季中2季以上EPS為負，獲利能力存疑",
                })
        except Exception:
            pass

    # R5: 淨值低於票面
    if not liq_df_risk.empty:
        try:
            valid_bvps = liq_df_risk[liq_df_risk["bvps"].notna()].sort_values("quarter")
            if not valid_bvps.empty:
                latest_bvps_r = float(valid_bvps.iloc[-1]["bvps"])
                if latest_bvps_r < 10.0:
                    risk_criteria.append({
                        "category": "財務惡化", "name": "淨值低於票面", "status": "warning",
                        "value_label": f"BVPS {latest_bvps_r:.2f} < 10",
                        "description": "每股淨值低於票面10元，資本侵蝕風險高",
                    })
        except Exception:
            pass

    # R6: 利息保障倍數不足
    if not is_df_risk.empty:
        try:
            def _get_latest_annual(df: pd.DataFrame, type_names: list[str]) -> float | None:
                for t in type_names:
                    sub = df[df["type"] == t].copy()
                    if sub.empty:
                        continue
                    sub["date"] = pd.to_datetime(sub["date"])
                    sub["year"] = sub["date"].dt.year
                    latest_year = sub["year"].max()
                    year_data = sub[sub["year"] == latest_year]
                    q4 = year_data[year_data["date"].dt.month == 12]
                    if not q4.empty:
                        return float(q4.sort_values("date").iloc[-1]["value"])
                    return float(year_data.sort_values("date").iloc[-1]["value"])
                return None

            op_inc = _get_latest_annual(is_df_risk, ["OperatingIncome", "ProfitFromOperations", "OperatingProfitLoss"])
            int_exp = _get_latest_annual(is_df_risk, ["FinanceCosts", "InterestExpenses", "InterestExpense", "FinancingCosts"])
            if op_inc is not None and int_exp is not None and abs(int_exp) > 0:
                coverage = op_inc / abs(int_exp)
                if coverage < 2.0:
                    risk_criteria.append({
                        "category": "財務惡化", "name": "利息保障倍數不足", "status": "warning",
                        "value_label": f"ICR {coverage:.1f}x",
                        "description": "營業利益不足支應利息費用兩倍，財務壓力大",
                    })
        except Exception:
            pass

    # R7: 董監質押比過高 (Goodinfo — opt-in)
    if not df_sh.empty and "total_dir_pledged" in df_sh.columns and "total_dir_shares" in df_sh.columns:
        try:
            df_sh_sorted = df_sh.dropna(subset=["total_dir_pledged", "total_dir_shares"]).sort_values("date")
            if not df_sh_sorted.empty:
                latest_row = df_sh_sorted.iloc[-1]
                pledged = float(latest_row["total_dir_pledged"])
                total = float(latest_row["total_dir_shares"])
                if total > 0:
                    pledge_ratio = pledged / total * 100
                    if pledge_ratio > 50.0:
                        risk_criteria.append({
                            "category": "籌碼治理", "name": "董監質押比過高", "status": "warning",
                            "value_label": f"質押比 {pledge_ratio:.1f}%",
                            "description": "全體董監事質押超過自身持股半數，股價下跌恐觸發強制賣出",
                        })
        except Exception:
            pass

    # R8: 毛利率/營益率連3季惡化
    if not df_margins.empty:
        try:
            for metric_col, metric_name, direction in [
                ("gross_margin", "毛利率", "down"),
                ("operating_margin", "營業利益率", "down"),
            ]:
                valid_m = df_margins.dropna(subset=[metric_col]).sort_values("quarter")
                if len(valid_m) >= 3:
                    last3 = valid_m.tail(3)[metric_col].tolist()
                    if direction == "down" and last3[0] > last3[1] > last3[2]:
                        risk_criteria.append({
                            "category": "財務惡化", "name": f"{metric_name}趨勢惡化", "status": "warning",
                            "value_label": f"連3季下滑至 {last3[-1]:.1f}%",
                            "description": f"{metric_name}連續3季單向下滑，盈利能力持續走弱",
                        })
        except Exception:
            pass

    # R8b: 負債比連3季上升
    if not liabilities_s.empty and not assets_debt_s.empty:
        try:
            q_dates = sorted(dt for dt in assets_debt_s.index if dt.month in {3, 6, 9, 12})[-5:]
            debt_ratios = []
            for dt in q_dates:
                a_val = assets_debt_s.get(dt)
                l_val = liabilities_s.get(dt)
                if a_val and not pd.isna(a_val) and float(a_val) > 0 and l_val is not None and not pd.isna(l_val):
                    debt_ratios.append(round(float(l_val) / float(a_val) * 100, 2))
            if len(debt_ratios) >= 3 and debt_ratios[-3] < debt_ratios[-2] < debt_ratios[-1]:
                risk_criteria.append({
                    "category": "財務惡化", "name": "負債比趨勢惡化", "status": "warning",
                    "value_label": f"連3季攀升至 {debt_ratios[-1]:.1f}%",
                    "description": "負債比連續3季上升，財務槓桿持續擴大",
                })
        except Exception:
            pass

    risk_score = len(risk_criteria)
    if risk_score >= 2:
        recommendation, recommendation_label = "not_recommended", "高風險避開"
        signal, signal_label = "neutral", "高風險避開"

    return {
        "stock_id": sid,
        "industry": industry,
        "score": score,
        "max_score": max_score,
        "eligible_count": eligible_count,
        "pass_rate": pass_rate,
        "recommendation": recommendation,
        "recommendation_label": recommendation_label,
        "signal": signal,
        "signal_label": signal_label,
        "criteria": criteria,
        "warnings": warnings,
        "risk_criteria": risk_criteria,
        "risk_score": risk_score,
    }
