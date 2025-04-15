import asyncio
import concurrent.futures
import threading
import time
from typing import Union, Coroutine

from .task_result import AsyncTask
from .i_task_executor import ITaskExecutor


class AsyncTaskExecutor(ITaskExecutor):
    """
    A class for managing asynchronous jobs with an asyncio event loop running in a separate thread.
    """

    def __init__(self):
        """
        Initializes the AsyncJobManager.
        """
        self.loop: Union[asyncio.BaseEventLoop, None] = None
        self.lock = threading.Lock()
        self.thread = None

    def _start_event_loop(self):
        """
        Starts the asyncio event loop in a separate thread.
        """
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _ensure_event_loop_running(self):
        """
        Ensures that the event loop thread is started if it's not already running.
        """
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._start_event_loop)
                self.thread.start()

            # wait until thread is running
            while self.loop is None or not self.loop.is_running():
                time.sleep(0.05)

    def _add_callback(self, async_job, future, callback=None):
        if callback is not None:
            _callback = lambda f: callback(async_job)
            future.add_done_callback(_callback)
        return future

    def submit(self, method: Coroutine, callback: callable = None, delay: float = None) -> AsyncTask:
        """
        Submits a coroutine to be executed asynchronously.

        Args:
            coro: An async function to be executed asynchronously.
            callback: A callback function to be called when the coroutine is done.
            delay: The delay in seconds before the coroutine is executed.
            method_params: A dictionary of parameters to be passed to the coroutine.

        Returns:
            A Future object representing the server_response of the coroutine.
        """
        self._ensure_event_loop_running()
        future = concurrent.futures.Future()

        async_job = AsyncTask(future=future, coro=method, delay=delay)
        future = self._add_callback(async_job, future, callback)

        self.loop.call_soon_threadsafe(asyncio.create_task, async_job.run())

        return async_job

    def shutdown(self):
        """
        Shuts down the AsyncJobManager, stopping the event loop and cleaning up resources.
        """
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join()
