# CLAUDE.md — Twse_Top100_Heat

## What This Project Is

台股成交量前 480 熱力圖 Dashboard。Vue 3 + FastAPI + SQLite + APScheduler，部署於 Yocto ARM64 嵌入式 Linux，連續運行 365×24 小時。

## Key Architecture Decisions

- **Display pool**: 480 stocks by volume (`mode=volume&limit=480` via `MAX_STOCKS` constant)；週轉率模式在前端重排，不動後端 query
- **Score candidate pool**: `volume_rank ≤ SCORE_CANDIDATE_LIMIT`（預設 480，硬上限 1000）
- **Score engine（重要）**: 買進評分**原生計算**於 crawler（`crawler/sources/buy_score_engine.py::compute_buy_score`，24 指標 + 排雷，直接打 FinMind），**不再代理** StockAnalysisDashBoard。引擎/FinMind client 由該專案移植而來
- **Score schedule**: 每月 1 日 03:00（月更新，財報基礎分數）。分時處理：每檔間 `BUY_SCORE_REQUEST_DELAY`、每資料集間 `BUY_SCORE_FETCH_DELAY`
- **Quota 續抓**: FinMind 額度耗盡（402→`FinMindError`）時寫 partial、等 `BUY_SCORE_QUOTA_WAIT_S`（預設 1h）後只續抓未完成者，最多 `BUY_SCORE_QUOTA_MAX_CYCLES` 輪
- **Token**: crawler 用 `FINMIND_TOKEN` env；禁止放入 query string 或 log
- **Force refresh**: backend `GET /api/scores?force=true` 寫旗標檔 `buy_scores/.force_refresh`；crawler 每分鐘偵測 → 寫 `.scoring_in_progress`（backend `fetching` 依此判定）→ 跑 `score_job(force=True)`。寫檔一律 `.tmp → rename` 原子切換，不先刪舊檔
- **不存 0/24**: 某檔所有資料抓取皆失敗（`eligible_count==0`）時不落地為誤導性 0/24，回 None（前端 N/A）等下輪重試
- **Polling**: 盤中 60s，盤後 5min（降低 eMMC 寫入）
- **Deployment**: Yocto 無 docker-compose，用 `run_containers.sh`（`--network host`）

## Test Commands

```bash
# Backend（必須在 commit 前通過）
cd backend && pytest -v           # 期望 63/63 pass

# Crawler 評分引擎（買進評分相關）
cd crawler && pytest tests/test_buy_score_source.py tests/test_buy_score_engine.py -v

# Frontend（必須在 commit 前通過）
cd frontend && npm run test       # 期望 56/56 pass
```

## Critical Rules

1. FinMind token：crawler 用 `FINMIND_TOKEN` env，禁止放入 query string 或 log（backend 不再需要 token）
2. 評分強制刷新不刪舊檔 — 用 `.tmp` 寫完後 `.replace()`
3. 前端 `useStockData.js` 永遠用 `mode=volume&limit=480`（由 `constants.js::MAX_STOCKS` 控制）；週轉率排序在 `HeatmapGrid.vue` allStocks computed 做
4. `CORS` 從 `ALLOWED_ORIGINS` env 讀取；不得寫死 `["*"]`
5. 每次 API contract 變更先改 `SPEC.md`，再補測試，再改實作

## Environment Variables (重要)

| 變數 | 說明 |
|------|------|
| `FINMIND_TOKEN` | FinMind token（crawler env，評分計算用） |
| `SCORE_CANDIDATE_LIMIT` | 評分候選池上限（預設 480） |
| `BUY_SCORE_REQUEST_DELAY` | 每檔評分間隔秒（預設 1.2） |
| `BUY_SCORE_FETCH_DELAY` | 引擎內每個 FinMind 資料集間隔秒（預設 0.4） |
| `BUY_SCORE_QUOTA_WAIT_S` | 額度耗盡後續抓等待秒（預設 3600） |
| `BUY_SCORE_QUOTA_MAX_CYCLES` | 額度續抓最多輪數（預設 24） |
| `BUY_SCORE_GOODINFO_ENABLED` | 是否啟用 Goodinfo 外資/質押爬蟲（預設 false，避免封鎖） |
| `ALLOWED_ORIGINS` | CORS 白名單（空 = `*`） |
| `ETF_KEEP_DAYS` | ETF 歷史保留天數（預設 90） |

## Data Directories

```
/app/data/
  twse_heat.db          # SQLite main DB
  buy_scores/           # YYYY-MM-DD.json（保留 7 天）+ .force_refresh / .scoring_in_progress 旗標
```

## Production Server

`root@10.1.1.230:/root/TWSE_TOP100_HEAT` — Yocto ARM64，Docker 28+，無 docker-compose

Deploy: build images locally → `docker save | gzip` → `scp` → `docker load` → `bash run_containers.sh`
Or: SCP source → build on remote → `bash run_containers.sh`
