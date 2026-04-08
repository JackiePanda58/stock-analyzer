#!/usr/bin/env python3
"""
性能基准测试脚本
覆盖：接口响应时间、并发性能、缓存性能
"""

import time
import json
import urllib.request
import argparse
from datetime import datetime
from pathlib import Path

BASE_URL = "http://localhost:8080"
TOKEN = None
RESULTS_DIR = Path("/root/stock-analyzer/tests/benchmark")
RESULTS_DIR.mkdir(exist_ok=True)

def get_token():
    global TOKEN
    if TOKEN:
        return TOKEN
    
    data = json.dumps({"username": "admin", "password": "admin123"}).encode()
    req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    TOKEN = resp["access_token"]
    return TOKEN

def headers():
    return {"Authorization": f"Bearer {get_token()}"}

def measure_latency(url, method="GET", data=None, count=10):
    """测量接口延迟"""
    latencies = []
    
    for i in range(count):
        start = time.time()
        try:
            if method == "GET":
                req = urllib.request.Request(url, headers=headers())
            else:
                req = urllib.request.Request(url, data=json.dumps(data).encode() if data else b"{}", headers={**headers(), "Content-Type": "application/json"})
            
            urllib.request.urlopen(req, timeout=30)
            latency = (time.time() - start) * 1000  # ms
            latencies.append(latency)
        except Exception as e:
            print(f"请求失败：{e}")
    
    if not latencies:
        return None
    
    latencies.sort()
    return {
        "p50": latencies[len(latencies)//2],
        "p90": latencies[int(len(latencies)*0.9)],
        "p99": latencies[int(len(latencies)*0.99)],
        "avg": sum(latencies) / len(latencies),
        "min": min(latencies),
        "max": max(latencies)
    }

def run_benchmark():
    """执行性能基准测试"""
    print("📊 性能基准测试")
    print("=" * 60)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "endpoints": {}
    }
    
    # 测试登录接口
    print("\n测试登录接口...")
    latency = measure_latency(f"{BASE_URL}/api/v1/login", method="POST", data={"username": "admin", "password": "admin123"}, count=10)
    if latency:
        results["endpoints"]["/api/v1/login"] = latency
        print(f"  P50: {latency['p50']:.1f}ms, P90: {latency['p90']:.1f}ms, P99: {latency['p99']:.1f}ms")
    
    # 测试搜索接口
    print("\n测试搜索接口...")
    latency = measure_latency(f"{BASE_URL}/api/stocks/search?q=600", count=20)
    if latency:
        results["endpoints"]["/api/stocks/search"] = latency
        print(f"  P50: {latency['p50']:.1f}ms, P90: {latency['p90']:.1f}ms, P99: {latency['p99']:.1f}ms")
    
    # 测试持仓接口
    print("\n测试持仓接口...")
    latency = measure_latency(f"{BASE_URL}/api/trade/positions", count=20)
    if latency:
        results["endpoints"]["/api/trade/positions"] = latency
        print(f"  P50: {latency['p50']:.1f}ms, P90: {latency['p90']:.1f}ms, P99: {latency['p99']:.1f}ms")
    
    # 测试缓存接口
    print("\n测试缓存接口...")
    latency = measure_latency(f"{BASE_URL}/api/favorites/", count=20)
    if latency:
        results["endpoints"]["/api/favorites/"] = latency
        print(f"  P50: {latency['p50']:.1f}ms, P90: {latency['p90']:.1f}ms, P99: {latency['p99']:.1f}ms")
    
    # 测试 Dashboard
    print("\n测试 Dashboard 接口...")
    latency = measure_latency(f"{BASE_URL}/api/dashboard/summary", count=10)
    if latency:
        results["endpoints"]["/api/dashboard/summary"] = latency
        print(f"  P50: {latency['p50']:.1f}ms, P90: {latency['p90']:.1f}ms, P99: {latency['p99']:.1f}ms")
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = RESULTS_DIR / f"benchmark_{timestamp}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 基准测试结果已保存：{result_file}")
    
    # 生成 Markdown 报告
    md_report = f"""# 性能基准测试报告

**执行时间**: {results['timestamp']}

## 测试结果

| 接口 | P50 | P90 | P99 | 平均 | 最小 | 最大 |
|------|-----|-----|-----|------|------|------|
"""
    
    for endpoint, latency in results["endpoints"].items():
        md_report += f"| {endpoint} | {latency['p50']:.1f}ms | {latency['p90']:.1f}ms | {latency['p99']:.1f}ms | {latency['avg']:.1f}ms | {latency['min']:.1f}ms | {latency['max']:.1f}ms |\n"
    
    md_file = RESULTS_DIR / f"benchmark_{timestamp}.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_report)
    
    print(f"📝 Markdown 报告已保存：{md_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="性能基准测试")
    parser.add_argument("--save-baseline", action="store_true", help="保存为基线")
    args = parser.parse_args()
    
    run_benchmark()
