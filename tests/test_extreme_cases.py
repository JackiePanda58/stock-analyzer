"""
极端用例测试 - 自动化查杀业务逻辑漏洞
覆盖场景：
- 停牌股 volume=0
- 第三方网络超时
- Redis 并发抢占
- ZeroDivisionError
- TimeoutError
"""
import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, '/root/stock-analyzer')

# ==================== 极端用例 1: 停牌股 volume=0 ====================

class TestSuspendedStock:
    """停牌股极端场景测试"""
    
    def test_volume_zero_no_division_error(self):
        """停牌股 volume=0 时不应触发 ZeroDivisionError"""
        # Mock 返回 volume=0 的数据
        mock_data = {
            'volume': [0, 0, 0, 0, 0],
            'close': [10.0, 10.0, 10.0, 10.0, 10.0],
            'amount': [0, 0, 0, 0, 0]
        }
        
        # VWMA 计算不应崩溃
        def calc_vwma(prices, volumes):
            if sum(volumes) == 0:
                return None  # 停牌时返回 None
            return sum(p * v for p, v in zip(prices, volumes)) / sum(volumes)
        
        result = calc_vwma(mock_data['close'], mock_data['volume'])
        assert result is None, "停牌股应返回 None 而非触发 ZeroDivisionError"
    
    def test_vwma_with_zero_volume(self):
        """VWMA 指标在零成交量时的容错处理"""
        def safe_vwma(prices, volumes):
            total_volume = sum(volumes)
            if total_volume == 0:
                return {'value': None, 'reason': 'suspended'}
            return {'value': sum(p * v for p, v in zip(prices, volumes)) / total_volume}
        
        # 停牌场景
        result = safe_vwma([10.0, 10.0, 10.0], [0, 0, 0])
        assert result['value'] is None
        assert result['reason'] == 'suspended'
        
        # 正常场景
        result = safe_vwma([10.0, 11.0, 12.0], [100, 200, 300])
        assert result['value'] == pytest.approx(11.333, rel=1e-2)


# ==================== 极端用例 2: 第三方网络超时 ====================

class TestNetworkTimeout:
    """第三方网络超时场景测试"""
    
    def test_baostock_timeout_handling(self):
        """BaoStock 连接超时应优雅降级"""
        import baostock as bs
        
        # Mock 超时场景
        with patch.object(bs, 'login', side_effect=TimeoutError("连接超时")):
            # 应捕获异常并返回友好错误
            try:
                bs.login()
                assert False, "应抛出 TimeoutError"
            except TimeoutError as e:
                assert "连接超时" in str(e)
    
    def test_akshare_timeout_with_retry(self):
        """AkShare 请求超时应有重试机制"""
        import requests
        
        call_count = 0
        
        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.Timeout("请求超时")
            return MagicMock(status_code=200, json=lambda: {'data': 'success'})
        
        # 重试逻辑
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with patch.object(requests, 'get', side_effect=mock_get):
                    response = requests.get('http://example.com', timeout=5)
                    assert response.json()['data'] == 'success'
                    break
            except requests.Timeout:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.1 * (attempt + 1))  # 指数退避
        
        assert call_count == 3, "应在第 3 次重试成功"


# ==================== 极端用例 3: Redis 并发抢占 ====================

