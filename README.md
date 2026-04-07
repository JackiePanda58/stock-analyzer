# Stock Analyzer

多智能体 A 股分析系统，基于 LangGraph + MiniMax M2.7 + BaoStock，支持个股、ETF、LOF 等场内基金的深度技术面 + 基本面分析。

## 主要功能

- **智能代码识别**：自动识别股票（6位数字）、ETF（15/51/56/58/16/17 开头）
- **技术分析**：K 线形态、均线系统、MACD、KDJ、Boll 等指标综合打分
- **基本面分析**：通过 BaoStock + AkShare 获取财务报表、股东数据、估值指标
- **财报结构识别**：自动区分 ETF 与股票，跳过不适合 ETF 的资产负债表查询
- **多智能体协作**：市场分析员、新闻分析员、基本面分析员协同决策
- **最终报告**：提取 `final_trade_decision` 字段，输出 HOLD/BUY/SELL 中文结论
- **自动巡航**：每日 14:00（周一至周五）自动对自选股批量预热分析
- **自选股管理**：Redis HASH 存储，支持 A股/港股/美股 CRUD
- **用量追踪**：SQLite 持久化，记录每次 LLM 调用的 token 消耗与成本

## 技术栈

| 组件 | 技术 | 端口 |
|------|------|------|
| 后端 API | FastAPI + Python（`api_server.py`） | 8080 |
| 前端 | Vue3 + Vite + Echarts | 62879 |
| WebSocket | ws + asyncio | 8030 |
| Agent 框架 | LangGraph | — |
| 大模型 | MiniMax M2.7 | — |
| 数据源 | BaoStock + AkShare + 腾讯财经 | — |
| 缓存 | Redis | 6379 |
| 用量数据库 | SQLite | — |
| 守护进程 | Watchdog | — |

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Vue3 Frontend                     │  :62879
│              (Echarts K线 / 分析报告)                 │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP + WebSocket
┌─────────────────▼───────────────────────────────────┐
│                   FastAPI Backend                    │  :8080
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Market Agent │  │ News Agent   │  │Fundamental │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │
│         └──────────────────┼─────────────────┘         │
│                            ▼                          │
│                    LangGraph State                    │
│                     ┌────────┐                       │
│                     │  LLM   │  MiniMax M2.7         │
│                     └────────┘                        │
└─────────────────────────┬─────────────────────────────┘
                          ▼
          ┌───────────────┴────────────────┐
          │    BaoStock + AkShare         │
          │   (OHLCV / 财务报表 / 估值)   │
          └───────────────────────────────┘
```

## 快速启动

```bash
cd /root/stock-analyzer

# 启动后端（8080）
python api_server.py

# 启动前端（新窗口）
cd frontend && npm run dev -- --port 62879

# 或使用脚本启动全部
bash scripts/start_all.sh
```

## 核心 API

### 股票数据
| 接口 | 说明 |
|------|------|
| `GET /api/stocks/{symbol}/quote` | 实时行情（OHLCV + 涨跌幅） |
| `GET /api/stocks/{symbol}/kline` | K线数据（日/周/月 + 复权） |
| `GET /api/stocks/{symbol}/fundamentals` | 基本面信息（PE/PB/市值） |
| `GET /api/stocks/{symbol}/news` | 股票新闻 |
| `GET /api/stock-data/search?keyword=` | 股票搜索（代码/名称） |
| `GET /api/stock-data/basic-info/{code}` | 股票基本信息 |

### 自选股
| 接口 | 说明 |
|------|------|
| `GET /api/favorites` | 列表 |
| `POST /api/favorites` | 添加 |
| `DELETE /api/favorites/{stock_code}` | 删除 |
| `GET /api/favorites/check/{symbol}` | 是否自选 |

### 分析
| 接口 | 说明 |
|------|------|
| `POST /api/analysis/single` | 单股分析 |
| `GET /api/analysis/tasks` | 分析历史 |
| `GET /api/analysis/tasks/{id}/result` | 报告详情（结构化字段） |
| `GET /api/analysis/search?query=` | 搜索报告 |
| `GET /api/reports/list` | 报告列表（支持市场筛选） |
| `GET /api/reports/{id}/download?format=markdown` | 下载报告 |

### 用量统计
| 接口 | 说明 |
|------|------|
| `GET /api/usage/statistics` | 汇总（总tokens/总费用） |
| `GET /api/usage/records` | 明细记录 |
| `GET /api/usage/cost/daily` | 按日费用 |
| `GET /api/usage/cost/by-provider` | 按提供商统计 |

### 配置与系统
| 接口 | 说明 |
|------|------|
| `GET /api/config/llm` | LLM 提供商与模型配置 |
| `GET /api/config/settings` | 系统设置 |
| `GET /api/config/datasource` | 数据源配置 |
| `GET /api/system/status` | 系统状态 |
| `GET /api/system/info` | 系统信息（内存/CPU） |
| `GET /api/dashboard/summary` | 首页摘要 |
| `GET /api/dashboard/market` | 市场指数（沪深300等） |
| `GET /api/scheduler/jobs` | 定时任务管理 |
| `GET /api/model-capabilities/default-configs` | 模型能力配置 |

## 目录结构

```
stock-analyzer/
├── api_server.py                 # FastAPI 入口（端口 8080）
├── auto_cruiser.py               # 自动巡航脚本（14:00 定时）
├── cron_daily_docs.py            # 每日文档更新（23:30 定时）
├── ws_server.py                  # WebSocket 服务（端口 8030）
├── requirements.txt
├── frontend/                     # Vue3 前端
│   ├── src/
│   │   ├── views/               # 页面组件
│   │   ├── api/                 # API 客户端
│   │   └── components/          # 公共组件
│   └── package.json
├── tradingagents/
│   ├── llm_clients/             # MiniMax LLM 客户端
│   └── dataflows/
│       ├── akshare_stock.py     # AkShare 数据获取
│       ├── baostock_stock.py    # BaoStock 数据获取
│       └── propagate.py         # LangGraph 状态机
├── config/                      # 配置文件
│   ├── llm_config.json          # LLM 提供商配置
│   ├── model_catalog.json       # 模型目录
│   ├── data_sources.json        # 数据源配置
│   ├── config.json              # 系统设置
│   └── model_capabilities.json  # 模型能力
├── data/                        # 数据目录
│   └── usage.db                 # 用量 SQLite 数据库
└── reports/                     # 分析报告存储
```

## 核心配置

```bash
# MiniMax API（通过环境变量或 .env）
MINIMAX_API_KEY=your_key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1

