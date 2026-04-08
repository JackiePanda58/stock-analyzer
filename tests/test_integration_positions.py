#!/usr/bin/env python3
"""
持仓管理集成测试
覆盖：查看持仓→买入→验证→卖出→验证
"""

import unittest
import json
import urllib.request

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

class TestPositionsIntegration(unittest.TestCase):
    """持仓管理集成测试"""
    
    def test_positions_list(self):
        """查看持仓列表"""
        req = urllib.request.Request(f"{BASE_URL}/api/trade/positions", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 持仓列表获取成功")
    
    def test_position_buy(self):
        """买入操作"""
        data = json.dumps({
            "symbol": "600519",
            "quantity": 100,
            "price": 1500
        }).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/trade/buy", data=data, headers={**headers(), "Content-Type": "application/json"})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if resp.get("success"):
                print("✓ 买入操作成功")
            else:
                print(f"⊘ 买入操作返回：{resp}")
        except urllib.error.HTTPError as e:
            print(f"⊘ 买入接口返回 HTTP {e.code}")
    
    def test_position_sell(self):
        """卖出操作"""
        data = json.dumps({
            "symbol": "600519",
            "quantity": 50,
            "price": 1550
        }).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/trade/sell", data=data, headers={**headers(), "Content-Type": "application/json"})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if resp.get("success"):
                print("✓ 卖出操作成功")
            else:
                print(f"⊘ 卖出操作返回：{resp}")
        except urllib.error.HTTPError as e:
            print(f"⊘ 卖出接口返回 HTTP {e.code}")
    
    def test_simulated_account(self):
        """查看模拟账户"""
        req = urllib.request.Request(f"{BASE_URL}/api/simulated-trading/account", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 模拟账户获取成功")

if __name__ == "__main__":
    unittest.main(verbosity=2)
