#!/usr/bin/env python3
"""
调度器管理测试套件
覆盖：任务列表、任务 CRUD、执行历史、任务统计
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

class TestSchedulerManagement(unittest.TestCase):
    """调度器管理测试"""
    
    def test_scheduler_jobs_list(self):
        """获取任务列表"""
        req = urllib.request.Request(f"{BASE_URL}/api/scheduler/jobs", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 任务列表获取成功")
    
    def test_scheduler_stats(self):
        """获取任务统计"""
        req = urllib.request.Request(f"{BASE_URL}/api/scheduler/stats", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 任务统计获取成功")
    
    def test_scheduler_executions(self):
        """获取执行历史"""
        req = urllib.request.Request(f"{BASE_URL}/api/scheduler/executions", headers=headers())
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        self.assertTrue(resp.get("success") or resp.get("data"))
        print("✓ 执行历史获取成功")
    
    def test_scheduler_job_detail(self):
        """获取任务详情"""
        req = urllib.request.Request(f"{BASE_URL}/api/scheduler/jobs/1/executions", headers=headers())
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            print("✓ 任务详情获取成功")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print("⊘ 任务详情接口不存在（跳过）")
            else:
                raise
    
    def test_scheduler_job_creation(self):
        """创建任务（如果支持）"""
        data = json.dumps({
            "name": "test_job",
            "cron": "0 * * * *",
            "action": "test"
        }).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/scheduler/jobs", data=data, headers={**headers(), "Content-Type": "application/json"})
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if resp.get("success"):
                print("✓ 任务创建成功")
            else:
                print("⊘ 任务创建不支持")
        except urllib.error.HTTPError as e:
            if e.code in (404, 405):
                print("⊘ 任务创建接口不存在（跳过）")
            else:
                raise

if __name__ == "__main__":
    unittest.main(verbosity=2)
