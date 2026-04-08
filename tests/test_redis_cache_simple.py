#!/usr/bin/env python3
"""
Redis 缓存测试（简化版，不使用 pytest）
"""

import unittest
import redis
import json
import time

REDIS_HOST = 'localhost'
REDIS_PORT = 6379

class TestRedisCache(unittest.TestCase):
    """Redis 缓存测试"""
    
    def setUp(self):
        """设置 Redis 客户端"""
        self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    
    def test_redis_connection(self):
        """测试 Redis 连接"""
        result = self.redis_client.ping()
        self.assertTrue(result)
        print("✓ Redis 连接成功")
    
    def test_cache_set_get(self):
        """测试缓存设置和获取"""
        self.redis_client.setex("test_key", 60, "test_value")
        value = self.redis_client.get("test_key")
        self.assertEqual(value, "test_value")
        print("✓ 缓存设置和获取成功")
    
    def test_cache_ttl(self):
        """测试缓存 TTL"""
        self.redis_client.setex("test_ttl_key", 120, "test_value")
        ttl = self.redis_client.ttl("test_ttl_key")
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 120)
        print(f"✓ 缓存 TTL 正确：{ttl}秒")
    
    def test_cache_delete(self):
        """测试缓存删除"""
        self.redis_client.set("test_del_key", "test_value")
        self.redis_client.delete("test_del_key")
        value = self.redis_client.get("test_del_key")
        self.assertIsNone(value)
        print("✓ 缓存删除成功")
    
    def test_cache_json(self):
        """测试 JSON 缓存"""
        data = {"key": "value", "number": 123}
        self.redis_client.setex("test_json_key", 60, json.dumps(data))
        value = json.loads(self.redis_client.get("test_json_key"))
        self.assertEqual(data, value)
        print("✓ JSON 缓存成功")

if __name__ == "__main__":
    unittest.main(verbosity=2)
