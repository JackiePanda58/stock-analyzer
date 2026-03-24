import os, sys, time
sys.path.insert(0, '/root/stock-analyzer')
from dotenv import load_dotenv
load_dotenv('/root/stock-analyzer/.env')

from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
set_config(TRADING_CONFIG)

# 记录每次 LLM 调用的时间
call_times = []

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.rate_limiter import RateLimitedChatOpenAI

_orig_invoke = RateLimitedChatOpenAI.invoke
def _timed_invoke(self, *args, **kwargs):
    t0 = time.time()
    result = _orig_invoke(self, *args, **kwargs)
    elapsed = time.time() - t0
    name = getattr(result, 'name', 'unknown')
    call_times.append((name, elapsed))
    print(f"  [LLM调用] agent={name} 耗时={elapsed:.1f}s")
    return result
RateLimitedChatOpenAI.invoke = _timed_invoke

print("初始化系统...")
ta = TradingAgentsGraph(
    selected_analysts=["market", "news", "fundamentals"],
    debug=False,
    config=TRADING_CONFIG,
)

phase_start = time.time()
print(f"\n开始分析：600519 | {time.strftime('%H:%M:%S')}\n")

result, agent_logs = ta.propagate("600519", "2025-03-01")

total = time.time() - phase_start

print(f"\n{'='*50}")
print(f"总耗时：{total:.0f}s")
print(f"\n各 LLM 调用耗时明细：")
for i, (name, t) in enumerate(call_times, 1):
    print(f"  {i:2d}. {name:<35} {t:5.1f}s")
print(f"\n  LLM 总耗时：{sum(t for _,t in call_times):.1f}s")
print(f"  非LLM耗时（数据获取等）：{total - sum(t for _,t in call_times):.1f}s")
print(f"  调用次数：{len(call_times)}")
if call_times:
    print(f"  平均单次耗时：{sum(t for _,t in call_times)/len(call_times):.1f}s")
