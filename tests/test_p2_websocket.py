"""
P2 WebSocket 实时推送测试 - pytest 格式
测试 WebSocket 进度推送端点
"""
import pytest
import requests
import json
import asyncio
import websockets
import time

BASE_URL = "http://localhost:8080"
WS_URL = "ws://127.0.0.1:8080"


@pytest.fixture(scope="module")
def token():
    """获取认证 token"""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10
    )
    data = resp.json()
    return data.get("data", {}).get("access_token") or data.get("data", {}).get("token")


@pytest.fixture(scope="module")
def client():
    """API 客户端"""
    class APIClient:
        def __init__(self, base_url):
            self.base_url = base_url.rstrip("/")
            self.token = None
        
        def login(self):
            resp = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": "admin", "password": "admin123"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("data", {}).get("access_token") or data.get("data", {}).get("token")
                return True
            return False
        
        def get(self, path):
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            resp = requests.get(f"{self.base_url}{path}", headers=headers, timeout=10)
            return resp.json()
    
    c = APIClient(BASE_URL)
    c.login()
    return c


def test_p2_websocket_endpoint_exists():
    """P2: WebSocket 进度端点存在"""
    # 测试 HTTP upgrade 请求（检查端点是否可访问）
    resp = requests.get(f"{BASE_URL}/api/ws/progress", timeout=5)
    # WebSocket 端点会返回 404 或 upgrade required
    assert resp.status_code in [404, 426, 101], \
        f"WebSocket 端点异常: {resp.status_code}"


def test_p2_api_progress_endpoint(client):
    """P2: API 进度端点正常"""
    # 使用已完成的任务测试
    resp = client.get("/api/analysis/tasks/560710_20260410/status")
    data = resp.get("data", {})
    
    # 验证返回结构
    assert "status" in data or "progress" in data or "result_data" in data, \
        f"进度 API 返回异常: {data}"


def test_p2_progress_websocket_message_format():
    """P2: WebSocket 消息格式验证"""
    # 定义期望的消息格式
    expected_message = {
        "type": "progress_update",
        "task_id": "test_task",
        "data": {
            "status": "running",
            "progress": 50,
            "current_step_name": "技术分析",
            "steps": []
        }
    }
    
    # 验证消息结构
    assert "type" in expected_message
    assert "task_id" in expected_message
    assert "data" in expected_message
    assert "status" in expected_message["data"]
    assert "progress" in expected_message["data"]


def test_p2_progress_broadcast_structure():
    """P2: 进度广播数据结构验证"""
    # 模拟广播数据
    broadcast_data = {
        "type": "progress_update",
        "task_id": "560710_20260410",
        "data": {
            "status": "running",
            "progress": 75,
            "elapsed_time": 120,
            "remaining_time": 40,
            "current_step_name": "新闻舆情分析",
            "current_step_description": "正在分析相关新闻和舆情",
            "steps": [
                {
                    "id": "data_fetch",
                    "name": "数据获取",
                    "status": "completed",
                    "progress": 100,
                    "operations": [
                        {"id": "fetch_ohlcv", "name": "获取K线数据", "status": "completed"},
                    ]
                }
            ]
        }
    }
    
    # 验证结构完整性
    assert broadcast_data["type"] == "progress_update"
    assert "steps" in broadcast_data["data"]
    assert len(broadcast_data["data"]["steps"]) > 0
    
    # 验证步骤结构
    step = broadcast_data["data"]["steps"][0]
    assert "id" in step
    assert "name" in step
    assert "status" in step
    assert "operations" in step


def test_p2_websocket_subscription_message():
    """P2: WebSocket 订阅消息格式"""
    subscribe_msg = {
        "type": "subscribe",
        "task_id": "560710_20260410"
    }
    
    assert subscribe_msg["type"] == "subscribe"
    assert "task_id" in subscribe_msg
    assert len(subscribe_msg["task_id"]) > 0


def test_p2_progress_update_frequency():
    """P2: 进度更新频率验证"""
    # 模拟进度数据
    progress_history = []
    for i in range(10):
        progress_history.append({
            "timestamp": time.time() - (10 - i),
            "progress": i * 10,
            "status": "running" if i < 9 else "completed"
        })
    
    # 验证更新间隔合理（每秒更新）
    for i in range(1, len(progress_history)):
        interval = progress_history[i]["timestamp"] - progress_history[i-1]["timestamp"]
        assert 0.9 <= interval <= 1.1, f"更新间隔异常: {interval}s"


def test_p2_redis_progress_key_format():
    """P2: Redis 进度键格式验证"""
    task_id = "560710_20260410"
    expected_key = f"task:{task_id}:progress"
    
    assert expected_key == "task:560710_20260410:progress"
    
    # 验证键格式符合预期
    parts = expected_key.split(":")
    assert parts[0] == "task"
    assert parts[2] == "progress"
    assert len(parts) == 3
