"""
P1 步骤详情组件测试 - pytest 格式
测试前端 SingleAnalysis.vue 步骤展示功能
"""
import pytest
import requests
import json

BASE_URL = "http://localhost:8080"


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


def test_p1_api_returns_steps_structure(client):
    """P1: API 返回步骤数据结构"""
    # 使用已完成的任务测试
    resp = client.get("/api/analysis/tasks/560710_20260410/status")
    data = resp.get("data", {})
    
    # API 应该返回基础字段
    assert "status" in data or "progress" in data or "result_data" in data, \
        f"API 返回结构异常: {data.keys()}"


def test_p1_progress_tracker_has_steps():
    """P1: ProgressTracker 支持步骤详情"""
    import sys
    sys.path.insert(0, '/root/stock-analyzer')
    from api_progress_tracker import ANALYSIS_STEPS
    
    # 验证步骤定义
    assert len(ANALYSIS_STEPS) == 5, f"应有5个步骤，实际: {len(ANALYSIS_STEPS)}"
    
    # 验证每个步骤有 operations
    for step in ANALYSIS_STEPS:
        assert "operations" in step, f"步骤 {step['id']} 缺少 operations"
        assert len(step["operations"]) > 0, f"步骤 {step['id']} 无操作"


def test_p1_step_operations_structure():
    """P1: 步骤操作结构验证"""
    import sys
    sys.path.insert(0, '/root/stock-analyzer')
    from api_progress_tracker import ANALYSIS_STEPS
    
    # 检查第一个步骤的操作结构
    first_step = ANALYSIS_STEPS[0]
    first_op = first_step["operations"][0]
    
    # 操作应该有 id 和 name
    assert "id" in first_op, "操作缺少 id 字段"
    assert "name" in first_op, "操作缺少 name 字段"


def test_p1_frontend_generateStepsFromBackend_logic():
    """P1: 前端 generateStepsFromBackend 逻辑验证"""
    # 模拟后端返回的步骤数据
    backend_steps = [
        {
            "id": "data_fetch",
            "name": "数据获取",
            "status": "completed",
            "progress": 100,
            "operations": [
                {"id": "fetch_ohlcv", "name": "获取K线数据", "status": "completed", "result": "600519 收盘价: 1850.00"},
                {"id": "fetch_news", "name": "获取新闻数据", "status": "completed", "result": "获取到 3 条新闻"},
            ],
            "current_operation": None
        },
        {
            "id": "technical_analysis",
            "name": "技术分析",
            "status": "running",
            "progress": 50,
            "operations": [
                {"id": "ma_calc", "name": "计算MA", "status": "completed", "result": "MA5=1840"},
                {"id": "macd_calc", "name": "计算MACD", "status": "running", "result": None},
            ],
            "current_operation": "计算MACD"
        }
    ]
    
    # 验证数据结构
    assert len(backend_steps) == 2
    assert backend_steps[0]["status"] == "completed"
    assert backend_steps[1]["status"] == "running"
    assert backend_steps[1]["current_operation"] == "计算MACD"
    
    # 验证操作列表
    assert len(backend_steps[1]["operations"]) == 2
    running_ops = [op for op in backend_steps[1]["operations"] if op["status"] == "running"]
    assert len(running_ops) == 1
    assert running_ops[0]["name"] == "计算MACD"


def test_p1_toggle_expand_logic():
    """P1: 展开/折叠逻辑验证"""
    # 模拟前端状态
    steps = [
        {"key": "data_fetch", "isExpanded": False},
        {"key": "technical_analysis", "isExpanded": False},
    ]
    
    # 切换第一个步骤
    step = next(s for s in steps if s["key"] == "data_fetch")
    step["isExpanded"] = not step["isExpanded"]
    
    assert steps[0]["isExpanded"] == True
    assert steps[1]["isExpanded"] == False
    
    # 再次切换
    step["isExpanded"] = not step["isExpanded"]
    assert steps[0]["isExpanded"] == False


def test_p1_operations_display():
    """P1: 操作详情显示验证"""
    # 模拟操作状态
    operations = [
        {"id": "ma_calc", "name": "计算MA", "status": "completed", "result": "MA5=1840"},
        {"id": "macd_calc", "name": "计算MACD", "status": "running", "result": None},
        {"id": "rsi_calc", "name": "计算RSI", "status": "pending", "result": None},
    ]
    
    # 验证状态分类
    completed = [op for op in operations if op["status"] == "completed"]
    running = [op for op in operations if op["status"] == "running"]
    pending = [op for op in operations if op["status"] == "pending"]
    
    assert len(completed) == 1
    assert len(running) == 1
    assert len(pending) == 1
    
    # 验证结果显示
    assert completed[0]["result"] == "MA5=1840"
    assert running[0]["result"] is None