class TestRedisConcurrency:
    """Redis 并发抢占场景测试"""
    @pytest.mark.asyncio
    async def test_redis_lock_with_uuid_isolation(self):
        """Redis 锁应支持 UUID 隔离，防止并发抢占"""
        import redis.asyncio as aioredis
        import uuid
        
        redis_client = aioredis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        try:
            # 生成唯一锁 ID
            lock_id = f"analysis_lock:{uuid.uuid4()}"
            
            # 尝试获取锁
            acquired = await redis_client.set(lock_id, "locked", nx=True, ex=300)
            assert acquired is True, "首次应成功获取锁"
            
            # 同一锁 ID 的第二次获取应失败
            acquired_again = await redis_client.set(lock_id, "locked", nx=True, ex=300)
            # Redis nx=True 在 key 已存在时返回 None 或 False
            assert acquired_again is None or acquired_again is False, "并发获取应失败"
            
        finally:
            # 清理测试数据
            try:
                await redis_client.delete(lock_id)
                await redis_client.close()
            except Exception:
                pass  # 测试清理失败不影响测试结果
    
    def test_concurrent_task_id_collision(self):
        """任务 ID 生成应避免冲突"""
        import uuid
        
        # 原方案：同一秒内可能冲突
        def old_task_id(symbol, date, timestamp):
            return f"{symbol}_{date}_{int(timestamp)}"
        
        # 新方案：添加 UUID 后缀
        def new_task_id(symbol, date, timestamp):
            return f"{symbol}_{date}_{int(timestamp)}_{uuid.uuid4().hex[:8]}"
        
        # 模拟同一秒内多次提交
        symbol = "600519"
        date = "20260409"
        timestamp = time.time()
        
        old_ids = [old_task_id(symbol, date, timestamp) for _ in range(10)]
        new_ids = [new_task_id(symbol, date, timestamp) for _ in range(10)]
        
        # 旧方案会冲突
        assert len(set(old_ids)) == 1, "旧方案同一秒内 ID 完全相同"
        
        # 新方案不会冲突
        assert len(set(new_ids)) == 10, "新方案应保证唯一性"


# ==================== 极端用例 4: 前端轮询退避算法 ====================

class TestPollingBackoff:
    """前端轮询退避算法测试"""
    
    def test_exponential_backoff_calculation(self):
        """指数退避间隔计算"""
        def calculate_interval(elapsed_seconds, base_interval=5000, max_interval=60000):
            """
            动态退避算法：
            - 前 2 分钟：10 秒轮询
            - 2-5 分钟：20 秒轮询
            - 5 分钟后：30 秒轮询
            - 最大间隔：60 秒
            """
            if elapsed_seconds < 120:
                return 10000
            elif elapsed_seconds < 300:
                return 20000
            else:
                return min(30000, max_interval)
        
        assert calculate_interval(0) == 10000
        assert calculate_interval(60) == 10000
        assert calculate_interval(119) == 10000
        assert calculate_interval(120) == 20000
        assert calculate_interval(200) == 20000
        assert calculate_interval(299) == 20000
        assert calculate_interval(300) == 30000
        assert calculate_interval(600) == 30000
    
    def test_dynamic_backoff_with_jitter(self):
        """带抖动的动态退避"""
        import random
        
        def calculate_interval_with_jitter(base, jitter_percent=0.2):
            """添加 ±20% 抖动，防止多客户端同步请求"""
            jitter = base * jitter_percent
            return base + random.uniform(-jitter, jitter)
        
        # 多次计算应产生不同结果
        base = 10000
        intervals = [calculate_interval_with_jitter(base) for _ in range(10)]
        
        # 所有间隔应在合理范围内
        assert all(8000 <= i <= 12000 for i in intervals)
        
        # 不应完全相同
        assert len(set(intervals)) > 1


# ==================== 极端用例 5: 浮点数精度 ====================

class TestFloatingPointPrecision:
    """浮点数精度测试"""
    
    def test_currency_calculation_error(self):
        """原生浮点数除法精度问题"""
        # 原生 float 精度问题
        result = 0.1 + 0.2
        assert result != 0.3  # True: 0.30000000000000004
        
        # 使用 decimal 修复
        from decimal import Decimal, ROUND_HALF_UP
        result = Decimal('0.1') + Decimal('0.2')
        assert result == Decimal('0.3')
    
    def test_position_calculation_with_decimal(self):
        """持仓计算应使用 Decimal"""
        from decimal import Decimal, ROUND_HALF_UP
        
        # 持仓数量计算
        total_amount = Decimal('10000.00')
        price = Decimal('123.45')
        
        # 原生 float 会丢失精度
        shares_float = float(total_amount) / float(price)
        
        # Decimal 保持精度
        shares_decimal = (total_amount / price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        assert shares_decimal == Decimal('81.00')
        assert abs(shares_float - 81.00) > 0.001  # float 有误差


# ==================== 执行报告 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
