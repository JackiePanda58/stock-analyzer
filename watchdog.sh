#!/bin/bash
# watchdog.sh - 服务守护脚本，崩溃自动重启
# 用法: nohup bash watchdog.sh &

LOG="/root/stock-analyzer/logs/watchdog.log"
API_PID=""
FRONTEND_PID=""
CHECK_INTERVAL=10

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

start_api() {
    cd /root/stock-analyzer
    python3 api_server.py >> logs/api.log 2>&1 &
    API_PID=$!
    log "API started, PID=$API_PID"
}

start_frontend() {
    cd /root/stock-analyzer/frontend
    npm run dev >> ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    log "Frontend started, PID=$FRONTEND_PID"
}

check_and_restart() {
    # 检查 API
    if ! kill -0 $API_PID 2>/dev/null; then
        log "API died, restarting..."
        start_api
    fi

    # 检查 Frontend
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        log "Frontend died, restarting..."
        start_frontend
    fi
}

log "Watchdog started"
start_api
start_frontend

while true; do
    sleep $CHECK_INTERVAL
    check_and_restart
done
