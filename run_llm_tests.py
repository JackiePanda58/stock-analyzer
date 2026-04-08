#!/usr/bin/env python3
"""
LLM Client Test Runner
Simple wrapper to run tests
"""
import os
import sys

# Set environment variables
os.environ["OPENAI_API_KEY"] = "sk-sp-55c61018342342eb85b9c3a8556f3a3d"
os.environ["OPENAI_BASE_URL"] = "https://coding.dashscope.aliyuncs.com/v1"

# Run the test
exec(open("/root/stock-analyzer/tests/test_llm_client.py").read())
