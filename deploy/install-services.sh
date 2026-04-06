#!/bin/bash
# install-services.sh - 一键安装系统服务（需要 sudo）
# 用法: sudo bash install-services.sh

set -e

echo "🚀 安装 TradingAgents-CN 系统服务..."

# 停止旧进程
pkill -f "api_server.py" || true
pkill -f "vite" || true

# 安装服务文件
echo "📦 安装 systemd 服务..."
cp tradingagents-api.service /etc/systemd/system/
cp tradingagents-frontend.service /etc/systemd/system/

# 重载 systemd
systemctl daemon-reload

# 启用开机自启
systemctl enable tradingagents-api
systemctl enable tradingagents-frontend

# 启动服务
systemctl start tradingagents-api
systemctl start tradingagents-frontend

# 状态检查
echo ""
echo "📊 服务状态:"
systemctl status tradingagents-api --no-pager | head -5
echo ""
systemctl status tradingagents-frontend --no-pager | head -5

echo ""
echo "✅ 安装完成！"
echo "  重启服务: sudo systemctl restart tradingagents-api tradingagents-frontend"
echo "  查看日志: sudo journalctl -u tradingagents-api -f"
