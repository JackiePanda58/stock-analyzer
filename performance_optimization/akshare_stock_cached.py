"""
AkShare + BaoStock A 股数据适配器 - 带 Redis 缓存优化版本
历史行情、技术指标、财务三表：BaoStock（服务器可访问）
财务指标（PE/ROE 等）、新闻：AkShare

OPTIMIZATION: Redis caching layer for data retrieval
- Cache stock data, indicators, fundamentals with 12-hour TTL
- Reduces redundant API calls for repeated analysis
- Expected improvement: 20-30% for repeated queries
"""
import time
import json
import baostock as bs
import traceback
from config.logger import sys_logger
import akshare as ak
import pandas as pd
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

# Redis 缓存客户端
try:
    import redis.asyncio as aioredis
    redis_client = aioredis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    sys_logger.info("✅ Dataflows: Redis 缓存已初始化（db=1）")
except Exception as e:
    sys_logger.warning(f"⚠️  Dataflows: Redis 连接失败，将降级为无缓存模式：{e}")
    redis_client = None


# ── BaoStock 连接管理（线程池优化）────────────────────────────

# OPTIMIZATION: 使用 RLock 替代 Lock，允许同一线程重复获取
_bs_lock = threading.RLock()  # 可重入锁，支持同一线程内的递归调用
_bs_session_count = 0  # 会话计数器


@contextmanager
def _baostock_session():
    """BaoStock 会话上下文管理器（线程安全，支持重入）"""
    global _bs_session_count
    with _bs_lock:
        _bs_session_count += 1
        try:
            # OPTIMIZATION: 减少不必要的等待，仅在首次连接时等待
            if _bs_session_count == 1:
                time.sleep(0.1)  # 首次连接等待 0.1s
            lg = bs.login()
            if lg.error_code != '0':
                raise ConnectionError(f"BaoStock 登录失败：{lg.error_msg}")
            yield
        finally:
            bs.logout()
            _bs_session_count -= 1


def _bs_query_to_df(rs) -> pd.DataFrame:
    """将 BaoStock 查询结果转为 DataFrame"""
    data_list = []
    while (rs.error_code == '0') and rs.next():
        data_list.append(rs.get_row_data())
    return pd.DataFrame(data_list, columns=rs.fields) if data_list else pd.DataFrame()


# ── 缓存辅助函数 ──────────────────────────────────────────────────

async def _cache_get(key: str) -> Optional[str]:
    """从 Redis 获取缓存"""
    if redis_client is None:
        return None
    try:
        return await redis_client.get(key)
    except Exception as e:
        sys_logger.warning(f"Redis get 失败：{e}")
        return None


async def _cache_set(key: str, value: str, ttl: int = 12 * 60 * 60) -> bool:
    """设置 Redis 缓存（默认 12 小时 TTL）"""
    if redis_client is None:
        return False
    try:
        await redis_client.setex(key, ttl, value)
        return True
    except Exception as e:
        sys_logger.warning(f"Redis setex 失败：{e}")
        return False


def is_etf(symbol: str) -> bool:
    """判断是否为 ETF 基金"""
    plain = symbol.replace(".SS", "").replace(".SZ", "").replace(".BJ", "").replace("sh.", "").replace("sz.", "").strip()
    return plain.startswith(('15', '51', '56', '58', '16', '17'))


def _normalize_symbol(symbol: str) -> tuple[str, str]:
    """统一股票/ETF 代码格式"""
    plain = symbol.replace(".SS", "").replace(".SZ", "").replace(".BJ", "").replace("sh.", "").replace("sz.", "").strip()
    # 沪市股票 (6 开头), 沪市 ETF(51,56,58 开头)
    if plain.startswith(('6', '9', '5')):
        bs_code = f"sh.{plain}"
    else:
        bs_code = f"sz.{plain}"
    return bs_code, plain


# ── 历史行情（带缓存）─────────────────────────────────────────────────

