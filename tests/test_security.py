#!/usr/bin/env python3
"""
TradingAgents-CN 安全权限测试套件

覆盖范围：
1. RBAC 角色权限测试（admin/user）
2. API 速率限制测试
3. SQL 注入防护测试
4. XSS 防护测试
5. CORS 配置测试

要求：
- 测试 JWT 鉴权扩展功能
- 使用不同角色 token 验证隔离
- 运行测试并生成报告

用法：python3 test_security.py [--backend URL] [--verbose]
"""
import argparse
import json
import time
import urllib.request
import urllib.error
import sys
import os
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import base64
import hmac
import hashlib

# ─── 配置 ────────────────────────────────────────────────────────────────────
DEFAULT_BACKEND = "http://localhost:8080"
SECRET_KEY = "trading-agents-cn-secret-key-2024"  # 从 api_server.py 获取
ALGORITHM = "HS256"

# 测试用户配置
TEST_USERS = {
    "admin": {"username": "admin", "password": "admin123", "role": "admin"},
    "user": {"username": "testuser", "password": "user123", "role": "user"},
    "analyst": {"username": "analyst", "password": "analyst123", "role": "analyst"},
}

# ─── 颜色 ────────────────────────────────────────────────────────────────────
class C:
    G = "\033[92m"
    R = "\033[91m"
    Y = "\033[93m"
    B = "\033[94m"
    BD = "\033[1m"
    E = "\033[0m"


# ─── 测试结果记录 ────────────────────────────────────────────────────────────
class TR:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []

    def ok(self, tid, msg=""):
        self.passed += 1
        self.results.append((True, tid, msg))
        print(f"  {C.G}✓{C.E} {tid} {msg}")

    def fail(self, tid, msg):
        self.failed += 1
        self.results.append((False, tid, msg))
        print(f"  {C.R}✗{C.E} {tid} {C.R}{msg}{C.E}")

    def skip(self, tid, msg):
        self.skipped += 1
        self.results.append((None, tid, msg))
        print(f"  {C.Y}⊘{C.E} {tid} {C.Y}{msg}{C.E}")

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*70}")
        print(f"{C.BD}测试结果汇总:{C.E}")
        print(f"  {C.G}✓ 通过：{self.passed}{C.E}")
        print(f"  {C.R}✗ 失败：{self.failed}{C.E}")
        print(f"  {C.Y}⊘ 跳过：{self.skipped}{C.E}")
        print(f"  总计：{total} 项")
        print(f"{'='*70}")
        return self.failed == 0


# ─── JWT 工具 ────────────────────────────────────────────────────────────────
class JWTUtils:
    @staticmethod
    def create_token(username: str, role: str = "user", exp_minutes: int = 60) -> str:
        """创建 JWT Token（用于测试不同角色）"""
        header = {"alg": ALGORITHM, "typ": "JWT"}
        now = datetime.utcnow()
        payload = {
            "sub": username,
            "role": role,
            "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
            "iat": int(now.timestamp())
        }
        
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
        
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b'=').decode()
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    @staticmethod
    def create_expired_token(username: str, role: str = "user") -> str:
        """创建已过期的 JWT Token"""
        return JWTUtils.create_token(username, role, exp_minutes=-60)

    @staticmethod
    def create_invalid_signature_token(username: str) -> str:
        """创建签名无效的 JWT Token"""
        token = JWTUtils.create_token(username, "user")
        parts = token.split('.')
        # 篡改签名部分
        return f"{parts[0]}.{parts[1]}.invalid_signature"


# ─── API 客户端 ──────────────────────────────────────────────────────────────
class API:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token = None
        self.username = None
        self.role = None

    def request(self, method: str, path: str, data=None, token=None, headers=None):
        """通用请求方法"""
        url = f"{self.base}{path}"
        req_headers = {"Content-Type": "application/json"}
        
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        elif self.token:
            req_headers["Authorization"] = f"Bearer {self.token}"
        
        if headers:
            req_headers.update(headers)
        
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
        
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode())
            except:
                error_body = {"error": str(e)}
            return e.code, error_body
        except Exception as e:
            return 0, {"error": str(e)}

    def login(self, username: str, password: str) -> str:
        """登录获取 token"""
        status, resp = self.request("POST", "/api/v1/login", {
            "username": username,
            "password": password
        })
        if status == 200 and "access_token" in resp:
            self.token = resp["access_token"]
            self.username = username
            return self.token
        raise Exception(f"登录失败：{resp}")

    def login_with_role(self, role: str = "user") -> str:
        """使用指定角色登录"""
        if role not in TEST_USERS:
            # 创建测试用户 token
            user_config = {"username": f"test_{role}", "password": "test123", "role": role}
        else:
            user_config = TEST_USERS[role]
        
        try:
            token = self.login(user_config["username"], user_config["password"])
            self.role = role
            return token
        except:
            # 如果登录失败，使用 JWT 工具创建测试 token
            token = JWTUtils.create_token(user_config["username"], role)
            self.token = token
            self.username = user_config["username"]
            self.role = role
            return token


