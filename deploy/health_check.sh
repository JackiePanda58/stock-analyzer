#!/bin/bash
#
# 服务健康检查脚本
# 检查 API、Redis、数据库等关键服务的健康状态
# 支持 systemd 服务管理和自动重启
#

set -e

# ==================== 配置 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/root/stock-analyzer/logs"
HEALTH_LOG="${LOG_DIR}/health_check.log"

# 服务配置
API_URL="http://localhost:8000"
API_HEALTH_ENDPOINT="/api/health"
REDIS_HOST="localhost"
REDIS_PORT="6379"
DB_PATH="/root/stock-analyzer/data/usage.db"

# 自动重启配置
AUTO_RESTART=true
MAX_RESTART_COUNT=3
RESTART_COOLDOWN=300  # 5 分钟

# ==================== 初始化 ====================
mkdir -p "${LOG_DIR}"

# 重启计数文件
RESTART_COUNT_FILE="/tmp/api_restart_count"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${HEALTH_LOG}"
}

# ==================== 健康检查函数 ====================

check_api_health() {
    log "[CHECK] 检查 API 服务健康状态..."
    
    local response=$(curl -s -w "\n%{http_code}" "${API_URL}${API_HEALTH_ENDPOINT}" 2>/dev/null)
    local http_code=$(echo "${response}" | tail -n1)
    local body=$(echo "${response}" | head -n -1)
    
    if [ "${http_code}" = "200" ]; then
        local status=$(echo "${body}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
        if [ "${status}" = "ok" ]; then
            log "[OK] API 服务健康"
            return 0
        else
            log "[WARN] API 服务响应异常：${status}"
            return 1
        fi
    else
        log "[ERROR] API 服务不可用 (HTTP ${http_code})"
        return 1
    fi
}

check_redis_health() {
    log "[CHECK] 检查 Redis 服务健康状态..."
    
    if redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping 2>/dev/null | grep -q "PONG"; then
        log "[OK] Redis 服务健康"
        return 0
    else
        log "[ERROR] Redis 服务不可用"
        return 1
    fi
}

check_database_health() {
    log "[CHECK] 检查 SQLite 数据库健康状态..."
    
    if [ -f "${DB_PATH}" ]; then
        # 检查数据库完整性
        if sqlite3 "${DB_PATH}" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
            log "[OK] SQLite 数据库健康"
            return 0
        else
            log "[WARN] SQLite 数据库完整性检查失败"
            return 1
        fi
    else
        log "[INFO] SQLite 数据库文件不存在（可能未初始化）"
        return 0  # 不视为错误
    fi
}

check_disk_space() {
    log "[CHECK] 检查磁盘空间..."
    
    local usage=$(df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    
    if [ "${usage}" -lt 90 ]; then
        log "[OK] 磁盘空间充足 (使用率：${usage}%)"
        return 0
    else
        log "[ERROR] 磁盘空间不足 (使用率：${usage}%)"
        return 1
    fi
}

check_process_running() {
    log "[CHECK] 检查 API 进程状态..."
    
    if pgrep -f "uvicorn.*api_server" > /dev/null 2>&1 || \
       pgrep -f "python.*api_server" > /dev/null 2>&1; then
        local pid=$(pgrep -f "api_server" | head -1)
        log "[OK] API 进程运行中 (PID: ${pid})"
        return 0
    else
        log "[ERROR] API 进程未运行"
        return 1
    fi
}

# ==================== 服务管理 ====================

restart_api_service() {
    log "[ACTION] 重启 API 服务..."
    
    # 检查重启次数
    local count=0
    if [ -f "${RESTART_COUNT_FILE}" ]; then
        count=$(cat "${RESTART_COUNT_FILE}")
        local last_restart=$(stat -c %Y "${RESTART_COUNT_FILE}" 2>/dev/null || echo 0)
        local now=$(date +%s)
        
        if [ $((now - last_restart)) -gt "${RESTART_COOLDOWN}" ]; then
            count=0  # 冷却期过后重置计数
        fi
    fi
    
    if [ "${count}" -ge "${MAX_RESTART_COUNT}" ]; then
        log "[ERROR] 达到最大重启次数 (${MAX_RESTART_COUNT})，停止自动重启"
        return 1
    fi
    
    # 增加重启计数
    count=$((count + 1))
    echo "${count}" > "${RESTART_COUNT_FILE}"
    
    log "[ACTION] 重启次数：${count}/${MAX_RESTART_COUNT}"
    
    # 停止现有进程
    pkill -f "api_server" 2>/dev/null || true
    sleep 2
    
    # 启动新进程
    cd /root/stock-analyzer
    nohup /root/stock-analyzer/venv/bin/python -m uvicorn api_server:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        > "${LOG_DIR}/api_stdout.log" 2>&1 &
    
    local new_pid=$!
    log "[OK] API 服务已重启 (PID: ${new_pid})"
    
    # 等待服务启动
    sleep 5
    return 0
}

reset_restart_count() {
    if [ -f "${RESTART_COUNT_FILE}" ]; then
        rm -f "${RESTART_COUNT_FILE}"
        log "[INFO] 重启计数已重置"
    fi
}

# ==================== 综合健康检查 ====================

run_health_check() {
    local failed=0
    
    log "========================================="
    log "开始健康检查"
    log "========================================="
    
    # 执行所有检查
    check_process_running || failed=$((failed + 1))
    check_api_health || failed=$((failed + 1))
    check_redis_health || failed=$((failed + 1))
    check_database_health || failed=$((failed + 1))
    check_disk_space || failed=$((failed + 1))
    
    log "========================================="
    if [ "${failed}" -eq 0 ]; then
        log "[SUCCESS] 所有健康检查通过"
        reset_restart_count
        return 0
    else
        log "[FAILURE] ${failed} 项健康检查失败"
        
        # 自动重启
        if [ "${AUTO_RESTART}" = "true" ]; then
            if ! check_process_running || ! check_api_health; then
                restart_api_service
            fi
        fi
        
        return 1
    fi
}

# ==================== 生成健康报告 ====================

generate_health_report() {
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local report_file="${LOG_DIR}/health_report_$(date +%Y%m%d_%H%M%S).json"
    
    # 采集各项指标
    local api_status="unknown"
    local redis_status="unknown"
    local db_status="unknown"
    local disk_usage=$(df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1)
    local memory_usage=$(free | grep Mem | awk '{printf("%.1f", $3/$2 * 100.0)}')
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    
    # 检查各服务状态
    check_api_health > /dev/null 2>&1 && api_status="healthy" || api_status="unhealthy"
    check_redis_health > /dev/null 2>&1 && redis_status="healthy" || redis_status="unhealthy"
    check_database_health > /dev/null 2>&1 && db_status="healthy" || db_status="unknown"
    
    # 生成报告
    cat > "${report_file}" << EOF
{
    "timestamp": "${timestamp}",
    "overall_status": "$([ "${api_status}" = "healthy" ] && [ "${redis_status}" = "healthy" ] && echo "healthy" || echo "degraded")",
    "services": {
        "api": {
            "status": "${api_status}",
            "endpoint": "${API_URL}${API_HEALTH_ENDPOINT}"
        },
        "redis": {
            "status": "${redis_status}",
            "host": "${REDIS_HOST}",
            "port": ${REDIS_PORT}
        },
        "database": {
            "status": "${db_status}",
            "path": "${DB_PATH}"
        }
    },
    "system": {
        "cpu_usage": ${cpu_usage},
        "memory_usage": ${memory_usage},
        "disk_usage": ${disk_usage}
    },
    "host": "$(hostname)",
    "uptime": $(uptime -p 2>/dev/null || echo "unknown")
}
EOF
    
    log "[REPORT] 健康报告已生成：${report_file}"
    cat "${report_file}"
}

# ==================== 主程序 ====================

main() {
    local action="${1:-check}"
    
    case "${action}" in
        check)
            run_health_check
            ;;
        report)
            generate_health_report
            ;;
        restart)
            restart_api_service
            ;;
        reset)
            reset_restart_count
            ;;
        *)
            echo "用法：$0 [动作]"
            echo "动作：check (健康检查), report (生成报告), restart (重启服务), reset (重置计数)"
            exit 1
            ;;
    esac
}

# 如果直接执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
