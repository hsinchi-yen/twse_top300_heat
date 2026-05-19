# Spec: 台股前100熱力圖 (TWSE Top 100 Heatmap Dashboard)

## Objective

建立一個以 **週轉率 / 成交量 Top 100** 為核心的台股熱力圖 Dashboard，可切換兩種排名視角，按題材分區塊呈現，顏色代表漲跌幅。系統以 Docker Compose 部署，支援 Embedded Linux Kiosk 環境，每 60 秒自動更新盤中資料，收盤後鎖定終值。

### Target Users
- **Trader / 投資人** — 快速掌握當日資金動向與題材輪動
- **Technical Manager** — 一眼看懂市場熱點與異常爆量
- **Embedded Engineer** — 部署於工業電腦 Kiosk 長時間穩定運行

### Success Criteria
- [ ] 開啟 Dashboard < 3 秒（首屏 LCP）
- [ ] 盤中資料每 60 秒自動刷新，無需手動操作
- [ ] 可在「成交量 Top 100」與「週轉率 Top 100」兩種模式間切換，動畫流暢
- [ ] 100 個格子固定大小，按題材分區塊（Treemap 風格）排列
- [ ] 5 段色階正確反映漲跌幅（深紅/淺紅/灰/淺綠/深綠）
- [ ] 收盤後（16:30 後）資料自動鎖定，不再刷新
- [ ] Docker Compose `docker compose up -d` 一鍵啟動，三個服務全部健康

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Vue 3 + Vite | Vue 3.4+, Vite 5+ |
| Chart | Apache ECharts | 5.x |
| Backend | FastAPI | 0.110+ |
| Database | SQLite (via SQLAlchemy) | — |
| Scheduler | APScheduler | 3.x |
| Data Source | TWSE OpenAPI + TPEX OpenAPI | — |
| Data Source | FinMind SDK | 最新 |
| Container | Docker Compose | v2 |
| Runtime | Python 3.11+ | — |

---

## Commands

```bash
# 開發
docker compose up -d              # 啟動所有服務
docker compose logs -f backend    # 看後端 log
docker compose logs -f crawler    # 看爬蟲 log
docker compose down               # 停止

# 前端獨立開發
cd frontend && npm install
npm run dev                       # http://localhost:8504

# 後端獨立開發
cd backend && pip install -r requirements.txt
uvicorn main:app --reload         # http://localhost:8000

# 測試
cd backend && pytest -v
cd frontend && npm run test       # Vitest

# 建置
cd frontend && npm run build      # 產生 dist/
docker compose build              # 重新 build images
```

---

## Project Structure

```
Twse_Top100_Heat/
├── docker-compose.yml
├── AGENTS.md
├── CONTEXT.md
├── SPEC.md                       # 本文件
├── frontend/                     # Vue3 + Vite + ECharts
│   ├── src/
│   │   ├── components/
│   │   │   ├── HeatmapGrid.vue   # 主熱力圖格子元件
│   │   │   ├── SectorBlock.vue   # 題材區塊元件
│   │   │   ├── StockCell.vue     # 單一股票格子
│   │   │   └── ModeToggle.vue    # 成交量/週轉率切換
│   │   ├── composables/
│   │   │   └── useStockData.js   # 資料 fetch + polling 邏輯
│   │   ├── stores/
│   │   │   └── stockStore.js     # Pinia store
│   │   ├── App.vue
│   │   └── main.js
│   ├── vite.config.js
│   └── package.json
├── backend/                      # FastAPI
│   ├── main.py
│   ├── routers/
│   │   ├── stocks.py             # GET /api/stocks/top100
│   │   └── sectors.py            # GET /api/sectors, PUT /api/sectors/{id}
│   ├── models/
│   │   ├── stock.py
│   │   └── sector.py
│   ├── services/
│   │   └── ranker.py             # 排名計算邏輯
│   ├── database.py
│   ├── requirements.txt
│   └── tests/
│       ├── test_ranker.py
│       └── test_stocks_api.py
├── crawler/                      # 資料爬取排程
│   ├── main.py                   # APScheduler entry
│   ├── sources/
│   │   ├── twse.py               # TWSE OpenAPI client
│   │   ├── tpex.py               # TPEX OpenAPI client
│   │   └── finmind.py            # FinMind SDK wrapper
│   ├── processor.py              # 合併排名、計算週轉率
│   ├── requirements.txt
│   └── tests/
│       └── test_processor.py
├── docs/
│   ├── agents/
│   └── adr/
└── Reference/
```

---

## Code Style

