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
import redis
import re
import subprocess

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
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    sys_logger.info("✅ Redis 缓存大脑连接成功！")
except Exception as e:
    sys_logger.error(f"❌ Redis 连接失败，将降级为无缓存模式: {e}")
    redis_client = None

@cl.action_callback("setup_cruise")
async def on_setup_cruise(action: cl.Action):
    msg = "⚙️ **盘后自动巡航管理中心**\n\n为您提供全自动的自选股预热服务。\n\n👉 **开启/修改巡航**：回复 `设置巡航 15:30`\n👉 **查看巡航规则**：回复 `查看巡航`\n👉 **查看今日报告**：回复 `今日巡航报告`\n👉 **取消自动巡航**：回复 `取消巡航`"
    await cl.Message(content=msg).send()

@cl.action_callback("view_watchlist")
async def on_view_watchlist(action: cl.Action):
    if not redis_client:
        await cl.Message(content="⚠️ Redis 未连接。").send()
        return
    try:
        members = redis_client.smembers("watchlist:default")
        member_list = sorted(members)
        if not member_list:
            content = "📋 **自选股名单为空**\n_回复 `添加自选 XXXXXX` 可新增，回复 `删除自选 XXXXXX` 可移除。"
        else:
            lines = "\n".join(f"  • `{code}`" for code in member_list)
            content = f"📋 **自选股名单**（共 {len(member_list)} 只）：\n{lines}\n\n_回复 `添加自选 XXXXXX` 可新增，回复 `删除自选 XXXXXX` 可移除。"
        await cl.Message(content=content).send()
    except Exception as e:
        await cl.Message(content=f"❌ 读取自选股失败：{str(e)}").send()

@cl.action_callback("view_history")
async def on_action_history(action: cl.Action):
    pdf_files = sorted(glob.glob("/root/stock-analyzer/reports/*.pdf"), reverse=True)
    if not pdf_files:
        await cl.Message(content="📭 目前还没有生成过历史研报。").send()
        return
    elements = [cl.File(name=os.path.basename(f), path=f, display="inline") for f in pdf_files[:10]]
    await cl.Message(content=f"📁 **最近的 {len(elements)} 份历史研报：**", elements=elements).send()

@cl.action_callback("export_log")
async def on_action_log(action: cl.Action):
    log_path = "/root/stock-analyzer/logs/system_debug.log"
    if os.path.exists(log_path):
        await cl.Message(content="📥 **排查日志已备好：**", elements=[cl.File(name="system_debug.log", path=log_path, display="inline", mime="text/plain")]).send()
    else:
        await cl.Message(content="⚠️ 未找到日志文件").send()

@cl.on_chat_start
async def start():
    actions = [
        cl.Action(name="view_history", payload={}, label="📚 查看历史报告"),
        cl.Action(name="view_watchlist", payload={}, label="⭐ 查看自选股"),
        cl.Action(name="setup_cruise", payload={}, label="⏱️ 巡航管理"),
        cl.Action(name="export_log", payload={}, label="🛠️ 导出排查日志"),
    ]
    welcome_msg = "👋 **欢迎使用极速 A股/ETF 分析引擎！**\n\n👉 **请输入 6 位纯数字代码** 开始深度分析。或者点击下方按钮进行管理："
    await cl.Message(content=welcome_msg, actions=actions).send()

