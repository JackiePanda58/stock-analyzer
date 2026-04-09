"""
统一错误处理模块

提供标准化的异常类和错误响应格式，确保所有 API 错误一致。
"""
from fastapi import HTTPException, status
from typing import Optional, Dict, Any
from datetime import datetime
import json


# ==================== 错误码规范 ====================
# 格式：ERR_<MODULE>_<CODE>
# 模块：AUTH, API, DATA, DB, CACHE, FILE, EXTERNAL, VALIDATION, SYSTEM

class ErrorCode:
    """标准错误码定义"""
    # 通用错误 (1000-1999)
    ERR_SUCCESS = 0
    ERR_UNKNOWN = 1000
    ERR_INTERNAL = 1001
    ERR_NOT_FOUND = 1002
    ERR_PERMISSION_DENIED = 1003
    ERR_RATE_LIMITED = 1004
    ERR_SERVICE_UNAVAILABLE = 1005
    ERR_TIMEOUT = 1006
    
    # 认证授权 (2000-2999)
    ERR_AUTH_INVALID_TOKEN = 2000
    ERR_AUTH_TOKEN_EXPIRED = 2001
    ERR_AUTH_INVALID_CREDENTIALS = 2002
    ERR_AUTH_MISSING_TOKEN = 2003
    ERR_AUTH_USER_NOT_FOUND = 2004
    
    # API 请求 (3000-3999)
    ERR_API_INVALID_REQUEST = 3000
    ERR_API_BAD_PARAMETERS = 3001
    ERR_API_METHOD_NOT_ALLOWED = 3002
    ERR_API_TOO_MANY_REQUESTS = 3003
    
    # 数据相关 (4000-4999)
    ERR_DATA_NOT_FOUND = 4000
    ERR_DATA_INVALID_FORMAT = 4001
    ERR_DATA_DUPLICATE = 4002
    ERR_DATA_SYNC_FAILED = 4003
    
    # 数据库 (5000-5999)
    ERR_DB_CONNECTION = 5000
    ERR_DB_QUERY = 5001
    ERR_DB_TRANSACTION = 5002
    ERR_DB_CONSTRAINT = 5003
    
    # 缓存 (6000-6999)
    ERR_CACHE_CONNECTION = 6000
    ERR_CACHE_MISS = 6001
    ERR_CACHE_WRITE = 6002
    
    # 文件 (7000-7999)
    ERR_FILE_NOT_FOUND = 7000
    ERR_FILE_READ = 7001
    ERR_FILE_WRITE = 7002
    ERR_FILE_PERMISSION = 7003
    
    # 外部服务 (8000-8999)
    ERR_EXTERNAL_API = 8000
    ERR_EXTERNAL_TIMEOUT = 8001
    ERR_EXTERNAL_RATE_LIMIT = 8002
    
    # 验证 (9000-9999)
    ERR_VALIDATION = 9000
    ERR_VALIDATION_FIELD = 9001
    ERR_VALIDATION_SCHEMA = 9002
    
    # 系统 (10000-10999)
    ERR_SYSTEM_RESOURCE = 10000
    ERR_SYSTEM_CONFIG = 10001
    ERR_SYSTEM_MAINTENANCE = 10002


# ==================== 自定义异常类 ====================

class APIException(HTTPException):
    """
    基础 API 异常类
    
    所有自定义异常都应继承此类，确保统一的错误响应格式。
    """
    def __init__(
        self,
        status_code: int = 500,
        error_code: int = ErrorCode.ERR_INTERNAL,
        message: str = "内部错误",
        detail: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.detail = detail
        self.data = data or {}
        self.timestamp = datetime.utcnow().isoformat()
        
        super().__init__(
            status_code=status_code,
            detail=self.to_dict()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "detail": self.detail,
                "data": self.data
            },
            "timestamp": self.timestamp
        }


class ValidationError(APIException):
    """验证错误"""
    def __init__(self, message: str = "验证失败", field: Optional[str] = None, detail: Optional[str] = None):
        data = {"field": field} if field else {}
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.ERR_VALIDATION,
            message=message,
            detail=detail,
            data=data
        )


class NotFoundError(APIException):
    """资源未找到错误"""
    def __init__(self, resource: str = "资源", identifier: Optional[str] = None):
        message = f"{resource}未找到"
        data = {"resource": resource, "identifier": identifier} if identifier else {"resource": resource}
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.ERR_NOT_FOUND,
            message=message,
            detail=f"请求的{resource}不存在或已被删除",
            data=data
        )


