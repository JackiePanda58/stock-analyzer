#!/bin/bash
#
# 数据备份脚本
# 备份 Redis 数据、SQLite 数据库、配置文件等
# 支持增量备份和压缩
#

set -e

# ==================== 配置 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/root/stock-analyzer"
BACKUP_DIR="/root/stock-analyzer/backups"
LOG_DIR="/root/stock-analyzer/logs"
BACKUP_LOG="${LOG_DIR}/backup.log"

# 备份内容
REDIS_HOST="localhost"
REDIS_PORT="6379"
REDIS_DB=0
DB_PATH="${PROJECT_DIR}/data/usage.db"
CONFIG_DIR="${PROJECT_DIR}/config"
ENV_FILE="${PROJECT_DIR}/.env"

# 备份保留策略
DAILY_RETENTION=7      # 保留 7 天的日备份
WEEKLY_RETENTION=4     # 保留 4 周的周备份
MONTHLY_RETENTION=12   # 保留 12 个月的月备份

# 压缩配置
COMPRESSION="gzip"
COMPRESSION_LEVEL=6

# ==================== 初始化 ====================
mkdir -p "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly" "${BACKUP_DIR}/monthly" "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${BACKUP_LOG}"
}

# ==================== 备份函数 ====================

backup_redis() {
    local backup_file="$1"
    log "[REDIS] 开始备份 Redis 数据..."
    
    # 检查 Redis 是否运行
    if ! redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping 2>/dev/null | grep -q "PONG"; then
        log "[ERROR] Redis 服务未运行，跳过备份"
        return 1
    fi
    
    # 使用 RDB 快照备份
    local rdb_file="/tmp/dump_${$}.rdb"
    
    # 触发 BGSAVE
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" BGSAVE 2>/dev/null || true
    
    # 等待保存完成（最多 30 秒）
    local wait_count=0
    while [ ! -f "/var/lib/redis/dump.rdb" ] && [ ${wait_count} -lt 30 ]; do
        sleep 1
        wait_count=$((wait_count + 1))
    done
    
    # 备份 RDB 文件（如果存在）
    if [ -f "/var/lib/redis/dump.rdb" ]; then
        cp "/var/lib/redis/dump.rdb" "${backup_file}.rdb"
        log "[OK] Redis RDB 备份完成：${backup_file}.rdb"
    else
        # 降级为 AOF 或导出所有键
        log "[WARN] 未找到 RDB 文件，尝试导出所有键..."
        redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" --rdb "${backup_file}.rdb" 2>/dev/null || {
            log "[WARN] Redis 备份降级为文本导出"
            redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" KEYS "*" | while read key; do
                redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" GET "${key}" >> "${backup_file}.txt" 2>/dev/null || true
            done
        }
    fi
    
    return 0
}

backup_database() {
    local backup_file="$1"
    log "[DATABASE] 开始备份 SQLite 数据库..."
    
    if [ ! -f "${DB_PATH}" ]; then
        log "[INFO] 数据库文件不存在，跳过备份"
        return 0
    fi
    
    # 使用 WAL 模式确保一致性
    sqlite3 "${DB_PATH}" "PRAGMA wal_checkpoint(TRUNCATE);" 2>/dev/null || true
    
    # 复制数据库文件
    cp "${DB_PATH}" "${backup_file}.db"
    
    # 同时备份 WAL 和 SHM 文件（如果存在）
    [ -f "${DB_PATH}-wal" ] && cp "${DB_PATH}-wal" "${backup_file}.db-wal"
    [ -f "${DB_PATH}-shm" ] && cp "${DB_PATH}-shm" "${backup_file}.db-shm"
    
    # 验证备份
    if sqlite3 "${backup_file}.db" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
        log "[OK] SQLite 数据库备份完成：${backup_file}.db"
        return 0
    else
        log "[ERROR] 数据库备份验证失败"
        return 1
    fi
}

