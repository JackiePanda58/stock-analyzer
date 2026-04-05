# Product Requirements Document (PRD)

## TradingAgents-CN 多智能体股票分析系统

> 本文档定义 TradingAgents-CN 产品的功能需求、接口规范与技术架构，为开发团队和产品负责人之间的共识基础。

---

## 1. 产品概述

### 1.1 产品名称
TradingAgents-CN（又称 Stock Analyzer）

### 1.2 一句话描述
基于 LangGraph 状态机 + MiniMax 大模型 + AkShare 金融数据的**多智能体股票分析 SaaS 平台**，支持 A 股、ETF、LOF 等场内基金的深度技术面 + 基本面分析。

### 1.3 目标用户
- **散户投资者**：缺乏专业投研资源，需要 AI 辅助决策
- **量化交易者**：需要批量预热自选股、生成交易信号
- **投资顾问**：使用分析报告辅助客户沟通

### 1.4 核心价值
- 将耗时数小时的基本面 + 技术面分析压缩到分钟级
- 通过多智能体协作（市场分析员、新闻分析员、基本面分析员）输出结构化研报
- Redis 缓存机制降低 LLM 调用成本，提升响应速度

---

## 2. 系统架构

### 2.1 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| Web UI | Chainlit | 交互式对话界面，端口 62878 |
| API 服务 | FastAPI + Uvicorn | REST API，端口 8080，JWT 鉴权 |
| 多智能体引擎 | LangGraph | 状态机驱动的多智能体流水线 |
| 大模型 | MiniMax M2.7（OpenAI 兼容接口） | 单模型，支持 deep_think 模式 |
| 金融数据 | **BaoStock**（主力）+ AkShare（辅助） | BaoStock 提供 OHLCV；AkShare 提供新闻/财务指标 |
| 缓存层 | Redis | 分析报告缓存，TTL 12小时 |
| 调度器 | APScheduler / auto_cruiser.py | 盘后巡航定时任务 |

### 2.2 核心组件

```
stock-analyzer/
├── app.py                    # Chainlit Web UI 入口（端口 62878）
├── api_server.py            # FastAPI REST API（端口 8080，JWT 保护）
├── auto_cruiser.py          # 自动巡航脚本（定时预热自选股）
├── run_analysis.py          # 命令行单次分析脚本
├── config/
│   ├── settings.py           # TRADING_CONFIG 配置
│   └── logger.py            # sys_logger 全局日志
├── tradingagents/
│   ├── graph/
│   │   └── trading_graph.py  # TradingAgentsGraph（LangGraph 多智能体）
│   ├── llm_clients/
│   │   └── base.py          # MiniMax LLM 客户端
│   └── dataflows/
│       ├── akshare_stock.py  # AkShare 数据获取（含 ETF 识别）
│       └── propagate.py      # LangGraph 状态机定义
└── reports/                  # PDF 研报输出目录
```

---

## 3. 功能需求

### 3.1 多智能体分析引擎

**描述**：通过 `TradingAgentsGraph` 启动多个专业分析智能体（市场分析员、新闻分析员、基本面分析员），协作完成股票深度分析。

**输入**：
- `symbol`：6位股票代码（如 `000001`）
- `date`：分析日期，格式 `YYYY-MM-DD`（可选，默认当天）

**输出**：
- `final_trade_decision`：结构化交易建议（买入/卖出/持有）及理由
- 各智能体 intermediate steps（可追踪推理过程）

**支持的标的类型**：
- A 股（6位数字，如 `000001`、`600519`）
- ETF（15/51/56/58/16/17 开头，如 `510300`、`513180`）

**数据源架构**（2026-04-05 更新）：
- **BaoStock**（主力）：OHLCV 日K线数据、财务报表（资产负债表、利润表、现金流量表）、财务指标
- **AkShare**（辅助）：新闻（`stock_news_main_cx`）、个股信息（`stock_individual_info_em`）、财务指标（`stock_financial_analysis_indicator`）
- ⚠️ BaoStock 的 K-line 数据**不含成交量字段**，VWMA 等依赖成交量的指标无法计算

**技术要求**：
- 使用 `asyncio.to_thread` 实现 TradingAgentsGraph 的异步调用
- `asyncio.TimeoutError` 超时处理，超时返回 504

---

### 3.2 REST API 服务

**基础信息**：
- 服务地址：`http://0.0.0.0:8080`
- 文档地址：`http://localhost:8080/docs`
- 鉴权方式：JWT Bearer Token

#### 接口列表

##### `POST /api/v1/login`
登录接口，颁发 JWT Token。