class AuthenticationError(APIException):
    """认证错误"""
    def __init__(self, message: str = "认证失败", error_code: int = ErrorCode.ERR_AUTH_INVALID_TOKEN):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            message=message,
            detail="请检查 Token 是否有效且未过期"
        )


class PermissionError(APIException):
    """权限错误"""
    def __init__(self, message: str = "权限不足", resource: Optional[str] = None):
        data = {"resource": resource} if resource else {}
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=ErrorCode.ERR_PERMISSION_DENIED,
            message=message,
            detail="您没有执行此操作的权限",
            data=data
        )


class RateLimitError(APIException):
    """速率限制错误"""
    def __init__(self, message: str = "请求过于频繁", retry_after: Optional[int] = None):
        data = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code=ErrorCode.ERR_RATE_LIMITED,
            message=message,
            detail="请稍后再试",
            data=data
        )


class DatabaseError(APIException):
    """数据库错误"""
    def __init__(self, message: str = "数据库操作失败", operation: Optional[str] = None, detail: Optional[str] = None):
        data = {"operation": operation} if operation else {}
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=ErrorCode.ERR_DB_QUERY,
            message=message,
            detail=detail,
            data=data
        )


class CacheError(APIException):
    """缓存错误"""
    def __init__(self, message: str = "缓存操作失败", operation: Optional[str] = None):
        data = {"operation": operation} if operation else {}
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=ErrorCode.ERR_CACHE_WRITE,
            message=message,
            detail="缓存服务暂时不可用",
            data=data
        )


class ExternalServiceError(APIException):
    """外部服务错误"""
    def __init__(self, service: str = "外部服务", message: Optional[str] = None, detail: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code=ErrorCode.ERR_EXTERNAL_API,
            message=message or f"{service}暂时不可用",
            detail=detail,
            data={"service": service}
        )


class TimeoutError(APIException):
    """超时错误"""
    def __init__(self, operation: str = "操作", timeout_seconds: Optional[int] = None):
        super().__init__(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            error_code=ErrorCode.ERR_TIMEOUT,
            message=f"{operation}超时",
            detail=f"操作在{timeout_seconds}秒内未完成" if timeout_seconds else "操作超时",
            data={"operation": operation, "timeout_seconds": timeout_seconds}
        )


# ==================== 统一错误响应格式 ====================

def format_error_response(
    success: bool = False,
    error_code: int = ErrorCode.ERR_UNKNOWN,
    message: str = "错误",
    detail: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    格式化错误响应
    
    所有错误响应应使用此函数确保格式一致。
    """
    return {
        "success": success,
        "error": {
            "code": error_code,
            "message": message,
            "detail": detail,
            "data": data or {}
        },
        "timestamp": timestamp or datetime.utcnow().isoformat()
    }


def format_success_response(data: Any, message: str = "成功") -> Dict[str, Any]:
    """
    格式化成功响应
    
    所有成功响应应使用此函数确保格式一致。
    """
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== 异常转 HTTP 响应 ====================

async def api_exception_handler(request, exc: APIException):
    """API 异常处理器"""
    from config.logger import sys_logger
    import traceback
    
    # 记录错误日志
    sys_logger.error(
        f"[API 异常] {exc.message} | 错误码：{exc.error_code} | 路径：{request.url.path} | "
        f"方法：{request.method} | 详情：{exc.detail}",
        exc_info=True
    )
    
    return exc


async def global_exception_handler(request, exc: Exception):
    """全局异常处理器（捕获未处理的异常）"""
    from config.logger import sys_logger
    import traceback
    
    # 记录完整堆栈
    stack_trace = traceback.format_exc()
    sys_logger.error(
        f"[未处理异常] {type(exc).__name__}: {str(exc)} | 路径：{request.url.path} | "
        f"方法：{request.method}\n{stack_trace}"
    )
    
    # 返回统一错误格式
    return format_error_response(
        error_code=ErrorCode.ERR_INTERNAL,
        message="内部错误",
        detail="系统遇到意外错误，已记录日志",
        data={
            "type": type(exc).__name__,
            "path": str(request.url.path),
            "method": request.method
        }
    )
