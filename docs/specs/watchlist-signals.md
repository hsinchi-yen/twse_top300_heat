# Spec Draft: 觀察力強化（自選股 + 篩選器 + 每日指標 + 卡片重排）

> Status: **IMPLEMENTED 2026-10-26** (T1–T7; schedule changed to nightly 03:00 per user) — was CONFIRMED 2026-10-26 — 使用者同意全部建議（門檻、配色、上限 30、schema 變更）。各階段在寫測試前先把對應 API contract 併入 `SPEC.md`（CLAUDE.md 規則 7）。
> Drafted: 2026-10-26

## 目標

給「沒耐心但會深度思考」的投資人：
1. 從 600 檔池用**篩選器組合**快速縮小到少數候選
2. 把研究中的股票**釘選成自選股**，在大卡片上並排比較
3. 卡片一眼看出四個面向：**評分結論、籌碼、技術／量能、估值**

## 已確認的方向

| 決策 | 選擇 |
|---|---|
| 核心流程 | 自選股視圖 + 600 檔池篩選 |
| 排序 | 篩選器組合（預設組合 + 自訂勾選），篩完依 `pass_rate` 排 |
| 卡片指標 | 評分摘要 + 籌碼（每日）+ 技術／量能（每日）+ 估值（月） |
| 視覺 | 資訊層級重排；評分／自選模式以訊號上色 |
| 自選股儲存 | backend SQLite，跨裝置共用 |
| 每日指標範圍 | 600 檔池 ∪ 自選股，盤後一次 |

## 現況缺口（程式碼依據）

- `compute_buy_score` 已算出 `pass_rate`、`signal_label`、`risk_score`、`risk_criteria`、`criteria`（含 C9 P/E），但 `sources/buy_score.py::fetch_buy_score` 只回傳 `score / max_score / fundamentals_uptrend`，其餘被丟棄
- `StockCell.vue` 底色只依 `color_tier`（當日漲跌）；評分只是 0.58rem 小字
- 卡片字級下限 0.5rem（≈8px）、多處文字 alpha 0.45，6×6 預設格下難以閱讀
- `stock_ranks` 只保留 7 個交易日，無法算 MA20／MA60／52 週高點

---

## Phase 1 — 評分摘要露出 + 卡片重排（不需新資料源）

### 1a. `GET /api/scores` 擴充欄位（向下相容）

每檔 summary 新增欄位；舊 JSON 缺欄位時前端一律視為 `null`（不顯示，不補 0）：

```json
"2330": {
  "score": 18, "max_score": 24, "fundamentals_uptrend": true,
  "eligible_count": 23,
  "pass_rate": 78.3,
  "signal": "strong_buy",
  "signal_label": "建議買進",
  "risk_score": 0,
  "risk_flags": [ { "category": "獲利排雷", "name": "自由現金流轉負" } ],
  "pe": { "current": 22.1, "median": 24.5, "p25": 19.8 }
}
```

- `signal` ∈ `strong_buy | buy | watch | neutral`；`risk_score >= 2` 時 `signal_label = "高風險避開"`（沿用引擎現行邏輯）
- `pe` 取自 C9 計算結果；任一值缺 → 該 key 為 `null`
- summary 檔大小預估 600 檔 ≈ 150 KB；**不得**把 `criteria` 明細放進 summary（每分鐘輪詢）

### 1b. 新增 `GET /api/scores/{stock_id}`（明細，按需讀取）

- crawler 另寫 `SCORES_DIR/details/YYYY-MM-DD.json`（`{stock_id: {criteria, risk_criteria, warnings}}`），同樣 `.tmp -> rename`，保留最新 7 份；`_prune_old` 與 `load_latest_scores` 不得把 `details/` 誤當 summary
- 回應：`{ "date", "stock_id", "criteria": [...], "risk_criteria": [...] }`；查無 → `404`
- 用途：自選股卡片展開、桌機 hover tooltip

### 1c. 卡片資訊層級（`StockCell.vue`）

一般尺寸（gridSize 4／5、自選股視圖）：

```text
┌──────────────────────────────┐
│ 台積電  2330        〔建議買進〕│  ← 名稱最大；訊號徽章
│ 78%  ▓▓▓▓▓▓▓▓░░   18/23       │  ← pass_rate 大字 + 進度條；分數降為小字
│ 1,045.0            +2.35%    │  ← 價格 + 漲跌（漲跌只上文字色）
│ ✅轉強 💲低估 法人+3 ⚠0        │  ← 指標 chips（Phase 3 補籌碼／技術）
└──────────────────────────────┘
```

精簡尺寸（gridSize 6）：chips 只留圖示；訊號改為卡片左緣 4px 色條。

規則：
- **評分／自選模式**：底色依 `signal`，不依漲跌。訊號色**避開紅綠**（台股紅漲綠跌會混淆）：`strong_buy` 金、`buy` 青、`watch` 灰藍、`neutral` 暗灰、`高風險避開` 紫 + 斜紋
- **成交量／週轉率模式**：底色維持漲跌熱度，但同樣顯示 chips 列
- `💲低估`：`pe.current < pe.p25`；`pe.current < pe.median` 顯示淡色 `💲`
- `⚠N`：`risk_score > 0` 才顯示，N = `risk_score`
- 排名、產業標籤降級為次要小字（仍保留）

