# User Guide

## TradingAgents-CN 多智能体股票分析系统 · 使用手册

> 本手册面向终端用户，帮助您快速上手安装、启动服务、提交分析和管理系统。

> **文档状态**：2026-04-12 更新 — Agentic Loop 自主修复 + Decimal.js 金融精度保护

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速安装](#2-快速安装)
3. [启动服务](#3-启动服务)
4. [Web UI 使用指南](#4-web-ui-使用指南)
5. [REST API 调用](#5-rest-api-调用)
6. [自动巡航](#6-自动巡航)
7. [常见问题](#7-常见问题)

---

## 1. 环境要求

### 必需环境

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.10 | 建议 3.11+ |
| Node.js | ≥ 18 | 前端构建需要 |
| Redis | ≥ 6.0 | 缓存服务，必须运行 |
| 网络 | 可访问 BaoStock/MiniMax | 防火墙放行 8080/62879/8030 |

### 必需配置

| 配置 | 说明 |
|------|------|
| `MINIMAX_API_KEY` | MiniMax API 密钥 |
| `.env` 文件 | 项目根目录，所有配置统一从此文件读取 |

---

## 2. 快速安装

### 2.1 项目目录

```bash
cd /root/stock-analyzer
```

### 2.2 安装 Python 依赖

```bash
pip install -r requirements.txt
```

主要依赖：

| 依赖 | 用途 |
|------|------|
| `fastapi` + `uvicorn` | REST API 服务 |
| `pyjwt` | JWT 认证 |
| `redis` | 缓存 |
| **`baostock`** | A 股 OHLCV 及财务报表数据（主力数据源） |
| `akshare` | 金融数据（辅助：新闻/财务指标） |
| `langgraph` / `langchain` | 多智能体框架 |
| `openai` | MiniMax API 适配 |
| `rank_bm25` | LangGraph 文档检索 |

### 2.3 安装 Node 前端依赖

```bash
cd frontend
npm install
cd ..
```

### 2.4 配置环境变量

在 `/root/stock-analyzer/.env` 中填写您的密钥：

```bash
# MiniMax API
MINIMAX_API_KEY=您的密钥
MINIMAX_BASE_URL=https://api.minimaxi.com/v1

# Redis（默认无需修改）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### 2.5 安装 BaoStock

```bash
pip3 install baostock --break-system-packages
```

### 2.6 启动 Redis

```bash
redis-server --daemonize yes
# 验证
redis-cli ping
# 应返回：PONG
```

---

## 3. 启动服务

系统有三套服务可以同时运行。

### 3.1 API 服务（必须）

```bash
cd /root/stock-analyzer
PYTHONPATH=/root/stock-analyzer PYTHONGC=MANUAL nohup python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8080 > logs/api.log 2>&1 &
```

API 文档地址：`http://您的服务器IP:8080/docs`

### 3.2 WebSocket 服务（可选）

```bash
cd /root/stock-analyzer
PYTHONPATH=/root/stock-analyzer nohup python3 ws_server.py > logs/ws.log 2>&1 &
```

### 3.3 Vue3 前端（推荐）

```bash
cd /root/stock-analyzer/frontend
NODE_OPTIONS="--max-old-space-size=512" npx vite --host 0.0.0.0 --port 62879
```

前端地址：`http://您的服务器IP:62879`

### 3.4 Watchdog 守护进程（推荐）

```bash
cd /root/stock-analyzer
nohup ./watchdog.sh > /tmp/watchdog.log 2>&1 &
```

自动检查 API (8080) 和 Frontend (62879) 健康状态，崩溃自动重启。

### 3.5 验证服务状态

```bash
# 检查 API
curl http://127.0.0.1:8080/api/health
# 应返回：{"status":"ok","message":"Backend service is running","jwt_enabled":true}

# 检查 Redis
redis-cli ping
# 应返回：PONG
```

---

## 4. Web UI 使用指南

打开 `http://服务器IP:62879`

### 4.1 页面概览

| 页面 | 功能 |
|------|------|
| **单股分析** | 输入股票代码，提交 AI 多智能体分析 |
| **报告列表** | 查看历史分析报告 |
| **任务中心** | 查看分析任务进度和状态 |
| **配置管理** | 管理 LLM 模型、数据源、系统设置 |
| **缓存管理** | 查看 Redis 缓存状态 |
| **定时任务** | 管理定时分析任务 |
| **使用统计** | 查看 API 调用量和成本 |
| **系统日志** | 查看/导出系统运行日志 |
| **操作日志** | 查看用户操作记录 |

### 4.2 分析单只股票

1. 访问 **单股分析** 页面
2. 输入股票代码（如 `600519`）或 ETF 代码（如 `513180`）
3. 选择分析日期（默认当天）
4. 点击 **开始分析**
5. 等待分析完成，查看报告详情

**报告详情包含**：
- 核心投资结论（买入/卖出/持有）
- 关键指标（分析参考、风险评估、置信度）
- 技术面分析
- 基本面数据
- 消息面摘要
- 多维深度解析

### 4.3 下载报告

在 **报告详情** 页面，点击 **下载报告** 按钮，可导出 Markdown 格式分析报告。

### 4.4 系统日志导出

访问 **系统日志** 页面，点击对应日志文件后的 **下载** 按钮，可导出 ZIP 压缩包。

---

## 5. REST API 调用

API 地址：`http://127.0.0.1:8080`
鉴权方式：JWT Bearer Token

### 5.1 登录获取 Token

```bash
curl -X POST http://127.0.0.1:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

返回：

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
    "expires_in": 86400
  }
}
```

> MVP 阶段用户名为 `admin`，密码为 `admin123`。

### 5.2 提交股票分析

```bash
curl -X POST http://127.0.0.1:8080/api/analysis/single \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <您的Token>" \
  -d '{"stock_code": "600519", "trade_date": "2026-04-06", "user_context": {}}'
```

返回示例：

```json
{
  "success": true,
  "data": {
    "task_id": "600519_1744051200",
    "status": "completed",
    "report": "# 📊 贵州茅台 (600519) 深度分析报告\n\n---\n\n## 1. 核心投资结论\n\n**最终交易建议**：持有...",
    "elapsed_seconds": 120.5,
    "cached": false
  }
}
```

### 5.3 获取报告列表

```bash
curl http://127.0.0.1:8080/api/reports/list \
  -H "Authorization: Bearer <您的Token>"
```

### 5.4 获取报告详情

```bash
curl http://127.0.0.1:8080/api/reports/600519_20260406/detail \
  -H "Authorization: Bearer <您的Token>"
```

返回结构化字段：`decision`、`recommendation`、`risk_level`、`confidence_score`、`key_points`。

### 5.5 下载报告

```bash
curl http://127.0.0.1:8080/api/reports/600519_20260406/download \
  -H "Authorization: Bearer <您的Token>"
```

### 5.6 健康检查

```bash
curl http://127.0.0.1:8080/api/health
```

---

## 6. 自动巡航

自动巡航会在非交易时间对您的自选股进行批量预热分析，将报告缓存到 Redis。

### 6.1 使用方法

```bash
cd /root/stock-analyzer
python auto_cruiser.py
```

巡航脚本会：
1. 从 Redis 读取自选股列表（`watchlist:default`）
2. 逐只调用 `/api/analysis/single` 获取分析报告
3. 将报告存入 Redis 缓存，供次日开盘使用

### 6.2 巡航配置参数

在 `auto_cruiser.py` 顶部可调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `WATCHLIST_KEY` | `watchlist:default` | Redis 中的自选股集合 |
| `API_URL` | `http://127.0.0.1:8080/api/analysis/single` | 分析接口地址 |
| `REQUEST_TIMEOUT` | `600` | 单次请求超时（秒） |
| `REQUEST_INTERVAL` | `30` | 相邻请求间隔（秒） |

### 6.3 日志查看

```bash
tail -f /root/stock-analyzer/logs/api.log
```

---

## 7. 常见问题

### Q1：请求返回 401 Unauthorized

**原因**：未携带 Token 或 Token 已过期。

**解决方法**：
```bash
curl -X POST http://127.0.0.1:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Q2：Redis 连接失败

**症状**：`❌ Redis 连接失败，将降级为无缓存模式`

**解决方法**：
```bash
redis-server --daemonize yes
redis-cli ping
```

### Q3：分析耗时很长

**原因**：首次分析需要调用 LLM 多智能体，通常耗时 3-10 分钟。

**优化方法**：第二次查询同一股票时会命中 Redis 缓存，响应 < 1 秒。

### Q4：前端页面打不开

**检查项**：
1. Vite dev server 是否正常运行：`ps aux | grep vite`
2. 端口是否冲突：`ss -tlnp | grep 62879`
3. 防火墙是否放行：`firewall-cmd --add-port=62879/tcp`

### Q5：Token 过期了怎么办

Token 默认有效期为 24 小时。过期后重新调用 `/api/auth/login` 获取新 Token 即可。

### Q6：支持的股票代码格式

| 类型 | 示例 | 说明 |
|------|------|------|
| A股 | `000001`、`600519` | 6位数字 |
| ETF | `510300`、`513180` | 15/51/56/58/16/17 开头 |

### Q7：服务崩溃了怎么办

系统已部署 Watchdog 守护进程，会自动检测并重启崩溃的服务。

手动重启：
```bash
# 重启 API
kill $(ss -tlnp | grep 8080 | awk '{print $7}' | sed 's/.*pid=\([0-9]*\).*/\1/')
cd /root/stock-analyzer && PYTHONPATH=/root/stock-analyzer PYTHONGC=MANUAL nohup python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8080 > logs/api.log 2>&1 &

# 重启前端
cd /root/stock-analyzer/frontend && NODE_OPTIONS="--max-old-space-size=512" nohup npx vite --host 0.0.0.0 --port 62879 > /tmp/vite.log 2>&1 &
```

### Q8：如何查看实时日志

```bash
# API 日志
tail -f /root/stock-analyzer/logs/api.log

# Watchdog 日志
tail -f /tmp/watchdog.log

# Vite 前端日志
tail -f /tmp/vite.log
```

---

## 联系方式与支持

如遇到问题，请提供以下信息：
- 完整的错误日志（`/root/stock-analyzer/logs/api.log`）
- 复现步骤
- 股票代码和分析日期

---

*本文档最后更新：2026-04-12*