### Python (backend / crawler)
```python
async def get_top100_by_volume(db: Session, date: str) -> list[StockRank]:
    """取得指定日期成交量前 100 名，依成交量降冪排序。"""
    return (
        db.query(StockRank)
        .filter(StockRank.date == date)
        .order_by(StockRank.volume.desc())
        .limit(100)
        .all()
    )
```

### Vue 3 (frontend)
```vue
<script setup>
const props = defineProps({
  mode: { type: String, required: true }, // 'volume' | 'turnover'
})
const emit = defineEmits(['mode-change'])
</script>
```

### 命名規範
- DB 欄位：`snake_case`（`turnover_rate`, `price_change_pct`）
- API endpoint：`/api/stocks/top100?mode=volume`
- Vue component：`PascalCase`
- JS 變數：`camelCase`

---

## Testing Strategy

| Layer | Framework | 覆蓋重點 |
|-------|-----------|---------|
| Backend unit | pytest | `ranker.py` 排名計算邏輯、週轉率公式 |
| Backend API | pytest + httpx | `/api/stocks/top100` response shape |
| Crawler unit | pytest | TWSE/TPEX/FinMind parser、processor 合併邏輯 |
| Frontend unit | Vitest | `useStockData` composable、顏色計算函式 |
| E2E | 手動 Chromium | 熱力圖渲染、模式切換動畫 |

- Coverage 目標：backend ≥ 80%、crawler ≥ 80%
- 每個 commit 前跑 `pytest`

---

## Data Flow

```
每 60 秒（盤中）or 每日 16:00（收盤後）
          │
    ┌─────▼──────┐
    │  crawler   │  TWSE/TPEX API → 成交量排行
    │            │  FinMind SDK  → 股本 → 週轉率
    └─────┬──────┘
          │ INSERT/UPDATE
    ┌─────▼──────┐
    │   SQLite   │  stock_ranks + sector_map
    └─────┬──────┘
          │ query
    ┌─────▼──────┐
    │  FastAPI   │  GET /api/stocks/top100?mode=volume|turnover
    └─────┬──────┘
          │ HTTP polling（每 60 秒）
    ┌─────▼──────┐
    │   Vue 3    │  Pinia → HeatmapGrid → SectorBlock → StockCell
    └────────────┘
```

---

## API Contract

### `GET /api/stocks/top100?mode=volume|turnover`
```json
{
  "mode": "volume",
  "date": "2026-05-16",
  "market_open": true,
  "updated_at": "2026-05-16T10:30:00+08:00",
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
          "color_tier": "light_red"
        }
      ]
    }
  ]
}
```

---

## Color Tier Mapping

| `color_tier` | 條件 | 顯示色 |
|---|---|---|
| `deep_red` | 漲幅 ≥ +5% | `#C62828` |
| `light_red` | +1% ≤ 漲幅 < +5% | `#EF5350` |
| `neutral` | -1% < 漲跌幅 < +1% | `#424242` |
| `light_green` | -5% < 跌幅 ≤ -1% | `#43A047` |
| `deep_green` | 跌幅 ≤ -5% | `#1B5E20` |

---

## SQLite Schema

```sql
CREATE TABLE stock_ranks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id TEXT NOT NULL,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    volume INTEGER,
    turnover_rate REAL,
    price_change_pct REAL,
    color_tier TEXT,
    volume_rank INTEGER,
    turnover_rank INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, date)
);

CREATE TABLE sector_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id TEXT NOT NULL UNIQUE,
    sector TEXT NOT NULL DEFAULT '其他'
);
```

---

## Boundaries

- **Always:**
  - 跑 `pytest` 通過後才 commit
  - API response 維持已定義的 contract shape
  - 爬蟲只在盤中每 60 秒及 16:00 收盤後各跑
  - TWSE/TPEX API 請求加 1-3 秒隨機 delay

- **Ask first:**
  - 修改 SQLite schema
  - 新增 Python / npm 套件
  - 更改 Docker Compose port 設定
  - 新增 API endpoint

- **Never:**
  - 硬編碼 API key 或 token
  - 在測試中跳過失敗的 assert
  - 高頻率全市場爬蟲（> 每分鐘一次）

---

## Open Questions

1. **FinMind token** — 是否有付費 token？股本資料每日只取一次，不跟 60 秒 polling
2. **後台維護介面** — 是否需要 Web UI 編輯題材對照表，還是直接操作 SQLite？
3. **爆量閃爍** — MVP 就做還是 Phase 2？
4. **TPEX 上櫃** — MVP 是否只做上市（TWSE），上櫃之後再補？

---

## Feature: 買入評分 (Buy Score)

