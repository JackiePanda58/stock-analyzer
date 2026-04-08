#!/usr/bin/env python3
"""
TradingAgents-CN UAT 自动化测试脚本
覆盖全项目所有功能的端到端测试
"""

import json
import urllib.request
import urllib.error
import time
import sys

BASE_URL = "http://localhost:8080"
TEST_RESULTS = []

class TestResult:
    def __init__(self, name):
        self.name = name
        self.success = False
        self.error = None
        self.details = {}
    
    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.name}"

def log_result(result):
    TEST_RESULTS.append(result)
    print(result)

# ==================== 用户认证模块 ====================

def test_auth_register():
    """UAT-AUTH-01: 新用户注册"""
    result = TestResult("UAT-AUTH-01: 新用户注册")
    try:
        data = json.dumps({"username": "uat_test_user", "password": "uat123456"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/users", data=data)
        req.add_header("Content-Type", "application/json")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = resp.get("success", False)
        result.details["response"] = resp
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_auth_login():
    """UAT-AUTH-02: 正常登录"""
    result = TestResult("UAT-AUTH-02: 正常登录")
    try:
        data = json.dumps({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data)
        req.add_header("Content-Type", "application/json")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = "access_token" in resp
        result.details["token"] = resp.get("access_token", "")[:50] + "..."
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_auth_wrong_password():
    """UAT-AUTH-03: 错误密码登录"""
    result = TestResult("UAT-AUTH-03: 错误密码登录")
    try:
        data = json.dumps({"username": "admin", "password": "wrong_password"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data)
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)
        result.success = False
        result.error = "应该失败但未失败"
    except urllib.error.HTTPError as e:
        result.success = e.code == 401
        result.details["status"] = e.code
    log_result(result)
    return result

def test_auth_sql_injection():
    """UAT-AUTH-11: SQL 注入防护"""
    result = TestResult("UAT-AUTH-11: SQL 注入防护")
    try:
        data = json.dumps({"username": "' OR '1'='1", "password": "anything"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data)
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)
        result.success = False
        result.error = "应该失败但未失败"
    except urllib.error.HTTPError as e:
        result.success = e.code in [401, 400]
        result.details["status"] = e.code
    log_result(result)
    return result

# ==================== 数据源模块 ====================

def test_datasource_a_share(token):
    """UAT-DS-01: A 股数据获取"""
    result = TestResult("UAT-DS-01: A 股数据获取")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/data/stock?code=600519")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        result.success = resp.get("success", False) or "data" in resp
        result.details["code"] = "600519"
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_datasource_etf(token):
    """UAT-DS-02: ETF 数据获取"""
    result = TestResult("UAT-DS-02: ETF 数据获取")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/data/stock?code=512170")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        result.success = resp.get("success", False) or "data" in resp
        result.details["code"] = "512170"
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_datasource_invalid_code(token):
    """UAT-DS-07: 无效代码处理"""
    result = TestResult("UAT-DS-07: 无效代码处理")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/data/stock?code=999999")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = not resp.get("success", True)
        result.details["response"] = resp
    except urllib.error.HTTPError as e:
        result.success = e.code in [400, 404]
        result.details["status"] = e.code
    log_result(result)
    return result

# ==================== 分析流程模块 ====================

def test_analysis_submit(token):
    """UAT-AN-01: 提交分析请求"""
    result = TestResult("UAT-AN-01: 提交分析请求")
    try:
        data = json.dumps({"symbol": "600519", "date": "2026-04-08"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/analyze", data=data)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        result.success = resp.get("success", False) or "task_id" in resp or "analysis_id" in resp
        result.details["response"] = resp
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_analysis_empty_code(token):
    """UAT-AN-12: 空代码处理"""
    result = TestResult("UAT-AN-12: 空代码处理")
    try:
        data = json.dumps({"symbol": "", "date": "2026-04-08"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/analyze", data=data)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)
        result.success = False
        result.error = "应该失败但未失败"
    except urllib.error.HTTPError as e:
        result.success = e.code in [400, 422]
        result.details["status"] = e.code
    log_result(result)
    return result

def test_analysis_history(token):
    """UAT-AN-14: 分析历史查询"""
    result = TestResult("UAT-AN-14: 分析历史查询")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/analysis/history")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = isinstance(resp.get("items", resp.get("data", [])), list)
        result.details["count"] = len(resp.get("items", resp.get("data", [])))
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_report_list(token):
    """UAT-AN-19: 报告列表"""
    result = TestResult("UAT-AN-19: 报告列表")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/analysis/list")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = isinstance(resp.get("items", resp.get("data", [])), list)
        result.details["count"] = len(resp.get("items", resp.get("data", [])))
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

# ==================== 搜索功能模块 ====================

def test_search_by_code(token):
    """UAT-SR-01: 股票代码搜索"""
    result = TestResult("UAT-SR-01: 股票代码搜索")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/search?q=600519")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = len(resp.get("results", resp.get("data", []))) > 0
        result.details["count"] = len(resp.get("results", resp.get("data", [])))
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_search_by_name(token):
    """UAT-SR-02: 股票名称搜索"""
    result = TestResult("UAT-SR-02: 股票名称搜索")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/search?q=茅台")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = len(resp.get("results", resp.get("data", []))) > 0
        result.details["count"] = len(resp.get("results", resp.get("data", [])))
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_search_xss(token):
    """UAT-SR-07: XSS 防护"""
    result = TestResult("UAT-SR-07: XSS 防护")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/search?q=<script>alert(1)</script>")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = "<script>" not in str(resp)
        result.details["sanitized"] = True
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

# ==================== 安全模块 ====================

def test_security_sql_injection_search(token):
    """UAT-SEC-02: SQL 注入 - 搜索"""
    result = TestResult("UAT-SEC-02: SQL 注入 - 搜索")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/search?q=' OR '1'='1")
        req.add_header("Authorization", f"Bearer {token}")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        result.success = "error" not in str(resp).lower() or resp.get("success", True)
        result.details["safe"] = True
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_security_cors():
    """UAT-SEC-06: CORS-合法域名"""
    result = TestResult("UAT-SEC-06: CORS-合法域名")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/health")
        req.add_header("Origin", "http://localhost:3000")
        resp = urllib.request.urlopen(req, timeout=10)
        cors_header = resp.headers.get("Access-Control-Allow-Origin", "")
        result.success = cors_header == "http://localhost:3000" or cors_header == "*"
        result.details["cors"] = cors_header
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_security_token_invalid():
    """UAT-SEC-10: Token 篡改"""
    result = TestResult("UAT-SEC-10: Token 篡改")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/v1/analyze")
        req.add_header("Authorization", "Bearer invalid_token_here")
        req.add_header("Content-Type", "application/json")
        data = json.dumps({"symbol": "600519"}).encode()
        req.data = data
        urllib.request.urlopen(req, timeout=10)
        result.success = False
        result.error = "应该失败但未失败"
    except urllib.error.HTTPError as e:
        result.success = e.code == 401
        result.details["status"] = e.code
    log_result(result)
    return result

# ==================== 性能模块 ====================

def test_performance_login():
    """UAT-PERF-01: 登录性能"""
    result = TestResult("UAT-PERF-01: 登录性能")
    try:
        start = time.time()
        data = json.dumps({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data)
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)
        elapsed = time.time() - start
        result.success = elapsed < 1.0
        result.details["time_ms"] = f"{elapsed*1000:.0f}ms"
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

def test_performance_search(token):
    """UAT-PERF-02: 搜索性能"""
    result = TestResult("UAT-PERF-02: 搜索性能")
    try:
        start = time.time()
        req = urllib.request.Request(f"{BASE_URL}/api/search?q=600519")
        req.add_header("Authorization", f"Bearer {token}")
        urllib.request.urlopen(req, timeout=10)
        elapsed = time.time() - start
        result.success = elapsed < 1.0
        result.details["time_ms"] = f"{elapsed*1000:.0f}ms"
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

# ==================== 健康检查 ====================

def test_health():
    """UAT-HEALTH-01: 后端健康检查"""
    result = TestResult("UAT-HEALTH-01: 后端健康检查")
    try:
        resp = json.loads(urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=10).read())
        result.success = resp.get("status") == "ok"
        result.details["response"] = resp
    except Exception as e:
        result.error = str(e)
    log_result(result)
    return result

# ==================== 主测试流程 ====================

def run_all_tests():
    """运行所有 UAT 测试"""
    print("=" * 60)
    print("TradingAgents-CN UAT 自动化测试")
    print("=" * 60)
    
    # 健康检查
    print("\n【健康检查】")
    test_health()
    
    # 用户认证
    print("\n【用户认证模块】")
    test_auth_register()
    login_result = test_auth_login()
    test_auth_wrong_password()
    test_auth_sql_injection()
    
    # 获取 Token
    token = login_result.details.get("token", "").replace("...", "")
    if not token:
        print("❌ 无法获取 Token，跳过后续测试")
        return
    
    # 数据源
    print("\n【数据源模块】")
    test_datasource_a_share(token)
    test_datasource_etf(token)
    test_datasource_invalid_code(token)
    
    # 分析流程
    print("\n【分析流程模块】")
    test_analysis_submit(token)
    test_analysis_empty_code(token)
    test_analysis_history(token)
    test_report_list(token)
    
    # 搜索功能
    print("\n【搜索功能模块】")
    test_search_by_code(token)
    test_search_by_name(token)
    test_search_xss(token)
    
    # 安全模块
    print("\n【安全模块】")
    test_security_sql_injection_search(token)
    test_security_cors()
    test_security_token_invalid()
    
    # 性能模块
    print("\n【性能模块】")
    test_performance_login()
    test_performance_search(token)
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for r in TEST_RESULTS if r.success)
    failed = sum(1 for r in TEST_RESULTS if not r.success)
    
    print(f"总测试数：{len(TEST_RESULTS)}")
    print(f"✅ 通过：{passed}")
    print(f"❌ 失败：{failed}")
    print(f"通过率：{passed/len(TEST_RESULTS)*100:.1f}%")
    
    if failed > 0:
        print("\n失败项:")
        for r in TEST_RESULTS:
            if not r.success:
                print(f"  ❌ {r.name}: {r.error}")
    
    return passed, failed

if __name__ == "__main__":
    run_all_tests()
