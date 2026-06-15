# CLAUDE.md — Twse_Top100_Heat

## What This Project Is

台股熱力圖 Dashboard。現行產品由三個主要視圖組成：
- 股票成交量 / 週轉率 / 買進評分，共用同一個 `600` 檔股票顯示池
- ETF 視圖，獨立走 `/api/etf`
- 買進評分由 crawler 原生計算，backend 只負責讀共享 JSON 與協調 force refresh

技術棧：Vue 3 + FastAPI + SQLite + APScheduler，部署於 Yocto ARM64 嵌入式 Linux，目標是 365x24 長時間運行。

## Key Architecture Decisions

- Display pool: frontend 股票頁永遠請求 `/api/stocks/top100?mode=volume&limit=600`
- Turnover / buy-score ordering: 都在前端對同一批 600 檔資料重排，不切換股票 API query
- ETF mode: 走 `/api/etf?sort_by=turnover|asset_scale&limit=300`
- Score candidate pool: `volume_rank <= SCORE_CANDIDATE_LIMIT`，預設 `600`，硬上限 `1000`
- Score engine: `crawler/sources/buy_score_engine.py::compute_buy_score` 原生直連 FinMind，不再依賴外部評分服務
- Score schedule: 每月 1 日 `03:00`
- Quota resume: FinMind 額度耗盡時寫 partial，等待 `BUY_SCORE_QUOTA_WAIT_S` 後只續抓未完成者
- Force refresh: backend 寫 `buy_scores/.force_refresh`；crawler 每分鐘偵測並執行 `score_job(force=True)`
- Stale-flag recovery: 旗標超過 `SCORING_FLAG_STALE_S`（預設 3h）視為 crash 殘留，backend 不再計入 `fetching`、crawler 自動清除，避免按鈕永久卡死
- Atomic cache writes: 評分 JSON 一律 `.tmp -> rename`，不得 delete-then-write
- No misleading zeroes: `eligible_count == 0` 時不落地 `0/24`，前端顯示 `N/A`
- Polling: 股票盤中 `60s`、盤後 `5min`；ETF 目前盤中 / 盤後都維持 `60s` 輪詢
- Deployment: Yocto production 使用 `run_containers.sh` + `--network host`，共四個容器

## Test Commands

```bash
# Backend
cd backend && pytest -v

# Crawler buy score path
cd crawler && pytest tests/test_buy_score_source.py tests/test_buy_score_engine.py -v

# Frontend
cd frontend && npm run test
```

## Critical Rules

1. `FINMIND_TOKEN` 只給 crawler；backend `GET /api/scores` 不應自行計分
2. `X-FinMind-Token` header 可被前端送出，但目前 backend 會忽略它；不要再把 token 放進 query string 或 log
3. Frontend 股票主畫面固定用 `mode=volume&limit=600`
4. 週轉率 / 買進評分都是前端排序行為，不要把它們改回股票 API 的不同抓法
5. 強制刷新不能先刪舊檔；必須維持舊資料可讀直到新檔原子替換
6. `ALLOWED_ORIGINS` 由 env 控制；不要在程式碼裡寫死特定來源
7. API contract 若變更，先改 `SPEC.md`，再補測試，再改實作

## Important Environment Variables

| Variable | Purpose |
|---|---|
| `FINMIND_TOKEN` | Crawler buy-score engine token |
| `SCORES_DIR` | Buy-score JSON directory |
| `SCORE_CANDIDATE_LIMIT` | Buy-score candidate pool limit |
| `BUY_SCORE_REQUEST_DELAY` | Delay between stocks during score batch |
| `BUY_SCORE_FETCH_DELAY` | Delay between FinMind datasets inside score engine |
| `BUY_SCORE_QUOTA_WAIT_S` | Wait time after quota exhaustion |
| `BUY_SCORE_QUOTA_MAX_CYCLES` | Legacy bound; quota-resume currently loops without an enforced upper limit |
| `SCORING_FLAG_STALE_S` | Age after which `.scoring_in_progress` / `.force_refresh` are treated as orphaned and cleared (default `10800`) |
| `BUY_SCORE_GOODINFO_ENABLED` | Optional Goodinfo crawler toggle |
| `ETF_KEEP_DAYS` | ETF history retention |
| `ALLOWED_ORIGINS` | Backend CORS allowlist |
| `TOP100_CACHE_TTL_SECONDS` | Stock API ETag/cache TTL |
| `ETF_CACHE_TTL_SECONDS` | ETF API ETag/cache TTL |
| `STORAGE_WARN_PCT` / `STORAGE_PROTECT_PCT` / `STORAGE_EMERGENCY_PCT` | Storage watermark thresholds |

## Data Directories

```text
/app/data/
  twse_heat.db
  buy_scores/
    YYYY-MM-DD.json
    .force_refresh
    .scoring_in_progress
```

## Production Server

Target host: `root@10.1.1.230:/root/TWSE_TOP100_HEAT`

Deploy pattern:
1. build three images locally (`backend`, `crawler`, `frontend`)
2. `docker save | gzip`
3. `scp` images + `run_containers.sh`
4. remote `docker load`
5. `bash run_containers.sh`
