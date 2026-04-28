"""LLM客户端连接池 - 单例模式复用"""
from typing import Dict, Optional
from .factory import create_llm_client
from .base_client import BaseLLMClient


class LLMClientPool:
    """LLM客户端连接池（单例）"""
    _instance = None
    _pool: Dict[str, BaseLLMClient] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_client(
        self,
        provider: str,
        model: str,
        base_url: Optional[str] = None,
        **kwargs
    ) -> BaseLLMClient:
        """获取或创建LLM客户端"""
        # 使用 provider:model 作为缓存键
        cache_key = f"{provider}:{model}:{base_url}"
        
        if cache_key not in self._pool:
            self._pool[cache_key] = create_llm_client(
                provider=provider,
                model=model,
                base_url=base_url,
                **kwargs
            )
        
        return self._pool[cache_key]
    
    def clear(self):
        """清空连接池"""
        self._pool.clear()


# 全局单例
llm_pool = LLMClientPool()
