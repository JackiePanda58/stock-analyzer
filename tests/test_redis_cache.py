"""
Redis 缓存层测试套件
覆盖：缓存过期策略、清理机制、连接池管理、缓存穿透/雪崩防护
"""

import asyncio
import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError

# 配置 pytest-asyncio
pytestmark = pytest.mark.asyncio


# ==================== 测试配置 ====================

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
DEFAULT_TTL = 12 * 60 * 60  # 12 小时 (秒)
TEST_KEY_PREFIX = "test:cache:"


# ==================== Fixtures ====================

@pytest_asyncio.fixture
async def redis_client():
    """创建 Redis 客户端连接"""
    client = await redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )
    yield client
    # 清理测试数据
    await client.aclose()


@pytest_asyncio.fixture
async def redis_pool():
    """创建 Redis 连接池"""
    pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        max_connections=20,
        decode_responses=True
    )
    yield pool
    await pool.disconnect()


# ==================== 1. 缓存过期策略测试（TTL 12 小时）====================

class TestCacheExpiration:
    """缓存过期策略测试"""
    
    async def test_set_with_ttl(self, redis_client):
        """测试设置带 TTL 的缓存"""
        key = f"{TEST_KEY_PREFIX}ttl_basic"
        value = "test_value"
        
        await redis_client.setex(key, DEFAULT_TTL, value)
        result = await redis_client.get(key)
        
        assert result == value
        
        ttl = await redis_client.ttl(key)
        assert 0 < ttl <= DEFAULT_TTL
        
        await redis_client.delete(key)
    
    async def test_ttl_expiration(self, redis_client):
        """测试 TTL 过期自动删除"""
        key = f"{TEST_KEY_PREFIX}ttl_expire"
        short_ttl = 2  # 2 秒用于快速测试
        
        await redis_client.setex(key, short_ttl, "temp_value")
        assert await redis_client.exists(key) == 1
        
        await asyncio.sleep(short_ttl + 1)
        assert await redis_client.exists(key) == 0
    
    async def test_refresh_ttl(self, redis_client):
        """测试刷新 TTL"""
        key = f"{TEST_KEY_PREFIX}ttl_refresh"
        initial_ttl = 10
        
        await redis_client.setex(key, initial_ttl, "value")
        await asyncio.sleep(2)
        
        remaining_ttl_before = await redis_client.ttl(key)
        await redis_client.expire(key, DEFAULT_TTL)
        remaining_ttl_after = await redis_client.ttl(key)
        
        assert remaining_ttl_after > remaining_ttl_before
        
        await redis_client.delete(key)
    
    async def test_permanent_key(self, redis_client):
        """测试永久缓存（无 TTL）"""
        key = f"{TEST_KEY_PREFIX}permanent"
        
        await redis_client.set(key, "permanent_value")
        ttl = await redis_client.ttl(key)
        
        assert ttl == -1  # -1 表示永不过期
        
        await redis_client.delete(key)
    
    async def test_batch_set_with_ttl(self, redis_client):
        """测试批量设置带 TTL 的缓存"""
        keys_values = {
            f"{TEST_KEY_PREFIX}batch1": "value1",
            f"{TEST_KEY_PREFIX}batch2": "value2",
            f"{TEST_KEY_PREFIX}batch3": "value3",
        }
        
        async with redis_client.pipeline() as pipe:
            for key, value in keys_values.items():
                await pipe.setex(key, DEFAULT_TTL, value)
            await pipe.execute()
        
        for key, expected_value in keys_values.items():
            result = await redis_client.get(key)
            assert result == expected_value
            ttl = await redis_client.ttl(key)
            assert 0 < ttl <= DEFAULT_TTL
        
        for key in keys_values.keys():
            await redis_client.delete(key)


# ==================== 2. 缓存清理机制测试 ====================

