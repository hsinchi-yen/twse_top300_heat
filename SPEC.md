# Spec: 台股熱力圖 Dashboard

> Updated: 2026-06-16
> This spec reflects the current implementation, including legacy route names that remain in service.

## Objective

建立一個可長時間連續運行的台股熱力圖 Dashboard：
- 股票主畫面使用固定 `600` 檔顯示池
- 提供 `成交量`、`週轉率`、`買進評分` 三種股票視角
- 提供獨立 ETF 視圖
- 部署於 Yocto ARM64，依賴 SQLite + Docker + `--network host`

## User-facing modes

| Mode | Data source | Sort rule |
|---|---|---|
| `volume` | `/api/stocks/top100?mode=volume&limit=600` | backend `volume_rank` |
| `turnover` | same 600-stock payload as `volume` | frontend re-sort by `turnover_rate` |
| `buy_score` | same 600-stock payload + `/api/scores` | frontend re-sort by buy score |
| `etf` | `/api/etf?sort_by=turnover|asset_scale&limit=300` | backend ETF ranks |

## Core invariants

1. Frontend stock view always fetches `mode=volume&limit=600`
2. Buy-score computation lives only in `crawler/`
3. Force refresh is file-based and non-blocking
4. Buy-score cache writes are atomic `.tmp -> rename`
5. Token stays in crawler env (`FINMIND_TOKEN`), never in query string
6. ETF data path is independent from stock data path

## Commands

```bash
# Full local stack
docker compose up -d
docker compose logs -f backend
docker compose logs -f crawler
docker compose down

# Frontend
cd frontend && npm install
cd frontend && npm run dev
cd frontend && npm run test

# Backend
cd backend && pip install -r requirements.txt
cd backend && pytest -v

# Crawler score engine tests
cd crawler && pytest tests/test_buy_score_source.py tests/test_buy_score_engine.py -v
```

## Project structure

```text
Twse_Top100_Heat/
├── CLAUDE.md
├── SPEC.md
├── improve.md
├── docker-compose.yml
├── run_containers.sh
├── backend/
│   ├── main.py
│   ├── database.py
│   └── routers/
│       ├── stocks.py
│       ├── scores.py
│       ├── etf.py
│       └── sectors.py
├── crawler/
│   ├── main.py
│   ├── etf_main.py
│   ├── processor.py
│   └── sources/
│       ├── buy_score.py
│       ├── buy_score_engine.py
│       ├── finmind_client.py
│       ├── finmind.py
│       ├── twse.py
│       ├── tpex.py
│       ├── yahoo.py
│       ├── etf_twse.py
│       └── etf_yahoo.py
└── frontend/
    └── src/
        ├── constants.js
        ├── stores/stockStore.js
        ├── composables/
        └── components/
```

## Runtime architecture

### Stocks

```text
TWSE/TPEX/Yahoo + FinMind issue shares
  -> crawler/main.py
  -> merge_and_rank()
  -> SQLite stock_ranks
  -> GET /api/stocks/top100
  -> frontend volume payload (limit=600)
  -> client-side reorder for turnover / buy_score
```

### Buy score

```text
Frontend /api/scores?force=true
  -> backend writes .force_refresh
  -> crawler force_refresh_watch_job()
  -> score_job(force=True)
  -> compute_buy_score() direct to FinMind
  -> write partial/final JSON to SCORES_DIR
  -> frontend polls /api/scores for progress
```

### ETF

```text
TWSE ETF + Yahoo ETF asset scale
  -> crawler/etf_main.py
  -> SQLite etf_ranks
  -> GET /api/etf
  -> frontend ETF view
```

## API contract

### `GET /api/stocks/top100`

Query params:
- `mode=volume|turnover`
- `limit=1..1000` (default `100`)

Implementation notes:
- Route name is historical; it is not limited to 100 rows
- Frontend stock UI always uses `mode=volume&limit=600`
- `market_open` is computed from current Taipei time (`Mon-Fri`, `09:00-13:30`)
- `updated_at` is the API response timestamp, not the trade-source timestamp
- Supports `ETag` + `Cache-Control`

Example:

```json
{
  "mode": "volume",
  "date": "2026-06-11",
  "market_open": false,
  "updated_at": "2026-06-11T16:03:12+08:00",
  "sectors": [
    {
      "name": "半導體",
      "stocks": [
        {
          "stock_id": "2330",
          "name": "台積電",
          "rank": 1,
          "volume": 45000000,
          "turnover_rate": 0.82,
          "price_change_pct": 2.35,
          "color_tier": "light_red",
          "close_price": 950.0
        }
      ]
    }
  ]
}
```

### `GET /api/scores`

Behavior:
- backend only reads the newest JSON in `SCORES_DIR`
- `force=true` writes a refresh flag if no fetch is already active
- `X-FinMind-Token` header is accepted but ignored
- `fetching=true` when `.scoring_in_progress` or `.force_refresh` exists.
  `score_job` / resume own `.scoring_in_progress`, so ALL scoring paths (monthly
  cron, force refresh, quota-resume) surface fetching + progress identically
- a coordination flag older than `SCORING_FLAG_STALE_S` is treated as orphaned
  (crashed mid-run): it no longer counts toward `fetching`, so a later
  `force=true` can take over and the frontend button is not pinned disabled
- `date` / `generated_at` feed the frontend "評分更新 <date> <time>" label;
  while fetching, the frontend renders a progress bar
- `progress: {done, total}` is included only while fetching, read from the
  crawler's `.score_progress` file (the dated JSON keeps the full baseline during
  a force refresh, so this counter is the only accurate recompute progress);
  the frontend prefers it and falls back to counting scored stocks on a cold start

Example:

```json
{
  "date": "2026-06-11",
  "generated_at": "2026-06-11T03:42:18+08:00",
  "scores": {
    "2330": { "score": 18, "max_score": 24 },
    "2317": { "score": 12, "max_score": 24 }
  },
  "fetching": false
}
```

Empty state:

```json
{
  "date": "",
  "scores": {},
  "fetching": false
}
```

### `GET /api/etf`

Query params:
- `sort_by=turnover|asset_scale`
- `limit=1..300` (default `300`)

Notes:
- supports `ETag` + `Cache-Control`
- `updated_at` is the API response timestamp

Example:

```json
{
  "sort_by": "turnover",
  "date": "2026-06-11",
  "market_open": false,
  "updated_at": "2026-06-11T16:05:10+08:00",
  "etfs": [
    {
      "etf_id": "0050",
      "name": "元大台灣50",
      "etf_type": "股票型",
      "asset_scale": 3241.5,
      "outstanding_units": 1680000000,
      "volume": 6888000,
      "turnover_rate": 0.41,
      "close_price": 185.5,
      "price_change_pct": 1.23,
      "nav": 185.2,
      "premium_discount": 0.162,
      "management_fee": 0.32,
      "portfolio_turnover": 6.0,
      "color_tier": "light_red",
      "turnover_rank": 2,
      "asset_scale_rank": 1
    }
  ]
}
```

### `GET /api/sectors`

Returns all `sector_map` rows for manual maintenance tooling.

### `PUT /api/sectors/{stock_id}`

Updates a single `sector_map` entry.

## Scheduler jobs

### Stock crawler (`crawler/main.py`)

| Job ID | Schedule | Purpose |
|---|---|---|
| `crawl_intraday` | Mon-Fri `09:00-12:59` every minute | intraday stock crawl |
| `crawl_intraday_1330` | Mon-Fri `13:00-13:30` every minute | extended market crawl |
| `crawl_close` | Mon-Fri `16:00` | close snapshot |
| `daily_maintenance` | Mon-Fri `08:55` | WAL checkpoint, storage check, cache clear, sector refresh, prune |
| `score_monthly` | day `1` at `03:00` | monthly buy-score batch |
| `monthly_vacuum` | day `1` at `02:00` | SQLite VACUUM |
| `force_refresh_watch` | every minute | detect `.force_refresh` |

### ETF crawler (`crawler/etf_main.py`)

| Job ID | Schedule | Purpose |
|---|---|---|
| `etf_intraday` | Mon-Fri `09:00-12:59` every minute | intraday ETF crawl |
| `etf_intraday_1330` | Mon-Fri `13:00-13:30` every minute | extended market crawl |
| `etf_close` | Mon-Fri `16:05` | close snapshot |
| `etf_asset_scale` | Mon-Fri `08:50` | refresh Yahoo asset scale |
| `etf_prune` | day `1` at `02:30` | prune old ETF history |

