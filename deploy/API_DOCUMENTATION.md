# TradingAgents API 文档

## 概述

TradingAgents Enterprise API 提供股票智能分析服务，基于多智能体系统（Multi-Agent System）进行深度股票分析。

**版本**: 1.0.0-preview  
**基础 URL**: `http://localhost:8000`  
**认证方式**: JWT Bearer Token

---

## 快速开始

### 1. 获取 Token

```bash
curl -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

响应:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### 2. 调用分析接口

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "symbol": "600519",
    "analysis_date": "2026-04-09"
  }'
```

---

## API 端点

### 认证接口

#### POST /api/v1/login

用户登录，获取 JWT Token。

**请求体**:
```json
{
  "username": "string",
  "password": "string"
}
```

**响应**:
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**错误码**:
- `2000`: 无效的用户名或密码
- `3003`: 请求过于频繁（速率限制）

---

### 分析接口

#### POST /api/v1/analyze

执行股票智能分析。

**请求头**:
- `Authorization: Bearer <token>` (必需)

**请求体**:
```json
{
  "symbol": "600519",
  "analysis_date": "2026-04-09",
  "risk_level": "medium",
  "selected_analysts": ["technical", "fundamental"],
  "user_context": {
    "investment_style": "value",
    "holding_period": "long_term"
  }
}
```

**参数说明**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 6 位股票代码 |
| analysis_date | string | 否 | 分析日期，默认今天 |
| risk_level | string | 否 | 风险等级：low/medium/high |
| selected_analysts | array | 否 | 指定分析师列表 |
| user_context | object | 否 | 用户上下文信息 |

**响应**:
```json
{
  "success": true,
  "data": {
    "status": "success",
    "symbol": "600519",
    "elapsed_seconds": 15.3,
    "report": "完整的分析报告 Markdown 内容...",
    "cached": false
  },
  "timestamp": "2026-04-09T12:34:56Z"
}
```

**错误码**:
- `2000`: Token 无效或过期
- `3000`: 无效的股票代码
- `4000`: 股票数据未找到
- `5001`: 数据库操作失败
- `8000`: 外部 API 调用失败

---

### 健康检查接口

#### GET /api/health

检查 API 服务健康状态（无需认证）。

**响应**:
```json
{
  "status": "ok",
  "message": "Backend service is running",
  "jwt_enabled": true
}
```

---

### 收藏夹接口

#### GET /api/favorites/

获取用户收藏的股票列表。

**请求头**:
- `Authorization: Bearer <token>` (必需)

**响应**:
```json
{
  "success": true,
  "data": [
    {
      "stock_code": "600519",
      "stock_name": "贵州茅台",
      "tags": ["白酒", "蓝筹"],
      "created_at": "2026-04-01T10:00:00Z"
    }
  ]
}
```

#### POST /api/favorites/

添加收藏股票。

**请求体**:
```json
{
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "tags": ["白酒", "蓝筹"]
}
```

#### DELETE /api/favorites/{stock_code}

删除收藏股票。

---

### 系统接口

#### GET /api/system/info

获取系统信息。

**响应**:
```json
{
  "version": "1.0.0-preview",
  "uptime": 86400,
  "environment": "production"
}
```

#### GET /api/system/status

获取服务状态。

**响应**:
```json
{
  "api": "running",
  "redis": "connected",
  "database": "healthy"
}
```

---

## 错误码说明

### 通用错误 (1000-1999)

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| 1000 | 未知错误 | 500 |
| 1001 | 内部错误 | 500 |
| 1002 | 资源未找到 | 404 |
| 1003 | 权限不足 | 403 |
| 1004 | 请求过于频繁 | 429 |
| 1005 | 服务不可用 | 503 |
| 1006 | 请求超时 | 504 |

### 认证错误 (2000-2999)

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| 2000 | 无效 Token | 401 |
| 2001 | Token 已过期 | 401 |
| 2002 | 无效凭证 | 401 |
| 2003 | 缺少 Token | 401 |

### API 请求错误 (3000-3999)

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| 3000 | 无效请求 | 400 |
| 3001 | 参数错误 | 400 |
| 3002 | 方法不允许 | 405 |
| 3003 | 速率限制 | 429 |

### 数据错误 (4000-4999)

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| 4000 | 数据未找到 | 404 |
| 4001 | 数据格式错误 | 400 |
| 4002 | 数据重复 | 409 |
| 4003 | 数据同步失败 | 500 |

### 数据库错误 (5000-5999)

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| 5000 | 数据库连接失败 | 500 |
| 5001 | 查询失败 | 500 |
| 5002 | 事务失败 | 500 |
| 5003 | 约束冲突 | 409 |

---

## 最佳实践

### 1. 错误处理

```python
import requests

def analyze_stock(symbol, token):
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/analyze",
            headers={"Authorization": f"Bearer {token}"},
            json={"symbol": symbol}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data["data"]["report"]
            else:
                print(f"API 错误：{data['error']['message']}")
        elif response.status_code == 401:
            print("Token 已过期，请重新登录")
        elif response.status_code == 429:
            print("请求过于频繁，请稍后再试")
        else:
            print(f"HTTP 错误：{response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"网络错误：{e}")
```

### 2. Token 刷新

```python
def refresh_token(username, password):
    response = requests.post(
        "http://localhost:8000/api/v1/login",
        json={"username": username, "password": password}
    )
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception("登录失败")
```

### 3. 批量分析

```python
def batch_analyze(symbols, token, delay=1):
    """批量分析股票，注意速率限制"""
    import time
    
    results = []
    for symbol in symbols:
        try:
            result = analyze_stock(symbol, token)
            results.append({"symbol": symbol, "report": result})
            time.sleep(delay)  # 避免触发速率限制
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})
    
    return results
```

---

## 性能指标

### 响应时间基准

| 接口 | 平均响应时间 | P95 | P99 |
|------|-------------|-----|-----|
| /api/v1/analyze | 15-30s | 45s | 60s |
| /api/favorites/ | <100ms | 200ms | 500ms |
| /api/health | <10ms | 20ms | 50ms |

### 速率限制

| 接口 | 限制 |
|------|------|
| /api/v1/login | 5 次/分钟 |
| /api/v1/analyze | 10 次/分钟 |
| 其他接口 | 60 次/分钟 |

---

## 支持

如有问题，请联系:
- 技术支持：support@stockanalyzer.com
- 文档更新：2026-04-09
