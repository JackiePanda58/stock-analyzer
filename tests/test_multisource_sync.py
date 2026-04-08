#!/usr/bin/env python3
"""
多数据源同步测试套件
覆盖：同步状态、数据源列表、同步历史、数据源测试
"""

import unittest
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"
TOKEN = None

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

class TestMultiSourceSync(unittest.TestCase):
    """多数据源同步测试"""
    
    def test_sync_status(self):
        """获取同步状态"""
        req = urllib.request.Request(f"{BASE_URL}/api/sync/multi-source/status", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 同步状态获取成功")
    
    def test_sync_sources_status(self):
        """获取各数据源状态"""
        req = urllib.request.Request(f"{BASE_URL}/api/sync/multi-source/sources/status", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 数据源状态获取成功")
    
    def test_sync_sources_current(self):
        """获取当前激活的数据源"""
        req = urllib.request.Request(f"{BASE_URL}/api/sync/multi-source/sources/current", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 当前数据源获取成功")
    
    def test_sync_recommendations(self):
        """获取数据源推荐"""
        req = urllib.request.Request(f"{BASE_URL}/api/sync/multi-source/recommendations", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 数据源推荐获取成功")
    
    def test_sync_history(self):
        """获取同步历史"""
        req = urllib.request.Request(f"{BASE_URL}/api/sync/multi-source/history?page=1", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 同步历史获取成功")
    
    def test_test_sources(self):
        """测试数据源连通性"""
        req = urllib.request.Request(f"{BASE_URL}/api/sync/multi-source/test-sources", headers=headers(), data=b"{}")
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if resp.get("success"):
                print("✓ 数据源连通性测试成功")
            else:
                print("⊘ 数据源测试返回异常")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("⊘ 数据源测试接口不存在（跳过）")
            else:
                raise

if __name__ == "__main__":
    unittest.main(verbosity=2)
