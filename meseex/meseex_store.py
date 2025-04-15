import threading
from collections import deque
from typing import Optional, Set, Dict, List, Any, Tuple

from meseex.mr_meseex import MrMeseex, TerminationState


class MeseexStore:
    """Thread-safe storage for Mr. Meseex instances with efficient lookups"""

    def __init__(self):
        self._lock = threading.Lock()
        # All active Meseex instances
        self._meekz: Dict[str, MrMeseex] = {}
        # Reference lists for different states
        self._queued: deque[str] = deque()
        self._working: Set[str] = set()
        self._completed: Set[str] = set()
        self._failed: Set[str] = set()
        # Task to Meseex ID mapping
        self._task_meekz: Dict[Any, Set[str]] = {}

    def get_meseex(self, meseex_id: str) -> Optional[MrMeseex]:
        """Get a Meseex instance by ID"""
        return self._meekz.get(meseex_id)

    def add_to_queue(self, meseex: MrMeseex) -> None:
        """Add a new Meseex to the queue"""
        with self._lock:
            self._meekz[meseex.meseex_id] = meseex
            self._queued.append(meseex.meseex_id)

    def get_next_queued(self) -> Optional[str]:
        """Get the next queued Meseex ID without removing it"""
        with self._lock:
            return self._queued[0] if self._queued else None

    def move_to_working(self, meseex_id: str, task: Any = None) -> Optional[MrMeseex]:
        """Move a Meseex from queue to working state and assign to a task"""
        with self._lock:
            if meseex_id in self._queued:
                self._queued.remove(meseex_id)
                self._working.add(meseex_id)
                meseex = self._meekz.get(meseex_id)
                
                if task is not None and meseex is not None:
                    # Add to task mapping
                    if task not in self._task_meekz:
                        self._task_meekz[task] = set()
                    self._task_meekz[task].add(meseex_id)
                
                return meseex
        return None

    def pop_next_queued(self) -> Tuple[str, MrMeseex]:
        """Atomically get and remove the next queued Meseex, and move it to working state"""
        with self._lock:
            if not self._queued:
                return None, None
                
            meseex_id = self._queued.popleft()
            self._working.add(meseex_id)
            return meseex_id, self._meekz.get(meseex_id)

    def has_queued(self) -> bool:
        """Check if there are any queued Meseex instances"""
        with self._lock:
            return len(self._queued) > 0

    def update_meseex_task(self, meseex_id: str, old_task: Any, new_task: Any) -> None:
        """Update the task assignment for a Meseex"""
        with self._lock:
            # Remove from old task
            if old_task in self._task_meekz:
                self._task_meekz[old_task].discard(meseex_id)
                
            # Add to new task
            if new_task is not None:
                if new_task not in self._task_meekz:
                    self._task_meekz[new_task] = set()
                self._task_meekz[new_task].add(meseex_id)

    def complete_meseex(self, meseex_id: str) -> None:
        """Mark a Meseex as completed"""
        with self._lock:
            meseex = self._meekz.get(meseex_id)
            if meseex_id in self._working and meseex:
                self._working.remove(meseex_id)
                self._completed.add(meseex_id)
                
                # Remove from any task mappings
                if meseex.current_task_index in self._task_meekz:
                    self._task_meekz[meseex.current_task_index].discard(meseex_id)

    def fail_meseex(self, meseex_id: str) -> None:
        """Mark a Meseex as failed"""
        with self._lock:
            meseex = self._meekz.get(meseex_id)
            if meseex_id in self._working and meseex:
                self._working.remove(meseex_id)
                self._failed.add(meseex_id)
                
                # Remove from any task mappings
                if meseex.current_task_index in self._task_meekz:
                    self._task_meekz[meseex.current_task_index].discard(meseex_id)

    def terminate_meseex(self, meseex_id: str) -> None:
        """Handle termination state of a Meseex"""
        with self._lock:
            meseex = self._meekz.get(meseex_id)
            if not meseex or not meseex.is_terminal:
                return
                
            # Remove from any task mappings first (important to do this before changing state)
            if meseex.current_task_index in self._task_meekz:
                self._task_meekz[meseex.current_task_index].discard(meseex_id)
            
            # Now update the state
            if meseex.termination_state == TerminationState.SUCCESS:
                self._working.discard(meseex_id)
                self._completed.add(meseex_id)
            elif meseex.termination_state in (TerminationState.FAILED, TerminationState.CANCELLED):
                self._working.discard(meseex_id)
                self._failed.add(meseex_id)

    def remove_meseex(self, meseex_id: str) -> None:
        """Remove a Meseex completely from all collections"""
        with self._lock:
            # Remove from state collections
            self._queued = deque(m_id for m_id in self._queued if m_id != meseex_id)
            self._working.discard(meseex_id)
            self._completed.discard(meseex_id)
            self._failed.discard(meseex_id)
            
            # Remove from task mapping
            meseex = self._meekz.get(meseex_id)
            if meseex and meseex.current_task_index in self._task_meekz:
                self._task_meekz[meseex.current_task_index].discard(meseex_id)
                
            # Remove from main collection
            self._meekz.pop(meseex_id, None)

    def get_state_snapshot(self):
        """Get a consistent snapshot of the current state"""
        with self._lock:
            return {
                "all_meekz": self._meekz.copy(),
                "task_map": {task: set(ids) for task, ids in self._task_meekz.items()},
                "completed_ids": self._completed.copy(),
                "failed_ids": self._failed.copy(),
                "working_ids": self._working.copy(),
                "queued_ids": list(self._queued)
            }

    @property
    def queued_meekz(self) -> List[MrMeseex]:
        """Get all queued Meseex instances"""
        with self._lock:
            return [self._meekz[m_id] for m_id in self._queued]

    @property
    def working_meekz(self) -> List[MrMeseex]:
        """Get all working Meseex instances"""
        with self._lock:
            return [self._meekz[m_id] for m_id in self._working]

    @property
    def completed_meekz(self) -> List[MrMeseex]:
        """Get all completed Meseex instances"""
        with self._lock:
            return [self._meekz[m_id] for m_id in self._completed]

    @property
    def failed_meekz(self) -> List[MrMeseex]:
        """Get all failed Meseex instances"""
        with self._lock:
            return [self._meekz[m_id] for m_id in self._failed]
    
    @property
    def task_map(self) -> Dict[Any, Set[str]]:
        """Get mapping of tasks to Meseex IDs"""
        with self._lock:
            # Return a copy to avoid external modification
            return {task: set(ids) for task, ids in self._task_meekz.items()}
    
    @property
    def all_meekz(self) -> Dict[str, MrMeseex]:
        """Get all Meseex instances"""
        with self._lock:
            return self._meekz.copy()
            
    @property
    def queued_ids(self) -> Set[str]:
        """Get IDs of queued Meseex instances"""
        with self._lock:
            return set(self._queued)
            
    @property
    def working_ids(self) -> Set[str]:
        """Get IDs of working Meseex instances"""
        with self._lock:
            return self._working.copy()
            
    @property
    def completed_ids(self) -> Set[str]:
        """Get IDs of completed Meseex instances"""
        with self._lock:
            return self._completed.copy()
            
    @property
    def failed_ids(self) -> Set[str]:
        """Get IDs of failed Meseex instances"""
        with self._lock:
            return self._failed.copy()
            
    @property
    def terminated_ids(self) -> Set[str]:
        """Get IDs of all terminated (completed or failed) Meseex instances"""
        with self._lock:
            return self._completed.union(self._failed)