backup_config() {
    local backup_file="$1"
    log "[CONFIG] 开始备份配置文件..."
    
    local config_tar="${backup_file}.config.tar"
    
    # 打包配置目录
    tar -cf "${config_tar}" -C "${PROJECT_DIR}" \
        config/ \
        .env \
        requirements.txt \
        deploy/ 2>/dev/null || {
        log "[WARN] 部分配置文件不存在"
    }
    
    if [ -f "${config_tar}" ]; then
        log "[OK] 配置文件备份完成：${config_tar}"
        return 0
    else
        log "[ERROR] 配置文件备份失败"
        return 1
    fi
}

backup_reports() {
    local backup_file="$1"
    log "[REPORTS] 开始备份分析报告..."
    
    local reports_dir="${PROJECT_DIR}/reports"
    
    if [ ! -d "${reports_dir}" ]; then
        log "[INFO] 报告目录不存在，跳过备份"
        return 0
    fi
    
    # 打包最近的报告（最近 7 天）
    find "${reports_dir}" -name "*.md" -mtime -7 -print0 2>/dev/null | \
        tar --null -cf "${backup_file}.reports.tar" --files-from=- 2>/dev/null || {
        log "[WARN] 无近期报告或打包失败"
        return 0
    }
    
    log "[OK] 分析报告备份完成：${backup_file}.reports.tar"
    return 0
}

compress_backup() {
    local backup_file="$1"
    log "[COMPRESS] 压缩备份文件..."
    
    # 压缩所有备份文件
    for file in "${backup_file}".*; do
        if [ -f "${file}" ] && [[ ! "${file}" =~ \.(gz|zip)$ ]]; then
            gzip -${COMPRESSION_LEVEL} "${file}" &
        fi
    done
    
    wait
    log "[OK] 备份文件压缩完成"
}

create_manifest() {
    local backup_file="$1"
    local manifest_file="${backup_file}.manifest.json"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    cat > "${manifest_file}" << EOF
{
    "backup_id": "$(basename ${backup_file})",
    "timestamp": "${timestamp}",
    "hostname": "$(hostname)",
    "files": [
$(ls -la "${backup_file}".* 2>/dev/null | awk '{print "        {\"name\": \"" $9 "\", \"size\": " $5 "},"}' | sed '$ s/,$//')
    ],
    "checksums": {
$(for file in "${backup_file}".*; do
    if [ -f "${file}" ]; then
        echo "        \"$(basename ${file})\": \"$(md5sum "${file}" | cut -d' ' -f1)\","
    fi
done | sed '$ s/,$//')
    }
}
EOF
    
    log "[OK] 备份清单已生成：${manifest_file}"
}

# ==================== 备份策略 ====================

run_daily_backup() {
    local date_str=$(date +%Y%m%d)
    local backup_name="daily_backup_${date_str}_$(date +%H%M%S)"
    local backup_path="${BACKUP_DIR}/daily/${backup_name}"
    
    log "========================================="
    log "开始日备份：${backup_name}"
    log "========================================="
    
    backup_redis "${backup_path}" || true
    backup_database "${backup_path}" || true
    backup_config "${backup_path}" || true
    backup_reports "${backup_path}" || true
    compress_backup "${backup_path}"
    create_manifest "${backup_path}"
    
    log "[SUCCESS] 日备份完成"
    
    # 清理旧备份
    cleanup_old_backups "daily" "${DAILY_RETENTION}"
}

run_weekly_backup() {
    local date_str=$(date +%Y%m%d)
    local backup_name="weekly_backup_${date_str}_$(date +%H%M%S)"
    local backup_path="${BACKUP_DIR}/weekly/${backup_name}"
    
    log "========================================="
    log "开始周备份：${backup_name}"
    log "========================================="
    
    # 周备份包含完整数据
    backup_redis "${backup_path}"
    backup_database "${backup_path}"
    backup_config "${backup_path}"
    backup_reports "${backup_path}"
    compress_backup "${backup_path}"
    create_manifest "${backup_path}"
    
    log "[SUCCESS] 周备份完成"
    
    cleanup_old_backups "weekly" "${WEEKLY_RETENTION}"
}

