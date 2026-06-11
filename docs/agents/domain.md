# Domain Docs

How engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- `CLAUDE.md` — current architecture decisions, invariants, and test commands
- `SPEC.md` — current API contract, schedules, deployment assumptions, and env vars
- `improve.md` — long-run stability notes and remaining hardening backlog

If `docs/adr/` exists and clearly matches the area you're changing, read only the relevant ADRs. If it does not exist, proceed silently.

## File structure

Single-context repo:

```text
/
├── AGENTS.md
├── CLAUDE.md
├── SPEC.md
├── improve.md
├── docs/
│   ├── agents/
│   └── adr/            ← optional; may be absent
├── backend/            ← FastAPI + SQLite API
├── crawler/            ← TWSE/TPEX/Yahoo/FinMind fetch + buy-score engine
├── frontend/           ← Vue 3 + Vite dashboard
├── embedded_deployment/
├── docker-compose.yml
└── run_containers.sh
```

## Domain glossary

- `顯示池 (display pool)` — 前端股票主畫面固定使用 `mode=volume&limit=480`
- `成交量模式 (volume mode)` — 依 backend 回傳的 `volume_rank` 顯示
- `週轉率模式 (turnover mode)` — 前端以同一批 480 檔依 `turnover_rate` 重新排序
- `買進評分模式 (buy_score mode)` — 前端以 crawler 產生的 `{score, max_score}` 重新排序
- `評分候選池 (score candidate pool)` — `volume_rank <= SCORE_CANDIDATE_LIMIT`，預設 480，硬上限 1000
- `強制刷新 (force refresh)` — backend 寫入 `buy_scores/.force_refresh`，crawler 偵測後跑 `score_job(force=True)`
- `評分進行中 (fetching)` — `buy_scores/.scoring_in_progress` 或 `.force_refresh` 旗標存在
- `ETF 模式` — 獨立走 `/api/etf`，排序維度為 `turnover` 或 `asset_scale`
- `legacy endpoint name` — `/api/stocks/top100` 只是歷史路徑名稱，實際 `limit` 可到 1000，前端固定取 480

## Use the glossary's vocabulary

When naming issues, tests, API notes, or docs, prefer the project's current terms:
- use `turnover_rate`, not alternative English synonyms
- say `display pool 480`, not `Top 100` or `Top 360`
- distinguish `trade date` from API `updated_at`

## Flag contract conflicts

If your planned change contradicts `CLAUDE.md` or `SPEC.md`, surface it explicitly instead of silently overriding the docs.
