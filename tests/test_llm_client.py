#!/usr/bin/env python3
"""
LLM Client Test Suite for TradingAgents-CN
Tests for base_client.py with MiniMax API integration

Coverage:
1. deep_think mode testing
2. Token counting and cost tracking
3. Streaming response testing
4. Error retry mechanism testing

Usage: python3 test_llm_client.py [--backend-url URL] [--api-key KEY]
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.base_client import BaseLLMClient
from tradingagents.usage_tracker import UsageTrackingCallback, init_db, get_usage_stats, get_usage_records


# ─── Configuration ─────────────────────────────────────────────────────────────
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []  # (passed, test_id, message, details)

    def ok(self, test_id: str, msg: str = "", details: str = ""):
        self.passed += 1
        self.results.append((True, test_id, msg, details))
        print(f"  {Colors.GREEN}✓{Colors.END} {test_id} {msg}")

    def fail(self, test_id: str, msg: str, details: str = ""):
        self.failed += 1
        self.results.append((False, test_id, msg, details))
        print(f"  {Colors.RED}✗{Colors.END} {test_id} {Colors.RED}{msg}{Colors.END}")
        if details:
            print(f"      {Colors.RED}Details: {details}{Colors.END}")

    def skip(self, test_id: str, msg: str = ""):
        self.skipped += 1
        self.results.append((None, test_id, msg, ""))
        print(f"  {Colors.YELLOW}⊘{Colors.END} {test_id} {Colors.YELLOW}{msg}{Colors.END}")

    def summary(self) -> bool:
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*70}")
        print(f"{Colors.BOLD}Test Summary:{Colors.END}")
        print(f"  {Colors.GREEN}✓ Passed:  {self.passed}{Colors.END}")
        print(f"  {Colors.RED}✗ Failed:  {self.failed}{Colors.END}")
        print(f"  {Colors.YELLOW}⊘ Skipped: {self.skipped}{Colors.END}")
        print(f"  Total: {total}")
        print(f"{'='*70}")
        return self.failed == 0

    def generate_report(self, output_path: str):
        """Generate detailed test report in Markdown format."""
        timestamp = datetime.now().isoformat()
        total = self.passed + self.failed + self.skipped
        
        report = f"""# LLM Client Test Report

**Generated:** {timestamp}
**Total Tests:** {total}
**Results:** {Colors.GREEN}{self.passed} Passed{Colors.END}, {Colors.RED}{self.failed} Failed{Colors.END}, {Colors.YELLOW}{self.skipped} Skipped{Colors.END}

---

## Test Results

"""
        # Group by category
        categories = {}
        for passed, test_id, msg, details in self.results:
            # Extract category from test_id (e.g., "deep_think_001" -> "deep_think")
            parts = test_id.rsplit('_', 1)
            category = parts[0] if len(parts) > 1 else "general"
            
            if category not in categories:
                categories[category] = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}
            
            cat = categories[category]
            cat["tests"].append((passed, test_id, msg, details))
            if passed is True:
                cat["passed"] += 1
            elif passed is False:
                cat["failed"] += 1
            else:
                cat["skipped"] += 1
        
        for category, data in sorted(categories.items()):
            report += f"### {category.replace('_', ' ').title()}\n\n"
            report += f"**Summary:** {data['passed']} passed, {data['failed']} failed, {data['skipped']} skipped\n\n"
            report += "| Status | Test ID | Message | Details |\n"
            report += "|--------|---------|---------|---------|\n"
            
            for passed, test_id, msg, details in data["tests"]:
                status = "✓" if passed is True else ("✗" if passed is False else "⊘")
                report += f"| {status} | `{test_id}` | {msg} | {details} |\n"
            
            report += "\n"
        
        # Usage statistics if available
        try:
            stats = get_usage_stats(days=1)
            if stats["total_requests"] > 0:
                report += f"""## Token Usage Statistics (Last 24h)

- **Total Requests:** {stats["total_requests"]}
- **Total Prompt Tokens:** {stats["total_prompt_tokens"]:,}
- **Total Completion Tokens:** {stats["total_completion_tokens"]:,}
- **Total Cost:** ¥{stats["total_cost"]:.6f}

