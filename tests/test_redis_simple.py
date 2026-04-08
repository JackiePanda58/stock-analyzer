#!/usr/bin/env python3
"""Redis 缓存简单测试"""

import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

print("测试 Redis 连接...")
assert r.ping(), "Redis 连接失败"
print("✓ Redis 连接成功")

print("测试缓存设置/获取...")
r.setex("test_key", 60, "test_value")
assert r.get("test_key") == "test_value"
print("✓ 缓存设置/获取成功")

print("测试缓存 TTL...")
r.setex("test_ttl", 120, "value")
ttl = r.ttl("test_ttl")
assert 0 < ttl <= 120
print(f"✓ 缓存 TTL 正确：{ttl}秒")

print("测试 JSON 缓存...")
data = {"key": "value"}
r.setex("test_json", 60, json.dumps(data))
result = json.loads(r.get("test_json"))
assert result == data
print("✓ JSON 缓存成功")

print("\n✅ Redis 缓存测试全部通过！")
