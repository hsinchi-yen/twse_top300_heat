# 買進評分實作現況

> Updated: 2026-06-11
> Replaces the older `STOCK_ANALYSIS_URL`-based troubleshooting note

## Current architecture

買進評分現在完全由 `crawler/` 原生計算，不再依賴外部 `StockAnalysisDashBoard` 或 `STOCK_ANALYSIS_URL`。

實際流程：

```text
Frontend ScoreRefreshBtn
  -> GET /api/scores?force=true
  -> backend writes buy_scores/.force_refresh
  -> crawler force_refresh_watch_job() detects flag
  -> crawler score_job(force=True)
  -> buy_score_engine.compute_buy_score() direct to FinMind
  -> partial JSON writes (.tmp -> rename)
  -> frontend polls /api/scores and picks up progress
```

## Runtime requirements

| Requirement | Current source of truth |
|---|---|
| Score engine | `crawler/sources/buy_score_engine.py` |
| Batch coordinator | `crawler/sources/buy_score.py` |
| Schedule | `crawler/main.py::score_job` monthly on day `1` at `03:00` |
| Shared cache dir | `SCORES_DIR` (default `/app/data/buy_scores`) |
| Token | `FINMIND_TOKEN` on the crawler container only |
| Force-refresh signal | `.force_refresh` / `.scoring_in_progress` |

## Key behavior

- Backend does not compute scores; it only serves the newest JSON and reports `fetching`
- Force refresh is non-blocking
- Current cache is never deleted first; writes are always `.tmp -> rename`
- Partial progress is flushed every 50 successful scores
- FinMind quota exhaustion pauses for `BUY_SCORE_QUOTA_WAIT_S` and resumes only missing symbols
- `eligible_count == 0` is treated as no data and is not persisted as misleading `0/24`

## Deployment checklist

1. Backend and crawler must share the same `/app/data` volume
2. Crawler must receive `FINMIND_TOKEN`
3. Both containers must agree on `SCORES_DIR`
4. Production should be started through `run_containers.sh` to keep container wiring consistent

## Operational checks

```bash
# Backend contract
curl http://localhost:8000/api/scores

# Force refresh
curl "http://localhost:8000/api/scores?force=true"

# Watch crawler progress
docker logs -f twse-crawler

# Inspect generated cache files
ls -la /root/TWSE_TOP100_HEAT/data/buy_scores/
```
