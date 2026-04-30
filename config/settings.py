"""
股票分析系统配置
MiniMax M2.7 + A股专用版
接口方式：OpenAI 兼容接口（M2.7 仅支持此方式）
"""
import os
from dotenv import load_dotenv

load_dotenv()

TRADING_CONFIG = {
    # 项目路径
    "project_dir": "/root/stock-analyzer",
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "/root/stock-analyzer/reports"),
    "data_dir": "/root/stock-analyzer/data",
    "data_cache_dir": "/root/stock-analyzer/data/cache",

    # LLM 配置
    # 使用 OpenAI 兼容接口接入 MiniMax
    # 注意：域名是 minimaxi.com（两个 i），不是 minimax.io
    "llm_provider": "openai",
    "backend_url": os.getenv("OPENAI_BASE_URL", "https://api.minimaxi.com/v1"),

    # 模型选择（均为 M2.7 系列）
    # deep_think_llm：用于基本面分析、多空辩论等复杂推理任务
    # quick_think_llm：用于数据整理、简单判断等快速任务
    "deep_think_llm": "qwen-plus",
    "quick_think_llm": "qwen-turbo",

    # 资源限制（2核2G 服务器保守配置）
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 50,

    # 数据模式
    "online_tools": True,

    # 数据源配置（A 股使用 AkShare）
    "data_vendors": {
        "core_stock_apis": "akshare",
        "technical_indicators": "akshare",
        "fundamental_data": "akshare",
        "news_data": "akshare",
    },
    "tool_vendors": {},
}
