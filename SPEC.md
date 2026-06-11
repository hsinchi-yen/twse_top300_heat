# Spec: 台股前360熱力圖 (TWSE Top 360 Heatmap Dashboard)

## Objective

建立一個以 **成交量前 360** 為候選池、可切換**成交量 / 週轉率**兩種排名視角的台股熱力圖 Dashboard。按題材分區塊呈現，顏色代表漲跌幅。支援 365 天 × 24 小時嵌入式 Kiosk 連續運行，兼顧 FinMind token 成本控制與 eMMC 儲存壽命。

### Target Users
- **Trader / 投資人** — 快速掌握當日資金動向與題材輪動
- **Technical Manager** — 一眼看懂市場熱點與異常爆量
- **Embedded Engineer** — 部署於工業電腦 Kiosk 長時間穩定運行

### Success Criteria
- [ ] 開啟 Dashboard < 3 秒（首屏 LCP）
- [ ] 盤中資料每 60 秒自動刷新，無需手動操作
- [ ] 可在「成交量 Top 360」與「週轉率 Top 360」兩種模式間切換，動畫流暢
- [ ] 格子按題材分區塊（Treemap 風格）排列，6×6 = 36 格為一頁
- [ ] 5 段色階正確反映漲跌幅（深紅/淺紅/灰/淺綠/深綠）
- [ ] 收盤後（16:30 後）降頻為每 5 分鐘輕量 check，不再觸發高頻寫入
- [ ] Docker 一鍵啟動（`bash run_containers.sh`），四個服務全部健康
- [ ] eMMC 長期穩態使用率 < 70%，不因儲存耗盡造成服務中斷
- [ ] 每日完整評分批次 ≤ 1 次，快取命中率 ≥ 90%

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Vue 3 + Vite | Vue 3.4+, Vite 5+ |
| State | Pinia | 2.x |
| Backend | FastAPI | 0.110+ |
| Database | SQLite (via SQLAlchemy) | — |
| Scheduler | APScheduler | 3.x |
| Data Source | TWSE OpenAPI + TPEX OpenAPI + Yahoo Finance | — |
| Data Source | FinMind SDK | 最新 |
| Container | Docker (run_containers.sh) | 28+ |
| Runtime | Python 3.11+ | — |

---

## Commands

```bash
# 開發（Docker Compose，僅 dev 環境）
docker compose up -d
docker compose logs -f backend
docker compose logs -f crawler
docker compose down

# 前端獨立開發
cd frontend && npm install
npm run dev          # http://localhost:8504

# 後端獨立開發
cd backend && pip install -r requirements.txt
uvicorn main:app --reload

# 測試
cd backend && pytest -v
cd frontend && npm run test   # Vitest

# Yocto / Production 部署（無 docker-compose）
scp deploy_pkg/*.tar.gz root@<HOST>:/root/TWSE_TOP100_HEAT/
ssh root@<HOST> "docker load < backend.tar.gz && ..."
bash run_containers.sh        # 啟動四個容器
```

---

## Project Structure

```
Twse_Top100_Heat/
├── docker-compose.yml        # Dev 用
├── run_containers.sh         # Yocto 生產環境用（Docker only）
├── AGENTS.md
├── SPEC.md                   # 本文件
├── improve.md                # 長期運行改善條文
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── HeatmapGrid.vue      # 主格子元件（Top 360，分頁）
│       │   ├── StockCell.vue        # 單一股票格子（含買入評分）
│       │   ├── ModeToggle.vue       # 成交量/週轉率切換
│       │   ├── TokenSettings.vue    # FinMind Token 設定
│       │   └── ScoreRefreshBtn.vue  # 手動強制刷新評分
│       ├── composables/
│       │   ├── useStockData.js      # 盤中 60s / 盤後 5min polling
│       │   ├── useScoreData.js      # 評分 fetch（header token）
│       │   └── useEtfData.js        # ETF 資料
│       └── stores/
│           └── stockStore.js
├── backend/
│   ├── main.py               # CORS (ALLOWED_ORIGINS env)
│   └── routers/
│       ├── stocks.py         # GET /api/stocks/top100
│       ├── sectors.py
│       ├── etf.py
│       └── scores.py         # GET /api/scores（讀 JSON + force 旗標）
├── crawler/
│   ├── main.py               # APScheduler：盤中/收盤/維護/月度評分 + force 偵測
│   ├── etf_main.py           # ETF 爬蟲 + etf_ranks 清理
│   └── sources/
│       ├── twse.py
│       ├── tpex.py
│       ├── yahoo.py          # 盤中即時報價 fallback
│       ├── finmind.py        # 發行股數 / 類股（週轉率用）
│       ├── finmind_client.py # FinMind 原始 API client（評分引擎用）
│       ├── buy_score_engine.py # compute_buy_score（24 指標 + 排雷）
│       ├── goodinfo_client.py  # Goodinfo 爬蟲（評分用，預設停用）
│       └── buy_score.py      # 評分 batch（原生計算 + 額度續抓）/ write / prune
└── Reference/
```

