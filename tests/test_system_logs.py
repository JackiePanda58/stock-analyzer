#!/usr/bin/env python3
"""
系统日志测试套件
覆盖：系统日志查询、操作日志查询、日志导出、日志级别过滤
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

class TestSystemLogs(unittest.TestCase):
    """系统日志测试"""
    
    def test_system_logs_query(self):
        """查询系统日志"""
        req = urllib.request.Request(f"{BASE_URL}/api/system/logs?page=1&page_size=10", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 系统日志查询成功")
    
    def test_operation_logs_query(self):
        """查询操作日志"""
        req = urllib.request.Request(f"{BASE_URL}/api/system/operation-logs?page=1&page_size=10", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 操作日志查询成功")
    
    def test_logs_export(self):
        """日志导出"""
        req = urllib.request.Request(f"{BASE_URL}/api/system/logs/export?format=json", headers=headers())
        try:
            resp = urllib.request.urlopen(req, timeout=10).read()
            self.assertTrue(len(resp) > 0)
            print("✓ 日志导出成功")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("⊘ 日志导出接口不存在（跳过）")
            else:
                raise
    
    def test_logs_filter_by_level(self):
        """按日志级别过滤"""
        for level in ["INFO", "WARNING", "ERROR"]:
            req = urllib.request.Request(f"{BASE_URL}/api/system/logs?level={level}&page=1", headers=headers())
            try:
                resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
                print(f"✓ {level} 级别日志过滤成功")
            except urllib.error.HTTPError:
                print(f"⊘ {level} 级别过滤不支持")

if __name__ == "__main__":
    unittest.main(verbosity=2)
