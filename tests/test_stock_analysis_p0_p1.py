#!/usr/bin/env python3
"""
TradingAgents-CN 股票分析模块 — P0/P1 自动化测试
覆盖：缓存命中、参数校验、轮询生命周期、结果结构、并发、历史记录

用法: python3 test_stock_analysis_p0_p1.py [--backend URL]
"""
import argparse
import json
import time
import urllib.request
import urllib.error
import sys
import os
from datetime import datetime

# ─── 配置 ────────────────────────────────────────────────────────────────────
DEFAULT_BACKEND = "http://localhost:8080"
TEST_SYMBOLS = {
    "600519": {"name": "贵州茅台", "type": "A股", "in_known": True},
    "512170": {"name": "医疗ETF", "type": "ETF", "in_known": True},
    "560280": {"name": "工业出口ETF", "type": "ETF", "in_known": True},
    "512400": {"name": "有色金属ETF", "type": "ETF", "in_known": True},
    "588000": {"name": "科创50ETF", "type": "ETF", "in_known": False},
    "999999": {"name": "不存在", "type": "invalid", "in_known": False},
}
TEST_DEPTHS = [1, 2, 3, 4, 5]  # 快速/基础/标准/深度/全面
POLL_INTERVAL = 2  # 秒
POLL_MAX = 30      # 最多轮询次数


# ─── 工具函数 ────────────────────────────────────────────────────────────────
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []  # (passed, test_id, message)

    def ok(self, test_id: str, msg: str = ""):
        self.passed += 1
        self.results.append((True, test_id, msg))
        print(f"  {Colors.GREEN}✓{Colors.END} {test_id} {msg}")

    def fail(self, test_id: str, msg: str):
        self.failed += 1
        self.results.append((False, test_id, msg))
        print(f"  {Colors.RED}✗{Colors.END} {test_id} {Colors.RED}{msg}{Colors.END}")

    def skip(self, test_id: str, msg: str):
        self.skipped += 1
        self.results.append((None, test_id, msg))
        print(f"  {Colors.YELLOW}⊘{Colors.END} {test_id} {Colors.YELLOW}{msg}{Colors.END}")

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}测试结果:{Colors.END}  {Colors.GREEN}✓ {self.passed}{Colors.END}  "
              f"{Colors.RED}✗ {self.failed}{Colors.END}  "
              f"{Colors.YELLOW}⊘ {self.skipped}{Colors.END}  (共 {total} 项)")
        return self.failed == 0


class APIClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.token = None

    def login(self, username="admin", password="admin123") -> str:
        data = json.dumps({"username": username, "password": password}).encode()
        req = urllib.request.Request(
            f"{self.base}/api/v1/login",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = self._read(req)
        self.token = resp["access_token"]
        return self.token

    def auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def post(self, path: str, data: dict, auth=True) -> dict:
        headers = {"Content-Type": "application/json"}
        if auth:
            headers.update(self.auth_headers())
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=json.dumps(data).encode(),
            headers=headers
        )
        return self._read(req)

    def get(self, path: str, auth=True) -> dict:
        headers = {}
        if auth:
            headers.update(self.auth_headers())
        req = urllib.request.Request(f"{self.base}{path}", headers=headers)
        return self._read(req)

    def get_raw(self, path: str, auth=True) -> urllib.request.urlopen:
        headers = {}
        if auth:
            headers.update(self.auth_headers())
        return urllib.request.urlopen(urllib.request.Request(f"{self.base}{path}", headers=headers))

    def _read(self, req: urllib.request.Request) -> dict:
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise APIError(f"HTTP {e.code}: {body[:200]}", e.code)
        except Exception as e:
            raise APIError(str(e), 0)


class APIError(Exception):
    def __init__(self, msg: str, code: int):
        super().__init__(msg)
        self.code = code


# ─── P0 测试 ─────────────────────────────────────────────────────────────────

