from typing import Optional


class TaskSignal:
    def __init__(self, message: Optional[str] = None, *args, **kwargs):
        self.message = message


class Repeat(TaskSignal):
    def __init__(self, delay_s: float, message: Optional[str] = None, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.delay_s = delay_s
