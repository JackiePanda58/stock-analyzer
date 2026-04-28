"""并行数据获取器 - 使用线程池并行获取多种数据"""
import concurrent.futures
from typing import Dict, Any, Callable
from config.logger import sys_logger


class ParallelDataFetcher:
    """并行数据获取器"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
    
    def fetch_all(
        self,
        symbol: str,
        trade_date: str,
        fetchers: Dict[str, Callable]
    ) -> Dict[str, Any]:
        """
        并行获取多种数据
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期
            fetchers: {数据名: 获取函数} 字典
            
        Returns:
            {数据名: 数据} 字典
        """
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_name = {
                executor.submit(fetcher, symbol, trade_date): name
                for name, fetcher in fetchers.items()
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    sys_logger.error(f"并行获取{name}数据失败: {e}")
                    results[name] = f"获取失败: {e}"
        
        return results


# 全局实例
parallel_fetcher = ParallelDataFetcher(max_workers=4)
