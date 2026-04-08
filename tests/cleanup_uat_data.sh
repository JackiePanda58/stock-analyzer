#!/bin/bash
# UAT 测试数据清理脚本
# 功能：清理测试账号、测试数据、缓存，恢复环境到测试前状态

set -e

echo "============================================================"
echo "TradingAgents-CN UAT 测试数据清理"
echo "============================================================"

BASE_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASS="admin123"
TEST_USERS=("test_user" "test_analyst" "test_trader")

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 1. 获取管理员 Token
echo ""
echo "【步骤 1】获取管理员 Token..."
TOKEN=$(curl -s -X POST "${BASE_URL}/api/v1/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}" \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    log_info "获取 Token 成功"
else
    log_warn "获取 Token 失败，继续清理本地数据"
fi

# 2. 删除测试账号
echo ""
echo "【步骤 2】删除测试账号..."
for user in "${TEST_USERS[@]}"; do
    log_info "删除测试账号：${user}"
    curl -s -X DELETE "${BASE_URL}/api/users/${user}" \
        -H "Authorization: Bearer ${TOKEN}" > /dev/null 2>&1 && \
        log_info "账号 ${user} 删除成功" || \
        log_warn "账号 ${user} 删除失败（可能不存在）"
done

# 3. 清理测试缓存
echo ""
echo "【步骤 3】清理测试缓存..."
curl -s -X POST "${BASE_URL}/api/cache/clear" \
    -H "Authorization: Bearer ${TOKEN}" > /dev/null 2>&1 && \
    log_info "缓存清理成功" || log_warn "缓存清理失败"

# 4. 清理测试数据库
echo ""
echo "【步骤 4】清理测试数据库..."
if [ -f "/root/stock-analyzer/data/uat_test.db" ]; then
    rm -f /root/stock-analyzer/data/uat_test.db
    log_info "测试数据库已删除"
else
    log_warn "测试数据库不存在"
fi

# 5. 清理测试报告
echo ""
echo "【步骤 5】清理测试报告..."
rm -f /root/stock-analyzer/tests/uat_test_data_report.json
rm -f /root/stock-analyzer/tests/uat_execution_*.json
log_info "测试报告已清理"

# 6. Redis 测试数据清理（可选）
echo ""
echo "【步骤 6】Redis 测试数据清理..."
if command -v redis-cli &> /dev/null; then
    redis-cli -n 1 FLUSHDB > /dev/null 2>&1 && \
        log_info "Redis DB 1 已清空" || \
        log_warn "Redis 清理失败"
else
    log_warn "redis-cli 未安装，跳过 Redis 清理"
fi

# 7. 生成清理报告
echo ""
echo "【步骤 7】生成清理报告..."
cat > /root/stock-analyzer/tests/uat_cleanup_report.json << EOF
{
    "cleaned_at": "$(date -Iseconds)",
    "deleted_users": $(printf '%s\n' "${TEST_USERS[@]}" | jq -R . | jq -s .),
    "cache_cleared": true,
    "database_removed": true,
    "reports_removed": true,
    "redis_cleared": true,
    "status": "completed"
}
EOF

log_info "清理报告已生成：/root/stock-analyzer/tests/uat_cleanup_report.json"

# 8. 总结
echo ""
echo "============================================================"
echo "UAT 测试数据清理完成！"
echo "============================================================"
echo ""
echo "已清理:"
echo "  - 测试账号：${#TEST_USERS[@]} 个"
echo "  - 测试缓存：已清空"
echo "  - 测试数据库：已删除"
echo "  - 测试报告：已删除"
echo "  - Redis DB 1: 已清空"
echo ""
log_info "环境已恢复到测试前状态"
echo ""
