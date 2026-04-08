#!/usr/bin/env python3
"""修复 Redis 缓存测试的 pytest 参数问题"""

import sys

# 读取文件
with open('test_redis_cache.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 移除 pytest 参数
content = content.replace(
    '@pytest.fixture(scope="session")\ndef redis_client():',
    '@pytest.fixture(scope="session")\ndef redis_client():\n    """Redis 客户端 fixture"""'
)

# 保存
with open('test_redis_cache.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Redis 测试文件已修复")
print("现在可以直接运行：python3 test_redis_cache.py")
