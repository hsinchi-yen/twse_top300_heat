# Remote Yocto Deploy — Operating Rules

> Updated: 2026-06-11
> Target: `root@10.1.1.230`
> Platform: Yocto aarch64, Docker only, `--network host`

## Runtime shape

Production uses three images and four containers:

1. `twse-backend`
2. `twse-crawler`
3. `twse-etf-crawler`
4. `twse-frontend`

The ETF crawler reuses the stock crawler image with `etf_main.py`.

## Prerequisites

| Requirement | Check |
|---|---|
| Docker Desktop with buildx | `docker buildx version` |
| ARM64 builder | `docker buildx inspect arm64-builder` |
| SSH access | `ssh root@10.1.1.230 echo ok` |
| Remote deploy dir | `/root/TWSE_TOP100_HEAT/` |
| Launcher script | `run_containers.sh` |

## Step 1 — Check working tree

```powershell
git -c safe.directory="C:/Users/lance.tn/AI Project/Twse_Top100_Heat" status --short
git -c safe.directory="C:/Users/lance.tn/AI Project/Twse_Top100_Heat" log --oneline -3
```

## Step 2 — Build ARM64 images locally

```powershell
docker buildx build --builder arm64-builder --platform linux/arm64 --load `
  --tag twse_top100_heat-backend:latest `
  --file backend\Dockerfile `
  backend
docker save twse_top100_heat-backend:latest | gzip > twse-backend.tar.gz

docker buildx build --builder arm64-builder --platform linux/arm64 --load `
  --tag twse_top100_heat-crawler:latest `
  --file crawler\Dockerfile `
  crawler
docker save twse_top100_heat-crawler:latest | gzip > twse-crawler.tar.gz

docker buildx build --builder arm64-builder --platform linux/arm64 --load `
  --tag twse_top100_heat-frontend:latest `
  --file frontend\Dockerfile `
  frontend
docker save twse_top100_heat-frontend:latest | gzip > twse-frontend.tar.gz
```

## Step 3 — Transfer artifacts

```powershell
$sshOpts = @("-o","StrictHostKeyChecking=no","-o","ConnectTimeout=10")
scp @sshOpts twse-backend.tar.gz twse-crawler.tar.gz twse-frontend.tar.gz `
  run_containers.sh `
  root@10.1.1.230:/root/TWSE_TOP100_HEAT/
```

## Step 4 — Prepare remote env

Remote `.env` should live beside `run_containers.sh`:

```dotenv
FINMIND_TOKEN=<your_token>
ALLOWED_ORIGINS=http://10.1.1.230:8504
SCORE_CANDIDATE_LIMIT=600
BUY_SCORE_QUOTA_WAIT_S=3600
ETF_KEEP_DAYS=90
```

Important:
- `FINMIND_TOKEN` is needed only by `twse-crawler`
- backend and crawler must share `/root/TWSE_TOP100_HEAT/data`

## Step 5 — Deploy on remote

```bash
ssh root@10.1.1.230
cd /root/TWSE_TOP100_HEAT

mkdir -p data

docker load < twse-backend.tar.gz
docker load < twse-crawler.tar.gz
docker load < twse-frontend.tar.gz

chmod +x run_containers.sh
bash run_containers.sh
```

`run_containers.sh` will:
- remove old containers
- start backend and wait for health
- start stock crawler
- start ETF crawler
- start frontend

## Step 6 — Verify

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
curl -sf http://localhost:8000/health
curl -sf http://localhost:8504/api/stocks/top100?mode=volume | head -c 120
curl -sf http://localhost:8504/api/etf?sort_by=turnover | head -c 120
curl -sf http://localhost:8000/api/scores | head -c 120
```

Browser URL:

```text
http://10.1.1.230:8504
```

## Step 7 — Cleanup

Remote:

```bash
docker image prune -f
rm -f twse-backend.tar.gz twse-crawler.tar.gz twse-frontend.tar.gz
```

Local:

```powershell
Remove-Item twse-backend.tar.gz, twse-crawler.tar.gz, twse-frontend.tar.gz -ErrorAction SilentlyContinue
```

## Useful runtime commands

```bash
docker logs -f twse-backend
docker logs -f twse-crawler
docker logs -f twse-etf-crawler

docker restart twse-crawler

cd /root/TWSE_TOP100_HEAT && bash run_containers.sh

docker exec twse-crawler python -c "
import sys; sys.path.insert(0, '/app')
from main import crawl_job
crawl_job(is_closing=True)
"

docker exec twse-etf-crawler python -c "
import sys; sys.path.insert(0, '/app')
from etf_main import etf_crawl_job
etf_crawl_job(is_closing=True)
"
```
