from abc import ABC, abstractmethod
from typing import Callable, Optional

from .task_result import AsyncTask


class ITaskExecutor(ABC):
    """Interface for task executors that can run both sync and async tasks"""
    
    @abstractmethod
    def submit(self, method: Callable, *args, callback: Optional[Callable] = None) -> AsyncTask:
        """Submit a task to be executed"""
        pass
    
    @abstractmethod
    def shutdown(self, wait: bool = True):
        """Shutdown the executor"""
        pass