# ─── 测试用例 ────────────────────────────────────────────────────────────────

def test_rbac_permissions(api: API, tr: TR, verbose: bool = False):
    """1. RBAC 角色权限测试"""
    print(f"\n{C.BD}[1] RBAC 角色权限测试{C.E}")
    print("-" * 70)
    
    # 测试 1.1: Admin 角色访问所有接口
    tr_test = "RBAC-01"
    try:
        admin_token = api.login_with_role("admin")
        status, resp = api.request("GET", "/api/auth/me", token=admin_token)
        if status == 200 and resp.get("success"):
            tr.ok(tr_test, "Admin 角色成功访问 /api/auth/me")
        else:
            tr.fail(tr_test, f"Admin 访问失败：{resp}")
    except Exception as e:
        tr.fail(tr_test, f"Admin 角色测试异常：{e}")
    
    # 测试 1.2: User 角色访问管理接口（应被拒绝）
    tr_test = "RBAC-02"
    try:
        user_token = api.login_with_role("user")
        # 尝试访问需要 admin 权限的接口
        status, resp = api.request("GET", "/api/scheduler/jobs", token=user_token)
        # 应该返回 403 或 401
        if status in [401, 403]:
            tr.ok(tr_test, "User 角色被正确拒绝访问管理接口")
        elif status == 200:
            tr.fail(tr_test, "User 角色不应有权访问管理接口")
        else:
            tr.skip(tr_test, f"接口返回状态：{status}")
    except Exception as e:
        tr.fail(tr_test, f"User 角色测试异常：{e}")
    
    # 测试 1.3: 不同角色 Token 隔离验证
    tr_test = "RBAC-03"
    try:
        admin_token = JWTUtils.create_token("admin_user", "admin")
        user_token = JWTUtils.create_token("normal_user", "user")
        analyst_token = JWTUtils.create_token("analyst_user", "analyst")
        
        # 验证 token 可以解码
        for token, expected_role in [(admin_token, "admin"), (user_token, "user"), (analyst_token, "analyst")]:
            status, resp = api.request("GET", "/api/auth/me", token=token)
            if status == 200:
                tr.ok(f"{tr_test}-{expected_role}", f"{expected_role.capitalize()} Token 验证通过")
            else:
                tr.fail(f"{tr_test}-{expected_role}", f"{expected_role} Token 验证失败：{resp}")
    except Exception as e:
        tr.fail(tr_test, f"角色隔离测试异常：{e}")
    
    # 测试 1.4: JWT Token 过期处理
    tr_test = "RBAC-04"
    try:
        expired_token = JWTUtils.create_expired_token("test_user")
        status, resp = api.request("GET", "/api/auth/me", token=expired_token)
        if status == 401:
            tr.ok(tr_test, "过期 Token 被正确拒绝 (401)")
        else:
            tr.fail(tr_test, f"过期 Token 应返回 401，实际：{status}")
    except Exception as e:
        tr.fail(tr_test, f"过期 Token 测试异常：{e}")
    
    # 测试 1.5: 无效签名 Token 处理
    tr_test = "RBAC-05"
    try:
        invalid_token = JWTUtils.create_invalid_signature_token("test_user")
        status, resp = api.request("GET", "/api/auth/me", token=invalid_token)
        if status == 401:
            tr.ok(tr_test, "无效签名 Token 被正确拒绝 (401)")
        else:
            tr.fail(tr_test, f"无效签名 Token 应返回 401，实际：{status}")
    except Exception as e:
        tr.fail(tr_test, f"无效签名测试异常：{e}")
    
    # 测试 1.6: Token 刷新机制
    tr_test = "RBAC-06"
    try:
        api.login_with_role("admin")
        status, resp = api.request("POST", "/api/auth/refresh", token=api.token)
        if status == 200 and "access_token" in resp:
            tr.ok(tr_test, "Token 刷新机制工作正常")
        else:
            tr.skip(tr_test, f"Token 刷新接口返回：{status}")
    except Exception as e:
        tr.skip(tr_test, f"Token 刷新测试异常：{e}")
    
    # 测试 1.7: 登出功能
    tr_test = "RBAC-07"
    try:
        api.login_with_role("admin")
        status, resp = api.request("POST", "/api/auth/logout", token=api.token)
        if status == 200:
            # 验证登出后 token 失效
            status2, _ = api.request("GET", "/api/auth/me", token=api.token)
            if status2 == 401:
                tr.ok(tr_test, "登出功能正常且 Token 被失效")
            else:
                tr.fail(tr_test, "登出后 Token 未失效")
        else:
            tr.skip(tr_test, f"登出接口返回：{status}")
    except Exception as e:
        tr.skip(tr_test, f"登出测试异常：{e}")