# BaoStock（自动登录，无需额外配置）
# Redis（可选，用于缓存和自选股）
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 定时任务

| 时间 | 任务 | 说明 |
|------|------|------|
| 14:00（周一至周五） | 自动巡航 | 对自选股批量预热分析 |
| 23:30（每天） | 文档更新 | 自动更新 CHANGELOG/PRD/USER_GUIDE |

## API 文档

- Swagger UI: `http://host:8080/docs`
- WebSocket: `ws://host:8030`

## 依赖版本

```
langgraph>=0.4.0
langchain-core>=0.3.0
langchain-openai>=0.2.0
akshare>=1.14.0
baostock>=0.8.8
fastapi>=0.110.0
uvicorn>=0.29.0
vue>=3.4.0
echarts>=5.5.0
redis>=5.0.0
pdfkit>=1.0.0
```

## 更新日志

### v1.2.0 (2026-04-07) — 质量治理
- **Token统计**：用量追踪接入真实 SQLite 数据，前端图表全部真实渲染
- **股票数据**：实现完整行情/K线/基本面/新闻接口（全部非 stub）
- **分析历史**：从报告目录读取真实历史记录
- **分析端点**：progress/result/stop/share/delete/mark-failed 全部实现
- **Redis优化**：移除 KEYS 命令，改为直接文件查找（避免阻塞）
- **Config系统**：40+ 接口全部实现，含 LLM 提供商/模型目录/数据源配置
- **Scheduler**：真实读取 crontab + journalctl 执行历史
- **Multi-Source Sync**：数据源状态与健康检查
- **Model Capabilities**：模型能力分级与推荐系统
- **Dashboard**：首页摘要/市场指数/最近动态
- **系统信息**：内存/CPU/运行时间实时监控
- **股票搜索**：代码精确匹配 + 名称模糊搜索

### v1.1.0 (2026-04-07)
- **架构升级**：Chainlit → FastAPI + Vue3 + WebSocket
- **前端**：Vue3 + Vite + Echarts K 线图，端口 62879
- **实时通信**：WebSocket 端口 8030，支持分析进度推送
- **数据源**：BaoStock + AkShare 双数据源
- **自动巡航**：每日 14:00 自选股批量预热分析
- **守护进程**：Watchdog 自动拉起崩溃进程
- **首次实盘**：贵州茅台（600519）→ HOLD
- **文档体系**：PRD + CHANGELOG + USER_GUIDE

### v1.0.0 (2026-03-24)
- 首版发布，支持 K 线形态分析、技术指标综合打分
- 财务报表、股东结构、估值分析
- ETF/LOF 代码识别（支持 15/51/56/58/16/17 开头）
- MiniMax API 限流自动重试机制
- Chainlit Web UI 展示中文最终报告
