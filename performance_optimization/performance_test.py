#!/usr/bin/env python3
"""
性能对比测试脚本
测试优化前后的性能差异

使用方法:
    python3 performance_test.py
"""
import os
import sys
import time
import asyncio
from datetime import datetime

sys.path.insert(0, '/root/stock-analyzer')

# 使用系统 Python 环境（已有 langgraph, baostock 等）

from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
set_config(TRADING_CONFIG)

# ==================== 性能追踪 ====================

class PerformanceTracker:
    """性能追踪器"""
    
    def __init__(self):
        self.timings = {}
        self.llm_calls = []
        self.data_calls = []
        self.start_time = None
    
    def start(self):
        self.start_time = time.time()
    
    def record_llm_call(self, agent_name: str, elapsed: float):
        self.llm_calls.append({
            'agent': agent_name,
            'elapsed': elapsed,
            'timestamp': time.time() - self.start_time
        })
    
    def record_data_call(self, data_type: str, elapsed: float):
        self.data_calls.append({
            'type': data_type,
            'elapsed': elapsed,
            'timestamp': time.time() - self.start_time
        })
    
    def get_summary(self) -> dict:
        total_time = time.time() - self.start_time
        llm_total = sum(c['elapsed'] for c in self.llm_calls)
        data_total = sum(c['elapsed'] for c in self.data_calls)
        
        return {
            'total_time': total_time,
            'llm_total': llm_total,
            'llm_count': len(self.llm_calls),
            'llm_avg': llm_total / len(self.llm_calls) if self.llm_calls else 0,
            'data_total': data_total,
            'data_count': len(self.data_calls),
            'other_time': total_time - llm_total - data_total
        }


# ==================== 测试场景 ====================

def test_sequential_analysis():
    """测试顺序执行（基线）"""
    print("\n" + "="*60)
    print("测试 1: 顺序执行分析（基线）")
    print("="*60)
    
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    
    tracker = PerformanceTracker()
    tracker.start()
    
    print(f"\n开始分析：600519 | {time.strftime('%H:%M:%S')}")
    
    ta = TradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        debug=False,
        config=TRADING_CONFIG,
    )
    
    result, agent_logs = ta.propagate("600519", "2025-03-01")
    
    summary = tracker.get_summary()
    print(f"\n总耗时：{summary['total_time']:.1f}s")
    
    return summary


async def test_parallel_analysis():
    """测试并行执行（优化后）"""
    print("\n" + "="*60)
    print("测试 2: 并行执行分析（优化）")
    print("="*60)
    
    # TODO: 实现并行版本
    print("待实现：并行分析师节点")
    
    return None


async def test_cached_data_retrieval():
    """测试缓存数据获取"""
    print("\n" + "="*60)
    print("测试 3: 缓存数据获取（优化）")
    print("="*60)
    
    from tradingagents.dataflows.akshare_stock import (
        get_china_stock_data,
        get_china_stock_indicators,
        get_china_fundamentals,
    )
    
    tracker = PerformanceTracker()
    tracker.start()
    
    symbol = "600519"
    start_date = "2025-02-01"
    end_date = "2025-03-01"
    
    # 第一次调用（缓存未命中）
    print(f"\n第一次获取 {symbol} 数据（缓存未命中）...")
    t0 = time.time()
    data1 = get_china_stock_data(symbol, start_date, end_date)
    t1 = time.time()
    print(f"  耗时：{t1 - t0:.2f}s")
    tracker.record_data_call('stock_data', t1 - t0)
    
    # 第二次调用（缓存命中）
    print(f"第二次获取 {symbol} 数据（缓存命中）...")
    t0 = time.time()
    data2 = get_china_stock_data(symbol, start_date, end_date)
    t1 = time.time()
    print(f"  耗时：{t1 - t0:.2f}s")
    tracker.record_data_call('stock_data_cached', t1 - t0)
    
    # 技术指标
    print(f"\n获取技术指标（RSI）...")
    t0 = time.time()
    indicators = get_china_stock_indicators(symbol, "rsi", "2025-03-01", 30)
    t1 = time.time()
    print(f"  耗时：{t1 - t0:.2f}s")
    tracker.record_data_call('indicators', t1 - t0)
    
    # 基本面数据
    print(f"\n获取基本面数据...")
    t0 = time.time()
    fundamentals = get_china_fundamentals(symbol)
    t1 = time.time()
    print(f"  耗时：{t1 - t0:.2f}s")
    tracker.record_data_call('fundamentals', t1 - t0)
    
    summary = tracker.get_summary()
    print(f"\n数据获取总耗时：{summary['data_total']:.2f}s")
    print(f"调用次数：{summary['data_count']}")
    
    return summary


