# User Guide

## TradingAgents-CN 多智能体股票分析系统 · 使用手册

> 本手册面向终端用户，帮助您快速上手安装、启动服务、提交分析、管理自选股和自动巡航。

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速安装](#2-快速安装)
3. [启动服务](#3-启动服务)
4. [Web UI 使用指南](#4-web-ui-使用指南)
5. [命令行工具](#5-命令行工具)
6. [REST API 调用](#6-rest-api-调用)
7. [自动巡航](#7-自动巡航)
8. [常见问题](#8-常见问题)

---

## 1. 环境要求

### 必需环境

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.10 | 建议 3.11 |
| Redis | ≥ 6.0 | 缓存服务，必须运行 |
| 网络 | 可访问 BaoStock/MiniMax | 防火墙放行 8080/62878 |

### 必需 API 密钥

| 密钥 | 获取方式 | 用途 |
|------|---------|------|
| `MINIMAX_API_KEY` | MiniMax 开放平台 | 大模型推理 |
| `.env` 文件 | 项目根目录 | 所有配置统一从此文件读取 |

---

## 2. 快速安装

### 2.1 克隆项目

```bash
cd /root/stock-analyzer
```

### 2.2 安装 Python 依赖

```bash
pip install -r requirements.txt
```

主要依赖包括：

| 依赖 | 用途 |
|------|------|
| `fastapi` + `uvicorn` | REST API 服务 |
| `chainlit` | Web UI |
| `pyjwt` | JWT 认证 |
| `redis` | 缓存 |
| **`baostock`** | A 股 OHLCV 及财务报表数据（主力数据源） |
| `akshare` | 金融数据（辅助：新闻/财务指标） |
| `langgraph` / `langchain` | 多智能体框架 |
| `openai` | MiniMax API 适配 |
| `rank_bm25` | LangGraph 文档检索 |

### 2.3 配置环境变量

在 `/root/stock-analyzer/.env` 中填写您的密钥：

```bash
# MiniMax API
MINIMAX_API_KEY=您的密钥

# Redis（默认无需修改）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### 2.4 安装 BaoStock

```bash
pip3 install baostock --break-system-packages
```

> **为什么需要 BaoStock？** Eastmoney（AkShare 行情数据源）在此 VPS 上被防火墙拦截，BaoStock 作为替代方案提供 A 股 OHLCV 日K线及财务报表数据。

### 2.5 启动 Redis

```bash
redis-server --daemonize yes
# 验证
redis-cli ping
# 应返回：PONG
```

---

## 3. 启动服务

系统有两套入口，**可以同时运行**。

### 方式一：Web UI（推荐新手）

```bash
cd /root/stock-analyzer
chainlit run app.py --host 0.0.0.0 --port 62878
```

启动成功后访问：`http://您的服务器IP:62878`

### 方式二：REST API 服务

```bash
cd /root/stock-analyzer
python3 api_server.py
# 或后台运行：
nohup python3 api_server.py > logs/api.log 2>&1 &
```

API 文档地址：`http://您的服务器IP:8080/docs`

### 验证服务状态

```bash
# 检查 API 是否正常运行
curl http://127.0.0.1:8080/

# 检查 Redis 是否连接
redis-cli ping
```

---

## 4. Web UI 使用指南

打开 `http://服务器IP:62878`，您将看到一个交互式对话界面。

### 4.1 分析单只股票

在对话框输入股票代码即可，例如：

```
000001
```

系统会自动识别为A股，分析完成后返回包含以下内容的结构化研报：
- 核心投资结论（买入/卖出/持有）
- 技术面分析（K线形态、MACD、KDJ、Boll）
- 基本面数据（财务报表、估值指标）
- 消息面摘要
- 最终交易建议

### 4.2 查看历史报告

点击左侧按钮 **📚 查看历史报告**，可下载历史生成的 PDF 研报。

### 4.3 管理自选股

点击 **⭐ 查看自选股**，可查看当前自选股列表。

添加自选股（回复消息）：

```
添加自选 600519
```

删除自选股：

```
删除自选 600519
```

### 4.4 设置自动巡航

点击 **⏱️ 巡航管理**，选择设置巡航时间，例如：

```
设置巡航 15:30
```

这会让系统在每天下午 15:30 自动对您的自选股进行预热分析。

---

## 5. 命令行工具

### 5.1 单次分析

```bash
cd /root/stock-analyzer
python run_analysis.py <股票代码>

# 示例
python run_analysis.py 000001
python run_analysis.py 510300  # ETF
```

### 5.2 其他分析脚本

| 脚本 | 用途 |
|------|------|
| `run_analysis.py` | 标准单次分析 |
| `run_analysis_timed.py` | 带计时分析 |
| `run_analysis_timed2.py` | 计时分析 v2 |
| `run_analysis_timed3.py` | 计时分析 v3 |

---

## 6. REST API 调用

API 地址：`http://127.0.0.1:8080`
鉴权方式：JWT Bearer Token

### 6.1 登录获取 Token

```bash
curl -X POST http://127.0.0.1:8080/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

返回：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

> MVP 阶段用户名为 `admin`，密码为 `admin123`。

### 6.2 提交股票分析

```bash
curl -X POST http://127.0.0.1:8080/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <您的Token>" \
  -d '{"symbol": "000001"}'
```

返回示例：

```json
{
  "status": "success",
  "symbol": "000001",
  "elapsed_seconds": 401.82,
  "report": "# 📊 Ping An Bank (000001.SZ) 深度分析报告\n\n---\n\n## 1. 核心投资结论\n\n**最终交易建议**：买入 (BUY)",
  "cached": false
}
```

### 6.3 刷新 Token

Token 过期前可使用此接口换发新 Token：

```bash
curl -X POST http://127.0.0.1:8080/api/v1/refresh \
  -H "Authorization: Bearer <您的Token>"
```

### 6.4 健康检查

```bash
curl http://127.0.0.1:8080/
```

---

## 7. 自动巡航

自动巡航会在非交易时间对您的自选股进行批量预热分析，将报告缓存到 Redis。

### 7.1 使用方法

```bash
cd /root/stock-analyzer
python auto_cruiser.py
```

巡航脚本会：
1. 从 Redis 读取自选股列表（`watchlist:default`）
2. 逐只调用 `/api/v1/analyze` 获取分析报告
3. 将报告存入 Redis 缓存，供次日开盘使用

### 7.2 巡航配置参数

在 `auto_cruiser.py` 顶部可调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `WATCHLIST_KEY` | `watchlist:default` | Redis 中的自选股集合 |
| `API_URL` | `http://127.0.0.1:8080/api/v1/analyze` | 分析接口地址 |
| `REQUEST_TIMEOUT` | `600` | 单次请求超时（秒） |
| `REQUEST_INTERVAL` | `30` | 相邻请求间隔（秒） |

### 7.3 日志查看

```bash
tail -f /root/stock-analyzer/logs/api.log
```

---

## 8. 常见问题

### Q1：请求返回 401 Unauthorized

**原因**：未携带 Token 或 Token 已过期。

**解决方法**：
```bash
# 重新登录获取新 Token
curl -X POST http://127.0.0.1:8080/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Q2：Redis 连接失败

**症状**：`❌ Redis 连接失败，将降级为无缓存模式`

**解决方法**：
```bash
# 确保 Redis 正在运行
redis-server --daemonize yes
redis-cli ping
```

### Q3：分析耗时很长

**原因**：首次分析需要调用 LLM 多智能体，通常耗时 3-10 分钟。

**优化方法**：第二次查询同一股票时会命中 Redis 缓存，响应 < 1 秒。

### Q4：Web UI 打不开

**检查项**：
1. Chainlit 是否正常运行：`ps aux | grep chainlit`
2. 端口是否冲突：`netstat -tlnp | grep 62878`
3. 防火墙是否放行：`firewall-cmd --add-port=62878/tcp`

### Q5：Token 过期了怎么办

Token 默认有效期为 24 小时。过期后重新调用 `/api/v1/login` 获取新 Token 即可。

### Q6：支持的股票代码格式

| 类型 | 示例 | 说明 |
|------|------|------|
| A股 | `000001`、`600519` | 6位数字 |
| ETF | `510300`、`513180` | 15/51/56/58/16/17 开头 |

### Q7：部分技术指标无法计算

**症状**：VWMA、成交量类指标显示 NaN。

**原因**：BaoStock 的 K-line 数据不提供成交量字段，这是 BaoStock 本身的数据限制。VWMA 等依赖成交量的指标无法在此系统计算。

### Q8：分析结果不准确

当前系统基于历史数据和公开信息进行 AI 分析，**不构成投资建议**。分析结果仅供参考，投资决策请自行承担风险。

---

## 联系方式与支持

如遇到问题，请提供以下信息联系开发团队：
- 完整的错误日志（`/root/stock-analyzer/logs/api.log`）
- 复现步骤
- 股票代码和分析日期

---

*本文档最后更新：2026-04-05*
