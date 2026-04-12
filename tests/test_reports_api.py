"""
报告排序功能测试 - pytest 格式
"""
import pytest
import requests
import time

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
            resp = requests.get(f"{self.base_url}{path}", headers=headers, timeout=30)
            return resp.json()
    
    c = APIClient(BASE_URL)
    c.login()
    return c


def test_sort_created_at_desc(client):
    """按创建时间降序排序"""
    resp = client.get("/api/reports/list?sort=created_at&order=desc&page_size=10")
    data = resp.get("data", {})
    
    assert data.get("sort") == "created_at", f"排序字段错误: {data.get('sort')}"
    assert data.get("order") == "desc", f"排序方向错误: {data.get('order')}"
    
    reports = data.get("reports", [])
    if len(reports) >= 2:
        t1 = reports[0].get("created_at", "")
        t2 = reports[1].get("created_at", "")
        assert t1 >= t2, f"降序验证失败: {t1} < {t2}"


def test_sort_created_at_asc(client):
    """按创建时间升序排序"""
    resp = client.get("/api/reports/list?sort=created_at&order=asc&page_size=10")
    data = resp.get("data", {})
    
    assert data.get("order") == "asc", f"升序参数错误: {data.get('order')}"
    
    reports = data.get("reports", [])
    if len(reports) >= 2:
        t1 = reports[0].get("created_at", "")
        t2 = reports[1].get("created_at", "")
        assert t1 <= t2, f"升序验证失败: {t1} > {t2}"


def test_sort_symbol(client):
    """按股票代码排序"""
    resp = client.get("/api/reports/list?sort=symbol&order=asc&page_size=10")
    data = resp.get("data", {})
    
    assert data.get("sort") == "symbol", f"排序字段错误: {data.get('sort')}"
    
    reports = data.get("reports", [])
    if len(reports) >= 2:
        s1 = reports[0].get("symbol", "")
        s2 = reports[1].get("symbol", "")
        assert s1 <= s2, f"股票代码排序验证失败: {s1} > {s2}"


def test_sort_market(client):
    """按市场排序"""
    resp = client.get("/api/reports/list?sort=market&order=asc&page_size=10")
    data = resp.get("data", {})
    
    assert data.get("sort") == "market", f"排序字段错误: {data.get('sort')}"


def test_sort_date_field(client):
    """按日期字段排序"""
    resp = client.get("/api/reports/list?sort=date&order=desc&page_size=10")
    data = resp.get("data", {})
    
    assert data.get("sort") == "date", f"排序字段错误: {data.get('sort')}"


def test_pagination_with_sort(client):
    """分页与排序结合"""
    resp = client.get("/api/reports/list?sort=created_at&order=desc&page=1&page_size=3")
    data = resp.get("data", {})
    
    reports = data.get("reports", [])
    assert len(reports) <= 3, f"分页失败: 返回 {len(reports)} 条"
    assert data.get("total", 0) > 0, "总记录数为0"
