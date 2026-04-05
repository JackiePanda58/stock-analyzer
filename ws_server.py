"""
独立 WebSocket 服务器
"""
import sys
sys.path.insert(0, '/root/stock-analyzer')
from dotenv import load_dotenv
load_dotenv('/root/stock-analyzer/.env', override=True)

import jwt
from fastapi import FastAPI, WebSocket
import uvicorn

# 在创建 app 之前初始化配置
from tradingagents.dataflows.config import set_config
from config.settings import TRADING_CONFIG
set_config(TRADING_CONFIG)

app = FastAPI(title="TradingAgents WS Server")
SECRET_KEY = "trading_agents_super_secret_key"
ALGORITHM = "HS256"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/api/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if token:
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except Exception:
            await websocket.close(code=4001)
            return
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "pong"})
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8083, log_level="info")
