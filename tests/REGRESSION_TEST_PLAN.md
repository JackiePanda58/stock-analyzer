# TradingAgents-CN 项目回归测试方案

**版本**: v1.2.2  
**制定时间**: 2026-04-08 19:15  
**测试范围**: 全功能模块回归测试  
**预计耗时**: 2-3 小时

---

## 一、测试目标

1. **验证所有已修复问题** - 确保 6 项安全问题无复发
2. **核心功能回归** - 确保分析、持仓、搜索等核心功能正常
3. **新增功能验证** - WebSocket、定时任务、缓存等新功能
4. **性能基准** - 确保响应时间在可接受范围内
5. **兼容性验证** - 前端、API、数据库兼容性

---

## 二、测试环境

### 2.1 环境配置

| 组件 | 配置 | 端口 |
|------|------|------|
| **后端 API** | FastAPI + Uvicorn | 8080 |
| **前端 UI** | Vue3 + Vite | 62879 |
| **WebSocket** | Python websockets | 8030 |
| **Redis** | Redis 6.x | 6379 |
| **数据库** | SQLite | - |
| **数据源** | BaoStock + AkShare | - |

### 2.2 测试账号

```yaml
admin:
  username: admin
  password: admin123
  role: admin

test_user:
  username: test
  password: test123
  role: user
```

### 2.3 测试数据

```yaml
测试股票:
  - 600519 (贵州茅台 - A 股)
  - 512170 (医疗 ETF - ETF)
  - 560280 (工业出口 ETF)
  - NVDA (英伟达 - 美股)
  - 00700 (腾讯控股 - 港股)

测试日期:
  - 2026-04-08 (今日)
  - 2026-04-07 (昨日)
  - 2026-04-01 (历史)
```

---

## 三、测试套件清单

### 3.1 单元测试套件

| 测试文件 | 测试数 | 预计耗时 | 优先级 |
|---------|--------|---------|--------|
| `test_stock_analysis_blind_spots.py` | 32 | 10 分钟 | P0 |
| `test_stock_analysis_p0_p1.py` | 35 | 15 分钟 | P0 |
| `test_stock_analysis_p1_completion.py` | 20+ | 20 分钟 | P1 |
| `test_datasources.py` | 25 | 5 分钟 | P0 |
| `test_redis_cache.py` | 30 | 10 分钟 | P0 |
| `test_llm_client.py` | 14 | 10 分钟 | P1 |
| `test_websocket.py` | 4 | 5 分钟 | P1 |
| `test_scheduler.py` | 21 | 15 分钟 | P2 |
| `test_security.py` | 24 | 10 分钟 | P0 |
| **小计** | **205+** | **100 分钟** | - |

### 3.2 集成测试套件

| 测试场景 | 测试用例 | 预计耗时 | 优先级 |
|---------|---------|---------|--------|
| 分析完整流程 | 10 | 30 分钟 | P0 |
| 持仓管理流程 | 8 | 15 分钟 | P0 |
| 用户认证流程 | 12 | 10 分钟 | P0 |
| 缓存命中/未命中 | 6 | 10 分钟 | P1 |
| 数据源降级 | 4 | 10 分钟 | P1 |
| WebSocket 推送 | 5 | 10 分钟 | P2 |
| 定时任务触发 | 4 | 20 分钟 | P2 |
| **小计** | **49** | **105 分钟** | - |

### 3.3 端到端测试套件

| 用户场景 | 步骤数 | 预计耗时 | 优先级 |
|---------|--------|---------|--------|
| 新用户注册 → 分析股票 | 8 | 10 分钟 | P0 |
| 添加自选股 → 批量分析 | 6 | 10 分钟 | P0 |
| 查看报告 → 下载 PDF | 5 | 5 分钟 | P1 |
| 模拟交易 → 查看持仓 | 7 | 10 分钟 | P1 |
| 设置 → 配置修改 | 4 | 5 分钟 | P2 |
| **小计** | **30** | **40 分钟** | - |

### 3.4 性能测试套件

| 测试类型 | 并发数 | 持续时间 | 指标 |
|---------|--------|---------|------|
| 登录接口压力测试 | 100 | 5 分钟 | QPS > 50 |
| 分析接口负载测试 | 10 | 10 分钟 | 响应 < 30s |
| 搜索接口并发测试 | 50 | 5 分钟 | 响应 < 1s |
| Redis 缓存性能 | 1000 | 5 分钟 | 命中 < 10ms |
| WebSocket 连接数 | 100 | 10 分钟 | 稳定连接 |
| **小计** | - | **35 分钟** | - |

### 3.5 安全测试套件

| 测试类型 | 测试用例 | 预计耗时 | 优先级 |
|---------|---------|---------|--------|
| SQL 注入防护 | 10 | 5 分钟 | P0 |
| XSS 防护 | 8 | 5 分钟 | P0 |
| CSRF 防护 | 5 | 5 分钟 | P1 |
| Token 安全 | 12 | 10 分钟 | P0 |
| 速率限制 | 6 | 5 分钟 | P0 |
| CORS 配置 | 4 | 5 分钟 | P1 |
| **小计** | **45** | **35 分钟** | - |

---

## 四、详细测试步骤

### 4.1 P0 核心功能回归（必测）

#### 4.1.1 股票分析功能

```bash
# 1. 登录获取 Token
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. 提交分析请求（缓存未命中）
curl -s -X POST http://localhost:8080/api/analysis/single \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "600519",
    "parameters": {
      "market_type": "A 股",
      "analysis_date": "2026-04-08",
      "research_depth": 1,
      "selected_analysts": [1, 2, 3]
    }
  }'

# 3. 轮询任务状态
TASK_ID="600519_xxx"
curl -s http://localhost:8080/api/analysis/tasks/$TASK_ID/status \
  -H "Authorization: Bearer $TOKEN"

# 4. 获取分析结果
curl -s http://localhost:8080/api/analysis/tasks/$TASK_ID/result \
  -H "Authorization: Bearer $TOKEN"

# 5. 验证缓存命中（相同参数再次请求）
# 应返回 cached_600519
```

**预期结果**:
- ✅ 分析请求成功提交
- ✅ 任务状态正确更新（pending → running → completed）
- ✅ 结果包含 decision.action（BUY/SELL/HOLD）
- ✅ 缓存命中返回 cached_{symbol}
- ✅ 响应时间 < 30s（深度 1）

---

#### 4.1.2 持仓管理功能

```bash
# 1. 查看当前持仓
curl -s http://localhost:8080/api/trade/positions \
  -H "Authorization: Bearer $TOKEN"

# 2. 买入操作
curl -s -X POST http://localhost:8080/api/trade/buy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"600519","quantity":100,"price":1500}'

# 3. 验证持仓更新
curl -s http://localhost:8080/api/trade/positions \
  -H "Authorization: Bearer $TOKEN"

# 4. 卖出操作
curl -s -X POST http://localhost:8080/api/trade/sell \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"600519","quantity":50,"price":1550}'

# 5. 查看模拟账户
curl -s http://localhost:8080/api/simulated-trading/account \
  -H "Authorization: Bearer $TOKEN"
```

**预期结果**:
- ✅ 持仓列表正确显示
- ✅ 买入后持仓数量增加
- ✅ 卖出后持仓数量减少
- ✅ 盈亏计算正确（pnl, pnl_percent）
- ✅ 账户余额正确更新

---

#### 4.1.3 搜索功能

```bash
# 1. 搜索股票
curl -s "http://localhost:8080/api/stocks/search?q=600" \
  -H "Authorization: Bearer $TOKEN"

# 2. 搜索自选股
curl -s "http://localhost:8080/api/favorites/search?keyword=512" \
  -H "Authorization: Bearer $TOKEN"

# 3. XSS 防护验证（应转义）
curl -s "http://localhost:8080/api/stocks/search?q=<script>alert(1)</script>" \
  -H "Authorization: Bearer $TOKEN"
```

**预期结果**:
- ✅ 搜索结果返回匹配股票
- ✅ 自选股搜索正常工作
- ✅ XSS payload 被转义（无脚本执行）

---

#### 4.1.4 用户认证与安全

```bash
# 1. 正常登录
curl -s -X POST http://localhost:8080/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 2. 速率限制测试（连续 6 次登录）
for i in {1..6}; do
  curl -s -X POST http://localhost:8080/api/v1/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin123"}'
  echo ""
done
# 第 6 次应返回 429

# 3. Token 登出验证
TOKEN="xxx"
curl -s -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/auth/logout
# 登出后再次使用该 Token 应返回 401

# 4. SQL 注入防护
curl -s -X POST http://localhost:8080/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin\' OR 1=1 --","password":"xxx"}'
# 应返回 401，而非登录成功
```

**预期结果**:
- ✅ 登录成功返回 Token
- ✅ 第 6 次登录返回 429 Too Many Requests
- ✅ 登出后 Token 失效（401）
- ✅ SQL 注入被阻止

---

#### 4.1.5 Dashboard 功能

```bash
# 1. 首页摘要
curl -s http://localhost:8080/api/dashboard/summary \
  -H "Authorization: Bearer $TOKEN"

# 2. 市场概览
curl -s http://localhost:8080/api/dashboard/market \
  -H "Authorization: Bearer $TOKEN"

# 3. 最近报告
curl -s http://localhost:8080/api/dashboard/recent \
  -H "Authorization: Bearer $TOKEN"
```

**预期结果**:
- ✅ total_reports > 0
- ✅ today_reports >= 0
- ✅ total_users = 1
- ✅ 市场指数数据包含 symbol 字段
- ✅ 最近报告列表非空

---

### 4.2 P1 重要功能回归

#### 4.2.1 缓存功能

```bash
# 1. 清空 Redis 缓存
redis-cli FLUSHDB

# 2. 首次分析（缓存未命中）
# 记录响应时间

# 3. 二次分析（缓存命中）
# 应返回 cached_{symbol}
# 响应时间应 < 1s

# 4. 验证缓存 TTL
redis-cli TTL "report:600519:2026-04-08"
# 应接近 43200 秒（12 小时）
```

---

#### 4.2.2 数据源降级

```bash
# 1. 模拟 BaoStock 超时
# 测试自动降级到 AkShare

# 2. 验证降级日志
tail -50 logs/api_server.log | grep -i "fallback\|降级"
```

---

#### 4.2.3 WebSocket 推送

```bash
# 1. 连接 WebSocket
python3 -c "
import asyncio
import websockets

async def test():
    async with websockets.connect('ws://localhost:8030') as ws:
        await ws.send('{\"type\":\"subscribe\",\"channel\":\"analysis\"}')
        msg = await ws.recv()
        print(f'收到：{msg}')

asyncio.run(test())
"
```

---

### 4.3 P2 次要功能回归

#### 4.3.1 定时任务

```bash
# 1. 查看定时任务状态
curl -s http://localhost:8080/api/scheduler/jobs \
  -H "Authorization: Bearer $TOKEN"

# 2. 查看执行历史
curl -s http://localhost:8080/api/scheduler/executions \
  -H "Authorization: Bearer $TOKEN"
```

---

#### 4.3.2 报告下载

```bash
# 1. 下载报告（Markdown）
curl -s http://localhost:8080/api/reports/600519_20260408/download?format=markdown \
  -H "Authorization: Bearer $TOKEN" > report.md

# 2. 下载报告（PDF）
curl -s http://localhost:8080/api/reports/600519_20260408/download?format=pdf \
  -H "Authorization: Bearer $TOKEN" > report.pdf
```

---

## 五、测试执行计划

### 5.1 阶段一：单元测试（30 分钟）

```bash
cd /root/stock-analyzer/tests

# P0 单元测试
python3 test_stock_analysis_blind_spots.py
python3 test_datasources.py
python3 test_redis_cache.py
python3 test_security.py
```

**通过标准**: 通过率 > 95%

---

### 5.2 阶段二：集成测试（45 分钟）

```bash
# 分析完整流程
python3 -m pytest test_integration_analysis.py -v

# 持仓管理流程
python3 -m pytest test_integration_positions.py -v

# 用户认证流程
python3 -m pytest test_integration_auth.py -v
```

**通过标准**: 所有核心场景通过

---

### 5.3 阶段三：端到端测试（30 分钟）

```bash
# 使用 Playwright 进行前端 E2E 测试
cd /root/stock-analyzer/frontend
npx playwright test e2e/
```

**通过标准**: 关键用户旅程通过

---

### 5.4 阶段四：性能测试（30 分钟）

```bash
# 使用 locust 进行压力测试
locust -f tests/perf_test.py --host=http://localhost:8080
```

**通过标准**:
- 登录 QPS > 50
- 分析响应 < 30s
- 搜索响应 < 1s

---

### 5.5 阶段五：安全测试（25 分钟）

```bash
# 运行安全测试套件
python3 test_security.py --backend http://localhost:8080

# OWASP ZAP 扫描（可选）
zap-baseline.py -t http://localhost:8080
```

**通过标准**: 无高危漏洞

---

## 六、测试报告模板

### 6.1 测试结果汇总

| 测试阶段 | 测试用例 | 通过 | 失败 | 跳过 | 通过率 |
|---------|---------|------|------|------|--------|
| 单元测试 | 205 | - | - | - | - |
| 集成测试 | 49 | - | - | - | - |
| E2E 测试 | 30 | - | - | - | - |
| 性能测试 | 5 | - | - | - | - |
| 安全测试 | 45 | - | - | - | - |
| **总计** | **334** | - | - | - | - |

---

### 6.2 缺陷清单

| ID | 模块 | 严重程度 | 描述 | 状态 |
|----|------|---------|------|------|
| BUG-001 | - | - | - | - |
| BUG-002 | - | - | - | - |

---

### 6.3 性能指标

| 接口 | P50 | P90 | P99 | 目标 | 状态 |
|------|-----|-----|-----|------|------|
| /api/v1/login | - | - | - | < 1s | - |
| /api/analysis/single | - | - | - | < 30s | - |
| /api/stocks/search | - | - | - | < 1s | - |

---

## 七、通过标准

### 7.1 准出条件

- ✅ 所有 P0 测试用例通过
- ✅ P1 测试用例通过率 > 95%
- ✅ 无严重（Critical）缺陷
- ✅ 性能指标达标
- ✅ 安全测试无高危漏洞

### 7.2 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 测试时间不足 | 中 | 高 | 优先 P0/P1 测试 |
| 环境不稳定 | 低 | 高 | 准备备用环境 |
| 数据源不可用 | 中 | 中 | Mock 数据源 |

---

## 八、执行清单

### 8.1 测试前准备

- [ ] 确认测试环境就绪
- [ ] 确认测试数据准备完成
- [ ] 确认测试工具已安装
- [ ] 备份生产数据（如适用）

### 8.2 测试执行

- [ ] 阶段一：单元测试
- [ ] 阶段二：集成测试
- [ ] 阶段三：端到端测试
- [ ] 阶段四：性能测试
- [ ] 阶段五：安全测试

### 8.3 测试后工作

- [ ] 生成测试报告
- [ ] 提交缺陷清单
- [ ] 评估通过标准
- [ ] 决定是否发布

---

## 九、自动化脚本

### 9.1 一键回归测试

```bash
#!/bin/bash
# run_regression.sh

echo "=== TradingAgents-CN 回归测试 ==="
echo "开始时间：$(date)"

# 阶段 1: 单元测试
echo "[1/5] 单元测试..."
cd /root/stock-analyzer/tests
python3 test_stock_analysis_blind_spots.py
python3 test_datasources.py
python3 test_redis_cache.py
python3 test_security.py

# 阶段 2: 集成测试
echo "[2/5] 集成测试..."
python3 -m pytest test_integration_*.py -v

# 阶段 3: E2E 测试
echo "[3/5] E2E 测试..."
cd /root/stock-analyzer/frontend
npx playwright test e2e/

# 阶段 4: 性能测试
echo "[4/5] 性能测试..."
locust -f tests/perf_test.py --headless -u 100 -r 10 --run-time 5m

# 阶段 5: 安全测试
echo "[5/5] 安全测试..."
cd /root/stock-analyzer/tests
python3 test_security.py --backend http://localhost:8080

echo "结束时间：$(date)"
echo "=== 回归测试完成 ==="
```

---

### 9.2 测试报告生成

```bash
#!/bin/bash
# generate_report.sh

python3 << 'EOF'
import json
from datetime import datetime

# 解析测试结果
results = {
    "timestamp": datetime.now().isoformat(),
    "version": "v1.2.2",
    "total_tests": 334,
    "passed": 0,
    "failed": 0,
    "skipped": 0
}

# 生成 Markdown 报告
report = f"""# 回归测试报告

**执行时间**: {results['timestamp']}
**版本**: {results['version']}

## 汇总

- 总测试数：{results['total_tests']}
- 通过：{results['passed']}
- 失败：{results['failed']}
- 跳过：{results['skipped']}
- 通过率：{results['passed']/results['total_tests']*100:.1f}%

## 详细结果

...
"""

with open('REGRESSION_TEST_REPORT.md', 'w') as f:
    f.write(report)

print("报告已生成：REGRESSION_TEST_REPORT.md")
EOF
```

---

## 十、附录

### 10.1 测试工具安装

```bash
# pytest
pip3 install pytest pytest-asyncio

# Playwright
npm install -D @playwright/test
npx playwright install

# Locust
pip3 install locust

# OWASP ZAP（可选）
docker pull owasp/zap2docker-stable
```

### 10.2 参考文档

- PRD.md - 产品需求文档
- USER_GUIDE.md - 用户指南
- CHANGELOG.md - 变更日志
- 各测试文件的详细注释

---

**方案制定者**: AI Assistant  
**审核状态**: 待审核  
**下次更新**: 2026-04-15
