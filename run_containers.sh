#!/bin/bash
set -e
# Load secret env vars
[ -f "$(dirname "$0")/.env" ] && source "$(dirname "$0")/.env"
DATA_DIR="/root/TWSE_TOP100_HEAT/data"

LOG_OPTS="--log-driver json-file --log-opt max-size=10m --log-opt max-file=3"

echo "[1/4] Clean old containers..."
docker rm -f twse-backend twse-crawler twse-etf-crawler twse-frontend 2>/dev/null || true

echo "[2/4] Start Backend (--network host)..."
docker run -d \
  --name twse-backend \
  --network host \
  -v ${DATA_DIR}:/app/data \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  -e SCORES_DIR="/app/data/buy_scores" \
  -e SCORING_FLAG_STALE_S="${SCORING_FLAG_STALE_S:-10800}" \
  -e ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-}" \
  ${LOG_OPTS} \
  --restart unless-stopped \
  --health-cmd "curl -f http://localhost:8000/health || exit 1" \
  --health-interval 10s \
  --health-timeout 5s \
  --health-retries 5 \
  twse_top100_heat-backend:latest

echo "  Waiting for backend healthy..."
for i in $(seq 1 30); do
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' twse-backend 2>/dev/null || echo "starting")
  if [ "${STATUS}" = "healthy" ]; then
    echo "  Backend healthy after ${i} checks."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Backend did not become healthy."
    docker logs --tail 30 twse-backend
    exit 1
  fi
  sleep 2
done

echo "[3/4] Start Crawler (--network host)..."
docker run -d \
  --name twse-crawler \
  --network host \
  -v ${DATA_DIR}:/app/data \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  -e FINMIND_TOKEN="${FINMIND_TOKEN:-}" \
  -e SCORES_DIR="/app/data/buy_scores" \
  -e SCORE_CANDIDATE_LIMIT="${SCORE_CANDIDATE_LIMIT:-600}" \
  -e BUY_SCORE_QUOTA_WAIT_S="${BUY_SCORE_QUOTA_WAIT_S:-3600}" \
  -e SCORING_FLAG_STALE_S="${SCORING_FLAG_STALE_S:-10800}" \
  ${LOG_OPTS} \
  --restart unless-stopped \
  twse_top100_heat-crawler:latest

echo "[3b/4] Start ETF Crawler (--network host)..."
docker run -d \
  --name twse-etf-crawler \
  --network host \
  -v ${DATA_DIR}:/app/data \
  -e DATABASE_URL="sqlite:////app/data/twse_heat.db" \
  -e ETF_KEEP_DAYS="${ETF_KEEP_DAYS:-90}" \
  ${LOG_OPTS} \
  --restart unless-stopped \
  --entrypoint python \
  twse_top100_heat-crawler:latest etf_main.py

echo "[4/4] Start Frontend (--network host, port 8504)..."
docker run -d \
  --name twse-frontend \
  --network host \
  ${LOG_OPTS} \
  --restart unless-stopped \
  -e NGINX_PORT=8504 \
  -e BACKEND_HOST=localhost \
  twse_top100_heat-frontend:latest

echo ""
echo "=== Container Status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Networks}}"

HOST_IP=$(ip route get 1 | awk '{print $7; exit}' 2>/dev/null || hostname -I | awk '{print $1}')
echo ""
echo "Frontend : http://${HOST_IP}:8504"
echo "API      : http://${HOST_IP}:8000/api/stocks/top100?mode=turnover"
echo "Scores   : http://${HOST_IP}:8000/api/scores"
