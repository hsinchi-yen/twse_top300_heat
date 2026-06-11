# PLAN.md — Current Implementation Snapshot

> Updated: 2026-06-11
> Scope: active implementation, not the original MVP plan

## Implemented

1. Stock dashboard
   - Frontend always loads `/api/stocks/top100?mode=volume&limit=480`
   - `turnover` and `buy_score` views are client-side reorderings over the same 480-stock display pool
   - Paging supports desktop (`6x6`, `5x5`, `4x4`) and mobile (`2x2`, `2x3`, `3x3`)

2. Data ingestion
   - Stock crawler merges TWSE + TPEX + FinMind issue shares
   - Yahoo Finance is used as an intraday fallback when TWSE data is stale
   - ETF crawler is split out as its own container and endpoint

3. Buy-score pipeline
   - Score computation is native in `crawler/sources/buy_score_engine.py`
   - Monthly batch at `03:00` on day `1`
   - Force refresh uses shared flag files, partial writes, quota-aware resume, and atomic cache replacement

4. Embedded deployment
   - Production uses `run_containers.sh` and `--network host`
   - Runtime shape is four containers: backend, crawler, etf-crawler, frontend
   - Logs rotate with `json-file` driver

5. Data-retention and stability
   - `stock_ranks`: keep 7 trading dates
   - `etf_ranks`: keep `ETF_KEEP_DAYS` trading dates, default `90`
   - `buy_scores/*.json`: keep latest 7 files
   - Daily WAL checkpoint and monthly VACUUM

## Current backlog

1. Add richer runtime metrics export for score coverage, retry count, and quota waits
2. Add broader automated tests around storage-watermark behavior and startup recovery
3. Consider making stock retention days configurable if production data growth requires it
4. Tighten `updated_at` semantics if consumers need source snapshot time instead of response time

## Intentionally retired assumptions

- No external `StockAnalysisDashBoard` dependency remains in the score path
- No frontend stock-mode API switching is required for `turnover`
- No `Top 100` or `Top 360` display-pool contract remains; the current stock display pool is `480`
