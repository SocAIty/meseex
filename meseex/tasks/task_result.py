import asyncio
from concurrent.futures import Future
from datetime import datetime, timezone
from typing import Optional, Any


class TaskResult:
    """Base class for task results"""
    def __init__(self):
        self.created_at = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None
        self._result: Optional[Any] = None
        self._error: Optional[Exception] = None

    @property
    def result(self) -> Optional[Any]:
        """Get the task result if completed successfully"""
        if not self.is_completed:
            return None
        if self._error is not None:
            return None
        return self._result

    @property
    def error(self) -> Optional[Exception]:
        """Get the error if the task failed"""
        return self._error

    @property
    def is_completed(self) -> bool:
        """Check if the task has completed"""
        return self.completed_at is not None

    def get_execution_time(self) -> float:
        """Get the execution time in seconds"""
        if not self.is_completed:
            return (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return (self.completed_at - self.created_at).total_seconds()

    def _set_result(self, result: Any):
        """Set the task result and mark as completed"""
        self._result = result
        self.completed_at = datetime.now(timezone.utc)

    def _set_error(self, error: Exception):
        """Set the task error and mark as completed"""
        self._error = error
        self.completed_at = datetime.now(timezone.utc)


class AsyncTask(TaskResult):
    """Result wrapper for asynchronous tasks"""
    def __init__(
            self,
            future: Future,
            coro,
            coro_timeout: int = 60,
            delay_s: float = None
    ):
        super().__init__()
        self._future = future
        self._coro = coro
        self.coro_timeout = coro_timeout
        self.delay_s = delay_s

    async def run(self):
        """Run the async task"""
        try:
            if self.delay_s is not None:
                await asyncio.sleep(self.delay_s)

            result = await self._coro
            self._set_result(result)
            self._future.set_result(result)
        except Exception as e:
            self._set_error(e)
            self._future.set_exception(e)
            return None

        return result


class SyncTask(TaskResult):
    """Result wrapper for synchronous tasks"""
    def __init__(self, future: Future):
        super().__init__()
        self._future = future
        # Set up callback to track completion
        future.add_done_callback(self._handle_completion)

    def _handle_completion(self, future: Future):
        """Handle task completion"""
        try:
            result = future.result()
            self._set_result(result)
        except Exception as e:
            self._set_error(e)
