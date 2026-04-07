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
- **首次实盘验证**：贵州茅台（600519）→ 结论 HOLD

## 技术栈

| 组件 | 技术 | 端口 |
|------|------|------|
| 后端 API | FastAPI + Python | 8080 |
| 前端 | Vue3 + Vite + Echarts | 62879 |
| WebSocket | ws + asyncio | 8030 |
| Agent 框架 | LangGraph | — |
| 大模型 | MiniMax M2.7 | — |
| 数据源 | BaoStock + AkShare | — |
| 缓存 | Redis | 6379 |
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
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ Market Agent │  │ News Agent   │  │Fundamental │  │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
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
python -m uvicorn main:app --host 0.0.0.0 --port 8080

# 启动前端（新窗口）
cd frontend && npm run dev -- --port 62879

# 或一键启动全部
bash scripts/start_all.sh
```

## 目录结构

```
stock-analyzer/
├── main.py                      # FastAPI 入口
├── auto_cruiser.py               # 自动巡航脚本（14:00 定时）
├── cron_daily_docs.py            # 每日文档更新（23:30 定时）
├── requirements.txt
├── frontend/                     # Vue3 前端
│   ├── src/
│   │   ├── views/               # 页面组件
│   │   ├── api/                 # API 客户端
│   │   └── components/          # 公共组件
│   └── package.json
├── tradingagents/
│   ├── llm_clients/             # MiniMax LLM 客户端
│   │   ├── base.py
│   │   └── rate_limiter.py
│   └── dataflows/
│       ├── akshare_stock.py     # AkShare 数据获取
│       ├── baostock_stock.py    # BaoStock 数据获取
│       ├── propagate.py          # LangGraph 状态机
│       └── tools/                # 工具函数
├── config/
│   └── logger.py                # 全局日志配置
├── docs/                         # 文档（飞书文档链接）
├── PRD.md                        # 产品需求文档
├── CHANGELOG.md                  # 更新日志
└── USER_GUIDE.md                # 用户指南
```

## 核心配置

```bash
# MiniMax API（通过环境变量或 .env）
MINIMAX_API_KEY=your_key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1

# BaoStock（自动登录，无需额外配置）
# Redis（可选，用于缓存）
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
```

## 更新日志

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
