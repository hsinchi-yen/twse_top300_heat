# Spec: 台股熱力圖 Dashboard

> Updated: 2026-11-02 (overview, stock panel, market trend, setup validation, position sizing)
> This spec reflects the current implementation, including legacy route names that remain in service.

## Objective

建立一個可長時間連續運行的台股熱力圖 Dashboard：
- 股票主畫面使用固定 `600` 檔顯示池
- 提供 `總覽`（市場狀態、族群輪動、候選清單）作為預設入口
- 提供 `成交量`、`週轉率`、`買進評分` 三種股票視角 + `自選股` 視圖
- 提供獨立 ETF 視圖
- 任一股票可開啟個股分析面板：趨勢、法人、評分走勢、基本面明細、部位試算
- 部署於 Yocto ARM64，依賴 SQLite + Docker + `--network host`

## User-facing modes

| Mode | Data source | Sort rule |
|---|---|---|
| `overview` | same 600-stock payload + `/api/scores` + `/api/signals` + `/api/market/trend` + `/api/market/backtest` | shortlist by 綜合分 (frontend) |
| `volume` | `/api/stocks/top100?mode=volume&limit=600` | backend `volume_rank` |
| `turnover` | same 600-stock payload as `volume` | frontend re-sort by `turnover_rate` |
| `buy_score` | same 600-stock payload + `/api/scores` | frontend re-sort by buy score |
| `watchlist` | `/api/watchlist` (embedded quotes) + `/api/scores` + `/api/scores/{id}` on expand | `added_at` order; large cards with note + criteria detail |
| `etf` | `/api/etf?sort_by=turnover|asset_scale&limit=300` | backend ETF ranks |

篩選器組合 (`frontend/src/utils/stockFilters.js`): frontend-only over the same
600-stock payload in volume / turnover / buy_score views (never a different
stock API query). Atomic conditions are AND-combined; a stock missing a needed
field never matches. Presets:

| Preset | Conditions |
|---|---|
| 穩健優質 | `pass_rate ≥ 75` ∧ `risk_score == 0` |
| 轉強起漲 | `fundamentals_uptrend` ∧ `above_ma20` ∧ `inst_streak ≥ 3` |
| 低估待買 | `pe.current < pe.p25` ∧ `pass_rate ≥ 60` ∧ `risk_score == 0` |
| 量增突破 | 量比 `≥ 2` (live volume ÷ `avg_volume_5d` while open) ∧ `price_change_pct > 0` ∧ `above_ma60` |

Filtered results sort by `pass_rate` desc → `inst_net_5d` desc (nulls last); the
bar shows `符合 N / 600`; the selection persists in `localStorage` (falls back
to no filter when storage is unavailable) and survives mode switches.

自選股 pin / unpin：stock cards show ☆／★ (desktop hover; mobile long-press
550 ms). Watchlist loads once at startup and polls only while `watchlist` mode is
active (60s 盤中 / 5min 盤後).

The active mode persists in `localStorage` (`view_mode`; falls back to `overview`),
so a kiosk keeps the view it was left on.

Navigation: 總覽 ｜ 熱力圖 ｜ ETF ｜ 自選. 熱力圖 covers `volume` / `turnover` /
`buy_score` via a segmented sort control; these stay distinct `mode` values and
never change the stock API query. Global search (code or name) covers the display
pool ∪ watchlist and opens the stock panel.

## Analysis layer (frontend-only)

`frontend/src/utils/analysis.js` derives everything below from the same payloads
the cards use. It is display logic: it never writes back, and `/api/scores` is not
changed by it. Missing input stays missing — a dimension without data is `null`,
never a fallback number.

