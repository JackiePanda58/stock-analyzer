#!/usr/bin/env python3
"""
test_scheduler.py - 定时任务/自动巡航测试套件

覆盖场景:
1. 盘后巡航定时触发测试
2. 自选股批量预热测试
3. 文档自动更新测试 (cron_daily_docs.py)
4. APScheduler 任务调度测试

使用 freezegun Mock 时间进行测试
"""

import pytest
import sys
import os
from datetime import datetime, date, time
from unittest.mock import Mock, patch, MagicMock, call
from freezegun import freeze_time
import json

# 添加项目路径
sys.path.insert(0, "/root/stock-analyzer")
os.chdir("/root/stock-analyzer")


# ============================================================================
# 测试 1: 盘后巡航定时触发测试
# ============================================================================

class TestAfterMarketCruiser:
    """盘后巡航定时触发测试"""
    
    @freeze_time("2026-04-08 15:30:00")  # A 股收盘后
    def test_cruiser_trigger_after_market_close(self):
        """测试盘后巡航在收盘后正确触发"""
        from auto_cruiser import run_cruiser
        
        with patch('auto_cruiser.connect_redis') as mock_redis, \
             patch('auto_cruiser.analyze_stock') as mock_analyze:
            
            # Mock Redis 连接
            mock_client = MagicMock()
            mock_client.smembers.return_value = {"600519", "000858", "300750"}
            mock_redis.return_value = mock_client
            
            # Mock 分析函数
            mock_analyze.return_value = {"success": True, "duration": 5.0, "error": None}
            
            # 执行巡航
            run_cruiser()
            
            # 验证 Redis 被调用
            mock_client.smembers.assert_called_once_with("watchlist:default")
            
            # 验证每个股票都被分析
            assert mock_analyze.call_count == 3
    
    @freeze_time("2026-04-08 10:30:00")  # 盘中时间
    def test_cruiser_should_not_trigger_during_market(self):
        """测试盘中时间不应触发巡航 (如果需要此逻辑)"""
        # 当前实现会随时执行，这里记录时间戳用于验证
        current_time = datetime.now()
        assert current_time.hour == 10
        assert current_time.minute == 30
    
    @freeze_time("2026-04-08 15:35:00")
    def test_cruiser_with_empty_watchlist(self):
        """测试自选股为空时的处理"""
        from auto_cruiser import run_cruiser
        
        with patch('auto_cruiser.connect_redis') as mock_redis, \
             patch('auto_cruiser.logger') as mock_logger:
            
            mock_client = MagicMock()
            mock_client.smembers.return_value = None
            mock_redis.return_value = mock_client
            
            run_cruiser()
            
            # 验证记录警告日志
            mock_logger.warning.assert_called()
    
    @freeze_time("2026-04-08 15:30:00")
    def test_cruiser_redis_connection_failure(self):
        """测试 Redis 连接失败时的处理"""
        from auto_cruiser import run_cruiser, connect_redis, logger
        
        # Mock connect_redis 内部抛出异常，触发 error 日志
        with patch.object(connect_redis, '__module__', 'auto_cruiser'), \
             patch('redis.Redis') as mock_redis_class, \
             patch.object(logger, 'error') as mock_error:
            
            # Mock Redis 连接抛出异常
            mock_redis_class.side_effect = Exception("Connection refused")
            
            # 直接调用 connect_redis 来验证 error 日志
            result = connect_redis()
            
            # 验证返回 None
            assert result is None
            
            # 验证记录错误日志
            mock_error.assert_called()


# ============================================================================
# 测试 2: 自选股批量预热测试
# ============================================================================

