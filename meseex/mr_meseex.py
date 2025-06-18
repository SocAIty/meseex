from datetime import datetime, timezone
from typing import Dict, Any, Union, List, Optional, Tuple
from pydantic import BaseModel
from enum import Enum, auto
import time
import traceback
import uuid


class TerminationState(Enum):
    SUCCESS = auto()
    FAILED = auto()      # Final failure state
    CANCELLED = auto()   # Final cancelled state


class TaskProgress(BaseModel):
    percent: float
    message: Optional[str] = None


class TaskMeta(BaseModel):
    entered_at: datetime = datetime.now(timezone.utc)
    left_at: Optional[datetime] = None
    progress: Optional[TaskProgress] = None

    @property
    def duration_ms(self) -> float:
        left_at = self.left_at or datetime.now(timezone.utc)
        return (left_at - self.entered_at).total_seconds() * 1000


class TaskException(Exception):
    """
    Base exception class for all Meseex-related exceptions.

    All exceptions in the Meseex package should inherit from this class.
    This allows for easier catching and handling of Meseex-specific errors.
    """
    def __init__(
        self,
        message: str,
        task: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.task = task
        self.original_error = original_error
        self.__traceback__ = getattr(original_error, '__traceback__', None)
        self.timestamp = datetime.now(timezone.utc)

        # Build a descriptive message
        full_message = message
        if task:
            full_message = f"Task '{task}' failed: {message}"

        super().__init__(full_message)

    def print_traceback(self):
        if self.__traceback__:
            traceback.print_tb(self.__traceback__)
        
    traceback = print_traceback
        

class MrMeseex:
    """
    The purpose of Mr. Meseex is to fulfill all its tasks.
    It maintains task-specific state, handles errors, and tracks progress.

    Example:
        # Create Mr. Meseex with custom tasks.
        meseex = MrMeseex(
            tasks=["prepare", "process", "finish"],
            data={"input": "value"},
            name="MrSuper"
        )
        
        # Set task-specific state
        meseex.set_task_state("intermediate_result")
        
        # Get current task state
        state = meseex.get_task_state()
        
        # Check completion status
        if meseex.is_terminal:
            result = meseex.result
    """
    def __init__(self, tasks: list = None, data: Any = None, name: str = None):
        """
        Initialize a new Mr. Meseex instance.
        
        Args:
            tasks: List of task identifiers. If None, Mr. Meseex will have just one task.
            data: Optional initial data for the tasks
            name: Optional name for Mr. Meseex (defaults to generated UUID)
        """

        if tasks is None:
            tasks = ["single_task"]

        if not isinstance(tasks, list):
            raise ValueError("Tasks must be a list")

        self.meseex_id = "meseex_" + str(uuid.uuid4())
        self._name = name

        self.tasks = tasks
        self.n_tasks = len(tasks) if isinstance(tasks, list) else 1
        self.current_task_index = -1  # -1 means the job is not started yet
        # Stores the metadata of each task by task index
        self.task_metadata: Dict[int, TaskMeta] = {-1: TaskMeta(started_at=datetime.now(timezone.utc))}
        # Stores the signal metadata of each task by task index
        # This is used for state handling for signals like PollAgain, Retry, etc.
        self.task_signal_metadata: Dict[int, Dict[str, Any]] = {}

        # Data the tasks can store
        self.task_data = {}
        self.set_task_data(data)
        # Stores the output of each task
        self.task_outputs = {}  # Stores the output of each task
        # Will be set to true when the job finishes
        self.termination_state: Union[TerminationState, None] = None
        # Stores the errors that occurred in each task
        self._errors: List[TaskException] = []
        
    def next_task(self) -> Enum:
        """Move to the next task in the sequence."""
        # Set the progress of the current task to 100%
        if self.current_task_index >= 0:
            self.task_progress = 1.0, None
        
        # Check if we are done
        if (self.current_task_index + 1) >= self.n_tasks:
            self.termination_state = TerminationState.SUCCESS
            # Record completion time for the final task
            if self.current_task_index >= 0:
                self.task_metadata[self.current_task_index].left_at = datetime.now(timezone.utc)
            return self.current_task_index

        # Update left_at for current task
        if self.current_task_index >= 0:
            self.task_metadata[self.current_task_index].left_at = datetime.now(timezone.utc)

        # Create task metadata for next task
        self.task_metadata[self.current_task_index + 1] = TaskMeta(entered_at=datetime.now(timezone.utc))

        self.current_task_index += 1
        return self.current_task_index

    def set_task_data(self, data: Any):
        """
        Store data for the current task.
        
        Args:
            data: Data to store for the current task
        """

        if self.current_task_index < 0:
            self.task_data[-1] = data
            return

        self.task_data[self.current_task_index] = data

    def get_task_data(self, task: Union[int, Any] = None) -> Any:
        """
        Retrieve data stored for a specific task.
        
        Args:
            task: Optional task identifier. If None, returns data
                  for the current task.
                  
        Returns:
            Any: The stored data for the specified task
        """
        if task is None:
            return self.task_data.get(self.current_task_index)
        
        if isinstance(task, int):
            return self.task_data.get(task)
        
        try:
            task_index = self.tasks.index(task)
            return self.task_data.get(task_index)
        except ValueError:
            raise ValueError(f"Invalid task value: {task}")

    def has_task_data(self, key: Any) -> bool:
        """
        Check if data exists for a specific key in the current task.
        
        Args:
            key: The key to check for existence
            
        Returns:
            bool: True if the key exists in the current task data
        """
        return key in self.task_data

    def clear_task_data(self, key: Any) -> None:
        """
        Remove data stored with a specific key.
        
        Args:
            key: The key to remove from task data
        """
        if key in self.task_data:
            del self.task_data[key]

    def get_task_signal(self, signal_name: str = None) -> Union[Dict[str, Any], Any, None]:
        """
        Retrieve signal metadata.
        If signal_name is None, returns all signal metadata for the current task.
        """
        if signal_name is None or signal_name == "":
            return self.task_signal_metadata.get(self.current_task_index, {})
        
        return self.task_signal_metadata.get(self.current_task_index, {}).get(signal_name)
    
    def set_task_signal(self, signal_name: str, signal_value: Any):
        """
        Set signal metadata for the current task.
        """
        if self.current_task_index not in self.task_signal_metadata:
            self.task_signal_metadata[self.current_task_index] = {}

        self.task_signal_metadata[self.current_task_index][signal_name] = signal_value

    def clear_task_signal(self, signal_name: str):
        """
        Clear signal metadata for the current task.
        """
        if signal_name in self.task_signal_metadata[self.current_task_index]:
            del self.task_signal_metadata[self.current_task_index][signal_name]

    def set_task_output(self, output: Any):
        self.task_outputs[self.current_task_index] = output

    @property
    def prev_task_output(self) -> Any:
        return self.task_outputs.get(self.current_task_index - 1)
    
    def get_task_output(self, task_index_or_name: Union[int, str]) -> Any:
        if isinstance(task_index_or_name, int):
            return self.task_outputs.get(task_index_or_name)
        else:
            try:
                task_index = self.tasks.index(task_index_or_name)
            except ValueError:
                return None

            return self.task_outputs.get(task_index)

    @property
    def input(self) -> Any:
        return self.get_task_data(-1)

    def set_error(self, error: Union[str, Exception], task: Optional[str] = None) -> bool:
        """
        Record an error and update the job's state.
        Subclassing can override this method to handle errors differently.
        
        Args:
            error: The exception that occurred or error message
            task: Optional task name if not already included in the error
                
        Returns:
            bool: True if the job should be terminated
        """
        # Convert string errors to MeseexException
        if isinstance(error, str):
            task_error = TaskException(
                message=error,
                task=task or self.tasks[self.current_task_index] if self.tasks else str(self.current_task_index)
            )
        # Keep MeseexExceptions as is
        elif isinstance(error, TaskException):
            task_error = error
        # Wrap other exceptions in MeseexException
        else:
            task_error = TaskException(
                message=str(error),
                task=task or self.tasks[self.current_task_index] if self.tasks else str(self.current_task_index),
                original_error=error
            )
        
        self._errors.append(task_error)
        self.termination_state = TerminationState.FAILED
        
        # Record completion time for the failed task
        if self.current_task_index >= 0:
            self.task_metadata[self.current_task_index].left_at = datetime.now(timezone.utc)
            
        return True

    def get_errors(self) -> List[TaskException]:
        """Get all errors associated with this job"""
        return self._errors.copy()

    def wait_for_result(self, timeout_s: float = None, default_value: Any = None):
        """
        Wait for the job to complete and return its result.
        
        Args:
            timeout_s: Maximum time to wait in seconds
            default_value: Value to return if the job times out
            
        Returns:
            Any: The job's result or default_value if timed out
        """
        if timeout_s is None:
            timeout_s = float('inf')
        
        if (not isinstance(timeout_s, float) and not isinstance(timeout_s, int)) or timeout_s <= 0:
            raise ValueError("timeout_s must be a float > 0")

        start_time = time.time()
        while not self.is_terminal:
            time.sleep(0.01)
            if time.time() - start_time > timeout_s:
                return default_value

        if self.termination_state == TerminationState.FAILED:
            return default_value
            
        return self.result
    
    def get_result(self, default_value_on_error: Any = 777, timeout_s: float = None):
        """
        Wait for the job to complete and return its result.
        :param default_value_on_error:
            If the job fails, it will return this value.
            If default_value_on_error is 777, it will raise an exception instead of returning a value.
        :param timeout_s: Maximum time to wait in seconds
        :return: The result of the job
        """
        result = self.wait_for_result(timeout_s, default_value=None)
        if self.termination_state == TerminationState.FAILED:
            if default_value_on_error == 777:
                raise self.error
            else:
                return default_value_on_error
        
        return result

    @property
    def task(self):
        return self.tasks[self.current_task_index] if self.current_task_index >= 0 else self.current_task_index

    @task.setter
    def task(self, value: Union[Any]):
        """
        Set the task to a new value.
        If the value is an integer, it is used as the index of the task.
        If the value is anything else, tries to find the index of the value in the tasks list.
        """
        if isinstance(value, int):
            self.current_task_index = value
        else:
            try:
                self.current_task_index = self.tasks.index(value)
            except ValueError:
                raise ValueError(f"Invalid task value: {value}")

    @property
    def task_meta(self):
        return self.task_metadata[self.current_task_index]

    @property
    def name(self) -> str:
        """
        Human-readable name of the job.
        
        Returns:
            str: The job's name or ID if no name was set
        """
        if self._name is None:
            return self.meseex_id
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def result(self) -> Any:
        """
        Get the final result of the job.
        
        Returns:
            Any: The job's result if successful, None otherwise
        """
        return self.task_outputs.get(self.n_tasks - 1)

    @property
    def is_terminal(self) -> bool:
        """
        Check if the job has reached a terminal state.
        
        A job is terminal when it has either completed successfully,
        failed, or been cancelled.
        
        Returns:
            bool: True if the job is in a terminal state
        """
        return self.termination_state is not None
    
    @property
    def error(self) -> Union[TaskException, None]:
        """
        Get the last error that occurred in the job. None if no error occurred.
        """
        return self._errors[-1] if self._errors else None

    @property
    def task_progress(self) -> Union[TaskProgress, None]:
        """
        Get the progress of the current task.
        """
        if self.task_metadata[self.current_task_index].progress is None:
            return None

        return self.task_metadata[self.current_task_index].progress
    
    @task_progress.setter
    def task_progress(self, percent_message: Tuple[float, str]):
        """
        Set the progress of the current task.
        Percent is between 0 and 1. If percent > 1 it will be divided by 100.
        """
        # Handle non-tuple inputs
        if not isinstance(percent_message, tuple):
            if isinstance(percent_message, float):
                percent_message = (percent_message, None)
            elif isinstance(percent_message, str):
                percent_message = (None, percent_message)
            else:
                raise ValueError("percent_message must be a tuple of (float, str)")

        percent, message = percent_message
        
        # Use existing percent if None provided
        if percent is None:
            prev_progress = self.task_metadata[self.current_task_index].progress
            percent = 0 if prev_progress is None else prev_progress.percent
        # Normalize percent value
        elif percent > 1:
            percent = percent / 100.0
        
        percent = max(0, percent)  # Ensure percent is not negative
        
        # Create or update progress
        task_meta = self.task_metadata[self.current_task_index]
        if task_meta.progress is None:
            task_meta.progress = TaskProgress(percent=percent, message=message)
        else:
            task_meta.progress.percent = percent
            task_meta.progress.message = message

    def set_task_progress(self, percent: float, message: str = None):
        """
        Set the progress of the current task.
        """
        self.task_progress = percent, message

    @property
    def progress(self) -> float:
        """
        Get the progress of the job.
        If not specified, every task will contribute equally to the total progress.
        """
        n_tasks = self.n_tasks
        total_progress = 0
        for i in range(self.current_task_index):
            if self.task_metadata[i].progress is None:
                total_progress += 1 / n_tasks
            else:
                total_progress += self.task_metadata[i].progress.percent / n_tasks

        return total_progress

    @property
    def total_duration_ms(self) -> float:
        """Calculate the total duration of all tasks in milliseconds."""
        if not self.task_metadata:
            return 0
            
        # Initial start time is when the Meseex was created
        start_time = self.task_metadata[-1].entered_at
        if start_time is None:
            return 0
        
        # For terminal tasks, use the recorded completion time of the final task
        if self.is_terminal:
            # Get the last task's metadata using the current_task_index (where it finished)
            if self.current_task_index in self.task_metadata and self.task_metadata[self.current_task_index].left_at:
                end_time = self.task_metadata[self.current_task_index].left_at
            else:
                # Fallback in case the metadata is missing
                end_time = datetime.now(timezone.utc)
        else:
            # For active tasks, use current time
            end_time = datetime.now(timezone.utc)

        if end_time is None:
            end_time = datetime.now(timezone.utc)

        return (end_time - start_time).total_seconds() * 1000

    def __await__(self):
        """
        Makes MrMeseex awaitable. When awaited, it will wait until he reaches a terminal state.
        Returns the ultimate task's result if successful, or raises an exception if failed.
        """
        while not self.is_terminal:
            yield
        if self.termination_state == TerminationState.SUCCESS:
            return self.result
        elif self.termination_state == TerminationState.FAILED:
            if self.error:
                raise self.error
            else:
                raise Exception("Job failed")
        elif self.termination_state == TerminationState.CANCELLED:
            raise Exception("Job was cancelled")
        return self.result
