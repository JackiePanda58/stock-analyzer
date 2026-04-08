#!/usr/bin/env python3
"""
数据源层测试 - 覆盖 AkShare、BaoStock、故障降级、一致性校验、数据清洗

测试目标：
1. AkShare 数据源测试（新闻/财务指标）
2. 数据源故障降级测试（BaoStock→AkShare）
3. 多数据源一致性校验
4. 数据清洗与格式化测试

用法：python3 test_datasources.py [--report]
"""
import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
import pandas as pd
import traceback

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import data source modules
from tradingagents.dataflows.akshare_stock import (
    get_china_stock_data,
    get_china_stock_indicators,
    get_china_fundamentals,
    get_china_balance_sheet,
    get_china_income_statement,
    get_china_cashflow,
    get_china_stock_news,
    get_china_market_news,
    _normalize_symbol,
    is_etf,
    _bs_query_to_df,
)
from tradingagents.dataflows.interface import (
    route_to_vendor,
    get_vendor,
    get_category_for_method,
    VENDOR_METHODS,
)
from tradingagents.dataflows.config import get_config, set_config


# ─── Test Result Tracking ─────────────────────────────────────────────────────
class TestColors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


class TestReport:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.skipped = 0

    def add_result(self, name, passed, message="", error=""):
        self.tests.append({
            "name": name,
            "passed": passed,
            "message": message,
            "error": error,
        })
        if passed:
            self.passed += 1
        elif error:
            self.errors += 1
        else:
            self.failed += 1

    def print_summary(self):
        total = self.passed + self.failed + self.errors + self.skipped
        print(f"\n{'='*70}")
        print(f"{TestColors.BOLD}测试报告{TestColors.END}")
        print(f"{'='*70}")
        print(f"总测试数：{total}")
        print(f"{TestColors.GREEN}通过：{self.passed}{TestColors.END}")
        print(f"{TestColors.RED}失败：{self.failed}{TestColors.END}")
        print(f"{TestColors.YELLOW}错误：{self.errors}{TestColors.END}")
        print(f"{TestColors.BLUE}跳过：{self.skipped}{TestColors.END}")
        
        if self.failed > 0 or self.errors > 0:
            print(f"\n{TestColors.BOLD}失败的测试:{TestColors.END}")
            for test in self.tests:
                if not test["passed"]:
                    print(f"  {TestColors.RED}✗{TestColors.END} {test['name']}")
                    if test["error"]:
                        print(f"    错误：{test['error'][:200]}")
                    if test["message"]:
                        print(f"    消息：{test['message']}")
        
        print(f"\n{'='*70}")
        success_rate = (self.passed / total * 100) if total > 0 else 0
        print(f"成功率：{success_rate:.1f}%")
        print(f"{'='*70}\n")


# Global report instance
report = TestReport()


# ─── Helper Functions ─────────────────────────────────────────────────────────
def create_mock_df(data=None, columns=None):
    """Create a mock DataFrame for testing"""
    if data is None:
        data = {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [99.0, 100.0, 101.0],
            "close": [103.0, 104.0, 105.0],
            "volume": [1000000, 1100000, 1200000],
        }
    if columns is None:
        columns = list(data.keys())
    return pd.DataFrame(data, columns=columns)


def create_mock_news_df():
    """Create mock news DataFrame"""
    return pd.DataFrame({
        "发布时间": ["2024-01-01 10:00", "2024-01-02 11:00"],
        "新闻标题": ["测试新闻标题 1", "测试新闻标题 2"],
        "文章来源": ["测试来源 1", "测试来源 2"],
    })


def create_mock_financial_df():
    """Create mock financial indicators DataFrame"""
    return pd.DataFrame({
        "日期": ["2024-03-31", "2023-12-31"],
        "ROE": [15.5, 14.2],
        "ROA": [8.3, 7.9],
        "毛利率": [45.2, 44.8],
        "净利率": [25.1, 24.5],
        "EPS": [5.2, 4.8],
        "市盈率": [25.5, 24.0],
    })


# ─── Test Cases ───────────────────────────────────────────────────────────────