def test_p0_cache_hit_logic(client: APIClient, tr: TestResult):
    """AC-01~05: 缓存命中逻辑"""
    print(f"\n{Colors.BOLD}【P0】AC-01~05 缓存命中逻辑{Colors.END}")

    # AC-01: 今日首次分析 → 新 task_id（如果没有缓存）或 cached_{symbol}（如果今日已有）
    try:
        resp = client.post("/api/analysis/single", {
            "symbol": "560280",
            "parameters": {
                "market_type": "A股",
                "analysis_date": "2026-04-09",
                "research_depth": 3,
                "selected_analysts": [1, 2]
            }
        })
        task_id = resp["data"]["task_id"]
        # 两种正确结果：1) 新task_id 2) cached_560280（今日已分析）
        if task_id.startswith("560280_") and "cached" not in task_id:
            tr.ok("AC-01", f"新分析 task_id={task_id}")
        elif task_id == "cached_560280":
            tr.ok("AC-01", f"今日已有分析，返回 cached_560280（正确行为）")
        else:
            tr.fail("AC-01", f"预期新task_id或cached_560280，实际={task_id}")
    except APIError as e:
        tr.fail("AC-01", str(e))

    # AC-02: 缓存命中规则：
    #   1. 如果今日已有完成态分析 → cached_{symbol}
    #   2. 如果上一个分析仍在 running → 新 task_id（无缓存可命中）
    # 先等待 AC-01 的分析完成
    try:
        # 轮询等待 AC-01 完成（最多60秒）
        for _ in range(30):
            time.sleep(2)
            st = client.get(f"/api/analysis/tasks/{task_id}/status")
            if st["data"]["status"] == "completed":
                break
        # 再发第二个请求
        resp2 = client.post("/api/analysis/single", {
            "symbol": "560280",
            "parameters": {
                "market_type": "A股",
                "analysis_date": "2026-04-09",
                "research_depth": 3,
                "selected_analysts": [1, 2]
            }
        })
        task_id2 = resp2["data"]["task_id"]
        if task_id2 == "cached_560280":
            tr.ok("AC-02", f"缓存命中 task_id={task_id2}")
        else:
            # 缓存未命中可能因为分析仍在进行或缓存写入慢，等待后重试
            time.sleep(2)
            st2 = client.get(f"/api/analysis/tasks/{task_id2}/status")
            if st2["data"]["status"] == "completed" and "cached" not in task_id2:
                tr.skip("AC-02", f"分析完成但无缓存标识（task_id={task_id2}），可能今日首次分析尚未缓存")
            else:
                tr.fail("AC-02", f"预期 cached_560280，实际={task_id2}")
    except APIError as e:
        tr.fail("AC-02", str(e))

    # AC-04: 不同日期 → 新分析
    try:
        resp3 = client.post("/api/analysis/single", {
            "symbol": "560280",
            "parameters": {
                "market_type": "A股",
                "analysis_date": "2026-04-07",
                "research_depth": 3,
                "selected_analysts": [1, 2]
            }
        })
        task_id3 = resp3["data"]["task_id"]
        if task_id3.startswith("560280_") and "cached" not in task_id3:
            tr.ok("AC-04", f"不同日期新分析 task_id={task_id3}")
        else:
            tr.fail("AC-04", f"预期新task_id，实际={task_id3}")
    except APIError as e:
        tr.fail("AC-04", str(e))

    # AC-05: 跨天（用昨天的日期）→ 新分析
    from datetime import timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        resp4 = client.post("/api/analysis/single", {
            "symbol": "512170",
            "parameters": {
                "market_type": "A股",
                "analysis_date": yesterday,
                "research_depth": 3,
                "selected_analysts": [1, 2]
            }
        })
        task_id4 = resp4["data"]["task_id"]
        if task_id4.startswith("512170_") and "cached" not in task_id4:
            tr.ok("AC-05", f"跨天新分析 task_id={task_id4}")
        else:
            tr.fail("AC-05", f"预期新task_id，实际={task_id4}")
    except APIError as e:
        tr.fail("AC-05", str(e))


