"""
增强日志配置模块

提供结构化日志、性能指标、请求/响应日志等生产级日志功能。
"""
import logging
import os
import sys
import json
import time
import traceback
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager
import uuid


# ==================== 日志配置 ====================

class JSONFormatter(logging.Formatter):
    """JSON 格式日志处理器（用于结构化日志）"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加额外字段
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'user'):
            log_data['user'] = record.user
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'path'):
            log_data['path'] = record.path
        if hasattr(record, 'method'):
            log_data['method'] = record.method
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class ProductionFormatter(logging.Formatter):
    """生产环境可读格式日志处理器"""
    
    def format(self, record):
        # 彩色级别（如果支持）
        level_colors = {
            'DEBUG': '\033[36m',     # 青色
            'INFO': '\033[32m',      # 绿色
            'WARNING': '\033[33m',   # 黄色
            'ERROR': '\033[31m',     # 红色
            'CRITICAL': '\033[35m',  # 紫色
        }
        reset = '\033[0m'
        
        level = record.levelname
        color = level_colors.get(level, '')
        
        return (
            f"{color}[{level}]{reset} "
            f"{datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')} | "
            f"{record.name} | {record.module}:{record.lineno} | "
            f"{record.getMessage()}"
        )


def setup_production_logger(
    name: str = "StockAnalyzer",
    log_dir: str = "/root/stock-analyzer/logs",
    level: int = logging.DEBUG,
    enable_json: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 7,
    console_level: int = logging.INFO
) -> logging.Logger:
    """
    设置生产级日志
    
    参数:
        name: 日志器名称
        log_dir: 日志目录
        level: 日志级别
        enable_json: 是否启用 JSON 格式（适合日志收集系统）
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的备份文件数量
        console_level: 控制台日志级别
    
    返回:
        配置好的 Logger 实例
    """
    os.makedirs(log_dir, exist_ok=True)
    
    # 主日志文件
    log_file = os.path.join(log_dir, "system.log")
    # 错误日志文件（单独记录 ERROR 及以上）
    error_file = os.path.join(log_dir, "error.log")
    # 性能日志文件
    perf_file = os.path.join(log_dir, "performance.log")
    
    logger = logging.getLogger(name)
    
    # 避免重复绑定 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 选择格式
    formatter = JSONFormatter() if enable_json else ProductionFormatter()
    
    # 主日志文件 handler（INFO 及以上）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # 错误日志文件 handler（ERROR 及以上）
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    
    # 性能日志文件 handler
    perf_handler = RotatingFileHandler(
        perf_file,
        maxBytes=max_bytes,
        backupCount=3,
        encoding='utf-8'
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.setFormatter(formatter)
    perf_handler.addFilter(lambda record: hasattr(record, 'performance'))
    
    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    
    # 添加 handlers
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(perf_handler)
    logger.addHandler(console_handler)
    
    # 记录启动信息
    logger.info("=" * 60)
    logger.info("生产日志系统初始化完成")
    logger.info(f"日志目录：{log_dir}")
    logger.info(f"日志级别：{logging.getLevelName(level)}")
    logger.info(f"JSON 格式：{'启用' if enable_json else '禁用'}")
    logger.info("=" * 60)
    
    return logger


# ==================== 性能日志装饰器 ====================

def log_performance(logger: logging.Logger, operation: str = "操作"):
    """
    性能日志装饰器
    
    用法:
        @log_performance(sys_logger, "数据库查询")
        def query_db(...):
            ...
    """
    def decorator(func):
        import functools
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            request_id = str(uuid.uuid4())[:8]
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # 性能日志
                extra = {
                    'performance': True,
                    'request_id': request_id,
                    'duration_ms': round(duration_ms, 2),
                    'operation': operation
                }
                logger.info(
                    f"[PERF] {operation} 完成 | 耗时：{duration_ms:.2f}ms | ID: {request_id}",
                    extra=extra
                )
                
                # 慢操作警告
                if duration_ms > 1000:
                    logger.warning(
                        f"[SLOW] {operation} 耗时过长：{duration_ms:.2f}ms | ID: {request_id}",
                        extra=extra
                    )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"[ERROR] {operation} 失败 | 耗时：{duration_ms:.2f}ms | 错误：{str(e)} | ID: {request_id}",
                    exc_info=True,
                    extra={'performance': True, 'request_id': request_id, 'duration_ms': round(duration_ms, 2)}
                )
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            request_id = str(uuid.uuid4())[:8]
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                extra = {
                    'performance': True,
                    'request_id': request_id,
                    'duration_ms': round(duration_ms, 2),
                    'operation': operation
                }
                logger.info(
                    f"[PERF] {operation} 完成 | 耗时：{duration_ms:.2f}ms | ID: {request_id}",
                    extra=extra
                )
                
                if duration_ms > 1000:
                    logger.warning(
                        f"[SLOW] {operation} 耗时过长：{duration_ms:.2f}ms | ID: {request_id}",
                        extra=extra
                    )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"[ERROR] {operation} 失败 | 耗时：{duration_ms:.2f}ms | 错误：{str(e)} | ID: {request_id}",
                    exc_info=True,
                    extra={'performance': True, 'request_id': request_id, 'duration_ms': round(duration_ms, 2)}
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ==================== 上下文管理器 ====================

@contextmanager
def log_context(logger: logging.Logger, operation: str, **extra_fields):
    """
    日志上下文管理器
    
    用法:
        with log_context(sys_logger, "数据库事务", user_id=123):
            # 执行操作
            pass
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    logger.info(
        f"[START] {operation} 开始 | ID: {request_id}",
        extra={'request_id': request_id, **extra_fields}
    )
    
    try:
        yield request_id
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"[END] {operation} 完成 | 耗时：{duration_ms:.2f}ms | ID: {request_id}",
            extra={'request_id': request_id, 'duration_ms': round(duration_ms, 2), **extra_fields}
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[FAIL] {operation} 失败 | 耗时：{duration_ms:.2f}ms | 错误：{str(e)} | ID: {request_id}",
            exc_info=True,
            extra={'request_id': request_id, 'duration_ms': round(duration_ms, 2), **extra_fields}
        )
        raise


