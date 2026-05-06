"""
API吞吐量压测脚本

使用方法:
python3 api_benchmark.py --token YOUR_TOKEN --concurrency 10 --requests 100
"""
import argparse
import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


def make_request(token: str, base_url: str, request_id: int) -> dict:
    """
    发送单个API请求
    
    参数:
        token: JWT Token
        base_url: API基础URL
        request_id: 请求ID
        
    返回:
        dict: 请求结果
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "symbol": "159995",
        "market": "A股",
        "parameters": {
            "research_depth": 1,
            "market": "A股"
        }
    }
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{base_url}/api/analysis/single",
            headers=headers,
            json=payload,
            timeout=30
        )
        elapsed = time.time() - start_time
        
        return {
            "request_id": request_id,
            "status_code": response.status_code,
            "elapsed": elapsed,
            "success": response.status_code == 200,
            "error": None
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "request_id": request_id,
            "status_code": 0,
            "elapsed": elapsed,
            "success": False,
            "error": str(e)
        }


def run_benchmark(token: str, base_url: str, concurrency: int, total_requests: int):
    """
    运行压测
    
    参数:
        token: JWT Token
        base_url: API基础URL
        concurrency: 并发数
        total_requests: 总请求数
    """
    print(f"开始压测...")
    print(f"  并发数: {concurrency}")
    print(f"  总请求数: {total_requests}")
    print(f"  目标URL: {base_url}/api/analysis/single")
    print()
    
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for i in range(total_requests):
            future = executor.submit(make_request, token, base_url, i + 1)
            futures.append(future)
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            # 每10个请求打印一次进度
            if len(results) % 10 == 0:
                print(f"  已完成: {len(results)}/{total_requests}")
    
    total_time = time.time() - start_time
    
    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    failed_count = total_requests - success_count
    avg_time = sum(r["elapsed"] for r in results) / len(results)
    min_time = min(r["elapsed"] for r in results)
    max_time = max(r["elapsed"] for r in results)
    qps = total_requests / total_time
    
    print()
    print("=" * 50)
    print("压测结果:")
    print("=" * 50)
    print(f"  总请求数: {total_requests}")
    print(f"  成功数: {success_count}")
    print(f"  失败数: {failed_count}")
    print(f"  成功率: {success_count / total_requests * 100:.2f}%")
    print()
    print(f"  总耗时: {total_time:.2f}秒")
    print(f"  QPS: {qps:.2f}")
    print()
    print(f"  平均响应时间: {avg_time * 1000:.2f}ms")
    print(f"  最小响应时间: {min_time * 1000:.2f}ms")
    print(f"  最大响应时间: {max_time * 1000:.2f}ms")
    print("=" * 50)
    
    # 保存结果
    result_data = {
        "timestamp": datetime.now().isoformat(),
        "concurrency": concurrency,
        "total_requests": total_requests,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": success_count / total_requests * 100,
        "total_time": total_time,
        "qps": qps,
        "avg_time_ms": avg_time * 1000,
        "min_time_ms": min_time * 1000,
        "max_time_ms": max_time * 1000,
        "results": results
    }
    
    output_file = f"benchmark_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(result_data, f, indent=2)
    
    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API吞吐量压测")
    parser.add_argument("--token", required=True, help="JWT Token")
    parser.add_argument("--url", default="http://localhost:8080", help="API基础URL")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数")
    parser.add_argument("--requests", type=int, default=100, help="总请求数")
    
    args = parser.parse_args()
    
    run_benchmark(args.token, args.url, args.concurrency, args.requests)
