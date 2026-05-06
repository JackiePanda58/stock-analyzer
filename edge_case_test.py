"""
异常输入处理测试脚本

测试API对各种异常输入的处理能力

使用方法:
python3 edge_case_test.py --token YOUR_TOKEN --url http://localhost:8080
"""
import argparse
import json
import requests
from datetime import datetime


def test_case(name: str, token: str, base_url: str, payload: dict, expected_status: int = 200) -> dict:
    """
    执行单个测试用例
    
    参数:
        name: 测试用例名称
        token: JWT Token
        base_url: API基础URL
        payload: 请求体
        expected_status: 预期状态码
        
    返回:
        dict: 测试结果
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/analysis/single",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        success = response.status_code == expected_status
        return {
            "name": name,
            "status_code": response.status_code,
            "expected_status": expected_status,
            "success": success,
            "response": response.text[:200] if not success else "OK",
            "error": None
        }
    except Exception as e:
        return {
            "name": name,
            "status_code": 0,
            "expected_status": expected_status,
            "success": False,
            "response": None,
            "error": str(e)
        }


def run_edge_case_tests(token: str, base_url: str):
    """
    运行异常输入处理测试
    
    参数:
        token: JWT Token
        base_url: API基础URL
    """
    print("开始异常输入处理测试...")
    print()
    
    test_cases = [
        # 正常输入
        ("正常A股代码", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": 3, "market": "A股"}}, 200),
        
        # 异常股票代码
        ("空股票代码", {"symbol": "", "market": "A股", "parameters": {"research_depth": 3}}, 400),
        ("A股代码-位数不对", {"symbol": "00001", "market": "A股", "parameters": {"research_depth": 3}}, 400),
        ("A股代码-包含字母", {"symbol": "00000A", "market": "A股", "parameters": {"research_depth": 3}}, 400),
        ("港股代码-格式错误", {"symbol": "007", "market": "港股", "parameters": {"research_depth": 3}}, 200),
        ("美股代码-格式错误", {"symbol": "A", "market": "美股", "parameters": {"research_depth": 3}}, 200),
        
        # 异常深度参数
        ("深度-0", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": 0, "market": "A股"}}, 400),
        ("深度-6", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": 6, "market": "A股"}}, 400),
        ("深度-负数", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": -1, "market": "A股"}}, 400),
        ("深度-字符串", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": "标准", "market": "A股"}}, 400),
        ("深度-null", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": None, "market": "A股"}}, 200),
        
        # 异常市场类型
        ("市场类型-空", {"symbol": "159995", "market": "", "parameters": {"research_depth": 3}}, 200),
        ("市场类型-无效", {"symbol": "159995", "market": "invalid", "parameters": {"research_depth": 3}}, 200),
        
        # 异常日期
        ("日期-未来日期", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": 3, "market": "A股", "analysis_date": "2030-01-01"}}, 400),
        ("日期-格式错误", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": 3, "market": "A股", "analysis_date": "2026/04/29"}}, 200),
        
        # 异常分析师
        ("分析师-空列表", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": 3}, "selected_analysts": []}, 200),
        ("分析师-无效名称", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": 3}, "selected_analysts": ["invalid"]}, 200),
        
        # 缺失字段
        ("缺失symbol", {"market": "A股", "parameters": {"research_depth": 3}}, 400),
        ("缺失market", {"symbol": "159995", "parameters": {"research_depth": 3}}, 200),
        ("缺失parameters", {"symbol": "159995", "market": "A股"}, 200),
        
        # 额外字段
        ("额外字段", {"symbol": "159995", "market": "A股", "parameters": {"research_depth": 3}, "unknown_field": "test"}, 200),
    ]
    
    results = []
    for name, payload, expected_status in test_cases:
        print(f"  测试: {name}...", end=" ")
        result = test_case(name, token, base_url, payload, expected_status)
        results.append(result)
        print("✅ 通过" if result["success"] else "❌ 失败")
    
    # 统计结果
    success_count = sum(1 for r in results if r["success"])
    failed_count = len(results) - success_count
    
    print()
    print("=" * 50)
    print("异常输入处理测试结果:")
    print("=" * 50)
    print(f"  总测试数: {len(results)}")
    print(f"  通过数: {success_count}")
    print(f"  失败数: {failed_count}")
    print(f"  通过率: {success_count / len(results) * 100:.2f}%")
    print("=" * 50)
    
    # 保存结果
    result_data = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": success_count / len(results) * 100,
        "results": results
    }
    
    output_file = f"edge_case_test_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(result_data, f, indent=2)
    
    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="异常输入处理测试")
    parser.add_argument("--token", required=True, help="JWT Token")
    parser.add_argument("--url", default="http://localhost:8080", help="API基础URL")
    
    args = parser.parse_args()
    
    run_edge_case_tests(args.token, args.url)
