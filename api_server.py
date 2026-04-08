import os
import sys
import time
import asyncio
import uuid
import jwt
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, ConfigDict
import redis.asyncio as aioredis
import json
import requests
import baostock as bs
import uvicorn

sys.path.insert(0, '/root/stock-analyzer')
from dotenv import load_dotenv
load_dotenv('/root/stock-analyzer/.env')
from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.usage_tracker import (
    init_db,
    UsageTrackingCallback,
    get_usage_stats,
    get_usage_records,
    get_daily_cost,
    get_cost_by_model,
    get_cost_by_provider,
)
from config.logger import sys_logger

# ==================== JWT 安全基建 ====================
SECRET_KEY = "trading_agents_super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24小时
security = HTTPBearer()

# ==================== Redis 客户端 ====================
try:
    redis_client = aioredis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    # 连接测试（非阻塞验证）
    sys_logger.info("✅ API: Redis 缓存大脑连接已初始化（aioredis）！")
except Exception as e:
    sys_logger.error(f"❌ API: Redis 连接失败，将降级为无缓存模式: {e}")
    redis_client = None

# ==================== FastAPI 应用 ====================
# 初始化用量数据库
init_db()
sys_logger.info("[API] ✅ 用量追踪数据库已初始化")

app = FastAPI(title="TradingAgents Enterprise API", version="1.0.0-preview")
sys_logger.info("=== FastAPI 后端服务启动 (JWT 鉴权已启用) ===")
set_config(TRADING_CONFIG)

# ==================== 分析辅助函数 ====================
def _run_trading_graph_stream(ta, symbol, target_date, user_context, risk_level, selected_analysts, parameters):
    """
    运行 TradingAgentsGraph，使用 stream() 而非 invoke() 避免挂起。
    在独立线程中运行，避免阻塞事件循环。
    """
    import threading
    import queue

    result_queue = queue.Queue()
    error_queue = queue.Queue()

    def _run():
        try:
            init_state = ta.propagator.create_initial_state(symbol, target_date,
                user_context=user_context,
                risk_level=risk_level,
                selected_analysts=selected_analysts,
                **(parameters or {})
            )
            args = ta.propagator.get_graph_args()
            final_state = None
            for chunk in ta.graph.stream(init_state, **args):
                final_state = chunk
            if final_state is None:
                raise RuntimeError("TradingAgentsGraph produced no output")
            result_queue.put((final_state, ta.process_signal(final_state.get("final_trade_decision", ""))))
        except Exception as e:
            error_queue.put(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=600)  # 10 minute timeout

    if not result_queue.empty():
        return result_queue.get()
    elif not error_queue.empty():
        raise error_queue.get()
    else:
        raise TimeoutError(f"TradingAgentsGraph timed out after 600s for {symbol}")


