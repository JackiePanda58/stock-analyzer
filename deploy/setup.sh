#!/bin/bash
# setup.sh - 服务器初始化配置（需要 sudo）
# 用法: sudo bash setup.sh

set -e

echo "🔧 服务器初始化..."

# 1. 增加 swap（如果没有足够 swap）
TOTAL_SWAP=$(free -b | awk '/Swap:/ {print $2}')
NEEDED_SWAP=$((4 * 1024 * 1024 * 1024))  # 4GB

if [ "$TOTAL_SWAP" -lt "$NEEDED_SWAP" ]; then
    echo "📦 增加 4GB swap..."
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
    echo "✅ swap 已增加"
else
    echo "✅ swap 空间足够"
fi

# 2. 安装 Node.js 优化工具（可选）
# apt-get install -y nodejs npm --no-install-recommendations

echo "✅ 初始化完成！"
echo ""
echo "下一步："
echo "  1. cd /root/stock-analyzer"
echo "  2. bash deploy/install-services.sh"
echo "  3. 或者直接运行: bash watchdog.sh &"
