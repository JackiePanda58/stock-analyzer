import requests
import time
import threading

BASE_URL = "http://127.0.0.1:8080"
TEST_CASES = [
    {"name": "1. 正常 ETF 测试", "payload": {"symbol": "510300", "parameters": {}, "user_context": {"risk": "low"}}},
    {"name": "2. 超长非法代码", "payload": {"symbol": "999999999999999"}},
    {"name": "3. 恶意 SQL 注入代码", "payload": {"symbol": "1' OR '1'='1"}},
    {"name": "4. 空参数请求", "payload": {}},
    {"name": "5. 缺少核心字段", "payload": {"parameters": {"test": 123}}},
    {"name": "6. 正常股票代码", "payload": {"symbol": "600519", "parameters": {"analysis_date": "2026-04-06"}}},
    {"name": "7. BaoStock 带小数点代码", "payload": {"symbol": "sh.600519"}},
    {"name": "8. 超长 user_context", "payload": {"symbol": "600519", "user_context": {"notes": "A" * 10000}}},
]

def get_token():
    try:
        res = requests.post(f"{BASE_URL}/api/v1/login", json={"username": "admin", "password": "admin123"}, timeout=10)
        res_json = res.json()
        return res_json.get("access_token") or res_json.get("data", {}).get("access_token")
    except Exception as e:
        return None

def run_test():
    token = get_token()
    if not token:
        print("❌ 无法获取测试 Token，登录接口或账号已失效！")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"🚀 开始 API 混沌测试 (目标: {BASE_URL}/api/analysis/single)")
    for i, case in enumerate(TEST_CASES):
        print(f"\n--- 执行测试: {case['name']} ---")
        try:
            res = requests.post(f"{BASE_URL}/api/analysis/single", json=case["payload"], headers=headers, timeout=30)
            print(f"返回状态码: {res.status_code}")
            if res.status_code == 500:
                print(f"🚨 触发了 500 崩溃！请检查 API 日志中的 Traceback。")
                try:
                    err = res.json()
                    print(f"响应: {err}")
                except:
                    print(f"响应文本: {res.text[:300]}")
            else:
                try:
                    result = res.json()
                    success = result.get("success")
                    status = result.get("data", {}).get("status", "N/A")
                    has_report = bool(result.get("data", {}).get("report"))
                    print(f"Success: {success} | Status: {status} | HasReport: {has_report}")
                except:
                    print(f"响应内容片段: {res.text[:200]}")
        except requests.exceptions.Timeout:
            print(f"⏱️ 请求超时（30s）")
        except Exception as e:
            print(f"网络请求异常: {e}")

if __name__ == "__main__":
    run_test()
