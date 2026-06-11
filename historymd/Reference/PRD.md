# Product Requirement Document

# Product Name

Embedded Insight Dashboard

---

# Product Vision

建立一套適合 Embedded Linux 的即時資訊 Dashboard，
整合：

- 系統監控
- 生產資訊
- 股票市場熱力圖
- 題材輪動分析

讓使用者能一眼掌握：

- 系統健康狀態
- 市場資金流向
- 即時事件

---

# Target Users

- Embedded Engineer
- Factory Operator
- Validation Engineer
- Trader
- Technical Manager

---

# Functional Requirements

## 1. 系統監控

### 即時資訊

- CPU
- RAM
- Storage
- Temperature
- Ethernet
- WiFi

### 更新頻率

- 每 1 秒更新

---

## 2. 股票市場資訊

### 成交量排行

- Top100
- 每日更新

### 週轉率排行

- Top100
- 每日更新

### 題材分類

- AI
- 散熱
- 機器人
- 重電
- 航運
- PCB
- 半導體

### 熱力圖

- 顏色代表漲跌
- 大小代表成交量
- 閃爍代表異常量能

---

## 3. 即時告警

### 系統

- 高溫
- 網路斷線
- Disk Full

### 股票

- 爆量
- 急拉
- 跌停

---

# Non-Functional Requirements

## 效能

- UI 更新 < 1 秒
- Dashboard 開啟 < 3 秒

## 穩定性

- 24/7 運作
- 自動重啟

## 相容性

- Chromium
- Edge
- Firefox

---

# Technical Requirements

## Backend

- FastAPI

## Frontend

- Vue3
- ECharts

## DB

- SQLite

---

# Future Features

- AI 題材分析
- 新聞情緒分析
- 多螢幕模式
- MQTT
- Grafana Integration
- TradingView Widget