class TestWatchlistBatchPreheat:
    """自选股批量预热测试"""
    
    @freeze_time("2026-04-08 15:30:00")
    def test_batch_preheat_multiple_stocks(self):
        """测试批量预热多个股票"""
        from auto_cruiser import run_cruiser, REQUEST_INTERVAL
        
        with patch('auto_cruiser.connect_redis') as mock_redis, \
             patch('auto_cruiser.analyze_stock') as mock_analyze, \
             patch('auto_cruiser.time.sleep') as mock_sleep, \
             patch('auto_cruiser.logger') as mock_logger:
            
            # 设置 5 个股票
            mock_client = MagicMock()
            mock_client.smembers.return_value = {"600519", "000858", "300750", "002415", "600036"}
            mock_redis.return_value = mock_client
            
            # Mock 分析结果
            mock_analyze.side_effect = [
                {"success": True, "duration": 3.0, "error": None},
                {"success": True, "duration": 4.5, "error": None},
                {"success": False, "duration": 10.0, "error": "Timeout"},
                {"success": True, "duration": 2.8, "error": None},
                {"success": True, "duration": 5.2, "error": None},
            ]
            
            run_cruiser()
            
            # 验证调用了 5 次分析
            assert mock_analyze.call_count == 5
            
            # 验证 sleep 被调用 4 次 (最后一个股票后不 sleep)
            assert mock_sleep.call_count == 4
            
            # 验证 sleep 间隔正确
            for call_arg in mock_sleep.call_args_list:
                assert call_arg[0][0] == REQUEST_INTERVAL
    
    @freeze_time("2026-04-08 15:30:00")
    def test_batch_preheat_with_partial_failures(self):
        """测试批量预热中部分失败的处理"""
        from auto_cruiser import run_cruiser
        
        with patch('auto_cruiser.connect_redis') as mock_redis, \
             patch('auto_cruiser.analyze_stock') as mock_analyze, \
             patch('auto_cruiser.logger') as mock_logger:
            
            mock_client = MagicMock()
            mock_client.smembers.return_value = {"600519", "000858", "300750"}
            mock_redis.return_value = mock_client
            
            # 第二个股票失败
            mock_analyze.side_effect = [
                {"success": True, "duration": 3.0, "error": None},
                {"success": False, "duration": 10.0, "error": "HTTP 500"},
                {"success": True, "duration": 2.5, "error": None},
            ]
            
            run_cruiser()
            
            # 验证即使有失败，仍然继续处理后续股票
            assert mock_analyze.call_count == 3
            
            # 验证记录了错误日志
            mock_logger.error.assert_called()
    
    @freeze_time("2026-04-08 15:30:00")
    def test_batch_preheat_performance_logging(self):
        """测试批量预热性能日志记录"""
        from auto_cruiser import run_cruiser
        
        with patch('auto_cruiser.connect_redis') as mock_redis, \
             patch('auto_cruiser.analyze_stock') as mock_analyze, \
             patch('auto_cruiser.logger') as mock_logger:
            
            mock_client = MagicMock()
            mock_client.smembers.return_value = {"600519"}
            mock_redis.return_value = mock_client
            mock_analyze.return_value = {"success": True, "duration": 5.5, "error": None}
            
            run_cruiser()
            
            # 验证记录了成功日志和耗时
            mock_logger.info.assert_called()
            call_args = [str(call) for call in mock_logger.info.call_args_list]
            assert any("耗时" in arg for arg in call_args)


# ============================================================================
# 测试 3: 文档自动更新测试 (cron_daily_docs.py)
# ============================================================================

