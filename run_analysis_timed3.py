import os, sys, time
sys.path.insert(0, '/root/stock-analyzer')
from dotenv import load_dotenv
load_dotenv('/root/stock-analyzer/.env')

from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
set_config(TRADING_CONFIG)

from tradingagents.dataflows.akshare_stock import (
    get_china_stock_data, 
    get_china_stock_indicators, 
    get_china_fundamentals,
)

ticker = "600519"
end_date = "2025-03-01"

print(f"逐步测试各函数耗时: {ticker}\n")

# Stock data (Eastmoney - fast)
t0 = time.time()
data = get_china_stock_data(ticker, "2024-09-01", end_date, adjust="qfq")
print(f"get_china_stock_data (Eastmoney): {time.time()-t0:.1f}s")

# Indicators (BaoStock - slow)
indicators = ["macd", "rsi", "boll", "atr", "close_50_sma"]
total_indicators = 0
for ind in indicators:
    t0 = time.time()
    result = get_china_stock_indicators(ticker, ind, end_date, 200)
    elapsed = time.time() - t0
    total_indicators += elapsed
    print(f"  {ind}: {elapsed:.1f}s")

print(f"5个指标总耗时: {total_indicators:.1f}s")

# Estimate full indicators (12 indicators)
print(f"预估12个指标总耗时: {total_indicators/5*12:.1f}s")
