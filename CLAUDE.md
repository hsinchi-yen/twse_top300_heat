# CLAUDE.md — Twse_Top100_Heat

## What This Project Is

台股熱力圖 Dashboard。導覽為 總覽 ｜ 熱力圖 ｜ ETF ｜ 自選，任一股票可開啟個股面板：
- 總覽：市場狀態、研究候選清單、市場寬度、族群輪動、技術型態歷史驗證（預設入口）
- 熱力圖：股票成交量 / 週轉率 / 買進評分，共用同一個 `600` 檔股票顯示池
- ETF 視圖，獨立走 `/api/etf`
- 自選：警示、筆記、最多 3 檔比較
- 個股面板：綜合評估、走勢、法人、評分走勢、部位試算、基本面明細
- 買進評分由 crawler 原生計算，backend 只負責讀共享 JSON 與協調 force refresh

技術棧：Vue 3 + FastAPI + SQLite + APScheduler，部署於 Yocto ARM64 嵌入式 Linux，目標是 365x24 長時間運行。

## Key Architecture Decisions

- Display pool: frontend 股票頁永遠請求 `/api/stocks/top100?mode=volume&limit=600`
- Turnover / buy-score ordering: 都在前端對同一批 600 檔資料重排，不切換股票 API query
- ETF mode: 走 `/api/etf?sort_by=turnover|asset_scale&limit=300`
- Score candidate pool: `volume_rank <= SCORE_CANDIDATE_LIMIT`，預設 `600`，硬上限 `1000`
- Score engine: `crawler/sources/buy_score_engine.py::compute_buy_score` 原生直連 FinMind，不再依賴外部評分服務
- Score schedule: 每天 `03:00` 的 `nightly` job，TWSE 官方日資料出現尚未處理的新交易日才跑（比對 `stock_signals` 最新日期，不是昨天：該資料源 03:00 時尚未更新）；先每日籌碼／技術指標，再買進評分；假日不觸發
- Quota resume: FinMind 額度耗盡時寫 partial，等待 `BUY_SCORE_QUOTA_WAIT_S` 後只續抓未完成者
- Force refresh: backend 寫 `buy_scores/.force_refresh`；crawler 每分鐘偵測並執行 `score_job(force=True)`
- Stale-flag recovery: 旗標超過 `SCORING_FLAG_STALE_S`（預設 3h）視為 crash 殘留，backend 不再計入 `fetching`、crawler 自動清除，避免按鈕永久卡死
- Atomic cache writes: 評分 JSON 一律 `.tmp -> rename`，不得 delete-then-write
- No misleading zeroes: `eligible_count == 0` 時不落地 `0/24`，前端顯示 `N/A`
- Polling: 股票盤中 `60s`、盤後 `5min`；ETF 目前盤中 / 盤後都維持 `60s` 輪詢
- 自選股: backend 擁有 `watchlist` 表與 `/api/watchlist`；評分候選池 = volume pool ∪ watchlist
- 每日指標: crawler `signals.py` 擁有 `daily_bars` / `inst_flows` / `stock_signals`，backend `/api/signals` 只讀
- 篩選器 / 卡片 chips: 純前端（`utils/stockFilters.js`、`utils/signals.js`）；缺欄位一律不顯示、不符合篩選
- 分析層: 純前端（`utils/analysis.js`、`utils/positionSizing.js`）。綜合分權重是經驗設定，未經報酬驗證；缺資料 = `null`，風險優先於分數
- 市場分析 API: `routers/market.py` 只讀 crawler 的 `daily_bars` / `inst_flows`，計算在 `services/market_analytics.py`，依最新 bars 記憶化；表不存在 = 空狀態
- 型態驗證只驗技術面：評分檔僅留 7 份，買進評分本身無法回測，UI 不得暗示已驗證
- 圖表: `components/charts/` 自製 SVG，不引入圖表套件；單一 y 軸、缺值斷線、附數據表與鍵盤操作
- Deployment: Yocto production 使用 `run_containers.sh` + `--network host`，共四個容器

## Test Commands

```bash
# Backend
cd backend && pytest -v

# Crawler (buy score, daily signals, nightly gate)
cd crawler && pytest -v

# Frontend
cd frontend && npm run test
```

## Critical Rules

1. FinMind token 只由 crawler 使用；backend `GET /api/scores` 不應自行計分。token 可由 UI 齒輪經 `/api/settings/finmind-token` 寫入 `FINMIND_TOKEN_FILE`（優先於 env `FINMIND_TOKEN`）
2. token 只存伺服器端（write-only API，任何回應都不得回傳 token；前端不得存 localStorage）；backend 仍忽略 `X-FinMind-Token` header。不要把 token 放進 query string 或 log
3. Frontend 股票主畫面固定用 `mode=volume&limit=600`
4. 週轉率 / 買進評分都是前端排序行為，不要把它們改回股票 API 的不同抓法
5. 強制刷新不能先刪舊檔；必須維持舊資料可讀直到新檔原子替換
6. `ALLOWED_ORIGINS` 由 env 控制；不要在程式碼裡寫死特定來源
7. API contract 若變更，先改 `SPEC.md`，再補測試，再改實作
8. 不得顯示推估或捏造的數字；來源沒有的欄位顯示 `—`。UI 用語為研究語氣（研究候選），不得承諾報酬，分析畫面須保留非投資建議聲明

## Important Environment Variables

| Variable | Purpose |
|---|---|
| `FINMIND_TOKEN` | Fallback buy-score token (crawler env) |
| `FINMIND_TOKEN_FILE` | UI-set token file (default `/app/data/.finmind_token`), overrides env |
| `SCORES_DIR` | Buy-score JSON directory |
| `SCORE_CANDIDATE_LIMIT` | Buy-score candidate pool limit |
| `BUY_SCORE_REQUEST_DELAY` | Delay between stocks during score batch |
| `BUY_SCORE_FETCH_DELAY` | Delay between FinMind datasets inside score engine |
| `BUY_SCORE_QUOTA_WAIT_S` | Wait time after quota exhaustion |
| `BUY_SCORE_QUOTA_MAX_CYCLES` | Legacy bound; quota-resume currently loops without an enforced upper limit |
| `SCORING_FLAG_STALE_S` | Age after which `.scoring_in_progress` / `.force_refresh` are treated as orphaned and cleared (default `10800`) |
| `BUY_SCORE_GOODINFO_ENABLED` | Optional Goodinfo crawler toggle |
| `WATCHLIST_MAX` / `SIGNALS_*` | Watchlist size; daily-signal retention, backfill delay, cache TTL (see `SPEC.md`) |
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
    details/YYYY-MM-DD.json   # per-stock criteria / risk detail for /api/scores/{id}
    .force_refresh
    .scoring_in_progress
    .score_progress      # {done,total} live recompute counter for the active run
    .score_resume        # quota-resume state (pending ids), persists across restarts
```

## Production Server

Target host: `root@10.1.1.230:/root/TWSE_TOP100_HEAT`

Deploy pattern:
1. build three images locally (`backend`, `crawler`, `frontend`)
2. `docker save | gzip`
3. `scp` images + `run_containers.sh`
4. remote `docker load`
5. `bash run_containers.sh`

## Agent skills

### Issue tracker

Issues live on GitHub Issues (`hsinchi-yen/twse_top300_heat`) and are managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default mattpocock/skills label vocabulary (no overrides). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — `CLAUDE.md` (key rules) + `SPEC.md` (full spec) + `improve.md` (long-run stability notes). See `docs/agents/domain.md`.
