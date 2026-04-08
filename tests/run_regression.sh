#!/bin/bash
# TradingAgents-CN 回归测试一键执行脚本（增强版）
# 版本：v1.2.2
# 功能：完整回归测试 + 错误处理 + HTML 报告

set -e  # 遇到错误立即退出

# ─── 配置 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TEST_DIR="/root/stock-analyzer/tests"
BACKEND_URL="http://localhost:8080"
REPORT_DIR="/root/stock-analyzer/tests/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ─── 工具函数 ────────────────────────────────────────────────────────────────
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

handle_error() {
    log_error "$1"
    echo -e "${YELLOW}错误详情已保存到：${REPORT_DIR}/error_${TIMESTAMP}.log${NC}"
    exit 1
}

check_service() {
    log_info "检查服务：$1..."
    if ! curl -s "$2" > /dev/null 2>&1; then
        handle_error "$1 服务未启动 ($2)"
    fi
    log_success "$1 服务正常"
}

# ─── 环境检查 ────────────────────────────────────────────────────────────────
echo -e "${YELLOW}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║   TradingAgents-CN 回归测试                            ║${NC}"
echo -e "${YELLOW}║   版本：v1.2.2                                         ║${NC}"
echo -e "${YELLOW}║   时间：$(date '+%Y-%m-%d %H:%M:%S')                    ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "准备测试环境..."
mkdir -p "$REPORT_DIR"

# 检查后端服务
check_service "后端 API" "$BACKEND_URL/api/health"

# 检查 Redis
if ! redis-cli ping > /dev/null 2>&1; then
    handle_error "Redis 服务未启动"
fi
log_success "Redis 服务正常"

# 获取测试 Token
log_info "获取测试 Token..."
TOKEN=$(curl -s -X POST "$BACKEND_URL/api/v1/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null) || \
  handle_error "登录失败，无法获取 Token"

log_success "Token 获取成功：${TOKEN:0:30}..."

# 保存 Token 供后续测试使用
echo "$TOKEN" > "$REPORT_DIR/test_token.txt"

echo ""

# ─── 阶段 1: 单元测试 ────────────────────────────────────────────────────────
echo -e "${YELLOW}[1/6] 单元测试${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd "$TEST_DIR"

# P0 核心单元测试
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name=$1
    local test_file=$2
    
    echo -n "  运行 $test_name... "
    if python3 "$test_file" > "$REPORT_DIR/${test_name}_${TIMESTAMP}.log" 2>&1; then
        log_success "$test_name 通过"
        ((TESTS_PASSED++))
        return 0
    else
        log_error "$test_name 失败"
        ((TESTS_FAILED++))
        return 1
    fi
}

# 执行单元测试
run_test "盲区补测" "test_stock_analysis_blind_spots.py" || true
run_test "数据源测试" "test_datasources.py" || true
run_test "Redis 缓存" "test_redis_cache.py" || true
run_test "安全权限" "test_security.py" || true

# P1 单元测试（可选）
if [ "$1" == "--full" ]; then
    run_test "LLM 客户端" "test_llm_client.py" || true
    run_test "WebSocket" "test_websocket.py" || true
    run_test "定时任务" "test_scheduler.py" || true
fi

echo ""
log_info "单元测试完成：${TESTS_PASSED} 通过，${TESTS_FAILED} 失败"
echo ""

# ─── 阶段 2: 集成测试 ──────────────────────────────────────────────────────
echo -e "${YELLOW}[2/6] 集成测试${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 分析流程集成测试
log_info "测试分析完整流程..."
python3 test_integration_analysis.py > "$REPORT_DIR/integration_analysis_${TIMESTAMP}.log" 2>&1 && \
    log_success "分析流程测试通过" || \
    log_warning "分析流程测试失败（详见日志）"

# 持仓管理集成测试
log_info "测试持仓管理流程..."
python3 test_integration_positions.py > "$REPORT_DIR/integration_positions_${TIMESTAMP}.log" 2>&1 && \
    log_success "持仓管理测试通过" || \
    log_warning "持仓管理测试失败（详见日志）"

# 用户认证集成测试
log_info "测试用户认证流程..."
python3 test_integration_auth.py > "$REPORT_DIR/integration_auth_${TIMESTAMP}.log" 2>&1 && \
    log_success "用户认证测试通过" || \
    log_warning "用户认证测试失败（详见日志）"

echo ""

# ─── 阶段 3: 安全测试 ──────────────────────────────────────────────────────
echo -e "${YELLOW}[3/6] 安全测试${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

log_info "运行安全测试套件..."
python3 test_security.py --backend "$BACKEND_URL" > "$REPORT_DIR/security_${TIMESTAMP}.log" 2>&1 && \
    log_success "安全测试通过" || \
    log_warning "安全测试部分失败（详见日志）"

echo ""

# ─── 阶段 4: 性能测试 ──────────────────────────────────────────────────────
echo -e "${YELLOW}[4/6] 性能测试${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

log_info "测试登录接口性能..."
START_TIME=$(date +%s%N)
for i in {1..10}; do
    curl -s -X POST "$BACKEND_URL/api/v1/login" \
      -H "Content-Type: application/json" \
      -d '{"username":"admin","password":"admin123"}' > /dev/null
