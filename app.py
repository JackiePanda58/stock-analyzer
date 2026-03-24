import chainlit as cl
import asyncio
import time
from datetime import datetime
import sys
import traceback
import os
import glob
import markdown
import pdfkit

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
    welcome_msg = """
👋 **欢迎使用极速 A股/ETF 分析引擎！**

👉 **请输入 6 位纯数字代码** 开始分析。
💡 **输入 `导出日志`**，下载系统排查日志。
📚 **输入 `历史报告`** 查看并下载过往的 PDF 研报归档。
"""
    await cl.Message(content=welcome_msg).send()

@cl.on_message
async def main(message: cl.Message):
    text = message.content.strip()

    # 1. 导出日志指令
    if text == "导出日志":
        log_path = "/root/stock-analyzer/logs/system_debug.log"
        if os.path.exists(log_path):
            await cl.Message(
                content="📥 **日志已备好：**",
                elements=[cl.File(name="system_debug.log", path=log_path, display="inline", mime="text/plain")]
            ).send()
        else:
            await cl.Message(content="⚠️ 日志文件不存在。").send()
        return

    # 2. 历史报告归档指令
    if text == "历史报告":
        pdf_files = sorted(glob.glob("/root/stock-analyzer/reports/*.pdf"), reverse=True)
        if not pdf_files:
            await cl.Message(content="📭 目前还没有生成过历史研报。").send()
            return
        elements = [cl.File(name=os.path.basename(f), path=f, display="inline") for f in pdf_files[:10]]
        await cl.Message(
            content=f"📁 **为您找到最近的 {len(elements)} 份历史研报，请点击下方附件下载：**",
            elements=elements
        ).send()
        return

    # 3. 股票分析流程
    symbol = text
    if not symbol.isdigit() or len(symbol) != 6:
        await cl.Message(content="⚠️ **格式错误**：请输入 6 位纯数字代码（如 `510300`）。").send()
        return

    date = datetime.now().strftime("%Y-%m-%d")
    msg = cl.Message(content=f"⏳ 正在深度分析 **{symbol}**，请稍候（约 3-5 分钟）...")
    await msg.send()

    try:
        t0 = time.time()
        sys_logger.info(f"[{symbol}] 🚀 开始执行 propagate 分析流水线...")

        result, _ = await asyncio.to_thread(ta.propagate, symbol, date)
        elapsed = time.time() - t0

        sys_logger.info(f"[{symbol}] ✅ 分析流水线顺利完成，耗时: {elapsed:.0f}秒")
        final_report = result.get("final_trade_decision", "⚠️ 未找到最终报告，原始输出:\n" + str(result))

        # 4. 自动生成 PDF
        report_dir = "/root/stock-analyzer/reports"
        os.makedirs(report_dir, exist_ok=True)
        pdf_path = f"{report_dir}/{symbol}_{date.replace('-','')}.pdf"
        elements = []

        try:
            html_content = markdown.markdown(final_report, extensions=['tables'])
            styled_html = f"""
            <html><head><meta charset='utf-8'><style>
            body {{ font-family: 'WenQuanYi Zen Hei', 'Microsoft YaHei', sans-serif; padding: 40px; line-height: 1.8; color: #333; }}
            h1, h2, h3 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #3498db; color: white; font-weight: bold; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .buy {{ color: #e74c3c; font-weight: bold; }}
            .sell {{ color: #27ae60; font-weight: bold; }}
            </style></head><body>{html_content}</body></html>
            """
            pdfkit.from_string(styled_html, pdf_path, options={
                'encoding': "UTF-8",
                'margin-top': '20mm',
                'margin-bottom': '20mm',
                'page-size': 'A4',
                'enable-local-file-access': ''
            })
            elements = [cl.File(name=f"{symbol}_深度研报.pdf", path=pdf_path, display="inline")]
            sys_logger.info(f"[{symbol}] ✅ PDF 生成成功: {pdf_path}")
        except Exception as pdf_err:
            sys_logger.error(f"[{symbol}] PDF生成失败:\n{traceback.format_exc()}")
            elements = []

        msg.content = f"✅ **分析完成！（耗时: {elapsed:.0f}秒）**\n\n---\n\n" + final_report
        msg.elements = elements
        await msg.update()

    except Exception as e:
        error_details = traceback.format_exc()
        sys_logger.error(f"[{symbol}] ❌ 分析过程发生灾难性中断:\n{error_details}")
        msg.content = f"❌ **分析发生异常中断**，系统已记录错误。请回复 `导出日志` 获取错误详情。\n```text\n{str(e)}\n```"
        await msg.update()
