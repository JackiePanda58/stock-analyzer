#!/usr/bin/env python3
"""
API 性能基准测试脚本

测试各 API 端点的响应时间、并发性能和资源使用情况。
"""

import requests
import time
import json
import statistics
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Any
import os

# ==================== 配置 ====================

BASE_URL = "http://localhost:8080"
TEST_USERNAME = "admin"
TEST_PASSWORD = "admin123"
RESULTS_DIR = "/root/stock-analyzer/reports/benchmarks"

# 测试配置
WARMUP_REQUESTS = 3
NORMAL_REQUESTS = 10
CONCURRENT_USERS = [1, 5, 10, 20]
TIMEOUT_SECONDS = 120

# ==================== 工具函数 ====================

def get_token() -> str:
    """获取测试 Token"""
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        timeout=10
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"登录失败：{response.status_code}")


def make_request(endpoint: str, method: str = "GET", headers: Dict = None, json_data: Dict = None) -> tuple:
    """发送请求并返回 (状态码，响应时间，响应大小)"""
    url = f"{BASE_URL}{endpoint}"
    start_time = time.time()
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=json_data, timeout=TIMEOUT_SECONDS)
        else:
            raise ValueError(f"不支持的方法：{method}")
        
        elapsed = time.time() - start_time
        return response.status_code, elapsed, len(response.content)
    
    except requests.exceptions.Timeout:
        return 0, TIMEOUT_SECONDS, 0
    except requests.exceptions.RequestException as e:
        return 0, time.time() - start_time, 0


def warmup(endpoint: str, method: str = "GET", headers: Dict = None, json_data: Dict = None):
    """预热请求"""
    print(f"  预热：{endpoint}")
    for i in range(WARMUP_REQUESTS):
        make_request(endpoint, method, headers, json_data)
        time.sleep(0.5)


# ==================== 基准测试 ====================

def test_single_endpoint(name: str, endpoint: str, method: str = "GET", headers: Dict = None, json_data: Dict = None) -> Dict:
    """测试单个端点的性能"""
    print(f"\n测试：{name}")
    print(f"  端点：{endpoint}")
    
    # 预热
    warmup(endpoint, method, headers, json_data)
    
    # 执行测试
    latencies = []
    status_codes = []
    sizes = []
    
    for i in range(NORMAL_REQUESTS):
        status, latency, size = make_request(endpoint, method, headers, json_data)
        latencies.append(latency)
        status_codes.append(status)
        sizes.append(size)
        
        # 避免过快请求
        if i < NORMAL_REQUESTS - 1:
            time.sleep(0.5)
    
    # 计算统计
    success_count = sum(1 for s in status_codes if 200 <= s < 300)
    
    results = {
        "name": name,
        "endpoint": endpoint,
        "method": method,
        "total_requests": NORMAL_REQUESTS,
        "successful_requests": success_count,
        "success_rate": success_count / NORMAL_REQUESTS * 100,
        "latency": {
            "min": min(latencies) * 1000,  # 转换为毫秒
            "max": max(latencies) * 1000,
            "avg": statistics.mean(latencies) * 1000,
            "median": statistics.median(latencies) * 1000,
            "p95": sorted(latencies)[int(NORMAL_REQUESTS * 0.95)] * 1000 if NORMAL_REQUESTS > 1 else 0,
            "p99": sorted(latencies)[int(NORMAL_REQUESTS * 0.99)] * 1000 if NORMAL_REQUESTS > 1 else 0,
        },
        "response_size": {
            "avg": statistics.mean(sizes) if sizes else 0,
            "max": max(sizes) if sizes else 0,
        }
    }
    
    print(f"  成功率：{results['success_rate']:.1f}%")
    print(f"  平均延迟：{results['latency']['avg']:.2f}ms")
    print(f"  P95 延迟：{results['latency']['p95']:.2f}ms")
    
    return results


def test_concurrent_load(name: str, endpoint: str, method: str = "GET", headers: Dict = None, json_data: Dict = None) -> Dict:
    """测试并发负载"""
    print(f"\n并发测试：{name}")
    
    results = {
        "name": name,
        "endpoint": endpoint,
        "concurrent_tests": []
    }
    
    for concurrent_users in CONCURRENT_USERS:
        print(f"  并发用户数：{concurrent_users}")
        
        def worker():
            return make_request(endpoint, method, headers, json_data)
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(worker) for _ in range(concurrent_users * 5)]
            responses = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        latencies = [r[1] for r in responses]
        success_count = sum(1 for r in responses if 200 <= r[0] < 300)
        
        test_result = {
            "concurrent_users": concurrent_users,
            "total_requests": len(responses),
            "successful_requests": success_count,
            "total_time_seconds": total_time,
            "requests_per_second": len(responses) / total_time,
            "avg_latency_ms": statistics.mean(latencies) * 1000,
            "min_latency_ms": min(latencies) * 1000,
            "max_latency_ms": max(latencies) * 1000,
        }
        
        results["concurrent_tests"].append(test_result)
        
        print(f"    QPS: {test_result['requests_per_second']:.2f}")
        print(f"    平均延迟：{test_result['avg_latency_ms']:.2f}ms")
    
    return results