async def get_china_stock_data_async(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
) -> str:
    """
    异步版本：获取 A 股历史行情（日线 OHLCV）- 带缓存
    """
    bs_code, plain = _normalize_symbol(symbol)
    start = start_date[:10]
    end = end_date[:10]
    adjustflag = "2" if adjust == "qfq" else "1" if adjust == "hfq" else "3"
    
    # 缓存键
    cache_key = f"stock_data:{plain}:{start}:{end}:{adjustflag}"
    
    # 尝试从缓存获取
    cached = await _cache_get(cache_key)
    if cached:
        sys_logger.info(f"✅ 缓存命中：{symbol} {start}→{end}")
        return cached
    
    # 缓存未命中，获取数据
    try:
        with _baostock_session():
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag=adjustflag,
            )
            df = _bs_query_to_df(rs)

        if df.empty:
            result = f"未找到 {symbol} 在 {start_date} 至 {end_date} 的历史数据"
        else:
            # 数值类型转换
            for col in ["open", "high", "low", "close", "volume", "amount", "turn", "pctChg"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.set_index("date")

            header = f"# A 股历史行情 {symbol} 从 {start_date} 到 {end_date}\n"
            header += f"# 总记录数：{len(df)}\n"
            header += f"# BaoStock 数据\n\n"
            result = header + df.to_string()
        
        # 写入缓存
        await _cache_set(cache_key, result)
        return result

    except Exception as e:
        return f"获取 {symbol} 历史行情失败：{e}"


def get_china_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
) -> str:
    """
    同步版本：获取 A 股历史行情（日线 OHLCV）- 带缓存
    向后兼容原有同步调用
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(get_china_stock_data_async(symbol, start_date, end_date, adjust))


# ── 技术指标（带缓存）─────────────────────────────────────────────────

async def get_china_stock_indicators_async(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    """
    异步版本：计算 A 股技术指标 - 带缓存
    """
    from dateutil.relativedelta import relativedelta

    bs_code, plain = _normalize_symbol(symbol)

    # 计算查询日期范围
    try:
        curr_dt = datetime.strptime(curr_date[:10], "%Y-%m-%d")
        start_dt = curr_dt - relativedelta(days=max(look_back_days + 120, 200))
        fetch_start = start_dt.strftime("%Y-%m-%d")
        fetch_end = (curr_dt + relativedelta(days=7)).strftime("%Y-%m-%d")
    except Exception as e:
        fetch_start = curr_date
        fetch_end = curr_date

    # 缓存键
    cache_key = f"indicators:{plain}:{indicator}:{curr_date[:10]}:{look_back_days}"
    
    # 尝试从缓存获取
    cached = await _cache_get(cache_key)
    if cached:
        sys_logger.info(f"✅ 指标缓存命中：{symbol} {indicator}")
        return cached

    best_ind_params = {
        "close_50_sma": "50 SMA：中期趋势指标，用于判断趋势方向并作为动态支撑/阻力位。",
        "close_200_sma": "200 SMA：长期趋势基准，确认整体市场趋势，识别黄金交叉/死亡交叉。",
        "close_10_ema": "10 EMA：快速短期均线，捕捉快速动量变化和潜在入场点。",
        "macd": "MACD：通过 EMA 差异计算动量，观察交叉和背离作为趋势变化信号。",
        "macds": "MACD Signal：MACD 线的 EMA 平滑，与 MACD 线交叉触发交易。",
        "macdh": "MACD Histogram：MACD 线与信号线的差距，可视化动量强度。",
        "rsi": "RSI：测量动量以标记超买/超卖状态，70/30 阈值。",
        "boll": "Bollinger Middle Band (20 SMA)，作为价格运动的动态基准。",
        "boll_ub": "Bollinger Upper Band：通常比中轨高 2 个标准差，标记潜在超买。",
        "boll_lb": "Bollinger Lower Band：通常比中轨低 2 个标准差，指示潜在超卖。",
        "atr": "ATR：平均真实波幅以衡量波动性，用于设置止损水平。",
        "vwma": "VWMA：成交量加权平均价格，BaoStock 已提供成交量数据。",
        "mfi": "MFI：资金流量指标，BaoStock 已提供成交量数据。",
    }

    if indicator not in best_ind_params:
        raise ValueError(f"指标 {indicator} 不支持。请选择：{list(best_ind_params.keys())}")

    try:
        with _baostock_session():
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,close,high,low,volume",
                start_date=fetch_start,
                end_date=fetch_end,
                frequency="d",
                adjustflag="2",
            )
            df = _bs_query_to_df(rs)

        if df.empty:
            result = f"未找到 {symbol} 的历史数据，无法计算技术指标"
        else:
            for col in ["close", "high", "low", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["close", "high", "low"])

            close = df["close"]
            high = df["high"]
            low_df = df["low"]
            volume = df["volume"] if "volume" in df.columns else None

            # MACD (12, 26, 9)
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line

            # RSI (14)
            delta = close.diff()
            gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
            loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
            rs_val = gain / loss.replace(0, float("nan"))
            rsi = 100 - (100 / (1 + rs_val))

            # 布林带 (20, 2)
            ma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            boll_upper = ma20 + 2 * std20
            boll_lower = ma20 - 2 * std20

            # KDJ
            n = 9
            low_n = low_df.rolling(n).min()
            high_n = high.rolling(n).max()
            rsv = (close - low_n) / (high_n - low_n).replace(0, float("nan")) * 100
            k = rsv.ewm(com=2, adjust=False).mean()
            d = k.ewm(com=2, adjust=False).mean()
            j = 3 * k - 2 * d

            # ATR
            tr1 = high - low_df
            tr2 = abs(high - close.shift())
            tr3 = abs(low_df - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()

            # VWMA
            if volume is not None and not volume.isna().all():
                vwma_vals = volume.rolling(20).apply(
                    lambda x: (x * close.iloc[x.index]).sum() / x.sum(), raw=False
                ).values
            else:
                vwma_vals = [float('nan')] * len(close)

            # MFI
            if volume is not None and not volume.isna().all():
                typical = (high + low_df + close) / 3
                pos_flow = typical.where(typical > typical.shift(), 0).rolling(14).sum()
                neg_flow = typical.where(typical < typical.shift(), 0).rolling(14).sum()
                mfi_vals = (100 - 100 / (1 + pos_flow / neg_flow.replace(0, float('nan')))).values
            else:
                mfi_vals = [float('nan')] * len(close)

            ind_col_map = {
                "macd": "MACD", "macds": "MACD_signal", "macdh": "MACD_hist",
                "rsi": "RSI14", "boll": "BOLL_mid", "boll_ub": "BOLL_upper",
                "boll_lb": "BOLL_lower", "atr": "ATR",
                "close_50_sma": "SMA50", "close_200_sma": "SMA200",
                "close_10_ema": "EMA10", "vwma": "VWMA", "mfi": "RSI14",
            }

            result_df = pd.DataFrame({
                "date": df["date"].values,
                "close": close.values,
                "MACD": macd_line.values,
                "MACD_signal": signal_line.values,
                "MACD_hist": macd_hist.values,
                "RSI14": rsi.values,
                "BOLL_mid": ma20.values,
                "BOLL_upper": boll_upper.values,
                "BOLL_lower": boll_lower.values,
                "KDJ_K": k.values,
                "KDJ_D": d.values,
                "KDJ_J": j.values,
                "ATR": atr.values,
                "SMA50": close.rolling(50).mean().values,
                "SMA200": close.rolling(200).mean().values,
                "EMA10": close.ewm(span=10, adjust=False).mean().values,
                "VWMA": vwma_vals,
                "MFI": mfi_vals,
            })

            filtered = result_df[result_df["date"] <= curr_date[:10]].tail(look_back_days)

            if filtered.empty:
                result = f"未找到 {symbol} 在 {curr_date} 之前的历史数据"
            else:
                show_col = ind_col_map.get(indicator, "close")
                disp = filtered[["date", show_col]].copy()
                disp.columns = ["date", indicator]
                result = (
                    f"## {indicator} values (last {len(disp)} trading days up to {curr_date[:10]}):\n"
                    + disp.to_string(index=False)
                    + "\n\n"
                    + best_ind_params.get(indicator, "")
                )
        
        # 写入缓存
        await _cache_set(cache_key, result, ttl=6 * 60 * 60)  # 指标缓存 6 小时
        return result

    except Exception as e:
        return f"计算 {symbol} 技术指标 {indicator} 失败：{e}"


def get_china_stock_indicators(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
) -> str:
    """
    同步版本：计算 A 股技术指标 - 带缓存
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(get_china_stock_indicators_async(symbol, indicator, curr_date, look_back_days))


