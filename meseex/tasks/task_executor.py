from typing import Callable, Optional, Union, Coroutine
import asyncio
from .task_result import AsyncTask, SyncTask
from .async_task_executor import AsyncTaskExecutor
from .thread_pool_task_executor import ThreadPoolTaskExecutor
from .i_task_executor import ITaskExecutor


class TaskExecutor(ITaskExecutor):
    """Executor that can handle both sync and async tasks"""
    
    def __init__(self, max_workers: int = 10):
        self.async_executor = AsyncTaskExecutor()
        self.thread_pool = ThreadPoolTaskExecutor(max_workers=max_workers)
    
    def submit(self, method: Union[Callable, Coroutine], *args, callback: Optional[Callable] = None, delay_s: Optional[float] = None) -> Union[AsyncTask, SyncTask]:
        """Submit a task, automatically choosing the appropriate executor"""
        if asyncio.iscoroutinefunction(method):
            # For coroutine functions, we need to call them to get the coroutine
            coro = method(*args)
            return self.async_executor.submit(coro, callback=callback, delay_s=delay_s)
        else:
            # For regular functions, we pass the function and args to the thread pool
            return self.thread_pool.submit(method, *args, callback=callback, delay_s=delay_s)
    
    def shutdown(self, wait: bool = True):
        """Shutdown both executors"""
        self.async_executor.shutdown()
        self.thread_pool.shutdown(wait=wait)
