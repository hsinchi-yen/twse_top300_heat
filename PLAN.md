# PLAN.md — 台股前100熱力圖 開發計劃

> 對應 spec: `SPEC.md`
> 更新時間: 2026-05-16

## 垂直 Slice 清單

每個 Slice 是一個端對端可獨立驗證的薄切片。依賴順序執行。

---

### Slice 1 — Docker Compose 骨架 + 三服務健康確認
**Type:** AFK | **Blocked by:** —

**What to build:**
建立 `docker-compose.yml`，定義 `frontend`、`backend`、`crawler` 三個 service。
各服務用最小可運行的骨架（frontend: nginx serve static, backend: FastAPI root endpoint, crawler: Python hello loop）。

**Acceptance criteria:**
- [ ] `docker compose up -d` 無報錯啟動
- [ ] `docker compose ps` 三個服務狀態均為 `healthy`
- [ ] `curl http://localhost:8000/health` 回傳 `{"status": "ok"}`
- [ ] `curl http://localhost:5173` 回傳前端首頁 HTML

---

### Slice 2 — SQLite schema 初始化 + sector_map 種子資料
**Type:** AFK | **Blocked by:** #1

**What to build:**
在 backend 建立 SQLAlchemy models 與 Alembic migration（或直接 `create_all`）。
初始化 `stock_ranks` 與 `sector_map` 兩張表。
寫入 7 個題材的種子資料（AI、散熱、機器人、重電、航運、PCB、半導體）及已知股票對應。

**Acceptance criteria:**
- [ ] `docker compose up backend` 後 SQLite 自動建表
- [ ] `sector_map` 含至少 20 筆種子資料（各題材各有代表股票）
- [ ] pytest `test_ranker.py` — DB 可讀寫 `stock_ranks`
- [ ] 未在 `sector_map` 的股票查詢時回傳 sector=`其他`

---

### Slice 3 — Crawler: TWSE + TPEX + FinMind 週轉率 → 寫入 DB
**Type:** AFK | **Blocked by:** #2

**What to build:**
Crawler service 實作三個 source client：
- `twse.py` — 抓 TWSE 全市場當日成交資料
- `tpex.py` — 抓 TPEX 上櫃全市場當日成交資料
- `finmind.py` — 每日一次取股本資料（發行股數），計算週轉率

`processor.py` 合併 TWSE + TPEX，計算：
- 成交量排名（volume_rank）
- 週轉率 = 成交量 / 發行股數 × 100，取排名（turnover_rank）
- 漲跌幅色階（color_tier）

APScheduler 每 60 秒（盤中）執行一次，UPSERT 進 `stock_ranks`。
收盤後（16:30 後）停止 polling。

**Acceptance criteria:**
- [ ] `pytest test_processor.py` — 給定 mock TWSE + TPEX + FinMind 資料，processor 正確計算 volume_rank, turnover_rank, color_tier
- [ ] `pytest test_processor.py` — 週轉率公式正確（volume / issue_shares × 100）
- [ ] `pytest test_processor.py` — color_tier 邊界值正確（±1%, ±5%）
- [ ] Crawler 實際執行後 `stock_ranks` 有資料寫入
- [ ] TWSE + TPEX 請求間有 1-3 秒隨機 delay

---

### Slice 4 — FastAPI: `GET /api/stocks/top100` endpoint
**Type:** AFK | **Blocked by:** #2

**What to build:**
實作 `/api/stocks/top100?mode=volume|turnover` endpoint。
從 `stock_ranks` 取當日最新資料，join `sector_map`，
按 mode 排序取前 100，依題材分組，回傳 SPEC.md 定義的 JSON shape。

**Acceptance criteria:**
- [ ] `pytest test_stocks_api.py` — `?mode=volume` 回傳正確 shape，stocks 依 volume_rank 排序
- [ ] `pytest test_stocks_api.py` — `?mode=turnover` stocks 依 turnover_rank 排序
- [ ] `pytest test_stocks_api.py` — sectors 欄位包含所有 8 個題材（含「其他」）
- [ ] `pytest test_stocks_api.py` — `market_open` 欄位在 09:00-16:30 為 true
- [ ] `curl http://localhost:8000/api/stocks/top100?mode=volume` 實際回傳正確 JSON

---

### Slice 5 — Frontend: Vite + Vue3 骨架 + ModeToggle UI
**Type:** AFK | **Blocked by:** #1

