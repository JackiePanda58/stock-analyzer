#!/usr/bin/env python3
import logging
import time
import requests
import redis
from typing import Optional, List

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
WATCHLIST_KEY = "watchlist:default"
API_URL = "http://127.0.0.1:8080/api/v1/analyze"
REQUEST_TIMEOUT = 600
REQUEST_INTERVAL = 30

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

# ==================== JWT 全局 Token 管理 ====================
GLOBAL_TOKEN: Optional[str] = None


def get_token() -> Optional[str]:
    """
    登录获取 JWT Token，并缓存到全局变量
    避免每次分析请求都重新登录
    """
    global GLOBAL_TOKEN
    if GLOBAL_TOKEN:
        return GLOBAL_TOKEN
    try:
        res = requests.post(
            "http://127.0.0.1:8080/api/v1/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        if res.status_code == 200:
            GLOBAL_TOKEN = res.json().get("access_token")
            logger.info("✅ [JWT] 令牌获取成功，已缓存")
            return GLOBAL_TOKEN
        else:
            logger.error(f"❌ [JWT] 登录失败，状态码: {res.status_code}")
    except Exception as e:
        logger.error(f"❌ [JWT] 获取令牌请求异常: {e}")
    return None


def analyze_stock(stock_code: str):
    """
    调用 /api/v1/analyze，自动携带 JWT Token
    Token 失效时自动重新登录获取
    """
    token = get_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {"symbol": stock_code}
    start_time = time.time()
    try:
        response = requests.post(API_URL, json=payload, timeout=REQUEST_TIMEOUT, headers=headers)
        elapsed = time.time() - start_time

        # Token 失效 (401)，自动重新登录后重试一次
        if response.status_code == 401:
            logger.warning(f"[JWT] Token 已失效，尝试重新登录...")
            global GLOBAL_TOKEN
            GLOBAL_TOKEN = None
            token = get_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
                response = requests.post(API_URL, json=payload, timeout=REQUEST_TIMEOUT, headers=headers)
                elapsed = time.time() - start_time

        if response.status_code == 200:
            return {"success": True, "duration": elapsed, "error": None}
        return {"success": False, "duration": elapsed, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
    except Exception as e:
        return {"success": False, "duration": time.time() - start_time, "error": str(e)}


def connect_redis():
    try:
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        logger.error(f"❌ Redis 连接失败: {e}")
        return None


def run_cruiser():
    redis_client = connect_redis()
    if not redis_client:
        return

    try:
        members = redis_client.smembers(WATCHLIST_KEY)
        watchlist = sorted(members) if members else None
    except Exception as e:
        logger.error(f"从 Redis 读取自选股失败: {e}")
        return

    if not watchlist:
        logger.warning("⚠️ 自选股集合为空，请在 Web UI 输入指令：添加自选 600519")
        return

    total = len(watchlist)
    success_count = 0
    logger.info("=" * 50)
    logger.info(f"🚀 自选股动态巡航开始 | 标的数量：{total} | 列表：{watchlist}")
    logger.info("=" * 50)

    for index, stock_code in enumerate(watchlist, start=1):
        logger.info(f"[{index}/{total}] 正在预热标的：{stock_code} ...")
        result = analyze_stock(stock_code)

        if result["success"]:
            logger.info(f"[{index}/{total}] ✅ 成功 {stock_code} | 耗时：{result['duration']:.1f} 秒")
            success_count += 1
        else:
            logger.error(f"[{index}/{total}] ❌ 失败 {stock_code} | 耗时：{result['duration']:.1f} 秒 | 原因：{result['error']}")

        if index < total:
            time.sleep(REQUEST_INTERVAL)

    logger.info("=" * 50)
    logger.info(f"🏁 巡航结束 | 成功预热：{success_count}/{total}")


if __name__ == "__main__":
    run_cruiser()