run_monthly_backup() {
    local date_str=$(date +%Y%m%d)
    local backup_name="monthly_backup_${date_str}_$(date +%H%M%S)"
    local backup_path="${BACKUP_DIR}/monthly/${backup_name}"
    
    log "========================================="
    log "开始月备份：${backup_name}"
    log "========================================="
    
    # 月备份包含完整数据 + 日志
    backup_redis "${backup_path}"
    backup_database "${backup_path}"
    backup_config "${backup_path}"
    backup_reports "${backup_path}"
    
    # 额外备份日志
    tar -czf "${backup_path}.logs.tar.gz" -C "${PROJECT_DIR}" logs/ 2>/dev/null || true
    
    compress_backup "${backup_path}"
    create_manifest "${backup_path}"
    
    log "[SUCCESS] 月备份完成"
    
    cleanup_old_backups "monthly" "${MONTHLY_RETENTION}"
}

# ==================== 清理旧备份 ====================

cleanup_old_backups() {
    local backup_type="$1"
    local retention="$2"
    local backup_dir="${BACKUP_DIR}/${backup_type}"
    
    log "[CLEANUP] 清理${backup_type}备份，保留最近${retention}个"
    
    # 删除旧备份
    find "${backup_dir}" -type f -name "*.manifest.json" -mtime +${retention} | while read manifest; do
        local base_name=$(basename "${manifest}" .manifest.json)
        log "[DELETE] 删除旧备份：${base_name}"
        rm -f "${backup_dir}/${base_name}".*
    done
}

# ==================== 恢复功能 ====================

list_backups() {
    log "[INFO] 可用备份列表:"
    echo ""
    echo "日备份:"
    ls -lh "${BACKUP_DIR}/daily/"*.manifest.json 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || echo "  无"
    echo ""
    echo "周备份:"
    ls -lh "${BACKUP_DIR}/weekly/"*.manifest.json 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || echo "  无"
    echo ""
    echo "月备份:"
    ls -lh "${BACKUP_DIR}/monthly/"*.manifest.json 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || echo "  无"
}

restore_backup() {
    local backup_file="$1"
    
    if [ ! -f "${backup_file}" ]; then
        log "[ERROR] 备份文件不存在：${backup_file}"
        return 1
    fi
    
    log "[RESTORE] 开始恢复备份：${backup_file}"
    
    # 解压备份
    local temp_dir=$(mktemp -d)
    tar -xzf "${backup_file}" -C "${temp_dir}" 2>/dev/null || {
        # 如果不是压缩包，直接复制
        cp "${backup_file}"* "${temp_dir}/" 2>/dev/null || true
    }
    
    # 恢复数据库
    if [ -f "${temp_dir}"/*.db ]; then
        log "[RESTORE] 恢复数据库..."
        cp "${temp_dir}"/*.db "${DB_PATH}"
        [ -f "${temp_dir}"/*.db-wal ] && cp "${temp_dir}"/*.db-wal "${DB_PATH}-wal"
        [ -f "${temp_dir}"/*.db-shm ] && cp "${temp_dir}"/*.db-shm "${DB_PATH}-shm"
    fi
    
    # 恢复配置
    if [ -f "${temp_dir}"/*.config.tar ]; then
        log "[RESTORE] 恢复配置文件..."
        tar -xf "${temp_dir}"/*.config.tar -C "${PROJECT_DIR}" 2>/dev/null || true
    fi
    
    # 清理临时目录
    rm -rf "${temp_dir}"
    
    log "[SUCCESS] 备份恢复完成"
}

# ==================== 主程序 ====================

main() {
    local action="${1:-daily}"
    
    case "${action}" in
        daily)
            run_daily_backup
            ;;
        weekly)
            run_weekly_backup
            ;;
        monthly)
            run_monthly_backup
            ;;
        all)
            run_daily_backup
            run_weekly_backup
            run_monthly_backup
            ;;
        list)
            list_backups
            ;;
        restore)
            restore_backup "$2"
            ;;
        *)
            echo "用法：$0 [动作] [参数]"
            echo "动作:"
            echo "  daily   - 执行日备份"
            echo "  weekly  - 执行周备份"
            echo "  monthly - 执行月备份"
            echo "  all     - 执行所有备份"
            echo "  list    - 列出可用备份"
            echo "  restore - 恢复备份 (需要提供备份文件路径)"
            exit 1
            ;;
    esac
}

# 如果直接执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