### 1d. 字體與對比（`tokens.css` + `StockCell.vue`）

- 數字改用 sans + `font-variant-numeric: tabular-nums`，不用 JetBrains Mono（中英數混排較易讀）
- 卡片內最小字級 `0.7rem`（≈11px）；低於此的元素改為隱藏，不再縮字
- 次要文字 alpha 下限 0.7（dark）／0.66（light）
- 移除內文 `text-shadow` 光暈與 hover 掃描線；光暈只保留給 `strong_buy` 徽章與搜尋高亮

---

## Phase 2 — 自選股

### 資料表（schema 變更）

```sql
CREATE TABLE watchlist (
  stock_id  TEXT PRIMARY KEY,
  note      TEXT NOT NULL DEFAULT '',   -- 研究筆記／買進理由
  added_at  TEXT NOT NULL               -- ISO8601 +08:00
);
```

### API

| Method | Path | 行為 |
|---|---|---|
| `GET` | `/api/watchlist` | `{"items":[{stock_id, note, added_at, quote}]}`；`quote` = 最新交易日 `stock_ranks` 的股票物件（與 top100 同欄位 + `sector`），不在 600 池也查得到；查無 → `null` |
| `PUT` | `/api/watchlist/{stock_id}` | body `{"note": "..."}`（可省略），upsert；`stock_id` 不在最新 `stock_ranks` → `404`；超過 `WATCHLIST_MAX` → `409` |
| `DELETE` | `/api/watchlist/{stock_id}` | `204`；不存在也回 `204` |

- 單一使用者、區網部署，不做驗證（與現有 API 一致）
- crawler 評分候選池改為 `volume_rank <= SCORE_CANDIDATE_LIMIT` **∪ watchlist**

### 前端

- 新 mode `watchlist`（ModeToggle 新按鈕「自選」）；固定大卡片（桌機 3–4 欄、手機 1 欄）
- 每張卡：Phase 1 版面 + 筆記一行 + 「展開明細」（呼叫 `/api/scores/{id}` 列出 criteria 通過／未通過與排雷項）
- 其他模式卡片右上角 ☆／★ 切換釘選（手機：長按）
- 輪詢：與股票同節奏（盤中 60s、盤後 5min）

---

## Phase 3 — 每日籌碼 + 技術／量能

### 資料表（schema 變更）

```sql
CREATE TABLE daily_bars (            -- 保留 SIGNALS_BAR_KEEP_DAYS 交易日（預設 260）
  stock_id TEXT, date TEXT, close REAL, volume INTEGER,
  PRIMARY KEY (stock_id, date)
);
CREATE TABLE inst_flows (            -- 保留 SIGNALS_INST_KEEP_DAYS 交易日（預設 20）
  stock_id TEXT, date TEXT,
  foreign_net INTEGER, trust_net INTEGER, dealer_net INTEGER,   -- 單位：張
  PRIMARY KEY (stock_id, date)
);
CREATE TABLE stock_signals (         -- 只保留最新一個交易日
  stock_id TEXT PRIMARY KEY, date TEXT,
  avg_volume_5d INTEGER, vol_ratio REAL,
  ma20 REAL, ma60 REAL, high_52w REAL, pct_from_52w_high REAL,
  inst_net_5d INTEGER, inst_streak INTEGER,
  foreign_net_1d INTEGER, trust_net_1d INTEGER
);
```

預估容量：650 檔 × 260 日 ≈ 17 萬列，約 10–15 MB，受既有 storage watermark 管控。

### 資料來源

| 資料 | 每日來源 | 新增請求 | 回補 |
|---|---|---|---|
| 收盤價／量 | 複製當日 `stock_ranks` 收盤快照 | 0 | 一次性：FinMind `fetch_stock_price` 逐檔補 1 年（約 600 次，額度內） |
| 三大法人 | TWSE T86（上市）+ TPEx 三大法人日報（上櫃），全市場一次 | 2 / 日 | 一次性：逐日補 20 交易日（約 40 次） |

- 端點 URL 實作時先實測；全市場端點不可用時，fallback 為 FinMind 逐檔（約 650 次／日，仍在 6000／小時額度內）
- 新進池或新釘選的股票若 `daily_bars` 不足，下一次 job 自動補該檔
- 價格未還原權息：除權息日附近的 MA 有小幅失真，接受並在 tooltip 註明

### 計算（crawler 擁有，backend 只讀）

- `vol_ratio` = 當日量 ÷ 前 5 日均量
- `inst_net_5d` = 外資 + 投信近 5 日淨買超（張）
- `inst_streak` = 外資 + 投信合計連續淨買（+N）／淨賣（−N）天數
- `pct_from_52w_high` = (close − high_52w) ÷ high_52w × 100
- 歷史不足 → 該欄 `null`（例：上市未滿 60 日 → `ma60 = null`），**不得**補 0

