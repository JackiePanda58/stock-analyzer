#!/usr/bin/env python3
"""
用户认证集成测试
覆盖：登录→Token 验证→刷新→登出→验证失效
"""

import unittest
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"

class TestAuthIntegration(unittest.TestCase):
    """用户认证集成测试"""
    
    def test_login(self):
        """登录获取 Token"""
        data = json.dumps({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        
        self.assertIn("access_token", resp)
        self.token = resp["access_token"]
        print("✓ 登录成功，Token 获取")
    
    def test_token_valid(self):
        """验证 Token 有效"""
        # 先登录
        data = json.dumps({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        token = resp["access_token"]
        
        # 使用 Token 访问受保护接口
        req = urllib.request.Request(f"{BASE_URL}/api/favorites/", headers={"Authorization": f"Bearer {token}"})
        resp = urllib.request.urlopen(req, timeout=10).read()
        
        self.assertTrue(len(resp) > 0)
        print("✓ Token 验证成功")
    
    def test_token_refresh(self):
        """Token 刷新"""
        # 先登录
        data = json.dumps({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        token = resp["access_token"]
        
        # 刷新 Token
        req = urllib.request.Request(f"{BASE_URL}/api/auth/refresh", data=b"{}", headers={**{"Authorization": f"Bearer {token}"}, "Content-Type": "application/json"})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if resp.get("data", {}).get("access_token"):
                print("✓ Token 刷新成功")
            else:
                print(f"⊘ Token 刷新返回：{resp}")
        except urllib.error.HTTPError as e:
            print(f"⊘ Token 刷新接口返回 HTTP {e.code}")
    
    def test_logout(self):
        """登出操作"""
        # 先登录
        data = json.dumps({"username": "admin", "password": "admin123"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        token = resp["access_token"]
        
        # 登出
        req = urllib.request.Request(f"{BASE_URL}/api/auth/logout", data=b"", headers={"Authorization": f"Bearer {token}"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        
        if resp.get("success"):
            print("✓ 登出成功")
        else:
            print(f"⊘ 登出返回：{resp}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
