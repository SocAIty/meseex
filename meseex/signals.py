from typing import Optional


class TaskSignal:
    def __init__(self, message: Optional[str] = None):
        self.message = message


class Repeat(TaskSignal):
    def __init__(self, delay_s: float = 0, message: Optional[str] = None):
        super().__init__(message)
        self.delay_s = delay_s