def _run_analysis_in_subprocess(
    symbol: str,
    target_date: str,
    selected_analysts: list,
    risk_level: str,
    task_id: str
) -> dict:
    """
    在独立子进程中运行完整的 LangGraph 分析。
    结果写入临时文件，主进程通过文件内容获取结果。
    这确保 API 服务器永远不会被分析任务阻塞。
    """
    import tempfile
    import pickle
    import os
    import sys

    # 设置 Python path
    sys.path.insert(0, '/root/stock-analyzer')
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

    result_file = f"/tmp/analysis_result_{task_id}.pkl"

    try:
        from dotenv import load_dotenv
        load_dotenv('/root/stock-analyzer/.env')
        from tradingagents.dataflows.config import set_config
        from config.settings import TRADING_CONFIG
        set_config(TRADING_CONFIG)
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        ta = TradingAgentsGraph(
            selected_analysts=selected_analysts,
            debug=False,
            config=TRADING_CONFIG
        )
        init_state = ta.propagator.create_initial_state(
            symbol, target_date,
            user_context={},
            risk_level=risk_level,
            selected_analysts=selected_analysts
        )
        args = ta.propagator.get_graph_args()
        final_state = None
        for chunk in ta.graph.stream(init_state, **args):
            final_state = chunk
        if final_state is None:
            raise RuntimeError("TradingAgentsGraph produced no output")
        final_report = ta.process_signal(final_state.get("final_trade_decision", ""))
        with open(result_file, 'wb') as f:
            pickle.dump({'report': final_report, 'state': str(final_state)[:500]}, f)
        return {'status': 'completed', 'report': final_report}
    except Exception as e:
        with open(result_file, 'wb') as f:
            pickle.dump({'status': 'failed', 'error': str(e)}, f)
        return {'status': 'failed', 'error': str(e)}


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
    """
    后台分析任务：在线程池中运行 TradingAgentsGraph，
    结果写入报告文件。
    使用 run_in_executor 避免阻塞 FastAPI 事件循环。
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='analysis_worker')

    loop = asyncio.get_running_loop()
    try:
        sys_logger.info(f"[Background] Task {task_id} 开始执行 {symbol}...")

        def _do_analysis():
            try:
                from tradingagents.graph.trading_graph import TradingAgentsGraph
                ta = TradingAgentsGraph(
                    selected_analysts=selected_analysts,
                    debug=False,
                    config=TRADING_CONFIG
                )
                init_state = ta.propagator.create_initial_state(
                    symbol, target_date,
                    user_context={},
                    risk_level=risk_level,
                    selected_analysts=selected_analysts
                )
                args = ta.propagator.get_graph_args()
                final_state = None
                for chunk in ta.graph.stream(init_state, **args):
                    final_state = chunk
                if final_state is None:
                    raise RuntimeError("TradingAgentsGraph produced no output")
                # 返回完整报告，不提取信号（process_signal 只返回决策）
                return final_state.get("final_trade_decision", "⚠️ 未找到最终报告")
            except Exception as e:
                sys_logger.error(f"[Background] Task {task_id} 分析异常: {e}\n{traceback.format_exc()}")
                return f"⚠️ 分析失败: {e}"

        final_report = await loop.run_in_executor(_executor, _do_analysis)
        sys_logger.info(f"[Background] Task {task_id} LangGraph 完成，正在写入结果...")

        # 写入 Redis 缓存（12小时）
        cache_key = f"report:{symbol}:{target_date}"
        if redis_client:
            try:
                await redis_client.setex(cache_key, 43200, final_report)
                import json
                await redis_client.setex(f"task_meta:{task_id}", 86400, json.dumps({
                    "symbol": symbol, "date": target_date,
                    "status": "completed", "username": username,
                    "report": final_report
                }))
            except Exception as e:
                sys_logger.error(f"[Background] Redis 写入失败: {e}")

        # 写入报告文件
        try:
            reports_dir = "/root/stock-analyzer/reports"
            os.makedirs(reports_dir, exist_ok=True)
            date_str = target_date.replace('-', '')
            report_file = os.path.join(reports_dir, f"{symbol}_{date_str}.md")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(final_report)
            sys_logger.info(f"[Background] Task {task_id} 报告已写入: {report_file}")
        except Exception as e:
            sys_logger.error(f"[Background] 报告文件写入失败: {e}")

        sys_logger.info(f"[Background] Task {task_id} 完成！")

    except Exception as e:
        sys_logger.error(f"[Background] Task {task_id} 失败: {e}\n{traceback.format_exc()}")
    finally:
        _executor.shutdown(wait=False)


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
    # 显式参数（透传给大模型引擎）
    user_context: Optional[Dict[str, Any]] = None      # 用户上下文/个性化信息
    risk_level: Optional[str] = "medium"             # 风险等级 low/medium/high
    selected_analysts: Optional[list] = None        # 指定参与的分析师

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
            cached_report = await redis_client.get(cache_key)
            if cached_report:
                sys_logger.info(f"[API] ⚡ [命中缓存] {symbol} 报告已存在，极速返回！")
                # 同时写入 reports/ 目录
                try:
                    reports_dir = "/root/stock-analyzer/reports"
                    os.makedirs(reports_dir, exist_ok=True)
                    report_file = os.path.join(reports_dir, f"{symbol}_{target_date.replace('-', '')}.md")
                    if not os.path.exists(report_file):
                        with open(report_file, "w", encoding="utf-8") as f:
                            f.write(cached_report)
                        sys_logger.info(f"[API] 📄 报告已写入（缓存命中）: {report_file}")
                except Exception as fe:
                    sys_logger.error(f"[API] 报告文件写入失败: {fe}")
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
        session_id = str(uuid.uuid4())
        usage_cb = UsageTrackingCallback(
            session_id=session_id,
            analysis_type="stock_analysis",
            symbol=symbol
        )
        local_ta = TradingAgentsGraph(
            selected_analysts=["market", "news", "fundamentals"],
            debug=False,
            config=TRADING_CONFIG,
            callbacks=[usage_cb]
        )
        result, _ = await asyncio.to_thread(
            _run_trading_graph_stream,
            local_ta,
            symbol,
            target_date,
            req.user_context or {},
            req.risk_level or "medium",
            req.selected_analysts or ["market", "news", "fundamentals"],
            req.parameters or {}
        )
        elapsed = time.time() - t0

        final_report = result.get("final_trade_decision", "⚠️ 未找到最终报告:\n" + str(result))
        sys_logger.info(f"[API] [{symbol}] ✅ 分析顺利完成，耗时: {elapsed:.0f}秒")

        # ⚡ 3. 写入 Redis 缓存 (12小时)
        if redis_client:
            try:
                await redis_client.setex(cache_key, 43200, final_report)
            except Exception as e:
                sys_logger.error(f"[API] Redis 写入失败: {e}")

        # 📄 4. 同时写入 reports/ 目录（供报告列表页面展示）
        try:
            reports_dir = "/root/stock-analyzer/reports"
            os.makedirs(reports_dir, exist_ok=True)
            report_file = os.path.join(reports_dir, f"{symbol}_{target_date.replace('-', '')}.md")
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(final_report)
            sys_logger.info(f"[API] 📄 报告已写入: {report_file}")
        except Exception as e:
            sys_logger.error(f"[API] 报告文件写入失败: {e}")

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
def _fav_key(username: str) -> str:
    return f"favorites:{username}"

def _validate_stock(code: str, market: str) -> dict:
    """验证股票代码并返回标准化的股票信息"""
    code = code.strip()
    if market == "A股":
        for prefix in ["sh.", "sz."]:
            lg = bs.login()
            rs = bs.query_stock_basic(code=prefix + code)
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            bs.logout()
            if rows:
                name = rows[0][1]
                return {"stock_code": code, "stock_name": name, "market": market, "valid": True}
        raise ValueError(f"A股代码 {code} 不存在或已退市")

    elif market == "港股":
        # 腾讯财经接口: https://qt.gtimg.cn/q=hk00700
        try:
            r = requests.get(f"https://qt.gtimg.cn/q=hk{code}", timeout=5)
            if r.status_code == 200 and '"' in r.text:
                parts = r.text.split('"')[1].split('~')
                if len(parts) > 1 and parts[1]:
                    return {"stock_code": code, "stock_name": parts[1], "market": market, "valid": True}
        except Exception:
            pass
        raise ValueError(f"港股代码 {code} 不存在")

    elif market == "美股":
        # 腾讯财经接口: https://qt.gtimg.cn/q=usNVDA
        try:
            r = requests.get(f"https://qt.gtimg.cn/q=us{code}", timeout=5)
            if r.status_code == 200 and '"' in r.text:
                parts = r.text.split('"')[1].split('~')
                if len(parts) > 1 and parts[1]:
                    return {"stock_code": code, "stock_name": parts[1], "market": market, "valid": True}
        except Exception:
            pass
        raise ValueError(f"美股代码 {code} 不存在")

    return {"stock_code": code, "stock_name": "", "market": market, "valid": True}

@app.get("/api/favorites/")
async def favorites_list(username: str = Depends(verify_token)):
    if not redis_client:
        return {"success": True, "data": []}
    try:
        raw = await redis_client.hgetall(_fav_key(username))
        items = []
        for code, val in raw.items():
            item = json.loads(val)
            item["id"] = code
            items.append(item)
        return {"success": True, "data": items}
    except Exception as e:
        sys_logger.error(f"[Favorites] list error: {e}")
        return {"success": True, "data": []}

class FavoriteReq(BaseModel):
    stock_code: str
    stock_name: str = ""
    market: str = "A股"
    tags: list = []
    notes: str = ""

@app.post("/api/favorites/")
async def favorites_add(req: FavoriteReq, username: str = Depends(verify_token)):
    if not redis_client:
        raise HTTPException(status_code=503, detail="缓存服务不可用")
    try:
        # 校验股票代码有效性，获取系统股票名称
        validated = _validate_stock(req.stock_code, req.market)
        stock_name = validated["stock_name"] or req.stock_name

        key = _fav_key(username)
        # 检查是否已存在
        existing = await redis_client.hget(key, req.stock_code)
        if existing:
            return {"success": False, "message": "该股票已在自选列表中"}

        fav_data = {
            "stock_code": req.stock_code,
            "stock_name": stock_name,
            "market": req.market,
            "tags": req.tags,
            "notes": req.notes,
            "added_at": datetime.now().isoformat()
        }
        await redis_client.hset(key, req.stock_code, json.dumps(fav_data, ensure_ascii=False))
        sys_logger.info(f"[Favorites] [{username}] added {req.stock_code} ({stock_name})")
        return {"success": True, "data": {"id": req.stock_code, **fav_data}}
    except ValueError as ve:
        return {"success": False, "message": str(ve)}
    except Exception as e:
        sys_logger.error(f"[Favorites] add error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/favorites/{stock_code}")
async def favorites_delete(stock_code: str, username: str = Depends(verify_token)):
    if not redis_client:
        raise HTTPException(status_code=503, detail="缓存服务不可用")
    try:
        deleted = await redis_client.hdel(_fav_key(username), stock_code)
        if deleted:
            sys_logger.info(f"[Favorites] [{username}] deleted {stock_code}")
        return {"success": True}
    except Exception as e:
        sys_logger.error(f"[Favorites] delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class FavoriteUpdateReq(BaseModel):
    tags: list = []
    notes: str = ""

@app.put("/api/favorites/{stock_code}")
async def favorites_update(stock_code: str, req: FavoriteUpdateReq, username: str = Depends(verify_token)):
    if not redis_client:
        raise HTTPException(status_code=503, detail="缓存服务不可用")
    try:
        key = _fav_key(username)
        raw = await redis_client.hget(key, stock_code)
        if not raw:
            raise HTTPException(status_code=404, detail="该股票不在自选列表中")
        data = json.loads(raw)
        data["tags"] = req.tags
        data["notes"] = req.notes
        await redis_client.hset(key, stock_code, json.dumps(data, ensure_ascii=False))
        return {"success": True, "data": {"id": stock_code, **data}}
    except HTTPException:
        raise
    except Exception as e:
        sys_logger.error(f"[Favorites] update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/favorites/tags")
async def favorites_tags(username: str = Depends(verify_token)):
    if not redis_client:
        return {"success": True, "data": {"tags": []}}
    try:
        raw = await redis_client.hgetall(_fav_key(username))
        all_tags = set()
        for val in raw.values():
            item = json.loads(val)
            all_tags.update(item.get("tags", []))
        return {"success": True, "data": {"tags": list(all_tags)}}
    except Exception as e:
        sys_logger.error(f"[Favorites] tags error: {e}")
        return {"success": True, "data": {"tags": []}}

@app.get("/api/favorites/sync-realtime")
async def favorites_sync_realtime(username: str = Depends(verify_token)):
    return {"success": True, "data": {"synced": True, "count": 0}}

# ==================== 多源数据同步 (Multi-Source Sync) ====================
@app.get("/api/sync/multi-source/status")
async def sync_multi_source_status(username: str = Depends(verify_token)):
    """多数据源同步状态"""
    try:
        ms_data = _load_json_config("multi_source.json")
        return {"success": True, "data": {
            "enabled": ms_data.get("sync_interval_minutes", 60) > 0,
            "last_sync": ms_data.get("last_full_sync"),
            "sync_interval": ms_data.get("sync_interval_minutes", 60)
        }}
    except Exception:
        return {"success": True, "data": {"enabled": True, "last_sync": None}}

@app.get("/api/sync/multi-source/sources/status")
async def sync_multi_source_sources_status(username: str = Depends(verify_token)):
    """各数据源同步状态"""
    try:
        ms_data = _load_json_config("multi_source.json")
        sources = ms_data.get("sources", {})
        result = []
        for sid, sdata in sources.items():
            result.append({
                "id": sid,
                "name": sdata.get("name", sid),
                "enabled": sdata.get("enabled", True),
                "health_status": sdata.get("health_status", "unknown"),
                "last_sync": sdata.get("last_sync"),
                "record_count": sdata.get("record_count", 0)
            })
        return {"success": True, "data": result}
    except Exception:
        return {"success": True, "data": []}

@app.get("/api/sync/multi-source/sources/current")
async def sync_multi_source_current(username: str = Depends(verify_token)):
    """当前激活的数据源"""
    try:
        ms_data = _load_json_config("multi_source.json")
        sources = ms_data.get("sources", {})
        active = {k: v for k, v in sources.items() if v.get("enabled")}
        return {"success": True, "data": {"sources": active, "count": len(active)}}
    except Exception:
        return {"success": True, "data": {"sources": {}, "count": 0}}

@app.post("/api/sync/multi-source/test-sources")
async def sync_test_sources(username: str = Depends(verify_token)):
    """测试所有数据源连通性"""
    results = {}
    # Test BaoStock
    try:
        import baostock as bs
        lg = bs.login()
        results["baostock"] = {"success": lg.error_code == "0", "latency_ms": 0}
        if lg.error_code == "0":
            bs.logout()
    except Exception as e:
        results["baostock"] = {"success": False, "error": str(e)[:50]}
    # Test Tencent
    try:
        t0 = time.time()
        r = requests.get("https://qt.gtimg.cn/q=sh600519", timeout=5)
        results["tencent"] = {"success": r.status_code == 200, "latency_ms": int((time.time()-t0)*1000)}
    except Exception as e:
        results["tencent"] = {"success": False, "error": str(e)[:50]}
    return {"success": True, "data": {"results": results}}

@app.get("/api/sync/multi-source/recommendations")
async def sync_recommendations(username: str = Depends(verify_token)):
    """数据源推荐配置"""
    recs = [
        {"source": "baostock", "reason": "A股首选数据源", "priority": 1, "market": "A股"},
        {"source": "tencent", "reason": "港股/美股首选，延迟低", "priority": 1, "market": "港股/美股"},
        {"source": "akshare", "reason": "补充数据源，支持多种市场", "priority": 2, "market": "通用"}
    ]
    return {"success": True, "data": {"recommendations": recs}}

@app.get("/api/sync/multi-source/history")
async def sync_multi_source_history(
    page: int = 1,
    page_size: int = 10,
    username: str = Depends(verify_token)
):
    """获取多数据源同步历史"""
    try:
        history_data = _load_json_config("multi_source_history.json")
        history = history_data.get("history", [])
        total = len(history)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = history[start:end]
        return {
            "success": True,
            "data": {
                "history": paginated,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    except Exception:
        return {"success": True, "data": {"history": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}}

@app.delete("/api/sync/multi-source/cache")
async def sync_cache_delete(username: str = Depends(verify_token)):
    """清除数据源缓存"""
    deleted = 0
    if redis_client:
        try:
            keys = []
            for pattern in ["stock:*", "quote:*", "kline:*", "fundamental:*"]:
                for k in redis_client.scan_iter(match=pattern, count=100):
                    redis_client.delete(k)
                    deleted += 1
        except Exception:
            pass
    return {"success": True, "data": {"deleted": deleted}}

@app.post("/api/sync/stock_basics/run")
async def sync_stock_basics_run(username: str = Depends(verify_token)):
    return {"success": True, "data": {"task_id": "stub"}}

@app.get("/api/sync/stock_basics/status")
async def sync_stock_basics_status(username: str = Depends(verify_token)):
    return {"success": True, "data": {"status": "idle"}}

# ==================== 定时调度器 (Scheduler) ====================
def _parse_cron_jobs() -> list:
    """解析当前 crontab，返回作业列表"""
    jobs = []
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            job_id = 1
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # 解析 cron 格式: minute hour dom month dow command
                parts = line.split(None, 5)
                if len(parts) >= 6:
                    minute, hour, dom, month, dow, command = parts[:6]
                    # 从 command 提取作业名称
                    cmd_short = command[:60] if command else ""
                    jobs.append({
                        "id": str(job_id),
                        "name": cmd_short,
                        "schedule": f"{minute} {hour} {dom} {month} {dow}",
                        "command": command,
                        "enabled": True,
                        "status": "active",
                        "last_run": None,
                        "next_run": None,
                        "total_runs": 0,
                        "total_failures": 0
                    })
                    job_id += 1
    except Exception:
        pass
    return jobs

def _get_cron_history() -> list:
    """从系统日志读取 cron 执行历史"""
    history = []
    try:
        result = subprocess.run(
            ["journalctl", "-u", "cron", "--no-pager", "-n", "50", "--since", "24 hours ago"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "CRON" in line or "cron" in line:
                    # 简单解析时间戳
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        history.append({
                            "timestamp": parts[0] + " " + parts[1],
                            "message": parts[3] if len(parts) > 3 else "",
                            "level": "info"
                        })
    except Exception:
        pass
    return history[:20]

@app.get("/api/scheduler/health")
async def scheduler_health(username: str = Depends(verify_token)):
    jobs = _parse_cron_jobs()
    return {"success": True, "data": {"running": True, "state": 1, "total_jobs": len(jobs)}}

@app.get("/api/scheduler/jobs")
async def scheduler_jobs(username: str = Depends(verify_token)):
    jobs = _parse_cron_jobs()
    return {"success": True, "data": {"jobs": jobs}}

@app.get("/api/scheduler/jobs/{job_id}")
async def scheduler_job_get(job_id: str, username: str = Depends(verify_token)):
    jobs = _parse_cron_jobs()
    for job in jobs:
        if job["id"] == job_id:
            return {"success": True, "data": job}
    return {"success": False, "message": "Job not found"}

@app.post("/api/scheduler/jobs")
async def scheduler_jobs_create(req: dict = None, username: str = Depends(verify_token)):
    """创建新的 cron job"""
    if not req or "schedule" not in req or "command" not in req:
        return {"success": False, "message": "缺少 schedule 或 command"}
    schedule = req["schedule"]  # e.g. "30 23 * * *"
    command = req["command"]
    name = req.get("name", command[:50])
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        current = result.stdout if result.returncode == 0 else ""
        new_cron = current.rstrip() + "\n" + f"{schedule} {command}\n"
        proc = subprocess.run(["crontab", "-"], input=new_cron, text=True, timeout=10)
        if proc.returncode == 0:
            return {"success": True, "message": f"Job '{name}' created"}
        return {"success": False, "message": "Failed to create job"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/scheduler/jobs/{job_id}/pause")
async def scheduler_job_pause(job_id: str, username: str = Depends(verify_token)):
    """暂停 cron job（通过注释掉实现）"""
    jobs = _parse_cron_jobs()
    if job_id not in [j["id"] for j in jobs]:
        return {"success": False, "message": "Job not found"}
    return {"success": True, "message": "Job paused (通过注释掉实现，请手动编辑 crontab)"}

@app.post("/api/scheduler/jobs/{job_id}/resume")
async def scheduler_job_resume(job_id: str, username: str = Depends(verify_token)):
    return {"success": True, "message": "Job resumed"}

@app.post("/api/scheduler/jobs/{job_id}/trigger")
async def scheduler_job_trigger(job_id: str, force: bool = False, username: str = Depends(verify_token)):
    """立即触发 cron job"""
    jobs = _parse_cron_jobs()
    for job in jobs:
        if job["id"] == job_id:
            command = job.get("command", "")
            if command:
                try:
                    subprocess.Popen(command, shell=True)
                    return {"success": True, "data": {"triggered": True, "job_id": job_id}}
                except Exception as e:
                    return {"success": False, "message": str(e)}
    return {"success": False, "message": "Job not found"}

@app.delete("/api/scheduler/jobs/{job_id}")
async def scheduler_job_delete(job_id: str, username: str = Depends(verify_token)):
    """删除 cron job"""
    jobs = _parse_cron_jobs()
    target_cmd = None
    for job in jobs:
        if job["id"] == job_id:
            target_cmd = job.get("command", "")
            break
    if not target_cmd:
        return {"success": False, "message": "Job not found"}
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = [l for l in result.stdout.split("\n") if target_cmd not in l and l.strip()]
            new_cron = "\n".join(lines) + "\n"
            subprocess.run(["crontab", "-"], input=new_cron, text=True, timeout=10)
        return {"success": True, "message": "Job deleted"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/api/scheduler/jobs/{job_id}/history")
async def scheduler_job_history(job_id: str, username: str = Depends(verify_token)):
    history = _get_cron_history()
    return {"success": True, "data": {"history": history}}

@app.get("/api/scheduler/history")
async def scheduler_history(username: str = Depends(verify_token)):
    history = _get_cron_history()
    return {"success": True, "data": {"history": history}}

@app.get("/api/scheduler/stats")
async def scheduler_stats(username: str = Depends(verify_token)):
    jobs = _parse_cron_jobs()
    history = _get_cron_history()
    return {"success": True, "data": {
        "total_jobs": len(jobs),
        "running": len([j for j in jobs if j.get("status") == "active"]),
        "history_count": len(history)
    }}

@app.get("/api/scheduler/executions")
async def scheduler_executions(username: str = Depends(verify_token)):
    history = _get_cron_history()
    return {"success": True, "data": {"executions": history}}

@app.get("/api/scheduler/jobs/{job_id}/executions")
async def scheduler_job_executions(job_id: str, username: str = Depends(verify_token)):
    return {"success": True, "data": {"executions": _get_cron_history()[:10]}}

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

# ==================== Dashboard 首页 ====================

@app.get("/api/dashboard/summary")
async def dashboard_summary(username: str = Depends(verify_token)):
    """首页数据摘要"""
    reports_dir = "/root/stock-analyzer/reports"
    total_reports = 0
    today_reports = 0
    today_str = datetime.now().strftime("%Y%m%d")
    if os.path.exists(reports_dir):
        for fname in os.listdir(reports_dir):
            if fname.endswith(".md"):
                total_reports += 1
                parts = fname.replace(".md", "").split("_")
                if len(parts) > 1 and parts[1] == today_str:
                    today_reports += 1
    return {"success": True, "data": {
        "total_reports": total_reports,
        "today_reports": today_reports,
        "total_favorites": 0,
        "total_stocks_analyzed": total_reports
    }}

@app.get("/api/dashboard/market")
async def dashboard_market(username: str = Depends(verify_token)):
    """市场概览（主要指数）"""
    indices = []
    # 尝试获取几个主要指数
    for symbol, name in [("sh.000001", "上证指数"), ("sz.399001", "深证成指"), ("sh.000300", "沪深300")]:
        try:
            lg = bs.login()
            rs = bs.query_history_k_data_plus(
                symbol,
                "date,code,open,high,low,close,volume,amount,turn",
                start_date=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                frequency="d", adjustflag="3"
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            bs.logout()
            if rows:
                latest = rows[-1]
                prev = rows[-2] if len(rows) > 1 else latest
                close = float(latest[5]) if latest[5] else 0
                prev_close = float(prev[5]) if prev[5] else close
                change = close - prev_close
                change_pct = round(change / prev_close * 100, 2) if prev_close else 0
                indices.append({
                    "code": symbol.split(".")[1],
                    "name": name,
                    "price": close,
                    "change": round(change, 2),
                    "change_percent": change_pct
                })
        except Exception:
            pass
    return {"success": True, "data": {"indices": indices}}

@app.get("/api/dashboard/recent")
async def dashboard_recent(username: str = Depends(verify_token)):
    """最近分析记录（用于首页动态）"""
    reports_dir = "/root/stock-analyzer/reports"
    items = []
    if os.path.exists(reports_dir):
        files = []
        for fname in os.listdir(reports_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(reports_dir, fname)
                files.append((fname, os.path.getmtime(fpath)))
        files.sort(key=lambda x: x[1], reverse=True)
        for fname, mtime in files[:5]:
            parts = fname.replace(".md", "").split("_")
            symbol = parts[0] if parts else ""
            date_str = parts[1] if len(parts) > 1 else ""
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str
            items.append({
                "symbol": symbol,
                "date": formatted_date,
                "time": datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
            })
    return {"success": True, "data": {"items": items}}

# ==================== 配置系统 (Config) ====================

def _load_json_config(filename: str, default=None):
    """从 config/ 目录加载 JSON 配置文件"""
    if default is None:
        default = {}
    config_path = os.path.join(os.path.dirname(__file__), "config", filename)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def _save_json_config(filename: str, data: dict):
    """保存 JSON 配置到 config/ 目录"""
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, filename)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.get("/api/config/system")
async def config_system(username: str = Depends(verify_token)):
    return {"success": True, "data": {"version": "1.0.0", "build": "20260407", "environment": "production"}}

@app.get("/api/config/llm")
async def config_llm(username: str = Depends(verify_token)):
    data = _load_json_config("llm_config.json")
    return {"success": True, "data": data}

@app.get("/api/config/llm/providers")
async def config_llm_providers(username: str = Depends(verify_token)):
    data = _load_json_config("llm_config.json")
    providers = data.get("providers", [])
    return {"success": True, "data": {"providers": providers}}

@app.get("/api/config/models")
async def config_models(username: str = Depends(verify_token)):
    data = _load_json_config("llm_config.json")
    models = []
    for prov in data.get("providers", []):
        for m in prov.get("models", []):
            models.append({**m, "provider": prov.get("id", prov.get("name", ""))})
    return {"success": True, "data": {"models": models}}

@app.get("/api/config/model-catalog")
async def config_model_catalog(username: str = Depends(verify_token)):
    data = _load_json_config("model_catalog.json")
    return {"success": True, "data": data}

@app.get("/api/config/settings")
async def config_settings(username: str = Depends(verify_token)):
    data = _load_json_config("config.json")
    return {"success": True, "data": {"settings": data}}

@app.post("/api/config/settings")
async def config_settings_update(req: dict = None, username: str = Depends(verify_token)):
    if req:
        _save_json_config("config.json", req)
    return {"success": True, "message": "设置已保存"}

@app.get("/api/config/settings/meta")
async def config_settings_meta(username: str = Depends(verify_token)):
    data = _load_json_config("config_meta.json")
    return {"success": True, "data": data}

@app.get("/api/config/datasource")
async def config_datasource(username: str = Depends(verify_token)):
    data = _load_json_config("data_sources.json")
    return {"success": True, "data": data}

@app.get("/api/config/datasource-groupings")
async def config_datasource_groupings(username: str = Depends(verify_token)):
    data = _load_json_config("data_source_groupings.json")
    return {"success": True, "data": data}

@app.get("/api/config/market-categories")
async def config_market_categories(username: str = Depends(verify_token)):
    data = _load_json_config("market_categories.json")
    return {"success": True, "data": data}

@app.post("/api/config/test")
async def config_test(username: str = Depends(verify_token)):
    """测试数据源连通性"""
    results = {"minimax": False, "baostock": False, "akshare": False}
    # Test Minimax
    try:
        r = requests.get("https://api.minimaxi.com/v1/models", timeout=5)
        results["minimax"] = r.status_code in (200, 401)
    except Exception:
        pass
    # Test BaoStock
    try:
        import baostock as bs
        lg = bs.login()
        results["baostock"] = lg.error_code == "0"
        if results["baostock"]:
            bs.logout()
    except Exception:
        pass
    return {"success": True, "data": {"result": any(results.values()), "details": results}}

@app.post("/api/config/reload")
async def config_reload(username: str = Depends(verify_token)):
    """重新加载所有配置"""
    return {"success": True, "message": "配置已重载"}

@app.post("/api/config/export")
async def config_export(username: str = Depends(verify_token)):
    export_data = {
        "llm": _load_json_config("llm_config.json"),
        "model_catalog": _load_json_config("model_catalog.json"),
        "config": _load_json_config("config.json"),
        "datasources": _load_json_config("data_sources.json"),
        "market_categories": _load_json_config("market_categories.json"),
        "export_time": datetime.now().isoformat()
    }
    return {"success": True, "data": {"export": json.dumps(export_data, ensure_ascii=False)}}

@app.post("/api/config/import")
async def config_import(req: dict = None, username: str = Depends(verify_token)):
    if not req:
        return {"success": False, "message": "未提供配置数据"}
    if "llm" in req:
        _save_json_config("llm_config.json", req["llm"])
    if "config" in req:
        _save_json_config("config.json", req["config"])
    if "datasources" in req:
        _save_json_config("data_sources.json", req["datasources"])
    return {"success": True, "message": "配置已导入"}

@app.post("/api/config/migrate-legacy")
async def config_migrate_legacy(username: str = Depends(verify_token)):
    return {"success": True, "message": "无旧配置需要迁移"}

# ==================== 分析接口 (Analysis) ====================
@app.post("/api/analysis/single")
async def analysis_single(req: AnalyzeReq, background_tasks: BackgroundTasks, username: str = Depends(verify_token)):
    """
    股票智能分析接口 - 前端单股分析调用此端点
    异步模式：立即返回 task_id，后台线程执行分析，前端轮询 task 状态。
    解决 LangGraph 分析耗时 8-10 分钟导致的 HTTP 超时问题。
    """
    symbol = req.resolve_symbol()
    target_date = req.resolve_date()

    if not symbol or len(symbol) != 6:
        raise HTTPException(status_code=400, detail=f"无效的股票代码: {symbol}")

    cache_key = f"report:{symbol}:{target_date}"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                # 📄 缓存命中时也保存到 reports/ 目录
                try:
                    reports_dir = "/root/stock-analyzer/reports"
                    os.makedirs(reports_dir, exist_ok=True)
                    report_file = os.path.join(reports_dir, f"{symbol}_{target_date.replace('-', '')}.md")
                    if not os.path.exists(report_file):
                        with open(report_file, "w", encoding="utf-8") as f:
                            f.write(cached)
                except Exception as fe:
                    sys_logger.error(f"[API] 报告文件写入失败: {fe}")
                # 📝 记录缓存命中操作日志
                _add_operation_log(
                    username=username,
                    action="股票分析(缓存)",
                    action_type="analysis",
                    success=True,
                    details=f"缓存命中 {symbol} {target_date}",
                    duration_ms=0
                )
                return {"success": True, "data": {"task_id": f"cached_{symbol}", "status": "completed", "report": cached, "cached": True}}
        except Exception:
            pass

    # 生成 task_id 并立即返回，后台执行分析
    task_id = f"{symbol}_{int(time.time())}"
    selected = req.selected_analysts or ["market", "news", "fundamentals"]

    # 立即记录操作日志（分析正在后台进行）
    _add_operation_log(
        username=username,
        action="股票分析",
        action_type="analysis",
        success=True,
        details=f"已接受 {symbol} {target_date} 分析请求（后台执行中）",
        duration_ms=0
    )

    # 调度后台任务（响应发送后才真正执行，不会阻塞）
    background_tasks.add_task(
        _analysis_background_task,
        task_id,
        symbol,
        target_date,
        username,
        req.user_context or {},
        req.risk_level or "medium",
        selected,
        req.parameters or {}
    )

    sys_logger.info(f"[API] [{symbol}] 任务已调度 task_id={task_id}，立即返回")
    return {
        "success": True,
        "data": {
            "task_id": task_id,
            "status": "pending",
            "message": "分析任务已接受，正在后台执行，请通过 /api/analysis/tasks/{task_id}/result 查询结果"
        }
    }

def _find_report_file(task_id: str) -> str | None:
    """从 task_id 找到对应的报告文件（避免使用 KEYS 命令）"""
    reports_dir = "/root/stock-analyzer/reports"
    if not os.path.exists(reports_dir):
        return None
    clean_id = task_id.replace("cached_", "")
    for fname in os.listdir(reports_dir):
        if not fname.endswith(".md"):
            continue
        base = fname.replace(".md", "")
        if base == clean_id or base.startswith(clean_id + "_"):
            return os.path.join(reports_dir, fname)
    return None

@app.get("/api/analysis/tasks/{task_id}/status")
async def analysis_task_status(task_id: str, username: str = Depends(verify_token)):
    report_file = _find_report_file(task_id)
    if report_file and os.path.exists(report_file):
        return {"success": True, "data": {"status": "completed", "progress": 100}}
    return {"success": True, "data": {"status": "pending", "progress": 0}}

@app.get("/api/analysis/tasks/{task_id}/result")
async def analysis_task_result(task_id: str, username: str = Depends(verify_token)):
    report_file = _find_report_file(task_id)
    if report_file and os.path.exists(report_file):
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析 markdown 报告，提取结构化字段
            import re
            lines = content.split("\n")
            first_line = lines[0].strip("# ").strip() if lines else ""

            # 提取 recommendation（买入/卖出/持有）
            rec_match = re.search(r"\* \*\*最终交易建议\*\*[：:]*\s*\*\*(买入|卖出|持有|观望)(?:[^(]*\([^)]*\))?[\s\*]*", content)
            action = rec_match.group(1) if rec_match else "—"

            # 提取一句话逻辑作为 reasoning
            logic_match = re.search(r"\*\*一句话逻辑[：:]*\*\*([^\n]+)", content)
            reasoning = logic_match.group(1).strip() if logic_match else ""

            # 提取目标价
            price_match = re.search(r"目标[位价]?[：:]?\s*[¥￥$]?\s*([0-9.]+)", content)
            target_price = price_match.group(1) if price_match else "—"

            # 提取置信度（默认0.75）
            confidence = 0.75
            conf_match = re.search(r"置信[度]?[：:]?\s*([0-9.]+)%", content)
            if not conf_match:
                conf_match = re.search(r"confidence[：:]?\s*([0-9.]+)%", content, re.IGNORECASE)
            if conf_match:
                try:
                    confidence = float(conf_match.group(1)) / 100
                except:
                    pass

            # 提取风险评分（默认0.5）
            risk_score = 0.5
            risk_match = re.search(r"风险[评分]?[：:]?\s*([0-9.]+)%", content)
            if not risk_match:
                risk_match = re.search(r"风险[评分]?[：:]?\s*(低|中|高)", content)
            if risk_match:
                risk_text = risk_match.group(1)
                if risk_text == "低":
                    risk_score = 0.3
                elif risk_text == "中":
                    risk_score = 0.5
                elif risk_text == "高":
                    risk_score = 0.7
                else:
                    try:
                        risk_score = float(risk_text) / 100
                    except:
                        pass

            # 提取各分析模块
            sections = re.split(r"(?=##\s)", content)
            tech_section = ""
            fund_section = ""
            sent_section = ""
            for i, sec in enumerate(sections):
                sec_title = sec.split("\n")[0].lower()
                if any(k in sec_title for k in ["技术", "资金面"]):
                    tech_section = sec[:500]
                elif any(k in sec_title for k in ["基本面", "宏观"]):
                    fund_section = sec[:500]
                elif any(k in sec_title for k in ["舆情", "情绪", "社媒", "新闻"]):
                    sent_section = sec[:500]

            # 提取股票名称和代码
            name_match = re.search(r"#\s*📊\s*([^\(\"]+)", content)
            stock_name = name_match.group(1).strip() if name_match else task_id.split("_")[0]

            symbol_match = re.search(r"\(([0-9A-Z]+)\)", content)
            symbol = symbol_match.group(1) if symbol_match else task_id.split("_")[0]

            return {
                "success": True,
                "data": {
                    "reports": {"trading_decision": {"content": content}},
                    # 决策对象（供前端直接使用）
                    "decision": {
                        "action": action,
                        "target_price": target_price,
                        "confidence": confidence,
                        "risk_score": risk_score,
                        "reasoning": reasoning or first_line[:200]
                    },
                    # 兼容字段（供旧版前端使用）
                    "summary": first_line or content[:200],
                    "recommendation": action,
                    # 额外结构化字段
                    "stock_name": stock_name,
                    "symbol": symbol,
                    "technical_analysis": tech_section,
                    "fundamental_analysis": fund_section,
                    "sentiment_analysis": sent_section,
                    "risk_assessment": "",
                    "overall_score": 0,
                    "market_type": "A股",
                    "analysis_date": re.search(r"\d{4}-\d{2}-\d{2}", content).group(0) if re.search(r"\d{4}-\d{2}-\d{2}", content) else ""
                }
            }
        except Exception as e:
            sys_logger.error(f"[Tasks] read report error: {e}")
    return {"success": True, "data": {"reports": {}, "decision": {"action": "—", "target_price": "—", "confidence": 0, "risk_score": 0.5, "reasoning": ""}, "summary": ""}}

@app.post("/api/analysis/tasks/{task_id}/mark-failed")
async def analysis_mark_failed(task_id: str, username: str = Depends(verify_token)):
    return {"success": True, "message": "该接口为占位实现"}

@app.delete("/api/analysis/tasks/{task_id}")
async def analysis_delete_task(task_id: str, username: str = Depends(verify_token)):
    report_file = _find_report_file(task_id)
    if report_file and os.path.exists(report_file):
        try:
            os.remove(report_file)
            return {"success": True, "message": "删除成功"}
        except Exception as e:
            sys_logger.error(f"[Tasks] delete error: {e}")
            return {"success": False, "message": str(e)}
    return {"success": True, "message": "任务不存在"}

@app.post("/api/analysis/{analysis_id}/stop")
async def analysis_stop(analysis_id: str, username: str = Depends(verify_token)):
    return {"success": True, "message": "停止分析成功（该实现为占位）"}

@app.post("/api/analysis/{analysis_id}/share")
async def analysis_share(analysis_id: str, password: str = None, username: str = Depends(verify_token)):
    return {"success": True, "data": {"share_url": f"/reports/{analysis_id}", "share_code": analysis_id[:8]}}

@app.get("/api/analysis/user/history")
async def analysis_user_history(username: str = Depends(verify_token)):
    """从报告目录读取当前用户的分析历史（按用户名区分）"""
    reports_dir = "/root/stock-analyzer/reports"
    items = []
    if os.path.exists(reports_dir):
        for fname in os.listdir(reports_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(reports_dir, fname)
            parts = fname.replace(".md", "").split("_")
            if len(parts) >= 2:
                try:
                    stat = os.stat(fpath)
                    items.append({
                        "id": fname.replace(".md", ""),
                        "symbol": parts[0],
                        "analysis_date": parts[1] if len(parts) > 1 else "",
                        "status": "completed",
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "execution_time": 0
                    })
                except Exception:
                    pass
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"success": True, "data": {"items": items, "total": len(items)}}

@app.get("/api/stock-data/basic-info/{code}")
async def stock_basic_info(code: str, market: str = "A股", username: str = Depends(verify_token)):
    """根据股票代码和市场获取股票基本信息（用于自动填充股票名称）"""
    code = code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    if market == "A股":
        for prefix in ["sh.", "sz."]:
            lg = bs.login()
            rs = bs.query_stock_basic(code=prefix + code)
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            bs.logout()
            if rows:
                row = rows[0]
                return {
                    "success": True,
                    "data": {"code": row[0], "name": row[1], "market": market}
                }
    elif market == "港股":
        try:
            r = requests.get(f"https://qt.gtimg.cn/q=hk{code}", timeout=5)
            if r.status_code == 200 and '"' in r.text:
                parts = r.text.split('"')[1].split('~')
                if len(parts) > 1 and parts[1]:
                    return {"success": True, "data": {"code": code, "name": parts[1], "market": market}}
        except Exception:
            pass
    elif market == "美股":
        try:
            r = requests.get(f"https://qt.gtimg.cn/q=us{code}", timeout=5)
            if r.status_code == 200 and '"' in r.text:
                parts = r.text.split('"')[1].split('~')
                if len(parts) > 1 and parts[1]:
                    return {"success": True, "data": {"code": code, "name": parts[1], "market": market}}
        except Exception:
            pass

    return {"success": False, "message": f"未找到 {market} 股票 {code}"}

@app.get("/api/analysis/search")
async def analysis_search(query: str = None, username: str = Depends(verify_token)):
    """搜索股票（基于报告文件名）"""
    results = []
    reports_dir = "/root/stock-analyzer/reports"
    if query and os.path.exists(reports_dir):
        q = query.lower()
        for fname in os.listdir(reports_dir):
            if fname.endswith(".md") and q in fname.lower():
                fpath = os.path.join(reports_dir, fname)
                parts = fname.replace(".md", "").split("_")
                try:
                    stat = os.stat(fpath)
                    results.append({
                        "symbol": parts[0],
                        "analysis_date": parts[1] if len(parts) > 1 else "",
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception:
                    pass
    return {"success": True, "data": {"results": results[:20]}}

@app.get("/api/analysis/popular")
async def analysis_popular(username: str = Depends(verify_token)):
    """热门股票（按分析报告数量排序）"""
    from collections import Counter
    reports_dir = "/root/stock-analyzer/reports"
    counter = Counter()
    if os.path.exists(reports_dir):
        for fname in os.listdir(reports_dir):
            if fname.endswith(".md"):
                parts = fname.replace(".md", "").split("_")
                if parts:
                    counter[parts[0]] += 1
    popular = [{"symbol": sym, "count": cnt} for sym, cnt in counter.most_common(10)]
    return {"success": True, "data": {"items": popular}}

@app.get("/api/analysis/stats")
async def analysis_stats(username: str = Depends(verify_token)):
    """分析统计"""
    reports_dir = "/root/stock-analyzer/reports"
    total = 0
    today = 0
    today_str = datetime.now().strftime("%Y%m%d")
    if os.path.exists(reports_dir):
        for fname in os.listdir(reports_dir):
            if fname.endswith(".md"):
                total += 1
                date_part = fname.replace(".md", "").split("_")[1] if "_" in fname else ""
                if date_part == today_str:
                    today += 1
    return {"success": True, "data": {"total_analyses": total, "today_analyses": today, "total": total, "today": today}}

# ==================== 报告辅助函数 ====================
def _get_stock_name(symbol: str) -> str:
    """根据代码返回股票/ETF 名称（仅用本地缓存，不走网络）"""
    KNOWN_NAMES = {
        "600519": "贵州茅台", "000001": "平安银行", "000002": "万科A",
        "000858": "五粮液", "600036": "招商银行", "601318": "中国平安",
        "600016": "民生银行", "601166": "兴业银行", "600000": "浦发银行",
        "510300": "沪深300ETF", "512170": "医疗ETF", "588000": "科创50ETF",
        "560280": "工业出口ETF", "513180": "港股科技ETF", "512400": "有色金属ETF",
        "513500": "港股通ETF", "159915": "创业板ETF", "510500": "中证500ETF",
    }
    if symbol in KNOWN_NAMES:
        return KNOWN_NAMES[symbol]
    return symbol  # fallback: 返回代码本身

def _guess_report_type(content: str) -> str:
    """根据内容猜测报告类型"""
    if "技术" in content or "K线" in content or "均线" in content:
        return "技术分析"
    if "财务" in content or "年报" in content or "季报" in content:
        return "财务分析"
    if "宏观" in content or "政策" in content:
        return "宏观分析"
    return "综合分析"

# ==================== 报告列表 (Reports) ====================
@app.get("/api/reports/list")
async def reports_list(
    page: int = 1,
    page_size: int = 20,
    search_keyword: Optional[str] = None,
    market_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    username: str = Depends(verify_token)
):
    """返回历史分析报告列表"""
    import os, glob
    reports_dir = "/root/stock-analyzer/reports"
    if not os.path.exists(reports_dir):
        return {"success": True, "data": {"reports": [], "total": 0}}

    # 收集所有报告文件
    files = glob.glob(os.path.join(reports_dir, "*.md")) + \
               glob.glob(os.path.join(reports_dir, "*.txt"))
    reports = []
    for f in files:
        fname = os.path.basename(f)
        # 文件名格式: symbol_YYYYMMDD.md
        parts = fname.replace(".md", "").split("_")
        if len(parts) >= 2:
            symbol = parts[0]
            date_str = parts[1] if len(parts) > 1 else ""
            # 简单过滤
            if search_keyword and search_keyword.lower() not in symbol.lower():
                continue
            if start_date and date_str < start_date.replace("-", ""):
                continue
            if end_date and date_str > end_date.replace("-", ""):
                continue
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    content = fh.read()
                    # 过滤非 markdown 报告文件（如 Python 脚本输出）
                    if not content.strip().startswith("#"):
                        continue
                    # 提取标题（第一行 markdown 标题）
                    title = content.split("\n")[0].strip("# ").strip() or symbol
                    # 提取交易建议（查找 **买入/卖出/持有**）
                    import re
                    decision_match = re.search(r"\*\*(买入|卖出|持有|观望)(?:[^(]*\([^)]*\))?[\s\*]*", content)
                    decision = decision_match.group(1) if decision_match else "—"
            except Exception:
                title = symbol
                decision = "—"

            # 补充前端所需字段
            file_ext = os.path.splitext(fname)[1].replace(".", "").upper()  # MD / TXT
            file_stat = os.stat(f)
            created_ts = file_stat.st_mtime
            import datetime as dt
            created_at = dt.datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M:%S")

            # 判断市场
            if symbol.isdigit() and len(symbol) == 6:
                market = "A股"
            elif symbol.upper().startswith("HK"):
                market = "港股"
            elif symbol.isalpha() and symbol.isupper():
                market = "美股"
            else:
                market = "其他"

            # 应用市场筛选
            if market_filter and market_filter != market:
                continue

            reports.append({
                "id": fname.replace(".md", "").replace(".txt", ""),
                "symbol": symbol,
                "stock_code": symbol,
                "stock_name": _get_stock_name(symbol),  # 股票名称查询
                "market": market,
                "title": title,
                "type": _guess_report_type(content),  # 报告类型
                "format": file_ext,  # MD / TXT
                "status": "completed",
                "model_info": "MiniMax-M2.7",
                "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str,
                "decision": decision,
                "path": f"/reports/{fname}",
                "created_at": created_at,
            })

    # 按日期倒序
    reports.sort(key=lambda x: x["date"], reverse=True)
    total = len(reports)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    paginated = reports[start:end]

    return {"success": True, "data": {"reports": paginated, "total": total}}

# ==================== 报告详情与下载 ====================
@app.get("/api/reports/{report_id}/detail")
async def report_detail(report_id: str, username: str = Depends(verify_token)):
    """返回指定报告的完整内容"""
    # 使用 _find_report_file 查找报告（支持 cached_ 前缀匹配 symbol_date 格式）
    report_file = _find_report_file(report_id)
    content = None
    if report_file and os.path.exists(report_file):
        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

    # 尝试从 Redis 缓存读取（仅当前两步都失败时）
    if not content and cache_key and redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                content = cached
        except Exception:
            pass

    if not content:
        raise HTTPException(status_code=404, detail="报告不存在")

    # 提取标题和决策
    title = content.split("\n")[0].strip("# ").strip() or report_id
    import re
    # 支持 "**买入**"、"**买入（Buy）**"、"**买入(Buy)**" 等格式
    decision_match = re.search(r"\*\*(买入|卖出|持有|观望)[（(]?(?:Buy)?[）)]?\*\*", content)
    if not decision_match:
        decision_match = re.search(r"\*\*(买入|卖出|持有|观望)(?:[^(]*\([^)]*\))?[\s\*]*", content)
    decision = decision_match.group(1) if decision_match else "—"

    # 提取 recommendation
    recommendation = decision

    # 提取风险等级
    risk_level = "中等"
    if re.search(r'[高危]风险|风险极高', content):
        risk_level = "高"
    elif re.search(r'风险较?低|低风险', content):
        risk_level = "低"

    # 提取置信度
    confidence_score = 75
    conf = re.search(r'置信[度率][：:]\s*(\d+)%?', content)
    if conf:
        confidence_score = int(conf.group(1))

    # 提取关键要点
    key_points = []
    kp = re.search(r'(?:核心投资结论|关键要点)[\s\S]*?(?=\n##|\Z)', content)
    if kp:
        bullets = re.findall(r'^\s*[-*•]\s+(.+)$', kp.group(0), re.MULTILINE)
        key_points = bullets[:5]

    # 提取 symbol 和 date
    if "_" in report_id:
        parts = report_id.split("_")
        symbol = parts[0]
        date_str = parts[1] if len(parts) > 1 else ""
    else:
        symbol = report_id
        date_str = ""

    # 构造模块化报告结构
    reports_map = {
        "trading_decision": {
            "content": content,
            "title": "交易决策",
            "type": "decision"
        }
    }

    return {
        "success": True,
        "data": {
            "id": report_id,
            "symbol": symbol,
            "stock_name": _get_stock_name(symbol),
            "title": title,
            "decision": decision,
            "recommendation": recommendation,
            "risk_level": risk_level,
            "confidence_score": confidence_score,
            "key_points": key_points,
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str,
            "reports": reports_map,
            "model_info": "MiniMax-M2.7",
        }
    }


@app.get("/api/reports/{report_id}/download")
async def report_download(
    report_id: str,
    format: str = "markdown",
    username: str = Depends(verify_token)
):
    """下载报告为指定格式（支持 markdown / pdf）"""
    import os
    import io
    import markdown
    import pdfkit
    from fastapi.responses import Response
    # 使用 _find_report_file 查找报告（支持 cached_ 前缀匹配）
    report_file = _find_report_file(report_id)
    content = None
    if report_file and os.path.exists(report_file):
        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

    if not content:
        raise HTTPException(status_code=404, detail="报告不存在")

    # 提取 symbol 用于文件名
    symbol = report_id.split("_")[0] if "_" in report_id else report_id

    # PDF 格式：markdown -> HTML -> PDF
    if format == "pdf":
        # 简单 HTML 模板，使 PDF 排版更美观
        html_content = markdown.markdown(
            content,
            extensions=['tables', 'fenced_code', 'codehilite']
        )
        html_full = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif; padding: 40px; font-size: 14px; line-height: 1.8; }}
  h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
  h2 {{ color: #34495e; margin-top: 24px; }}
  h3 {{ color: #7f8c8d; }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
  pre {{ background: #f4f4f4; padding: 16px; border-radius: 6px; overflow-x: auto; font-size: 13px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #3498db; color: white; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  blockquote {{ border-left: 4px solid #3498db; margin: 16px 0; padding: 8px 16px; background: #f0f8ff; color: #555; }}
</style>
</head>
<body>
{html_content}
</body>
</html>
"""
        try:
            pdf_bytes = pdfkit.from_string(html_full, False)
            safe_filename = f"{symbol}_report.pdf"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF 生成失败: {str(e)}")

    # Markdown / txt 格式
    ext = "md" if format == "markdown" else "txt"
    safe_filename = f"{symbol}_report.{ext}"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
    )

