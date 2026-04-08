#!/usr/bin/env python3
"""启动 WebSocket 服务"""

import subprocess
import sys

print("启动 WebSocket 服务...")
subprocess.Popen([
    sys.executable,
    '/root/stock-analyzer/ws_server.py'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("WebSocket 服务已启动（端口 8030）")