## Buy-score rules

- Candidate pool: `volume_rank <= SCORE_CANDIDATE_LIMIT`
- Delay between stocks: `BUY_SCORE_REQUEST_DELAY`
- Delay between datasets: `BUY_SCORE_FETCH_DELAY`
- Quota exhaustion: wait `BUY_SCORE_QUOTA_WAIT_S`, then resume only missing names
- Partial persistence: write every 50 successful scores
- Full-fetch failure for a stock: do not persist `0/24`
- File retention: keep latest 7 JSON files
- Orphan recovery: a `.scoring_in_progress` left by a crashed run is cleared once
  older than `SCORING_FLAG_STALE_S` (crawler on startup + every-minute watch job;
  backend ignores it for `fetching` past the same age)
- Frontend buy-score view: progress bar + "評分更新 <date> <time>" in the topbar;
  each card shows 成交量 ｜ 週轉率 ｜ 漲跌幅

## Data retention

| Data | Retention |
|---|---|
| `stock_ranks` | latest 7 trading dates |
| `etf_ranks` | latest `ETF_KEEP_DAYS` trading dates, default `90` |
| `buy_scores/*.json` | latest 7 files |

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | implementation-specific | SQLite location |
| `FINMIND_TOKEN` | `""` | crawler-only buy-score token |
| `SCORES_DIR` | `/app/data/buy_scores` | shared score JSON directory |
| `SCORE_CANDIDATE_LIMIT` | `600` | score candidate pool limit |
| `BUY_SCORE_REQUEST_DELAY` | `1.2` | delay between stocks |
| `BUY_SCORE_FETCH_DELAY` | `0.4` | delay between FinMind datasets |
| `BUY_SCORE_QUOTA_WAIT_S` | `3600` | wait after quota exhaustion |
| `BUY_SCORE_QUOTA_MAX_CYCLES` | `24` | legacy bound; quota-resume currently loops without an enforced upper limit until all stocks are scored |
| `SCORING_FLAG_STALE_S` | `10800` | age after which `.scoring_in_progress` / `.force_refresh` are treated as orphaned and cleared (backend + crawler) |
| `BUY_SCORE_GOODINFO_ENABLED` | `false` | optional Goodinfo scoring inputs |
| `ETF_KEEP_DAYS` | `90` | ETF history retention |
| `ALLOWED_ORIGINS` | `""` | CORS allowlist; empty currently maps to `*` |
| `TOP100_CACHE_TTL_SECONDS` | `3` | stock endpoint cache TTL |
| `ETF_CACHE_TTL_SECONDS` | `3` | ETF endpoint cache TTL |
| `SQLITE_BUSY_TIMEOUT_MS` | `5000` | SQLite busy timeout |
| `SQLITE_CACHE_SIZE_KIB` | `8192` | SQLite cache size |
| `STORAGE_WARN_PCT` | `70.0` | storage warning threshold |
| `STORAGE_PROTECT_PCT` | `80.0` | storage protection threshold |
| `STORAGE_EMERGENCY_PCT` | `90.0` | storage emergency threshold |

## Deployment

### Local dev

Use `docker-compose.yml`.

### Yocto production

Use `run_containers.sh`.

Runtime shape:
1. `twse-backend`
2. `twse-crawler`
3. `twse-etf-crawler`
4. `twse-frontend`

All production containers use `--network host`.

## Testing strategy

| Layer | Tooling | Focus |
|---|---|---|
| Backend API | `pytest` | stocks / scores / etf response contracts |
| Backend logic | `pytest` | ranking and DB behavior |
| Crawler score engine | `pytest` | native buy-score computation |
| Frontend | `vitest` | store, composables, sorting, rendering helpers |

## Boundaries

### Always

- Keep stock frontend fetch fixed to `mode=volume&limit=600`
- Keep buy-score ownership in crawler
- Preserve atomic score writes
- Preserve ETF as a separate endpoint and polling path

### Ask first

- changing SQLite schema
- adding new runtime dependencies
- changing scheduler frequencies
- changing the display pool or score candidate pool

### Never

- put tokens in query strings
- delete current buy-score cache before the replacement file exists
- reintroduce an external score-computation HTTP dependency
