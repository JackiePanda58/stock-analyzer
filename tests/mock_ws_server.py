#!/usr/bin/env python3
"""
WebSocket 模拟服务器 - 用于测试

监听端口：8030
支持功能：
- 连接建立
- 消息接收和响应
- 推送通知
- 心跳检测
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Set, Dict, Any
import websockets
from websockets.server import WebSocketServerProtocol

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局连接集合
connected_clients: Set[WebSocketServerProtocol] = set()
subscriptions: Dict[WebSocketServerProtocol, list] = {}


async def handle_client(websocket: WebSocketServerProtocol):
    """处理客户端连接"""
    logger.info(f"新客户端连接：{websocket.remote_address}")
    connected_clients.add(websocket)
    subscriptions[websocket] = []
    
    try:
        async for message in websocket:
            try:
                # 解析消息
                data = json.loads(message)
                logger.info(f"收到消息：{data}")
                
                # 处理不同类型的消息
                msg_type = data.get("type", "")
                
                if msg_type == "subscribe":
                    # 处理订阅
                    channel = data.get("channel", "")
                    symbols = data.get("symbols", [])
                    subscriptions[websocket] = symbols
                    logger.info(f"客户端订阅：channel={channel}, symbols={symbols}")
                    
                    # 发送确认响应
                    response = {
                        "type": "response",
                        "status": "success",
                        "message": f"已订阅 {len(symbols)} 个股票",
                        "channel": channel
                    }
                    await websocket.send(json.dumps(response))
                    
                    # 模拟推送通知
                    await push_notification(websocket, symbols)
                
                elif msg_type == "unsubscribe":
                    # 处理取消订阅
                    channel = data.get("channel", "")
                    subscriptions[websocket] = []
                    logger.info(f"客户端取消订阅：channel={channel}")
                    
                    response = {
                        "type": "response",
                        "status": "success",
                        "message": "已取消订阅"
                    }
                    await websocket.send(json.dumps(response))
                
                elif msg_type == "heartbeat":
                    # 心跳响应
                    response = {
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                        "status": "alive"
                    }
                    await websocket.send(json.dumps(response))
                
                elif msg_type == "query":
                    # 查询响应
                    symbol = data.get("symbol", "")
                    response = {
                        "type": "response",
                        "status": "success",
                        "data": {
                            "symbol": symbol,
                            "price": 1700.00,
                            "volume": 10000,
                            "change": 2.5
                        }
                    }
                    await websocket.send(json.dumps(response))
                
                else:
                    # 未知消息类型
                    response = {
                        "type": "error",
                        "message": f"未知的消息类型：{msg_type}"
                    }
                    await websocket.send(json.dumps(response))
                    
            except json.JSONDecodeError:
                logger.error("无效的 JSON 格式")
                error_response = {
                    "type": "error",
                    "message": "无效的 JSON 格式"
                }
                await websocket.send(json.dumps(error_response))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"客户端断开连接：{websocket.remote_address}")
    finally:
        # 清理连接
        connected_clients.discard(websocket)
        subscriptions.pop(websocket, None)


async def push_notification(client: WebSocketServerProtocol, symbols: list):
    """推送通知给客户端"""
    if not symbols:
        return
    
    # 模拟延迟
    await asyncio.sleep(1)
    
    # 生成通知
    notification = {
        "type": "notification",
        "channel": "stock_notification",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "symbol": symbols[0] if symbols else "600519",
            "price": 1700.00,
            "change": 2.5,
            "change_percent": 1.47,
            "volume": 10000,
            "alert_type": "price_change"
        },
        "content": f"股票 {symbols[0] if symbols else '600519'} 价格变动提醒"
    }
    
    try:
        await client.send(json.dumps(notification, ensure_ascii=False))
        logger.info(f"推送通知：{notification}")
    except Exception as e:
        logger.error(f"推送通知失败：{e}")


async def broadcast_heartbeat():
    """定期广播心跳"""
    while True:
        await asyncio.sleep(20)
        
        if not connected_clients:
            continue
        
        heartbeat = {
            "type": "heartbeat",
            "timestamp": datetime.now().isoformat(),
            "server_status": "running",
            "connected_clients": len(connected_clients)
        }
        
        dead_clients = set()
        for client in connected_clients:
            try:
                await client.send(json.dumps(heartbeat))
            except Exception:
                dead_clients.add(client)
        
        # 清理断开的客户端
        for client in dead_clients:
            connected_clients.discard(client)
            subscriptions.pop(client, None)


async def main():
    """主函数"""
    logger.info("启动 WebSocket 服务器...")
    logger.info("监听端口：8030")
    
    # 启动心跳广播
    heartbeat_task = asyncio.create_task(broadcast_heartbeat())
    
    # 启动 WebSocket 服务器
    async with websockets.serve(handle_client, "localhost", 8030):
        logger.info("WebSocket 服务器已启动")
        logger.info("按 Ctrl+C 停止服务器")
        
        # 保持运行
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务器已停止")