@cl.on_message
async def main(message: cl.Message):
    text = message.content.strip()

    # 1. 巡航管理指令 (完全切换至 Linux 原生 Crontab)
    cruise_match = re.match(r"^设置巡航\s*(\d{1,2})[:：](\d{2})$", text)
    if cruise_match:
        h, m = cruise_match.groups()
        crontab_out = subprocess.run('crontab -l', shell=True, capture_output=True, text=True).stdout
        new_cron = [line for line in crontab_out.splitlines() if "auto_cruiser.py" not in line and line.strip()]
        python_path = subprocess.run('which python3', shell=True, capture_output=True, text=True).stdout.strip() or "/usr/bin/python3"
        job = f"{int(m)} {int(h)} * * 1-5 {python_path} /root/stock-analyzer/auto_cruiser.py >> /root/stock-analyzer/logs/cruiser.log 2>&1"
        new_cron.append(job)
        process = subprocess.Popen('crontab -', shell=True, stdin=subprocess.PIPE)
        process.communicate(input=("\n".join(new_cron) + "\n").encode('utf-8'))
        await cl.Message(content=f"✅ **原生巡航设置成功！**\n系统 Crontab 将在每个交易日 **{int(h):02d}:{int(m):02d}** 自动为您预热。").send()
        return

    if text == "取消巡航":
        crontab_out = subprocess.run('crontab -l', shell=True, capture_output=True, text=True).stdout
        new_cron = [line for line in crontab_out.splitlines() if "auto_cruiser.py" not in line and line.strip()]
        cron_text = "\n".join(new_cron) + "\n" if new_cron else ""
        process = subprocess.Popen('crontab -', shell=True, stdin=subprocess.PIPE)
        process.communicate(input=cron_text.encode('utf-8'))
        await cl.Message(content="✅ **系统原生巡航已彻底取消！**").send()
        return

    if text == "查看巡航":
        res = subprocess.run("crontab -l | grep 'auto_cruiser.py'", shell=True, capture_output=True, text=True)
        out = res.stdout.strip()
        if not out:
            await cl.Message(content="📭 **当前无生效的系统巡航任务。**").send()
        else:
            import re as _re
            mch = _re.search(r"^(\d+)\s+(\d+)\s+\*\s+\*\s+1-5", out, _re.MULTILINE)
            if mch:
                _m, _h = mch.groups()
                await cl.Message(content=f"⏱️ **巡航任务运行中**：\n\n系统将在每个交易日 **{int(_h):02d}:{int(_m):02d}** 自动为您预热自选股。").send()
            else:
                await cl.Message(content=f"⏱️ **系统原生任务列表**（原始格式）：\n```bash\n{out}\n```").send()
        return

    if text == "今日巡航报告":
        if not redis_client:
            await cl.Message(content="⚠️ Redis 未连接。").send()
            return
        members = redis_client.smembers("watchlist:default")
        if not members:
            await cl.Message(content="⚠️ 自选股为空，请先发送 `添加自选 XXXXXX`").send()
            return
        today = datetime.now().strftime("%Y-%m-%d")
        lines = []
        for code in sorted(members):
            if redis_client.exists(f"report:{code}:{today}"):
                lines.append(f"✅ `{code}`：今日研报已就绪 ⚡")
            else:
                lines.append(f"⏳ `{code}`：尚未生成")
        await cl.Message(content="📊 **今日巡航状态**：\n" + "\n".join(lines)).send()
        return

    # 2. 自选股管理指令
    if text == "查看自选":
        await on_view_watchlist(cl.Action(name="view_watchlist", payload={}, label=""))
        return

    add_match = re.match(r"^添加自选\s*(\d{6})$", text)
    if add_match:
        code = add_match.group(1)
        if redis_client and redis_client.sadd("watchlist:default", code):
            await cl.Message(content=f"✅ 已将 `{code}` 加入自选！").send()
        elif redis_client:
            await cl.Message(content=f"ℹ️ `{code}` 已在自选股中。").send()
        return

    del_match = re.match(r"^删除自选\s*(\d{6})$", text)
    if del_match:
        code = del_match.group(1)
        if redis_client and redis_client.srem("watchlist:default", code):
            await cl.Message(content=f"✅ 已移除 `{code}`。").send()
        elif redis_client:
            await cl.Message(content=f"ℹ️ `{code}` 不在自选股中。").send()
        return

    # 3. 旧版杂项
    if text == "导出日志":
        await on_action_log(None)
        return
    if text == "历史报告":
        await on_action_history(None)
        return

    # 4. 股票代码流转
    symbol = text
    if not symbol.isdigit() or len(symbol) != 6:
        await cl.Message(content="⚠️ **格式错误**：未识别的指令或代码。\n如果是查询股票，请输入 6 位纯数字。").send()
        return

    date = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"report:{symbol}:{date}"
    cached_report = None
    if redis_client:
        try: cached_report = redis_client.get(cache_key)
        except Exception: pass

    if cached_report:
        msg = cl.Message(content=f"⚡ **命中高速缓存！正在极速提取 **{symbol}** 的今日研报...**")
        await msg.send()
        final_report = cached_report
        elapsed = 0.01
    else:
        msg = cl.Message(content=f"⏳ 正在深度分析 **{symbol}**，请稍候...")
        await msg.send()
        try:
            t0 = time.time()
            local_ta = TradingAgentsGraph(
                selected_analysts=["market", "news", "fundamentals"],
                debug=False,
                config=TRADING_CONFIG,
            )
            result, _ = await asyncio.to_thread(local_ta.propagate, symbol, date)
            elapsed = time.time() - t0
            final_report = result.get("final_trade_decision", "⚠️ 未找到报告")
            if redis_client: redis_client.setex(cache_key, 43200, final_report)
        except Exception as e:
            sys_logger.error(traceback.format_exc())
            await cl.Message(content=f"❌ **分析异常**。\n{str(e)}").send()
            return

    # 5. 渲染 PDF
    report_dir = "/root/stock-analyzer/reports"
    os.makedirs(report_dir, exist_ok=True)
    pdf_path = f"{report_dir}/{symbol}_{date.replace('-','')}.pdf"
    elements = []
    try:
        if not os.path.exists(pdf_path):
            html_content = markdown.markdown(final_report, extensions=['tables'])
            styled_html = f"<html><head><meta charset='utf-8'><style>body {{ font-family: sans-serif; padding: 40px; line-height: 1.6; color: #333; }} table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }} th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }} th {{ background-color: #f8f9fa; font-weight: bold; }}</style></head><body>{html_content}</body></html>"
            await asyncio.to_thread(pdfkit.from_string, styled_html, pdf_path, options={'encoding': "UTF-8"})
        elements = [cl.File(name=f"{symbol}_深度研报.pdf", path=pdf_path, display="inline")]
    except Exception: pass

    actions = [
        cl.Action(name="view_history", payload={}, label="📚 历史报告"),
        cl.Action(name="view_watchlist", payload={}, label="⭐ 查看自选股"),
        cl.Action(name="setup_cruise", payload={}, label="⏱️ 巡航管理"),
    ]
    speed_str = "⚡ 极速缓存" if elapsed == 0.01 else f"耗时: {elapsed:.0f}秒"
    await cl.Message(content=f"✅ **分析完成！（{speed_str}）**\n\n---\n\n" + final_report, elements=elements, actions=actions).send()
