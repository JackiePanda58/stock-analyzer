#!/usr/bin/env python3
"""验证 WebSocket 连接"""

import asyncio
import websockets

async def test_connection():
    try:
        print("尝试连接 WebSocket...")
        async with websockets.connect("ws://localhost:8030", close_timeout=5) as ws:
            print("✓ WebSocket 连接成功")
            
            # 发送测试消息
            await ws.send('{"type":"ping"}')
            print("✓ 发送 ping 成功")
            
            # 接收响应
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"✓ 收到响应：{response}")
            
            print("\n✅ WebSocket 服务正常！")
            return True
    except Exception as e:
        print(f"✗ WebSocket 连接失败：{e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_connection())
    exit(0 if result else 1)
