# 台股熱力圖 — 嵌入式 Docker 部署手冊

> Updated: 2026-06-11
> 適用環境：僅安裝 Docker Engine 的嵌入式 Linux / Yocto 裝置
> 目前架構：3 個 image / 4 個 container / 共用 `data/` / `--network host`

## 1. 目前部署模型

容器如下：

1. `twse-backend`
2. `twse-crawler`
3. `twse-etf-crawler`
4. `twse-frontend`

其中 `twse-etf-crawler` 直接重用 crawler image，以 `python etf_main.py` 啟動。

## 2. 為什麼一定用 `--network host`

Yocto / 精簡核心常缺少 `iptable_raw`，Docker `-p` port mapping 會失敗。

因此 production 一律採：

```bash
docker run --network host ...
```

## 3. 首次部署建議流程

1. 在開發機 build 三個 image
2. `docker save | gzip`
3. `scp` 到裝置
4. 在裝置端 `docker load`
5. 執行 repo 內建的 `run_containers.sh`

若是本專案的標準 Yocto 主機，請優先參考根目錄的 [remote_deploy.md](../remote_deploy.md)。

## 4. 裝置端目錄

```text
/root/TWSE_TOP100_HEAT/
  .env
  run_containers.sh
  data/
    twse_heat.db
    buy_scores/
```

## 5. `.env` 範例

```dotenv
FINMIND_TOKEN=<your_token>
ALLOWED_ORIGINS=http://<device-ip>:8504
SCORE_CANDIDATE_LIMIT=480
BUY_SCORE_QUOTA_WAIT_S=3600
BUY_SCORE_QUOTA_MAX_CYCLES=24
ETF_KEEP_DAYS=90
```

## 6. 啟動

```bash
cd /root/TWSE_TOP100_HEAT
mkdir -p data
chmod +x run_containers.sh
bash run_containers.sh
```

## 7. 啟動後應有的行為

- backend 先啟動並通過 `/health`
- stock crawler 啟動後先做一次 startup fetch
- ETF crawler 啟動後先做一次 startup fetch
- frontend 提供 `8504`

## 8. 目前排程

### Stock crawler

- `09:00-13:30`：每分鐘
- `16:00`：收盤最終抓取
- `08:55`：日常維護
- 每月 1 日 `02:00`：VACUUM
- 每月 1 日 `03:00`：買進評分
- 每分鐘：force-refresh 旗標檢查

### ETF crawler

- `09:00-13:30`：每分鐘
- `16:05`：收盤最終抓取
- `08:50`：資產規模刷新
- 每月 1 日 `02:30`：修剪歷史

## 9. 驗證

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
curl -sf http://localhost:8000/health
curl -sf http://localhost:8504/api/stocks/top100?mode=volume | head -c 120
curl -sf http://localhost:8504/api/etf?sort_by=turnover | head -c 120
curl -sf http://localhost:8000/api/scores | head -c 120
```

前端網址：

```text
http://<device-ip>:8504
```

## 10. 常用維運指令

```bash
docker logs -f twse-backend
docker logs -f twse-crawler
docker logs -f twse-etf-crawler

docker restart twse-crawler
docker restart twse-etf-crawler

cd /root/TWSE_TOP100_HEAT && bash run_containers.sh
```

## 11. 常見錯誤

### `can't initialize iptables table 'raw'`

代表核心缺少 `iptable_raw`，不要改回 `-p`；請維持 `--network host`。

### 前端顯示無資料

先檢查：

```bash
docker logs --tail 100 twse-backend
docker logs --tail 100 twse-crawler
docker logs --tail 100 twse-etf-crawler
ls -la /root/TWSE_TOP100_HEAT/data/buy_scores/
```

### 買進評分沒有更新

檢查 crawler 是否有 `FINMIND_TOKEN`，以及 backend / crawler 是否共用同一個 `data/` 目錄。