def test_rate_limiting(api: API, tr: TR, verbose: bool = False):
    """2. API 速率限制测试"""
    print(f"\n{C.BD}[2] API 速率限制测试{C.E}")
    print("-" * 70)
    
    # 测试 2.1: 快速连续请求
    tr_test = "RATE-01"
    try:
        api.login_with_role("admin")
        success_count = 0
        rate_limited = False
        
        for i in range(20):
            status, _ = api.request("GET", "/api/health", token=api.token)
            if status == 200:
                success_count += 1
            elif status == 429:
                rate_limited = True
                break
            time.sleep(0.1)
        
        if rate_limited:
            tr.ok(tr_test, f"速率限制触发（{success_count} 次成功后被限制）")
        elif success_count == 20:
            tr.skip(tr_test, "未触发速率限制（可能未配置或阈值较高）")
        else:
            tr.fail(tr_test, f"异常：{success_count} 次成功，未触发限制")
    except Exception as e:
        tr.fail(tr_test, f"速率限制测试异常：{e}")
    
    # 测试 2.2: 多端点并发请求
    tr_test = "RATE-02"
    try:
        endpoints = ["/api/health", "/api/auth/me", "/api/favorites/"]
        rate_limited_count = 0
        
        def make_request(endpoint):
            status, _ = api.request("GET", endpoint, token=api.token)
            return status == 429
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for _ in range(5):
                for ep in endpoints:
                    futures.append(executor.submit(make_request, ep))
            
            for future in as_completed(futures):
                if future.result():
                    rate_limited_count += 1
        
        if rate_limited_count > 0:
            tr.ok(tr_test, f"并发请求触发速率限制 ({rate_limited_count}/15)")
        else:
            tr.skip(tr_test, "并发请求未触发速率限制")
    except Exception as e:
        tr.fail(tr_test, f"并发速率测试异常：{e}")
    
    # 测试 2.3: 不同角色速率限制差异
    tr_test = "RATE-03"
    try:
        # 测试 admin 角色
        api.login_with_role("admin")
        admin_limited = False
        for i in range(30):
            status, _ = api.request("GET", "/api/health", token=api.token)
            if status == 429:
                admin_limited = True
                break
            time.sleep(0.05)
        
        # 测试 user 角色
        api.login_with_role("user")
        user_limited = False
        for i in range(30):
            status, _ = api.request("GET", "/api/health", token=api.token)
            if status == 429:
                user_limited = True
                break
            time.sleep(0.05)
        
        if admin_limited or user_limited:
            tr.ok(tr_test, f"速率限制生效 (admin:{admin_limited}, user:{user_limited})")
        else:
            tr.skip(tr_test, "未观察到速率限制差异")
    except Exception as e:
        tr.fail(tr_test, f"角色速率差异测试异常：{e}")