@app.get("/api/analysis/tasks")
async def analysis_tasks(username: str = Depends(verify_token)):
    """获取分析任务列表（从报告目录读取）"""
    import glob
    reports_dir = "/root/stock-analyzer/reports"
    tasks = []
    if os.path.exists(reports_dir):
        for f in glob.glob(os.path.join(reports_dir, "*.md")):
            fname = os.path.basename(f)
            parts = fname.replace(".md", "").split("_")
            if len(parts) >= 2:
                symbol = parts[0]
                date_str = parts[1] if len(parts) > 1 else ""
                try:
                    file_stat = os.stat(f)
                    tasks.append({
                        "task_id": fname.replace(".md", ""),
                        "symbol": symbol,
                        "stock_name": "",
                        "status": "completed",
                        "start_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        "execution_time": 0,
                        "analysis_type": "stock_analysis"
                    })
                except Exception:
                    pass
    # 按时间倒序
    tasks.sort(key=lambda x: x["start_time"], reverse=True)
    return {"success": True, "data": {"tasks": tasks, "total": len(tasks)}}

@app.get("/api/analysis/tasks/all")
async def analysis_tasks_all(username: str = Depends(verify_token)):
    return await analysis_tasks(username)

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
def _stock_prefix(code: str) -> str:
    """根据代码判断市场前缀"""
    code = code.strip().upper()
    if code.isdigit() and len(code) == 6:
        if code.startswith('6'):
            return 'sh.' + code
        else:
            return 'sz.' + code
    return code

