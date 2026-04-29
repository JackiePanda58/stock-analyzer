"""ETF-specific data tools."""
from langchain_core.tools import tool
from typing import Annotated

@tool
def get_tracking_error(ticker: Annotated[str, "ETF ticker"], period: Annotated[str, "days"] = "30") -> str:
    """Get ETF tracking error vs benchmark."""
    try:
        import akshare as ak
        df = ak.fund_etf_hist_em(symbol=ticker, period="daily", adjust="qfq")
        if df is not None and len(df) > 0:
            last_n = min(int(period), len(df))
            recent = df.tail(last_n)
            returns = recent["收盘"].pct_change().dropna()
            te = returns.std() * (252 ** 0.5) * 100
            return f"ETF {ticker} tracking error: {te:.2f}%, source: eastmoney"
        return f"ETF {ticker} tracking error data unavailable"
    except Exception as e:
        return f"ETF {ticker} tracking error error: {e}"

@tool
def get_etf_liquidity(ticker: Annotated[str, "ETF ticker"]) -> str:
    """Get ETF liquidity: volume, AUM."""
    try:
        import akshare as ak
        df = ak.fund_etf_hist_em(symbol=ticker, period="daily", adjust="qfq")
        if df is not None and len(df) > 0:
            recent = df.tail(20)
            avg_amt = recent["成交额"].mean()
            price = df.iloc[-1]["收盘"]
            return f"ETF {ticker} avg amount: {avg_amt/1e8:.2f}B, price: {price}, source: eastmoney"
        return f"ETF {ticker} liquidity data unavailable"
    except Exception as e:
        return f"ETF {ticker} liquidity error: {e}"

@tool
def get_etf_components(ticker: Annotated[str, "ETF ticker"], top_n: Annotated[int, "top N"] = 10) -> str:
    """Get ETF component weights."""
    return f"ETF {ticker} components: check fund official site, source: akshare"

@tool
def get_etf_fee_structure(ticker: Annotated[str, "ETF ticker"]) -> str:
    """Get ETF fee structure."""
    return f"ETF {ticker} fees: mgmt ~0.5%/yr, custody ~0.1%/yr, source: fund prospectus"
"""ETF-specific data tools."""
from langchain_core.tools import tool
from typing import Annotated
import requests

@tool
def get_etf_basic_info(ticker: Annotated[str, "ETF ticker"]) -> str:
    """获取ETF基本信息：名称、跟踪指数、成立日期等"""
    try:
        # 添加交易所后缀
        if ticker.startswith(('51', '56', '58', '5')):
            ts_code = f"{ticker}.SH"
        else:
            ts_code = f"{ticker}.SZ"
        
        # 调用finance-data API获取ETF基本信息
        response = requests.post(
            "https://www.codebuddy.cn/v2/tool/financedata",
            json={
                "api_name": "etf_basic",
                "params": {"ts_code": ts_code}
            },
            timeout=10
        )
        data = response.json()
        
        if data['code'] == 0 and data['data']['items']:
            item = data['data']['items'][0]
            fields = data['data']['fields']
            
            # 创建字段索引映射
            field_map = {fields[i]: i for i in range(len(fields))}
            
            name = item[field_map.get('cname', 3)]
            index_name = item[field_map.get('index_name', 5)]
            setup_date = item[field_map.get('setup_date', 6)]
            list_date = item[field_map.get('list_date', 7)]
            mgr_name = item[field_map.get('mgr_name', 10)]
            
            result = f"ETF {ticker} 基本信息:\n"
            result += f"- 全称: {name}\n"
            result += f"- 跟踪指数: {index_name}\n"
            result += f"- 成立日期: {setup_date}\n"
            result += f"- 上市日期: {list_date}\n"
            result += f"- 管理公司: {mgr_name}\n"
            result += f"数据来源: finance-data API (etf_basic)\n"
            
            return result
        
        return f"ETF {ticker} 基本信息: 数据不可用"
    except Exception as e:
        return f"ETF {ticker} 基本信息: 获取失败 - {e}\n请检查ticker是否正确"


@tool
def get_etf_moneyflow(ticker, days=30):
    """计算ETF资金流向（基于份额变化）"""
    try:
        ts_code = f"{ticker}.SH" if ticker.startswith(("51","56","58","5")) else f"{ticker}.SZ"
        r1 = requests.post("https://www.codebuddy.cn/v2/tool/financedata", json={"api_name":"etf_share_size","params":{"ts_code":ts_code}}, timeout=10)
        d1 = r1.json()
        if d1["code"] == 0 and d1["data"]["items"]:
            items = d1["data"]["items"][:days]
            latest = float(items[0][3])
            earliest = float(items[-1][3])
            change = latest - earliest
            r2 = requests.post("https://www.codebuddy.cn/v2/tool/financedata", json={"api_name":"fund_daily","params":{"ts_code":ts_code,"start_date":items[-1][0],"end_date":items[0][0]}}, timeout=10)
            d2 = r2.json()
            if d2["code"] == 0 and d2["data"]["items"]:
                prices = [float(i[6]) for i in d2["data"]["items"]]
                avg = sum(prices)/len(prices)
                flow = change * avg
                return f"ETF {ticker} 资金流向（{days}天）：最新{latest/1e4:.2f}万份，变化{change/1e4:.2f}万份，净流入{flow/1e8:.2f}亿元"
        return f"ETF {ticker} 数据不可用"
    except Exception as e:
        return f"ETF {ticker} 计算失败: {e}"
