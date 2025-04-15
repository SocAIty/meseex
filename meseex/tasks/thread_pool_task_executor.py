from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from .task_result import SyncTask
from .i_task_executor import ITaskExecutor


class ThreadPoolTaskExecutor(ITaskExecutor):
    """Executor for synchronous tasks using a thread pool"""
    
    def __init__(self, max_workers: int = None):
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
    
    def submit(self, method: Callable, *args, callback: Optional[Callable] = None) -> SyncTask:
        """Submit a synchronous task to be executed in a thread"""            
        future = self.thread_pool.submit(method, *args)
        sync_task = SyncTask(future=future)
        
        if callback:
            future.add_done_callback(lambda _: callback(sync_task))
            
        return sync_task
    
    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool"""
        self.thread_pool.shutdown(wait=wait)