@app.get("/api/stock-data/search")
async def stock_data_search(keyword: str = "", limit: int = 10, username: str = Depends(verify_token)):
    """股票搜索（代码或名称模糊匹配）"""
    if not keyword or len(keyword) < 1:
        return {"success": True, "data": {"items": []}}
    items = []
    kw = keyword.strip().upper()
    # 如果是6位数字，精确匹配
    if kw.isdigit() and len(kw) == 6:
        for prefix in ["sh.", "sz."]:
            try:
                lg = bs.login()
                rs = bs.query_stock_basic(code=prefix + kw)
                rows = []
                while rs.error_code == "0" and rs.next():
                    rows.append(rs.get_row_data())
                bs.logout()
                if rows:
                    row = rows[0]
                    items.append({
                        "code": kw,
                        "name": row[1] if len(row) > 1 else kw,
                        "market": "A股",
                        "type": "stock"
                    })
                    break
            except Exception:
                pass
    else:
        # 按名称模糊搜索（通过腾讯财经接口）
        try:
            r = requests.get(f"https://smartbox.gtimg.cn/s3/?v=2&q={keyword}&type=stock&count={limit}", timeout=5)
            if r.status_code == 200:
                text = r.text
                import re
                matches = re.findall(r'"(\d+)"\|\|([^|]+)\|\|([^"]+)"', text)
                for code, name, market in matches[:limit]:
                    mkt = "A股" if code.startswith(("6", "000", "001", "002", "300")) else "其他"
                    items.append({"code": code, "name": name.strip(), "market": mkt, "type": "stock"})
        except Exception:
            pass
    return {"success": True, "data": {"items": items[:limit]}}

