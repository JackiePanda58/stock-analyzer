#!/bin/bash
#
# 系统监控脚本
# 监控 CPU、内存、磁盘、网络等系统资源
# 支持告警通知（邮件、Webhook）
#

set -e

# ==================== 配置 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/root/stock-analyzer/logs"
METRICS_DIR="/root/stock-analyzer/metrics"
ALERT_CONFIG="${SCRIPT_DIR}/alert_config.json"

# 告警阈值
CPU_THRESHOLD=80
MEMORY_THRESHOLD=85
DISK_THRESHOLD=90
PROCESS_COUNT_THRESHOLD=500

# 告警通知配置
ENABLE_EMAIL_ALERT=false
ENABLE_WEBHOOK_ALERT=true
WEBHOOK_URL="http://localhost:8080/alerts"  # 替换为实际告警接收地址
ALERT_EMAIL="admin@example.com"

# 日志文件
MONITOR_LOG="${LOG_DIR}/monitor.log"
METRICS_FILE="${METRICS_DIR}/system_metrics.jsonl"

# ==================== 初始化 ====================
mkdir -p "${LOG_DIR}" "${METRICS_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${MONITOR_LOG}"
}

# ==================== 指标采集 ====================

get_cpu_usage() {
    # 获取 CPU 使用率
    top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
}

get_memory_usage() {
    # 获取内存使用率
    free | grep Mem | awk '{printf("%.1f", $3/$2 * 100.0)}'
}

get_disk_usage() {
    # 获取根分区使用率
    df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1
}

get_process_count() {
    # 获取进程数量
    ps aux | wc -l
}

get_load_average() {
    # 获取系统负载
    cat /proc/loadavg | awk '{print $1, $2, $3}'
}

get_network_stats() {
    # 获取网络统计（简化版）
    cat /proc/net/dev | grep -E "eth0|ens|enp" | head -1 | awk '{print $2, $10}'
}

get_api_server_status() {
    # 检查 API 服务器状态
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health | grep -q "200"; then
        echo "running"
    else
        echo "down"
    fi
}

get_redis_status() {
    # 检查 Redis 状态
    if redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo "running"
    else
        echo "down"
    fi
}

# ==================== 告警发送 ====================

send_alert() {
    local level="$1"
    local metric="$2"
    local value="$3"
    local threshold="$4"
    local message="$5"
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local alert_data=$(cat <<EOF
{
    "timestamp": "${timestamp}",
    "level": "${level}",
    "metric": "${metric}",
    "value": ${value},
    "threshold": ${threshold},
    "message": "${message}",
    "host": "$(hostname)"
}
EOF
)
    
    log "[ALERT] ${level}: ${message}"
    
    # 写入告警日志
    echo "${alert_data}" >> "${METRICS_DIR}/alerts.jsonl"
    
    # Webhook 通知
    if [ "${ENABLE_WEBHOOK_ALERT}" = "true" ]; then
        curl -s -X POST "${WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "${alert_data}" \
            || log "[WARN] Webhook 发送失败"
    fi
    
    # 邮件通知
    if [ "${ENABLE_EMAIL_ALERT}" = "true" ]; then
        echo "${message}" | mail -s "[StockAnalyzer 告警] ${level}: ${metric}" "${ALERT_EMAIL}" \
            || log "[WARN] 邮件发送失败"
    fi
}

check_threshold() {
    local metric="$1"
    local value="$2"
    local threshold="$3"
    local level="$4"
    
    # 使用 bc 进行浮点数比较
    if (( $(echo "${value} > ${threshold}" | bc -l) )); then
        send_alert "${level}" "${metric}" "${value}" "${threshold}" \
            "${metric} 使用率过高：${value}% (阈值：${threshold}%)"
        return 1
    fi
    return 0
}

# ==================== 监控主循环 ====================

