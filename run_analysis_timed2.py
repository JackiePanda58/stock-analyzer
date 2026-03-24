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
    get_china_balance_sheet,
    get_china_income_statement,
    get_china_cashflow,
)

ticker = "600519"
end_date = "2025-03-01"

print(f"测试数据获取耗时: {ticker}\n")

# Test get_china_stock_data (needs start_date)
t0 = time.time()
data = get_china_stock_data(ticker, "2024-09-01", end_date, adjust="qfq")
t1 = time.time()
print(f"get_china_stock_data: {t1-t0:.1f}s")
if data:
    print(f"  返回: {len(data)} 字符")

# Test get_china_stock_indicators  
t0 = time.time()
indicators = get_china_stock_indicators(ticker, end_date)
t1 = time.time()
print(f"get_china_stock_indicators: {t1-t0:.1f}s")
if indicators:
    print(f"  返回: {len(indicators)} 字符")

# Test get_china_fundamentals
t0 = time.time()
fundamentals = get_china_fundamentals(ticker, end_date)
t1 = time.time()
print(f"get_china_fundamentals: {t1-t0:.1f}s")
if fundamentals:
    print(f"  返回: {len(fundamentals)} 字符")

# Test balance sheet
t0 = time.time()
bs = get_china_balance_sheet(ticker, "quarterly", end_date)
t1 = time.time()
print(f"get_china_balance_sheet: {t1-t0:.1f}s")
if bs:
    print(f"  返回: {len(bs)} 字符")

# Test income statement
t0 = time.time()
inc = get_china_income_statement(ticker, "quarterly", end_date)
t1 = time.time()
print(f"get_china_income_statement: {t1-t0:.1f}s")
if inc:
    print(f"  返回: {len(inc)} 字符")

# Test cashflow
t0 = time.time()
cf = get_china_cashflow(ticker, "quarterly", end_date)
t1 = time.time()
print(f"get_china_cashflow: {t1-t0:.1f}s")
if cf:
    print(f"  返回: {len(cf)} 字符")
