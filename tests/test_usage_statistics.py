#!/usr/bin/env python3
"""
使用统计测试套件
覆盖：用量统计、趋势分析、模型使用、Key 管理、成本统计
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

class TestUsageStatistics(unittest.TestCase):
    """使用统计测试"""
    
    def test_usage_stats(self):
        """获取用量统计"""
        req = urllib.request.Request(f"{BASE_URL}/api/usage/stats", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 用量统计获取成功")
    
    def test_usage_trends(self):
        """获取趋势分析"""
        req = urllib.request.Request(f"{BASE_URL}/api/usage/trends", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 趋势分析获取成功")
    
    def test_usage_models(self):
        """获取模型使用统计"""
        req = urllib.request.Request(f"{BASE_URL}/api/usage/models", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 模型使用统计获取成功")
    
    def test_usage_keys(self):
        """获取 Key 管理"""
        req = urllib.request.Request(f"{BASE_URL}/api/usage/keys", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ Key 管理获取成功")
    
    def test_usage_cost(self):
        """获取成本统计"""
        req = urllib.request.Request(f"{BASE_URL}/api/usage/cost", headers=headers())
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            self.assertTrue(resp.get("success") or resp.get("data"))
            print("✓ 成本统计获取成功")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("⊘ 成本统计接口不存在（跳过）")
            else:
                raise
    
    def test_usage_cost_by_provider(self):
        """获取按供应商分类的成本"""
        req = urllib.request.Request(f"{BASE_URL}/api/usage/cost/by_provider", headers=headers())
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            self.assertTrue(resp.get("success") or resp.get("data"))
            print("✓ 按供应商分类成本获取成功")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("⊘ 按供应商分类接口不存在（跳过）")
            else:
                raise

if __name__ == "__main__":
    unittest.main(verbosity=2)
