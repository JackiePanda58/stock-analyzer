#!/bin/bash
# 发送告警到 Feishu
# 用法: ./send_alert.sh "message"

ALERT_DIR="/root/stock-analyzer/logs/alerts"
FEISHU_WEBHOOK=""  # 如果有 webhook 可配置

message="$1"

# 方案1: 写入告警队列文件（供 OpenClaw 心跳读取）
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$ALERT_DIR/alert_queue.txt"

# 方案2: 如果配置了 webhook，发送到 Feishu
if [ -n "$FEISHU_WEBHOOK" ]; then
  curl -s -X POST "$FEISHU_WEBHOOK" \
    -H 'Content-Type: application/json' \
    -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"TradingAgents 告警: $message\"}}" \
    >/dev/null 2>&1
fi

# 方案3: 记录到系统日志
logger -t tradingagents-alert "$message"

echo "Alert recorded: $message"