| Dimension | Weight | Input | Score (0–100) |
|---|---|---|---|
| 基本面 `quality` | 40% | `pass_rate`, `eligible_count`, `fundamentals_uptrend` | `pass_rate`, +5 when uptrend, capped at 100; `null` when `eligible_count < 12` (a new listing or failed datasets: 6/6 would read as a perfect score, and failed datasets also skip 排雷 checks, so `risk_score` 0 is not "no risk") |
| 趨勢 `trend` | 25% | `above_ma20`, `above_ma60`, `pct_from_52w_high` | earned ÷ available of: MA20 35, MA60 35, 距高點 30 (≥-5% 30, ≥-15% 20, ≥-30% 10, else 0); needs at least one MA flag |
| 籌碼 `flow` | 20% | `inst_streak`, `inst_net_5d` | `50 + 8 × clamp(streak, ±5)`, ±10 by sign of `inst_net_5d`, clamped to 0–100 |
| 評價 `value` | 15% | `pe.current`, `pe.p25`, `pe.median` | `< p25` 90, `< median` 65, `≤ 1.25 × median` 40, else 20; `current ≤ 0` or missing → `null` |

- 綜合分 = weighted mean over available dimensions, then `-10` per triggered 排雷
  item, floored at 0. It is `null` unless `quality` is present and at least 3
  dimensions are.
- The weights are editorial heuristics, not fitted to returns. The UI must say so.
- 投資人狀態 (`stance`), first match wins:

| Stance | Rule |
|---|---|
| `avoid` 避開 | `risk_score ≥ 2` or signal `avoid` |
| `insufficient` 資料不足 | 綜合分 `null` |
| `wait_pullback` 等回檔 | 綜合分 `≥ 60` and live price `> 1.10 × ma20` |
| `candidate` 研究候選 | 綜合分 `≥ 70` and live price above `ma20` |
| `watch` 觀察 | 綜合分 `≥ 55` |
| `pass` 暫不考慮 | otherwise |

候選清單 = stocks with stance `candidate` or `wait_pullback`, 綜合分 desc →
`inst_net_5d` desc. Wording is research language ("研究候選"), never an instruction
or a return claim.

自選警示 (watchlist): 跌破月線 / 跌破季線 (live price vs. nightly MA), 法人連賣 ≥ 3,
排雷 ≥ 1, 距 52 週高點 ≤ -20%.

部位試算 (`frontend/src/utils/positionSizing.js`): shares = min(capital × 單筆風險% ÷
(entry − stop), capital × 單檔上限% ÷ entry), floored to whole 張 (1000 股); 零股
shown when under 1 張. Reports max loss, position %, 成交量占比 against
`avg_volume_5d` (warns above 5%), and round-trip cost using the statutory 0.1425% × 2
+ 0.3% 證交稅, no broker discount. Default stop = `ma60` when it sits 3–8% below the
price, otherwise price − 8%: closer than 3% is noise (the stop would trigger on an
ordinary day and inflate the position), further than 8% risks too much. Settings
persist per viewer in `localStorage`.

族群下鑽: a sector row on the overview opens the heatmap limited to that sector.
Frontend-only over the same 600-stock payload; combines with the filter conditions;
shown as a removable chip; not persisted.

比較 (watchlist): up to 3 pinned stocks side by side. Chart = closes over the last 6
months on the dates all selected stocks share, rebased to 100 at the first shared
date (one axis, never dual). Table = 綜合分, stance, the four dimensions, price, 期間
報酬, P/E, 法人 5 日. A stock keeps its colour while it stays selected. History comes
from `/api/stocks/{stock_id}/history?days=132`, fetched on selection.

使用說明 (Guide): in-app, explains the workflow and the limits of the data. Every
analysis surface shows that this is not investment advice and that the score has
not been shown to predict returns.

## Core invariants

1. Frontend stock view always fetches `mode=volume&limit=600`
2. Buy-score computation lives only in `crawler/`
3. Force refresh is file-based and non-blocking
4. Buy-score cache writes are atomic `.tmp -> rename`
5. Token is stored server-side only (`FINMIND_TOKEN_FILE`, set from the UI gear via `/api/settings/finmind-token`, fallback to crawler env `FINMIND_TOKEN`); never in query string, logs, or any API response; the browser never persists it
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
│       ├── market.py
│       ├── signals.py
│       ├── watchlist.py
│       ├── etf.py
│       └── sectors.py
│   └── services/
│       └── market_analytics.py
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
        ├── stores/
        ├── composables/
        ├── utils/          # analysis.js, positionSizing.js, signals.js, stockFilters.js
        └── components/     # charts/ holds the dependency-free SVG charts
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