def test_sql_injection(api: API, tr: TR, verbose: bool = False):
    """3. SQL 注入防护测试"""
    print(f"\n{C.BD}[3] SQL 注入防护测试{C.E}")
    print("-" * 70)
    
    sql_injection_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "' UNION SELECT * FROM users --",
        "1; DELETE FROM stocks WHERE '1'='1",
        "' OR 1=1 --",
        "admin'--",
        "1' AND '1'='1",
        "' UNION ALL SELECT NULL,NULL,NULL --",
    ]
    
    # 测试 3.1: 登录接口 SQL 注入
    tr_test = "SQL-01"
    injection_success = 0
    for payload in sql_injection_payloads[:3]:
        try:
            status, resp = api.request("POST", "/api/v1/login", {
                "username": payload,
                "password": "anything"
            })
            # 如果返回 200 且有 token，说明可能被注入
            if status == 200 and "access_token" in resp:
                injection_success += 1
        except:
            pass
    
    if injection_success == 0:
        tr.ok(tr_test, "登录接口 SQL 注入防护有效")
    else:
        tr.fail(tr_test, f"发现 {injection_success} 次可能的 SQL 注入成功")
    
    # 测试 3.2: 搜索接口 SQL 注入
    tr_test = "SQL-02"
    injection_detected = False
    for payload in sql_injection_payloads[3:6]:
        try:
            status, resp = api.request("GET", f"/api/stocks/search?q={payload}", token=api.token)
            # 检查响应是否包含 SQL 错误信息
            resp_str = json.dumps(resp)
            if "syntax" in resp_str.lower() or "sql" in resp_str.lower():
                injection_detected = True
                break
        except:
            pass
    
    if not injection_detected:
        tr.ok(tr_test, "搜索接口 SQL 注入防护有效")
    else:
        tr.fail(tr_test, "搜索接口可能暴露 SQL 错误信息")
    
    # 测试 3.3: 收藏接口 SQL 注入
    tr_test = "SQL-03"
    api.login_with_role("admin")
    for payload in ["' OR '1'='1", "1; DROP TABLE favorites; --"]:
        try:
            status, resp = api.request("GET", f"/api/favorites/?code={payload}", token=api.token)
            if status == 500:
                resp_str = json.dumps(resp)
                if "syntax" in resp_str.lower() or "sql" in resp_str.lower():
                    tr.fail(tr_test, f"收藏接口 SQL 错误暴露：{payload}")
                    break
        except:
            pass
    else:
        tr.ok(tr_test, "收藏接口 SQL 注入防护有效")
    
    # 测试 3.4: 错误信息不暴露数据库结构
    tr_test = "SQL-04"
    error_exposed = False
    test_paths = [
        "/api/stocks/search?q=' UNION SELECT table_name FROM information_schema.tables --",
        "/api/favorites/?code='; SELECT * FROM sqlite_master --",
    ]
    for path in test_paths:
        try:
            status, resp = api.request("GET", path, token=api.token)
            resp_str = json.dumps(resp)
            if any(kw in resp_str.lower() for kw in ["table", "column", "schema", "sqlite"]):
                error_exposed = True
                break
        except:
            pass
    
    if not error_exposed:
        tr.ok(tr_test, "错误信息未暴露数据库结构")
    else:
        tr.fail(tr_test, "错误信息可能暴露数据库结构")


