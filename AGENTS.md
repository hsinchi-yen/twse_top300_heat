# Twse_Top100_Heat — Agent Configuration

## Agent skills

### Issue tracker

Issues live on GitHub Issues and are managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default mattpocock/skills label vocabulary (no overrides). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — `CLAUDE.md` (key rules) + `SPEC.md` (full spec) + `improve.md` (long-run stability conditions) + `docs/adr/`. See `docs/agents/domain.md`.

## Critical Knowledge

Read `CLAUDE.md` first for key architecture decisions and rules before modifying any file.
Key invariants:
- Token → `X-FinMind-Token` header only, never query string
- Score refresh → atomic `.tmp → rename`, never delete-then-write
- Frontend always fetches `mode=volume&limit=360`; turnover re-sort is frontend-only
- See `SPEC.md` for full API contract and environment variables
