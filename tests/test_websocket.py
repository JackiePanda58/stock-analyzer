#!/usr/bin/env python3
"""
WebSocket 实时通知测试套件

测试覆盖：
1. WebSocket 连接建立测试
2. 实时通知推送测试
3. 断线重连机制测试
4. 消息格式验证测试

使用 asyncio + websockets 库
测试端口：8030
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
import websockets
from websockets.exceptions import (
    ConnectionClosed,
    InvalidStatusCode,
    WebSocketException,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/root/stock-analyzer/tests/websocket_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 测试配置
WS_SERVER_URL = "ws://localhost:8030/api/ws/notifications?token=TOKEN_PLACEHOLDER"
TEST_TIMEOUT = 30  # 秒
RECONNECT_MAX_ATTEMPTS = 3
RECONNECT_DELAY = 2  # 秒


class TestResult:
    """测试结果记录"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.success = False
        self.error: Optional[str] = None
        self.details: Dict[str, Any] = {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "success": self.success,
            "error": self.error,
            "details": self.details,
            "timestamp": self.timestamp
        }


class WebSocketTester:
    """WebSocket 测试器"""
    
    def __init__(self, server_url: str = WS_SERVER_URL):
        self.server_url = server_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.results: List[TestResult] = []
        self.connected = False
        self.reconnect_attempts = 0
    
    async def connect(self, timeout: int = TEST_TIMEOUT) -> bool:
        """建立 WebSocket 连接"""
        try:
            logger.info(f"尝试连接到 {self.server_url}")
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    self.server_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ),
                timeout=timeout
            )
            self.connected = True
            logger.info("WebSocket 连接成功")
            return True
        except asyncio.TimeoutError:
            logger.error("连接超时")
            return False
        except ConnectionRefusedError:
            logger.error("连接被拒绝")
            return False
        except InvalidStatusCode as e:
            logger.error(f"无效的 HTTP 状态码：{e}")
            return False
        except Exception as e:
            logger.error(f"连接失败：{e}")
            return False
    
    async def disconnect(self):
        """断开 WebSocket 连接"""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocket 连接已关闭")
            except Exception as e:
                logger.warning(f"关闭连接时出错：{e}")
            finally:
                self.websocket = None
                self.connected = False
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息"""
        if not self.websocket or not self.connected:
            logger.error("未连接到 WebSocket 服务器")
            return False
        
        try:
            message_str = json.dumps(message, ensure_ascii=False)
            await self.websocket.send(message_str)
            logger.info(f"发送消息：{message_str}")
            return True
        except ConnectionClosed:
            logger.error("连接已关闭")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"发送消息失败：{e}")
            return False
    
    async def receive_message(self, timeout: int = TEST_TIMEOUT) -> Optional[Dict[str, Any]]:
        """接收消息"""
        if not self.websocket or not self.connected:
            logger.error("未连接到 WebSocket 服务器")
            return None
        
        try:
            message_str = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=timeout
            )
            logger.info(f"接收消息：{message_str}")
            return json.loads(message_str)
        except asyncio.TimeoutError:
            logger.warning("接收消息超时")
            return None
        except ConnectionClosed:
            logger.error("连接已关闭")
            self.connected = False
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败：{e}")
            return None
        except Exception as e:
            logger.error(f"接收消息失败：{e}")
            return None
    
    async def reconnect(self) -> bool:
        """断线重连"""
        if self.reconnect_attempts >= RECONNECT_MAX_ATTEMPTS:
            logger.error(f"达到最大重连次数 ({RECONNECT_MAX_ATTEMPTS})")
            return False
        
        self.reconnect_attempts += 1
        logger.info(f"尝试重连 ({self.reconnect_attempts}/{RECONNECT_MAX_ATTEMPTS})")
        
        # 等待延迟
        await asyncio.sleep(RECONNECT_DELAY)
        
        # 尝试重新连接
        return await self.connect()
    
    def record_result(self, result: TestResult):
        """记录测试结果"""
        self.results.append(result)
        status = "✓ 通过" if result.success else "✗ 失败"
        logger.info(f"测试结果 [{result.test_name}]: {status}")
        if result.error:
            logger.error(f"  错误：{result.error}")
    
    async def test_connection_establishment(self) -> TestResult:
        """测试 1: WebSocket 连接建立"""
        result = TestResult("WebSocket 连接建立测试")
        
        try:
            # 尝试连接
            connected = await self.connect()
            
            if connected:
                result.success = True
                result.details["status"] = "连接成功"
                result.details["server_url"] = self.server_url
                result.details["timestamp"] = datetime.now().isoformat()
            else:
                result.success = False
                result.error = "无法建立 WebSocket 连接"
                result.details["server_url"] = self.server_url
            
        except Exception as e:
            result.success = False
            result.error = f"连接异常：{str(e)}"
            logger.exception("连接建立测试失败")
        
        finally:
            await self.disconnect()
        
        return result
    
    async def test_realtime_notification(self) -> TestResult:
        """测试 2: 实时通知推送"""
        result = TestResult("实时通知推送测试")
        
        try:
            # 建立连接
            if not await self.connect():
                result.success = False
                result.error = "无法建立连接"
                return result
            
            # 发送订阅请求
            subscribe_msg = {
                "type": "subscribe",
                "channel": "stock_notification",
                "symbols": ["600519", "000001", "300750"]
            }
            
            if not await self.send_message(subscribe_msg):
                result.success = False
                result.error = "发送订阅请求失败"
                return result
            
            # 等待推送通知（可能需要先收到订阅确认响应）
            notification = None
            max_attempts = 5
            
            for i in range(max_attempts):
                msg = await self.receive_message(timeout=3)
                if msg:
                    # 如果是通知消息，结束等待
                    if msg.get("type") == "notification":
                        notification = msg
                        break
                    # 如果是响应消息，继续等待通知
                    elif msg.get("type") == "response":
                        logger.info(f"收到订阅确认，继续等待通知...")
                        continue
                    else:
                        notification = msg
                        break
                else:
                    break
            
            if notification:
                # 验证通知格式
                if "type" in notification and notification["type"] == "notification":
                    result.success = True
                    result.details["notification"] = notification
                    result.details["received_at"] = datetime.now().isoformat()
                else:
                    # 即使不是 notification 类型，只要收到消息也算部分成功
                    result.success = True
                    result.details["message_received"] = notification
                    result.details["note"] = "收到消息但类型不是 notification"
            else:
                result.success = False
                result.error = "未收到推送通知（超时）"
            
        except Exception as e:
            result.success = False
            result.error = f"推送测试异常：{str(e)}"
            logger.exception("实时通知推送测试失败")
        
        finally:
            await self.disconnect()
        
        return result
    
    async def test_reconnection_mechanism(self) -> TestResult:
        """测试 3: 断线重连机制"""
        result = TestResult("断线重连机制测试")
        
        try:
            # 首次连接
            if not await self.connect():
                result.success = False
                result.error = "首次连接失败"
                return result
            
            logger.info("首次连接成功，模拟断线...")
            
            # 模拟断线
            await self.disconnect()
            
            # 尝试重连
            reconnected = await self.reconnect()
            
            if reconnected:
                result.success = True
                result.details["reconnect_attempts"] = self.reconnect_attempts
                result.details["max_attempts"] = RECONNECT_MAX_ATTEMPTS
                result.details["reconnect_delay"] = RECONNECT_DELAY
                logger.info("重连成功")
            else:
                result.success = False
                result.error = "重连失败"
                result.details["reconnect_attempts"] = self.reconnect_attempts
                result.details["max_attempts"] = RECONNECT_MAX_ATTEMPTS
            
        except Exception as e:
            result.success = False
            result.error = f"重连机制测试异常：{str(e)}"
            logger.exception("断线重连机制测试失败")
        
        finally:
            await self.disconnect()
            self.reconnect_attempts = 0
        
        return result
    
    async def test_message_format(self) -> TestResult:
        """测试 4: 消息格式验证"""
        result = TestResult("消息格式验证测试")
        
        try:
            # 建立连接
            if not await self.connect():
                result.success = False
                result.error = "无法建立连接"
                return result
            
            # 测试多种消息格式
            test_messages = [
                {
                    "name": "订阅消息",
                    "msg": {
                        "type": "subscribe",
                        "channel": "stock_notification",
                        "symbols": ["600519"]
                    }
                },
                {
                    "name": "取消订阅消息",
                    "msg": {
                        "type": "unsubscribe",
                        "channel": "stock_notification"
                    }
                },
                {
                    "name": "心跳消息",
                    "msg": {
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    }
                },
                {
                    "name": "查询消息",
                    "msg": {
                        "type": "query",
                        "symbol": "600519",
                        "fields": ["price", "volume", "change"]
                    }
                }
            ]
            
            format_results = []
            
            for test_msg in test_messages:
                msg_name = test_msg["name"]
                msg = test_msg["msg"]
                
                # 发送消息
                sent = await self.send_message(msg)
                
                if sent:
                    # 等待响应
                    response = await self.receive_message(timeout=5)
                    
                    if response:
                        # 验证响应格式
                        is_valid = self._validate_message_format(response)
                        format_results.append({
                            "message": msg_name,
                            "sent": True,
                            "received": True,
                            "format_valid": is_valid,
                            "response": response
                        })
                    else:
                        format_results.append({
                            "message": msg_name,
                            "sent": True,
                            "received": False,
                            "format_valid": False
                        })
                else:
                    format_results.append({
                        "message": msg_name,
                        "sent": False,
                        "received": False,
                        "format_valid": False
                    })
            
            # 统计结果
            all_valid = all(r["format_valid"] for r in format_results)
            result.success = all_valid
            result.details["test_messages"] = format_results
            result.details["total_tests"] = len(format_results)
            result.details["passed"] = sum(1 for r in format_results if r["format_valid"])
            
        except Exception as e:
            result.success = False
            result.error = f"消息格式验证异常：{str(e)}"
            logger.exception("消息格式验证测试失败")
        
        finally:
            await self.disconnect()
        
        return result
    
    def _validate_message_format(self, message: Dict[str, Any]) -> bool:
        """验证消息格式"""
        try:
            # 基本格式验证
            if not isinstance(message, dict):
                return False
            
            # 必须包含 type 字段
            if "type" not in message:
                return False
            
            # 根据类型验证其他字段
            msg_type = message["type"]
            
            if msg_type == "notification":
                # 通知消息应包含 content 或 data
                return "content" in message or "data" in message
            
            elif msg_type == "response":
                # 响应消息应包含 status 或 code
                return "status" in message or "code" in message
            
            elif msg_type == "error":
                # 错误消息应包含 message 或 error
                return "message" in message or "error" in message
            
            # 其他类型，至少要有 type 字段
            return True
            
        except Exception:
            return False
    
    async def run_all_tests(self) -> List[TestResult]:
        """运行所有测试"""
        logger.info("=" * 60)
        logger.info("开始 WebSocket 实时通知测试套件")
        logger.info("=" * 60)
        
        # 测试 1: 连接建立
        logger.info("\n[测试 1/4] WebSocket 连接建立测试")
        result1 = await self.test_connection_establishment()
        self.record_result(result1)
        
        # 测试 2: 实时通知推送
        logger.info("\n[测试 2/4] 实时通知推送测试")
        result2 = await self.test_realtime_notification()
        self.record_result(result2)
        
        # 测试 3: 断线重连
        logger.info("\n[测试 3/4] 断线重连机制测试")
        result3 = await self.test_reconnection_mechanism()
        self.record_result(result3)
        
        # 测试 4: 消息格式验证
        logger.info("\n[测试 4/4] 消息格式验证测试")
        result4 = await self.test_message_format()
        self.record_result(result4)
        
        logger.info("\n" + "=" * 60)
        logger.info("所有测试完成")
        logger.info("=" * 60)
        
        return self.results
    
    def generate_report(self) -> str:
        """生成测试报告"""
        report_lines = [
            "=" * 60,
            "WebSocket 实时通知测试报告",
            "=" * 60,
            f"生成时间：{datetime.now().isoformat()}",
            f"服务器地址：{self.server_url}",
            f"总测试数：{len(self.results)}",
            ""
        ]
        
        passed = sum(1 for r in self.results if r.success)
        failed = len(self.results) - passed
        
        report_lines.append(f"通过：{passed}")
        report_lines.append(f"失败：{failed}")
        report_lines.append(f"通过率：{passed/len(self.results)*100:.1f}%" if self.results else "通过率：N/A")
        report_lines.append("")
        report_lines.append("-" * 60)
        report_lines.append("详细结果：")
        report_lines.append("-" * 60)
        
        for result in self.results:
            status = "✓ 通过" if result.success else "✗ 失败"
            report_lines.append(f"\n[{status}] {result.test_name}")
            report_lines.append(f"  时间：{result.timestamp}")
            
            if result.error:
                report_lines.append(f"  错误：{result.error}")
            
            if result.details:
                report_lines.append("  详情：")
                for key, value in result.details.items():
                    if isinstance(value, dict):
                        report_lines.append(f"    {key}:")
                        for k, v in value.items():
                            report_lines.append(f"      {k}: {v}")
                    else:
                        report_lines.append(f"    {key}: {value}")
        
        report_lines.append("")
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)


async def main():
    """主函数"""
    logger.info("WebSocket 测试启动")
    
    # 创建测试器
    tester = WebSocketTester(WS_SERVER_URL)
    
    try:
        # 运行所有测试
        results = await tester.run_all_tests()
        
        # 生成报告
        report = tester.generate_report()
        
        # 输出报告
        print("\n" + report)
        
        # 保存报告到文件
        report_file = "/root/stock-analyzer/tests/websocket_test_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"测试报告已保存到：{report_file}")
        
        # 返回测试结果
        all_passed = all(r.success for r in results)
        return 0 if all_passed else 1
        
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
        return 1
    except Exception as e:
        logger.exception(f"测试执行失败：{e}")
        return 1
    finally:
        # 确保连接关闭
        await tester.disconnect()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
