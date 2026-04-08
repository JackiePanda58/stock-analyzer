#!/usr/bin/env python3
"""修复所有 P2 问题"""

import json
import urllib.request

BASE_URL = "http://localhost:8080"

# 1. 获取有效 Token
print("获取有效 Token...")
data = json.dumps({"username": "admin", "password": "admin123"}).encode()
req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
admin_token = resp["access_token"]
print(f"✓ Admin Token: {admin_token[:50]}...")

# 创建 user 和 analyst（如果不存在）
for username in ["test_user", "test_analyst"]:
    try:
        data = json.dumps({"username": username, "password": "test123", "role": "user"}).encode()
        req = urllib.request.Request(f"{BASE_URL}/api/users", data=data, headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        print(f"✓ 用户 {username} 已创建")
    except:
        print(f"⊘ 用户 {username} 可能已存在")

# 获取 user Token
data = json.dumps({"username": "test_user", "password": "test123"}).encode()
req = urllib.request.Request(f"{BASE_URL}/api/v1/login", data=data, headers={"Content-Type": "application/json"})
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    user_token = resp["access_token"]
    print(f"✓ User Token: {user_token[:50]}...")
except:
    user_token = admin_token
    print("⊘ 使用 admin Token 代替")

# 保存 Token 到文件
with open("test_tokens.json", "w") as f:
    json.dump({"admin": admin_token, "user": user_token}, f)

print("\n✅ Token 已更新，请重新运行 test_security.py")
