# 台股熱力圖 — 嵌入式系統 Docker 部署手冊

> **適用環境**：僅安裝 Docker Engine（無 docker-compose）的嵌入式 Linux 裝置  
> **目標平台**：Raspberry Pi 4B / Jetson Nano / 任何執行 Linux + Docker 的 ARM/x86 裝置  
> **架構**：3 個容器（backend / crawler / frontend）+ 1 個 bridge network + 1 個資料目錄

---

## 目錄

1. [系統需求](#1-系統需求)
2. [取得映像檔](#2-取得映像檔)
3. [首次部署（快速啟動）](#3-首次部署快速啟動)
4. [逐步說明](#4-逐步說明)
5. [Systemd 自動啟動](#5-systemd-自動啟動)
6. [常用操作指令](#6-常用操作指令)
7. [更新映像檔](#7-更新映像檔)
8. [資源限制設定](#8-資源限制設定)
9. [故障排除](#9-故障排除)

---

## 1. 系統需求

| 項目 | 最低需求 | 建議 |
|------|----------|------|
| RAM | 1 GB | 2 GB |
| eMMC / SD | 4 GB 可用空間 | 8 GB |
| Docker Engine | 20.10+ | 最新版 |
| 網路 | 有線 / WiFi（爬取用） | 有線 |
| 架構 | amd64 / arm64 / armv7 | — |

**確認 Docker 版本：**
```bash
docker --version
# Docker Engine 20.10.x 以上即可
```

---

## 2. 取得映像檔

### 方法 A：在裝置上直接 Build（需要網路與足夠儲存空間）

```bash
# 1. Clone 原始碼
git clone git@github.com:hsinchi-yen/twse_top300_heat.git
cd twse_top300_heat

# 2. Build 三個映像檔（約需 5-15 分鐘，視裝置效能）
docker build -t twse-backend:latest  ./backend
docker build -t twse-crawler:latest  ./crawler
docker build -t twse-frontend:latest ./frontend
```

### 方法 B：從開發機匯出，離線傳輸到裝置（推薦）

**在開發機上執行：**
```bash
# 匯出映像檔（約 670 MB 壓縮後）
docker save twse_top100_heat-backend:latest  | gzip > twse-backend.tar.gz
docker save twse_top100_heat-crawler:latest  | gzip > twse-crawler.tar.gz
docker save twse_top100_heat-frontend:latest | gzip > twse-frontend.tar.gz

# 用 scp 傳到嵌入式裝置（替換 <device-ip>）
scp twse-*.tar.gz pi@<device-ip>:~/twse/
```

**在嵌入式裝置上執行：**
```bash
cd ~/twse

# 載入映像檔
docker load < twse-backend.tar.gz
docker load < twse-crawler.tar.gz
docker load < twse-frontend.tar.gz

# 確認映像已載入
docker images | grep twse
```

---

## 3. 首次部署（快速啟動）

複製以下腳本整段執行，或存為 `start.sh`：

```bash
#!/bin/bash
set -e

APP_DIR="/opt/twse_heat"
DATA_DIR="${APP_DIR}/data"
NETWORK="twse-net"

# ── 1. 建立資料目錄 ──────────────────────────────────────
mkdir -p "${DATA_DIR}"

# ── 2. 建立隔離網路 ──────────────────────────────────────
docker network create "${NETWORK}" 2>/dev/null || echo "Network '${NETWORK}' already exists."

# ── 3. 啟動 Backend ───────────────────────────────────────
docker run -d \
  --name twse-backend \
  --network "${NETWORK}" \
  -p 8000:8000 \
  -v "${DATA_DIR}:/app/data" \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  --restart unless-stopped \
  --health-cmd "curl -f http://localhost:8000/health || exit 1" \
  --health-interval 10s \
  --health-timeout 5s \
  --health-retries 5 \
  twse-backend:latest

# ── 4. 等待 Backend 健康 ──────────────────────────────────
echo "Waiting for backend to become healthy..."
for i in $(seq 1 30); do
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' twse-backend 2>/dev/null || echo "starting")
  [ "${STATUS}" = "healthy" ] && echo "Backend is healthy." && break
  [ "$i" -eq 30 ] && echo "ERROR: Backend did not become healthy in 30s." && exit 1
  sleep 2
done

# ── 5. 啟動 Crawler ───────────────────────────────────────
docker run -d \
  --name twse-crawler \
  --network "${NETWORK}" \
  -v "${DATA_DIR}:/app/data" \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  -e FINMIND_TOKEN="${FINMIND_TOKEN:-}" \
  --restart unless-stopped \
  twse-crawler:latest

# ── 6. 啟動 Frontend ──────────────────────────────────────
docker run -d \
  --name twse-frontend \
  --network "${NETWORK}" \
  -p 5173:80 \
  --restart unless-stopped \
  twse-frontend:latest

echo ""
echo "=== 部署完成 ==="
echo "前端：http://$(hostname -I | awk '{print $1}'):5173"
echo "API ：http://$(hostname -I | awk '{print $1}'):8000/api/stocks/top100?mode=turnover"
```

```bash
# 給腳本執行權限並運行
chmod +x start.sh
sudo ./start.sh
```

---

## 4. 逐步說明

### 4-1. 建立網路

容器間透過 `twse-net` 這個私有 bridge network 通訊，彼此用容器名稱（如 `twse-backend`）互相定位，不暴露在外部網路。

```bash
docker network create twse-net
```

### 4-2. 建立資料目錄

SQLite 資料庫掛載到宿主機，確保容器重啟後資料不遺失。

```bash
sudo mkdir -p /opt/twse_heat/data
sudo chown $USER:$USER /opt/twse_heat/data
```

### 4-3. 啟動 Backend

```bash
docker run -d \
  --name twse-backend \
  --network twse-net \
  -p 8000:8000 \
  -v /opt/twse_heat/data:/app/data \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  --restart unless-stopped \
  --health-cmd "curl -f http://localhost:8000/health || exit 1" \
  --health-interval 10s \
  --health-timeout 5s \
  --health-retries 5 \
  twse-backend:latest
```

| 參數 | 說明 |
|------|------|
| `-d` | 背景執行 |
| `--name twse-backend` | 容器名稱（其他容器用此名稱連線） |
| `--network twse-net` | 加入隔離網路 |
| `-p 8000:8000` | 宿主機 8000 → 容器 8000 |
| `-v .../data:/app/data` | SQLite DB 持久化掛載 |
| `--restart unless-stopped` | 裝置重開機自動重啟 |
| `--health-*` | 健康檢查，crawler 啟動前會等待 |

### 4-4. 等待 Backend 健康（必要步驟）

Crawler 必須等 Backend 完全就緒再啟動，否則 DB 初始化可能競爭。

```bash
# 等待健康狀態
until [ "$(docker inspect --format='{{.State.Health.Status}}' twse-backend)" = "healthy" ]; do
  echo "Waiting for backend... ($(docker inspect --format='{{.State.Health.Status}}' twse-backend))"
  sleep 3
done
echo "Backend ready."
```

### 4-5. 啟動 Crawler

```bash
# 若有 FinMind Token（可選，無 token 仍可運作）
# export FINMIND_TOKEN="your_token_here"

docker run -d \
  --name twse-crawler \
  --network twse-net \
  -v /opt/twse_heat/data:/app/data \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  -e FINMIND_TOKEN="${FINMIND_TOKEN:-}" \
  --restart unless-stopped \
  twse-crawler:latest
```

> **說明**：Crawler 內建 APScheduler，平日 09:00-13:30 每 10 分鐘拉取一次，13:35 收盤最終一次，週末自動跳過。

### 4-6. 啟動 Frontend

```bash
docker run -d \
  --name twse-frontend \
  --network twse-net \
  -p 5173:80 \
  --restart unless-stopped \
  twse-frontend:latest
```

### 4-7. 確認所有容器正常

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

預期輸出：
```
NAMES            STATUS                    PORTS
twse-frontend    Up 2 minutes              0.0.0.0:5173->80/tcp
twse-crawler     Up 2 minutes
twse-backend     Up 3 minutes (healthy)    0.0.0.0:8000->8000/tcp
```

### 4-8. 驗證 API 正常回應

```bash
curl -s "http://localhost:8000/api/stocks/top100?mode=turnover&limit=5" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('date:', d['date'], '| stocks:', sum(len(s['stocks']) for s in d['sectors']))"
```

---

## 5. Systemd 自動啟動

裝置上電後自動啟動所有服務，無需人工介入。

### 5-1. 建立啟動腳本

```bash
sudo mkdir -p /opt/twse_heat
sudo tee /opt/twse_heat/start.sh > /dev/null << 'EOF'
#!/bin/bash
set -e
DATA_DIR="/opt/twse_heat/data"
NETWORK="twse-net"
mkdir -p "${DATA_DIR}"

docker network create "${NETWORK}" 2>/dev/null || true

# 清理可能殘留的舊容器
docker rm -f twse-backend twse-crawler twse-frontend 2>/dev/null || true

# Backend
docker run -d \
  --name twse-backend \
  --network "${NETWORK}" \
  -p 8000:8000 \
  -v "${DATA_DIR}:/app/data" \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  --restart unless-stopped \
  --health-cmd "curl -f http://localhost:8000/health || exit 1" \
  --health-interval 10s \
  --health-timeout 5s \
  --health-retries 5 \
  twse-backend:latest

# 等待 Backend 健康
for i in $(seq 1 30); do
  [ "$(docker inspect --format='{{.State.Health.Status}}' twse-backend)" = "healthy" ] && break
  sleep 2
done

# Crawler
docker run -d \
  --name twse-crawler \
  --network "${NETWORK}" \
  -v "${DATA_DIR}:/app/data" \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  --restart unless-stopped \
  twse-crawler:latest

# Frontend
docker run -d \
  --name twse-frontend \
  --network "${NETWORK}" \
  -p 5173:80 \
  --restart unless-stopped \
  twse-frontend:latest
EOF

sudo chmod +x /opt/twse_heat/start.sh
```

### 5-2. 建立 systemd service 檔

```bash
sudo tee /etc/systemd/system/twse-heat.service > /dev/null << 'EOF'
[Unit]
Description=Taiwan Stock Heatmap Services
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/twse_heat/start.sh
ExecStop=/bin/bash -c 'docker stop twse-frontend twse-crawler twse-backend 2>/dev/null; docker rm twse-frontend twse-crawler twse-backend 2>/dev/null; true'
StandardOutput=journal
StandardError=journal
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF
```

### 5-3. 啟用服務

```bash
sudo systemctl daemon-reload
sudo systemctl enable twse-heat.service
sudo systemctl start twse-heat.service

# 查看狀態
sudo systemctl status twse-heat.service
```

---

## 6. 常用操作指令

### 查看狀態

```bash
# 所有容器
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 健康狀態
docker inspect --format='{{.Name}}: {{.State.Health.Status}}' twse-backend
```

### 查看 Logs

```bash
# 即時 log（Ctrl+C 退出）
docker logs -f twse-crawler
docker logs -f twse-backend

# 最後 100 行
docker logs --tail 100 twse-crawler

# 指定時間範圍
docker logs --since 1h twse-backend
```

### 停止 / 重啟

```bash
# 停止全部
docker stop twse-frontend twse-crawler twse-backend

# 重啟單一容器
docker restart twse-crawler

# 完全移除（保留 DB 資料）
docker stop twse-frontend twse-crawler twse-backend
docker rm   twse-frontend twse-crawler twse-backend
```

### 進入容器偵錯

```bash
# 進入 backend 執行 Python 指令
docker exec -it twse-backend python -c "
from database import get_db
from sqlalchemy import text
db = next(get_db())
result = db.execute(text('SELECT date, COUNT(*) FROM stock_ranks GROUP BY date')).fetchall()
print(result)
"

# 進入 crawler 手動觸發一次爬取
docker exec -it twse-crawler python -c "
import sys; sys.path.insert(0, '/app')
from main import crawl_job
crawl_job(is_closing=True)
"
```

### 查看資料庫

```bash
# 確認 DB 有資料
docker exec twse-backend python -c "
from database import get_db
from sqlalchemy import text
db = next(get_db())
rows = db.execute(text('SELECT date, COUNT(*), MAX(turnover_rate) FROM stock_ranks GROUP BY date ORDER BY date DESC LIMIT 5')).fetchall()
for r in rows: print(r)
"
```

---

## 7. 更新映像檔

### 方法 A：重新 Build

```bash
# 在開發機 build 並匯出
git pull origin main
docker build -t twse-backend:latest  ./backend
docker build -t twse-crawler:latest  ./crawler
docker build -t twse-frontend:latest ./frontend

docker save twse-backend:latest  | gzip > twse-backend.tar.gz
docker save twse-crawler:latest  | gzip > twse-crawler.tar.gz
docker save twse-frontend:latest | gzip > twse-frontend.tar.gz
scp twse-*.tar.gz pi@<device-ip>:~/
```

### 方法 B：在裝置上套用更新

```bash
# 傳輸完成後，在裝置上執行：
cd ~

# 載入新映像
for f in twse-*.tar.gz; do docker load < "$f"; done

# 停止舊容器
docker stop twse-frontend twse-crawler twse-backend
docker rm   twse-frontend twse-crawler twse-backend

# 用 systemd 重啟（會用新映像）
sudo systemctl restart twse-heat.service

# 清理舊映像（可選）
docker image prune -f
```

---

## 8. 資源限制設定

嵌入式裝置 RAM 有限，可加入記憶體上限防止 OOM：

```bash
# Backend：限制 128 MB RAM
docker run -d \
  --name twse-backend \
  --memory="128m" \
  --memory-swap="128m" \
  --network twse-net \
  -p 8000:8000 \
  -v /opt/twse_heat/data:/app/data \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  --restart unless-stopped \
  --health-cmd "curl -f http://localhost:8000/health || exit 1" \
  --health-interval 10s \
  --health-timeout 5s \
  --health-retries 5 \
  twse-backend:latest

# Crawler：爬取高峰約 80 MB，限制 150 MB
docker run -d \
  --name twse-crawler \
  --memory="150m" \
  --memory-swap="150m" \
  --network twse-net \
  -v /opt/twse_heat/data:/app/data \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  --restart unless-stopped \
  twse-crawler:latest

# Frontend (nginx)：限制 32 MB 即可
docker run -d \
  --name twse-frontend \
  --memory="32m" \
  --memory-swap="32m" \
  --network twse-net \
  -p 5173:80 \
  --restart unless-stopped \
  twse-frontend:latest
```

> **注意**：`--memory-swap` 與 `--memory` 相同時表示不使用 swap，確保容器被 OOM killer 終止而非拖慢裝置。

---

## 9. 故障排除

### 問題：Backend 健康檢查一直 `unhealthy`

```bash
docker logs twse-backend --tail 50
# 確認 /health endpoint 是否存在
curl -v http://localhost:8000/health
```

**常見原因**：`./data` 目錄權限不足。
```bash
sudo chown -R $USER:$USER /opt/twse_heat/data
```

### 問題：Crawler 無資料 / 全部週轉率為 0

```bash
docker logs twse-crawler --tail 30
# 觀察是否有 "Total volume = 0" 警告
```

**原因**：在非交易時間（週末、假日）TWSE API 仍回傳前一交易日，若抓到 0 值會自動跳過，屬正常行為。  
手動觸發一次（工作日）：
```bash
docker exec twse-crawler python -c "
import sys; sys.path.insert(0, '/app')
from main import crawl_job; crawl_job(is_closing=True)
"
```

### 問題：Frontend 空白頁 / API 連線失敗

```bash
# 確認前端能打到後端
docker exec twse-frontend wget -qO- http://twse-backend:8000/health
# 預期輸出：{"status":"ok"}
```

**原因**：容器未加入相同 network。確認兩個容器都有 `--network twse-net`。

### 問題：容器啟動後立即 Exited

```bash
docker logs <container-name>
# 查看錯誤訊息
docker inspect <container-name> --format='{{.State.ExitCode}}'
```

### 問題：eMMC 空間不足

```bash
# 查看 Docker 佔用
docker system df

# 清理所有未使用映像、容器、快取
docker system prune -a --volumes
```

### 問題：Raspberry Pi ARM 架構 Build 失敗

部分映像可能需要指定平台：
```bash
docker build --platform linux/arm64 -t twse-backend:latest  ./backend
docker build --platform linux/arm64 -t twse-crawler:latest  ./crawler
docker build --platform linux/arm64 -t twse-frontend:latest ./frontend
```

---

## 附錄：映像檔大小參考

| 映像 | 壓縮大小 | 執行期 RAM（idle） | 執行期 RAM（高峰） |
|------|----------|---------------------|---------------------|
| twse-backend | 217 MB | ~63 MB | ~80 MB |
| twse-crawler | 392 MB | ~45 MB | ~80 MB |
| twse-frontend | 62.5 MB | ~13 MB | ~13 MB |
| **合計** | **671.5 MB** | **~121 MB** | **~173 MB** |

> DB 成長速度：約 110 MB / 年（250 交易日 × 1956 支股票）

---

*文件最後更新：2026-05-16*  
*專案：[github.com/hsinchi-yen/twse_top300_heat](https://github.com/hsinchi-yen/twse_top300_heat)*
