"""
任务取消功能实现 - api_server.py集成补丁

本文件包含需要添加到api_server.py中的代码片段
以实现完整的任务取消功能
"""

# ==================== 需要添加到api_server.py的代码 ====================

# 1. 在文件开头添加导入
"""
from task_manager import (
    get_cancel_event,
    cancel_task,
    get_task_status,
    set_task_status,
    register_thread,
    unregister_thread,
    cleanup_task,
    check_cancelled
)
import threading
"""

# 2. 修改_analysis_background_task函数
"""
async def _analysis_background_task(
    task_id: str,
    symbol: str,
    target_date: str,
    username: str,
    user_context: dict,
    risk_level: str,
    selected_analysts: list,
    parameters: dict
):
    # 设置任务状态为pending
    set_task_status(task_id, "pending")
    
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='analysis_worker')

    loop = asyncio.get_running_loop()
    try:
        sys_logger.info(f"[Background] Task {task_id} 开始执行 {symbol}...")
        
        # 初始化进度追踪
        if api_progress_tracker.progress_tracker:
            await api_progress_tracker.progress_tracker.start_task(task_id, symbol)
            sys_logger.info(f"[Progress] Task {task_id} 进度追踪已启动")

        def _do_analysis():
            # 定期检查取消状态
            if check_cancelled(task_id):
                sys_logger.info(f"[Background] Task {task_id} 被取消")
                return "⚠️ 分析已取消"
            
            try:
                from tradingagents.graph.trading_graph import TradingAgentsGraph
                ta = TradingAgentsGraph(
                    selected_analysts=selected_analysts,
                    debug=False,
                    config=TRADING_CONFIG
                )
                # 使用带超时机制的函数（900秒）
                final_state, signal = _run_trading_graph_stream(
                    ta, symbol, target_date,
                    user_context={},
                    risk_level=risk_level,
                    selected_analysts=selected_analysts,
                    parameters={}
                )
                # 返回完整报告
                return final_state.get("final_trade_decision", "⚠️ 未找到最终报告")
            except TimeoutError as e:
                sys_logger.error(f"[Background] Task {task_id} 超时: {e}")
                return f"⚠️ 分析超时: {e}"
            except Exception as e:
                sys_logger.error(f"[Background] Task {task_id} 分析异常: {e}\\n{traceback.format_exc()}")
                return f"⚠️ 分析失败: {e}"

        final_report = await loop.run_in_executor(_executor, _do_analysis)
        
        # 检查是否被取消
        if check_cancelled(task_id):
            sys_logger.info(f"[Background] Task {task_id} 已取消，清理资源")
            cleanup_task(task_id)
            return
        
        sys_logger.info(f"[Background] Task {task_id} LangGraph 完成，正在写入结果...")
        
        # ... 原有代码 ...
"""

# 3. 替换analysis_stop接口
"""
@app.post("/api/analysis/{analysis_id}/stop")
async def analysis_stop(analysis_id: str, username: str = Depends(verify_token)):
    \"\"\"
    取消分析任务
    \"\"\"
    # 检查任务是否存在
    current_status = get_task_status(analysis_id)
    if current_status == "unknown":
        raise HTTPException(status_code=404, detail=f"任务 {analysis_id} 不存在")
    
    # 检查任务是否已完成
    if current_status in ["completed", "failed", "cancelled"]:
        return {
            "success": False,
            "message": f"任务已{current_status}，无法取消"
        }
    
    # 取消任务
    success = cancel_task(analysis_id)
    if success:
        sys_logger.info(f"[API] 任务 {analysis_id} 已取消")
        # 清理资源
        cleanup_task(analysis_id)
        return {
            "success": True,
            "message": "任务取消成功"
        }
    else:
        return {
            "success": False,
            "message": "任务取消失败"
        }
"""

# 4. 添加任务状态查询接口
"""
@app.get("/api/analysis/tasks/{task_id}/cancel-status")
async def analysis_cancel_status(task_id: str, username: str = Depends(verify_token)):
    \"\"\"
    查询任务取消状态
    \"\"\"
    status = get_task_status(task_id)
    return {
        "success": True,
        "data": {
            "task_id": task_id,
            "status": status,
            "is_cancelled": status == "cancelled"
        }
    }
"""

print("任务取消功能集成补丁已生成")
print("请参考INTEGRATION_GUIDE.md将上述代码添加到api_server.py中")