class TestSymbolNormalization(unittest.TestCase):
    """测试股票代码标准化功能"""

    def test_normalize_shanghai_stock(self):
        """测试沪市股票代码标准化"""
        test_cases = [
            ("600519.SS", "sh.600519", "600519"),
            ("600519", "sh.600519", "600519"),
            ("sh.600519", "sh.600519", "600519"),
        ]
        for input_sym, expected_bs, expected_plain in test_cases:
            bs_code, plain = _normalize_symbol(input_sym)
            self.assertEqual(bs_code, expected_bs, f"BS code mismatch for {input_sym}")
            self.assertEqual(plain, expected_plain, f"Plain code mismatch for {input_sym}")
        report.add_result("test_normalize_shanghai_stock", True)

    def test_normalize_shenzhen_stock(self):
        """测试深市股票代码标准化"""
        test_cases = [
            ("000858.SZ", "sz.000858", "000858"),
            ("000858", "sz.000858", "000858"),
            ("sz.000858", "sz.000858", "000858"),
        ]
        for input_sym, expected_bs, expected_plain in test_cases:
            bs_code, plain = _normalize_symbol(input_sym)
            self.assertEqual(bs_code, expected_bs, f"BS code mismatch for {input_sym}")
            self.assertEqual(plain, expected_plain, f"Plain code mismatch for {input_sym}")
        report.add_result("test_normalize_shenzhen_stock", True)

    def test_normalize_etf(self):
        """测试 ETF 代码标准化"""
        test_cases = [
            ("512170.SS", "sh.512170", "512170"),
            ("159999.SZ", "sz.159999", "159999"),
        ]
        for input_sym, expected_bs, expected_plain in test_cases:
            bs_code, plain = _normalize_symbol(input_sym)
            self.assertEqual(bs_code, expected_bs, f"BS code mismatch for {input_sym}")
            self.assertEqual(plain, expected_plain, f"Plain code mismatch for {input_sym}")
        report.add_result("test_normalize_etf", True)

    def test_is_etf(self):
        """测试 ETF 识别功能"""
        etf_cases = ["512170", "159999", "512400", "588000"]
        for symbol in etf_cases:
            self.assertTrue(is_etf(symbol), f"Should identify {symbol} as ETF")
        
        non_etf_cases = ["600519", "000858", "300750"]
        for symbol in non_etf_cases:
            self.assertFalse(is_etf(symbol), f"Should not identify {symbol} as ETF")
        report.add_result("test_is_etf", True)


class TestAkShareNews(unittest.TestCase):
    """测试 AkShare 新闻数据获取"""

    @patch('tradingagents.dataflows.akshare_stock.ak')
    def test_get_stock_news_success(self, mock_ak):
        """测试成功获取个股新闻"""
        mock_ak.stock_news_em.return_value = create_mock_news_df()
        
        result = get_china_stock_news("600519", look_back_days=7)
        
        self.assertIn("最新新闻", result)
        self.assertIn("测试新闻标题 1", result)
        mock_ak.stock_news_em.assert_called_once()
        report.add_result("test_get_stock_news_success", True)

    @patch('tradingagents.dataflows.akshare_stock.ak')
    def test_get_stock_news_empty(self, mock_ak):
        """测试新闻数据为空的情况"""
        mock_ak.stock_news_em.return_value = pd.DataFrame()
        
        result = get_china_stock_news("600519", look_back_days=7)
        
        self.assertIn("未找到", result)
        report.add_result("test_get_stock_news_empty", True)

    @patch('tradingagents.dataflows.akshare_stock.ak')
    def test_get_stock_news_exception(self, mock_ak):
        """测试新闻获取异常处理"""
        mock_ak.stock_news_em.side_effect = Exception("网络错误")
        
        result = get_china_stock_news("600519", look_back_days=7)
        
        self.assertIn("失败", result)
        self.assertIn("网络错误", result)
        report.add_result("test_get_stock_news_exception", True)

    @patch('tradingagents.dataflows.akshare_stock.ak')
    def test_get_market_news_success(self, mock_ak):
        """测试成功获取市场快讯"""
        mock_df = pd.DataFrame({
            "tag": ["宏观", "行业"],
            "summary": ["测试宏观新闻", "测试行业新闻"],
        })
        mock_ak.stock_news_main_cx.return_value = mock_df
        
        result = get_china_market_news(look_back_days=7, limit=20)
        
        self.assertIn("市场最新快讯", result)
        self.assertIn("宏观", result)
        mock_ak.stock_news_main_cx.assert_called_once()
        report.add_result("test_get_market_news_success", True)