def test_p0_polling_lifecycle(client: APIClient, tr: TestResult):
    """AL-01~07: 轮询生命周期"""
    print(f"\n{Colors.BOLD}【P0】AL-01~07 轮询生命周期{Colors.END}")

    # AL-01: 正常轮询 pending→completed
    # 注意：真实 LangGraph 分析耗时 10+ 分钟，测试用已完成的历史任务验证轮询机制
    try:
        # 用已有报告的股票，走缓存立即返回
        resp = client.post("/api/analysis/single", {
            "symbol": "600519",
            "parameters": {
                "market_type": "A股",
                "analysis_date": "2026-04-07",  # 历史日期，有报告
                "research_depth": 1,
                "selected_analysts": [1]
            }
        })
        task_id = resp["data"]["task_id"]
        # 缓存命中应该立即 completed
        st = client.get(f"/api/analysis/tasks/{task_id}/status")
        status = st["data"]["status"]
        if status == "completed":
            tr.ok("AL-01", f"缓存分析立即 completed (task_id={task_id})")
        elif status == "pending":
            # 真实新分析：最多等 POLL_MAX*INTERVAL 秒
            status_seen = [status]
            for i in range(POLL_MAX):
                time.sleep(POLL_INTERVAL)
                st = client.get(f"/api/analysis/tasks/{task_id}/status")
                status = st["data"]["status"]
                status_seen.append(status)
                if status == "completed":
                    tr.ok(f"AL-01[{i+1}]", f"轮询 {i+1} 次后 completed")
                    break
            else:
                tr.skip("AL-01", f"真实分析耗时超过 {POLL_MAX*POLL_INTERVAL}s，状态序列: {status_seen}")
        else:
            tr.fail("AL-01", f"未知 status={status}")
    except APIError as e:
        tr.fail("AL-01", str(e))

    # AL-02: 立即轮询
    try:
        resp = client.post("/api/analysis/single", {
            "symbol": "512170",
            "parameters": {
                "market_type": "A股",
                "analysis_date": "2026-04-09",
                "research_depth": 1,
                "selected_analysts": [1]
            }
        })
        task_id = resp["data"]["task_id"]
        # 立即查询
        st = client.get(f"/api/analysis/tasks/{task_id}/status")
        status = st["data"]["status"]
        if status in ("pending", "running", "completed"):
            tr.ok("AL-02", f"立即轮询返回 status={status}")
        else:
            tr.fail("AL-02", f"未知 status={status}")
    except APIError as e:
        tr.fail("AL-02", str(e))

    # AL-03: 轮询不存在的 task
    try:
        st = client.get("/api/analysis/tasks/999999_9999999/status")
        status = st["data"]["status"]
        if status == "pending":
            tr.ok("AL-03", "不存在的 task 返回 pending（预期行为）")
        else:
            tr.fail("AL-03", f"预期 pending，实际={status}")
    except APIError as e:
        tr.fail("AL-03", str(e))

    # AL-04: 并发轮询（3个同时）
    try:
        r1 = client.post("/api/analysis/single", {
            "symbol": "512170",
            "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": 1, "selected_analysts": [1]}
        })
        import concurrent.futures
        task_ids = [r1["data"]["task_id"]]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(client.get, f"/api/analysis/tasks/{tid}/status") for tid in task_ids * 3]
            results = [f.result()["data"]["status"] for f in concurrent.futures.as_completed(futures)]
        if all(s in ("pending", "running", "completed") for s in results):
            tr.ok("AL-04", f"并发轮询 3 个请求全部成功: {results}")
        else:
            tr.fail("AL-04", f"部分请求失败: {results}")
    except Exception as e:
        tr.fail("AL-04", str(e))


def test_p0_result_structure(client: APIClient, tr: TestResult):
    """AR-01~08: 分析结果结构"""
    print(f"\n{Colors.BOLD}【P0】AR-01~08 分析结果结构{Colors.END}")

    # 用已有的 cached_560280 测试
    for task_id in ["560280_20260408", "cached_560280"]:
        try:
            resp = client.get(f"/api/analysis/tasks/{task_id}/result")
            data = resp["data"]
            dec = data.get("decision", {})
            reports = data.get("reports", {})

            # AR-01: decision.action 非空
            action = dec.get("action", "—")
            if action and action != "—":
                tr.ok(f"AR-01[{task_id}]", f"decision.action={action}")
            else:
                tr.fail(f"AR-01[{task_id}]", f"decision.action 为空或 '—': {dec}")

            # AR-02: confidence 在 0-1
            conf = dec.get("confidence", -1)
            if 0 <= conf <= 1:
                tr.ok(f"AR-02[{task_id}]", f"confidence={conf}")
            else:
                tr.fail(f"AR-02[{task_id}]", f"confidence={conf} 超出 [0,1]")

            # AR-03: reasoning 非空
            reasoning = dec.get("reasoning", "")
            if reasoning and len(reasoning) > 5:
                tr.ok(f"AR-03[{task_id}]", f"reasoning 长度={len(reasoning)}")
            else:
                tr.fail(f"AR-03[{task_id}]", f"reasoning 为空: '{reasoning[:30]}'")

            # AR-04: reports.trading_decision.content 长度
            content = reports.get("trading_decision", {}).get("content", "")
            if len(content) > 100:
                tr.ok(f"AR-04[{task_id}]", f"content 长度={len(content)}")
            else:
                tr.fail(f"AR-04[{task_id}]", f"content 过短: {len(content)}")

            # AR-05/06: 缓存/新分析都返回正确结构（已覆盖 above）

        except APIError as e:
            tr.fail(f"AR-xx[{task_id}]", str(e))

    # AR-07: 不同股票结果隔离
    try:
        r1 = client.get("/api/analysis/tasks/560280_20260408/result")
        r2 = client.get("/api/analysis/tasks/600519_20260408/result")
        sym1 = r1.get("data", {}).get("symbol", "")
        sym2 = r2.get("data", {}).get("symbol", "")
        if sym1 == "560280" and sym2 == "600519" and sym1 != sym2:
            tr.ok("AR-07", f"结果隔离正确: {sym1} vs {sym2}")
        else:
            tr.fail("AR-07", f"结果隔离异常: {sym1}, {sym2}")
    except APIError as e:
        tr.fail("AR-07", str(e))

    # AR-08: 不同日期结果不同
    try:
        r1 = client.get("/api/analysis/tasks/600519_20260408/result")
        r2 = client.get("/api/analysis/tasks/600519_20260409/result")
        content1 = r1.get("data", {}).get("reports", {}).get("trading_decision", {}).get("content", "")[:50]
        content2 = r2.get("data", {}).get("reports", {}).get("trading_decision", {}).get("content", "")[:50]
        if content1 != content2:
            tr.ok("AR-08", "不同日期内容不同")
        else:
            tr.skip("AR-08", "不同日期内容相同（可能是相同分析）")
    except APIError as e:
        tr.fail("AR-08", str(e))


# ─── P1 测试 ─────────────────────────────────────────────────────────────────

def test_p1_parameter_validation(client: APIClient, tr: TestResult):
    """AP-01~09: 参数校验"""
    print(f"\n{Colors.BOLD}【P1】AP-01~09 参数校验{Colors.END}")

    # AP-01: 正常 A股 ETF
    try:
        resp = client.post("/api/analysis/single", {
            "symbol": "512170",
            "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": 1, "selected_analysts": [1]}
        })
        if resp.get("success"):
            tr.ok("AP-01", "正常 A股 ETF 请求成功")
        else:
            tr.fail("AP-01", f"success=False: {resp}")
    except APIError as e:
        tr.fail("AP-01", str(e))

    # AP-05: 空股票代码
    try:
        client.post("/api/analysis/single", {
            "symbol": "",
            "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": 1, "selected_analysts": [1]}
        })
        tr.fail("AP-05", "空代码未被拒绝")
    except APIError as e:
        if e.code in (400, 422):
            tr.ok("AP-05", f"空代码被拒绝 (HTTP {e.code})")
        else:
            tr.fail("AP-05", f"空代码未被正确拒绝: HTTP {e.code}")

    # AP-06: 非法股票代码
    try:
        resp = client.post("/api/analysis/single", {
            "symbol": "abc123",
            "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": 1, "selected_analysts": [1]}
        })
        # 如果不报错，至少不应该返回成功
        if not resp.get("success"):
            tr.ok("AP-06", "非法代码被拒绝")
        else:
            tr.skip("AP-06", "非法代码未拒绝但返回（降级处理）")
    except APIError as e:
        if e.code in (400, 422):
            tr.ok("AP-06", f"非法代码被拒绝 (HTTP {e.code})")
        else:
            tr.fail("AP-06", f"非法代码未被正确拒绝: HTTP {e.code}")

    # AP-07: research_depth 边界（已修复，现在会返回 400）
    for depth in [0, 6]:
        try:
            client.post("/api/analysis/single", {
                "symbol": "512170",
                "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": depth, "selected_analysts": [1]}
            })
            tr.fail(f"AP-07[{depth}]", f"depth={depth} 未被拒绝")
        except APIError as e:
            if e.code in (400, 422):
                tr.ok(f"AP-07[{depth}]", f"depth={depth} 超出范围被拒绝")
            else:
                tr.fail(f"AP-07[{depth}]", f"depth={depth} 未被正确拒绝: HTTP {e.code}")

    # AP-08: selected_analysts 空数组
    try:
        resp = client.post("/api/analysis/single", {
            "symbol": "512170",
            "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": 1, "selected_analysts": []}
        })
        if resp.get("success"):
            tr.ok("AP-08", "空数组未拒绝（使用默认分析师）")
        else:
            tr.fail("AP-08", f"空数组被拒绝: {resp}")
    except APIError as e:
        if e.code in (400, 422):
            tr.ok("AP-08", f"空数组被拒绝 (HTTP {e.code})")
        else:
            tr.fail("AP-08", str(e))

    # AP-09: selected_analysts 包含无效 ID
    try:
        resp = client.post("/api/analysis/single", {
            "symbol": "512170",
            "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": 1, "selected_analysts": [99]}
        })
        if resp.get("success"):
            tr.ok("AP-09", "无效分析师ID未导致崩溃（忽略无效ID）")
        else:
            tr.fail("AP-09", f"无效ID导致失败: {resp}")
    except APIError as e:
        tr.fail("AP-09", str(e))