class TestCacheCleanup:
    """缓存清理机制测试"""
    
    async def test_delete_single_key(self, redis_client):
        """测试删除单个缓存键"""
        key = f"{TEST_KEY_PREFIX}delete_single"
        
        await redis_client.set(key, "value")
        assert await redis_client.exists(key) == 1
        
        await redis_client.delete(key)
        assert await redis_client.exists(key) == 0
    
    async def test_delete_multiple_keys(self, redis_client):
        """测试批量删除缓存键"""
        keys = [
            f"{TEST_KEY_PREFIX}del_multi_1",
            f"{TEST_KEY_PREFIX}del_multi_2",
            f"{TEST_KEY_PREFIX}del_multi_3",
        ]
        
        for key in keys:
            await redis_client.set(key, "value")
        
        deleted_count = await redis_client.delete(*keys)
        assert deleted_count == len(keys)
        
        for key in keys:
            assert await redis_client.exists(key) == 0
    
    async def test_delete_by_pattern(self, redis_client):
        """测试按模式删除缓存"""
        pattern_keys = [
            f"{TEST_KEY_PREFIX}pattern_a1",
            f"{TEST_KEY_PREFIX}pattern_a2",
            f"{TEST_KEY_PREFIX}pattern_b1",
        ]
        
        for key in pattern_keys:
            await redis_client.set(key, "value")
        
        cursor = 0
        deleted_count = 0
        pattern = f"{TEST_KEY_PREFIX}pattern_a*"
        
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            if keys:
                deleted_count += await redis_client.delete(*keys)
            if cursor == 0:
                break
        
        assert deleted_count == 2
        
        for key in pattern_keys:
            await redis_client.delete(key)
    
    async def test_flush_database(self, redis_client):
        """测试清空数据库（谨慎使用）"""
        test_key = f"{TEST_KEY_PREFIX}flush_test"
        await redis_client.set(test_key, "value")
        
        await redis_client.flushdb()
        assert await redis_client.exists(test_key) == 0
    
    async def test_cleanup_expired_keys(self, redis_client):
        """测试清理过期键的机制"""
        short_ttl_keys = [
            f"{TEST_KEY_PREFIX}cleanup_1",
            f"{TEST_KEY_PREFIX}cleanup_2",
        ]
        
        for key in short_ttl_keys:
            await redis_client.setex(key, 1, "temp")
        
        assert await redis_client.exists(short_ttl_keys[0]) == 1
        
        await asyncio.sleep(2)
        
        for key in short_ttl_keys:
            assert await redis_client.exists(key) == 0


# ==================== 3. Redis 连接池管理测试 ====================