### 排程

| Job ID | Schedule | Purpose |
|---|---|---|
| `nightly` | 每天 `03:00`（前一日為交易日才跑） | 官方收盤 bars → 三大法人 → 回補缺口 → 重算 `stock_signals` → prune → 買進評分 |

> 2026-10-26 使用者決定：資料不需即時，指標與買進評分都改在交易日後的凌晨 03:00 跑；原 16:20／17:30 排程與啟動補跑取消。

（啟動補跑已取消：首次部署後，指標於下一次凌晨 03:00 出現。）

### `GET /api/signals`

```json
{
  "date": "2026-10-23",
  "generated_at": "2026-10-23T16:24:10+08:00",
  "signals": {
    "2330": {
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

- `above_ma20 / above_ma60` 由 backend 以最新 close 比對算出（null-safe）
- 支援 `ETag` + `Cache-Control`；前端載入時抓一次，之後每 5 分鐘輪詢
- 盤中前端用即時 `volume ÷ avg_volume_5d` 算即時量比

### 卡片 chips（補進 Phase 1 的 chips 列）

`法人+3`（`inst_streak`，連買紅／連賣綠字）、`📈MA20`、`量×2.1`（`vol_ratio ≥ 1.5` 才顯示）、`距高 −5%`

---

## Phase 4 — 篩選器組合

純前端，對同一批 600 檔（∪ 自選）資料過濾；**不改股票 API query**（CLAUDE.md 規則 3、4）。

### 預設組合（AND）

| 名稱 | 條件 |
|---|---|
| 穩健優質 | `pass_rate ≥ 75` ∧ `risk_score == 0` |
| 轉強起漲 | `fundamentals_uptrend` ∧ `above_ma20` ∧ `inst_streak ≥ 3` |
| 低估待買 | `pe.current < pe.p25` ∧ `pass_rate ≥ 60` ∧ `risk_score == 0` |
| 量增突破 | `vol_ratio ≥ 2` ∧ `price_change_pct > 0` ∧ `above_ma60` |

### 自訂勾選

上列每個原子條件各一個 checkbox，可自由組合；選了預設組合等於勾好它的條件，之後可再增減。

- 欄位為 `null` 的股票視為**不符合**（不因缺資料混入結果）
- 結果排序：`pass_rate` desc → `inst_net_5d` desc
- 篩選列顯示「符合 37 / 600」；篩選狀態存 `localStorage`（try/catch，讀不到就回到不篩選）
- 適用於成交量／週轉率／評分三種模式；ETF 不適用

---

## 新環境變數

| Variable | Default | Purpose |
|---|---|---|
| `WATCHLIST_MAX` | `30` | 自選股上限 |
| `SIGNALS_BAR_KEEP_DAYS` | `260` | `daily_bars` 保留交易日數 |
| `SIGNALS_INST_KEEP_DAYS` | `20` | `inst_flows` 保留交易日數 |
| `SIGNALS_BACKFILL_DELAY` | `1.0` | 回補時每檔間隔秒數 |

無新增 runtime 依賴（crawler 已有 pandas）。

---

## Tickets（依序；T5 可在 T1 之後與 T2–T4 平行）

| # | 範圍 | 內容 | 驗收 |
|---|---|---|---|
| T1 | crawler + backend | `fetch_buy_score` 保留 summary 欄位；寫 `details/`；`GET /api/scores/{id}`；SPEC.md 更新 | 舊 JSON 仍可讀；新欄位 contract 測試；details 原子寫入 + prune 測試；summary 不含 criteria |
| T2 | frontend | 卡片層級重排、訊號底色、chips 列（評分／估值／排雷）、字體與對比 token | vitest：signal→樣式對應、缺欄位不顯示；6×6 精簡版不溢出；light/dark 皆檢視 |
| T3 | backend + crawler | `watchlist` 表 + 三支 API；候選池 ∪ watchlist | 404／409／204 行為測試；池外股票 quote 正確 |
| T4 | frontend | ☆ 釘選、`watchlist` mode、展開明細 | 釘選跨重新整理保留；明細 404 時顯示「尚未評分」 |
| T5 | crawler | 三張新表、`signals_daily`、回補、計算 | 指標計算單元測試（含歷史不足 → null）；回補可中斷續跑；prune 測試 |
| T6 | backend + frontend | `GET /api/signals` + ETag；籌碼／技術 chips；即時量比 | contract 測試；chips 顯示門檻測試 |
| T7 | frontend | 篩選列（預設 + 自訂）、計數、localStorage | 每個預設組合的過濾測試；null 欄位排除；切模式保留篩選 |

## 待你確認

1. 預設組合的門檻（75／60、`inst_streak ≥ 3`、`vol_ratio ≥ 2`）是否合你的操作習慣？之後也可以改成 env 或 UI 調整
2. 訊號配色：金／青／灰藍／暗灰／紫，避開紅綠 — 可以接受嗎？
3. 自選股上限 30 檔是否足夠？
4. 三張新表 + `watchlist` 屬 SPEC.md「Ask first: changing SQLite schema」，確認本稿即視為同意