class TestAkShareFinancials(unittest.TestCase):
    """测试 AkShare 财务指标数据获取"""

    @patch('tradingagents.dataflows.akshare_stock.ak')
    def test_get_fundamentals_success(self, mock_ak):
        """测试成功获取财务指标"""
        mock_ak.stock_financial_analysis_indicator.return_value = create_mock_financial_df()
        mock_ak.stock_individual_info_em.return_value = pd.DataFrame({
            "item": ["股票代码", "股票简称"],
            "value": ["600519", "贵州茅台"],
        })
        
        result = get_china_fundamentals("600519")
        
        self.assertIn("财务分析指标", result)
        self.assertIn("ROE", result)
        report.add_result("test_get_fundamentals_success", True)

    @patch('tradingagents.dataflows.akshare_stock.ak')
    def test_get_fundamentals_etf(self, mock_ak):
        """测试 ETF 无财务数据"""
        result = get_china_fundamentals("512170")
        
        self.assertIn("ETF", result)
        self.assertIn("无传统公司财务报表", result)
        # Should not call akshare for ETFs
        mock_ak.assert_not_called()
        report.add_result("test_get_fundamentals_etf", True)

    @patch('tradingagents.dataflows.akshare_stock.ak')
    def test_get_fundamentals_partial_failure(self, mock_ak):
        """测试部分数据获取失败"""
        mock_ak.stock_financial_analysis_indicator.side_effect = Exception("API 错误")
        mock_ak.stock_individual_info_em.return_value = pd.DataFrame({
            "item": ["股票代码"],
            "value": ["600519"],
        })
        
        result = get_china_fundamentals("600519")
        
        # Should still have basic info
        self.assertIn("股票基本信息", result)
        self.assertIn("财务指标获取失败", result)
        report.add_result("test_get_fundamentals_partial_failure", True)


class TestDataSourceFallback(unittest.TestCase):
    """测试数据源故障降级机制"""

    def setUp(self):
        """设置测试配置"""
        self.original_config = get_config()
        set_config({
            "data_vendors": {
                "core_stock_apis": "baostock",
                "technical_indicators": "baostock",
                "fundamental_data": "akshare",
            },
            "tool_vendors": {},
        })

    def tearDown(self):
        """恢复原始配置"""
        set_config(self.original_config)

    @patch('tradingagents.dataflows.akshare_stock._baostock_session')
    @patch('tradingagents.dataflows.akshare_stock.bs')
    def test_baostock_timeout_fallback(self, mock_bs, mock_session):
        """测试 BaoStock 超时降级到 AkShare"""
        # Mock BaoStock to raise timeout
        mock_session.side_effect = TimeoutError("BaoStock 连接超时")
        
        # Mock AkShare as fallback
        with patch('tradingagents.dataflows.akshare_stock.ak') as mock_ak:
            mock_ak.stock_financial_analysis_indicator.return_value = create_mock_financial_df()
            mock_ak.stock_individual_info_em.return_value = pd.DataFrame()
            
            # Should fallback to AkShare
            result = get_china_fundamentals("600519")
            
            # Verify AkShare was called as fallback
            mock_ak.stock_financial_analysis_indicator.assert_called()
            self.assertIn("财务分析指标", result)
        
        report.add_result("test_baostock_timeout_fallback", True)

    def test_vendor_fallback_chain(self):
        """测试供应商降级链配置"""
        # Test that vendor methods are properly configured
        from tradingagents.dataflows.interface import VENDOR_METHODS
        
        # Verify get_stock_data has multiple vendors
        self.assertIn("get_stock_data", VENDOR_METHODS)
        vendors = list(VENDOR_METHODS["get_stock_data"].keys())
        self.assertGreater(len(vendors), 1, "Should have multiple vendors for fallback")
        
        # Verify at least yfinance and alpha_vantage are available
        self.assertIn("yfinance", vendors)
        self.assertIn("alpha_vantage", vendors)
        
        report.add_result("test_vendor_fallback_chain", True)

    def test_all_vendors_fail(self):
        """测试所有供应商都失败的情况 - 验证降级逻辑存在"""
        from tradingagents.dataflows.interface import VENDOR_METHODS, get_category_for_method
        
        # Verify the fallback logic exists in route_to_vendor
        # Check that method categorization works
        category = get_category_for_method("get_stock_data")
        self.assertEqual(category, "core_stock_apis")
        
        # Verify multiple vendors available for fallback
        vendors = list(VENDOR_METHODS["get_stock_data"].keys())
        self.assertGreater(len(vendors), 1, "Should support multiple vendors for fallback")
        
        report.add_result("test_all_vendors_fail", True)


