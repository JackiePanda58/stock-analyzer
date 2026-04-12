"""
测试报告列表排序功能 - verification-loop Phase 4

测试文件: /root/stock-analyzer/tests/test_reports_sort.py
执行: python tests/test_reports_sort.py
"""

import os
import sys
import json
import time
from typing import Tuple

# 配置
DEFAULT_BACKEND = os.environ.get("TEST_BACKEND", "http://127.0.0.1:8080")

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class APIError(Exception):
    pass

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.username = "admin"
        self.password = "admin123"
    
    def login(self) -> bool:
        import requests
        resp = requests.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            # 尝试 access_token 或 token
            self.token = data.get("data", {}).get("access_token") or data.get("data", {}).get("token")
            return True
        return False
    
    def get(self, path: str, **kwargs) -> dict:
        import requests
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        resp = requests.get(
            f"{self.base_url}{path}",
            headers=headers,
            timeout=10,
            **kwargs
        )
        if resp.status_code == 200:
            return resp.json()
        raise APIError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    
    def post(self, path: str, **kwargs) -> dict:
        import requests
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        resp = requests.post(
            f"{self.base_url}{path}",
            headers=headers,
            timeout=10,
            **kwargs
        )
        if resp.status_code in (200, 201):
            return resp.json()
        raise APIError(f"HTTP {resp.status_code}: {resp.text[:200]}")


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []
    
    def ok(self, test_id: str, msg: str):
        self.passed += 1
        self.results.append(("PASS", test_id, msg))
        print(f"  {Colors.GREEN}✅{Colors.END} {test_id}: {msg}")
    
    def fail(self, test_id: str, msg: str):
        self.failed += 1
        self.results.append(("FAIL", test_id, msg))
        print(f"  {Colors.RED}❌{Colors.END} {test_id}: {msg}")
    
    def skip(self, test_id: str, msg: str):
        self.skipped += 1
        self.results.append(("SKIP", test_id, msg))
        print(f"  {Colors.YELLOW}⏭️{Colors.END} {test_id}: {msg}")
    
    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{Colors.BOLD}{'='*60}")
        print(f"测试结果: {total} 合计 | {Colors.GREEN}{self.passed} 通过{Colors.END} | {Colors.RED}{self.failed} 失败{Colors.END} | {Colors.YELLOW}{self.skipped} 跳过{Colors.END}")
        return self.failed == 0


# ─── 排序测试 ────────────────────────────────────────────────────────────────

def test_sort_created_at_desc(client: APIClient, tr: TestResult):
    """按创建时间降序排序（默认）"""
    print(f"\n{Colors.BOLD}【排序】按创建时间降序{Colors.END}")
    try:
        resp = client.get("/api/reports/list?sort=created_at&order=desc&page=1&page_size=10")
        reports = resp.get("data", {}).get("reports", [])
        sort = resp.get("data", {}).get("sort", "unknown")
        order = resp.get("data", {}).get("order", "unknown")
        
        if sort == "created_at" and order == "desc":
            tr.ok("SORT-01", f"排序参数正确: sort={sort}, order={order}")
        else:
            tr.fail("SORT-01", f"排序参数错误: sort={sort}, order={order}")
        
        if len(reports) >= 2:
            # 验证降序
            t1 = reports[0].get("created_at", "")
            t2 = reports[1].get("created_at", "")
            if t1 >= t2:
                tr.ok("SORT-02", f"降序验证通过: {t1} >= {t2}")
            else:
                tr.fail("SORT-02", f"降序验证失败: {t1} < {t2}")
        elif len(reports) == 1:
            tr.skip("SORT-02", "报告数量不足，无法验证排序")
        else:
            tr.skip("SORT-02", "报告列表为空")
    except Exception as e:
        tr.fail("SORT-01", str(e))


