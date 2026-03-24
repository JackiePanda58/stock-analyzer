import chainlit as cl
import asyncio
import time
from datetime import datetime
import sys
import traceback
import os

sys.path.insert(0, '/root/stock-analyzer')
from dotenv import load_dotenv
load_dotenv('/root/stock-analyzer/.env')
from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from config.logger import sys_logger

sys_logger.info("=== Web UI 服务启动 ===")
set_config(TRADING_CONFIG)

try:
    ta = TradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        debug=False,
        config=TRADING_CONFIG,
    )
    sys_logger.info("✅ TradingAgentsGraph 多智能体引擎初始化成功")
except Exception as e:
    sys_logger.error(f"❌ 引擎初始化彻底失败:\n{traceback.format_exc()}")

@cl.on_chat_start
async def start():
    sys_logger.info("新用户建立了 Web 访问连接。")
    welcome_msg = """
👋 **欢迎使用极速 A股/ETF 分析引擎！**

本系统由 MiniMax M2.7 驱动，已全面兼容个股及全市场 ETF。
👉 **请输入 6 位纯数字代码**（例如：`600519` 或 `588000`）开始分析。
💡 **输入 `导出日志`**，可随时下载最新的系统排查日志。
"""
    await cl.Message(content=welcome_msg).send()

@cl.on_message
async def main(message: cl.Message):
    text = message.content.strip()

    # --- 新增：日志一键导出逻辑 ---
    if text == "导出日志":
        log_path = "/root/stock-analyzer/logs/system_debug.log"
        if os.path.exists(log_path):
            elements = [cl.File(name="system_debug.log", path=log_path, display="inline", mime="text/plain")]
            await cl.Message(content="📥 **系统诊断日志已备好，请点击下方附件下载：**", elements=elements).send()
        else:
            await cl.Message(content="⚠️ 暂未找到日志文件，可能系统尚未生成。").send()
        return
    # --------------------------------

    symbol = text
    sys_logger.info(f"👉 收到分析请求，目标代码: {symbol}")

    if not symbol.isdigit() or len(symbol) != 6:
        sys_logger.warning(f"用户输入了无效代码: {symbol}")
        await cl.Message(content="⚠️ **格式错误**：请输入正确的 6 位纯数字代码（如 `510300`）。").send()
        return

    date = datetime.now().strftime("%Y-%m-%d")
    msg = cl.Message(content=f"⏳ 正在拉起多智能体流水线，目标标的：**{symbol}**\n\n*深度分析通常需要 3-5 分钟，请不要关闭当前页面，喝口水稍作等待...*")
    await msg.send()

    try:
        t0 = time.time()
        sys_logger.info(f"[{symbol}] 🚀 开始执行 propagate 分析流水线...")

        result, _ = await asyncio.to_thread(ta.propagate, symbol, date)
        elapsed = time.time() - t0

        sys_logger.info(f"[{symbol}] ✅ 分析流水线顺利完成，耗时: {elapsed:.0f}秒")
        final_report = result.get("final_trade_decision", "⚠️ 未找到最终报告，原始输出:\n" + str(result))
        msg.content = f"✅ **分析完成！(耗时: {elapsed:.0f}秒)**\n\n---\n\n" + final_report
        await msg.update()

    except Exception as e:
        error_details = traceback.format_exc()
        sys_logger.error(f"[{symbol}] ❌ 分析过程发生灾难性中断:\n{error_details}")
        msg.content = f"❌ **分析发生异常中断**，系统已记录错误。请回复 `导出日志` 获取错误详情发给技术专家。\n```text\n{str(e)}\n```"
        await msg.update()
