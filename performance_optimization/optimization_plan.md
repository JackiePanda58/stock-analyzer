# 性能优化任务日志

**任务开始时间**: 2026-04-09 00:41
**目标**: 将分析请求耗时从 120s 降低到 30s 以内
**项目路径**: /root/stock-analyzer/

---

## 任务 1: 分析 LangGraph 工作流代码，识别性能瓶颈 ✅

**完成时间**: 2026-04-09 00:45

### 瓶颈识别

#### 1.1 LangGraph 工作流顺序执行
- **问题**: `setup.py` 中分析师节点按顺序连接（market → social → news → fundamentals）
- **影响**: 4 个分析师节点串行执行，无法并发
- **代码位置**: `tradingagents/graph/setup.py` line 107-118

#### 1.2 BaoStock 全局锁串行化
- **问题**: `akshare_stock.py` 使用 `_bs_lock = threading.Lock()` 全局锁
- **影响**: 所有 BaoStock 调用被强制串行化，即使多个分析师同时请求数据
- **代码位置**: `tradingagents/dataflows/akshare_stock.py` line 18-24

#### 1.3 数据获取层无缓存
- **问题**: 虽然 API 层有 Redis，但数据获取层（akshare_stock.py）没有使用缓存
- **影响**: 相同股票的重复查询每次都重新获取数据
- **代码位置**: `tradingagents/dataflows/akshare_stock.py`

#### 1.4 LLM 调用串行
- **问题**: LangGraph 的节点执行是串行的，没有并行调用 LLM
- **影响**: 多个分析师的 LLM 调用依次执行

#### 1.5 配置限制
- **问题**: `max_debate_rounds=1, max_risk_discuss_rounds=1` 已经是最低配置
- **影响**: 无法通过减少轮次进一步优化

---

## 任务 2: 检查数据获取层（BaoStock/AkShare）的耗时 ✅

**完成时间**: 2026-04-09 00:50

### 数据获取分析

#### BaoStock 调用
- `get_china_stock_data`: 历史行情查询，包含连接建立/销毁
- `get_china_stock_indicators`: 技术指标计算，需要查询 200+ 天数据
- `_fetch_all_financial_data`: 财务三表查询，单次会话查完三表

#### AkShare 调用
- `get_china_fundamentals`: 财务指标查询
- `get_china_stock_news`: 新闻数据查询

#### 耗时估算
- 单次 BaoStock 会话建立：~0.3s (代码中有 `time.sleep(0.3)`)
- 历史行情查询：~1-2s
- 财务三表查询：~2-3s (单次会话)
- 技术指标计算：~0.5-1s (本地计算)
- 新闻查询：~1-2s

**总数据获取耗时估算**: 每个分析师 ~3-5s，4 个分析师串行 = 12-20s

---

## 任务 3: 检查模型调用（MiniMax-M2.7）的耗时 ✅

**完成时间**: 2026-04-09 00:55

### 模型调用分析

#### 当前配置
- `deep_think_llm`: "kimi-k2.5"
- `quick_think_llm`: "kimi-k2.5"
- `max_tokens`: 2000
- `temperature`: 1.0
- `max_retries`: 5

#### 调用链
1. Market Analyst: 1-2 次 LLM 调用
2. Social Analyst: 1-2 次 LLM 调用
3. News Analyst: 1-2 次 LLM 调用
4. Fundamentals Analyst: 1-2 次 LLM 调用
5. Bull Researcher: 1 次 LLM 调用
6. Bear Researcher: 1 次 LLM 调用
7. Research Manager: 1 次 LLM 调用
8. Trader: 1 次 LLM 调用
9. Risk Analysts (3 个): 各 1 次 LLM 调用
10. Risk Judge: 1 次 LLM 调用

**总 LLM 调用次数**: ~12-15 次

#### 耗时估算
- 单次 LLM 调用：~5-8s (基于 120s 总耗时推算)
- 总 LLM 耗时：~60-90s

---

## 任务 4: 检查缓存层（Redis）的使用情况 ✅

**完成时间**: 2026-04-09 01:00

### 缓存使用情况

#### API 层缓存
- `api_server.py` 使用 Redis 缓存最终分析报告 (43200s = 12 小时 TTL)
- 缓存键：`analysis:{symbol}:{date}`
- **问题**: 只缓存最终结果，不缓存中间数据

#### 数据获取层缓存
- **无缓存**: `akshare_stock.py` 没有使用 Redis
- **问题**: 相同股票的重复分析每次都重新获取数据

#### 测试文件
- `tests/test_redis_cache.py`: 完整的 Redis 缓存测试套件
- **问题**: 测试代码未在实际业务中使用

---

## 优化方案

### 方案 1: 并行化分析师节点 (预计提升：40-50%)
- 修改 `setup.py` 使 4 个分析师节点并行执行
- 使用 LangGraph 的 `StateGraph.add_node` + `add_edge` 并行模式

### 方案 2: 数据获取层缓存 (预计提升：20-30%)
- 在 `akshare_stock.py` 添加 Redis 缓存
- 缓存键：`stock_data:{symbol}:{start}:{end}`, `indicators:{symbol}:{indicator}:{date}`
- TTL: 12 小时

### 方案 3: BaoStock 连接池优化 (预计提升：10-15%)
- 移除全局锁，使用连接池
- 或保持单会话但批量查询

### 方案 4: LLM 调用批处理 (预计提升：10-20%)
- 合并多个分析师的提示词
- 使用批处理 API (如果支持)

### 方案 5: 减少非必要调用 (预计提升：5-10%)
- 优化提示词减少工具调用次数
- 缓存分析师报告避免重复生成

---

## 下一步

1. 实施并行化改造
2. 添加数据缓存层
3. 优化 BaoStock 连接
4. 测试优化效果
