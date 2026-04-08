#!/bin/bash
# 测试数据准备脚本
# 功能：清理旧数据、创建测试股票、预生成测试报告

set -e

echo "📦 准备测试数据..."

# 1. 清理旧数据
echo "  清理旧数据..."
redis-cli FLUSHDB > /dev/null 2>&1 || echo "  ⚠️ Redis 清理失败"
rm -rf /root/stock-analyzer/reports/*.md 2>/dev/null || echo "  ⚠️ 报告清理失败"

# 2. 获取 Token
echo "  获取测试 Token..."
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "  Token: ${TOKEN:0:30}..."

# 3. 创建测试股票
echo "  创建测试股票..."
for stock in "600519:A 股:贵州茅台" "512170:A 股:医疗 ETF" "560280:A 股:工业 ETF" "NVDA:美股:英伟达"; do
    IFS=':' read -r code market name <<< "$stock"
    curl -s -X POST http://localhost:8080/api/favorites/ \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"stock_code\":\"$code\",\"market_type\":\"$market\"}" > /dev/null
    echo "    ✓ $code ($name)"
done

# 4. 验证测试数据
echo "  验证测试数据..."
FAVORITES=$(curl -s http://localhost:8080/api/favorites/ \
  -H "Authorization: Bearer $TOKEN" | \
  python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data.get('data', [])))")

echo "  自选股数量：$FAVORITES"

if [ "$FAVORITES" -ge 3 ]; then
    echo "✅ 测试数据准备完成！"
else
    echo "⚠️ 测试数据可能不完整"
fi