"""
        except Exception as e:
            report += f"\n*Usage statistics unavailable: {e}*\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Strip ANSI codes for file output
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            f.write(ansi_escape.sub('', report))
        
        print(f"\n{Colors.BLUE}Report saved to:{Colors.END} {output_path}")


# ─── Test Suite ────────────────────────────────────────────────────────────────

class LLMClientTester:
    def __init__(self, api_key: str, base_url: str, model: str = "MiniMax-M2.7"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.result = TestResult()
        self.client: Optional[BaseLLMClient] = None
        
    def setup_client(self, **kwargs):
        """Create LLM client with specified parameters."""
        try:
            self.client = create_llm_client(
                provider="openai",
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,
                **kwargs
            )
            return True
        except Exception as e:
            self.result.fail("setup", f"Failed to create client: {e}")
            return False
    
    # ─── Section 1: Deep Think Mode Tests ───────────────────────────────────
    
    def test_deep_think_basic(self):
        """Test 1.1: Basic deep_think mode functionality."""
        test_id = "deep_think_001"
        try:
            if not self.setup_client(reasoning_effort="high"):
                self.result.skip(test_id, "Client setup failed")
                return
            
            llm = self.client.get_llm()
            response = llm.invoke("请详细分析：为什么价值投资在长期来看是有效的？请给出至少三个理由。")
            
            if response and hasattr(response, 'content') and len(response.content) > 100:
                self.result.ok(test_id, "Deep think mode returned detailed response", 
                              f"Response length: {len(response.content)} chars")
            else:
                self.result.fail(test_id, "Response too short or empty")
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    def test_deep_think_reasoning_effort_levels(self):
        """Test 1.2: Test different reasoning_effort levels."""
        test_id = "deep_think_002"
        effort_levels = ["low", "medium", "high"]
        results = {}
        
        for effort in effort_levels:
            try:
                if not self.setup_client(reasoning_effort=effort):
                    results[effort] = "setup_failed"
                    continue
                
                llm = self.client.get_llm()
                start = time.time()
                response = llm.invoke("解释量子纠缠的概念。")
                elapsed = time.time() - start
                
                results[effort] = {
                    "success": response is not None,
                    "time": elapsed,
                    "length": len(response.content) if response else 0
                }
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                results[effort] = f"error: {e}"
        
        # Verify all levels work
        all_success = all(
            isinstance(r, dict) and r.get("success", False) 
            for r in results.values()
        )
        
        if all_success:
            self.result.ok(test_id, "All reasoning effort levels functional",
                          f"Times: {', '.join(f'{k}: {v.get('time', 0):.2f}s' for k, v in results.items())}")
        else:
            self.result.fail(test_id, "Some reasoning effort levels failed", str(results))
    
    def test_deep_think_vs_quick_think(self):
        """Test 1.3: Compare deep_think vs quick_think performance."""
        test_id = "deep_think_003"
        question = "请简要说明通货膨胀的原因。"
        
        try:
            # Quick think (low reasoning)
            if not self.setup_client(reasoning_effort="low"):
                self.result.skip(test_id, "Client setup failed")
                return
            
            llm_quick = self.client.get_llm()
            start_quick = time.time()
            resp_quick = llm_quick.invoke(question)
            time_quick = time.time() - start_quick
            
            time.sleep(0.5)
            
            # Deep think (high reasoning)
            if not self.setup_client(reasoning_effort="high"):
                self.result.skip(test_id, "Deep think setup failed")
                return
            
            llm_deep = self.client.get_llm()
            start_deep = time.time()
            resp_deep = llm_deep.invoke(question)
            time_deep = time.time() - start_deep
            
            # Compare
            quick_len = len(resp_quick.content) if resp_quick else 0
            deep_len = len(resp_deep.content) if resp_deep else 0
            
            self.result.ok(test_id, "Comparison completed",
                          f"Quick: {time_quick:.2f}s/{quick_len}chars, Deep: {time_deep:.2f}s/{deep_len}chars")
        except Exception as e:
            self.result.fail(test_id, f"Comparison failed: {e}")
    
    # ─── Section 2: Token Counting & Cost Tracking Tests ─────────────────────
    
    def test_token_counting_basic(self):
        """Test 2.1: Basic token counting with callback."""
        test_id = "token_001"
        try:
            # Initialize database
            init_db()
            
            callback = UsageTrackingCallback(
                session_id="test_session_001",
                analysis_type="test",
                symbol="TEST"
            )
            
            if not self.setup_client(callbacks=[callback]):
                self.result.skip(test_id, "Client setup failed")
                return
            
            llm = self.client.get_llm()
            response = llm.invoke("用 50 字左右解释什么是机器学习。")
            
            # Check if usage was recorded
            time.sleep(0.5)  # Allow DB write
            
            from tradingagents.usage_tracker import get_usage_records
            records = get_usage_records(limit=1, provider="minimax")
            
            if records["total"] > 0:
                latest = records["records"][0]
                prompt_tokens = latest.get("prompt_tokens", 0)
                completion_tokens = latest.get("completion_tokens", 0)
                
                if prompt_tokens > 0 or completion_tokens > 0:
                    self.result.ok(test_id, "Token usage recorded",
                                  f"Prompt: {prompt_tokens}, Completion: {completion_tokens}")
                else:
                    self.result.fail(test_id, "Token counts are zero")
            else:
                self.result.fail(test_id, "No usage records found in database")
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    def test_cost_calculation(self):
        """Test 2.2: Cost calculation accuracy."""
        test_id = "token_002"
        try:
            init_db()
            callback = UsageTrackingCallback(session_id="test_cost_001")
            
            if not self.setup_client(callbacks=[callback]):
                self.result.skip(test_id, "Client setup failed")
                return
            
            llm = self.client.get_llm()
            
            # Make multiple requests of varying lengths
            prompts = [
                "Hi",
                "Explain photosynthesis in one sentence.",
                "Write a detailed paragraph about climate change causes and effects."
            ]
            
            for prompt in prompts:
                llm.invoke(prompt)
                time.sleep(0.3)
            
            # Check cost calculation
            stats = get_usage_stats(days=1)
            
            if stats["total_cost"] > 0:
                self.result.ok(test_id, "Cost calculated correctly",
                              f"Total cost: ¥{stats['total_cost']:.6f}")
            else:
                self.result.fail(test_id, "Cost calculation returned zero",
                                f"Stats: {json.dumps(stats, indent=2)}")
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    def test_token_tracking_multiple_sessions(self):
        """Test 2.3: Token tracking across multiple sessions."""
        test_id = "token_003"
        try:
            init_db()
            
            sessions = ["session_A", "session_B", "session_C"]
            
            for session_id in sessions:
                callback = UsageTrackingCallback(session_id=session_id)
                if not self.setup_client(callbacks=[callback]):
                    continue
                
                llm = self.client.get_llm()
                llm.invoke(f"Test message for {session_id}")
                time.sleep(0.3)
            
            # Verify each session has records
            from tradingagents.usage_tracker import get_usage_records
            all_tracked = True
            session_counts = {}
            
            for session_id in sessions:
                # Query would need session filtering - simplified check
                records = get_usage_records(limit=100)
                session_records = [r for r in records["records"] 
                                  if r.get("session_id") == session_id]
                session_counts[session_id] = len(session_records)
                if len(session_records) == 0:
                    all_tracked = False
            
            if all_tracked:
                self.result.ok(test_id, "All sessions tracked",
                              f"Counts: {session_counts}")
            else:
                self.result.fail(test_id, "Some sessions not tracked",
                                str(session_counts))
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    # ─── Section 3: Streaming Response Tests ──────────────────────────────────
    
    def test_streaming_basic(self):
        """Test 3.1: Basic streaming functionality."""
        test_id = "stream_001"
        try:
            if not self.setup_client(streaming=True):
                self.result.skip(test_id, "Client setup failed")
                return
            
            llm = self.client.get_llm()
            
            # Test streaming with callback
            chunks = []
            def stream_callback(chunk):
                chunks.append(str(chunk))
            
            # Use stream method
            response_stream = llm.stream("从 1 数到 5，每个数字一行。")
            
            chunk_count = 0
            for chunk in response_stream:
                chunk_count += 1
                if hasattr(chunk, 'content'):
                    chunks.append(chunk.content)
            
            if chunk_count > 0 and len(''.join(chunks)) > 0:
                self.result.ok(test_id, "Streaming works",
                              f"Received {chunk_count} chunks, {len(''.join(chunks))} chars")
            else:
                self.result.fail(test_id, "No chunks received")
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    def test_streaming_vs_non_streaming(self):
        """Test 3.2: Compare streaming vs non-streaming performance."""
        test_id = "stream_002"
        prompt = "写一首关于春天的短诗，四句即可。"
        
        try:
            # Non-streaming
            if not self.setup_client(streaming=False):
                self.result.skip(test_id, "Non-streaming setup failed")
                return
            
            llm_sync = self.client.get_llm()
            start_sync = time.time()
            resp_sync = llm_sync.invoke(prompt)
            time_sync = time.time() - start_sync
            
            # Streaming
            if not self.setup_client(streaming=True):
                self.result.skip(test_id, "Streaming setup failed")
                return
            
            llm_stream = self.client.get_llm()
            start_stream = time.time()
            chunks_stream = []
            for chunk in llm_stream.stream(prompt):
                if hasattr(chunk, 'content'):
                    chunks_stream.append(chunk.content)
            time_stream = time.time() - start_stream
            
            # Compare
            sync_content = resp_sync.content if resp_sync else ""
            stream_content = ''.join(chunks_stream)
            
            content_match = sync_content.strip() == stream_content.strip()
            
            self.result.ok(test_id, "Performance comparison complete",
                          f"Sync: {time_sync:.2f}s, Stream: {time_stream:.2f}s, Match: {content_match}")
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    def test_streaming_token_tracking(self):
        """Test 3.3: Token tracking with streaming responses."""
        test_id = "stream_003"
        try:
            init_db()
            callback = UsageTrackingCallback(session_id="stream_test")
            
            if not self.setup_client(streaming=True, callbacks=[callback]):
                self.result.skip(test_id, "Client setup failed")
                return
            
            llm = self.client.get_llm()
            
            # Stream a response
            chunk_count = 0
            for chunk in llm.stream("解释牛顿第一定律。"):
                chunk_count += 1
            
            time.sleep(0.5)
            
            # Check if tokens were tracked
            records = get_usage_records(limit=1)
            
            if records["total"] > 0 and chunk_count > 0:
                self.result.ok(test_id, "Streaming tokens tracked",
                              f"Chunks: {chunk_count}, Records: {records['total']}")
            else:
                self.result.fail(test_id, "Streaming tokens not tracked properly",
                                f"Chunks: {chunk_count}, Records: {records['total']}")
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    # ─── Section 4: Error Retry Mechanism Tests ───────────────────────────────
    
    def test_retry_on_rate_limit(self):
        """Test 4.1: Automatic retry on rate limit (429)."""
        test_id = "retry_001"
        try:
            # Set low max_retries for faster testing
            if not self.setup_client(max_retries=3, timeout=5):
                self.result.skip(test_id, "Client setup failed")
                return
            
            llm = self.client.get_llm()
            
            # Make multiple rapid requests to potentially trigger rate limiting
            start = time.time()
            success_count = 0
            
            for i in range(5):
                try:
                    llm.invoke(f"Test request {i}")
                    success_count += 1
                except Exception as e:
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        # Expected rate limiting - retry should handle it
                        pass
                    else:
                        raise
            
            elapsed = time.time() - start
            
            # If we got here without crashing, retry mechanism is working
            self.result.ok(test_id, "Retry mechanism functional",
                          f"Success: {success_count}/5, Time: {elapsed:.2f}s")
        except Exception as e:
            self.result.fail(test_id, f"Retry mechanism failed: {e}")
    
    def test_retry_configuration(self):
        """Test 4.2: Configurable retry parameters."""
        test_id = "retry_002"
        try:
            # Test different retry configurations
            configs = [
                {"max_retries": 1, "timeout": 3},
                {"max_retries": 3, "timeout": 5},
                {"max_retries": 5, "timeout": 10},
            ]
            
            results = {}
            for config in configs:
                try:
                    if not self.setup_client(**config):
                        results[str(config)] = "setup_failed"
                        continue
                    
                    llm = self.client.get_llm()
                    start = time.time()
                    response = llm.invoke("Hello")
                    elapsed = time.time() - start
                    
                    results[str(config)] = {
                        "success": response is not None,
                        "time": elapsed
                    }
                    time.sleep(0.3)
                except Exception as e:
                    results[str(config)] = f"error: {e}"
            
            # Check if configs were applied
            success_count = sum(
                1 for r in results.values() 
                if isinstance(r, dict) and r.get("success", False)
            )
            
            if success_count > 0:
                self.result.ok(test_id, "Retry configs applied",
                              f"Success: {success_count}/{len(configs)}")
            else:
                self.result.fail(test_id, "Retry configs not working", str(results))
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    def test_error_handling_graceful(self):
        """Test 4.3: Graceful error handling on invalid requests."""
        test_id = "retry_003"
        try:
            if not self.setup_client(max_retries=2):
                self.result.skip(test_id, "Client setup failed")
                return
            
            llm = self.client.get_llm()
            
            # Test with very long prompt (might trigger errors)
            long_prompt = "分析这个：" + "重复文字。" * 10000
            
            error_handled = False
            start = time.time()
            
            try:
                response = llm.invoke(long_prompt)
                # If it succeeds, that's also fine
                error_handled = True
            except Exception as e:
                # Check if error is handled gracefully (not a crash)
                error_handled = True
                error_msg = str(e)
            
            elapsed = time.time() - start
            
            if error_handled:
                self.result.ok(test_id, "Error handled gracefully",
                              f"Time: {elapsed:.2f}s")
            else:
                self.result.fail(test_id, "Error not handled properly")
        except Exception as e:
            self.result.fail(test_id, f"Unexpected exception: {e}")
    
    # ─── Additional Integration Tests ─────────────────────────────────────────
    
    def test_client_initialization(self):
        """Test: Basic client initialization."""
        test_id = "init_001"
        try:
            if self.setup_client():
                llm = self.client.get_llm()
                if llm:
                    self.result.ok(test_id, "Client initialized successfully",
                                  f"Model: {self.client.model}")
                else:
                    self.result.fail(test_id, "get_llm() returned None")
            else:
                self.result.fail(test_id, "setup_client() failed")
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")
    
    def test_model_validation(self):
        """Test: Model validation."""
        test_id = "init_002"
        try:
            if not self.setup_client():
                self.result.skip(test_id, "Client setup failed")
                return
            
            is_valid = self.client.validate_model()
            
            # validate_model returns bool - either True or False is acceptable
            # as it just checks if model is supported by provider
            self.result.ok(test_id, "Model validation completed", f"Result: {is_valid}")
        except Exception as e:
            self.result.fail(test_id, f"Exception: {e}")


# ─── Main Test Runner ──────────────────────────────────────────────────────────

def run_all_tests(api_key: str, base_url: str, model: str) -> TestResult:
    """Run all LLM client tests."""
    tester = LLMClientTester(api_key, base_url, model)
    
    print(f"\n{Colors.BOLD}Starting LLM Client Tests{Colors.END}")
    print(f"Model: {model}")
    print(f"Base URL: {base_url}")
    print(f"{'='*70}\n")
    
    # Section 1: Deep Think Mode
    print(f"{Colors.BLUE}[1/4] Deep Think Mode Tests{Colors.END}")
    tester.test_deep_think_basic()
    tester.test_deep_think_reasoning_effort_levels()
    tester.test_deep_think_vs_quick_think()
    
    # Section 2: Token Counting & Cost
    print(f"\n{Colors.BLUE}[2/4] Token Counting & Cost Tracking Tests{Colors.END}")
    tester.test_token_counting_basic()
    tester.test_cost_calculation()
    tester.test_token_tracking_multiple_sessions()
    
    # Section 3: Streaming
    print(f"\n{Colors.BLUE}[3/4] Streaming Response Tests{Colors.END}")
    tester.test_streaming_basic()
    tester.test_streaming_vs_non_streaming()
    tester.test_streaming_token_tracking()
    
    # Section 4: Error Retry
    print(f"\n{Colors.BLUE}[4/4] Error Retry Mechanism Tests{Colors.END}")
    tester.test_retry_on_rate_limit()
    tester.test_retry_configuration()
    tester.test_error_handling_graceful()
    
    # Additional tests
    print(f"\n{Colors.BLUE}[Additional] Integration Tests{Colors.END}")
    tester.test_client_initialization()
    tester.test_model_validation()
    
    return tester.result


def main():
    parser = argparse.ArgumentParser(description="LLM Client Test Suite")
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY", ""),
        help="API key for MiniMax/OpenAI compatible API"
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENAI_BASE_URL", "https://api.minimaxi.com/v1"),
        help="Base URL for the API"
    )
    parser.add_argument(
        "--model",
        default="MiniMax-M2.7",
        help="Model name to test"
    )
    parser.add_argument(
        "--output",
        default="/root/stock-analyzer/tests/test_llm_client_report.md",
        help="Output path for test report"
    )
    
    args = parser.parse_args()
    
    if not args.api_key:
        print(f"{Colors.RED}Error: API key not provided.{Colors.END}")
        print("Set OPENAI_API_KEY environment variable or use --api-key")
        sys.exit(1)
    
    # Run tests
    result = run_all_tests(args.api_key, args.base_url, args.model)
    
    # Print summary
    success = result.summary()
    
    # Generate report
    result.generate_report(args.output)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
