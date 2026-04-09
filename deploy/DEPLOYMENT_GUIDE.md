# TradingAgents 生产环境部署指南

## 目录结构

```
/root/stock-analyzer/
├── api_server.py              # 主 API 服务器
├── deploy/                    # 部署脚本和配置
│   ├── error_handler.py       # 统一错误处理
│   ├── logging_config.py      # 增强日志配置
│   ├── monitor.sh             # 系统监控脚本
│   ├── health_check.sh        # 健康检查脚本
│   ├── backup.sh              # 备份脚本
│   ├── restore.sh             # 恢复脚本
│   ├── benchmark_test.py      # 性能测试脚本
│   ├── alert_config.json      # 告警配置
│   ├── openapi.yaml           # OpenAPI 规范
│   ├── API_DOCUMENTATION.md   # API 文档
│   ├── PERFORMANCE_BENCHMARK_REPORT.md  # 性能报告
│   ├── crontab.example        # Cron 配置示例
│   ├── tradingagents.service  # Systemd 服务配置
│   └── PRODUCTION_READINESS_PROGRESS.md # 进展跟踪
├── config/                    # 配置文件
├── data/                      # 数据目录
├── logs/                      # 日志目录
├── reports/                   # 分析报告
├── backups/                   # 备份目录 (自动创建)
└── metrics/                   # 监控指标 (自动创建)
```

---

## 快速部署

### 1. 安装依赖

```bash
cd /root/stock-analyzer
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件:

```bash
# API 配置
OPENAI_BASE_URL=https://coding.dashscope.aliyuncs.com/v1
OPENAI_API_KEY=sk-your-api-key

# 数据源配置
TUSHARE_TOKEN=your-tushare-token

# 项目路径
TRADINGAGENTS_RESULTS_DIR=/root/stock-analyzer/reports
```

### 3. 安装 Systemd 服务

```bash
# 复制服务配置
sudo cp /root/stock-analyzer/deploy/tradingagents.service /etc/systemd/system/

# 重载 systemd
sudo systemctl daemon-reload

# 启用并启动服务
sudo systemctl enable tradingagents
sudo systemctl start tradingagents

# 检查状态
sudo systemctl status tradingagents
```

### 4. 配置定时任务

```bash
# 编辑 crontab
crontab -e

# 粘贴 deploy/crontab.example 内容
```

### 5. 验证部署

```bash
# 检查 API 健康
curl http://localhost:8000/api/health

# 检查日志
tail -f /root/stock-analyzer/logs/system.log

# 运行健康检查
/root/stock-analyzer/deploy/health_check.sh check
```

---

## 监控配置

### 系统监控

监控脚本自动采集以下指标:
- CPU 使用率
- 内存使用率
- 磁盘使用率
- 进程数量
- 系统负载
- API 服务状态
- Redis 状态

查看监控日志:
```bash
tail -f /root/stock-analyzer/logs/monitor.log
```

### 告警配置

编辑 `deploy/alert_config.json`:

```json
{
    "notifications": {
        "webhook": {
            "enabled": true,
            "url": "YOUR_WEBHOOK_URL"
        },
        "email": {
            "enabled": true,
            "recipients": ["admin@example.com"]
        }
    }
}
```

### 健康检查

手动运行健康检查:
```bash
/root/stock-analyzer/deploy/health_check.sh check
```

生成健康报告:
```bash
/root/stock-analyzer/deploy/health_check.sh report
```

---

## 备份策略

### 自动备份

- **日备份**: 每天凌晨 2 点，保留 7 天
- **周备份**: 每周日凌晨 3 点，保留 4 周
- **月备份**: 每月 1 日凌晨 4 点，保留 12 个月

### 手动备份

```bash
# 日备份
/root/stock-analyzer/deploy/backup.sh daily

# 周备份
/root/stock-analyzer/deploy/backup.sh weekly

# 月备份
/root/stock-analyzer/deploy/backup.sh monthly

# 列出可用备份
/root/stock-analyzer/deploy/backup.sh list
```

### 数据恢复

```bash
# 验证备份
/root/stock-analyzer/deploy/restore.sh verify /path/to/backup

# 恢复数据库
/root/stock-analyzer/deploy/restore.sh database /path/to/backup.db

# 完整恢复
/root/stock-analyzer/deploy/restore.sh full /path/to/backup.manifest.json
```

---

## 日志管理

### 日志文件

- `logs/system.log` - 主系统日志
- `logs/error.log` - 错误日志
- `logs/performance.log` - 性能日志
- `logs/monitor.log` - 监控日志
- `logs/backup.log` - 备份日志
- `logs/health_check.log` - 健康检查日志

### 日志轮转

自动配置:
- 单个文件最大：10MB
- 保留备份数：7 个
- 自动清理：30 天前的日志

### 查看日志

```bash
# 实时查看
tail -f /root/stock-analyzer/logs/system.log

# 查看错误
tail -f /root/stock-analyzer/logs/error.log

# 搜索日志
grep "ERROR" /root/stock-analyzer/logs/system.log | tail -20
```

---

## 性能优化

### 缓存配置

Redis 缓存已启用，默认配置:
- 分析报告缓存：12 小时
- 用户数据缓存：1 小时

### 并发配置

Systemd 服务配置:
- 工作进程数：2
- 连接超时：300 秒
- 文件描述符限制：65535

### 数据库优化

定期执行:
```bash
# 数据库完整性检查
sqlite3 /root/stock-analyzer/data/usage.db "PRAGMA integrity_check;"

# 数据库优化
sqlite3 /root/stock-analyzer/data/usage.db "VACUUM;"
```

---

## 故障排查

### API 无法启动

```bash
# 检查服务状态
sudo systemctl status tradingagents

# 查看日志
sudo journalctl -u tradingagents -n 50

# 手动启动测试
cd /root/stock-analyzer
source venv/bin/activate
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

### Redis 连接失败

```bash
# 检查 Redis 状态
sudo systemctl status redis

# 测试连接
redis-cli ping

# 重启 Redis
sudo systemctl restart redis
```

### 数据库损坏

```bash
# 检查完整性
sqlite3 /root/stock-analyzer/data/usage.db "PRAGMA integrity_check;"

# 从备份恢复
/root/stock-analyzer/deploy/restore.sh database /path/to/backup.db
```

### 磁盘空间不足

```bash
# 检查磁盘使用
df -h

# 清理旧日志
find /root/stock-analyzer/logs -name "*.log" -mtime +30 -delete

# 清理旧备份
/root/stock-analyzer/deploy/backup.sh cleanup 7
```

---

## 安全建议

### 1. 修改默认密码

```bash
# 编辑 api_server.py，修改默认凭证
# 搜索：admin123
```

### 2. 配置防火墙

```bash
# 仅开放必要端口
sudo ufw allow 8000/tcp
sudo ufw enable
```

### 3. 启用 HTTPS

使用 Nginx 反向代理:

```nginx
server {
    listen 443 ssl;
    server_name api.stockanalyzer.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. 定期更新

```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y

# 更新 Python 依赖
cd /root/stock-analyzer
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

---

## 联系支持

- 技术问题：support@stockanalyzer.com
- 文档更新：2026-04-09