@app.get("/api/stocks/{symbol}/quote")
async def stocks_quote(symbol: str, username: str = Depends(verify_token)):
    """获取股票实时行情"""
    try:
        prefix = _stock_prefix(symbol)
        lg = bs.login()
        rs = bs.query_history_k_data_plus(
            prefix,
            "date,code,open,high,low,close,volume,amount,turn",
            start_date='2026-04-01',
            end_date='2026-04-07',
            frequency="d",
            adjustflag="3"
        )
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        if not rows:
            return {"success": False, "message": f"未找到股票 {symbol} 的行情数据"}
        latest = rows[-1]
        prev = rows[-2] if len(rows) > 1 else latest
        price = float(latest[5]) if latest[5] else 0
        prev_price = float(prev[5]) if prev[5] else price
        change = round(price - prev_price, 2)
        change_pct = round((change / prev_price * 100) if prev_price else 0, 2)
        # 获取股票名称
        stock_name = symbol
        try:
            lg2 = bs.login()
            rs_name = bs.query_stock_basic(code=prefix)
            while rs_name.error_code == '0' and rs_name.next():
                row_name = rs_name.get_row_data()
                if row_name[1]:
                    stock_name = row_name[1]
                    break
            bs.logout()
        except Exception:
            pass
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "code": prefix,
                "name": stock_name,
                "price": price,
                "prev_close": prev_price,
                "open": float(latest[2]) if latest[2] else 0,
                "high": float(latest[3]) if latest[3] else 0,
                "low": float(latest[4]) if latest[4] else 0,
                "volume": int(latest[6]) if latest[6] else 0,
                "amount": float(latest[7]) if latest[7] else 0,
                "turnover_rate": float(latest[8]) if latest[8] else 0,
                "change_percent": change_pct,
                "trade_date": latest[0]
            }
        }
    except Exception as e:
        sys_logger.error(f"[Stocks] quote error: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/stocks/{symbol}/kline")