def test_baostock_connection():
    """测试 BaoStock 连接优化"""
    print("\n" + "="*60)
    print("测试 4: BaoStock 连接优化")
    print("="*60)
    
    import baostock as bs
    from tradingagents.dataflows.akshare_stock import _baostock_session, _bs_query_to_df
    
    # 测试单次会话多查询
    print("\n测试单次会话多查询...")
    t0 = time.time()
    
    with _baostock_session():
        # 查询历史行情
        rs1 = bs.query_history_k_data_plus(
            "sh.600519",
            "date,open,high,low,close",
            start_date="2025-02-01",
            end_date="2025-03-01",
            frequency="d",
            adjustflag="2",
        )
        df1 = _bs_query_to_df(rs1)
        
        # 查询财务数据
        rs2 = bs.query_balance_data(code="sh.600519", year="2024", quarter="3")
        df2 = _bs_query_to_df(rs2)
    
    elapsed = time.time() - t0
    print(f"  单次会话多查询耗时：{elapsed:.2f}s")
    print(f"  历史行情记录数：{len(df1)}")
    print(f"  财务数据记录数：{len(df2)}")
    
    return elapsed


# ==================== 主测试流程 ====================

def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Stock Analyzer 性能优化测试")
    print(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': {}
    }
    
    # 测试 1: 基线测试
    try:
        baseline = test_sequential_analysis()
        results['tests']['sequential'] = baseline
    except Exception as e:
        print(f"❌ 基线测试失败：{e}")
        results['tests']['sequential'] = {'error': str(e)}
    
    # 测试 2: 缓存数据获取
    try:
        cache_result = asyncio.run(test_cached_data_retrieval())
        results['tests']['cached_data'] = cache_result
    except Exception as e:
        print(f"❌ 缓存测试失败：{e}")
        results['tests']['cached_data'] = {'error': str(e)}
    
    # 测试 3: BaoStock 连接
    try:
        bs_time = test_baostock_connection()
        results['tests']['baostock'] = {'elapsed': bs_time}
    except Exception as e:
        print(f"❌ BaoStock 测试失败：{e}")
        results['tests']['baostock'] = {'error': str(e)}
    
    # 生成报告
    print("\n" + "="*60)
    print("性能测试报告")
    print("="*60)
    
    if 'sequential' in results['tests'] and 'error' not in results['tests']['sequential']:
        baseline_time = results['tests']['sequential']['total_time']
        print(f"\n基线耗时（顺序执行）: {baseline_time:.1f}s")
    
    if 'cached_data' in results['tests'] and 'error' not in results['tests']['cached_data']:
        cache_time = results['tests']['cached_data']['data_total']
        print(f"数据获取耗时（带缓存）: {cache_time:.1f}s")
        cache_hit_savings = results['tests']['cached_data']['data_total'] - \
                           sum(c['elapsed'] for c in 
                               [c for c in results['tests']['cached_data'].get('data_calls', []) 
                                if 'cached' in c.get('type', '')])
        print(f"缓存命中节省时间：{cache_hit_savings:.2f}s")
    
    if 'baostock' in results['tests'] and 'error' not in results['tests']['baostock']:
        print(f"BaoStock 单次会话耗时：{results['tests']['baostock']['elapsed']:.2f}s")
    
    # 保存结果
    import json
    report_path = '/root/stock-analyzer/performance_optimization/test_results.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n测试结果已保存至：{report_path}")
    
    return results


if __name__ == "__main__":
    run_all_tests()