# ── 财务数据（带缓存）─────────────────────────────────────────────────

async def _fetch_all_financial_data_async(bs_code: str) -> dict:
    """
    异步版本：单次 BaoStock 会话查完三表，带缓存
    """
    cache_key = f"financials:{bs_code}"
    
    # 尝试从缓存获取
    cached = await _cache_get(cache_key)
    if cached:
        sys_logger.info(f"✅ 财务数据缓存命中：{bs_code}")
        return json.loads(cached)
    
    quarters = [
        ("2024", "3"),
        ("2024", "2"),
        ("2023", "4"),
    ]

    result = {
        "balance": pd.DataFrame(),
        "income": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
    }

    with _baostock_session():
        for year, quarter in quarters:
            if result["balance"].empty:
                rs = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
                result["balance"] = _bs_query_to_df(rs)

            if result["income"].empty:
                rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                result["income"] = _bs_query_to_df(rs)

            if result["cashflow"].empty:
                rs = bs.query_cash_flow_data(code=bs_code, year=year, quarter=quarter)
                result["cashflow"] = _bs_query_to_df(rs)

            if all(not df.empty for df in result.values()):
                break

    # 转换 DataFrame 为可序列化格式
    serializable_result = {
        "balance": result["balance"].to_dict() if not result["balance"].empty else {},
        "income": result["income"].to_dict() if not result["income"].empty else {},
        "cashflow": result["cashflow"].to_dict() if not result["cashflow"].empty else {},
    }
    
    # 写入缓存（24 小时 TTL，财务数据变化较慢）
    await _cache_set(cache_key, json.dumps(serializable_result), ttl=24 * 60 * 60)
    
    return result