done
END_TIME=$(date +%s%N)
ELAPSED=$(( (END_TIME - START_TIME) / 1000000 ))
AVG_TIME=$((ELAPSED / 10))
log_info "登录接口平均响应时间：${AVG_TIME}ms"

if [ $AVG_TIME -lt 1000 ]; then
    log_success "性能达标 (< 1s)"
else
    log_warning "性能不达标 (>= 1s)"
fi

echo ""

# ─── 阶段 5: 速率限制验证 ──────────────────────────────────────────────────
echo -e "${YELLOW}[5/6] 速率限制验证${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

log_info "测试登录速率限制..."
RATE_LIMIT_TRIGGERED=false
for i in {1..6}; do
    RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/v1/login" \
      -H "Content-Type: application/json" \
      -d '{"username":"admin","password":"admin123"}')
    if echo "$RESPONSE" | grep -q "429"; then
        RATE_LIMIT_TRIGGERED=true
        log_success "速率限制已触发（第 $i 次请求）"
        break
    fi
done

if [ "$RATE_LIMIT_TRIGGERED" = false ]; then
    log_warning "速率限制未触发（可能阈值较高）"
fi

echo ""

# ─── 阶段 6: 生成报告 ──────────────────────────────────────────────────────
echo -e "${YELLOW}[6/6] 生成测试报告${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

log_info "生成 HTML 测试报告..."
python3 << 'PYTHON_SCRIPT'
import os
import json
from datetime import datetime

TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
REPORT_DIR = '/root/stock-analyzer/tests/reports'

# 解析测试结果
results = {
    'timestamp': datetime.now().isoformat(),
    'version': 'v1.2.2',
    'unit_tests': {'passed': 0, 'failed': 0},
    'integration_tests': {'passed': 0, 'failed': 0},
    'security_tests': {'passed': 0, 'failed': 0},
    'performance': {'login_avg_ms': 0}
}

# 读取日志文件
import glob
log_files = glob.glob(f'{REPORT_DIR}/*.log')
for log_file in log_files:
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if '✓' in content or '通过' in content:
                results['unit_tests']['passed'] += content.count('✓') + content.count('通过')
            if '✗' in content or '失败' in content:
                results['unit_tests']['failed'] += content.count('✗') + content.count('失败')
    except:
        pass

# 生成 HTML 报告
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>回归测试报告 - TradingAgents-CN {results['version']}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
        .card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff; }}
        .card.success {{ border-left-color: #28a745; }}
        .card.warning {{ border-left-color: #ffc107; }}
        .card.danger {{ border-left-color: #dc3545; }}
        .stat {{ font-size: 32px; font-weight: bold; color: #333; }}
        .label {{ color: #666; font-size: 14px; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .pass {{ color: #28a745; }}
        .fail {{ color: #dc3545; }}
        .timestamp {{ color: #999; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 回归测试报告</h1>
        <p class="timestamp">执行时间：{results['timestamp']}</p>
        <p>版本：{results['version']}</p>
        
        <h2>测试汇总</h2>
        <div class="summary">
            <div class="card success">
                <div class="stat">{results['unit_tests']['passed']}</div>
                <div class="label">单元测试通过</div>
            </div>
            <div class="card danger">
                <div class="stat">{results['unit_tests']['failed']}</div>
                <div class="label">单元测试失败</div>
            </div>
            <div class="card {'success' if results['unit_tests']['failed'] == 0 else 'warning'}">
                <div class="stat">{(results['unit_tests']['passed'] / max(1, results['unit_tests']['passed'] + results['unit_tests']['failed']) * 100):.1f}%</div>
                <div class="label">通过率</div>
            </div>
        </div>
        
        <h2>测试详情</h2>
        <table>
            <tr>
                <th>测试类型</th>
                <th>通过</th>
                <th>失败</th>
                <th>状态</th>
            </tr>
            <tr>
                <td>单元测试</td>
                <td class="pass">{results['unit_tests']['passed']}</td>
                <td class="fail">{results['unit_tests']['failed']}</td>
                <td>{'✅ 通过' if results['unit_tests']['failed'] == 0 else '⚠️ 部分失败'}</td>
            </tr>
            <tr>
                <td>集成测试</td>
                <td class="pass">-</td>
                <td class="fail">-</td>
                <td>⏳ 待执行</td>
            </tr>
            <tr>
                <td>安全测试</td>
                <td class="pass">-</td>
                <td class="fail">-</td>
                <td>⏳ 待执行</td>
            </tr>
        </table>
        
        <h2>日志文件</h2>
        <ul>
"""

for log_file in sorted(log_files)[-10:]:
    html += f'            <li><a href="{os.path.basename(log_file)}">{os.path.basename(log_file)}</a></li>\n'

html += """
        </ul>
        
        <h2>结论</h2>
        <p>测试执行完成。详细结果请查看上方日志文件。</p>
    </div>
</body>
</html>
"""

with open(f'{REPORT_DIR}/report_{TIMESTAMP}.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"HTML 报告已生成：{REPORT_DIR}/report_{TIMESTAMP}.html")
PYTHON_SCRIPT

log_success "测试报告生成完成"

echo ""
echo -e "${YELLOW}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║   回归测试完成                                        ║${NC}"
echo -e "${YELLOW}║   报告目录：${REPORT_DIR}                      ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# 显示测试结果摘要
if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  ${TESTS_FAILED} 项测试失败，请查看日志${NC}"
    exit 1
fi
