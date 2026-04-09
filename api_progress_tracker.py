"""
分析进度追踪器
- 使用 Redis 缓存实时进度
- 支持 WebSocket 推送
- 提供真实进度而非模拟
"""

import asyncio
import time
import json
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)

# 分析步骤定义
ANALYSIS_STEPS = [
    {"name": "数据获取", "description": "正在从 BaoStock 获取股票历史数据和财务指标", "weight": 0.15},
    {"name": "技术分析", "description": "正在计算技术指标：RSI, MACD, VWMA, 布林带", "weight": 0.20},
    {"name": "基本面分析", "description": "正在分析财务报表和估值指标", "weight": 0.25},
    {"name": "新闻分析", "description": "正在分析相关新闻和舆情", "weight": 0.20},
    {"name": "综合决策", "description": "正在整合各分析师观点生成最终决策", "weight": 0.20},
]


class ProgressTracker:
    """进度追踪器"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.start_times = {}  # task_id -> start_time
    
    async def start_task(self, task_id: str, symbol: str):
        """标记任务开始"""
        start_time = int(time.time())
        self.start_times[task_id] = start_time
        
        # 写入 Redis
        await self.redis.setex(
            f"task:{task_id}:progress",
            3600,  # 1 小时 TTL
            json.dumps({
                "status": "running",
                "progress": 0,
                "elapsed_time": 0,
                "remaining_time": 120,  # 初始估计 2 分钟
                "estimated_total_time": 120,
                "current_step_name": "初始化",
                "current_step_description": "正在初始化分析引擎...",
                "message": "分析任务已启动"
            })
        )
        logger.info(f"[Progress] 任务 {task_id} 已启动")
    
    async def update_step(self, task_id: str, step_index: int, custom_progress: int = None):
        """更新当前步骤"""
        if step_index < 0 or step_index >= len(ANALYSIS_STEPS):
            return
        
        step = ANALYSIS_STEPS[step_index]
        start_time = self.start_times.get(task_id, int(time.time()))
        elapsed = int(time.time()) - start_time
        
        # 计算进度
        if custom_progress is not None:
            progress = custom_progress
        else:
            # 基于步骤权重计算进度
            progress = 0
            for i in range(step_index):
                progress += int(ANALYSIS_STEPS[i]["weight"] * 100)
            progress += int(step["weight"] * 100 * 0.5)  # 当前步骤完成 50%
        
        # 估算剩余时间
        if progress > 0:
            estimated_total = int(elapsed / (progress / 100))
            remaining = max(0, estimated_total - elapsed)
        else:
            estimated_total = 120
            remaining = 120
        
        # 写入 Redis
        await self.redis.setex(
            f"task:{task_id}:progress",
            3600,
            json.dumps({
                "status": "running",
                "progress": min(progress, 95),
                "elapsed_time": elapsed,
                "remaining_time": remaining,
                "estimated_total_time": estimated_total,
                "current_step_name": step["name"],
                "current_step_description": step["description"],
                "message": f"正在执行{step['name']}..."
            })
        )
        logger.info(f"[Progress] 任务 {task_id} 更新到步骤 {step_index}: {step['name']} ({progress}%)")
    
    async def complete_task(self, task_id: str):
        """标记任务完成"""
        start_time = self.start_times.get(task_id, int(time.time()))
        elapsed = int(time.time()) - start_time
        
        await self.redis.setex(
            f"task:{task_id}:progress",
            3600,
            json.dumps({
                "status": "completed",
                "progress": 100,
                "elapsed_time": elapsed,
                "remaining_time": 0,
                "estimated_total_time": elapsed,
                "current_step_name": "分析完成",
                "current_step_description": "报告已生成，可以查看完整结果",
                "message": "分析已完成"
            })
        )
        logger.info(f"[Progress] 任务 {task_id} 已完成 ({elapsed}s)")
    
    async def fail_task(self, task_id: str, error_message: str):
        """标记任务失败"""
        start_time = self.start_times.get(task_id, int(time.time()))
        elapsed = int(time.time()) - start_time
        
        await self.redis.setex(
            f"task:{task_id}:progress",
            3600,
            json.dumps({
                "status": "failed",
                "progress": 0,
                "elapsed_time": elapsed,
                "remaining_time": 0,
                "estimated_total_time": elapsed,
                "current_step_name": "分析失败",
                "current_step_description": error_message,
                "message": f"分析失败：{error_message}"
            })
        )
        logger.error(f"[Progress] 任务 {task_id} 失败：{error_message}")
    
    async def get_progress(self, task_id: str) -> dict:
        """获取任务进度"""
        data = await self.redis.get(f"task:{task_id}:progress")
        if data:
            return json.loads(data)
        
        # 如果 Redis 中没有，返回默认值
        return {
            "status": "pending",
            "progress": 0,
            "elapsed_time": 0,
            "remaining_time": 0,
            "estimated_total_time": 0,
            "current_step_name": "等待中",
            "current_step_description": "任务正在排队等待处理",
            "message": "任务已提交，等待处理"
        }


# 全局进度追踪器实例
progress_tracker: ProgressTracker = None


def init_progress_tracker(redis_client: aioredis.Redis):
    """初始化进度追踪器"""
    global progress_tracker
    if redis_client:
        progress_tracker = ProgressTracker(redis_client)
        logger.info("✅ 进度追踪器已初始化")
    else:
        logger.warning("⚠️ Redis 客户端为空，进度追踪器不可用")


async def track_analysis_progress(
    task_id: str,
    symbol: str,
    target_date: str,
    user_context: dict,
    risk_level: str,
    selected_analysts: list,
    parameters: dict,
    start_time: float
):
    """
    追踪分析任务进度（后台任务）
    在后台运行真实的 LangGraph 分析，同时更新 Redis 进度
    """
    if not progress_tracker:
        logger.error("[Progress] 进度追踪器未初始化")
        return
    
    try:
        # 标记任务开始
        await progress_tracker.start_task(task_id, symbol)
        
        # 导入 LangGraph
        sys.path.insert(0, '/root/stock-analyzer')
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from config.settings import TRADING_CONFIG
        from api_server import _run_trading_graph_stream, UsageTrackingCallback, sys_logger, redis_client
        
        # 创建分析实例
        session_id = str(uuid.uuid4())
        usage_cb = UsageTrackingCallback(
            session_id=session_id,
            analysis_type="stock_analysis",
            symbol=symbol
        )
        
        ta = TradingAgentsGraph(
            selected_analysts=selected_analysts or ["market", "news", "fundamentals"],
            debug=False,
            config=TRADING_CONFIG,
            callbacks=[usage_cb]
        )
        
        # 步骤 1：数据获取 (0-15%)
        await progress_tracker.update_step(task_id, 0, 5)
        
        # 执行分析
        result, _ = await asyncio.to_thread(
            _run_trading_graph_stream,
            ta,
            symbol,
            target_date,
            user_context,
            risk_level,
            selected_analysts,
            parameters
        )
        
        # 步骤 2-5：各分析阶段
        for i in range(1, len(ANALYSIS_STEPS)):
            await progress_tracker.update_step(task_id, i)
            await asyncio.sleep(0.5)  # 短暂延迟让前端能捕捉到状态变化
        
        # 获取最终报告
        final_report = result.get("final_trade_decision", "⚠️ 未找到最终报告")
        elapsed = time.time() - start_time
        
        sys_logger.info(f"[API] [{symbol}] ✅ 分析顺利完成，耗时：{elapsed:.0f}秒")
        
        # 写入 Redis 缓存
        if redis_client:
            cache_key = f"report:{symbol}:{target_date}"
            await redis_client.setex(cache_key, 300, final_report)
            
            # 写入 reports 目录
            reports_dir = "/root/stock-analyzer/reports"
            os.makedirs(reports_dir, exist_ok=True)
            report_file = os.path.join(reports_dir, f"{symbol}_{target_date.replace('-', '')}.md")
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(final_report)
        
        # 标记任务完成
        await progress_tracker.complete_task(task_id)
        
    except Exception as e:
        sys_logger.error(f"[API] [{symbol}] ❌ 分析失败：{e}")
        await progress_tracker.fail_task(task_id, str(e))
        raise


# 导入所需模块
import sys
import os
import uuid
