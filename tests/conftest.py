#!/usr/bin/env python3
"""
pytest 配置文件
提供通用 fixture 和工具函数
"""

import pytest
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"
_cached_token = None


@pytest.fixture(scope="session")
def base_url():
    """返回后端 API 基础 URL"""
    return BASE_URL


@pytest.fixture(scope="session")
def token():
    """获取并缓存测试 Token"""
    global _cached_token
    if _cached_token:
        return _cached_token
    
    data = json.dumps({"username": "admin", "password": "admin123"}).encode()
    req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        _cached_token = resp["access_token"]
        return _cached_token
    except Exception as e:
        pytest.fail(f"无法获取测试 Token: {e}")


@pytest.fixture
def headers(token):
    """返回包含 Authorization 的请求头"""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_request(token):
    """API 请求辅助函数"""
    def _request(method, path, data=None):
        url = f"{BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {token}"}
        
        if data is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data).encode()
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return {"error": e.code, "body": e.read().decode()}
        except Exception as e:
            return {"error": str(e)}
    
    return _request


@pytest.fixture
def test_stocks():
    """返回测试股票列表"""
    return [
        {"code": "600519", "market": "A 股", "name": "贵州茅台"},
        {"code": "512170", "market": "A 股", "name": "医疗 ETF"},
        {"code": "560280", "market": "A 股", "name": "工业 ETF"},
        {"code": "NVDA", "market": "美股", "name": "英伟达"},
    ]


@pytest.fixture
def test_dates():
    """返回测试日期列表"""
    return [
        "2026-04-08",  # 今日
        "2026-04-07",  # 昨日
        "2026-04-01",  # 历史
    ]