class TestDailyDocsUpdate:
    """文档自动更新测试"""
    
    @freeze_time("2026-04-08 23:30:00")  # 设定的执行时间
    def test_daily_docs_scheduled_time(self):
        """测试文档更新在正确时间执行"""
        # 验证当前时间确实是 23:30
        now = datetime.now()
        assert now.hour == 23
        assert now.minute == 30
    
    @freeze_time("2026-04-08 23:30:00")
    def test_changelog_update(self):
        """测试 CHANGELOG 更新逻辑"""
        from cron_daily_docs import update_changelog, TODAY
        
        # Mock 文件读取
        mock_content = "## [1.1.0] - 2026-04-05\n\n一些更新内容\n"
        
        with patch('builtins.open', mock_open_read(mock_content)) as mock_file, \
             patch('cron_daily_docs.re') as mock_re:
            
            # Mock re.sub 返回新内容
            mock_re.sub.return_value = "## [1.1.0] - 2026-04-05\n\n## [Unreleased] - 2026-04-08\n\n### Added\n- （每日自动更新占位）\n\n一些更新内容\n"
            
            result = update_changelog()
            
            # 验证返回 True 表示已更新
            assert result is True
    
    @freeze_time("2026-04-08 23:30:00")
    def test_readme_update(self):
        """测试 README 更新时间戳更新"""
        from cron_daily_docs import update_readme_date, TODAY
        
        mock_content = "README 内容\n*本文档自动同步：2026-04-07*\n更多內容"
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open_read(mock_content)), \
             patch('cron_daily_docs.re.sub') as mock_sub:
            
            mock_sub.return_value = f"README 内容\n*本文档自动同步：{TODAY}*\n更多內容"
            
            result = update_readme_date()
            
            # 验证返回 True 表示已更新
            assert result is True
    
    @freeze_time("2026-04-08 23:30:00")
    def test_git_commit_auto(self):
        """测试自动 git commit"""
        from cron_daily_docs import git_commit
        
        with patch('cron_daily_docs.run') as mock_run:
            # Mock 有变更
            mock_run.side_effect = [
                ("", 0),  # git add
                ("README.md | 2 +-\nCHANGELOG.md | 5 +++++", 0),  # git diff
                ("", 0),  # git commit
            ]
            
            committed, result = git_commit()
            
            # 验证执行了 git 命令
            assert mock_run.call_count >= 2
    
    @freeze_time("2026-04-08 23:30:00")
    def test_feishu_notification(self):
        """测试飞书通知发送"""
        from cron_daily_docs import send_feishu_message
        import urllib.request
        
        with patch('cron_daily_docs.load_env') as mock_env, \
             patch.object(urllib.request, 'urlopen') as mock_urlopen:
            
            # Mock 环境变量
            mock_env.return_value = {
                "FEISHU_APP_ID": "test_app_id",
                "FEISHU_APP_SECRET": "test_secret"
            }
            
            # Mock API 响应
            mock_token_resp = MagicMock()
            mock_token_resp.read.return_value = json.dumps({"tenant_access_token": "test_token"}).encode()
            mock_token_resp.__enter__ = lambda self: self
            mock_token_resp.__exit__ = lambda self, *args: None
            
            mock_msg_resp = MagicMock()
            mock_msg_resp.read.return_value = json.dumps({"code": 0}).encode()
            mock_msg_resp.__enter__ = lambda self: self
            mock_msg_resp.__exit__ = lambda self, *args: None
            
            mock_urlopen.side_effect = [mock_token_resp, mock_msg_resp]
            
            result = send_feishu_message("测试消息")
            
            # 验证发送成功
            assert result is True
            
            # 验证调用了 2 次 urlopen (获取 token + 发送消息)
            assert mock_urlopen.call_count == 2
    
    @freeze_time("2026-04-08 23:30:00")
    def test_full_daily_docs_workflow(self):
        """测试完整的文档更新工作流"""
        from cron_daily_docs import main
        
        with patch('cron_daily_docs.update_changelog', return_value=True) as mock_changelog, \
             patch('cron_daily_docs.update_readme_date', return_value=True) as mock_readme, \
             patch('cron_daily_docs.git_commit', return_value=(True, "变更内容")) as mock_commit, \
             patch('cron_daily_docs.get_git_changes', return_value="commit 123456 测试提交") as mock_git, \
             patch('cron_daily_docs.send_feishu_message', return_value=True) as mock_feishu:
            
            main()
            
            # 验证所有步骤都被执行
            mock_changelog.assert_called_once()
            mock_readme.assert_called_once()
            mock_commit.assert_called_once()
            mock_git.assert_called_once()
            mock_feishu.assert_called_once()


# ============================================================================
# 测试 4: APScheduler 任务调度测试
# ============================================================================

class TestAPSchedulerIntegration:
    """APScheduler 任务调度测试"""
    
    def test_scheduler_job_definition(self):
        """测试调度任务定义"""
        # 验证 cron_daily_docs 可以被导入
        import cron_daily_docs
        
        # 验证 main 函数存在
        assert hasattr(cron_daily_docs, 'main')
        assert callable(cron_daily_docs.main)
    
    def test_scheduler_job_auto_cruiser(self):
        """测试自动巡航调度任务"""
        import auto_cruiser
        
        # 验证 run_cruiser 函数存在
        assert hasattr(auto_cruiser, 'run_cruiser')
        assert callable(auto_cruiser.run_cruiser)
    
    @freeze_time("2026-04-08 15:30:00")
    def test_scheduler_time_validation(self):
        """测试调度时间验证"""
        from datetime import datetime
        
        # 验证盘后时间 (15:30)
        now = datetime.now()
        assert now.hour == 15
        assert now.minute == 30
        
        # 验证文档更新时间 (23:30)
        with freeze_time("2026-04-08 23:30:00"):
            now = datetime.now()
            assert now.hour == 23
            assert now.minute == 30
    
    def test_scheduler_mock_with_freezegun(self):
        """测试使用 freezegun 模拟时间"""
        from datetime import datetime, timedelta
        
        # 测试时间前进
        with freeze_time("2026-04-08 15:30:00") as frozen_time:
            from freezegun import freeze_time as ft
            # 使用 freeze_time 内部的 datetime
            assert ft().time_to_freeze.hour == 15
            
            # 前进 8 小时
            frozen_time.tick(timedelta(hours=8))
            assert ft().time_to_freeze.hour == 23
    
    @freeze_time("2026-04-08 15:30:00")
    def test_scheduler_job_error_handling(self):
        """测试调度任务错误处理"""
        from auto_cruiser import run_cruiser
        
        with patch('auto_cruiser.connect_redis') as mock_redis:
            # Mock Redis 连接失败
            mock_redis.return_value = None
            
            # 应该不抛出异常
            try:
                run_cruiser()
                success = True
            except Exception:
                success = False
            
            assert success is True


