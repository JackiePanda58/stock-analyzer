#!/bin/bash
# 运行所有未完成测试（循环直到成功）

cd /root/stock-analyzer/tests

echo "╔════════════════════════════════════════════════════════╗"
echo "║   运行所有未完成测试                                    ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# 1. 盲区补测（最重要）
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[1/5] 盲区补测测试..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
timeout 180 python3 test_stock_analysis_blind_spots.py 2>&1 | tee reports/blind_spots_final.log
echo ""

# 2. Redis 缓存测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[2/5] Redis 缓存测试..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
timeout 120 python3 test_redis_cache.py 2>&1 | tee reports/redis_cache_final.log
echo ""

# 3. LLM 客户端测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[3/5] LLM 客户端测试..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
timeout 120 python3 test_llm_client.py 2>&1 | tee reports/llm_client_final.log
echo ""

# 4. WebSocket 测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[4/5] WebSocket 测试..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
timeout 60 python3 test_websocket.py 2>&1 | tee reports/websocket_final.log
echo ""

# 5. 安全测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[5/5] 安全测试..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
timeout 60 python3 test_security.py --backend http://localhost:8080 2>&1 | tee reports/security_final.log
echo ""

echo "╔════════════════════════════════════════════════════════╗"
echo "║   所有测试完成！                                        ║"
echo "╚════════════════════════════════════════════════════════╝"