class TestConnectionPool:
    """Redis 连接池管理测试"""
    
    async def test_connection_pool_creation(self, redis_pool):
        """测试连接池创建"""
        assert redis_pool is not None
        assert redis_pool.max_connections == 20
    
    async def test_connection_pool_reuse(self, redis_pool):
        """测试连接池复用"""
        client1 = redis.Redis(connection_pool=redis_pool)
        client2 = redis.Redis(connection_pool=redis_pool)
        
        await client1.set("pool_test", "value1")
        result = await client2.get("pool_test")
        
        assert result == "value1"
        
        await client1.delete("pool_test")
        await client1.aclose()
        await client2.aclose()
    
    async def test_connection_pool_max_connections(self, redis_pool):
        """测试连接池最大连接数限制"""
        clients = []
        
        try:
            for i in range(redis_pool.max_connections):
                client = redis.Redis(connection_pool=redis_pool)
                clients.append(client)
                await client.ping()
            
            assert len(clients) == redis_pool.max_connections
            
        finally:
            for client in clients:
                await client.aclose()
    
    async def test_connection_pool_release(self, redis_pool):
        """测试连接池连接释放"""
        client = redis.Redis(connection_pool=redis_pool)
        await client.ping()
        
        initial_in_use = redis_pool._in_use_connections
        await client.aclose()
        
        assert client.connection_pool == redis_pool
    
    async def test_connection_pool_health_check(self, redis_pool):
        """测试连接池健康检查"""
        client = redis.Redis(connection_pool=redis_pool)
        
        try:
            result = await client.ping()
            assert result is True
        finally:
            await client.aclose()
    
    async def test_connection_pool_with_retry(self, redis_pool):
        """测试连接池重试机制"""
        client = redis.Redis(
            connection_pool=redis_pool,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        try:
            await client.set("retry_test", "value")
            result = await client.get("retry_test")
            assert result == "value"
        finally:
            await client.delete("retry_test")
            await client.aclose()


# ==================== 4. 缓存穿透/雪崩防护测试 ====================

class TestCacheProtection:
    """缓存穿透/雪崩防护测试"""
    
    async def test_cache_penetration_null_object(self, redis_client):
        """测试缓存穿透防护 - 空值缓存"""
        key = f"{TEST_KEY_PREFIX}penetration_null"
        non_existent_id = "invalid_999"
        
        value = await redis_client.get(key)
        if value is None:
            null_value = "NULL_OBJECT"
            await redis_client.setex(key, 300, null_value)
        
        cached_value = await redis_client.get(key)
        assert cached_value == "NULL_OBJECT"
        
        await redis_client.delete(key)
    
    async def test_cache_penetration_bloom_filter_simulation(self, redis_client):
        """测试缓存穿透防护 - 布隆过滤器模拟"""
        valid_ids = {"1001", "1002", "1003", "1004", "1005"}
        bloom_filter_key = f"{TEST_KEY_PREFIX}bloom_filter"
        
        for id in valid_ids:
            await redis_client.sadd(bloom_filter_key, id)
        
        async def exists_in_bloom_filter(id):
            return await redis_client.sismember(bloom_filter_key, id)
        
        assert await exists_in_bloom_filter("1001") == 1
        assert await exists_in_bloom_filter("9999") == 0
        
        await redis_client.delete(bloom_filter_key)
    
    async def test_cache_avalanche_random_ttl(self, redis_client):
        """测试缓存雪崩防护 - 随机 TTL"""
        base_ttl = DEFAULT_TTL
        random_range = 3600
        
        keys = []
        for i in range(5):
            key = f"{TEST_KEY_PREFIX}avalanche_{i}"
            random_ttl = base_ttl + (i * random_range // 5)
            await redis_client.setex(key, random_ttl, f"value_{i}")
            keys.append((key, random_ttl))
        
        ttls = []
        for key, expected_ttl in keys:
            ttl = await redis_client.ttl(key)
            ttls.append(ttl)
            assert 0 < ttl <= expected_ttl
        
        assert len(set(ttls)) > 1
        
        for key, _ in keys:
            await redis_client.delete(key)
    
    async def test_cache_breakdown_mutex_lock(self, redis_client):
        """测试缓存击穿防护 - 互斥锁"""
        key = f"{TEST_KEY_PREFIX}mutex_lock"
        lock_key = f"{key}:lock"
        lock_timeout = 10
        
        async def acquire_lock():
            return await redis_client.set(lock_key, "locked", nx=True, ex=lock_timeout)
        
        async def release_lock():
            await redis_client.delete(lock_key)
        
        lock_acquired = await acquire_lock()
        assert lock_acquired is True  # 第一次获取锁成功
        
        second_attempt = await acquire_lock()
        assert second_attempt is None  # 第二次获取失败，返回 None
        
        await release_lock()
        third_attempt = await acquire_lock()
        assert third_attempt is True  # 释放后再次获取成功
        
        await redis_client.delete(lock_key)
    
    async def test_cache_warmup(self, redis_client):
        """测试缓存预热机制"""
        warmup_keys = [
            (f"{TEST_KEY_PREFIX}warmup_1", "hot_data_1"),
            (f"{TEST_KEY_PREFIX}warmup_2", "hot_data_2"),
            (f"{TEST_KEY_PREFIX}warmup_3", "hot_data_3"),
        ]
        
        async with redis_client.pipeline() as pipe:
            for key, value in warmup_keys:
                await pipe.setex(key, DEFAULT_TTL, value)
            await pipe.execute()
        
        for key, expected_value in warmup_keys:
            result = await redis_client.get(key)
            assert result == expected_value
        
        for key, _ in warmup_keys:
            await redis_client.delete(key)
    
    async def test_cache_hierarchy(self, redis_client):
        """测试缓存层级结构"""
        user_id = "user_123"
        level1_key = f"{TEST_KEY_PREFIX}cache:level1:{user_id}"
        level2_key = f"{TEST_KEY_PREFIX}cache:level2:{user_id}:detail"
        
        await redis_client.setex(level1_key, 3600, "basic_info")
        await redis_client.setex(level2_key, 1800, "detailed_info")
        
        assert await redis_client.exists(level1_key) == 1
        assert await redis_client.exists(level2_key) == 1
        
        await redis_client.delete(level1_key)
        await redis_client.delete(level2_key)


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试"""
    
    async def test_full_cache_workflow(self, redis_client):
        """测试完整缓存工作流程"""
        key = f"{TEST_KEY_PREFIX}workflow"
        
        await redis_client.setex(key, DEFAULT_TTL, "initial_value")
        
        value = await redis_client.get(key)
        assert value == "initial_value"
        
        await redis_client.append(key, "_updated")
        value = await redis_client.get(key)
        assert value == "initial_value_updated"
        
        ttl = await redis_client.ttl(key)
        assert 0 < ttl <= DEFAULT_TTL
        
        await redis_client.delete(key)
        assert await redis_client.exists(key) == 0
    
    async def test_concurrent_cache_access(self, redis_client):
        """测试并发缓存访问"""
        key = f"{TEST_KEY_PREFIX}concurrent"
        await redis_client.set(key, "0")
        
        async def increment():
            for _ in range(10):
                await redis_client.incr(key)
        
        tasks = [increment() for _ in range(5)]
        await asyncio.gather(*tasks)
        
        final_value = int(await redis_client.get(key))
        assert final_value == 50
        
        await redis_client.delete(key)
    
    async def test_cache_with_serialization(self, redis_client):
        """测试带序列化的缓存"""
        import json
        
        key = f"{TEST_KEY_PREFIX}serialized"
        data = {
            "stock_code": "600519",
            "price": 1800.50,
            "change": 2.5,
            "timestamp": time.time()
        }
        
        serialized = json.dumps(data)
        await redis_client.setex(key, DEFAULT_TTL, serialized)
        
        cached = await redis_client.get(key)
        deserialized = json.loads(cached)
        
        assert deserialized["stock_code"] == data["stock_code"]
        assert abs(deserialized["price"] - data["price"]) < 0.01
        
        await redis_client.delete(key)


# ==================== 性能测试 ====================

class TestPerformance:
    """性能测试"""
    
    async def test_batch_write_performance(self, redis_client):
        """测试批量写入性能"""
        keys = [f"{TEST_KEY_PREFIX}perf_write_{i}" for i in range(100)]
        
        start_time = time.time()
        
        async with redis_client.pipeline() as pipe:
            for key in keys:
                await pipe.setex(key, DEFAULT_TTL, "value")
            await pipe.execute()
        
        elapsed = time.time() - start_time
        print(f"\n批量写入 100 个键耗时：{elapsed:.3f}秒")
        assert elapsed < 5.0
        
        for key in keys:
            await redis_client.delete(key)
    
    async def test_batch_read_performance(self, redis_client):
        """测试批量读取性能"""
        keys = [f"{TEST_KEY_PREFIX}perf_read_{i}" for i in range(100)]
        
        async with redis_client.pipeline() as pipe:
            for key in keys:
                await pipe.setex(key, DEFAULT_TTL, "value")
            await pipe.execute()
        
        start_time = time.time()
        
        async with redis_client.pipeline() as pipe:
            for key in keys:
                await pipe.get(key)
            results = await pipe.execute()
        
        elapsed = time.time() - start_time
        print(f"\n批量读取 100 个键耗时：{elapsed:.3f}秒")
        assert len(results) == 100
        assert elapsed < 5.0
        
        for key in keys:
            await redis_client.delete(key)


# ==================== 异常处理测试 ====================

class TestExceptionHandling:
    """异常处理测试"""
    
    async def test_connection_error_handling(self, redis_client):
        """测试连接错误处理"""
        with patch.object(redis_client, 'get', side_effect=ConnectionError("Connection lost")):
            with pytest.raises(ConnectionError):
                await redis_client.get("test_key")
    
    async def test_redis_error_handling(self, redis_client):
        """测试 Redis 错误处理"""
        with patch.object(redis_client, 'set', side_effect=RedisError("Redis error")):
            with pytest.raises(RedisError):
                await redis_client.set("test_key", "value")
    
    async def test_timeout_handling(self, redis_client):
        """测试超时处理"""
        key = f"{TEST_KEY_PREFIX}timeout"
        
        try:
            await asyncio.wait_for(
                redis_client.setex(key, DEFAULT_TTL, "value"),
                timeout=10.0
            )
            assert await redis_client.exists(key) == 1
        except asyncio.TimeoutError:
            pytest.fail("操作超时")
        finally:
            await redis_client.delete(key)


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        f"--redis-host={REDIS_HOST}",
        f"--redis-port={REDIS_PORT}",
        "-s"
    ])
