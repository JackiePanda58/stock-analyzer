#!/bin/bash
#
# 数据恢复脚本
# 从备份文件恢复 Redis、数据库、配置等
#

set -e

# ==================== 配置 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/root/stock-analyzer"
BACKUP_DIR="/root/stock-analyzer/backups"
LOG_DIR="/root/stock-analyzer/logs"
RECOVER_LOG="${LOG_DIR}/recovery.log"

# 服务配置
REDIS_HOST="localhost"
REDIS_PORT="6379"
DB_PATH="${PROJECT_DIR}/data/usage.db"

# ==================== 初始化 ====================
mkdir -p "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${RECOVER_LOG}"
}

confirm() {
    read -p "$1 (y/N): " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

# ==================== 恢复函数 ====================

stop_services() {
    log "[ACTION] 停止相关服务..."
    
    # 停止 API 服务
    pkill -f "api_server" 2>/dev/null || true
    pkill -f "uvicorn" 2>/dev/null || true
    
    # 等待进程停止
    sleep 2
    
    log "[OK] 服务已停止"
}

start_services() {
    log "[ACTION] 启动相关服务..."
    
    cd "${PROJECT_DIR}"
    nohup /root/stock-analyzer/venv/bin/python -m uvicorn api_server:app \
        --host 0.0.0.0 \
        --port 8000 \
        > "${LOG_DIR}/api_stdout.log" 2>&1 &
    
    log "[OK] API 服务已启动 (PID: $!)"
    
    # 等待服务启动
    sleep 5
}

restore_redis() {
    local backup_file="$1"
    
    log "[REDIS] 开始恢复 Redis 数据..."
    
    if [ ! -f "${backup_file}" ]; then
        log "[ERROR] Redis 备份文件不存在：${backup_file}"
        return 1
    fi
    
    # 检查 Redis 是否运行
    if ! redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping 2>/dev/null | grep -q "PONG"; then
        log "[ERROR] Redis 服务未运行"
        return 1
    fi
    
    # 清空当前数据
    log "[WARN] 清空当前 Redis 数据..."
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" FLUSHALL
    
    # 恢复 RDB 文件
    if [[ "${backup_file}" =~ \.rdb$ ]] || [[ "${backup_file}" =~ \.rdb\.gz$ ]]; then
        local temp_rdb="/tmp/restore_dump.rdb"
        
        if [[ "${backup_file}" =~ \.gz$ ]]; then
            gunzip -c "${backup_file}" > "${temp_rdb}"
        else
            cp "${backup_file}" "${temp_rdb}"
        fi
        
        # 复制到 Redis 数据目录
        cp "${temp_rdb}" "/var/lib/redis/dump.rdb"
        
        # 触发 Redis 加载
        redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" BGREWRITEAOF 2>/dev/null || true
        
        log "[OK] Redis 数据恢复完成"
    else
        log "[WARN] 非 RDB 格式备份，跳过 Redis 恢复"
    fi
    
    return 0
}

restore_database() {
    local backup_file="$1"
    
    log "[DATABASE] 开始恢复 SQLite 数据库..."
    
    if [ ! -f "${backup_file}" ]; then
        log "[ERROR] 数据库备份文件不存在：${backup_file}"
        return 1
    fi
    
    # 备份当前数据库（以防万一）
    if [ -f "${DB_PATH}" ]; then
        local backup_current="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "${DB_PATH}" "${backup_current}"
        log "[INFO] 当前数据库已备份：${backup_current}"
    fi
    
    # 恢复数据库
    cp "${backup_file}" "${DB_PATH}"
    
    # 恢复 WAL 和 SHM 文件（如果存在）
    [ -f "${backup_file}-wal" ] && cp "${backup_file}-wal" "${DB_PATH}-wal"
    [ -f "${backup_file}-shm" ] && cp "${backup_file}-shm" "${DB_PATH}-shm"
    
    # 验证恢复
    if sqlite3 "${DB_PATH}" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
        log "[OK] SQLite 数据库恢复完成"
        return 0
    else
        log "[ERROR] 数据库恢复验证失败，回滚..."
        mv "${backup_current}" "${DB_PATH}"
        return 1
    fi
}

restore_config() {
    local backup_file="$1"
    
    log "[CONFIG] 开始恢复配置文件..."
    
    if [ ! -f "${backup_file}" ]; then
        log "[ERROR] 配置文件备份不存在：${backup_file}"
        return 1
    fi
    
    # 备份当前配置
    local config_backup="/tmp/config_backup_$(date +%Y%m%d_%H%M%S).tar"
    tar -cf "${config_backup}" -C "${PROJECT_DIR}" config/ .env 2>/dev/null || true
    log "[INFO] 当前配置已备份：${config_backup}"
    
    # 恢复配置
    tar -xf "${backup_file}" -C "${PROJECT_DIR}" 2>/dev/null || {
        log "[ERROR] 配置恢复失败"
        return 1
    }
    
    log "[OK] 配置文件恢复完成"
    return 0
}

restore_full_backup() {
    local backup_manifest="$1"
    
    if [ ! -f "${backup_manifest}" ]; then
        log "[ERROR] 备份清单不存在：${backup_manifest}"
        return 1
    fi
    
    local backup_dir=$(dirname "${backup_manifest}")
    local backup_base=$(basename "${backup_manifest}" .manifest.json)
    
    log "========================================="
    log "开始完整恢复：${backup_base}"
    log "========================================="
    
    # 显示备份信息
    log "[INFO] 备份信息:"
    cat "${backup_manifest}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))"
    
    if ! confirm "确认要恢复此备份吗？"; then
        log "[ABORT] 用户取消恢复"
        return 1
    fi
    
    # 停止服务
    stop_services
    
    # 恢复各项数据
    local errors=0
    
    # 恢复数据库
    local db_backup="${backup_dir}/${backup_base}.db.gz"
    [ ! -f "${db_backup}" ] && db_backup="${backup_dir}/${backup_base}.db"
    if [ -f "${db_backup}" ]; then
        restore_database "${db_backup}" || errors=$((errors + 1))
    fi
    
    # 恢复配置
    local config_backup="${backup_dir}/${backup_base}.config.tar.gz"
    [ ! -f "${config_backup}" ] && config_backup="${backup_dir}/${backup_base}.config.tar"
    if [ -f "${config_backup}" ]; then
        restore_config "${config_backup}" || errors=$((errors + 1))
    fi
    
    # 恢复 Redis
    local redis_backup="${backup_dir}/${backup_base}.rdb.gz"
    [ ! -f "${redis_backup}" ] && redis_backup="${backup_dir}/${backup_base}.rdb"
    if [ -f "${redis_backup}" ]; then
        restore_redis "${redis_backup}" || errors=$((errors + 1))
    fi
    
    # 重启服务
    start_services
    
    log "========================================="
    if [ "${errors}" -eq 0 ]; then
        log "[SUCCESS] 完整恢复完成"
        return 0
    else
        log "[FAILURE] 恢复完成，但有${errors}项错误"
        return 1
    fi
}

# ==================== 验证备份 ====================

verify_backup() {
    local backup_file="$1"
    
    log "[VERIFY] 验证备份文件：${backup_file}"
    
    if [ ! -f "${backup_file}" ]; then
        log "[ERROR] 文件不存在"
        return 1
    fi
    
    # 检查文件完整性
    if [[ "${backup_file}" =~ \.gz$ ]]; then
        if gzip -t "${backup_file}" 2>/dev/null; then
            log "[OK] 压缩文件完整性检查通过"
        else
            log "[ERROR] 压缩文件损坏"
            return 1
        fi
    fi
    
    # 如果是数据库备份，验证完整性
    if [[ "${backup_file}" =~ \.db$ ]] || [[ "${backup_file}" =~ \.db\.gz$ ]]; then
        local temp_db=$(mktemp)
        
        if [[ "${backup_file}" =~ \.gz$ ]]; then
            gunzip -c "${backup_file}" > "${temp_db}"
        else
            cp "${backup_file}" "${temp_db}"
        fi
        
        if sqlite3 "${temp_db}" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
            log "[OK] 数据库完整性检查通过"
            rm -f "${temp_db}"
            return 0
        else
            log "[ERROR] 数据库完整性检查失败"
            rm -f "${temp_db}"
            return 1
        fi
    fi
    
    log "[OK] 备份文件验证通过"
    return 0
}

# ==================== 主程序 ====================

show_help() {
    echo "数据恢复工具"
    echo ""
    echo "用法：$0 [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  full <备份清单>     - 从备份清单完整恢复"
    echo "  database <备份文件>  - 恢复数据库"
    echo "  config <备份文件>    - 恢复配置"
    echo "  redis <备份文件>     - 恢复 Redis"
    echo "  verify <备份文件>    - 验证备份文件"
    echo "  list                 - 列出可用备份"
    echo ""
    echo "示例:"
    echo "  $0 full /root/stock-analyzer/backups/daily/daily_backup_20260409_120000.manifest.json"
    echo "  $0 database /root/stock-analyzer/backups/daily/daily_backup_20260409_120000.db.gz"
    echo "  $0 verify /root/stock-analyzer/backups/daily/daily_backup_20260409_120000.db.gz"
}

main() {
    local command="${1:-help}"
    
    case "${command}" in
        full)
            restore_full_backup "$2"
            ;;
        database)
            stop_services
            restore_database "$2"
            start_services
            ;;
        config)
            restore_config "$2"
            ;;
        redis)
            restore_redis "$2"
            ;;
        verify)
            verify_backup "$2"
            ;;
        list)
            echo "可用备份:"
            find "${BACKUP_DIR}" -name "*.manifest.json" -exec echo "  {}" \;
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "未知命令：${command}"
            show_help
            exit 1
            ;;
    esac
}

# 如果直接执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
