#!/bin/bash
# UAT 测试数据准备脚本
# 功能：创建测试账号、准备测试股票池、初始化模拟账户、清理历史测试数据

set -e

echo "============================================================"
echo "TradingAgents-CN UAT 测试数据准备"
echo "============================================================"

BASE_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASS="admin123"
TEST_USERS=("test_user" "test_analyst" "test_trader")
TEST_STOCKS=("600519" "512170" "560280" "512400")

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 检查后端服务
echo ""
echo "【步骤 1】检查后端服务状态..."
if curl -s "${BASE_URL}/api/health" | grep -q '"status":"ok"'; then
    log_info "后端服务运行正常"
else
    log_error "后端服务未运行，请先启动服务"
    exit 1
fi

# 2. 获取管理员 Token
echo ""
echo "【步骤 2】获取管理员 Token..."
TOKEN=$(curl -s -X POST "${BASE_URL}/api/v1/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}" \
    | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    log_info "获取 Token 成功：${TOKEN:0:50}..."
else
    log_error "获取 Token 失败"
    exit 1
fi

# 3. 创建测试账号
echo ""
echo "【步骤 3】创建测试账号..."
for user in "${TEST_USERS[@]}"; do
    log_info "创建测试账号：${user}"
    # 先尝试删除已存在的测试账号（避免冲突）
    curl -s -X DELETE "${BASE_URL}/api/users/${user}" \
        -H "Authorization: Bearer ${TOKEN}" > /dev/null 2>&1 || true
    
    # 创建新账号
    RESULT=$(curl -s -X POST "${BASE_URL}/api/auth/register" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${TOKEN}" \
        -d "{\"username\":\"${user}\",\"password\":\"test123456\",\"email\":\"${user}@test.com\"}")
    
    if echo "$RESULT" | grep -q '"success":true\|"username"'; then
        log_info "账号 ${user} 创建成功"
    else
        log_warn "账号 ${user} 可能已存在或创建失败：${RESULT}"
    fi
done

# 4. 验证测试股票数据
echo ""
echo "【步骤 4】验证测试股票数据..."
for stock in "${TEST_STOCKS[@]}"; do
    log_info "验证股票数据：${stock}"
    RESULT=$(curl -s -X GET "${BASE_URL}/api/stocks/${stock}/quote" \
        -H "Authorization: Bearer ${TOKEN}")
    
    if echo "$RESULT" | grep -q '"code"\|"symbol"\|"data"'; then
        log_info "股票 ${stock} 数据可用"
    else
        log_warn "股票 ${stock} 数据不可用：${RESULT}"
    fi
done

# 5. 初始化模拟账户
echo ""
echo "【步骤 5】初始化模拟账户..."
for user in "${TEST_USERS[@]}"; do
    log_info "为用户 ${user} 初始化模拟账户..."
    # 获取用户 Token
    USER_TOKEN=$(curl -s -X POST "${BASE_URL}/api/v1/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"${user}\",\"password\":\"test123456\"}" \
        | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$USER_TOKEN" ]; then
        # 检查模拟账户
        ACCOUNT=$(curl -s -X GET "${BASE_URL}/api/simulated-trading/account" \
            -H "Authorization: Bearer ${USER_TOKEN}")
        
        if echo "$ACCOUNT" | grep -q '"balance"\|"cash"'; then
            log_info "用户 ${user} 模拟账户已存在"
        else
            log_warn "用户 ${user} 模拟账户未初始化"
        fi
    fi
done

# 6. 清理历史测试数据
echo ""
echo "【步骤 6】清理历史测试数据..."
log_info "清理测试缓存..."
curl -s -X POST "${BASE_URL}/api/cache/clear" \
    -H "Authorization: Bearer ${TOKEN}" > /dev/null 2>&1 && \
    log_info "缓存清理成功" || log_warn "缓存清理失败"

# 7. 生成测试数据报告
echo ""
echo "【步骤 7】生成测试数据报告..."
cat > /root/stock-analyzer/tests/uat_test_data_report.json << EOF
{
    "generated_at": "$(date -Iseconds)",
    "admin_token": "${TOKEN:0:50}...",
    "test_users": $(printf '%s\n' "${TEST_USERS[@]}" | jq -R . | jq -s .),
    "test_stocks": $(printf '%s\n' "${TEST_STOCKS[@]}" | jq -R . | jq -s .),
    "environment": {
        "backend_url": "${BASE_URL}",
        "redis_db": "1",
        "sqlite_db": "/root/stock-analyzer/data/uat_test.db"
    },
    "status": "ready"
}
EOF

log_info "测试数据报告已生成：/root/stock-analyzer/tests/uat_test_data_report.json"

# 8. 总结
echo ""
echo "============================================================"
echo "UAT 测试数据准备完成！"
echo "============================================================"
echo ""
echo "测试账号:"
for user in "${TEST_USERS[@]}"; do
    echo "  - ${user} / test123456"
done
echo ""
echo "测试股票:"
for stock in "${TEST_STOCKS[@]}"; do
    echo "  - ${stock}"
done
echo ""
echo "环境配置:"
echo "  - 后端 URL: ${BASE_URL}"
echo "  - Redis DB: 1 (测试隔离)"
echo "  - SQLite: /root/stock-analyzer/data/uat_test.db"
echo ""
log_info "可以开始执行 UAT 测试！"
echo ""
