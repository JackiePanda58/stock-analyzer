#!/bin/bash
# 运行剩余测试脚本

cd /root/stock-analyzer/tests

echo "=== 运行集成测试 ==="

echo ""
echo "1. 分析流程集成测试..."
python3 test_integration_analysis.py 2>&1 | tee reports/integration_analysis_rerun.log

echo ""
echo "2. 持仓管理集成测试..."
python3 test_integration_positions.py 2>&1 | tee reports/integration_positions_rerun.log

echo ""
echo "3. 用户认证集成测试..."
python3 test_integration_auth.py 2>&1 | tee reports/integration_auth_rerun.log

echo ""
echo "=== 所有测试完成 ==="
