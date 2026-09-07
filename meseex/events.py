"""Per-job lifecycle events. Observation only; never drives execution."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

Unsubscribe = Callable[[], None]
EventCallback = Callable[["MeseexEvent"], None]


class EventKind(str, Enum):
    """Lifecycle kinds emitted by ``MrMeseex``."""

    STARTED = "started"
    TASK_CHANGED = "task_changed"
    PROGRESS = "progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL = (EventKind.SUCCEEDED, EventKind.FAILED, EventKind.CANCELLED)
_REPLAY_ORDER = (
    EventKind.STARTED,
    EventKind.TASK_CHANGED,
    EventKind.PROGRESS,
    EventKind.SUCCEEDED,
    EventKind.FAILED,
    EventKind.CANCELLED,
)


@dataclass(frozen=True)
class MeseexEvent:
    """One lifecycle snapshot. Callbacks receive this and must not block."""

    kind: EventKind
    meseex_id: str
    task: Optional[str] = None
    task_index: Optional[int] = None
    progress: Optional[float] = None
    task_progress: Optional[float] = None
    message: Optional[str] = None
    result: Any = None
    error: Optional[BaseException] = None


class EventDispatcher:
    """Thread-safe subscribe / emit / replay for one job."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: List[EventCallback] = []
        self._latest: Dict[EventKind, MeseexEvent] = {}

    def emit(self, event: MeseexEvent) -> None:
        """Store the latest event of this kind and notify subscribers.

        Terminal kinds fire at most once. ``started`` fires at most once.
        Callback exceptions are swallowed so observation cannot fail the job.
        """
        with self._lock:
            if event.kind is EventKind.STARTED and EventKind.STARTED in self._latest:
                return
            if event.kind in _TERMINAL and any(kind in self._latest for kind in _TERMINAL):
                return
            self._latest[event.kind] = event
            listeners = list(self._subscribers)
        for callback in listeners:
            _safe_call(callback, event)

    def subscribe(self, callback: EventCallback, replay: bool = True) -> Unsubscribe:
        """Register ``callback(event)``. Replay delivers the current snapshot first."""
        with self._lock:
            self._subscribers.append(callback)
            snapshot = dict(self._latest) if replay else {}

        if replay:
            for kind in _REPLAY_ORDER:
                event = snapshot.get(kind)
                if event is not None:
                    _safe_call(callback, event)

        def unsubscribe() -> None:
            with self._lock:
                try:
                    self._subscribers.remove(callback)
                except ValueError:
                    pass

        return unsubscribe


def _safe_call(callback: EventCallback, event: MeseexEvent) -> None:
    try:
        callback(event)
    except Exception:
        pass