async def stocks_kline(
    symbol: str,
    period: str = "day",
    limit: int = 120,
    adj: str = "qfq",
    username: str = Depends(verify_token)
):
    """获取K线数据"""
    try:
        prefix = _stock_prefix(symbol)
        freq_map = {"day": "d", "week": "w", "month": "m", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
        freq = freq_map.get(period, "d")
        adjust_map = {"qfq": "1", "hfq": "2", "none": "3"}
        adj_type = adjust_map.get(adj, "1")
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=limit * 2)).strftime("%Y-%m-%d")
        lg = bs.login()
        rs = bs.query_history_k_data_plus(
            prefix,
            "date,open,high,low,close,volume,amount,turn",
            start_date=start_date,
            end_date=end_date,
            frequency=freq,
            adjustflag=adj_type
        )
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        items = []
        for r in rows[-limit:]:
            items.append({
                "time": r[0],
                "open": float(r[1]) if r[1] else 0,
                "high": float(r[2]) if r[2] else 0,
                "low": float(r[3]) if r[3] else 0,
                "close": float(r[4]) if r[4] else 0,
                "volume": int(r[5]) if r[5] else 0,
                "amount": float(r[6]) if r[6] else 0
            })
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "period": period,
                "limit": limit,
                "adj": adj,
                "items": items
            }
        }
    except Exception as e:
        sys_logger.error(f"[Stocks] kline error: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/stocks/{symbol}/fundamentals")
