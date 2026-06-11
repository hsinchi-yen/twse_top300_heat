# Frontend

Vue 3 + Vite dashboard for the TWSE heatmap kiosk.

## What it does

- Stock display pool: fixed `480` names fetched from `/api/stocks/top100?mode=volume&limit=480`
- Client-side stock modes:
  - `volume` — keep backend order
  - `turnover` — re-sort the same 480 names by `turnover_rate`
  - `buy_score` — re-sort the same 480 names by crawler-generated buy score
- ETF mode: separate `/api/etf?sort_by=turnover|asset_scale&limit=300`
- Responsive paging:
  - desktop `6x6`, `5x5`, `4x4`
  - mobile `2x2`, `2x3`, `3x3`

## Development

```bash
cd frontend
npm install
npm run dev
```

This project's served frontend endpoint is [http://localhost:8504](http://localhost:8504). If you run raw `npm run dev`, Vite may still use its own default development port unless separately configured.

## Test

```bash
cd frontend
npm run test
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE` | `""` | API base URL; empty means same-origin `/api/...` |
| `VITE_EMBEDDED` | `false` | Enables tighter kiosk spacing when set to `true` |

## Key files

| Path | Purpose |
|---|---|
| `src/constants.js` | `MAX_STOCKS=480` and mobile density presets |
| `src/composables/useStockData.js` | Stock polling, backoff, visibility/online handling |
| `src/composables/useEtfData.js` | ETF polling and sort-mode refresh |
| `src/composables/useScoreData.js` | Buy-score fetch + progressive refresh polling |
| `src/stores/stockStore.js` | Shared dashboard state |
| `src/components/HeatmapGrid.vue` | Stock paging, search, client-side reordering |
| `src/components/EtfGrid.vue` | ETF grid |
| `src/components/ModeToggle.vue` | `volume` / `turnover` / `etf` / `buy_score` switch |

## Notes

- `X-FinMind-Token` may still be sent by the frontend for compatibility, but the current backend ignores it; buy-score computation uses crawler-side `FINMIND_TOKEN`.
- `updated_at` in stock and ETF responses is the API response timestamp, while `date` is the underlying trade date.
