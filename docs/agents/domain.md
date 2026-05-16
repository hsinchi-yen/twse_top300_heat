# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — domain glossary, key concepts, and architectural decisions for this project.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront.

## File structure

Single-context repo:

```
/
├── CONTEXT.md          ← domain glossary + project context
├── AGENTS.md           ← agent configuration
├── docs/
│   ├── agents/         ← skill configuration (issue tracker, labels, domain)
│   └── adr/            ← architectural decision records
├── frontend/           ← Vue3 + Vite + ECharts
├── backend/            ← FastAPI + SQLite
├── crawler/            ← Python data fetcher (TWSE/TPEX + FinMind)
└── docker-compose.yml
```

## Domain glossary (key terms)

- **週轉率 (Turnover Rate)** — 成交量 / 流通股數 × 100，衡量籌碼活躍度
- **成交量 (Volume)** — 當日成交股數
- **漲跌幅 (Price Change %)** — (今日收盤 - 昨日收盤) / 昨日收盤 × 100
- **題材 (Sector/Theme)** — 市場定義的概念性分類（AI、散熱、機器人、重電、航運、PCB、半導體、其他）
- **熱力圖 (Heatmap)** — 以格子排列呈現 Top 100 股票，顏色代表漲跌幅，位置代表排名
- **Top 100** — 依指定指標（成交量或週轉率）排名前 100 名的股票
- **爆量 (Volume Spike)** — 成交量異常放大，超過移動平均的特定倍數

## Use the glossary's vocabulary

When naming issues, tests, API endpoints, or database columns, use the terms as defined above. Don't drift to synonyms (e.g. use `turnover_rate`, not `churn_rate` or `circulation_rate`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0001 (TWSE as primary data source) — but worth reopening because…_
