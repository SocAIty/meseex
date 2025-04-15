import time
from typing import Dict, Callable, Union, List
import threading
from datetime import datetime, timezone

from meseex import MrMeseex
from meseex.tasks import AsyncTask, TaskExecutor
from meseex.progress_bar import ProgressBar
from meseex.mr_meseex import TerminationState
from meseex.meseex_store import MeseexStore
import signal


class TaskError(Exception):
    """Exception raised for job errors"""
    def __init__(self, message: str = None, task: str = None, original_error: Exception = None):
        if not message and not original_error:
            raise ValueError("message or original_error must be provided")

        if not message:
            message = str(original_error)
        
        self.message = message
        self.task = task
        self.original_error = original_error
        self.timestamp = datetime.now(timezone.utc)
        
        # Preserve the original traceback if available
        if original_error and hasattr(original_error, '__traceback__'):
            self.__cause__ = original_error
            self.__traceback__ = original_error.__traceback__
        
        super().__init__(self.message)


class MeseexBox:
    """
    Summon and manage the lifecycle of Mr. Meseex instances while they perform their tasks.
    
    MeseexBox orchestrates the work of Mr. Meseex instances.
    It supports both synchronous and asynchronous task methods.
    It handles state transitions, progress tracking, and error management.
    
    Example:
        # Define task methods
        async def prepare(meseex: MrMeseex) -> MrMeseex:
            # Initial setup
            return meseex
            
        def process(meseex: MrMeseex) -> MrMeseex:
            # Heavy computation
            return meseex
            
        async def finish(meseex: MrMeseex) -> MrMeseex:
            # Cleanup and finalization
            return meseex
            
        # Create MeseexBox with task methods
        meseex_box = MeseexBox({
            "prepare": prepare,
            "process": process,
            "finish": finish
        })
        
        # Summon Mr. Meseex
        meseex = meseex_box.summon({"data": "value"}, "my_task")
        
        # Wait for completion
        result = await meseex
    """
    def __init__(self, task_methods: Union[Dict[Union[int, str], Callable], List[Callable]], raise_on_meseex_error: bool = False):
        """
        Initialize the MeseexBox with task methods.
        
        Args:
            task_methods: Dictionary mapping task identifiers to their handler methods.
                         Task identifiers can be integers (for ordered tasks) or strings
                         (for named tasks). Each handler method should accept a Mr. Meseex
                         parameter and return the modified Mr. Meseex.
            raise_on_meseex_error: If True, raise an exception if Mr. Meseex has a problem. Only set to true for debugging.
        Example:
            task_methods = {
                "prepare": prepare_task,    # First task
                "process": process_task,    # Second task
                "finish": finalize_task    # Third task
            }
        """
        # Initialize the meseex store for thread-safe instance management
        self.meseex_store = MeseexStore()
        
        if isinstance(task_methods, List):
            self.task_methods = {i: task for i, task in enumerate(task_methods)}
        else:
            self.task_methods = task_methods

        self.async_tasks: Dict[str, AsyncTask] = {}
        self.task_executor = TaskExecutor(max_workers=10)

        self.progress_bar = ProgressBar()
        self._worker_thread = None
        self._shutdown = threading.Event()
        self._is_running = False
        self.raise_on_meseex_error = raise_on_meseex_error

        # Add signal handlers. Needed for shutdown if raise_on_meseex_error
        def signal_handler(signum, frame):
            self.shutdown(graceful=False)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def _handle_task_error(self, meseex: MrMeseex, async_task: AsyncTask):
        if not async_task.error:
            return
        
        terminate_meseex = meseex.set_error(async_task.error)
        if terminate_meseex is None or terminate_meseex:
            # Update meseex state to failed
            self.meseex_store.fail_meseex(meseex.meseex_id)
            
            # Ensure the UI is updated with the failed state
            snapshot = self.meseex_store.get_state_snapshot()
            self.progress_bar.update_progress(
                snapshot["all_meekz"],
                snapshot["task_map"],
                snapshot["completed_ids"],
                snapshot["failed_ids"]
            )

        if self.raise_on_meseex_error:
            import traceback
            print(f"\nError occurred in {meseex.name} task: {meseex.task}")
            print("Full traceback:")
            traceback.print_exception(type(async_task.error), async_task.error, async_task.error.__traceback__)
            self.shutdown(graceful=False)
            return  # Don't continue to next task
        
    def _result_transition(self, meseex: MrMeseex, async_task: AsyncTask):
        """Handle task results and transition to next task"""
        # First check for errors
        if async_task.error:
            self._handle_task_error(meseex, async_task)
            # Check if error handling set terminal state, and update UI
            if meseex.is_terminal:
                snapshot = self.meseex_store.get_state_snapshot()
                self.progress_bar.update_progress(
                    snapshot["all_meekz"],
                    snapshot["task_map"],
                    snapshot["completed_ids"],
                    snapshot["failed_ids"]
                )
            return

        # Set result on successful task completion
        if async_task.result is not None:
            meseex.set_task_output(async_task.result)
        
        # Special case: Check if this is the last task
        is_final_task = meseex.current_task_index == meseex.n_tasks - 1
        
        # Continue to the next task (which may trigger termination)
        self._continue_to_next_task(meseex)
        
        # If it was the final task, ensure UI update shows it as completed
        if is_final_task and meseex.is_terminal:
            # Double check termination was handled properly
            self.meseex_store.terminate_meseex(meseex.meseex_id)
            
            # Force additional UI refresh after final task
            snapshot = self.meseex_store.get_state_snapshot()
            self.progress_bar.update_progress(
                snapshot["all_meekz"],
                snapshot["task_map"],
                snapshot["completed_ids"],
                snapshot["failed_ids"]
            )

    def _continue_to_next_task(self, meseex: MrMeseex):
        """Helper method to continue Mr. Meseex to next task"""
        # Store previous task for updating the task mapping
        prev_task = meseex.current_task_index
        
        # Move to next task
        new_task = meseex.next_task()
        
        # Handle terminal state immediately and return early
        if meseex.is_terminal:
            # First update task mapping to remove from previous task
            if prev_task in self.meseex_store.task_map:
                self.meseex_store.update_meseex_task(meseex.meseex_id, prev_task, None)
            
            # Then mark as terminated
            self.meseex_store.terminate_meseex(meseex.meseex_id)
            
            # Force an immediate UI update
            snapshot = self.meseex_store.get_state_snapshot()
            self.progress_bar.update_progress(
                snapshot["all_meekz"],
                snapshot["task_map"],
                snapshot["completed_ids"],
                snapshot["failed_ids"]
            )
            return
        
        # Update task mapping for non-terminal state
        if prev_task != new_task:
            self.meseex_store.update_meseex_task(meseex.meseex_id, prev_task, new_task)
         
        # Get the task method using the task name or index
        task_method = None
        if isinstance(new_task, int) and new_task < len(meseex.tasks):
            task_name = meseex.tasks[new_task]
            task_method = self.task_methods.get(task_name)
        else:
            task_method = self.task_methods.get(new_task)

        if not task_method:
            error_msg = f"No task method found for {meseex.name} task: {new_task}"
            print(f"Warning: {error_msg}")
            meseex.set_error(TaskError(message=error_msg, task=str(new_task)))
            # Handle termination after error
            if meseex.is_terminal:
                self.meseex_store.terminate_meseex(meseex.meseex_id)
                # Force UI update to show the failed task
                snapshot = self.meseex_store.get_state_snapshot()
                self.progress_bar.update_progress(
                    snapshot["all_meekz"],
                    snapshot["task_map"],
                    snapshot["completed_ids"],
                    snapshot["failed_ids"]
                )
            return

        self._run_async(task_method, meseex)

    def _run_async(self, method, meseex: MrMeseex):
        """Run a task using the hybrid executor"""
        async_task = self.task_executor.submit(
            method,
            meseex,
            callback=lambda async_task: self._result_transition(meseex, async_task)
        )
        self.async_tasks[meseex.meseex_id] = async_task
        return async_task

    def summon(self, params=None, meseex_name: str = None) -> MrMeseex:
        """
        Create and start a new Mr. Meseex instance.
        
        Creates a new Mr. Meseex with the given parameters and starts its execution
        through the defined tasks.
        
        Args:
            params: Optional input parameters to pass to the Mr. Meseex
            meseex_name: Optional name for the Mr. Meseex (defaults to generated identifier)
            
        Returns:
            MrMeseex: The created Mr. Meseex instance
        """
        meseex = MrMeseex(tasks=list(self.task_methods.keys()), data=params, name=meseex_name)
        self.meseex_store.add_to_queue(meseex)
        self.start()
        return meseex

    def summon_meseex(self, meseex: MrMeseex) -> MrMeseex:
        """
        Add an existing Mr. Meseex instance to the box.
        
        This is useful when you need to customize the Mr. Meseex's tasks or
        initial state before submission.
        
        Args:
            meseex: Pre-configured Mr. Meseex instance to add
            
        Returns:
            MrMeseex: The added Mr. Meseex instance
        """
        self.meseex_store.add_to_queue(meseex)
        self.start()
        return meseex

    def _start_queued_meekz(self):
        """Start processing queued Meseex instances"""
        # Using atomic pop operation to prevent deadlocks
        while self.meseex_store.has_queued():
            meseex_id, meseex = self.meseex_store.pop_next_queued()
            if meseex:
                self._continue_to_next_task(meseex)

    def _process_meekz_in_background(self) -> None:
        """Background thread that processes Meseex instances"""
        last_active_count = 0
        last_all_completed = False
        
        while not self._shutdown.is_set() and self._is_running:
            try:
                self._start_queued_meekz()
                
                # Get a snapshot for consistent state
                snapshot = self.meseex_store.get_state_snapshot()
                
                # Detect all jobs completed
                active_count = len(snapshot["working_ids"]) + len(snapshot["queued_ids"])
                task_count = len(snapshot["completed_ids"]) + len(snapshot["failed_ids"])
                all_completed = (active_count == 0) and (task_count > 0)
                
                # Only update the UI if there's been a state change or if tasks are still active
                if (last_active_count != active_count) or (last_all_completed != all_completed) or not all_completed:
                    # Update the progress bar
                    self.progress_bar.update_progress(
                        snapshot["all_meekz"],
                        snapshot["task_map"],
                        snapshot["completed_ids"],
                        snapshot["failed_ids"]
                    )
                
                # Store state for next iteration
                last_active_count = active_count
                last_all_completed = all_completed
                
                # More responsive shutdown check
                if self._shutdown.wait(timeout=0.01):
                    break
                    
                # If all completed, slow down the update loop
                if all_completed:
                    time.sleep(0.05)
            except Exception as e:
                if not self._shutdown.is_set():
                    import traceback
                    print(f"Error in background thread: {e}")
                    traceback.print_exc()
                    raise

    def start(self):
        """
        Start the MeseexBox's background processing.
        
        This method initializes the background thread that processes
        queued Mr. Meseex instances and manages their lifecycle. It's called automatically
        when summoning Mr. Meseex instances, but can be called manually if needed.
        """
        if not self._worker_thread:
            self._worker_thread = threading.Thread(target=self._process_meekz_in_background, daemon=True)

        if not self._worker_thread.is_alive():
            self._worker_thread.start()
            self._is_running = True

    def shutdown(self, graceful: bool = True):
        """
        Shut down the MeseexBox.
        
        Args:
            graceful: If True, waits for current tasks to complete.
                    If False, forces immediate termination.
        """
        # First, stop accepting new tasks
        self._is_running = False
        self._shutdown.set()

        if not graceful:
            # Cancel all running tasks
            for meseex_id in self.meseex_store.working_ids:
                meseex = self.meseex_store.get_meseex(meseex_id)
                if meseex:
                    meseex.termination_state = TerminationState.CANCELLED
            
            # Force kill the process
            import signal
            import os
            # Send SIGTERM to our own process
            os.kill(os.getpid(), signal.SIGTERM)
            # If still running after 1 second, use SIGKILL
            time.sleep(1)
            os.kill(os.getpid(), signal.SIGKILL)
        else:
            # Graceful shutdown
            self.task_executor.shutdown(wait=True)
            
            # Force one final UI update to ensure all completed tasks are shown
            snapshot = self.meseex_store.get_state_snapshot()
            self.progress_bar.update_progress(
                snapshot["all_meekz"],
                snapshot["task_map"],
                snapshot["completed_ids"],
                snapshot["failed_ids"]
            )
            
            # Now stop the progress bar display
            self.progress_bar.stop()
            
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=5.0)
                self._worker_thread = None

    async def shutdown_async(self):
        """Shutdown the MeseexBox asynchronously"""
        self.task_executor.shutdown(wait=True)
        self.progress_bar.stop()

        self._shutdown.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
            self._worker_thread = None
        self._is_running = False

    async def __aenter__(self):
        """Async context manager entry"""
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        self.shutdown()