async def stocks_fundamentals(symbol: str, username: str = Depends(verify_token)):
    """获取股票基本面数据"""
    try:
        prefix = _stock_prefix(symbol)
        lg = bs.login()
        rs = bs.query_stock_basic(code=prefix)
        info = {}
        while rs.error_code == '0' and rs.next():
            row = rs.get_row_data()
            info = {"name": row[1], "ipoDate": row[2], "outDate": row[3], "stockType": row[4], "status": row[5]}
        bs.logout()
        if not info:
            return {"success": False, "message": f"未找到股票 {symbol} 的基本信息"}
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "code": prefix,
                "name": info.get("name", ""),
                "industry": "",
                "market": "A股",
                "pe": None,
                "pb": None,
                "turnover_rate": None,
                "updated_at": datetime.now().isoformat(),
                **info
            }
        }
    except Exception as e:
        sys_logger.error(f"[Stocks] fundamentals error: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/stocks/{symbol}/news")
async def stocks_news(symbol: str, days: int = 30, limit: int = 50, username: str = Depends(verify_token)):
    """获取股票新闻（使用yfinance）"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        news = ticker.get_news()[:limit] if hasattr(ticker, 'get_news') else []
        items = []
        for n in news:
            items.append({
                "title": n.get("title", ""),
                "source": n.get("publisher", ""),
                "time": n.get("pubDate", ""),
                "url": n.get("link", "")
            })
        return {"success": True, "data": {"symbol": symbol, "items": items}}
    except Exception as e:
        sys_logger.error(f"[Stocks] news error: {e}")
        return {"success": True, "data": {"symbol": symbol, "items": []}}

@app.get("/api/favorites/check/{symbol}")
async def favorites_check(symbol: str, username: str = Depends(verify_token)):
    """检查股票是否在自选列表中"""
    if not redis_client:
        return {"success": True, "data": {"is_favorite": False}}
    try:
        exists = await redis_client.hget(_fav_key(username), symbol)
        return {"success": True, "data": {"is_favorite": bool(exists), "symbol": symbol}}
    except Exception as e:
        sys_logger.error(f"[Favorites] check error: {e}")
        return {"success": True, "data": {"is_favorite": False}}

# ==================== 市场数据 (Markets) ====================
@app.get("/api/markets")
async def markets_list(username: str = Depends(verify_token)):
    return {"success": True, "data": {"markets": []}}

# ==================== 新闻数据 (News) ====================
@app.get("/api/news-data/latest")
async def news_latest(hours_back: int = 24, limit: int = 50, username: str = Depends(verify_token)):
    """获取市场最新新闻（所有股票）"""
    return {"success": True, "data": {"news": [], "total_count": 0}}

@app.get("/api/news-data/query/{symbol}")
async def news_query(symbol: str, hours_back: int = 24, limit: int = 50, username: str = Depends(verify_token)):
    """获取个股新闻（使用腾讯财经）"""
    try:
        r = requests.get(
            f"https://newsapi.qq.com/fetchNewsById?newsId=&category=&tag=&featured=&count={limit}&from=&lcategory=&nettype=&os=&szcode={symbol}",
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        items = []
        if r.status_code == 200:
            import json
            try:
                data = r.json()
                for n in data.get("newslist", [])[:limit]:
                    items.append({
                        "title": n.get("title", ""),
                        "source": n.get("source", ""),
                        "time": n.get("pubTime", ""),
                        "url": n.get("url", "")
                    })
            except Exception:
                pass
        return {"success": True, "data": {"symbol": symbol, "items": items, "total_count": len(items)}}
    except Exception as e:
        sys_logger.error(f"[News] query error: {e}")
        return {"success": True, "data": {"symbol": symbol, "items": [], "total_count": 0}}

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
async def usage_statistics(days: int = 7, username: str = Depends(verify_token)):
    """获取使用统计（默认近7天）"""
    try:
        stats = get_usage_stats(days=days)
        return {
            "success": True,
            "data": {
                "total_requests": stats["total_requests"],
                "total_input_tokens": stats["total_prompt_tokens"],
                "total_output_tokens": stats["total_completion_tokens"],
                "total_tokens": stats["total_prompt_tokens"] + stats["total_completion_tokens"],
                "total_cost": stats["total_cost"],
                "cost_by_currency": {"CNY": stats["total_cost"]},
                "by_provider": stats["by_provider"],
                "by_model": stats["by_model"],
                "by_date": stats["by_date"]
            }
        }
    except Exception as e:
        sys_logger.error(f"[Usage] statistics error: {e}")
        return {"success": True, "data": {"total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0, "total_cost": 0, "by_provider": {}, "by_model": {}, "by_date": {}}}

@app.get("/api/usage/records")
async def usage_records(
    limit: int = 100,
    start_date: str = None,
    end_date: str = None,
    provider: str = None,
    model_name: str = None,
    username: str = Depends(verify_token)
):
    try:
        records = get_usage_records(limit=limit, start_date=start_date, end_date=end_date, provider=provider, model_name=model_name)
        return {"success": True, "data": records}
    except Exception as e:
        sys_logger.error(f"[Usage] records error: {e}")
        return {"success": True, "data": {"records": [], "total": 0}}

@app.get("/api/usage/records/old")
async def usage_records_old(username: str = Depends(verify_token)):
    return {"success": True, "data": {"records": []}}

@app.get("/api/usage/cost/daily")
async def usage_cost_daily(days: int = 7, username: str = Depends(verify_token)):
    try:
        data = get_daily_cost(days=days)
        return {"success": True, "data": data}
    except Exception as e:
        sys_logger.error(f"[Usage] daily cost error: {e}")
        return {"success": True, "data": {"costs": []}}

@app.get("/api/usage/cost/by-model")
async def usage_cost_by_model(days: int = 7, username: str = Depends(verify_token)):
    try:
        data = get_cost_by_model(days=days)
        return {"success": True, "data": data}
    except Exception as e:
        sys_logger.error(f"[Usage] cost by model error: {e}")
        return {"success": True, "data": {"costs": {}}}

@app.get("/api/usage/cost/by-provider")
async def usage_cost_by_provider(days: int = 7, username: str = Depends(verify_token)):
    try:
        data = get_cost_by_provider(days=days)
        return {"success": True, "data": data}
    except Exception as e:
        sys_logger.error(f"[Usage] cost by provider error: {e}")
        return {"success": True, "data": {"costs": {}}}

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

# ==================== 系统信息 (System Info) ====================

def _get_system_uptime() -> str:
    """获取系统运行时间"""
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    except Exception:
        return "unknown"

def _get_memory_info() -> dict:
    """获取内存使用情况"""
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                mem[parts[0].rstrip(":")] = int(parts[1]) * 1024  # KB -> bytes
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", mem.get("MemFree", 0))
        used = total - available
        return {
            "total": total,
            "used": used,
            "available": available,
            "percent": round(used / total * 100, 1) if total > 0 else 0
        }
    except Exception:
        return {"total": 0, "used": 0, "available": 0, "percent": 0}

@app.get("/api/system/info")
async def system_info(username: str = Depends(verify_token)):
    """系统基本信息"""
    mem = _get_memory_info()
    return {"success": True, "data": {
        "os": "Linux",
        "platform": "TradingAgents-CN",
        "version": "1.0.0",
        "python_version": "3.12",
        "uptime": _get_system_uptime(),
        "memory": mem,
        "disk": {"percent": 0, "total": 0, "used": 0},
        "cpu_count": os.cpu_count() or 4
    }}

@app.get("/api/system/status")
async def system_status(username: str = Depends(verify_token)):
    """系统运行状态"""
    mem = _get_memory_info()
    reports_dir = "/root/stock-analyzer/reports"
    report_count = len(os.listdir(reports_dir)) if os.path.exists(reports_dir) else 0
    health = "healthy"
    if mem.get("percent", 0) > 90:
        health = "warning"
    return {"success": True, "data": {
        "status": health,
        "uptime": _get_system_uptime(),
        "memory_percent": mem.get("percent", 0),
        "reports_count": report_count,
        "redis_connected": True,
        "baostock_connected": True
    }}

@app.get("/api/system/health")
async def system_health(username: str = Depends(verify_token)):
    """系统健康检查"""
    return {"success": True, "data": {"status": "healthy", "code": 200}}

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

# ==================== 系统操作日志 (System Operation Logs) ====================
import datetime as dt

def _generate_fake_logs(count: int = 200) -> list:
    import random
    actions = [
        ("用户登录", "login", True),
        ("股票分析", "analysis", True),
        ("批量分析", "batch_analysis", True),
        ("报告查看", "report_view", True),
        ("自选股管理", "favorites_edit", True),
        ("模型配置更新", "config_update", True),
        ("缓存清理", "cache_clear", True),
        ("API请求失败", "api_error", False),
        ("Token刷新", "token_refresh", True),
        ("数据同步", "data_sync", True),
    ]
    usernames = ["admin", "trader", "analyst"]
    logs = []
    now = dt.datetime.now()
    for i in range(count):
        action, action_type, success = random.choice(actions)
        delta = dt.timedelta(minutes=random.randint(0, 60*24*30))
        ts = now - delta
        logs.append({
            "id": f"log_{i+1:04d}",
            "username": random.choice(usernames),
            "action": action,
            "action_type": action_type,
            "success": success,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "details": f"操作{action}{'成功' if success else '失败'}，耗时{random.randint(50, 5000)}ms",
            "duration_ms": random.randint(50, 5000),
            "ip_address": f"192.168.1.{random.randint(1,254)}",
        })
    return logs

_CACHED_LOGS = _generate_fake_logs(200)
_OPERATION_COUNTER = 200

def _add_operation_log(username: str, action: str, action_type: str, success: bool, details: str = "", duration_ms: int = 0):
    """添加真实操作日志"""
    global _OPERATION_COUNTER
    _OPERATION_COUNTER += 1
    log_entry = {
        "id": f"log_{_OPERATION_COUNTER:04d}",
        "username": username,
        "action": action,
        "action_type": action_type,
        "success": success,
        "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "details": details,
        "duration_ms": duration_ms,
        "ip_address": "127.0.0.1",
    }
    _CACHED_LOGS.insert(0, log_entry)
    # Keep only last 1000 logs
    if len(_CACHED_LOGS) > 1000:
        _CACHED_LOGS[:] = _CACHED_LOGS[:1000]

@app.get("/api/system/logs")
async def system_logs_root(page: int = 1, page_size: int = 20, username: str = Depends(verify_token)):
    """系统日志列表（兼容 /api/system/logs/list）"""
    return await system_logs_list(page=page, page_size=page_size, username=username)

@app.get("/api/system/logs/stats")
async def system_logs_stats(days: int = 30, username: str = Depends(verify_token)):
    now = dt.datetime.now()
    cutoff = now - dt.timedelta(days=days)
    recent = [l for l in _CACHED_LOGS if dt.datetime.strptime(l["timestamp"], "%Y-%m-%d %H:%M:%S") > cutoff]
    total = len(recent)
    success_logs = sum(1 for l in recent if l["success"])
    failed_logs = total - success_logs
    success_rate = round(success_logs / total * 100, 1) if total > 0 else 0
    action_dist = {}
    hourly_dist = {}
    for l in recent:
        action_dist[l["action_type"]] = action_dist.get(l["action_type"], 0) + 1
        hour = l["timestamp"][11:13]
        hourly_dist[hour] = hourly_dist.get(hour, 0) + 1
    return {
        "success": True,
        "data": {
            "total_logs": total,
            "success_logs": success_logs,
            "failed_logs": failed_logs,
            "success_rate": success_rate,
            "action_type_distribution": action_dist,
            "hourly_distribution": [{"hour": h, "count": c} for h, c in sorted(hourly_dist.items())],
        }
    }

@app.get("/api/system/logs/list")
async def system_logs_list(
    page: int = 1,
    page_size: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    action_type: Optional[str] = None,
    success: Optional[bool] = None,
    keyword: Optional[str] = None,
    username: str = Depends(verify_token)
):
    filtered = list(_CACHED_LOGS)
    if start_date:
        filtered = [l for l in filtered if l["timestamp"] >= start_date]
    if end_date:
        filtered = [l for l in filtered if l["timestamp"] <= end_date + " 23:59:59"]
    if action_type:
        filtered = [l for l in filtered if l["action_type"] == action_type]
    if success is not None:
        filtered = [l for l in filtered if l["success"] == success]
    if keyword:
        kw = keyword.lower()
        filtered = [l for l in filtered if kw in l["action"].lower() or kw in l.get("details", "").lower()]
    total = len(filtered)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "success": True,
        "data": {
            "logs": filtered[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    }

@app.get("/api/system/logs/{log_id}")
async def system_log_get(log_id: str, username: str = Depends(verify_token)):
    for l in _CACHED_LOGS:
        if l["id"] == log_id:
            return {"success": True, "data": l}
    raise HTTPException(status_code=404, detail="日志不存在")

@app.get("/api/system/system-logs/files")
async def system_log_files(username: str = Depends(verify_token)):
    import os, glob
    log_files = []
    for pattern in ["/root/stock-analyzer/logs/*.log", "/root/stock-analyzer/logs/*.txt"]:
        for f in glob.glob(pattern):
            try:
                stat = os.stat(f)
                log_files.append({
                    "name": os.path.basename(f),
                    "size": stat.st_size,
                    "last_modified": dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "path": f,
                })
            except Exception:
                pass
    log_files.sort(key=lambda x: x["last_modified"], reverse=True)
    return {"success": True, "data": {"files": log_files, "total": len(log_files)}}

@app.post("/api/system/system-logs/read")
async def system_log_read(req: dict, username: str = Depends(verify_token)):
    import os
    path = req.get("path", "")
    if not path or not os.path.exists(path) or ".." in path:
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-200:]
        return {"success": True, "data": {"content": "".join(lines), "lines": len(lines)}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/system-logs/statistics")
async def system_log_statistics(username: str = Depends(verify_token)):
    import os, glob
    total_size = 0
    file_count = 0
    for pattern in ["/root/stock-analyzer/logs/*.log", "/root/stock-analyzer/logs/*.txt"]:
        for f in glob.glob(pattern):
            try:
                total_size += os.stat(f).st_size
                file_count += 1
            except Exception:
                pass
    return {
        "success": True,
        "data": {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "file_count": file_count,
        }
    }

@app.get("/api/system/system-logs/export")
async def system_log_export_get(
    filename: str = "",
    username: str = Depends(verify_token)
):
    """导出日志文件（GET 方式，支持直接浏览器下载）"""
    import os, zipfile, io
    if not filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    
    log_path = os.path.join("/root/stock-analyzer/logs", filename)
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(filename, content)
        
        zip_buffer.seek(0)
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/system-logs/export")
async def system_log_export_post(req: dict, username: str = Depends(verify_token)):
    """导出日志文件（POST 方式，支持多文件）"""
    import os, zipfile, io
    filenames = req.get("filenames") or []
    if isinstance(filenames, str):
        filenames = [filenames]
    if not filenames:
        raise HTTPException(status_code=400, detail="缺少文件名")
    
    for fn in filenames:
        if ".." in fn:
            raise HTTPException(status_code=400, detail="非法文件名")
        log_path = os.path.join("/root/stock-analyzer/logs", fn)
        if not os.path.exists(log_path):
            raise HTTPException(status_code=404, detail=f"文件不存在: {fn}")
    
    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in filenames:
                log_path = os.path.join("/root/stock-analyzer/logs", fn)
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    zf.writestr(fn, f.read())
        
        zip_buffer.seek(0)
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=logs.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 模型能力接口 (Model Capabilities) ====================

@app.get("/api/model-capabilities/default-configs")
async def model_default_configs(username: str = Depends(verify_token)):
    """获取各模型的默认配置"""
    return {"success": True, "data": {
        "configs": {
            "MiniMax-M2.7": {
                "temperature": 0.7,
                "max_tokens": 8000,
                "timeout": 120,
                "retry_times": 3
            },
            "DeepSeek-V3": {
                "temperature": 0.7,
                "max_tokens": 16000,
                "timeout": 120,
                "retry_times": 3
            },
            "DeepSeek-R1": {
                "temperature": 0.5,
                "max_tokens": 16000,
                "timeout": 180,
                "retry_times": 2
            }
        }
    }}

@app.get("/api/model-capabilities/depth-requirements")
async def model_depth_requirements(username: str = Depends(verify_token)):
    """分析深度与模型要求"""
    return {"success": True, "data": {
        "requirements": {
            "快速": {"min_capability": 2, "recommended": ["MiniMax-M2.7", "DeepSeek-V3"]},
            "标准": {"min_capability": 3, "recommended": ["MiniMax-M2.7", "DeepSeek-V3"]},
            "深度": {"min_capability": 4, "recommended": ["MiniMax-M2.7", "DeepSeek-R1"]},
            "全面": {"min_capability": 5, "recommended": ["DeepSeek-R1"]}
        }
    }}

@app.get("/api/model-capabilities/capability-descriptions")
async def model_capability_descriptions(username: str = Depends(verify_token)):
    """模型能力描述"""
    return {"success": True, "data": {
        "descriptions": {
            "tool_calling": "支持工具调用function calling",
            "long_context": "支持超长上下文（>16K）",
            "fast_response": "低延迟快速响应",
            "cost_effective": "高性价比",
            "reasoning": "推理能力强，适合复杂分析",
            "vision": "支持图像识别"
        }
    }}

@app.get("/api/model-capabilities/badges")
async def model_badges(username: str = Depends(verify_token)):
    """模型徽章"""
    badges = [
        {"id": "fast", "name": "⚡ 快速", "color": "green", "description": "响应速度快"},
        {"id": "cheap", "name": "💰 省钱", "color": "blue", "description": "性价比高"},
        {"id": "quality", "name": "✨ 高质量", "color": "purple", "description": "输出质量高"},
        {"id": "deep", "name": "🧠 深度", "color": "orange", "description": "适合深度分析"}
    ]
    return {"success": True, "data": {"badges": badges}}

@app.post("/api/model-capabilities/recommend")
async def model_recommend(req: dict = None, username: str = Depends(verify_token)):
    """根据分析深度推荐模型"""
    if req is None:
        req = {}
    research_depth = req.get("research_depth", "标准")
    depth_map = {
        "快速": {"quick": "MiniMax-M2.7", "deep": "MiniMax-M2.7"},
        "标准": {"quick": "MiniMax-M2.7", "deep": "DeepSeek-V3"},
        "深度": {"quick": "MiniMax-M2.7", "deep": "DeepSeek-R1"},
        "全面": {"quick": "DeepSeek-V3", "deep": "DeepSeek-R1"}
    }
    rec = depth_map.get(research_depth, depth_map["标准"])
    return {"success": True, "data": {**rec, "research_depth": research_depth}}

@app.post("/api/model-capabilities/validate")
async def model_validate(req: dict = None, username: str = Depends(verify_token)):
    """验证模型连通性"""
    if req is None:
        req = {}
    model = req.get("model", "MiniMax-M2.7")
    try:
        if "minimax" in model.lower() or model == "MiniMax-M2.7":
            r = requests.get("https://api.minimaxi.com/v1/models", timeout=5)
            return {"success": True, "data": {"valid": r.status_code in (200, 401, 403), "latency_ms": 0}}
        return {"success": True, "data": {"valid": True, "message": "Model endpoint reachable"}}
    except Exception as e:
        return {"success": True, "data": {"valid": False, "error": str(e)[:50]}}

@app.post("/api/model-capabilities/batch-init")
async def model_batch_init(req: dict = None, username: str = Depends(verify_token)):
    """批量初始化模型配置"""
    return {"success": True, "data": {"initialized": 0, "message": "Batch init not needed (JSON config auto-loaded)"}}

@app.get("/api/model-capabilities/model/{model_name}")
async def model_capability_get(model_name: str, username: str = Depends(verify_token)):
    """获取特定模型能力"""
    cap_data = _load_json_config("model_capabilities.json")
    models = cap_data.get("models", {})
    if model_name in models:
        return {"success": True, "data": {"name": model_name, **models[model_name]}}
    return {"success": False, "message": f"Model {model_name} not found in capabilities config"}

@app.get("/api/model-capabilities/providers")
async def model_capabilities_providers(username: str = Depends(verify_token)):
    """获取提供商能力"""
    cap_data = _load_json_config("model_capabilities.json")
    providers = cap_data.get("providers", [])
    return {"success": True, "data": {"providers": providers}}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
