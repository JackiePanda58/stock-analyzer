# Stock Analyzer

多智能体股票分析系统，基于 LangGraph + MiniMax + AkShare，支持 A 股、ETF、LOF 等场内基金的深度技术面 + 基本面分析。

## 主要功能

- **代码识别**：自动识别股票（6位数字）、ETF（15/51/56/58/16/17 开头）
- **技术分析**：K 线形态、均线系统、MACD、KDJ、Boll 等指标综合打分
- **基本面分析**：通过 AkShare 获取财务报表、股东数据、估值指标
- **财报结构识别**：自动区分 ETF 与股票，跳过不适合 ETF 的资产负债表查询
- **速限重试机制**：接入全局日志，MiniMax API 限流时自动休眠重试
- **最终报告**：提取 `final_trade_decision` 字段，输出纯净中文分析结论

## 技术栈

- **Agent 框架**：LangGraph（状态机驱动的多智能体流水线）
- **大模型**：MiniMax（通过 `openai` 接口适配）
- **数据源**：AkShare（免费开源金融数据库）
- **前端**：Chainlit（Web UI）
- **日志**：自定义全局日志系统 `sys_logger`

## 目录结构

```
stock-analyzer/
├── app.py                        # Chainlit Web UI 入口
├── run_analysis.py               # 命令行分析脚本
├── config/
│   └── logger.py                 # 全局日志配置
├── tradingagents/
│   ├── llm_clients/
│   │   ├── base.py               # MiniMax LLM 客户端
│   │   └── rate_limiter.py        # 速率限制 & 重试装饰器
│   └── dataflows/
│       ├── akshare_stock.py       # AkShare 数据获取（含 ETF 识别）
│       ├── propagate.py           # LangGraph 状态机定义
│       └── tools/                 # 工具函数
├── data/                          # 缓存数据目录
└── logs/                          # 日志输出目录
```

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# Web UI（默认端口 62878）
chainlit run app.py --host 0.0.0.0 --port 62878

# 命令行分析
python run_analysis.py <股票代码>
# 例如：
python run_analysis.py 510300
python run_analysis.py 513180
```

## 依赖版本

```
langgraph>=0.4.0
langchain-core>=0.3.0
langchain-openai>=0.2.0
akshare>=1.14.0
baostock>=0.8.8
pandas>=2.0.0
numpy>=1.26.0
chainlit>=0.14.0
```

## 更新日志

### v1.0.0 (2026-03-24)
- 首版发布
- 支持 K 线形态分析、技术指标综合打分
- 支持财务报表、股东结构、估值分析
- ETF/LOF 代码识别（支持 15/51/56/58/16/17 开头）
- MiniMax API 限流自动重试机制
- Chainlit Web UI 展示纯净中文最终报告
