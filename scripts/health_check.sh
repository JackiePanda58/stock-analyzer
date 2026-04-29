#!/bin/bash
URL="http://127.0.0.1:8080/api/health"
MAX_TIME=5
SLOW_LIMIT=10
SVC="tradingagents"
LOG="/var/log/tradingagents_health.log"
COOLDOWN=30
NOW=$(date +%s)
LAST_RESTART_FILE="/tmp/${SVC}_last_restart"

if [ -f "$LAST_RESTART_FILE" ]; then
    LAST=$(cat "$LAST_RESTART_FILE")
    if [ $((NOW - LAST)) -lt $COOLDOWN ]; then exit 0; fi
fi

START=$(date +%s%N)
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" --max-time $MAX_TIME)
END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000000 ))

FAIL=false
if [ "$CODE" != "200" ]; then FAIL=true; REASON="HTTP $CODE"; fi
if [ $ELAPSED -gt $SLOW_LIMIT ]; then FAIL=true; REASON="Slow ${ELAPSED}s"; fi

if [ "$FAIL" = true ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $REASON | Restarting..." >> "$LOG"
    echo $NOW > "$LAST_RESTART_FILE"
    systemctl restart $SVC
fi