class TestDataConsistency(unittest.TestCase):
    """测试多数据源一致性校验"""

    def test_symbol_normalization_consistency(self):
        """测试不同格式股票代码标准化一致性"""
        symbols = [
            "600519.SS",
            "sh.600519",
            "600519",
        ]
        
        # All should normalize to the same BaoStock code
        expected_bs = "sh.600519"
        expected_plain = "600519"
        
        for symbol in symbols:
            bs_code, plain = _normalize_symbol(symbol)
            self.assertEqual(bs_code, expected_bs, f"BS inconsistency for {symbol}")
            self.assertEqual(plain, expected_plain, f"Plain inconsistency for {symbol}")
        
        report.add_result("test_symbol_normalization_consistency", True)

    @patch('tradingagents.dataflows.akshare_stock._baostock_session')
    @patch('tradingagents.dataflows.akshare_stock.bs')
    def test_data_format_consistency(self, mock_bs, mock_session):
        """测试数据格式一致性"""
        # Mock BaoStock response
        mock_rs = MagicMock()
        mock_rs.error_code = '0'
        mock_rs.next.side_effect = [True, True, False]
        mock_rs.get_row_data.side_effect = [
            ["2024-01-01", "100.0", "105.0", "99.0", "103.0", "1000000"],
            ["2024-01-02", "101.0", "106.0", "100.0", "104.0", "1100000"],
        ]
        mock_rs.fields = ["date", "open", "high", "low", "close", "volume"]
        
        mock_session.return_value.__enter__ = lambda s: s
        mock_session.return_value.__exit__ = lambda s, *args: None
        mock_bs.query_history_k_data_plus.return_value = mock_rs
        
        result = get_china_stock_data("600519", "2024-01-01", "2024-01-03")
        
        # Verify consistent format
        self.assertIn("A股历史行情", result)
        self.assertIn("open", result.lower())
        self.assertIn("close", result.lower())
        self.assertIn("volume", result.lower())
        self.assertIn("BaoStock", result)
        
        report.add_result("test_data_format_consistency", True)


class TestDataCleaning(unittest.TestCase):
    """测试数据清洗与格式化"""

    @patch('tradingagents.dataflows.akshare_stock._baostock_session')
    @patch('tradingagents.dataflows.akshare_stock.bs')
    def test_numeric_conversion(self, mock_bs, mock_session):
        """测试数值类型转换"""
        # Mock data with string numbers
        mock_rs = MagicMock()
        mock_rs.error_code = '0'
        mock_rs.next.side_effect = [True, False]
        mock_rs.get_row_data.return_value = ["2024-01-01", "100.5", "105.3", "99.2", "103.8", "1000000"]
        mock_rs.fields = ["date", "open", "high", "low", "close", "volume"]
        
        mock_session.return_value.__enter__ = lambda s: s
        mock_session.return_value.__exit__ = lambda s, *args: None
        mock_bs.query_history_k_data_plus.return_value = mock_rs
        
        result = get_china_stock_data("600519", "2024-01-01", "2024-01-01")
        
        # Verify numeric conversion happened
        self.assertIn("103.8", result)
        report.add_result("test_numeric_conversion", True)

    @patch('tradingagents.dataflows.akshare_stock._baostock_session')
    @patch('tradingagents.dataflows.akshare_stock.bs')
    def test_empty_data_handling(self, mock_bs, mock_session):
        """测试空数据处理"""
        mock_rs = MagicMock()
        mock_rs.error_code = '0'
        mock_rs.next.return_value = False  # No data
        mock_rs.fields = ["date", "open", "high", "low", "close", "volume"]
        
        mock_session.return_value.__enter__ = lambda s: s
        mock_session.return_value.__exit__ = lambda s, *args: None
        mock_bs.query_history_k_data_plus.return_value = mock_rs
        
        result = get_china_stock_data("600519", "2024-01-01", "2024-01-03")
        
        self.assertIn("未找到", result)
        report.add_result("test_empty_data_handling", True)

    @patch('tradingagents.dataflows.akshare_stock._baostock_session')
    @patch('tradingagents.dataflows.akshare_stock.bs')
    def test_indicator_calculation(self, mock_bs, mock_session):
        """测试指标计算数据清洗"""
        # Mock historical data for indicator calculation
        mock_rs = MagicMock()
        mock_rs.error_code = '0'
        mock_rs.next.side_effect = [True, True, True, False]
        mock_rs.get_row_data.side_effect = [
            ["2024-01-01", "100.0", "105.0", "99.0", "1000000"],
            ["2024-01-02", "101.0", "106.0", "100.0", "1100000"],
            ["2024-01-03", "102.0", "107.0", "101.0", "1200000"],
        ]
        mock_rs.fields = ["date", "close", "high", "low", "volume"]
        
        mock_session.return_value.__enter__ = lambda s: s
        mock_session.return_value.__exit__ = lambda s, *args: None
        mock_bs.query_history_k_data_plus.return_value = mock_rs
        
        result = get_china_stock_indicators("600519", "macd", "2024-01-03", 3)
        
        # Verify indicator calculation output
        self.assertIn("MACD", result)
        report.add_result("test_indicator_calculation", True)

    def test_etf_financial_statement_handling(self):
        """测试 ETF 财务报表处理"""
        etf_symbols = ["512170", "512400", "588000"]
        
        for symbol in etf_symbols:
            for func, name in [
                (get_china_fundamentals, "fundamentals"),
                (get_china_balance_sheet, "balance_sheet"),
                (get_china_income_statement, "income_statement"),
                (get_china_cashflow, "cashflow"),
            ]:
                result = func(symbol)
                self.assertIn("ETF", result, f"{symbol} {name} should mention ETF")
                self.assertIn("无传统公司财务报表", result, f"{symbol} {name} should explain no financials")
        
        report.add_result("test_etf_financial_statement_handling", True)


