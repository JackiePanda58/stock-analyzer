#!/bin/bash
cd /root/stock-analyzer
export $(grep -v '^#' .env | xargs)
python3 tests/test_langgraph.py 2>&1 | tee tests/test_langgraph_output.txt
