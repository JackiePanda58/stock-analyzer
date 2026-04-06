# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-05

## [Unreleased] - 2026-04-05

### Added
- （每日自动更新占位）



### Added
- **BaoStock 数据源适配器** (`tradingagents/dataflows/akshare_stock.py`)
  - 因 Eastmoney API 被防火墙拦截，新增 BaoStock 作为 OHLCV 主力数据源
  - BaoStock session 使用 `threading.Lock` 解决 LangGraph 并行工具调用时的并发问题
  - 支持函数：`get_china_stock_data`（日K线）、`get_china_stock_indicators`（财务指标）、
    `get_china_fundamentals`、`get_china_balance_sheet`、`get_china_income_statement`、`get_china_cashflow`
  - `get_china_market_news` 改用 `stock_news_main_cx`（替代已弃用的 `stock_telegraph_cls_em`）
  - `get_china_market_news` 新增 `limit` 参数

### Changed
- AkShare 降级为辅助数据源：仅用于 `stock_news_main_cx`（新闻）、`stock_individual_info_em`（个股信息）、`stock_financial_analysis_indicator`（财务指标）
- 历史行情（OHLCV）数据源由 AkShare/Eastmoney 切换为 BaoStock

### Fixed
- `get_china_stock_indicators`：修复 `datetime.timedelta` 重复导入 bug；修复日期过滤逻辑（`>=` → `<=`）
- `get_china_balance_sheet/income_statement/cashflow`：参数名 `ticker` → `symbol`（与 router 传参对齐）
- `get_china_stock_data`：日期格式 bug（`replace("-", "")` → `[:10]`，BaoStock 需要 `YYYY-MM-DD` 格式）

### Notes
- 首次 E2E 全流程测试完成（600519 贵州茅台），最终建议 HOLD，报告：`reports/600519_20250301.txt`
- BaoStock 成交量数据缺失（返回 NaN），BaoStock k-line 数据不提供 volume 字段
- AkShare 保留用于：新闻、个股信息、财务指标

---

## [1.0.0] - 2026-04-01

### Added
- **JWT 安全认证防线** (`api_server.py`)
  - 引入 PyJWT，实现 `/api/v1/login` 登录接口
  - `SECRET_KEY`、`ALGORITHM`（HS256）、`ACCESS_TOKEN_EXPIRE_MINUTES`（24小时）安全基建常量
  - `HTTPBearer` + `verify_token` 鉴权中间件，解码校验 JWT，Token 失效或篡改时返回 401
  - `/api/v1/analyze` 接口强制注入鉴权依赖 `token: str = Depends(verify_token)`
  - `/api/v1/refresh` Token 刷新接口，支持已登录用户换发新 Token
- **自动巡航脚本 JWT 适配** (`auto_cruiser.py`)
  - 新增全局 `GLOBAL_TOKEN` 变量，缓存 JWT 避免重复登录
  - 新增 `get_token()` 函数，自动换取并缓存 Token
  - `analyze_stock()` 自动注入 `Authorization: Bearer <token>` 请求头
  - Token 失效（401）时自动重新登录并重试
- **FastAPI 统一接口服务** (`api_server.py`)
  - 基于 FastAPI + Uvicorn 构建，端口 8080
  - 完整的 `AnalyzeRequest` / `AnalyzeResponse` Pydantic 模型
  - Redis Cache-Aside Pattern，用户维度缓存隔离
  - `TradingAgentsGraph` 多智能体异步调用（`asyncio.to_thread`）
  - 请求追踪：每请求生成 `X-Request-ID`、`X-Process-Time-Ms` 响应头
  - 全局异常处理，防止 500 时敏感信息泄露
- **TradingAgentsGraph 参数签名统一**
  - 修正初始化参数：`TradingAgentsGraph(selected_analysts=["market", "news", "fundamentals"], debug=False, config=TRADING_CONFIG)`
  - 与 Web UI (`app.py`) 保持一致

### Changed
- `api_server.py` 从简单无鉴权版本重构为 JWT 保护版本
- `auto_cruiser.py` 从直连无鉴权改为 JWT 自动鉴权模式

### Fixed
- 修复 `TradingAgentsGraph.__init__()` 参数不匹配导致的 500 错误
- 修复 SyntaxWarning：Pydantic Field pattern 字符串添加 `r` 前缀（`api_server.py` 重启验证通过）

---

## [0.9.x] - 2026-03-26

### Added
- Chainlit Web UI（`app.py`），端口 62878
  - 多智能体分析交互界面
  - 盘后自动巡航管理中心（`setup_cruise` action）
  - 自选股管理（添加/删除/查看）
  - 历史研报查看与 PDF 导出
  - 排查日志导出功能
- `auto_cruiser.py` 自动巡航脚本
  - 从 Redis `watchlist:default` 读取自选股列表
  - 定时对自选股预热分析，支持间隔配置
- Redis 高速缓存拦截机制
  - Cache Key：`report:{symbol}:{date}`，TTL 12小时
  - 缓存命中时直接返回，绕过 LLM 调用
- AkShare 数据源集成
  - 自动识别股票（6位数字）、ETF（15/51/56/58/16/17 开头）
  - K线形态、均线系统、MACD、KDJ、Boll 等技术指标
  - 财务报表、股东数据、估值指标基本面分析
- 日志系统（`config/logger.py`）
  - 全局 `sys_logger`，统一日志输出格式
  - 请求追踪与操作日志中间件

### Notes
- 更早版本记录已丢失

---

## [Unreleased] - 2026-04-06

### 🐛 Bug 修复

- **修复 `/api/analysis/single` Stub 问题**
  - 原来返回 `task_id: "stub"`，现在真正调用 `TradingAgentsGraph` 执行完整多智能体分析
  - 返回 `status: "completed"` + 完整报告，匹配前端轮询逻辑

- **修复 `/api/analysis/tasks/{task_id}/status` 端点**
  - 原来始终返回 `status: "pending"`，现在正确查询 Redis 缓存
  - 对于已缓存的报告返回 `status: "completed", progress: 100`

- **修复 `/api/analysis/tasks/{task_id}/result` 端点（缺失）**
  - 新增实现，从 Redis 缓存读取报告内容并返回结构化数据
  - 解决前端 `status: "completed"` 后调用 result 接口 404 的问题

- **修复 `/api/model-capabilities/recommend` HTTP 方法**
  - 前端发送 POST，后端原为 GET（第一组定义），现已统一为 POST

- **清理重复的 Model Capabilities 端点定义**
  - 删除了第一组重复的 model-capabilities 端点（保留正确实现的第二组）

- **BaoStock Volume 数据问题（误报 + 真实修复）**
  - 确认：BaoStock 实际上返回 `volume` 字段（测试验证：`fields: ['date','code','open','high','low','close','volume','amount']`）
  - 修复 `get_china_stock_indicators`：将 `volume` 字段加入 BaoStock 查询
  - VWMA：实现了真实的成交量加权平均价计算（之前硬编码为 NaN）
  - MFI：实现了真实的资金流量指标计算（之前用 RSI 近似）
  - 修正了描述文案：`"BaoStock 无成交量数据"` → `"BaoStock 已提供成交量数据"`

- **前端 WebSocket 端点硬编码**
  - 从 `ws://139.155.146.217:8083/...` 改为 `ws://139.155.146.217:8030/...`
  - 配合腾讯云开通的 8030 端口
  - Vite proxy 添加 `ws: true` 支持 WebSocket 升级

- **前端 API 代理配置**
  - Vite dev server 端口由 62879→62880→62879 漂移问题已稳定
  - 62879 端口确认可用

