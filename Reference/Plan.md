# Embedded Insight Dashboard - 開發計劃

## 專案目標

建立一套可運行於 Embedded Linux / Yocto 的 Web Dashboard 系統，
提供：

- 嵌入式系統監控
- 股票題材輪動熱力圖
- 即時事件觀察
- 生產資訊整合

並能以 Kiosk 模式長時間穩定運行。

---

# 第一階段（MVP）

## 系統監控

- CPU Usage
- Memory Usage
- Disk Usage
- Temperature
- Ethernet Status
- WiFi Status

## 股票市場資訊

- 成交量 Top100
- 週轉率 Top100
- 題材分類
- 熱力圖

## UI

- Dark Mode
- 自動刷新
- Fullscreen Kiosk

---

# 技術架構

## Frontend

- Vue3
- Vite
- Apache ECharts

## Backend

- FastAPI
- WebSocket
- APScheduler

## Database

- SQLite

## Embedded Platform

- Yocto Linux
- Docker
- Chromium Kiosk

---

# 開發階段

## Phase 1

- 建立 FastAPI Backend
- 建立 Dashboard UI
- FinMind API 串接
- 系統資訊 API

## Phase 2

- WebSocket 即時更新
- 股票熱力圖
- 題材輪動分析

## Phase 3

- AI 新聞分析
- 多設備管理
- MQTT Integration

---

# 部署方式

## Docker Compose

- frontend
- backend
- crawler
- database

---

# 長期目標

建立可部署於：

- 工業電腦
- NXP i.MX8MP
- RK3588
- Intel N97

的戰情室資訊平台。