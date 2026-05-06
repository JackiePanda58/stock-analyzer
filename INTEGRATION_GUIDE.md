"""
任务取消功能集成指南

本指南说明如何在api_server.py中集成task_manager.py模块

## 需要修改的部分

### 1. 导入task_manager模块

在api_server.py的导入部分添加：
```python
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
```

### 2. 修改_analysis_background_task函数

在函数开始处注册任务状态：
```python
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
    
    # ... 原有代码 ...
```

在_do_analysis函数中定期检查取消状态：
```python
def _do_analysis():
    try:
        # 定期检查取消状态
        if check_cancelled(task_id):
            sys_logger.info(f"[Background] Task {task_id} 被取消")
            return "⚠️ 分析已取消"
        
        # ... 原有分析代码 ...
        
    except Exception as e:
        # ... 原有异常处理 ...
```

### 3. 实现analysis_stop接口

替换原有的占位实现：
```python
@app.post("/api/analysis/{analysis_id}/stop")
async def analysis_stop(analysis_id: str, username: str = Depends(verify_token)):
    """
    取消分析任务
    """
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
        return {
            "success": True,
            "message": "任务取消成功"
        }
    else:
        return {
            "success": False,
            "message": "任务取消失败"
        }
```

### 4. 添加任务状态查询接口

```python
@app.get("/api/analysis/tasks/{task_id}/cancel-status")
async def analysis_cancel_status(task_id: str, username: str = Depends(verify_token)):
    """
    查询任务取消状态
    """
    status = get_task_status(task_id)
    return {
        "success": True,
        "data": {
            "task_id": task_id,
            "status": status,
            "is_cancelled": status == "cancelled"
        }
    }
```

## 测试方法

### 测试取消pending任务
```bash
# 1. 提交分析任务
curl -X POST http://localhost:8080/api/analysis/single \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"symbol":"159995","market":"A股","parameters":{"research_depth":3}}'

# 2. 立即取消任务
curl -X POST http://localhost:8080/api/analysis/159995_*/stop \
  -H "Authorization: Bearer $TOKEN"
```

### 测试取消running任务
```bash
# 1. 提交分析任务
# 2. 等待任务开始运行（约10-30秒）
# 3. 取消任务
curl -X POST http://localhost:8080/api/analysis/159995_*/stop \
  -H "Authorization: Bearer $TOKEN"
```

## 注意事项

1. Python无法强制终止线程，只能等待线程检查取消事件
2. 取消事件是异步的，可能需要几秒才能生效
3. 已完成的任务无法取消
4. 取消任务会清理临时文件