# ==================== 请求日志中间件 ====================

async def request_logging_middleware(request, call_next, logger: logging.Logger):
    """
    FastAPI 请求日志中间件
    
    用法:
        @app.middleware("http")
        async def log_requests(request, call_next):
            return await request_logging_middleware(request, call_next, sys_logger)
    """
    import time
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # 记录请求
    logger.info(
        f"[REQUEST] {request.method} {request.url.path} | ID: {request_id} | IP: {request.client.host if request.client else 'unknown'}",
        extra={
            'request_id': request_id,
            'path': str(request.url.path),
            'method': request.method
        }
    )
    
    try:
        response = await call_next(request)
        
        # 记录响应
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"[RESPONSE] {request.method} {request.url.path} | 状态：{response.status_code} | 耗时：{duration_ms:.2f}ms | ID: {request_id}",
            extra={
                'request_id': request_id,
                'path': str(request.url.path),
                'method': request.method,
                'status_code': response.status_code,
                'duration_ms': round(duration_ms, 2)
            }
        )
        
        # 添加请求 ID 到响应头
        response.headers["X-Request-ID"] = request_id
        
        return response
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[ERROR] {request.method} {request.url.path} | 耗时：{duration_ms:.2f}ms | 错误：{str(e)} | ID: {request_id}",
            exc_info=True,
            extra={
                'request_id': request_id,
                'path': str(request.url.path),
                'method': request.method,
                'duration_ms': round(duration_ms, 2)
            }
        )
        raise


# ==================== 初始化生产日志 ====================

# 创建生产日志实例
prod_logger = setup_production_logger(
    name="StockAnalyzer",
    log_dir="/root/stock-analyzer/logs",
    level=logging.DEBUG,
    enable_json=False,  # 生产环境建议启用 JSON 格式
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=7
)
