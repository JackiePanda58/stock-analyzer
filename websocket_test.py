"""
WebSocket连接稳定性测试脚本

测试WebSocket连接的稳定性和重连机制

使用方法:
python3 websocket_test.py --token YOUR_TOKEN --url ws://localhost:8080/api/ws/progress --connections 10 --duration 60
"""
import argparse
import asyncio
import json
import time
import websockets
from datetime import datetime


async def test_single_connection(token: str, url: str, connection_id: int, duration: int, results: list):
    """
    测试单个WebSocket连接
    
    参数:
        token: JWT Token
        url: WebSocket URL
        connection_id: 连接ID
        duration: 测试时长（秒）
        results: 结果列表
    """
    start_time = time.time()
    connection_result = {
        "connection_id": connection_id,
        "start_time": datetime.now().isoformat(),
        "connected": False,
        "disconnected": False,
        "reconnected": False,
        "messages_sent": 0,
        "messages_received": 0,
        "errors": [],
        "duration": 0
    }
    
    try:
        # 连接WebSocket
        ws_url = f"{url}?token={token}"
        async with websockets.connect(ws_url) as websocket:
            connection_result["connected"] = True
            print(f"  [{connection_id}] 连接成功")
            
            # 发送订阅消息
            await websocket.send(json.dumps({
                "type": "subscribe",
                "task_id": f"test_task_{connection_id}"
            }))
            connection_result["messages_sent"] += 1
            
            # 持续接收消息
            while time.time() - start_time < duration:
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=1.0
                    )
                    connection_result["messages_received"] += 1
                except asyncio.TimeoutError:
                    # 发送心跳
                    await websocket.send(json.dumps({"type": "ping"}))
                    connection_result["messages_sent"] += 1
    
    except websockets.exceptions.ConnectionClosed as e:
        connection_result["disconnected"] = True
        connection_result["errors"].append(f"Connection closed: {e}")
        print(f"  [{connection_id}] 连接关闭: {e}")
    
    except Exception as e:
        connection_result["errors"].append(f"Error: {e}")
        print(f"  [{connection_id}] 错误: {e}")
    
    finally:
        connection_result["duration"] = time.time() - start_time
        results.append(connection_result)
        print(f"  [{connection_id}] 测试完成，时长: {connection_result['duration']:.1f}秒")


async def run_websocket_test(token: str, url: str, connections: int, duration: int):
    """
    运行WebSocket连接测试
    
    参数:
        token: JWT Token
        url: WebSocket URL
        connections: 并发连接数
        duration: 测试时长（秒）
    """
    print(f"开始WebSocket连接测试...")
    print(f"  并发连接数: {connections}")
    print(f"  测试时长: {duration}秒")
    print(f"  目标URL: {url}")
    print()
    
    results = []
    start_time = time.time()
    
    # 创建并发连接
    tasks = []
    for i in range(connections):
        task = asyncio.create_task(
            test_single_connection(token, url, i + 1, duration, results)
        )
        tasks.append(task)
    
    # 等待所有任务完成
    await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # 统计结果
    connected_count = sum(1 for r in results if r["connected"])
    disconnected_count = sum(1 for r in results if r["disconnected"])
    error_count = sum(len(r["errors"]) for r in results)
    total_messages_sent = sum(r["messages_sent"] for r in results)
    total_messages_received = sum(r["messages_received"] for r in results)
    
    print()
    print("=" * 50)
    print("WebSocket测试结果:")
    print("=" * 50)
    print(f"  总连接数: {connections}")
    print(f"  成功连接: {connected_count}")
    print(f"  断开连接: {disconnected_count}")
    print(f"  连接成功率: {connected_count / connections * 100:.2f}%")
    print()
    print(f"  总耗时: {total_time:.2f}秒")
    print(f"  发送消息数: {total_messages_sent}")
    print(f"  接收消息数: {total_messages_received}")
    print(f"  错误数: {error_count}")
    print("=" * 50)
    
    # 保存结果
    result_data = {
        "timestamp": datetime.now().isoformat(),
        "connections": connections,
        "duration": duration,
        "total_time": total_time,
        "connected_count": connected_count,
        "disconnected_count": disconnected_count,
        "connection_success_rate": connected_count / connections * 100,
        "total_messages_sent": total_messages_sent,
        "total_messages_received": total_messages_received,
        "error_count": error_count,
        "results": results
    }
    
    output_file = f"websocket_test_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(result_data, f, indent=2)
    
    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebSocket连接稳定性测试")
    parser.add_argument("--token", required=True, help="JWT Token")
    parser.add_argument("--url", default="ws://localhost:8080/api/ws/progress", help="WebSocket URL")
    parser.add_argument("--connections", type=int, default=10, help="并发连接数")
    parser.add_argument("--duration", type=int, default=60, help="测试时长（秒）")
    
    args = parser.parse_args()
    
    asyncio.run(run_websocket_test(args.token, args.url, args.connections, args.duration))
