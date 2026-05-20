# CLAUDE.md — Twse_Top100_Heat

## What This Project Is

台股成交量前 360 熱力圖 Dashboard。Vue 3 + FastAPI + SQLite + APScheduler，部署於 Yocto ARM64 嵌入式 Linux，連續運行 365×24 小時。

## Key Architecture Decisions

- **Display pool**: 360 stocks by volume (`mode=volume&limit=360` always)；週轉率模式在前端重排，不動後端 query
- **Score candidate pool**: `volume_rank ≤ SCORE_CANDIDATE_LIMIT`（預設 480，硬上限 1000）
- **Score schedule**: 每月 1 日 03:00（月更新，財報基礎分數）
- **Token**: 只能透過 `X-FinMind-Token` HTTP header 傳遞，禁止放入 query string 或 log
- **Force refresh**: `.tmp → rename` 原子切換，不先刪舊檔
- **Polling**: 盤中 60s，盤後 5min（降低 eMMC 寫入）
- **Deployment**: Yocto 無 docker-compose，用 `run_containers.sh`（`--network host`）

## Test Commands

```bash
# Backend（必須在 commit 前通過）
cd backend && pytest -v           # 期望 60/60 pass

# Frontend（必須在 commit 前通過）
cd frontend && npm run test       # 期望 41/41 pass
```

## Critical Rules

1. Token 只透過 `X-FinMind-Token` header，禁止 query string
2. 評分強制刷新不刪舊檔 — 用 `.tmp` 寫完後 `.replace()`
3. 前端 `useStockData.js` 永遠用 `mode=volume&limit=360`；週轉率排序在 `HeatmapGrid.vue` allStocks computed 做
4. `CORS` 從 `ALLOWED_ORIGINS` env 讀取；不得寫死 `["*"]`
5. 每次 API contract 變更先改 `SPEC.md`，再補測試，再改實作

## Environment Variables (重要)

| 變數 | 說明 |
|------|------|
| `FINMIND_TOKEN` | FinMind token（crawler env） |
| `STOCK_ANALYSIS_URL` | StockAnalysisDashBoard URL |
| `SCORE_CANDIDATE_LIMIT` | 評分候選池上限（預設 480） |
| `ALLOWED_ORIGINS` | CORS 白名單（空 = `*`） |
| `ETF_KEEP_DAYS` | ETF 歷史保留天數（預設 90） |

## Data Directories

```
/app/data/
  twse_heat.db          # SQLite main DB
  buy_scores/           # YYYY-MM-DD.json（保留 7 天）
  metrics/              # 每日 token 成本指標
```

## Production Server

`root@10.1.1.230:/root/TWSE_TOP100_HEAT` — Yocto ARM64，Docker 28+，無 docker-compose

Deploy: build images locally → `docker save | gzip` → `scp` → `docker load` → `bash run_containers.sh`
Or: SCP source → build on remote → `bash run_containers.sh`
