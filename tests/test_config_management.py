#!/usr/bin/env python3
"""
配置管理测试套件
覆盖：LLM 配置、系统设置、数据源配置、配置热重载
"""

import unittest
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"
TOKEN = None

def get_token():
    """获取测试 Token"""
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

class TestConfigManagement(unittest.TestCase):
    """配置管理测试"""
    
    def test_config_llm_read(self):
        """读取 LLM 配置"""
        req = urllib.request.Request(f"{BASE_URL}/api/config/llm", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ LLM 配置读取成功")
    
    def test_config_models(self):
        """读取模型列表"""
        req = urllib.request.Request(f"{BASE_URL}/api/config/models", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 模型列表读取成功")
    
    def test_config_settings(self):
        """读取系统设置"""
        req = urllib.request.Request(f"{BASE_URL}/api/config/settings", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 系统设置读取成功")
    
    def test_config_datasource(self):
        """读取数据源配置"""
        req = urllib.request.Request(f"{BASE_URL}/api/config/datasource", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 数据源配置读取成功")
    
    def test_config_system(self):
        """读取系统配置"""
        req = urllib.request.Request(f"{BASE_URL}/api/config/system", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        self.assertIn("version", str(resp))
        print("✓ 系统配置读取成功")

if __name__ == "__main__":
    unittest.main(verbosity=2)
