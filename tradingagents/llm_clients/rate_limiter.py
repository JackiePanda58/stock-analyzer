import time
import functools
from typing import Any, Callable
from config.logger import sys_logger

def retry_on_rate_limit(
 max_retries: int = 5,
 base_delay: float = 10.0,
 max_delay: float = 120.0,
 backoff_factor: float = 2.0,
):
 def decorator(func: Callable) -> Callable:
 @functools.wraps(func)
 def wrapper(*args, **kwargs) -> Any:
 delay = base_delay
 for attempt in range(max_retries + 1):
 try:
 return func(*args, **kwargs)
 except Exception as e:
 err_str = str(e).lower()
 is_rate_limit = (
 "429" in err_str
 or "rate limit" in err_str
 or "ratelimit" in err_str
 or "2056" in err_str
 or "usage limit exceeded" in err_str
 )
 if is_rate_limit and attempt < max_retries:
 wait = min(delay, max_delay)
 sys_logger.warning(f"⚠️ MiniMax 速率限制触发！第 {attempt + 1}/{max_retries} 次重试，正在休眠等待 {wait:.0f} 秒...")
 time.sleep(wait)
 delay = min(delay * backoff_factor, max_delay)
 else:
 raise
 return func(*args, **kwargs)
 return wrapper
 return decorator

class RateLimitedChatOpenAI:
 def __init__(self, llm: Any, **retry_kwargs):
 self._llm = llm
 self._retry_kwargs = retry_kwargs

 def invoke(self, *args, **kwargs):
 @retry_on_rate_limit(**self._retry_kwargs)
 def _invoke():
 return self._llm.invoke(*args, **kwargs)
 return _invoke()

 def stream(self, *args, **kwargs):
 @retry_on_rate_limit(**self._retry_kwargs)
 def _stream():
 return self._llm.stream(*args, **kwargs)
 return _stream()

 def __getattr__(self, name: str) -> Any:
 return getattr(self._llm, name)

 def bind_tools(self, *args, **kwargs):
 bound_llm = self._llm.bind_tools(*args, **kwargs)
 return RateLimitedChatOpenAI(bound_llm, **self._retry_kwargs)

 def with_structured_output(self, *args, **kwargs):
 bound_llm = self._llm.with_structured_output(*args, **kwargs)
 return RateLimitedChatOpenAI(bound_llm, **self._retry_kwargs)
