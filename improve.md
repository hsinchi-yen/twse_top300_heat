# Twse_Top100_Heat 改善條文

> Updated: 2026-06-11
> This file now records the current long-run operating contract plus the remaining hardening backlog.

## 1. 目的與範圍

1. 規範本專案在 365x24 連續運行下的穩定性、可維運性、FinMind 成本控制與儲存安全。
2. 適用範圍包含 crawler、backend、frontend、Docker 啟動方式與 `/app/data` 目錄策略。

## 2. 已落地的核心規則

1. 股票主畫面固定抓 `mode=volume&limit=480`。
2. `turnover` 與 `buy_score` 是前端對同一批 480 檔資料重排，不再切換股票 API 來源。
3. 買進評分由 crawler 原生計算，backend 不再負責代理或轉算。
4. 強制刷新使用旗標檔協調，屬非阻塞流程。
5. 評分快取寫入一律採 `.tmp -> rename` 原子切換。
6. FinMind 額度耗盡後會等待並只續抓未完成股票，不從零開始。
7. `eligible_count == 0` 不會被寫成誤導性的 `0/24`。
8. 生產部署統一採 `run_containers.sh` 與 `--network host`。

## 3. FinMind 成本控制條文

1. 月度評分批次固定於每月 1 日 `03:00` 執行。
2. 強制刷新由人工觸發，但同時間僅允許單一有效工作。
3. token 只允許存在於 crawler `FINMIND_TOKEN` env，不得寫入 query string 或 log。
4. 既有快取存在時，背景抓取期間 API 應優先回傳現有資料與 `fetching=true`。
5. 評分候選池必須可配置且有硬上限，現況為預設 `480`、上限 `1000`。
6. 每 50 筆成功分數需落地一次，以降低長批次中斷成本。

## 4. 儲存與 eMMC 保護條文

1. 儲存水位採三段告警：
   - `70%`：warning
   - `80%`：protection warning
   - `90%`：emergency warning
2. `stock_ranks` 只保留最近 7 個交易日。
3. `etf_ranks` 只保留最近 `ETF_KEEP_DAYS` 個交易日，預設 `90`。
4. `buy_scores/*.json` 只保留最近 7 份檔案。
5. 每日 `08:55` 執行 WAL checkpoint、storage check、cache clear、sector refresh、舊資料修剪。
6. 每月 1 日 `02:00` 執行 VACUUM；`02:30` 修剪 ETF 歷史。
7. 所有容器日誌必須啟用 `json-file` rotation：`max-size=10m`、`max-file=3`。

## 5. 排程與一致性條文

1. 股票與 ETF 盤中資料維持每分鐘更新，範圍為 `09:00-13:30`。
2. 股票收盤最終抓取為 `16:00`；ETF 收盤最終抓取為 `16:05`。
3. 當 TWSE 當日資料尚未更新時，可回退 Yahoo Finance 作為盤中即時補值。
4. 最新交易日查詢應排除 `volume=0` 的非有效資料日。
5. `date` 表示交易日；`updated_at` 目前表示 API response timestamp，若要變更語意需同步改 spec 與測試。

## 6. 安全與介面條文

1. `ALLOWED_ORIGINS` 必須由 env 提供，不得寫死固定名單。
2. migration 相容處理只可忽略可預期的重複欄位錯誤。
3. 不得重新引入會暴露 token 的 query-string 模式。
4. API contract 變更前需先更新 `SPEC.md`，再更新測試與實作。

## 7. 仍建議補強的項目

1. 產出更完整的 runtime metrics，例如評分覆蓋率、quota wait 次數、平均耗時。
2. 補齊 storage watermark 與啟動恢復流程的自動化測試。
3. 若一年期資料量接近預期上限，評估將 `stock_ranks` 保留天數配置化。
4. 若下游需要更精準快照語意，將 `updated_at` 改為資料更新時間而非 response time。

## 8. SLO 與門檻

1. 股票盤中自動刷新頻率：60 秒。
2. ETF 盤中自動刷新頻率：60 秒。
3. 任一時點都應能讀到最近一份有效 buy-score 檔。
4. eMMC 長期穩態使用率目標 < `70%`。
5. 不得因評分重跑而出現 delete-then-empty 的讀取空窗。