TPEx `tpex_mainboard_daily_close_quotes` reports volume as `TradingShares` and
the move as `Change` (no `TradeVolume` / `Yesterday`). Before 2026-10-26 the
parser read the old names, so every 上櫃 stock had volume 0 / change 0% and none
ranked into the 600 pool; after the fix ≈166 of the top 600 are 上櫃.

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

### `GET /api/stocks/{stock_id}/history`

Price, moving-average and institutional history for the stock panel. Reads the
crawler's `daily_bars` / `inst_flows` (read-only; a missing table means "not
computed yet").

Query params: `days=20..260` (default `260`).

```json
{
  "stock_id": "2330",
  "date": "2026-10-23",
  "bars": [
    { "date": "2026-10-23", "close": 1045.0, "volume": 41000000, "ma20": 1010.5, "ma60": 980.2 }
  ],
  "flows": [
    { "date": "2026-10-23", "foreign_net": 3200, "trust_net": 400, "dealer_net": -50 }
  ]
}
```

- `bars` / `flows` ascending; `flows` = all retained days (≤ `SIGNALS_INST_KEEP_DAYS`)
- MAs are computed over all retained bars before trimming to `days`, so the first
  returned row is not `null` merely because of the window; `null` = fewer than 20 / 60
  bars exist
- closes are unadjusted (same caveat as Daily signal rules)
- unknown stock or missing tables → `200` with empty lists and `date: ""`
- supports `ETag` + `Cache-Control` (`SIGNALS_CACHE_TTL_SECONDS`)

### `GET /api/market/trend`

Market breadth and sector rotation over the signal universe, derived from
`daily_bars` + `sector_map` + `inst_flows`; memoized until the bars, the flows or a
sector mapping change.

Query params: `days=20..120` (default `60`).

```json
{
  "date": "2026-10-23",
  "universe": 612,
  "breadth": [
    { "date": "2026-10-23", "advancers": 320, "decliners": 250, "unchanged": 42,
      "pct_above_ma20": 56.1, "pct_above_ma60": 61.3, "ew_index": 104.2 }
  ],
  "sectors": [
    { "name": "半導體", "count": 52, "ret_5d": 2.1, "ret_20d": 6.4, "ret_60d": 11.2,
      "pct_above_ma20": 71.0, "inst_net_5d": 125000 }
  ]
}
```

- `breadth` ascending. `pct_above_*` is over stocks with enough history that day
  (`null` when fewer than 20 qualify). `ew_index` = chain-linked equal-weight mean
  daily return, rebased to 100 at the first returned day
- a daily move beyond ±11% is treated as a corporate action (limit is ±10%) and
  excluded from `ew_index` and advancers / decliners
- sector `ret_*` = **median** stock return over N market days of the calendar, not
  N of the stock's own bars, which can skip days when it leaves and re-enters the
  universe. A stock without a bar N market days back, or with any bar-to-bar move
  beyond ±11% inside the window, is excluded (`null` under 3 stocks with data);
  sectors with fewer than 3 stocks and `其他` are omitted; sorted by `ret_20d` desc,
  nulls last
- `inst_net_5d` = 外資 + 投信 net over the last 5 flow dates, 張; `null` without flows
- universe is today's most-traded names, so history is survivorship-biased; the
  UI must say so
- missing tables → `{"date": "", "universe": 0, "breadth": [], "sectors": []}`
- supports `ETag` + `Cache-Control` (`SIGNALS_CACHE_TTL_SECONDS`)

### `GET /api/market/backtest`

Historical check of the **technical** setups over retained `daily_bars`. Buy scores
are not validated here: only 7 score files are retained, so the score has no
history to test.