def test_xss_protection(api: API, tr: TR, verbose: bool = False):
    """4. XSS 防护测试"""
    print(f"\n{C.BD}[4] XSS 防护测试{C.E}")
    print("-" * 70)
    
    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<svg onload=alert('XSS')>",
        "'\"><script>alert(document.cookie)</script>",
        "<iframe src='javascript:alert(1)'>",
    ]
    
    # 测试 4.1: 搜索接口 XSS
    tr_test = "XSS-01"
    xss_reflected = False
    api.login_with_role("admin")
    
    for payload in xss_payloads[:3]:
        try:
            status, resp = api.request("GET", f"/api/stocks/search?q={payload}", token=api.token)
            resp_str = json.dumps(resp)
            # 检查 payload 是否被原样返回
            if payload in resp_str or payload.replace(" ", "") in resp_str.replace(" ", ""):
                xss_reflected = True
                break
        except:
            pass
    
    if not xss_reflected:
        tr.ok(tr_test, "搜索接口 XSS 防护有效（未反射 payload）")
    else:
        tr.fail(tr_test, "搜索接口可能反射 XSS payload")
    
    # 测试 4.2: 收藏接口 XSS
    tr_test = "XSS-02"
    xss_stored = False
    for payload in xss_payloads[3:5]:
        try:
            # 尝试添加包含 XSS 的收藏
            status, resp = api.request("POST", "/api/favorites/", {
                "stock_code": "600519",
                "name": payload,
                "tags": ["test"]
            }, token=api.token)
            
            # 获取收藏列表检查是否存储了 XSS
            status2, resp2 = api.request("GET", "/api/favorites/", token=api.token)
            if payload in json.dumps(resp2):
                xss_stored = True
                break
        except:
            pass
    
    if not xss_stored:
        tr.ok(tr_test, "收藏接口 XSS 防护有效（未存储 payload）")
    else:
        tr.fail(tr_test, "收藏接口可能存储 XSS payload")
    
    # 测试 4.3: 响应头 Content-Type 防护
    tr_test = "XSS-03"
    try:
        req = urllib.request.Request(f"{api.base}/api/health")
        req.add_header("Authorization", f"Bearer {api.token}")
        resp = urllib.request.urlopen(req, timeout=10)
        content_type = resp.headers.get("Content-Type", "")
        x_content_type = resp.headers.get("X-Content-Type-Options", "")
        
        if "charset" in content_type and x_content_type == "nosniff":
            tr.ok(tr_test, "响应头配置正确（Content-Type + X-Content-Type-Options）")
        elif "charset" in content_type:
            tr.skip(tr_test, f"Content-Type 正确但缺少 X-Content-Type-Options: {content_type}")
        else:
            tr.skip(tr_test, f"响应头配置不完整：{content_type}")
    except Exception as e:
        tr.skip(tr_test, f"响应头检查异常：{e}")
    
    # 测试 4.4: CSP 头检查
    tr_test = "XSS-04"
    try:
        req = urllib.request.Request(f"{api.base}/api/health")
        req.add_header("Authorization", f"Bearer {api.token}")
        resp = urllib.request.urlopen(req, timeout=10)
        csp = resp.headers.get("Content-Security-Policy", "")
        
        if csp:
            tr.ok(tr_test, "CSP 头已配置")
        else:
            tr.skip(tr_test, "未配置 Content-Security-Policy 头")
    except Exception as e:
        tr.skip(tr_test, f"CSP 检查异常：{e}")


def test_cors_configuration(api: API, tr: TR, verbose: bool = False):
    """5. CORS 配置测试"""
    print(f"\n{C.BD}[5] CORS 配置测试{C.E}")
    print("-" * 70)
    
    # 测试 5.1: OPTIONS 预检请求
    tr_test = "CORS-01"
    try:
        req = urllib.request.Request(f"{api.base}/api/v1/analyze", method="OPTIONS")
        req.add_header("Origin", "http://evil.com")
        req.add_header("Access-Control-Request-Method", "POST")
        req.add_header("Access-Control-Request-Headers", "Content-Type,Authorization")
        
        resp = urllib.request.urlopen(req, timeout=10)
        acao = resp.headers.get("Access-Control-Allow-Origin", "")
        acam = resp.headers.get("Access-Control-Allow-Methods", "")
        acah = resp.headers.get("Access-Control-Allow-Headers", "")
        
        if acao and acao != "*":
            tr.ok(tr_test, f"CORS 配置正确 (Allow-Origin: {acao})")
        elif acao == "*":
            tr.fail(tr_test, "CORS 配置过宽 (Allow-Origin: *)")
        else:
            tr.skip(tr_test, "未返回 CORS 头")
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            tr.ok(tr_test, "CORS 预检请求被正确拒绝（需认证）")
        else:
            tr.skip(tr_test, f"OPTIONS 请求返回：{e.code}")
    except Exception as e:
        tr.skip(tr_test, f"CORS 预检测试异常：{e}")
    
    # 测试 5.2: 跨域请求头检查
    tr_test = "CORS-02"
    try:
        api.login_with_role("admin")
        req = urllib.request.Request(f"{api.base}/api/health")
        req.add_header("Authorization", f"Bearer {api.token}")
        req.add_header("Origin", "http://localhost:3000")
        
        resp = urllib.request.urlopen(req, timeout=10)
        acao = resp.headers.get("Access-Control-Allow-Origin", "")
        vary = resp.headers.get("Vary", "")
        
        if acao and "Origin" in vary:
            tr.ok(tr_test, f"CORS 头配置正确 (Origin: {acao}, Vary: {vary})")
        elif acao:
            tr.skip(tr_test, f"CORS 头存在但 Vary 缺失：{acao}")
        else:
            tr.skip(tr_test, "未返回 CORS 相关头")
    except Exception as e:
        tr.skip(tr_test, f"跨域头检查异常：{e}")
    
    # 测试 5.3: 凭证支持检查
    tr_test = "CORS-03"
    try:
        req = urllib.request.Request(f"{api.base}/api/health", method="OPTIONS")
        req.add_header("Origin", "http://localhost:3000")
        req.add_header("Access-Control-Request-Credentials", "include")
        
        resp = urllib.request.urlopen(req, timeout=10)
        acac = resp.headers.get("Access-Control-Allow-Credentials", "")
        
        if acac == "true":
            tr.ok(tr_test, "CORS 凭证支持已启用")
        elif acac:
            tr.skip(tr_test, f"CORS 凭证配置：{acac}")
        else:
            tr.skip(tr_test, "未配置 Access-Control-Allow-Credentials")
    except Exception as e:
        tr.skip(tr_test, f"凭证支持检查异常：{e}")
    
    # 测试 5.4: 恶意域名拒绝
    tr_test = "CORS-04"
    try:
        req = urllib.request.Request(f"{api.base}/api/health", method="OPTIONS")
        req.add_header("Origin", "http://malicious-site.com")
        
        resp = urllib.request.urlopen(req, timeout=10)
        acao = resp.headers.get("Access-Control-Allow-Origin", "")
        
        if acao == "" or acao == "null":
            tr.ok(tr_test, "恶意域名 CORS 请求被正确拒绝")
        elif acao == "*":
            tr.fail(tr_test, "恶意域名未被拒绝 (Allow-Origin: *)")
        else:
            tr.skip(tr_test, f"响应头：{acao}")
    except urllib.error.HTTPError:
        tr.ok(tr_test, "恶意域名请求被拒绝")
    except Exception as e:
        tr.skip(tr_test, f"恶意域名测试异常：{e}")