---

## Data Flow

```
盤中（09:00–13:30）：每 60 秒
盤後（16:00）       ：收盤最終一次
         │
   ┌─────▼──────┐
   │  crawler   │  TWSE/TPEX/Yahoo → 成交量排行（Top 360 候選池）
   │            │  FinMind SDK     → 股本 → 週轉率
   └─────┬──────┘
         │ UPSERT
   ┌─────▼──────┐
   │   SQLite   │  stock_ranks（保留 7 交易日）+ sector_map
   │            │  etf_ranks（保留 90 交易日）
   └─────┬──────┘
         │ query
   ┌─────▼──────┐
   │  FastAPI   │  GET /api/stocks/top100?mode=volume&limit=360
   └─────┬──────┘
         │ HTTP polling（盤中 60s / 盤後 5min）
   ┌─────▼──────┐
   │   Vue 3    │  Pinia → HeatmapGrid（分頁）→ StockCell（+買入評分）
   └────────────┘

月度評分（每月 1 日 03:00）：
   Crawler score_job
     → compute_buy_score(id) × ≤ 480 次（原生計算，直接打 FinMind，間隔 1.2s）
     → 引擎 24 指標 + 排雷（移植自 StockAnalysisDashBoard，無 HTTP 代理）
     → FinMind 額度耗盡 → 寫 partial、等 1h、只續抓未完成者（最多 24 輪）
     → 寫入 /app/data/buy_scores/YYYY-MM-DD.json（原子切換）
     → 保留最近 7 天檔案

手動強制刷新：
   Frontend ScoreRefreshBtn → GET /api/scores?force=true
     → backend 寫旗標 buy_scores/.force_refresh
     → crawler 每分鐘偵測 → 寫 .scoring_in_progress → score_job(force=True)
```

---

## API Contract

### `GET /api/stocks/top100?mode=volume|turnover&limit=360`
```json
{
  "mode": "volume",
  "date": "2026-05-20",
  "market_open": false,
  "updated_at": "2026-05-20T16:00:00+08:00",
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

**注意：** `rank` 欄位固定為 `volume_rank`；週轉率模式的重排在前端完成。

### `GET /api/scores`

評分由 crawler 原生計算（FinMind token 在 crawler 端的 `FINMIND_TOKEN`）。
backend 只讀取共享 JSON 並回傳；`X-FinMind-Token` header 可帶但會被忽略。

```http
GET /api/scores
```

Response:
```json
{
  "date": "2026-05-20",
  "generated_at": "2026-05-20T16:15:00+08:00",
  "scores": {
    "2330": { "score": 18, "max_score": 24 },
    "2317": { "score": 12, "max_score": 24 }
  },
  "fetching": false
}
```

- 無資料時：`{"date": "", "scores": {}, "fetching": false}`
- 評分進行中：`{"date": "...", "scores": {...}, "fetching": true}`（回傳當前部分資料）
- `fetching` 依旗標檔判定：`.scoring_in_progress` 或 `.force_refresh` 存在時為 true

Query params:
- `force=true`：寫旗標檔 `buy_scores/.force_refresh`，由 crawler 偵測後重新計算全部股票
  （**非阻塞**，不刪舊檔，crawler 逐步原子覆寫；前端輪詢 `/api/scores` 取得進度）。
  已在計算中（`fetching=true`）時忽略。

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
    close_price REAL,
    turnover_rate REAL,
    price_change_pct REAL,
    color_tier TEXT,
    volume_rank INTEGER,
    turnover_rank INTEGER,
    UNIQUE(stock_id, date)
    -- 保留最近 7 交易日（daily_maintenance_job 清除）
);

CREATE TABLE sector_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id TEXT NOT NULL UNIQUE,
    sector TEXT NOT NULL DEFAULT '其他'
);

-- etf_ranks 保留最近 ETF_KEEP_DAYS（預設 90）交易日
-- 每月 1 日 02:30 由 etf_main prune_old_etf_ranks() 清除
```

---

## Scheduler Jobs（crawler/main.py）