Query params: `horizon=5|20|60` (default `20` trading days).

```json
{
  "date": "2026-10-23",
  "horizon": 20,
  "periods": 11,
  "baseline": { "avg_ret": 1.8, "win_rate": 54.2 },
  "setups": [
    { "key": "trend_up", "label": "站上月季線", "periods": 11, "beat_periods": 7,
      "samples": 2400, "avg_ret": 2.6, "avg_excess": 0.8, "win_rate": 57.1,
      "worst_period_ret": -9.4 }
  ]
}
```

- Evaluated on non-overlapping signal dates every `horizon` trading days, walking
  back from the last date with a forward bar, so a period is one independent look.
  Only data on or before the signal date decides membership (no look-ahead)
- Entry is the close of the day **after** the signal: signals publish at 03:00, so
  the signal day's own close, and the gap that created the signal, cannot be traded
- A period counts only with ≥ 5 member stocks. Return = close(t+1+horizon) ÷
  close(t+1) − 1, unadjusted, before costs. A stock missing either bar, or with any
  bar-to-bar move beyond ±11% while held, is excluded from that period: a single-day
  move past the limit is a corporate action, while a run of limit-downs is a real
  loss and stays in
- `avg_ret` = mean of period means; `avg_excess` = mean of (setup − baseline);
  `beat_periods` = periods above baseline; `win_rate` = stocks with a positive
  return, pooled; `worst_period_ret` = lowest period mean
- `setups`: `trend_up` 站上月季線 (close > MA20 ∧ close > MA60), `breakout` 量增突破
  (量比 ≥ 2 ∧ up day ∧ close > MA60), `near_high` 近半年高 (within 5% of the 120-day
  closing high), `pullback` 多頭回檔 (close > MA60 ∧ close 0–5% below MA20)
- empty state (too little history, missing tables):
  `{"date": "", "horizon": 20, "periods": 0, "baseline": null, "setups": []}`
- supports `ETag` + `Cache-Control` (`SIGNALS_CACHE_TTL_SECONDS`)

### `GET /api/stocks/top100`

Query params:
- `mode=volume|turnover`
- `limit=1..1000` (default `100`)

Implementation notes:
- Route name is historical; it is not limited to 100 rows
- Frontend stock UI always uses `mode=volume&limit=600`
- `market_open` is computed from current Taipei time (`Mon-Fri`, `09:00-13:30`)
- `updated_at` is the API response timestamp, not the trade-source timestamp. The
  header therefore shows its clock time only when it falls on the data `date`
  (Taipei); otherwise it shows the date alone, so a weekend request never reads as
  a trade time
- `turnover_rate` = `volume / issued shares × 100`, with issued shares from TWSE
  `t187ap03_L` plus TPEx `mopsfin_t187ap03_O`. It is `null` when the share count is
  unknown, never `0.0`; such a stock ranks last. Rows written before this rule can
  still hold `0.0`, so the frontend renders any non-positive rate as `—`
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

### `/api/settings/finmind-token`

Lets the operator set the FinMind token from the UI settings gear. The token is
write-only: no response ever contains it.

- `GET` → `{"configured": bool, "hint": "****abcd" | null}`. `configured` reflects the
  UI-set token only (the backend has no `FINMIND_TOKEN` env, so an env-only token
  shows as not configured). `hint` = last 4 chars, only when the token is >= 12 chars
- `PUT` body `{"token": "<string>"}` → same shape as GET. Token is trimmed; 422 when
  empty, containing whitespace, or longer than 512 chars
- `DELETE` → removes the UI token (falls back to env); same shape as GET
- Storage: file `FINMIND_TOKEN_FILE` (default `/app/data/.finmind_token`) on the
  data volume shared with the crawler; written `.tmp -> rename`, mode `0600`
- The crawler resolves the token at every score job / signals job (file first,
  then `FINMIND_TOKEN` env), so a change applies to the next run without restart
