"""
进度追踪器测试 - 验证 _analysis_background_task 是否正确更新 Redis 进度
"""
import pytest
import pytest_asyncio
import asyncio
import time
import sys
sys.path.insert(0, '/root/stock-analyzer')

from api_progress_tracker import ProgressTracker, progress_tracker, init_progress_tracker
import redis.asyncio as aioredis


class TestProgressTracker:
    """进度追踪器单元测试"""
    
    @pytest_asyncio.fixture
    async def redis_client(self):
        """Redis 测试夹具"""
        client = aioredis.from_url("redis://localhost:6379/1", decode_responses=True)
        yield client
        # 清理测试数据
        keys = await client.keys("task:test_*:progress")
        if keys:
            await client.delete(*keys)
        await client.close()
    
    @pytest_asyncio.fixture
    async def tracker(self, redis_client):
        """ProgressTracker 实例"""
        return ProgressTracker(redis_client)
    
    @pytest.mark.asyncio
    async def test_start_task(self, tracker, redis_client):
        """测试任务启动"""
        task_id = "test_start_001"
        symbol = "600519"
        
        await tracker.start_task(task_id, symbol)
        
        # 验证 Redis 中是否有进度数据
        data = await redis_client.get(f"task:{task_id}:progress")
        assert data is not None
        
        import json
        progress = json.loads(data)
        assert progress["status"] == "running"
        assert progress["progress"] == 0
        assert progress["elapsed_time"] == 0
        print(f"✅ test_start_task 通过")
    
    @pytest.mark.asyncio
    async def test_update_step(self, tracker, redis_client):
        """测试步骤更新"""
        task_id = "test_step_002"
        symbol = "600519"
        
        await tracker.start_task(task_id, symbol)
        await asyncio.sleep(0.1)
        
        # 更新到步骤 2（基本面分析）
        await tracker.update_step(task_id, 2)
        
        data = await redis_client.get(f"task:{task_id}:progress")
        import json
        progress = json.loads(data)
        
        assert progress["current_step_name"] == "基本面分析"
        assert progress["progress"] > 0
        print(f"✅ test_update_step 通过 - 步骤：{progress['current_step_name']}, 进度：{progress['progress']}%")
    
    @pytest.mark.asyncio
    async def test_complete_task(self, tracker, redis_client):
        """测试任务完成"""
        task_id = "test_complete_003"
        symbol = "600519"
        
        await tracker.start_task(task_id, symbol)
        await asyncio.sleep(0.5)  # 模拟执行时间
        
        await tracker.complete_task(task_id)
        
        data = await redis_client.get(f"task:{task_id}:progress")
        import json
        progress = json.loads(data)
        
        assert progress["status"] == "completed"
        assert progress["progress"] == 100
        assert progress["elapsed_time"] >= 0
        print(f"✅ test_complete_task 通过 - 耗时：{progress['elapsed_time']}秒")
    
    @pytest.mark.asyncio
    async def test_fail_task(self, tracker, redis_client):
        """测试任务失败"""
        task_id = "test_fail_004"
        symbol = "600519"
        error_msg = "测试错误"
        
        await tracker.start_task(task_id, symbol)
        await tracker.fail_task(task_id, error_msg)
        
        data = await redis_client.get(f"task:{task_id}:progress")
        import json
        progress = json.loads(data)
        
        assert progress["status"] == "failed"
        assert error_msg in progress["current_step_description"]
        print(f"✅ test_fail_task 通过 - 错误：{progress['current_step_description']}")
    
    @pytest.mark.asyncio
    async def test_get_progress(self, tracker, redis_client):
        """测试获取进度"""
        task_id = "test_get_005"
        symbol = "600519"
        
        await tracker.start_task(task_id, symbol)
        await tracker.update_step(task_id, 1)
        
        progress = await tracker.get_progress(task_id)
        
        assert progress["status"] == "running"
        assert progress["current_step_name"] == "技术分析"
        print(f"✅ test_get_progress 通过 - {progress}")


# 集成测试：验证 api_server.py 中的 _analysis_background_task
@pytest.mark.skip(reason="需要完整 API 环境")
class TestAnalysisBackgroundTask:
    """后台任务集成测试"""
    
    @pytest.mark.asyncio
    async def test_background_task_updates_progress(self):
        """测试后台任务是否更新进度"""
        # TODO: 调用 /api/analysis/single 并提交分析请求
        # TODO: 轮询 Redis 验证进度数据是否更新
        # TODO: 验证进度从 0% → 20% → 40% → 60% → 80% → 100%
        pass


if __name__ == "__main__":
    # 快速手动测试
    async def manual_test():
        redis_client = aioredis.from_url("redis://localhost:6379/1", decode_responses=True)
        tracker = ProgressTracker(redis_client)
        
        print("🧪 手动测试进度追踪器...")
        
        task_id = f"manual_test_{int(time.time())}"
        print(f"📋 任务 ID: {task_id}")
        
        # 测试启动
        await tracker.start_task(task_id, "600519")
        print("✅ 任务已启动")
        
        # 测试步骤更新
        for i in range(5):
            await tracker.update_step(task_id, i)
            await asyncio.sleep(0.2)
            progress = await tracker.get_progress(task_id)
            print(f"📊 步骤 {i+1}/5: {progress['current_step_name']} - {progress['progress']}%")
        
        # 测试完成
        await tracker.complete_task(task_id)
        progress = await tracker.get_progress(task_id)
        print(f"✅ 任务完成 - 总耗时：{progress['elapsed_time']}秒")
        
        await redis_client.close()
        print("\n✅ 所有手动测试通过!")
    
    asyncio.run(manual_test())
