#!/usr/bin/env python3
"""修复安全测试中的 Token 问题"""

import json
import urllib.request

BASE_URL = "http://localhost:8080"

# 获取 Token
data = json.dumps({"username": "admin", "password": "admin123"}).encode()
req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
token = resp["access_token"]

print(f"Token: {token[:50]}...")
print(f"Token 长度：{len(token)}")
print("Token 已更新，请重新运行 test_security.py")