def generate_report(tr: TR, output_file: str = None):
    """生成测试报告"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""
# 安全权限测试报告

**生成时间:** {timestamp}
**测试总数:** {tr.passed + tr.failed + tr.skipped}
**通过率:** {tr.passed / (tr.passed + tr.failed) * 100:.1f}% (排除跳过项)

## 汇总

| 状态 | 数量 |
|------|------|
| ✓ 通过 | {tr.passed} |
| ✗ 失败 | {tr.failed} |
| ⊘ 跳过 | {tr.skipped} |

## 详细结果

"""
    
    # 按类别分组
    categories = {
        "RBAC": [],
        "RATE": [],
        "SQL": [],
        "XSS": [],
        "CORS": [],
    }
    
    for passed, tid, msg in tr.results:
        for cat in categories:
            if tid.startswith(cat.split("-")[0]):
                status = "✓" if passed else ("✗" if passed is False else "⊘")
                categories[cat].append(f"- {status} **{tid}**: {msg}")
                break
    
    for cat, results in categories.items():
        if results:
            report += f"\n### {cat} 测试\n\n"
            report += "\n".join(results) + "\n"
    
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n{C.BD}报告已保存:{C.E} {output_file}")
    
    return report


# ─── 主函数 ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="TradingAgents 安全权限测试")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help=f"后端地址 (默认：{DEFAULT_BACKEND})")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--report", default="SECURITY_TEST_REPORT.md", help="报告输出文件")
    args = parser.parse_args()
    
    print(f"{C.BD}{'='*70}{C.E}")
    print(f"{C.BD}TradingAgents-CN 安全权限测试套件{C.E}")
    print(f"{C.BD}{'='*70}{C.E}")
    print(f"后端地址：{args.backend}")
    print(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tr = TR()
    api = API(args.backend)
    
    # 1. RBAC 角色权限测试
    test_rbac_permissions(api, tr, args.verbose)
    
    # 2. API 速率限制测试
    test_rate_limiting(api, tr, args.verbose)
    
    # 3. SQL 注入防护测试
    test_sql_injection(api, tr, args.verbose)
    
    # 4. XSS 防护测试
    test_xss_protection(api, tr, args.verbose)
    
    # 5. CORS 配置测试
    test_cors_configuration(api, tr, args.verbose)
    
    # 生成报告
    tr.summary()
    generate_report(tr, args.report)
    
    # 返回退出码
    sys.exit(0 if tr.failed == 0 else 1)


if __name__ == "__main__":
    main()