| Job ID | 觸發 | 說明 |
|--------|------|------|
| `crawl_intraday` | Mon-Fri 09:00–12:59 每分鐘 | 盤中股票資料 |
| `crawl_intraday_1330` | Mon-Fri 13:00–13:30 每分鐘 | 盤中延伸 |
| `crawl_close` | Mon-Fri 16:00 | 收盤最終資料 |
| `daily_maintenance` | Mon-Fri 08:55 | WAL checkpoint、儲存水位檢查、cache 清除、stock_ranks 修剪 |
| `score_monthly` | 每月 1 日 03:00 | 買入評分批次（misfire 補跑 24h） |
| `monthly_vacuum` | 每月 1 日 02:00 | SQLite VACUUM |

ETF Crawler（crawler/etf_main.py）另有獨立 scheduler：
- `etf_intraday` / `etf_intraday_1330` / `etf_close` / `etf_asset_scale` / `etf_prune`（月度清理）

---

## Feature: 買入評分 (Buy Score)

### 決策紀錄

| 問題 | 決策 | 原因 |
|------|------|------|
| 資料來源 | **原生計算**（`compute_buy_score` 直接打 FinMind） | 移除跨專案 HTTP 依賴與其失敗點 |
| 評分邏輯 | 24 指標 + 排雷，移植自 StockAnalysisDashBoard | 沿用既有邏輯，不重新發明 |
| 計算位置 | crawler（已有 FinMind/排程/續跑邏輯） | backend 不加 pandas、不複製引擎 |
| 儲存方式 | JSON 檔案 `data/buy_scores/YYYY-MM-DD.json`（僅存 `{score,max_score}`） | 不動 DB schema；原子切換（.tmp → rename） |
| 計算時機 | **每月 1 日 03:00**（月更新） | 財報基礎分數；月更新即足夠 |
| 候選池 | volume_rank ≤ `SCORE_CANDIDATE_LIMIT`（預設 480，硬上限 1000） | 可配置，防止無限擴張消耗 token |
| Token | crawler `FINMIND_TOKEN` env（禁止 query string / log） | 防止 token 出現在 URL / log |
| 分時處理 | 每檔間 `BUY_SCORE_REQUEST_DELAY`；資料集間 `BUY_SCORE_FETCH_DELAY` | 降載，避免觸發 FinMind burst limiter |
| 額度耗盡 | 402→`FinMindError`：寫 partial、等 `BUY_SCORE_QUOTA_WAIT_S`(1h)、只續抓未完成者、最多 24 輪 | 「token 用完一小時後繼續更新」 |
| 強制刷新 | backend 寫旗標檔，crawler 偵測後 `force=True` 重算（merge over 現檔，不刪舊） | 非阻塞；舊資料持續可用、不閃 N/A |
| 部分進度 | 每 50 筆寫一次磁碟（原子切換）；中斷/續跑跳過已完成 | 不需從零開始 |
| 不存 0/24 | `eligible_count==0`（全失敗）→ 回 None（N/A）不落地 | 避免卡在誤導性 0/24 |
| 評分顯示 | `股票名稱 - score/max_score`（如 `台積電 - 18/24`） | 最精簡，卡片空間有限 |
| 無資料顯示 | `N/A` | 財報不完整或 API 失敗 |
| Goodinfo | 預設停用（`BUY_SCORE_GOODINFO_ENABLED`） | 逐檔爬蟲易被封；只影響 1 評分 + 1 排雷 |
| ETF 頁面 | 不顯示 | ETF 無個股財報，評分無意義 |

### Success Criteria（買入評分）
- [ ] 每月 1 日後，`data/buy_scores/YYYY-MM-DD.json` 包含 ≥ 50 支分數
- [ ] `GET /api/scores` 回傳正確 JSON schema
- [ ] FinMind token 僅透過 crawler `FINMIND_TOKEN` env（不入 query string / log）
- [ ] 強制刷新不刪除舊檔（`.tmp → rename` 原子切換）
- [ ] 額度耗盡 → 寫 partial → 等待 → 只續抓未完成股票
- [ ] 中斷後重跑可跳過已完成股票（部分進度持久化）
- [ ] 全失敗（eligible_count==0）不落地為 0/24
- [ ] 所有 pytest 與 vitest 測試通過

---

## Feature: eMMC 365×24 長期穩定性

### 儲存水位保護

| 使用率 | 動作 |
|--------|------|
| ≥ 70% | `WARNING` log 告警 |
| ≥ 80% | `WARNING` 保護模式告警 |
| ≥ 90% | `ERROR` 緊急模式告警 |

由 `daily_maintenance_job`（每日 08:55）與容器啟動時觸發。

### 資料保留策略

| 資料 | 預設保留 | 環境變數 |
|------|---------|---------|
| `stock_ranks` | 7 交易日 | — |
| `etf_ranks` | 90 交易日 | `ETF_KEEP_DAYS` |
| `buy_scores/*.json` | 7 天 | — |
| `metrics/*.json` | 永久 | — |