### 目標
在每支股票卡片名稱旁顯示來自 StockAnalysisDashBoard 的買入評分（如 `台積電 - 18/24`），協助使用者快速判斷買入強度，不額外消耗本專案的 FinMind token。

### 決策紀錄
| 問題 | 決策 | 原因 |
|------|------|------|
| 資料來源 | 代理 StockAnalysisDashBoard API | 評分邏輯已實作，不重複建置；StockAnalysisDashBoard 有自己的 FinMind daily cache |
| 儲存方式 | JSON 檔案 `data/buy_scores/YYYY-MM-DD.json` | 不動 DB schema；簡單、可檢視、易回溯 |
| 計算時機 | 每工作日 16:05（收盤後 5 分鐘） | 一天一次，法人資料盤後才完整 |
| 顯示格式 | `股票名稱 - score/max_score`（如 `台積電 - 18/24`） | 最精簡，卡片空間有限 |
| 無資料處理 | 顯示 `N/A` | 財報不完整或 API 失敗的股票 |
| 盤中顯示 | 顯示昨日分數（最新可用 JSON） | 不延誤頁面載入 |
| ETF 頁面 | 不顯示 | ETF 無個股財報，評分無意義 |

### 資料流

```
每工作日 16:05
  Crawler (score_job)
    → GET http://host.docker.internal:18000/api/stocks/{id}/buy_score  (100次，間隔1.2秒)
    → StockAnalysisDashBoard 回傳 {score, max_score, ...}（當日已快取，不耗 FinMind token）
    → 寫入 /app/data/buy_scores/YYYY-MM-DD.json
    → 保留最近 7 天檔案

Backend GET /api/scores
  → 讀最新 JSON（今天 > 昨天 > 最近交易日）
  → 記憶體快取（每天一份，重啟後重讀）
  → 回傳 {date, scores: {stock_id: {score, max_score}}}

Frontend (App.vue onMounted)
  → fetchScores() 一次性呼叫 /api/scores
  → scores 存入 Pinia store (useStockStore)
  → HeatmapGrid 將 buyScore prop 傳給 StockCell
  → StockCell 在名稱後顯示 " - 18/24" 或 " - N/A"
```

### 新 API Contract

#### `GET /api/scores`
```json
{
  "date": "2026-05-19",
  "generated_at": "2026-05-19T16:15:00+08:00",
  "scores": {
    "2330": { "score": 18, "max_score": 24 },
    "2317": { "score": 12, "max_score": 24 }
  }
}
```
- 無資料時：`{"date": "", "scores": {}}`
- 快取：backend 記憶體快取，每日首次請求讀檔

### 新增 / 修改的檔案

| 檔案 | 類型 | 說明 |
|------|------|------|
| `crawler/sources/buy_score.py` | 新增 | fetch / write / load scores JSON |
| `crawler/main.py` | 修改 | 16:05 新增 `score_job` |
| `backend/routers/scores.py` | 新增 | `GET /api/scores` 端點 |
| `backend/main.py` | 修改 | 註冊 scores router |
| `frontend/src/composables/useScoreData.js` | 新增 | 一次性 fetch /api/scores |
| `frontend/src/stores/stockStore.js` | 修改 | 加 `scores`、`scoresLoaded` state |
| `frontend/src/components/HeatmapGrid.vue` | 修改 | 將 `buyScore` prop 傳給 StockCell |
| `frontend/src/components/StockCell.vue` | 修改 | 名稱列顯示 score |
| `frontend/src/App.vue` | 修改 | onMounted 呼叫 fetchScores() |
| `docker-compose.yml` | 修改 | 加 `STOCK_ANALYSIS_URL`、`SCORES_DIR` env |
| `crawler/tests/test_buy_score_source.py` | 新增 | crawler 單元測試 |
| `backend/tests/test_scores_api.py` | 新增 | API 合約測試 |
| `frontend/tests/StockCell.test.js` | 新增 | component 測試 |

### Success Criteria（買入評分）
- [ ] 每工作日 16:05 後，`data/buy_scores/YYYY-MM-DD.json` 存在且包含 ≥ 50 支股票分數
- [ ] `GET /api/scores` 回傳正確 JSON schema
- [ ] 股票卡片名稱後顯示 `- score/max_score`（分數存在時）
- [ ] 分數不存在的股票顯示 `- N/A`
- [ ] 分數尚未載入時卡片名稱正常顯示（無 N/A 亂跳）
- [ ] 現有熱力圖功能（volume/turnover 排名、分頁、搜尋）無回歸
- [ ] 所有 pytest 與 vitest 測試通過