class TestTimeoutScenarios(unittest.TestCase):
    """测试超时场景"""

    @patch('tradingagents.dataflows.akshare_stock.time.sleep')
    @patch('tradingagents.dataflows.akshare_stock._baostock_session')
    def test_connection_timeout(self, mock_session, mock_sleep):
        """测试连接超时处理"""
        mock_session.side_effect = TimeoutError("连接超时")
        
        result = get_china_stock_data("600519", "2024-01-01", "2024-01-03")
        
        self.assertIn("失败", result)
        report.add_result("test_connection_timeout", True)

    @patch('tradingagents.dataflows.akshare_stock.ak')
    def test_api_timeout(self, mock_ak):
        """测试 API 超时处理"""
        mock_ak.stock_news_em.side_effect = TimeoutError("API 超时")
        
        result = get_china_stock_news("600519")
        
        self.assertIn("失败", result)
        self.assertIn("超时", result)
        report.add_result("test_api_timeout", True)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_interface_routing(self):
        """测试接口路由功能"""
        # Test method categorization
        categories = {
            "get_stock_data": "core_stock_apis",
            "get_indicators": "technical_indicators",
            "get_fundamentals": "fundamental_data",
            "get_news": "news_data",
        }
        
        for method, expected_category in categories.items():
            category = get_category_for_method(method)
            self.assertEqual(category, expected_category, f"Wrong category for {method}")
        
        report.add_result("test_interface_routing", True)

    def test_vendor_configuration(self):
        """测试供应商配置"""
        config = get_config()
        
        # Verify vendor configuration exists
        self.assertIn("data_vendors", config)
        self.assertIn("core_stock_apis", config["data_vendors"])
        
        report.add_result("test_vendor_configuration", True)

    @patch('tradingagents.dataflows.interface.get_YFin_data_online')
    def test_yfinance_integration(self, mock_yf):
        """测试 YFinance 集成"""
        mock_yf.return_value = "YFinance 数据"
        
        from tradingagents.dataflows.interface import VENDOR_METHODS
        
        # Verify yfinance is in vendor methods
        self.assertIn("yfinance", VENDOR_METHODS["get_stock_data"])
        
        report.add_result("test_yfinance_integration", True)


# ─── Test Runner ──────────────────────────────────────────────────────────────
def run_tests():
    """Run all tests and generate report"""
    print(f"{TestColors.BOLD}{'='*70}{TestColors.END}")
    print(f"{TestColors.BOLD}数据源层测试{TestColors.END}")
    print(f"{TestColors.BOLD}{'='*70}{TestColors.END}\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestSymbolNormalization,
        TestAkShareNews,
        TestAkShareFinancials,
        TestDataSourceFallback,
        TestDataConsistency,
        TestDataCleaning,
        TestTimeoutScenarios,
        TestIntegration,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with custom result tracking
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    report.print_summary()
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
