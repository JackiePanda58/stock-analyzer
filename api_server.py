import os
import sys
import time
import asyncio
import jwt
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
import redis
import uvicorn

sys.path.insert(0, '/root/stock-analyzer')
from dotenv import load_dotenv
load_dotenv('/root/stock-analyzer/.env')
from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from config.logger import sys_logger

# ==================== JWT 安全基建 ====================
SECRET_KEY = "trading_agents_super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24小时
security = HTTPBearer()

# ==================== Redis 客户端 ====================
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    sys_logger.info("✅ API: Redis 缓存大脑连接成功！")
except Exception as e:
    sys_logger.error(f"❌ API: Redis 连接失败，将降级为无缓存模式: {e}")
    redis_client = None

# ==================== FastAPI 应用 ====================
app = FastAPI(title="TradingAgents Enterprise API", version="1.0.0-preview")
sys_logger.info("=== FastAPI 后端服务启动 (JWT 鉴权已启用) ===")
set_config(TRADING_CONFIG)

# ==================== JWT 鉴权依赖 ====================
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """解码并校验 JWT Token，无效或过期返回 401"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")
    except Exception:
        raise HTTPException(status_code=401, detail="无效或被篡改的 Token")


# ==================== Pydantic 模型（宽容度设计） ====================
class LoginReq(BaseModel):
    username: str
    password: str


class AnalyzeReq(BaseModel):
    """
    宽容度分析请求模型，兼容官方前端 SingleAnalysisRequest 格式。

    支持字段：
    - symbol: 标准 6 位股票代码
    - stock_code: 官方前端兼容字段
    - parameters: 官方前端参数包（内含 analysis_date、selected_analysts 等）
    - 直接顶层字段如 analysis_date、market_type 等（extra=allow）

    自动忽略所有未知字段，实现与官方前端的零摩擦对接。
    """
    # 主字段
    symbol: Optional[str] = None
    stock_code: Optional[str] = None
    # 官方前端参数包
    parameters: Optional[Dict[str, Any]] = None
    # 顶层兼容字段（部分官方调用会直接放在顶层）
    analysis_date: Optional[str] = None
    market_type: Optional[str] = None
    analysis_type: Optional[str] = None

    model_config = ConfigDict(extra='allow')  # 核心：接受任何未知字段，实现最大宽容度

    def resolve_symbol(self) -> str:
        """从 symbol / stock_code / parameters 中解析股票代码"""
        if self.symbol:
            return self.symbol.strip()
        if self.stock_code:
            return self.stock_code.strip()
        if self.parameters:
            return self.parameters.get("symbol", "").strip()
        return ""

    def resolve_date(self) -> str:
        """从 analysis_date / parameters 中解析分析日期"""
        if self.analysis_date:
            return self.analysis_date
        if self.parameters:
            return self.parameters.get("analysis_date", "")
        return datetime.now().strftime("%Y-%m-%d")


class AnalyzeResponse(BaseModel):
    status: str
    symbol: str
    elapsed_seconds: float
    report: str
    cached: bool


# ==================== 全局异常处理 ====================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    sys_logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "内部分析流转失败"})


# ==================== 健康检查 (无需鉴权) ====================
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "TradingAgents API is running.", "jwt_enabled": True}


# ==================== 前端兼容接口 (无需鉴权) ====================
@app.get("/api/health")
async def api_health():
    """前端 NetworkStatus 组件轮询的健康检查"""
    return {"status": "ok", "message": "Backend service is running", "jwt_enabled": True}


@app.post("/api/auth/login")
def api_auth_login(req: LoginReq):
    """前端 /api/auth/login 兼容接口"""
    if req.username == "admin" and req.password == "admin123":
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 7)
        token = jwt.encode({"sub": req.username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
        refresh_token = jwt.encode({"sub": req.username, "exp": refresh_expire}, SECRET_KEY, algorithm=ALGORITHM)
        sys_logger.info(f"✅ [登录成功] 用户: {req.username} | Token 有效期: {ACCESS_TOKEN_EXPIRE_MINUTES}min")
        return {
            "success": True,
            "data": {
                "access_token": token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": {"id": 1, "username": "admin", "email": "admin@tradingagents.cn", "role": "admin"}
            }
        }
    sys_logger.warning(f"❌ [登录失败] 用户名或密码错误: {req.username}")
    raise HTTPException(status_code=401, detail="用户名或密码错误")


# ==================== 前端配置验证接口 ====================
@app.get("/api/system/config/validate")
async def validate_config():
    """前端 ConfigValidator 和 App.vue 调用的配置验证接口"""
    import os
    from dotenv import load_dotenv
    load_dotenv('/root/stock-analyzer/.env', override=True)

    required_vars = ["OPENAI_API_KEY", "OPENAI_BASE_URL"]
    missing = [v for v in required_vars if not os.getenv(v)]

    return {
        "success": True,
        "data": {
            "success": len(missing) == 0,
            "missing_required": missing,
            "env_validation": {
                "success": len(missing) == 0,
                "missing_keys": missing
            },
            "mongodb_validation": {
                "success": True,
                "message": "MongoDB not required in this deployment"
            }
        }
    }


# ==================== 登录接口 ====================
@app.post("/api/v1/login")
def login(req: LoginReq):
    """颁发 JWT Token (MVP 硬编码校验)"""
    if req.username == "admin" and req.password == "admin123":
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        token = jwt.encode({"sub": req.username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
        sys_logger.info(f"✅ [登录成功] 用户: {req.username} | Token 有效期: {ACCESS_TOKEN_EXPIRE_MINUTES}min")
        return {"access_token": token, "token_type": "bearer", "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60}
    sys_logger.warning(f"❌ [登录失败] 用户名或密码错误: {req.username}")
    raise HTTPException(status_code=401, detail="用户名或密码错误")


# ==================== 受保护的 /api/v1/analyze ====================
@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_stock(req: AnalyzeReq, username: str = Depends(verify_token)):
    """
    股票智能分析接口 (JWT 鉴权保护)

    保护机制：
    - 必须携带有效 JWT Token (Authorization: Bearer <token>)
    - Redis 高速缓存拦截
    - LLM 多智能体异步调用 (TradingAgentsGraph)

    官方前端兼容：
    - AnalyzeReq.extra='allow' 接受任意未知字段
    - resolve_symbol() / resolve_date() 自动从多个可能位置提取字段
    """
    symbol = req.resolve_symbol()
    target_date = req.resolve_date()

    # 参数校验
    if not symbol or len(symbol) != 6:
        raise HTTPException(status_code=400, detail=f"无效的股票代码: {symbol}")

    sys_logger.info(f"[API] 👉 收到分析请求，目标代码: {symbol} | 日期: {target_date} | 用户: {username}")

    # ⚡ 1. Redis 缓存拦截
    cache_key = f"report:{symbol}:{target_date}"
    if redis_client:
        try:
            cached_report = redis_client.get(cache_key)
            if cached_report:
                sys_logger.info(f"[API] ⚡ [命中缓存] {symbol} 报告已存在，极速返回！")
                return AnalyzeResponse(
                    status="success",
                    symbol=symbol,
                    elapsed_seconds=0.01,
                    report=cached_report,
                    cached=True
                )
        except Exception as e:
            sys_logger.error(f"[API] Redis 读取失败: {e}")

    # 2. 未命中缓存，执行真实 TradingAgentsGraph 分析
    try:
        t0 = time.time()
        local_ta = TradingAgentsGraph(
            selected_analysts=["market", "news", "fundamentals"],
            debug=False,
            config=TRADING_CONFIG
        )
        result, _ = await asyncio.to_thread(local_ta.propagate, symbol, target_date)
        elapsed = time.time() - t0

        final_report = result.get("final_trade_decision", "⚠️ 未找到最终报告:\n" + str(result))
        sys_logger.info(f"[API] [{symbol}] ✅ 分析顺利完成，耗时: {elapsed:.0f}秒")

        # ⚡ 3. 写入 Redis 缓存 (12小时)
        if redis_client:
            try:
                redis_client.setex(cache_key, 43200, final_report)
            except Exception as e:
                sys_logger.error(f"[API] Redis 写入失败: {e}")

        return AnalyzeResponse(
            status="success",
            symbol=symbol,
            elapsed_seconds=round(elapsed, 2),
            report=final_report,
            cached=False
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="LLM 多智能体分析超时，请稍后重试")
    except Exception as e:
        sys_logger.error(f"[API] [{symbol}] ❌ 分析发生灾难性中断:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"内部分析流转失败: {str(e)}")


# ==================== 通知系统 (Notifications) ====================
@app.get("/api/notifications/unread_count")
async def notifications_unread_count(username: str = Depends(verify_token)):
    return {"success": True, "data": {"count": 0}}

@app.get("/api/notifications")
async def notifications_list(username: str = Depends(verify_token)):
    return {"success": True, "data": {"items": [], "total": 0}}

@app.post("/api/notifications/{notification_id}/read")
async def notifications_mark_read(notification_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"marked": True}}

@app.post("/api/notifications/read_all")
async def notifications_read_all(username: str = Depends(verify_token)):
    return {"success": True, "data": {"marked": 0}}

@app.websocket("/api/ws/notifications")
async def ws_notifications(websocket):
    sys_logger.info(f"WebSocket 连接请求: {websocket.query_params}")
    try:
        # 从 query string 获取 token
        token = websocket.query_params.get("token")
        sys_logger.info(f"Token: {token[:20] if token else None}...")
        if token:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                sys_logger.info(f"Token decoded: {payload}")
            except Exception as e:
                sys_logger.error(f"Token decode failed: {e}")
                await websocket.close(code=4001, reason="Invalid token")
                return
        await websocket.accept()
        sys_logger.info("WebSocket accepted!")
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({"type": "pong"})
        except Exception as e:
            sys_logger.error(f"WebSocket recv error: {e}")
    except Exception as e:
        sys_logger.error(f"WebSocket error: {type(e).__name__}: {e}")

# ==================== 收藏夹 (Favorites) ====================
@app.get("/api/favorites/")
async def favorites_list(username: str = Depends(verify_token)):
    return {"success": True, "data": []}

@app.post("/api/favorites/")
async def favorites_add(username: str = Depends(verify_token)):
    return {"success": True, "data": {"id": "stub"}}

@app.delete("/api/favorites/{fav_id}")
async def favorites_delete(fav_id: str, username: str = Depends(verify_token)):
    return {"success": True}

@app.get("/api/favorites/tags")
async def favorites_tags(username: str = Depends(verify_token)):
    return {"success": True, "data": {"tags": []}}

@app.get("/api/favorites/sync-realtime")
async def favorites_sync_realtime(username: str = Depends(verify_token)):
    return {"success": True, "data": {"synced": True}}

# ==================== 多源数据同步 (Multi-Source Sync) ====================
@app.get("/api/sync/multi-source/status")
async def sync_multi_source_status(username: str = Depends(verify_token)):
    return {"success": True, "data": {"enabled": True, "last_sync": None}}

@app.get("/api/sync/multi-source/sources/status")
async def sync_multi_source_sources_status(username: str = Depends(verify_token)):
    return {"success": True, "data": []}

@app.get("/api/sync/multi-source/sources/current")
async def sync_multi_source_current(username: str = Depends(verify_token)):
    return {"success": True, "data": None}

@app.post("/api/sync/multi-source/test-sources")
async def sync_test_sources(username: str = Depends(verify_token)):
    return {"success": True, "data": {"results": []}}

@app.get("/api/sync/multi-source/recommendations")
async def sync_recommendations(username: str = Depends(verify_token)):
    return {"success": True, "data": {"recommendations": []}}

@app.delete("/api/sync/multi-source/cache")
async def sync_cache_delete(username: str = Depends(verify_token)):
    return {"success": True, "data": {"deleted": 0}}

@app.post("/api/sync/stock_basics/run")
async def sync_stock_basics_run(username: str = Depends(verify_token)):
    return {"success": True, "data": {"task_id": "stub"}}

@app.get("/api/sync/stock_basics/status")
async def sync_stock_basics_status(username: str = Depends(verify_token)):
    return {"success": True, "data": {"status": "idle"}}

# ==================== 定时调度器 (Scheduler) ====================
@app.get("/api/scheduler/health")
async def scheduler_health(username: str = Depends(verify_token)):
    return {"success": True, "data": {"running": True, "state": 1}}

@app.get("/api/scheduler/jobs")
async def scheduler_jobs(username: str = Depends(verify_token)):
    return {"success": True, "data": {"jobs": []}}

@app.get("/api/scheduler/jobs/{job_id}")
async def scheduler_job_get(job_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"id": job_id, "name": "stub"}}

@app.post("/api/scheduler/jobs/{job_id}/pause")
async def scheduler_job_pause(job_id: str, username: str = Depends(verify_token)):
    return {"success": True}

@app.post("/api/scheduler/jobs/{job_id}/resume")
async def scheduler_job_resume(job_id: str, username: str = Depends(verify_token)):
    return {"success": True}

@app.post("/api/scheduler/jobs/{job_id}/trigger")
async def scheduler_job_trigger(job_id: str, force: bool = False, username: str = Depends(verify_token)):
    return {"success": True, "data": {"triggered": True}}

@app.get("/api/scheduler/jobs/{job_id}/history")
async def scheduler_job_history(job_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"history": []}}

@app.get("/api/scheduler/history")
async def scheduler_history(username: str = Depends(verify_token)):
    return {"success": True, "data": {"history": []}}

@app.get("/api/scheduler/stats")
async def scheduler_stats(username: str = Depends(verify_token)):
    return {"success": True, "data": {"total_jobs": 0, "running": 0}}

@app.get("/api/scheduler/executions")
async def scheduler_executions(username: str = Depends(verify_token)):
    return {"success": True, "data": {"executions": []}}

@app.get("/api/scheduler/jobs/{job_id}/executions")
async def scheduler_job_executions(job_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"executions": []}}

@app.get("/api/scheduler/jobs/{job_id}/execution-stats")
async def scheduler_job_execution_stats(job_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"stats": {"total": 0, "success": 0, "failed": 0}}}

# ==================== 认证相关 (Auth) ====================
@app.post("/api/auth/logout")
async def auth_logout(username: str = Depends(verify_token)):
    return {"success": True}

@app.post("/api/auth/refresh")
async def auth_refresh(req: LoginReq, username: str = Depends(verify_token)):
    return {"success": True, "data": {"access_token": "stub", "refresh_token": "stub"}}

@app.post("/api/auth/change-password")
async def auth_change_password(username: str = Depends(verify_token)):
    return {"success": True}

@app.post("/api/auth/register")
async def auth_register(req: LoginReq):
    return {"success": True}

@app.post("/api/auth/reset-password")
async def auth_reset_password():
    return {"success": True}

@app.post("/api/auth/verify-email")
async def auth_verify_email():
    return {"success": True}

@app.get("/api/auth/me")
async def auth_me(username: str = Depends(verify_token)):
    return {"success": True, "data": {"id": 1, "username": username, "email": f"{username}@tradingagents.cn", "role": "admin"}}

@app.get("/api/auth/permissions")
async def auth_permissions(username: str = Depends(verify_token)):
    return {"success": True, "data": {"permissions": ["*"], "roles": ["admin"]}}

# ==================== 配置系统 (Config) ====================
@app.get("/api/config/system")
async def config_system(username: str = Depends(verify_token)):
    return {"success": True, "data": {"version": "1.0.0"}}

@app.get("/api/config/llm")
async def config_llm(username: str = Depends(verify_token)):
    return {"success": True, "data": {"providers": [], "default": None}}

@app.get("/api/config/llm/providers")
async def config_llm_providers(username: str = Depends(verify_token)):
    return {"success": True, "data": {"providers": []}}

@app.get("/api/config/models")
async def config_models(username: str = Depends(verify_token)):
    return {"success": True, "data": {"models": []}}

@app.get("/api/config/model-catalog")
async def config_model_catalog(username: str = Depends(verify_token)):
    return {"success": True, "data": {"catalog": []}}

@app.get("/api/config/settings")
async def config_settings(username: str = Depends(verify_token)):
    return {"success": True, "data": {"settings": {}}}

@app.get("/api/config/settings/meta")
async def config_settings_meta(username: str = Depends(verify_token)):
    return {"success": True, "data": {"meta": {}}}

@app.get("/api/config/datasource")
async def config_datasource(username: str = Depends(verify_token)):
    return {"success": True, "data": {"datasources": []}}

@app.get("/api/config/datasource-groupings")
async def config_datasource_groupings(username: str = Depends(verify_token)):
    return {"success": True, "data": {"groupings": []}}

@app.get("/api/config/market-categories")
async def config_market_categories(username: str = Depends(verify_token)):
    return {"success": True, "data": {"categories": []}}

@app.post("/api/config/test")
async def config_test(username: str = Depends(verify_token)):
    return {"success": True, "data": {"result": True}}

@app.post("/api/config/reload")
async def config_reload(username: str = Depends(verify_token)):
    return {"success": True}

@app.post("/api/config/export")
async def config_export(username: str = Depends(verify_token)):
    return {"success": True, "data": {"export": "{}"}}

@app.post("/api/config/import")
async def config_import(username: str = Depends(verify_token)):
    return {"success": True}

@app.post("/api/config/migrate-legacy")
async def config_migrate_legacy(username: str = Depends(verify_token)):
    return {"success": True}

# ==================== 分析接口 (Analysis) ====================
@app.post("/api/analysis/single")
async def analysis_single(req: AnalyzeReq, username: str = Depends(verify_token)):
    return {"success": True, "data": {"task_id": "stub", "status": "queued"}}

@app.get("/api/analysis/tasks/{task_id}/status")
async def analysis_task_status(task_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"status": "pending", "progress": 0}}

@app.get("/api/analysis/user/history")
async def analysis_user_history(username: str = Depends(verify_token)):
    return {"success": True, "data": {"items": [], "total": 0}}

@app.get("/api/analysis/stock-info")
async def analysis_stock_info(username: str = Depends(verify_token)):
    return {"success": True, "data": {}}

@app.get("/api/analysis/search")
async def analysis_search(username: str = Depends(verify_token)):
    return {"success": True, "data": {"results": []}}

@app.get("/api/analysis/popular")
async def analysis_popular(username: str = Depends(verify_token)):
    return {"success": True, "data": {"items": []}}

@app.get("/api/analysis/stats")
async def analysis_stats(username: str = Depends(verify_token)):
    return {"success": True, "data": {"total": 0, "today": 0}}

@app.get("/api/analysis/tasks")
async def analysis_tasks(username: str = Depends(verify_token)):
    return {"success": True, "data": {"tasks": []}}

@app.get("/api/analysis/tasks/all")
async def analysis_tasks_all(username: str = Depends(verify_token)):
    return {"success": True, "data": {"tasks": []}}

@app.post("/api/analysis/batch")
async def analysis_batch(username: str = Depends(verify_token)):
    return {"success": True, "data": {"batch_id": "stub"}}

@app.get("/api/analysis/batches/{batch_id}")
async def analysis_batch_get(batch_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"batch_id": batch_id, "status": "pending"}}

# ==================== 缓存 (Cache) ====================
@app.get("/api/cache/stats")
async def cache_stats(username: str = Depends(verify_token)):
    return {"success": True, "data": {"size": 0, "items": 0}}

@app.get("/api/cache/details")
async def cache_details(username: str = Depends(verify_token)):
    return {"success": True, "data": {"details": {}}}

@app.get("/api/cache/backend-info")
async def cache_backend_info(username: str = Depends(verify_token)):
    return {"success": True, "data": {"backend": "redis", "connected": True}}

@app.post("/api/cache/clear")
async def cache_clear(username: str = Depends(verify_token)):
    return {"success": True, "data": {"cleared": 0}}

@app.delete("/api/cache/cleanup")
async def cache_cleanup(username: str = Depends(verify_token)):
    return {"success": True, "data": {"deleted": 0}}

# ==================== 股票数据 (Stocks) ====================
@app.get("/api/stocks/quote")
async def stocks_quote(username: str = Depends(verify_token)):
    return {"success": True, "data": {}}

@app.get("/api/stocks/quote/")
async def stocks_quote_slash(username: str = Depends(verify_token)):
    return {"success": True, "data": {}}

# ==================== 市场数据 (Markets) ====================
@app.get("/api/markets")
async def markets_list(username: str = Depends(verify_token)):
    return {"success": True, "data": {"markets": []}}

# ==================== 新闻数据 (News) ====================
@app.get("/api/news-data/latest")
async def news_latest(username: str = Depends(verify_token)):
    return {"success": True, "data": {"news": []}}

@app.post("/api/news-data/sync/start")
async def news_sync_start(username: str = Depends(verify_token)):
    return {"success": True, "data": {"sync_id": "stub"}}

# ==================== 智能选股 (Screening) ====================
@app.get("/api/screening/fields")
async def screening_fields(username: str = Depends(verify_token)):
    return {"success": True, "data": {"fields": []}}

@app.get("/api/screening/industries")
async def screening_industries(username: str = Depends(verify_token)):
    return {"success": True, "data": {"industries": []}}

@app.post("/api/screening/run")
async def screening_run(username: str = Depends(verify_token)):
    return {"success": True, "data": {"job_id": "stub"}}

# ==================== 股票同步 (Stock Sync) ====================
@app.post("/api/stock-sync/single")
async def stock_sync_single(username: str = Depends(verify_token)):
    return {"success": True, "data": {"synced": True}}

@app.post("/api/stock-sync/batch")
async def stock_sync_batch(username: str = Depends(verify_token)):
    return {"success": True, "data": {"synced": 0}}

# ==================== 模板 (Templates) ====================
@app.get("/api/templates")
async def templates_list(username: str = Depends(verify_token)):
    return {"success": True, "data": {"templates": []}}

@app.get("/api/agents/templates")
async def agents_templates(username: str = Depends(verify_token)):
    return {"success": True, "data": {"templates": []}}

# ==================== 标签 (Tags) ====================
@app.get("/api/tags/")
async def tags_list(username: str = Depends(verify_token)):
    return {"success": True, "data": {"tags": []}}

# ==================== 使用统计 (Usage) ====================
@app.get("/api/usage/statistics")
async def usage_statistics(username: str = Depends(verify_token)):
    return {"success": True, "data": {"total": 0}}

@app.get("/api/usage/records")
async def usage_records(username: str = Depends(verify_token)):
    return {"success": True, "data": {"records": []}}

@app.get("/api/usage/records/old")
async def usage_records_old(username: str = Depends(verify_token)):
    return {"success": True, "data": {"records": []}}

@app.get("/api/usage/cost/daily")
async def usage_cost_daily(username: str = Depends(verify_token)):
    return {"success": True, "data": {"costs": []}}

@app.get("/api/usage/cost/by-model")
async def usage_cost_by_model(username: str = Depends(verify_token)):
    return {"success": True, "data": {"costs": {}}}

@app.get("/api/usage/cost/by-provider")
async def usage_cost_by_provider(username: str = Depends(verify_token)):
    return {"success": True, "data": {"costs": {}}}

# ==================== 模型能力 (Model Capabilities) ====================
@app.get("/api/model-capabilities/recommend")
async def model_capabilities_recommend(username: str = Depends(verify_token)):
    return {"success": True, "data": {"recommended": None}}

@app.get("/api/model-capabilities/badges")
async def model_capabilities_badges(username: str = Depends(verify_token)):
    return {"success": True, "data": {"badges": []}}

@app.get("/api/model-capabilities/capability-descriptions")
async def model_capabilities_descriptions(username: str = Depends(verify_token)):
    return {"success": True, "data": {"descriptions": {}}}

@app.get("/api/model-capabilities/default-configs")
async def model_capabilities_default_configs(username: str = Depends(verify_token)):
    return {"success": True, "data": {"configs": {}}}

@app.get("/api/model-capabilities/depth-requirements")
async def model_capabilities_depth_requirements(username: str = Depends(verify_token)):
    return {"success": True, "data": {"requirements": {}}}

@app.post("/api/model-capabilities/validate")
async def model_capabilities_validate(username: str = Depends(verify_token)):
    return {"success": True, "data": {"valid": True}}

@app.post("/api/model-capabilities/batch-init")
async def model_capabilities_batch_init(username: str = Depends(verify_token)):
    return {"success": True}

# ==================== 纸带交易 (Paper Trading) ====================
@app.get("/api/paper/positions")
async def paper_positions(username: str = Depends(verify_token)):
    return {"success": True, "data": {"positions": []}}

@app.get("/api/paper/account")
async def paper_account(username: str = Depends(verify_token)):
    return {"success": True, "data": {"account": {"cash": 100000, "positions_value": 0, "equity": 100000, "currency": "CNY"}}}

@app.get("/api/paper/order")
async def paper_order(username: str = Depends(verify_token)):
    return {"success": True, "data": {"orders": []}}

# ==================== 系统数据库 (System Database) ====================
@app.get("/api/system/database/status")
async def system_database_status(username: str = Depends(verify_token)):
    return {"success": True, "data": {"status": "connected"}}

@app.get("/api/system/database/stats")
async def system_database_stats(username: str = Depends(verify_token)):
    return {"success": True, "data": {"tables": 0, "records": 0}}

@app.post("/api/system/database/test")
async def system_database_test(username: str = Depends(verify_token)):
    return {"success": True, "data": {"connected": True}}

@app.get("/api/system/database/backups")
async def system_database_backups(username: str = Depends(verify_token)):
    return {"success": True, "data": {"backups": []}}

@app.post("/api/system/database/backup")
async def system_database_backup(username: str = Depends(verify_token)):
    return {"success": True, "data": {"backup_id": "stub"}}

@app.post("/api/system/database/export")
async def system_database_export(username: str = Depends(verify_token)):
    return {"success": True, "data": {"export_id": "stub"}}

# ==================== 系统日志 (System Logs) ====================
@app.get("/api/system/system-logs/files")
async def system_logs_files(username: str = Depends(verify_token)):
    return {"success": True, "data": {"files": []}}

@app.post("/api/system/system-logs/read")
async def system_logs_read(username: str = Depends(verify_token)):
    return {"success": True, "data": {"logs": []}}

@app.get("/api/system/system-logs/statistics")
async def system_logs_statistics(username: str = Depends(verify_token)):
    return {"success": True, "data": {"statistics": {}}}

@app.get("/api/system/logs/stats")
async def system_logs_stats(username: str = Depends(verify_token)):
    return {"success": True, "data": {"stats": {}}}

@app.get("/api/system/logs/{log_id}")
async def system_log_get(log_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"id": log_id, "content": ""}}

@app.post("/api/system/logs/create")
async def system_logs_create(username: str = Depends(verify_token)):
    return {"success": True}

@app.post("/api/system/logs/clear")
async def system_logs_clear(username: str = Depends(verify_token)):
    return {"success": True, "data": {"cleared": 0}}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
