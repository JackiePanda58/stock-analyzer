#!/usr/bin/env python3
"""
飞书告警推送脚本
用法: python feishu_alert.py "告警消息内容"
"""

import os
import sys
import json
import requests
from datetime import datetime

# OpenClaw Gateway 配置
OPENCLAW_GATEWAY = "http://localhost:15545"  # OpenClaw Gateway 地址
CHANNEL = "feishu"
TARGET_USER = "ou_fa14240ad1821e000cf72ccaa09addb5"  # AaronXiong 的 open_id

# 飞书 Webhook 配置（可选，备用方案）
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

def send_via_openclaw(message: str) -> bool:
    """通过 OpenClaw Gateway 发送飞书消息"""
    try:
        # 使用 OpenClaw 内部 API
        payload = {
            "action": "send",
            "channel": CHANNEL,
            "target": f"user:{TARGET_USER}",
            "message": message
        }
        
        response = requests.post(
            f"{OPENCLAW_GATEWAY}/message",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[OK] 告警已通过 OpenClaw 发送")
            return True
        else:
            print(f"[ERROR] OpenClaw 发送失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] OpenClaw 发送异常: {e}")
        return False

def send_via_webhook(message: str) -> bool:
    """通过飞书 Webhook 发送消息（备用方案）"""
    if not FEISHU_WEBHOOK:
        return False
    
    try:
        payload = {
            "msg_type": "text",
            "content": {
                "text": f"TradingAgents 告警: {message}"
            }
        }
        
        response = requests.post(
            FEISHU_WEBHOOK,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[OK] 告警已通过 Webhook 发送")
            return True
        else:
            print(f"[ERROR] Webhook 发送失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Webhook 发送异常: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("用法: python feishu_alert.py '告警消息'")
        sys.exit(1)
    
    message = sys.argv[1]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"⚠️ TradingAgents 告警 [{timestamp}]\n{message}"
    
    # 优先使用 OpenClaw Gateway
    if send_via_openclaw(full_message):
        sys.exit(0)
    
    # 备用：使用飞书 Webhook
    if send_via_webhook(message):
        sys.exit(0)
    
    # 都失败，写入本地队列
    alert_queue = "/root/stock-analyzer/logs/alerts/alert_queue.txt"
    with open(alert_queue, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[WARN] 告警已写入本地队列: {alert_queue}")
    sys.exit(1)

if __name__ == "__main__":
    main()