collect_metrics() {
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # 采集指标
    local cpu_usage=$(get_cpu_usage)
    local memory_usage=$(get_memory_usage)
    local disk_usage=$(get_disk_usage)
    local process_count=$(get_process_count)
    local load_avg=$(get_load_average)
    local api_status=$(get_api_server_status)
    local redis_status=$(get_redis_status)
    
    # 记录指标
    local metrics_json=$(cat <<EOF
{"timestamp":"${timestamp}","cpu":${cpu_usage},"memory":${memory_usage},"disk":${disk_usage},"processes":${process_count},"load_avg":"${load_avg}","api_server":"${api_status}","redis":"${redis_status}"}
EOF
)
    
    echo "${metrics_json}" >> "${METRICS_FILE}"
    
    log "[METRICS] CPU: ${cpu_usage}% | MEM: ${memory_usage}% | DISK: ${disk_usage}% | PROC: ${process_count} | LOAD: ${load_avg}"
    
    # 检查阈值并发送告警
    check_threshold "CPU" "${cpu_usage}" "${CPU_THRESHOLD}" "WARNING"
    check_threshold "MEMORY" "${memory_usage}" "${MEMORY_THRESHOLD}" "WARNING"
    check_threshold "DISK" "${disk_usage}" "${DISK_THRESHOLD}" "CRITICAL"
    check_threshold "PROCESS_COUNT" "${process_count}" "${PROCESS_COUNT_THRESHOLD}" "WARNING"
    
    # 服务状态检查
    if [ "${api_status}" = "down" ]; then
        send_alert "CRITICAL" "API_SERVER" "0" "1" "API 服务器已停止运行"
    fi
    
    if [ "${redis_status}" = "down" ]; then
        send_alert "CRITICAL" "REDIS" "0" "1" "Redis 服务已停止运行"
    fi
}

# ==================== 历史数据统计 ====================

generate_daily_report() {
    local date="${1:-$(date +%Y-%m-%d)}"
    local report_file="${METRICS_DIR}/daily_report_${date}.json"
    
    log "[REPORT] 生成日报：${date}"
    
    # 从指标文件中提取当天的数据
    grep "${date}" "${METRICS_FILE}" | python3 << 'PYTHON'
import sys
import json
from datetime import datetime

metrics = []
for line in sys.stdin:
    try:
        metrics.append(json.loads(line.strip()))
    except:
        pass

if not metrics:
    print(json.dumps({"error": "No data found"}))
    sys.exit(0)

# 计算统计
cpu_values = [m.get('cpu', 0) for m in metrics]
mem_values = [m.get('memory', 0) for m in metrics]
disk_values = [m.get('disk', 0) for m in metrics]

report = {
    "date": metrics[0].get('timestamp', '')[:10],
    "data_points": len(metrics),
    "cpu": {
        "avg": sum(cpu_values) / len(cpu_values),
        "max": max(cpu_values),
        "min": min(cpu_values)
    },
    "memory": {
        "avg": sum(mem_values) / len(mem_values),
        "max": max(mem_values),
        "min": min(mem_values)
    },
    "disk": {
        "avg": sum(disk_values) / len(disk_values),
        "max": max(disk_values),
        "min": min(disk_values)
    },
    "alerts": len([m for m in metrics if m.get('alert')])
}

print(json.dumps(report, indent=2))
PYTHON
}

# ==================== 清理旧数据 ====================

cleanup_old_data() {
    local days="${1:-7}"
    
    log "[CLEANUP] 清理${days}天前的数据"
    
    # 清理旧指标文件
    find "${METRICS_DIR}" -name "*.jsonl" -mtime +${days} -delete 2>/dev/null || true
    
    # 清理旧日志
    find "${LOG_DIR}" -name "*.log" -mtime +${days} -delete 2>/dev/null || true
}

# ==================== 主程序 ====================

main() {
    local interval="${1:-60}"  # 默认 60 秒
    local action="${2:-monitor}"
    
    log "========================================="
    log "系统监控脚本启动"
    log "监控间隔：${interval}秒"
    log "动作：${action}"
    log "========================================="
    
    case "${action}" in
        monitor)
            # 持续监控
            while true; do
                collect_metrics
                sleep "${interval}"
            done
            ;;
        once)
            # 单次采集
            collect_metrics
            ;;
        report)
            # 生成报告
            generate_daily_report "$3"
            ;;
        cleanup)
            # 清理旧数据
            cleanup_old_data "$3"
            ;;
        *)
            echo "用法：$0 [间隔秒数] [动作]"
            echo "动作：monitor (持续监控), once (单次), report (报告), cleanup (清理)"
            exit 1
            ;;
    esac
}

# 如果直接执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
