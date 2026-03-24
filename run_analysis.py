import os, sys, time
sys.path.insert(0, '/root/stock-analyzer')
from dotenv import load_dotenv
load_dotenv('/root/stock-analyzer/.env')
from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
set_config(TRADING_CONFIG)
from tradingagents.graph.trading_graph import TradingAgentsGraph

if len(sys.argv) < 3:
    print("❌ 用法错误。请使用: python3 run_analysis.py <股票/ETF代码> <日期YYYY-MM-DD>")
    sys.exit(1)

symbol = sys.argv[1]
date = sys.argv[2]

print(f"初始化系统...准备分析标的: {symbol} | 日期: {date}")
ta = TradingAgentsGraph(
    selected_analysts=["market", "news", "fundamentals"],
    debug=False,
    config=TRADING_CONFIG,
)

t0 = time.time()
try:
    result, agent_logs = ta.propagate(symbol, date)
    elapsed = time.time() - t0
    print(f"\n{'='*50}\n✅ 分析完成，总耗时: {elapsed:.0f}s")
    os.makedirs('/root/stock-analyzer/reports', exist_ok=True)
    report_path = f'/root/stock-analyzer/reports/{symbol}_{date.replace("-", "")}.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(result.get("final_trade_decision", str(result)))
    print(f"📄 报告已保存至: {report_path}\n{'='*50}")
    print("【报告内容预览】")
    print(result.get("final_trade_decision", str(result))[:400] + "...\n")
except Exception as e:
    import traceback
    print(f"\n❌ 分析过程发生严重错误：{e}")
    traceback.print_exc()