def test_resource_usage() -> Dict:
    """测试资源使用情况"""
    print("\n资源使用情况:")
    
    # CPU 使用率
    cpu_result = os.popen("top -bn1 | grep 'Cpu(s)'").read()
    cpu_usage = cpu_result.split()[1] if cpu_result else "N/A"
    
    # 内存使用率
    mem_result = os.popen("free | grep Mem").read()
    if mem_result:
        parts = mem_result.split()
        mem_usage = f"{float(parts[2])/float(parts[1])*100:.1f}%"
    else:
        mem_usage = "N/A"
    
    # 磁盘使用率
    disk_result = os.popen("df -h / | tail -1").read()
    disk_usage = disk_result.split()[4] if disk_result else "N/A"
    
    # 进程数
    process_count = os.popen("ps aux | wc -l").read().strip()
    
    return {
        "cpu_usage": cpu_usage,
        "memory_usage": mem_usage,
        "disk_usage": disk_usage,
        "process_count": int(process_count)
    }


# ==================== 主测试流程 ====================

def run_benchmarks():
    """运行所有基准测试"""
    print("=" * 60)
    print("TradingAgents API 性能基准测试")
    print("=" * 60)
    print(f"开始时间：{datetime.now().isoformat()}")
    print(f"目标 URL: {BASE_URL}")
    
    # 获取 Token
    print("\n获取测试 Token...")
    try:
        token = get_token()
        auth_headers = {"Authorization": f"Bearer {token}"}
        print("✓ Token 获取成功")
    except Exception as e:
        print(f"✗ Token 获取失败：{e}")
        return None
    
    # 测试端点列表
    endpoints = [
        {
            "name": "健康检查",
            "endpoint": "/api/health",
            "method": "GET"
        },
        {
            "name": "系统信息",
            "endpoint": "/api/system/info",
            "method": "GET",
            "headers": auth_headers
        },
        {
            "name": "获取收藏列表",
            "endpoint": "/api/favorites/",
            "method": "GET",
            "headers": auth_headers
        },
        # 分析接口测试（保守测试，避免过载）
        # {
        #     "name": "股票分析",
        #     "endpoint": "/api/v1/analyze",
        #     "method": "POST",
        #     "headers": auth_headers,
        #     "json_data": {"symbol": "600519"}
        # }
    ]
    
    # 执行单端点测试
    single_results = []
    for ep in endpoints:
        result = test_single_endpoint(
            ep["name"],
            ep["endpoint"],
            ep["method"],
            ep.get("headers"),
            ep.get("json_data")
        )
        single_results.append(result)
    
    # 执行并发测试（仅针对轻量接口）
    concurrent_results = []
    for ep in endpoints[:2]:  # 只测试前两个轻量接口
        result = test_concurrent_load(
            ep["name"],
            ep["endpoint"],
            ep["method"],
            ep.get("headers"),
            ep.get("json_data")
        )
        concurrent_results.append(result)
    
    # 资源使用情况
    resource_usage = test_resource_usage()
    
    # 生成报告
    report = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "test_config": {
                "warmup_requests": WARMUP_REQUESTS,
                "normal_requests": NORMAL_REQUESTS,
                "concurrent_users": CONCURRENT_USERS,
                "timeout_seconds": TIMEOUT_SECONDS
            }
        },
        "single_endpoint_tests": single_results,
        "concurrent_load_tests": concurrent_results,
        "resource_usage": resource_usage,
        "summary": {
            "total_endpoints_tested": len(single_results),
            "average_latency_ms": statistics.mean([r["latency"]["avg"] for r in single_results]),
            "overall_success_rate": statistics.mean([r["success_rate"] for r in single_results])
        }
    }
    
    # 保存报告
    os.makedirs(RESULTS_DIR, exist_ok=True)
    report_file = f"{RESULTS_DIR}/benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print(f"测试完成！报告已保存：{report_file}")
    print("=" * 60)
    
    # 打印摘要
    print("\n性能摘要:")
    print(f"  测试端点数：{len(single_results)}")
    print(f"  平均延迟：{report['summary']['average_latency_ms']:.2f}ms")
    print(f"  平均成功率：{report['summary']['overall_success_rate']:.1f}%")
    print(f"\n资源使用:")
    print(f"  CPU: {resource_usage['cpu_usage']}")
    print(f"  内存：{resource_usage['memory_usage']}")
    print(f"  磁盘：{resource_usage['disk_usage']}")
    
    return report


if __name__ == "__main__":
    run_benchmarks()
