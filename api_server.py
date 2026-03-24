"""
FastAPI 股票分析接口服务
- 输入校验：symbol 6位纯数字，date 合法日期格式
- 线程安全：每次请求独立实例化 TradingAgentsGraph，无全局共享状态
- 统一错误处理
"""
import asyncio
import sys
import traceback
import os
import re
from datetime import datetime
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import glob

sys.path.insert(0, '/root/stock-analyzer')
from dotenv import load_dotenv
load_dotenv('/root/stock-analyzer/.env')
from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from config.logger import sys_logger

set_config(TRADING_CONFIG)

# ─────────────────────────────────────────
# 输入模型（严格校验）
# ─────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    symbol: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6位股票代码，纯数字"
    )
    date: Optional[str] = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="分析日期，格式 YYYY-MM-DD，默认为今天"
    )

class HealthResponse(BaseModel):
    status: str
    timestamp: str

# ─────────────────────────────────────────
# 线程安全：每次请求独立实例化引擎
# ─────────────────────────────────────────
def build_ta():
    """每次调用独立实例化，无全局共享状态"""
    return TradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        debug=False,
        config=TRADING_CONFIG,
    )

# ─────────────────────────────────────────
# FastAPI 生命周期
# ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    sys_logger.info("=== FastAPI 接口服务启动 ===")
    yield
    sys_logger.info("=== FastAPI 接口服务关闭 ===")

app = FastAPI(
    title="A股分析引擎 API",
    version="1.0.0",
    description="提供股票/ETF 分析的 RESTful 接口，每次请求独立实例化，安全并发",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# 路由
# ─────────────────────────────────────────
@app.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    symbol = req.symbol
    target_date = req.date or datetime.now().strftime("%Y-%m-%d")

    sys_logger.info(f"[API] 收到分析请求: {symbol} @ {target_date}")

    try:
        ta = build_ta()          # ← 线程安全，每次请求独立实例
        result, _ = await asyncio.to_thread(ta.propagate, symbol, target_date)

        final_report = result.get(
            "final_trade_decision",
            f"⚠️ 未找到 final_trade_decision 字段，原始结果：\n{str(result)}"
        )
        sys_logger.info(f"[API] {symbol} 分析完成")

        return {
            "code": 0,
            "message": "分析成功",
            "data": {
                "symbol": symbol,
                "date": target_date,
                "report": final_report,
            }
        }

    except Exception as e:
        sys_logger.error(f"[API] {symbol} 分析异常:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": 1,
                "message": f"分析异常: {str(e)}",
                "symbol": symbol,
            }
        )

@app.get("/reports")
async def list_reports(limit: int = 10):
    """返回最近 N 份 PDF 研报列表"""
    pdf_files = sorted(
        glob.glob("/root/stock-analyzer/reports/*.pdf"),
        reverse=True
    )[:limit]

    return {
        "code": 0,
        "data": [
            {
                "name": os.path.basename(f),
                "path": f,
                "size": os.path.getsize(f),
            }
            for f in pdf_files
        ]
    }

@app.get("/reports/{filename}")
async def download_report(filename: str):
    """下载指定研报 PDF"""
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "", filename)
    path = f"/root/stock-analyzer/reports/{safe_name}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="研报不存在")
    return FileResponse(path, media_type="application/pdf", filename=safe_name)

# ─────────────────────────────────────────
# 启动入口
# ─────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )
