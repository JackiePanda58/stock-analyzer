"""
任务管理器 - 实现任务取消、状态管理和资源清理功能
"""
import os
import sys
import time
import threading
import traceback
from typing import Dict, Optional, Any
from datetime import datetime

# 全局任务取消事件字典
_task_cancel_events: Dict[str, threading.Event] = {}

# 全局任务状态字典
_task_states: Dict[str, str] = {}

# 全局任务线程字典
_task_threads: Dict[str, threading.Thread] = {}


def get_cancel_event(task_id: str) -> threading.Event:
    """获取或创建任务的取消事件"""
    if task_id not in _task_cancel_events:
        _task_cancel_events[task_id] = threading.Event()
    return _task_cancel_events[task_id]


def cancel_task(task_id: str) -> bool:
    """
    取消指定任务
    
    参数:
        task_id: 任务ID
        
    返回:
        bool: 是否成功取消
    """
    # 检查任务是否存在
    if task_id not in _task_states:
        return False
    
    # 检查任务状态
    current_status = _task_states.get(task_id, "unknown")
    if current_status in ["completed", "failed", "cancelled"]:
        return False
    
    # 设置取消事件
    cancel_event = get_cancel_event(task_id)
    cancel_event.set()
    
    # 更新任务状态
    _task_states[task_id] = "cancelled"
    
    # 尝试中断线程
    if task_id in _task_threads:
        thread = _task_threads[task_id]
        if thread.is_alive():
            # 注意：Python无法强制终止线程，只能等待线程检查取消事件
            # 这里我们只是标记取消，线程会在下一个检查点退出
            pass
    
    return True


def get_task_status(task_id: str) -> str:
    """获取任务状态"""
    return _task_states.get(task_id, "unknown")


def set_task_status(task_id: str, status: str):
    """设置任务状态"""
    _task_states[task_id] = status


def register_thread(task_id: str, thread: threading.Thread):
    """注册任务线程"""
    _task_threads[task_id] = thread


def unregister_thread(task_id: str):
    """注销任务线程"""
    if task_id in _task_threads:
        del _task_threads[task_id]


def cleanup_task(task_id: str, reports_dir: str = "/root/stock-analyzer/reports"):
    """
    清理任务资源
    
    参数:
        task_id: 任务ID
        reports_dir: 报告目录
    """
    # 删除取消事件
    if task_id in _task_cancel_events:
        del _task_cancel_events[task_id]
    
    # 删除线程引用
    if task_id in _task_threads:
        del _task_threads[task_id]
    
    # 删除临时报告文件
    try:
        # 从task_id提取股票代码
        parts = task_id.split("_")
        if len(parts) >= 2:
            symbol = parts[0]
            # 查找并删除对应的报告文件
            for fname in os.listdir(reports_dir):
                if fname.startswith(f"{symbol}_") and fname.endswith(".md"):
                    fpath = os.path.join(reports_dir, fname)
                    if os.path.exists(fpath):
                        os.remove(fpath)
    except Exception as e:
        print(f"清理报告文件失败: {e}")
    
    # 更新状态为已清理
    if task_id in _task_states:
        del _task_states[task_id]


def check_cancelled(task_id: str) -> bool:
    """
    检查任务是否被取消
    
    参数:
        task_id: 任务ID
        
    返回:
        bool: 是否已取消
    """
    cancel_event = _task_cancel_events.get(task_id)
    if cancel_event and cancel_event.is_set():
        return True
    return False


def run_with_cancel_check(task_id: str, func, *args, **kwargs):
    """
    运行函数并定期检查取消状态
    
    参数:
        task_id: 任务ID
        func: 要运行的函数
        *args, **kwargs: 函数参数
        
    返回:
        函数返回值或None（如果取消）
    """
    # 创建取消事件
    cancel_event = get_cancel_event(task_id)
    
    # 设置状态为运行中
    set_task_status(task_id, "running")
    
    try:
        # 运行函数
        result = func(*args, **kwargs)
        
        # 检查是否被取消
        if cancel_event.is_set():
            set_task_status(task_id, "cancelled")
            return None
        
        # 设置状态为完成
        set_task_status(task_id, "completed")
        return result
        
    except Exception as e:
        set_task_status(task_id, "failed")
        raise


def get_all_tasks() -> Dict[str, str]:
    """获取所有任务状态"""
    return _task_states.copy()


def get_active_tasks() -> Dict[str, str]:
    """获取活跃任务（pending或running）"""
    return {k: v for k, v in _task_states.items() if v in ["pending", "running"]}


def get_cancelled_tasks() -> Dict[str, str]:
    """获取已取消任务"""
    return {k: v for k, v in _task_states.items() if v == "cancelled"}