- The token is never logged and never accepted in a query string
- No authentication: anyone who can reach the backend can replace the token.
  Deploy on a trusted network only

### `GET /api/scores`

Behavior:
- backend only reads the newest JSON in `SCORES_DIR`
- `force=true` writes a refresh flag if no fetch is already active
- `X-FinMind-Token` header is accepted but ignored (the token comes only from the server-side store)
- `fetching=true` when `.scoring_in_progress` or `.force_refresh` exists.
  `score_job` / resume own `.scoring_in_progress`, so ALL scoring paths (nightly
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
- `fundamentals_uptrend` is a display-only derived flag, NOT part of `score`/
  `max_score`: `true` only when (a) the 3 most recent monthly revenue YoY values
  are all `> 0%`, AND (b) at least 2 of the 3 most recent quarterly EPS YoY
  values are `> 0%`; insufficient data → `false` (no tri-state)
- summary fields per stock (files written before 2026-10 carry only `score` /
  `max_score` / `fundamentals_uptrend`; the frontend treats any missing field as
  `null` and hides it — never shows a fallback `0`):
  - `eligible_count`: criteria with real data (not_applicable / 無資料 excluded)
  - `pass_rate`: `score / eligible_count * 100`, 1 decimal
  - `signal`: `strong_buy | buy | watch | neutral` (`pass_rate` ≥75 / ≥60 / ≥50 / else)
  - `signal_label`: `建議買進 | 可分批買進 | 觀察清單 | 不建議買進`; when
    `risk_score >= 2` it becomes `高風險避開` and `signal` is forced to `neutral`
  - `risk_score`: count of triggered 排雷 items; `risk_flags`: `[{category, name}]`
  - `pe`: `{current, median, p25}` from the 5-year PER history used by C9; each
    value may be `null`
- the summary never contains `criteria` / `risk_criteria` detail (polled every
  minute); detail is served by `GET /api/scores/{stock_id}`

Example:

```json
{
  "date": "2026-06-11",
  "generated_at": "2026-06-11T03:42:18+08:00",
  "scores": {
    "2330": {
      "score": 18, "max_score": 24, "fundamentals_uptrend": true,
      "eligible_count": 23, "pass_rate": 78.3,
      "signal": "strong_buy", "signal_label": "建議買進",
      "risk_score": 0, "risk_flags": [],
      "pe": { "current": 22.1, "median": 24.5, "p25": 19.8 }
    },
    "2317": { "score": 12, "max_score": 24, "fundamentals_uptrend": false }
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

### `GET /api/scores/{stock_id}`

Per-stock score detail, read on demand (watchlist expand, desktop tooltip).

- backend reads the newest file in `SCORES_DIR/details/` (memory-cached by mtime)
- `404` when no detail file exists or the stock is not in it
- `criteria` items: `{id, label, weight, pass, value, value_label, threshold, warning, not_applicable?}`
  (`pass: null` = 無資料 or not applicable)
- `risk_criteria` items: `{category, name, status, value_label, description}`

```json
{
  "date": "2026-06-11",
  "stock_id": "2330",
  "criteria": [
    { "id": "roe", "label": "ROE (TTM) > 12%", "weight": 2, "pass": true,
      "value": 28.1, "value_label": "28.1%", "threshold": "> 12%", "warning": null }
  ],
  "risk_criteria": []
}
```

### `GET /api/scores/{stock_id}/history`

The stock's score across the retained score files (at most 7), oldest first.

```json
{
  "stock_id": "2330",
  "points": [
    { "date": "2026-10-22", "score": 17, "eligible_count": 23, "pass_rate": 73.9,
      "signal": "buy", "risk_score": 0 }
  ]
}
```

- files that lack the stock are skipped (no gap filling here); legacy entries have
  `null` for fields they never stored; corrupt files are skipped
- a score file can carry a stock's previous entry when a run did not re-score it
  (`crawler/main.py` merges onto the prior baseline), so a flat stretch may mean "not
  re-scored", not "unchanged"
- unknown stock → `200` with `points: []`
- per-file memory cache keyed by path + mtime

### `GET /api/watchlist`

自選股（單一使用者、區網部署，與其他 API 一樣不做驗證）。

```json
{
  "items": [
    {
      "stock_id": "2330",
      "note": "等回測月線再加碼",
      "added_at": "2026-10-26T09:12:00+08:00",
      "quote": {
        "stock_id": "2330", "name": "台積電", "rank": 1, "volume": 45000000,
        "turnover_rate": 0.82, "price_change_pct": 2.35, "color_tier": "light_red",
        "close_price": 950.0, "sector": "半導體"
      }
    }
  ]
}
```

- items ordered by `added_at` ascending
- `quote` = the stock's row on the latest trading date in `stock_ranks` (same
  fields as a `/api/stocks/top100` stock + `sector`, `rank` = `volume_rank`);
  works for stocks outside the 600 display pool; `null` when the stock has no
  row on that date

### `PUT /api/watchlist/{stock_id}`

- body (optional): `{"note": "..."}`; `note` max 500 chars (`422` beyond)
- upsert: re-PUT keeps `added_at`, replaces `note` only when provided
- `404` when `stock_id` has no row on the latest trading date in `stock_ranks`
- `409` when adding a new stock would exceed `WATCHLIST_MAX` (default `30`)
- returns the item (same shape as a `GET` item)

### `DELETE /api/watchlist/{stock_id}`

- `204`, also when the stock was not in the watchlist

### `GET /api/signals`

每日盤後籌碼 + 技術／量能指標 for the signal universe (`volume_rank <=
SCORE_CANDIDATE_LIMIT` ∪ watchlist). Computed by the crawler into `stock_signals`;
the backend only reads it.

```json
{
  "date": "2026-10-23",
  "generated_at": "2026-10-23T17:34:10+08:00",
  "signals": {
    "2330": {
      "close": 1045.0,
      "avg_volume_5d": 41000000, "vol_ratio": 1.10,
      "ma20": 1010.5, "ma60": 980.2,
      "above_ma20": true, "above_ma60": true,
      "high_52w": 1100.0, "pct_from_52w_high": -5.0,
      "inst_net_5d": 12500, "inst_streak": 3,
      "foreign_net_1d": 3200, "trust_net_1d": 400
    }
  }
}
```

- units: volumes in shares (same as `/api/stocks/top100`), institutional nets in
  張; `inst_*` = 外資（不含外資自營商）+ 投信
- `vol_ratio` = trade-date volume ÷ mean of the previous 5 trading days
- `high_52w` = highest **close** of the last 240 trading days (`null` with fewer bars)
- `inst_streak` = consecutive days the 外資+投信 net kept the same sign (+N 連買 /
  −N 連賣 / 0 when the latest day nets to 0); bounded by `SIGNALS_INST_KEEP_DAYS`
- insufficient history → that field is `null`, never `0`; if the stock has no bar
  on `date` every price field is `null`, if `date` has no institutional data every
  `inst_*` field is `null`
- `above_ma20` / `above_ma60` are derived by the backend from `close` (null-safe)
- empty state (table missing / no rows): `{"date": "", "generated_at": "", "signals": {}}`
- supports `ETag` + `Cache-Control` (`SIGNALS_CACHE_TTL_SECONDS`, default `60`);
  the frontend fetches on load and every 5 minutes

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
| `nightly` | every day `03:00` | only if the previous calendar day was a trading day: daily signals → buy-score batch (sequential) |
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

- Candidate pool: `volume_rank <= SCORE_CANDIDATE_LIMIT` ∪ `watchlist` stocks
  (watchlist stocks outside the pool are appended after the volume-ordered pool;
  a missing `watchlist` table is treated as empty)
- Delay between stocks: `BUY_SCORE_REQUEST_DELAY`
- Delay between datasets: `BUY_SCORE_FETCH_DELAY`
- Quota exhaustion: wait `BUY_SCORE_QUOTA_WAIT_S`, then resume only missing names
- Partial persistence: write every 50 successful scores
- Full-fetch failure for a stock: do not persist `0/24`
- File retention: keep latest 7 JSON files
- Detail persistence: every summary write also writes
  `SCORES_DIR/details/YYYY-MM-DD.json` (`{stock_id: {criteria, risk_criteria}}`).
  Stocks carried over from the baseline keep their previous detail; detail is
  written before the summary, both `.tmp -> rename`, latest 7 kept. `details/`
  is a subdirectory so summary globbing (`SCORES_DIR/*.json`) never sees it
- Orphan recovery: a `.scoring_in_progress` left by a crashed run is cleared once
  older than `SCORING_FLAG_STALE_S` (crawler on startup + every-minute watch job;
  backend ignores it for `fetching` past the same age)
- Frontend buy-score view: progress bar + "評分更新 <date> <time>" in the topbar;
  each card shows 訊號徽章 ｜ 通過率（大字 + 進度條）｜ 分數 `score/eligible_count`
  ｜ 價格 ｜ 週轉率 ｜ 漲跌幅 ｜ 指標 chips. Card background follows `signal`
  (金／青／灰藍／暗灰／紫斜紋 — never red/green); volume / turnover views keep the
  price-change heat tint but show the same badge + chips. Clicking a card opens the
  stock panel (Enter / Space on keyboard)
- Card typography: minimum `0.7rem`; elements that do not fit are hidden (narrow
  cards: chip text + sector hidden, signal badge becomes a 4px left bar)
- `fundamentals_uptrend`: derived indicator, computed in `buy_score_engine.py`
  from the same monthly-revenue and quarterly-EPS series used by the
  `revenue_yoy` / `eps_yoy` criteria, but with a stricter all-3-months-positive
  rule for revenue; not scored, shown as a 轉強 chip on the card

## Nightly schedule (`crawler/main.py::nightly_job`)

Data need not be real-time (user decision 2026-10-26). Every day at `03:00`:

1. fetch the official TWSE / TPEx close feeds; there is work to do iff the TWSE
   feed reports a trade date newer than the last one processed
   (`MAX(stock_signals.date)`; never processed counts as newer). TWSE unreachable →
   fall back to "the latest `stock_ranks` date is yesterday". Otherwise do nothing —
   weekends and holidays produce no new date, so no trading calendar is maintained.
   The OpenAPI feed publishes after 03:00 (on Saturday 03:00 it still reports
   Thursday), so comparing it with yesterday can never match: a run covers the newest
   date the feed reports, typically the session before last
2. daily signals for that trade date (below)
3. `score_job()` — full candidate-pool recompute for the new run date
   (~80–90 min within the 6000 req/h FinMind tier); failures in step 2 do not
   block step 3

Scoring runs are single-flight (`_SCORE_LOCK`): a force refresh or quota-resume
that starts while another scoring run is active skips (resume re-queues its
state). There is no startup catch-up; after a fresh deploy signals appear
after the next nightly run.

## Daily signal rules (`crawler/signals.py`)

- Trade date = date reported by the official TWSE `STOCK_DAY_ALL` / TPEx daily
  close feeds (not "yesterday": see Nightly schedule). Bars come only from a feed whose date equals the trade date
  (never from `stock_ranks`, whose intraday/Yahoo fallback rows can carry a stale
  close under today's date)
- 三大法人: TWSE `rwd/zh/fund/T86?date=YYYYMMDD&selectType=ALLBUT0999` (上市) and
  TPEx `www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=YYYY/MM/DD` (上櫃),
  whole market per request, 3–5 s apart; shares converted to 張
- Missing institutional dates within the last `SIGNALS_INST_KEEP_DAYS` trading
  dates are fetched each run (first run ≈ 40 requests, then 2 per day)
- Bar backfill: a universe stock with < 240 bars in the last 380 days is
  backfilled from FinMind `TaiwanStockPrice` (1 year), at most once per 30 days
  per stock (`signal_backfill` marker), `SIGNALS_BACKFILL_DELAY` apart; committed
  per stock so an interrupted run resumes; FinMind quota error stops the
  backfill for this run only
- Bars are written only when TWSE and TPEx report the same trade date
- A run is complete when `stock_signals.date` = trade date **and** `inst_flows`
  has rows for it; re-runs for that date are no-ops. Closes are not adjusted for
  dividends (small MA distortion around ex-dividend dates)
- Tables are created by the crawler (`CREATE TABLE IF NOT EXISTS`):

```sql
daily_bars     (stock_id, date, close, volume, PRIMARY KEY (stock_id, date))
inst_flows     (stock_id, date, foreign_net, trust_net, dealer_net, PRIMARY KEY (stock_id, date))
stock_signals  (stock_id PRIMARY KEY, date, generated_at, close, avg_volume_5d, vol_ratio,
                ma20, ma60, high_52w, pct_from_52w_high,
                inst_net_5d, inst_streak, foreign_net_1d, trust_net_1d)
signal_backfill(stock_id PRIMARY KEY, bars_at)
```

## Data retention

| Data | Retention |
|---|---|
| `stock_ranks` | latest 7 trading dates |
| `etf_ranks` | latest `ETF_KEEP_DAYS` trading dates, default `90` |
| `watchlist` | user-managed, no pruning |
| `daily_bars` | latest `SIGNALS_BAR_KEEP_DAYS` trading dates, default `260` |
| `inst_flows` | latest `SIGNALS_INST_KEEP_DAYS` trading dates, default `20` |
| `stock_signals` | latest trade date only (rebuilt each run) |
| `buy_scores/*.json` | latest 7 files |
| `buy_scores/details/*.json` | latest 7 files |

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | implementation-specific | SQLite location |
| `FINMIND_TOKEN` | `""` | fallback buy-score token (crawler env) |
| `FINMIND_TOKEN_FILE` | `/app/data/.finmind_token` | UI-set token file shared by backend (writes) and crawler (reads); takes precedence over env |
| `SCORES_DIR` | `/app/data/buy_scores` | shared score JSON directory |
| `SCORE_CANDIDATE_LIMIT` | `600` | score candidate pool limit (also the daily-signal universe) |
| `BUY_SCORE_REQUEST_DELAY` | `1.2` | delay between stocks |
| `BUY_SCORE_FETCH_DELAY` | `0.4` | delay between FinMind datasets |
| `BUY_SCORE_QUOTA_WAIT_S` | `3600` | wait after quota exhaustion |
| `BUY_SCORE_QUOTA_MAX_CYCLES` | `24` | legacy bound; quota-resume currently loops without an enforced upper limit until all stocks are scored |
| `SCORING_FLAG_STALE_S` | `10800` | age after which `.scoring_in_progress` / `.force_refresh` are treated as orphaned and cleared (backend + crawler) |
| `BUY_SCORE_GOODINFO_ENABLED` | `false` | optional Goodinfo scoring inputs |
| `ETF_KEEP_DAYS` | `90` | ETF history retention |
| `WATCHLIST_MAX` | `30` | watchlist size limit |
| `SIGNALS_BAR_KEEP_DAYS` | `260` | `daily_bars` retention (trading dates) |
| `SIGNALS_INST_KEEP_DAYS` | `20` | `inst_flows` retention (trading dates) |
| `SIGNALS_BACKFILL_DELAY` | `1.0` | seconds between FinMind price backfills |
| `SIGNALS_CACHE_TTL_SECONDS` | `60` | `/api/signals` ETag/cache TTL |
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
| Backend analytics | `pytest` | breadth, sector rotation, setup validation (no look-ahead) |
| Backend integration | `pytest` | seeded DB + score files through every read endpoint |
| Frontend | `vitest` | store, composables, sorting, rendering helpers, analysis, sizing |
| Frontend integration | `vitest` | full app mount against a contract-shaped fake API |

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