**What to build:**
用 Vite 初始化 Vue3 + Pinia 專案。
實作 `ModeToggle.vue`：兩個按鈕「成交量」/「週轉率」，切換時 emit `mode-change`。
建立 `stockStore.js` Pinia store：管理 `mode`、`sectors`、`lastUpdated`、`marketOpen`。

**Acceptance criteria:**
- [ ] `npm run dev` 無報錯啟動
- [ ] `ModeToggle.vue` Vitest — 點擊「週轉率」按鈕 emit `mode-change` 帶值 `'turnover'`
- [ ] `stockStore` Vitest — `setMode('volume')` 正確更新 state
- [ ] 頁面渲染出兩個切換按鈕，active 狀態有視覺差異

---

### Slice 6 — Frontend: HeatmapGrid — 固定格子 + 5段色階
**Type:** AFK | **Blocked by:** #4 #5

**What to build:**
實作 `StockCell.vue`：顯示股票代號、名稱、漲跌幅%。
格子大小固定（CSS grid），背景色根據 `color_tier` prop 套用 5 段色階。
實作 `colorTier.js` 純函式：`getColorTier(pct) -> color_tier string`。
`HeatmapGrid.vue` 將 API 回傳的 sectors/stocks 渲染成格子群。

**Acceptance criteria:**
- [ ] `colorTier.js` Vitest — 邊界值全過（+5%, +1%, 0%, -1%, -5%）
- [ ] `StockCell.vue` Vitest — `color_tier='deep_red'` 套用正確 CSS class
- [ ] `StockCell.vue` Vitest — 漲跌幅顯示 `+2.35%` 格式（含正號）
- [ ] 100 個格子在畫面上全部可見，不溢出

---

### Slice 7 — Frontend: SectorBlock — Treemap 分區排版
**Type:** AFK | **Blocked by:** #6

**What to build:**
實作 `SectorBlock.vue`：顯示題材名稱標題 + 該題材的所有 `StockCell`。
`HeatmapGrid.vue` 按 API 回傳的 sectors 順序渲染各 `SectorBlock`。
題材區塊有視覺分隔（border 或 background）。

**Acceptance criteria:**
- [ ] 8 個題材區塊（含「其他」）各自有標題
- [ ] 各題材的股票正確歸屬在對應區塊下
- [ ] Dark mode 配色符合 PRD（背景深色，文字清晰）
- [ ] 畫面在 1920×1080 解析度下排版正確

---

### Slice 8 — Frontend: 60 秒 polling + 收盤鎖定邏輯
**Type:** AFK | **Blocked by:** #6

**What to build:**
`useStockData.js` composable 實作：
- 每 60 秒 fetch `/api/stocks/top100?mode={mode}`，更新 Pinia store
- API 回傳 `market_open: false` 時停止 polling，顯示「已收盤」badge
- mode 切換時立即重新 fetch（不等 60 秒）

**Acceptance criteria:**
- [ ] `useStockData` Vitest（mock fetch）— 60 秒後觸發第二次 fetch
- [ ] `useStockData` Vitest — `market_open: false` 時 polling 停止
- [ ] `useStockData` Vitest — mode 切換時立即 fetch
- [ ] 頁面左下角顯示「最後更新：HH:MM:SS」時間戳
- [ ] 收盤後顯示「今日已收盤」badge

---

### Slice 9 — E2E: Docker Compose 一鍵啟動驗收
**Type:** HITL | **Blocked by:** 全部

**What to build:**
手動驗收 checklist — 確認整個系統端對端正常運作。

**Acceptance criteria:**
- [ ] `docker compose up -d` 三服務全部健康
- [ ] 瀏覽器開啟 `http://localhost:5173`，熱力圖正確渲染
- [ ] 切換「週轉率」/「成交量」模式，格子排序改變
- [ ] 等待 60 秒，資料自動刷新（時間戳更新）
- [ ] 在非交易時間訪問，顯示「已收盤」badge

---

## Phase 2（MVP 後）

- Slice 10: `GET/PUT /api/sectors` 後台維護 Web UI
- Slice 11: 爆量閃爍視覺效果
- Slice 12: AI 新聞情緒分析整合
- Slice 13: 多設備管理 / MQTT

---

## 資料來源優先順序

1. **TWSE OpenAPI** — 上市市場成交量排行（主要）
2. **TPEX OpenAPI** — 上櫃市場成交量排行（合併）
3. **FinMind SDK** — 股本/發行股數（每日一次，計算週轉率分母）