**Request Body**：
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response（200）**：
```json
{
  "access_token": "<jwt_token>",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**MVP 用户表（硬编码）**：
| 用户名 | 密码 | 说明 |
|--------|------|------|
| admin | admin123 | 管理员 |

##### `POST /api/v1/analyze`
股票智能分析接口（**需鉴权**）。

**Headers**：`Authorization: Bearer <token>`

**Request Body**：
```json
{
  "symbol": "000001",
  "date": "2026-04-01"
}
```

**Response（200）**：
```json
{
  "status": "success",
  "symbol": "000001",
  "elapsed_seconds": 401.82,
  "report": "# 📊 Ping An Bank ...\n**最终交易建议**：买入...",
  "cached": false
}
```

**错误码**：
| HTTP 状态码 | error.code | 说明 |
|-------------|-----------|------|
| 401 | `MISSING_TOKEN` | 未携带 Token |
| 401 | `TOKEN_EXPIRED` | Token 已过期 |
| 401 | `TOKEN_INVALID` | Token 无效或被篡改 |
| 401 | `INVALID_CREDENTIALS` | 用户名或密码错误 |
| 400 | `INVALID_SYMBOL` | symbols 参数为空 |
| 400 | `TOO_MANY_SYMBOLS` | symbols 数量超过上限 |
| 500 | `INTERNAL_SERVER_ERROR` | 服务器内部错误 |
| 504 | `ANALYSIS_TIMEOUT` | LLM 多智能体分析超时 |

##### `GET /health`
健康检查接口（**无需鉴权**）。

##### `GET /`
根路径信息（**无需鉴权**）。

---

### 3.3 Redis 高速缓存

**策略**：Cache-Aside Pattern（旁路缓存）

**缓存 Key 规则**：`report:{symbol}:{date}`

**TTL**：43200 秒（12小时）

**流程**：
1. 请求到达，先查 Redis
2. 命中 → 直接返回 `cached: true`，绕过 LLM
3. 未命中 → 调用 TradingAgentsGraph → 结果写入 Redis → 返回

---

### 3.4 自动巡航（auto_cruiser.py）

**功能**：定时对自选股列表进行预热分析，将分析报告缓存到 Redis。

**触发方式**：
- 命令行手动运行：`python auto_cruiser.py`
- 可接入 APScheduler 实现定时自动运行

**自选股来源**：Redis Set，`watchlist:default`

**JWT 适配**：
- 启动时自动调用 `/api/v1/login` 获取 Token
- Token 缓存到全局变量，避免重复登录
- 收到 401 时自动重新登录并重试

**请求间隔**：默认 30 秒（`REQUEST_INTERVAL`），防止触发 API 限流

---

### 3.5 Web UI（Chainlit）

**端口**：62878

**核心功能**：
- 自然语言对话提交分析请求
- 查看自选股列表（添加/删除）
- 查看历史研报（PDF 导出）
- 盘后巡航管理（设置/查看/取消）
- 导出排查日志

---

## 4. 非功能需求

### 4.1 安全性
- 所有业务接口（`/api/v1/analyze` 等）必须携带有效 JWT Token
- JWT Secret 禁止硬编码，需支持环境变量注入
- MVP 阶段用户表硬编码，正式版需对接数据库
- CORS 配置需限制为实际前端域名

### 4.2 性能
- Redis 缓存命中时响应时间 < 100ms
- LLM 分析首次调用目标 < 5 分钟（受模型速度影响）
- 支持并发请求（Uvicorn ASGI）

### 4.3 可观测性
- 每请求生成 `X-Request-ID`，支持日志追踪
- 全局异常处理，防止堆栈信息泄露
- `sys_logger` 统一日志格式

### 4.4 可用性
- Redis 连接失败时自动降级为无缓存模式（不阻塞分析）
- API 请求超时 10 分钟（`REQUEST_TIMEOUT`）
- Token 失效自动重试机制

---

## 5. 路线图

### Phase 1 ✅ 已完成
- [x] Chainlit Web UI
- [x] FastAPI REST API（无鉴权）
- [x] Redis 缓存
- [x] 自动巡航脚本
- [x] JWT 安全认证

### Phase 2 📋 下一步
- [ ] 用户数据库（替代硬编码用户表）
- [ ] 多用户 SaaS 租户隔离
- [ ] Token 刷新机制持久化
- [ ] API 调用频率限制（Rate Limiting）

### Phase 3 📋 规划中
- [ ] 港股、美股数据支持
- [ ] 实时行情推送（WebSocket SSE）
- [ ] 分析报告 PDF 自动生成与邮件推送
- [ ] 开放平台 API（API Key 鉴权）

---

## 6. 附录

### 6.1 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `MINIMAX_API_KEY` | MiniMax API 密钥 | `xxx` |
| `REDIS_HOST` | Redis 主机 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `JWT_SECRET_KEY` | JWT 签名密钥（生产必设） | `your-super-secret` |

### 6.2 端口占用

| 端口 | 服务 | 说明 |
|------|------|------|
| 8080 | `api_server.py` | FastAPI JWT API |
| 62878 | `app.py` | Chainlit Web UI |
| 6379 | Redis | 缓存服务 |

### 6.3 关键文件

| 文件 | 作用 |
|------|------|
| `api_server.py` | FastAPI 应用入口，JWT 鉴权 + 分析接口 |
| `app.py` | Chainlit Web UI 入口 |
| `auto_cruiser.py` | 自动巡航脚本 |
| `tradingagents/graph/trading_graph.py` | TradingAgentsGraph 多智能体引擎 |
| `tradingagents/dataflows/akshare_stock.py` | **BaoStock + AkShare 双数据源适配器** |
| `config/settings.py` | TRADING_CONFIG 配置 |
| `config/logger.py` | sys_logger 日志配置 |