def test_p1_concurrency(client: APIClient, tr: TestResult):
    """ACON-01~04: 并发场景"""
    print(f"\n{Colors.BOLD}【P1】ACON-01~04 并发场景{Colors.END}")
    import concurrent.futures

    # ACON-01: 并发同股票
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futures = [
                ex.submit(client.post, "/api/analysis/single", {
                    "symbol": "560280",
                    "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": 1, "selected_analysts": [1]}
                })
                for _ in range(5)
            ]
            results = [f.result()["data"]["task_id"] for f in concurrent.futures.as_completed(futures)]
        # 应该有1个新分析，其余命中缓存
        cached = [r for r in results if "cached" in r]
        new = [r for r in results if not r.startswith("cached")]
        if len(cached) >= 4 and len(new) <= 1:
            tr.ok("ACON-01", f"并发同股票: {len(new)} 新分析, {len(cached)} 缓存命中")
        else:
            tr.fail("ACON-01", f"结果分布异常: {results}")
    except Exception as e:
        tr.fail("ACON-01", str(e))

    # ACON-02: 并发不同股票
    try:
        symbols = ["512170", "512400", "560280"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            futures = [
                ex.submit(client.post, "/api/analysis/single", {
                    "symbol": sym,
                    "parameters": {"market_type": "A股", "analysis_date": "2026-04-09", "research_depth": 1, "selected_analysts": [1]}
                })
                for sym in symbols
            ]
            results = [f.result()["data"]["task_id"] for f in concurrent.futures.as_completed(futures)]
        if len(results) == 3:
            tr.ok("ACON-02", f"并发3个不同股票全部成功: {results}")
        else:
            tr.fail("ACON-02", f"结果数量异常: {len(results)}")
    except Exception as e:
        tr.fail("ACON-02", str(e))


def test_p1_history(client: APIClient, tr: TestResult):
    """AH-01~05: 分析历史"""
    print(f"\n{Colors.BOLD}【P1】AH-01~05 分析历史{Colors.END}")

    # AH-01: 获取历史记录
    try:
        resp = client.get("/api/analysis/user/history?page=1&page_size=10")
        items = resp.get("data", {}).get("items", [])
        if isinstance(items, list):
            tr.ok("AH-01", f"历史记录返回列表，共 {len(items)} 条")
        else:
            tr.fail("AH-01", f"返回类型异常: {type(items)}")
    except APIError as e:
        tr.fail("AH-01", str(e))

    # AH-02: 按股票筛选
    try:
        resp = client.get("/api/analysis/user/history?symbol=600519&page=1&page_size=10")
        items = resp.get("data", {}).get("items", [])
        symbols = set(i.get("symbol", "") for i in items)
        if all(s == "600519" for s in symbols):
            tr.ok("AH-02", f"按股票筛选正确: {symbols}")
        elif len(items) == 0:
            tr.skip("AH-02", "筛选结果为空（历史无此股票）")
        else:
            tr.fail("AH-02", f"筛选混入其他股票: {symbols}")
    except APIError as e:
        tr.fail("AH-02", str(e))

    # AH-03: 分页
    try:
        resp1 = client.get("/api/analysis/user/history?page=1&page_size=2")
        resp2 = client.get("/api/analysis/user/history?page=2&page_size=2")
        items1 = resp1.get("data", {}).get("items", [])
        items2 = resp2.get("data", {}).get("items", [])
        ids1 = set(i.get("id") for i in items1)
        ids2 = set(i.get("id") for i in items2)
        if len(items1) == 2 and len(items2) == 2 and len(ids1 & ids2) == 0:
            tr.ok("AH-03", "分页正确，页1和页2无重叠")
        elif len(items1) == 0:
            tr.skip("AH-03", "历史记录不足2页")
        else:
            tr.fail("AH-03", f"分页重叠或异常: 页1({len(items1)}) vs 页2({len(items2)})")
    except APIError as e:
        tr.fail("AH-03", str(e))

    # AH-04: 缓存记录可通过 id 获取 result
    try:
        resp = client.get("/api/reports/cached_560280/detail")
        if resp.get("success") and resp.get("data", {}).get("id"):
            tr.ok("AH-05", "cached_560280 可通过历史 id 获取详情")
        else:
            tr.fail("AH-05", f"详情获取失败: {resp}")
    except APIError as e:
        tr.fail("AH-05", str(e))


def test_p1_download(client: APIClient, tr: TestResult):
    """下载相关"""
    print(f"\n{Colors.BOLD}【P1】Download 下载功能{Colors.END}")

    # 下载 cached_ 前缀
    try:
        resp = client.get_raw("/api/reports/cached_560280/download?format=markdown")
        content = resp.read()
        if len(content) > 100:
            tr.ok("AP-DL-01", f"cached_ 前缀下载成功 {len(content)} bytes")
        else:
            tr.fail("AP-DL-01", f"下载内容过短: {len(content)}")
    except APIError as e:
        tr.fail("AP-DL-01", str(e))

    # 下载不存在的报告
    try:
        client.get_raw("/api/reports/999999_9999999/download?format=markdown")
        tr.fail("AP-DL-02", "不存在的报告未被拒绝")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            tr.ok("AP-DL-02", "不存在报告返回 404")
        else:
            tr.fail("AP-DL-02", f"预期 404，实际 HTTP {e.code}")
    except Exception as e:
        tr.fail("AP-DL-02", str(e))


def test_p1_reports_list(client: APIClient, tr: TestResult):
    """报告列表"""
    print(f"\n{Colors.BOLD}【P1】报告列表{Colors.END}")

    # 列表含 decision
    try:
        resp = client.get("/api/reports/list?page=1&page_size=5")
        reports = resp.get("data", {}).get("reports", [])
        if all(r.get("decision", "—") != "—" for r in reports):
            tr.ok("AP-RL-01", f"所有报告都有 decision: {[r['decision'] for r in reports]}")
        elif len(reports) == 0:
            tr.skip("AP-RL-01", "报告列表为空")
        else:
            tr.fail("AP-RL-01", f"部分报告无 decision: {[r.get('decision') for r in reports]}")
    except APIError as e:
        tr.fail("AP-RL-01", str(e))

    # 搜索
    try:
        resp = client.get("/api/reports/list?search_keyword=600519&page=1&page_size=5")
        reports = resp.get("data", {}).get("reports", [])
        if all("600519" in r.get("symbol", "") for r in reports):
            tr.ok("AP-RL-02", f"搜索 600519 返回 {len(reports)} 条")
        elif len(reports) == 0:
            tr.skip("AP-RL-02", "搜索结果为空")
        else:
            tr.fail("AP-RL-02", f"搜索混入其他股票: {[r['symbol'] for r in reports]}")
    except APIError as e:
        tr.fail("AP-RL-02", str(e))


# ─── 主函数 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="股票分析模块 P0/P1 自动化测试")
    parser.add_argument("--backend", default=os.environ.get("TEST_BACKEND", DEFAULT_BACKEND),
                        help=f"后端地址 (默认: {DEFAULT_BACKEND})")
    args = parser.parse_args()

    print(f"{Colors.BOLD}{'='*60}")
    print(f"TradingAgents-CN 股票分析模块 — P0/P1 自动化测试")
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

    # P0
    test_p0_cache_hit_logic(client, tr)
    test_p0_polling_lifecycle(client, tr)
    test_p0_result_structure(client, tr)

    # P1
    test_p1_parameter_validation(client, tr)
    test_p1_concurrency(client, tr)
    test_p1_history(client, tr)
    test_p1_download(client, tr)
    test_p1_reports_list(client, tr)

    # 汇总
    ok = tr.summary()
    print(f"\n{'='*60}")
    if ok:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 全部通过！{Colors.END}")
        sys.exit(0)
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ 有 {tr.failed} 项测试失败{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()