def get_china_fundamentals(symbol: str, curr_date: Optional[str] = None) -> str:
    """获取 A 股基本面数据（带缓存）"""
    if is_etf(symbol):
        return "该标的为 ETF 基金，无传统公司财务报表数据。"
    
    _, plain = _normalize_symbol(symbol)
    cache_key = f"fundamentals:{plain}"
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # 尝试从缓存获取
    cached = loop.run_until_complete(_cache_get(cache_key))
    if cached:
        sys_logger.info(f"✅ 基本面缓存命中：{symbol}")
        return cached
    
    result_parts = []

    try:
        df = ak.stock_financial_analysis_indicator(symbol=plain, start_year="2023")
        if df is not None and not df.empty:
            result_parts.append("=== 财务分析指标（近期）===")
            key_cols = [c for c in df.columns if any(
                kw in c for kw in ["ROE", "ROA", "毛利", "净利", "营收", "EPS", "市盈", "日期"]
            )]
            if key_cols:
                result_parts.append(df[key_cols].head(6).to_string(index=False))
            else:
                result_parts.append(df.head(4).to_string(index=False))
    except Exception as e:
        result_parts.append(f"财务指标获取失败：{e}")

    try:
        info_df = ak.stock_individual_info_em(symbol=plain)
        if info_df is not None and not info_df.empty:
            result_parts.append("\n=== 股票基本信息 ===")
            result_parts.append(info_df.to_string(index=False))
    except Exception as e:
        result_parts.append(f"\n基本信息获取失败：{e}")

    result = "\n".join(result_parts) if result_parts else f"未能获取 {plain} 基本面数据"
    
    # 写入缓存
    loop.run_until_complete(_cache_set(cache_key, result, ttl=24 * 60 * 60))
    
    return result


def get_china_balance_sheet(symbol: str, freq: str = "quarterly", curr_date: Optional[str] = None) -> str:
    """获取资产负债表（带缓存）"""
    if is_etf(symbol):
        return "该标的为 ETF 基金，无传统公司财务报表数据。"
    
    bs_code, _ = _normalize_symbol(symbol)
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        data = loop.run_until_complete(_fetch_all_financial_data_async(bs_code))
        df = pd.DataFrame.from_dict(data["balance"])
        if df.empty:
            return f"未找到 {symbol} 资产负债表数据"
        header = f"# 资产负债表 {symbol}\n# BaoStock 单会话数据\n\n"
        return header + df.to_string(index=False)
    except Exception as e:
        return f"获取 {symbol} 资产负债表失败：{e}"