def test_sort_created_at_asc(client: APIClient, tr: TestResult):
    """按创建时间升序排序"""
    print(f"\n{Colors.BOLD}【排序】按创建时间升序{Colors.END}")
    try:
        resp = client.get("/api/reports/list?sort=created_at&order=asc&page=1&page_size=10")
        reports = resp.get("data", {}).get("reports", [])
        order = resp.get("data", {}).get("order", "unknown")
        
        if order == "asc":
            tr.ok("SORT-03", f"升序参数正确: order={order}")
        else:
            tr.fail("SORT-03", f"升序参数错误: order={order}")
        
        if len(reports) >= 2:
            t1 = reports[0].get("created_at", "")
            t2 = reports[1].get("created_at", "")
            if t1 <= t2:
                tr.ok("SORT-04", f"升序验证通过: {t1} <= {t2}")
            else:
                tr.fail("SORT-04", f"升序验证失败: {t1} > {t2}")
        elif len(reports) == 1:
            tr.skip("SORT-04", "报告数量不足，无法验证排序")
        else:
            tr.skip("SORT-04", "报告列表为空")
    except Exception as e:
        tr.fail("SORT-03", str(e))


def test_sort_symbol(client: APIClient, tr: TestResult):
    """按股票代码排序"""
    print(f"\n{Colors.BOLD}【排序】按股票代码排序{Colors.END}")
    try:
        resp = client.get("/api/reports/list?sort=symbol&order=asc&page=1&page_size=10")
        reports = resp.get("data", {}).get("reports", [])
        sort = resp.get("data", {}).get("sort", "unknown")
        
        if sort == "symbol":
            tr.ok("SORT-05", f"股票代码排序参数正确: sort={sort}")
        else:
            tr.fail("SORT-05", f"股票代码排序参数错误: sort={sort}")
        
        if len(reports) >= 2:
            s1 = reports[0].get("symbol", "")
            s2 = reports[1].get("symbol", "")
            if s1 <= s2:
                tr.ok("SORT-06", f"股票代码排序验证通过: {s1} <= {s2}")
            else:
                tr.fail("SORT-06", f"股票代码排序验证失败: {s1} > {s2}")
        elif len(reports) == 1:
            tr.skip("SORT-06", "报告数量不足")
        else:
            tr.skip("SORT-06", "报告列表为空")
    except Exception as e:
        tr.fail("SORT-05", str(e))


def test_sort_market(client: APIClient, tr: TestResult):
    """按市场排序"""
    print(f"\n{Colors.BOLD}【排序】按市场排序{Colors.END}")
    try:
        resp = client.get("/api/reports/list?sort=market&order=asc&page=1&page_size=10")
        reports = resp.get("data", {}).get("reports", [])
        sort = resp.get("data", {}).get("sort", "unknown")
        
        if sort == "market":
            tr.ok("SORT-07", f"市场排序参数正确: sort={sort}")
        else:
            tr.fail("SORT-07", f"市场排序参数错误: sort={sort}")
    except Exception as e:
        tr.fail("SORT-07", str(e))


def test_sort_invalid_field(client: APIClient, tr: TestResult):
    """无效排序字段处理"""
    print(f"\n{Colors.BOLD}【排序】无效排序字段{Colors.END}")
    try:
        resp = client.get("/api/reports/list?sort=invalid_field&order=desc&page=1&page_size=5")
        reports = resp.get("data", {}).get("reports", [])
        # 应该返回默认排序（created_at desc），不报错
        tr.ok("SORT-08", f"无效字段不报错，返回 {len(reports)} 条记录")
    except Exception as e:
        tr.fail("SORT-08", str(e))


# ─── 主函数 ──────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="报告列表排序功能测试")
    parser.add_argument("--backend", default=DEFAULT_BACKEND,
                        help=f"后端地址 (默认: {DEFAULT_BACKEND})")
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{'='*60}")
    print(f"报告列表排序功能测试 - verification-loop Phase 4")
    print(f"后端: {args.backend}{Colors.END}")
    
    client = APIClient(args.backend)
    tr = TestResult()
    
    # 登录
    try:
        client.login()
        print(f"\n{Colors.GREEN}✅ 登录成功{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ 登录失败: {e}{Colors.END}")
        sys.exit(1)
    
    # 执行测试
    test_sort_created_at_desc(client, tr)
    test_sort_created_at_asc(client, tr)
    test_sort_symbol(client, tr)
    test_sort_market(client, tr)
    test_sort_invalid_field(client, tr)
    
    # 总结
    success = tr.summary()
    print(f"\n{Colors.BOLD}测试完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
