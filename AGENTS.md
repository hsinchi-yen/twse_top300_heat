# Twse_Top100_Heat — Agent Configuration

## Agent skills

### Issue tracker

Issues live on GitHub Issues and are managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default mattpocock/skills label vocabulary (no overrides). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — `CLAUDE.md` (key rules) + `SPEC.md` (full spec) + `improve.md` (long-run stability notes). See `docs/agents/domain.md`.

## Critical Knowledge

Read `CLAUDE.md` first for key architecture decisions and rules before modifying any file.

Key invariants:
- Buy-score computation lives in `crawler/` and uses `FINMIND_TOKEN` env only; backend `GET /api/scores` only serves JSON + force-refresh flags
- Score refresh writes via `.tmp -> rename`; never delete the current cache first
- Frontend stock view always fetches `/api/stocks/top100?mode=volume&limit=480`; turnover and buy-score ordering are frontend-only over that same display pool
- ETF mode is separate and fetches `/api/etf?sort_by=turnover|asset_scale&limit=300`
- See `SPEC.md` for the current API contract, schedules, and environment variables