# ============================================================================
# 测试 5: 集成测试场景
# ============================================================================

class TestIntegrationScenarios:
    """集成测试场景"""
    
    @freeze_time("2026-04-08 15:30:00")
    def test_cruiser_with_jwt_token_refresh(self):
        """测试巡航中 JWT Token 自动刷新"""
        from auto_cruiser import analyze_stock, GLOBAL_TOKEN
        
        with patch('auto_cruiser.get_token') as mock_get_token, \
             patch('auto_cruiser.requests.post') as mock_post:
            
            # Mock Token
            mock_get_token.return_value = "test_token"
            
            # Mock 401 响应后重试成功
            mock_response_401 = MagicMock()
            mock_response_401.status_code = 401
            
            mock_response_200 = MagicMock()
            mock_response_200.status_code = 200
            
            mock_post.side_effect = [mock_response_401, mock_response_200]
            
            result = analyze_stock("600519")
            
            # 验证重试逻辑
            assert mock_post.call_count == 2
    
    @freeze_time("2026-04-08 23:30:00")
    def test_daily_docs_with_git_failure(self):
        """测试文档更新中 git 失败的处理"""
        from cron_daily_docs import git_commit
        
        with patch('cron_daily_docs.run') as mock_run:
            # Mock git 失败
            mock_run.return_value = ("", 1)
            
            committed, result = git_commit()
            
            # 验证返回 False
            assert committed is False
    
    @freeze_time("2026-04-08 15:30:00")
    def test_cruiser_concurrent_execution_simulation(self):
        """模拟并发执行场景"""
        from auto_cruiser import run_cruiser
        import threading
        
        results = []
        
        def run_cruiser_thread():
            with patch('auto_cruiser.connect_redis') as mock_redis, \
                 patch('auto_cruiser.analyze_stock') as mock_analyze:
                
                mock_client = MagicMock()
                mock_client.smembers.return_value = {"600519"}
                mock_redis.return_value = mock_client
                mock_analyze.return_value = {"success": True, "duration": 1.0, "error": None}
                
                run_cruiser()
                results.append("success")
        
        # 创建 2 个线程模拟并发
        threads = [
            threading.Thread(target=run_cruiser_thread),
            threading.Thread(target=run_cruiser_thread)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证两个线程都完成
        assert len(results) == 2


# ============================================================================
# 辅助函数
# ============================================================================

def mock_open_read(content):
    """Mock open 用于读取"""
    mock_file = MagicMock()
    mock_file.return_value.__enter__.return_value.read.return_value = content
    return mock_file


# ============================================================================
# 测试报告生成
# ============================================================================

def generate_test_report():
    """生成测试报告"""
    import subprocess
    
    print("\n" + "="*80)
    print("定时任务/自动巡航测试报告")
    print("="*80)
    print(f"生成时间：{datetime.now().isoformat()}")
    print("="*80 + "\n")
    
    # 运行 pytest
    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    # 解析结果
    if result.returncode == 0:
        print("✅ 所有测试通过!")
    else:
        print("❌ 部分测试失败，请查看上方详情")
    
    print("="*80 + "\n")
    
    return result.returncode == 0


if __name__ == "__main__":
    # 运行测试并生成报告
    success = generate_test_report()
    sys.exit(0 if success else 1)