def get_china_income_statement(symbol: str, freq: str = "quarterly", curr_date: Optional[str] = None) -> str:
    """获取利润表（带缓存）"""
    if is_etf(symbol):
        return "该标的为 ETF 基金，无传统公司财务报表数据。"
    
    bs_code, _ = _normalize_symbol(symbol)
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        data = loop.run_until_complete(_fetch_all_financial_data_async(bs_code))
        df = pd.DataFrame.from_dict(data["income"])
        if df.empty:
            return f"未找到 {symbol} 利润表数据"
        header = f"# 利润表 {symbol}\n# BaoStock 单会话数据\n\n"
        return header + df.to_string(index=False)
    except Exception as e:
        return f"获取 {symbol} 利润表失败：{e}"


def get_china_cashflow(symbol: str, freq: str = "quarterly", curr_date: Optional[str] = None) -> str:
    """获取现金流量表（带缓存）"""
    if is_etf(symbol):
        return "该标的为 ETF 基金，无传统公司财务报表数据。"
    
    bs_code, _ = _normalize_symbol(symbol)
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        data = loop.run_until_complete(_fetch_all_financial_data_async(bs_code))
        df = pd.DataFrame.from_dict(data["cashflow"])
        if df.empty:
            return f"未找到 {symbol} 现金流量表数据"
        header = f"# 现金流量表 {symbol}\n# BaoStock 单会话数据\n\n"
        return header + df.to_string(index=False)
    except Exception as e:
        return f"获取 {symbol} 现金流量表失败：{e}"


# ── 新闻数据（带缓存）─────────────────────────────────────────────────

async def get_china_stock_news_async(
    symbol: str,
    curr_date: Optional[str] = None,
    look_back_days: int = 7,
) -> str:
    """异步版本：获取个股新闻 - 带缓存"""
    _, plain = _normalize_symbol(symbol)
    
    # 缓存键（新闻缓存时间较短）
    cache_key = f"news:{plain}:{curr_date}"
    
    # 尝试从缓存获取
    cached = await _cache_get(cache_key)
    if cached:
        sys_logger.info(f"✅ 新闻缓存命中：{symbol}")
        return cached
    
    try:
        df = ak.stock_news_em(symbol=plain)
        if df is None or df.empty:
            result = f"未找到 {plain} 的相关新闻"
        else:
            df = df.head(20)
            lines = [f"=== {plain} 最新新闻（{len(df)}条）==="]
            for _, row in df.iterrows():
                lines.append(
                    f"[{row.get('发布时间', '')}] {row.get('新闻标题', '')}\n"
                    f"  来源：{row.get('文章来源', '')}"
                )
            result = "\n".join(lines)
    except Exception as e:
        result = f"获取 {plain} 新闻失败：{e}"
    
    # 写入缓存（新闻缓存 2 小时）
    await _cache_set(cache_key, result, ttl=2 * 60 * 60)
    return result


def get_china_stock_news(
    symbol: str,
    curr_date: Optional[str] = None,
    look_back_days: int = 7,
) -> str:
    """同步版本：获取个股新闻 - 带缓存"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(get_china_stock_news_async(symbol, curr_date, look_back_days))


async def get_china_market_news_async(
    curr_date: Optional[str] = None,
    look_back_days: int = 7,
    limit: int = 20,
) -> str:
    """异步版本：获取 A 股市场快讯 - 带缓存"""
    cache_key = f"market_news:{curr_date}"
    
    # 尝试从缓存获取
    cached = await _cache_get(cache_key)
    if cached:
        sys_logger.info(f"✅ 市场新闻缓存命中")
        return cached
    
    try:
        df = ak.stock_news_main_cx()
        if df is None or df.empty:
            result = "暂无市场快讯"
        else:
            df = df.head(limit)
            lines = ["=== A 股市场最新快讯 ==="]
            for _, row in df.iterrows():
                tag = row.get("tag", "")
                summary = str(row.get("summary", row.get("内容", "")))[:120]
                lines.append(f"[{tag}] {summary}")
            result = "\n".join(lines)
    except Exception as e:
        result = f"获取市场快讯失败：{e}"
    
    # 写入缓存（市场新闻缓存 1 小时）
    await _cache_set(cache_key, result, ttl=1 * 60 * 60)
    return result


def get_china_market_news(
    curr_date: Optional[str] = None,
    look_back_days: int = 7,
    limit: int = 20,
) -> str:
    """同步版本：获取 A 股市场快讯 - 带缓存"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(get_china_market_news_async(curr_date, look_back_days, limit))