### 日誌 Rotation

所有容器啟用 `json-file` driver，`max-size: 10m, max-file: 3`。

### WAL / VACUUM

- WAL checkpoint：每日 08:55（`daily_maintenance_job`）
- VACUUM：每月 1 日 02:00（`monthly_vacuum`），在評分批次前執行

---

## Deployment

### 開發（Docker Compose）

```bash
docker compose up -d
```

### Yocto / 生產（Docker only）

```bash
# 本機 build 並 SCP
docker build -t twse_top100_heat-backend:latest ./backend
docker save ... | gzip > backend.tar.gz
scp *.tar.gz root@<HOST>:/root/TWSE_TOP100_HEAT/

# 在 Yocto 機器上（或直接 SSH build）
docker load < backend.tar.gz
bash run_containers.sh
```

`run_containers.sh` 以 `--network host` 啟動四個容器，並注入所有 env vars。

### 環境變數

| 變數 | 預設 | 說明 |
|------|------|------|
| `FINMIND_TOKEN` | `""` | FinMind token（crawler 端，評分計算用） |
| `SCORES_DIR` | `/app/data/buy_scores` | 評分 JSON 目錄 |
| `SCORE_CANDIDATE_LIMIT` | `480` | 評分候選池上限（硬上限 1000） |
| `BUY_SCORE_REQUEST_DELAY` | `1.2` | 每檔評分間隔秒 |
| `BUY_SCORE_FETCH_DELAY` | `0.4` | 引擎內每個 FinMind 資料集間隔秒 |
| `BUY_SCORE_QUOTA_WAIT_S` | `3600` | 額度耗盡後續抓等待秒 |
| `BUY_SCORE_QUOTA_MAX_CYCLES` | `24` | 額度續抓最多輪數 |
| `BUY_SCORE_GOODINFO_ENABLED` | `false` | 啟用 Goodinfo 外資/質押爬蟲（封鎖風險，預設關） |
| `ALLOWED_ORIGINS` | `""` (等同 `*`) | CORS 白名單，逗號分隔 |
| `ETF_KEEP_DAYS` | `90` | ETF 歷史保留天數 |
| `STORAGE_WARN_PCT` | `70.0` | 儲存告警閾值 (%) |
| `STORAGE_PROTECT_PCT` | `80.0` | 儲存保護閾值 (%) |
| `STORAGE_EMERGENCY_PCT` | `90.0` | 儲存緊急閾值 (%) |

---

## Code Style

### Python (backend / crawler)
```python
async def get_top100_by_volume(db: Session, date: str) -> list[StockRank]:
    """取得指定日期成交量前 360 名，依成交量降冪排序。"""
    ...
```

### Vue 3 (frontend)
```vue
<script setup>
const props = defineProps({
  mode: { type: String, required: true }, // 'volume' | 'turnover' | 'etf'
})
</script>
```

### 命名規範
- DB 欄位：`snake_case`（`turnover_rate`, `price_change_pct`）
- API endpoint：`/api/stocks/top100?mode=volume&limit=360`
- Vue component：`PascalCase`
- JS 變數：`camelCase`

---

## Testing Strategy

| Layer | Framework | 覆蓋重點 |
|-------|-----------|---------|
| Backend unit | pytest | ranker 排名計算、週轉率公式 |
| Backend API | pytest + httpx | `/api/stocks/top100`、`/api/scores` response shape |
| Frontend unit | Vitest | StockCell、TokenSettings、useStockData composable |
| E2E | 手動 Chromium | 熱力圖渲染、模式切換、評分顯示 |

- Coverage 目標：backend ≥ 80%
- 每個 commit 前跑 `pytest` + `npm run test`

---

## Boundaries

- **Always:**
  - 跑 `pytest` + `vitest` 通過後才 commit
  - API response 維持已定義的 contract shape
  - FinMind token 只透過 crawler `FINMIND_TOKEN` env，禁止 query string / log
  - TWSE/TPEX API 請求加 1-3 秒隨機 delay
  - 評分強制刷新用 `.tmp → rename` 原子切換，不先刪舊檔

- **Ask first:**
  - 修改 SQLite schema
  - 新增 Python / npm 套件
  - 更改 Docker port 設定
  - 新增 API endpoint
  - 調整評分候選池上限或保留天數

- **Never:**
  - 硬編碼 API key 或 token
  - 將 token 放入 URL query string 或 log
  - 在測試中跳過失敗的 assert
  - 高頻率全市場爬蟲（盤中 > 每分鐘一次）
  - 評分任務一日執行超過 1 次（手動觸發另計）
