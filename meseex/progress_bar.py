"""Event-driven job display. Live UI on a TTY, plain logs otherwise."""
from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional

from rich import box
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from meseex.events import EventKind, MeseexEvent
from meseex.mr_meseex import MrMeseex, TerminationState

SPINNER_FRAMES = ("╭◕‿◕╮", "\\◕‿◕/", "╰◕‿◕╯", "ᕦ◕‿◕ᕤ", "╰◕‿◕╯", "\\◕‿◕/")
SPINNER_PERIOD_S = 0.12
_MAX_DETAILED_JOBS = 15


class ProgressBar:
    """Observe ``MrMeseex`` events and render them.

    Interactive terminal: Rich Live. Spinner frames come from wall clock,
    so Live auto-refresh animates without treating jobs as changed.
    Non-interactive: one log line per event. No Live, no ANSI animation.

    Args:
        progress_verbosity: ``0`` silent, ``1`` state and progress only,
            ``2`` same plus spinner on a TTY.
    """

    def __init__(self, progress_verbosity: int = 2):
        if progress_verbosity not in (0, 1, 2):
            progress_verbosity = 2
        self._verbosity = progress_verbosity
        self._console = Console(highlight=False)
        self._interactive = self._console.is_terminal
        self._animate = self._interactive and progress_verbosity >= 2
        self._jobs: Dict[str, MrMeseex] = {}
        self._unsubs: List[Callable[[], None]] = []
        self._lock = threading.Lock()
        self._live: Optional[Live] = None

    def track(self, meseex: MrMeseex) -> None:
        """Subscribe to one job. No-op when verbosity is 0."""
        if self._verbosity == 0:
            return
        with self._lock:
            self._jobs[meseex.meseex_id] = meseex
        self._unsubs.append(meseex.subscribe(self._on_event, replay=True))
        if self._interactive:
            self._ensure_live()

    def stop(self) -> None:
        """Drop subscribers and close Live."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._live is not None:
            self._live.stop()
            self._live = None

    def _on_event(self, event: MeseexEvent) -> None:
        if self._verbosity == 0:
            return
        if not self._interactive:
            self._log(event)
            return
        if self._live is not None and not self._animate:
            self._live.refresh()

    def _ensure_live(self) -> None:
        if self._live is not None:
            return
        self._live = Live(
            _ProgressView(self),
            console=self._console,
            refresh_per_second=10 if self._animate else 4,
            transient=False,
            auto_refresh=self._animate,
        )
        self._live.start()

    def _spinner(self) -> str:
        if not self._animate:
            return "..."
        index = int(time.monotonic() / SPINNER_PERIOD_S) % len(SPINNER_FRAMES)
        return SPINNER_FRAMES[index]

    def _snapshot(self) -> List[MrMeseex]:
        with self._lock:
            return list(self._jobs.values())

    def _render(self):
        jobs = self._snapshot()
        if not jobs:
            return Text("No Meseex jobs currently running or completed.")
        terminated = [job for job in jobs if job.is_terminal]
        active = [job for job in jobs if not job.is_terminal]
        if jobs and not active:
            panel = self._all_done_panel(terminated)
            return panel or Text("No Meseex jobs currently running or completed.")
        done_panel = self._terminated_panel(terminated)
        active_panel = self._active_panel(active)
        if done_panel and active_panel:
            return Columns([done_panel, active_panel], equal=True, expand=True)
        return done_panel or active_panel or Text("No Meseex jobs currently running or completed.")

    def _all_done_panel(self, terminated: List[MrMeseex]):
        if len(terminated) > _MAX_DETAILED_JOBS:
            return self._completed_summary(terminated)
        lines = [self._terminated_line(job) for job in sorted(terminated, key=lambda job: job.name)]
        if not lines:
            return None
        return Panel(
            Text("\n").join(lines),
            title="All Tasks Completed",
            box=box.ROUNDED,
            border_style="bright_green",
            expand=True,
        )

    def _completed_summary(self, terminated: List[MrMeseex]):
        total = len(terminated)
        completed = sum(1 for job in terminated if job.termination_state is TerminationState.SUCCESS)
        failed = sum(1 for job in terminated if job.termination_state is TerminationState.FAILED)
        cancelled = sum(1 for job in terminated if job.termination_state is TerminationState.CANCELLED)
        runtimes = [job.total_duration_ms for job in terminated]
        avg = sum(runtimes) / total if total else 0
        table = Table(box=box.MINIMAL)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Total Jobs", str(total))
        table.add_row("Completed", f"{completed} ({_pct(completed, total)})")
        table.add_row("Failed", f"{failed} ({_pct(failed, total)})")
        table.add_row("Cancelled", f"{cancelled} ({_pct(cancelled, total)})")
        table.add_row("Avg Runtime", _format_duration_ms(avg))
        table.add_row("Max Runtime", _format_duration_ms(max(runtimes) if runtimes else 0))
        table.add_row("Min Runtime", _format_duration_ms(min(runtimes) if runtimes else 0))
        task_counts = Counter()
        for job in terminated:
            task_counts[str(job.tasks[0]) if job.tasks else "unknown"] += 1
        task_table = Table(title="Task Distribution", box=box.MINIMAL)
        task_table.add_column("Task Type", style="cyan")
        task_table.add_column("Count", style="green")
        for task_type, count in task_counts.most_common(5):
            task_table.add_row(task_type, f"{count} ({_pct(count, total)})")
        return Panel(
            Group(Text("Job Summary", style="bold cyan"), table, task_table),
            title=f"Completed Jobs Summary (Total: {total})",
            box=box.ROUNDED,
            border_style="bright_green",
            expand=True,
        )

    def _terminated_panel(self, terminated: List[MrMeseex]):
        if not terminated:
            return None
        if len(terminated) > _MAX_DETAILED_JOBS:
            return self._terminated_summary(terminated)
        lines = [self._terminated_line(job) for job in sorted(terminated, key=lambda job: job.name)]
        return Panel(
            Text("\n").join(lines),
            title="Terminated Jobs",
            box=box.ROUNDED,
            border_style="dim",
            expand=True,
        )

    def _terminated_summary(self, terminated: List[MrMeseex]):
        total = len(terminated)
        completed = [job for job in terminated if job.termination_state is TerminationState.SUCCESS]
        failed = [job for job in terminated if job.termination_state is TerminationState.FAILED]
        cancelled = [job for job in terminated if job.termination_state is TerminationState.CANCELLED]
        table = Table(box=box.MINIMAL)
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Percentage", style="magenta")
        table.add_row("Completed", str(len(completed)), _pct(len(completed), total))
        table.add_row("Failed", str(len(failed)), _pct(len(failed), total))
        table.add_row("Cancelled", str(len(cancelled)), _pct(len(cancelled), total))
        recent = Table(title="Most Recent Jobs", box=box.MINIMAL)
        recent.add_column("Name", style="cyan")
        recent.add_column("Status", style="green")
        recent.add_column("Runtime", style="magenta")
        for job in sorted(completed, key=lambda item: item.total_duration_ms, reverse=True)[:3]:
            recent.add_row(job.name, "✓ Completed", _format_duration_ms(job.total_duration_ms))
        for job in sorted(failed, key=lambda item: item.total_duration_ms, reverse=True)[:2]:
            recent.add_row(job.name, "✗ Failed", _format_duration_ms(job.total_duration_ms))
        for job in sorted(cancelled, key=lambda item: item.total_duration_ms, reverse=True)[:2]:
            recent.add_row(job.name, "⊘ Cancelled", _format_duration_ms(job.total_duration_ms))
        return Panel(
            Group(table, recent),
            title=f"Terminated Jobs Summary (Total: {total})",
            box=box.ROUNDED,
            border_style="dim",
            expand=True,
        )

    def _terminated_line(self, job: MrMeseex) -> Text:
        run_time = _format_duration_ms(job.total_duration_ms)
        if job.termination_state is TerminationState.SUCCESS:
            status = Text("✓ Completed", style="green")
            extra = ""
        elif job.termination_state is TerminationState.CANCELLED:
            status = Text("⊘ Cancelled", style="yellow")
            extra = ""
        else:
            status = Text("✗ Failed", style="red")
            extra = _format_error(job.error)
        return Text.assemble(
            (f"{job.name:<20} ", "cyan"),
            status,
            (f" Runtime: {run_time:<10}", "magenta"),
            (f" {extra}", "yellow"),
        )

    def _active_panel(self, active: List[MrMeseex]):
        if not active:
            return None
        active = sorted(active, key=lambda job: job.name)
        if len(active) > _MAX_DETAILED_JOBS:
            return self._active_summary(active)
        lines = [self._active_line(job) for job in active]
        return Panel(
            Text("\n").join(lines),
            title="Active Jobs",
            box=box.ROUNDED,
            border_style="blue",
            expand=True,
        )

    def _active_summary(self, active: List[MrMeseex]):
        total = len(active)
        groups = defaultdict(list)
        for job in active:
            groups[_task_label(job)].append(job)
        avg = sum(job.progress for job in active) / total if total else 0
        overall = _bar(avg, 20)
        table = Table(box=box.MINIMAL)
        table.add_column("Task", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Avg Progress", style="magenta")
        for task, group in sorted(groups.items()):
            task_avg = sum(job.progress for job in group) / len(group)
            table.add_row(task, str(len(group)), _bar(task_avg, 10))
        processing = f"\n{self._spinner()} Processing {total} active jobs..." if self._animate else f"\nProcessing {total} active jobs..."
        return Panel(
            Group(
                Text.assemble(("Overall Progress: ", "bold cyan"), (overall, "green")),
                Text("\nActive Jobs by Task:", style="bold cyan"),
                table,
                Text(processing, style="yellow"),
            ),
            title=f"Active Jobs Summary (Total: {total})",
            box=box.ROUNDED,
            border_style="blue",
            expand=True,
        )

    def _active_line(self, job: MrMeseex) -> Text:
        task_display = f"{_task_label(job)} ({job.current_task_index + 1}/{job.n_tasks})"
        message = job.task_progress.message if job.task_progress and job.task_progress.message else ""
        return Text.assemble(
            (f"{job.name:<20} ", "cyan"),
            (f"Task: {task_display:<20} ", "green"),
            (f"Progress: {self._task_progress_display(job):<25} ", "default"),
            (f"Running: {_format_duration_ms(job.total_duration_ms):<10} ", "magenta"),
            (f"Total: {job.progress * 100:.1f}%{'':<3} ", "blue"),
            (message, "yellow"),
        )

    def _task_progress_display(self, job: MrMeseex) -> str:
        current = job.task_progress
        if current is not None and current.percent is not None and current.percent > 0.0:
            return _bar(current.percent, 15)
        if self._animate:
            return f"{self._spinner()} working..."
        return "... working"

    def _log(self, event: MeseexEvent) -> None:
        job = self._jobs.get(event.meseex_id)
        name = job.name if job is not None else event.meseex_id
        kind = event.kind.value
        if event.kind is EventKind.STARTED:
            self._console.print(f"meseex {kind:<11} {name}  task={event.task}")
        elif event.kind is EventKind.TASK_CHANGED:
            self._console.print(f"meseex {kind:<11} {name}  task={event.task}")
        elif event.kind is EventKind.PROGRESS:
            percent = f"{event.task_progress * 100:.0f}%" if event.task_progress is not None else ""
            message = event.message or ""
            self._console.print(f"meseex {kind:<11} {name}  {percent}  {message}".rstrip())
        elif event.kind is EventKind.SUCCEEDED:
            runtime = _format_duration_ms(job.total_duration_ms) if job is not None else ""
            self._console.print(f"meseex {kind:<11} {name}  {runtime}")
        elif event.kind is EventKind.FAILED:
            self._console.print(f"meseex {kind:<11} {name}  {_format_error(event.error)}")
        elif event.kind is EventKind.CANCELLED:
            runtime = _format_duration_ms(job.total_duration_ms) if job is not None else ""
            self._console.print(f"meseex {kind:<11} {name}  {runtime}")


class _ProgressView:
    """Rich renderable that reads live job objects and a clock-driven spinner."""

    def __init__(self, bar: ProgressBar):
        self._bar = bar

    def __rich__(self):
        return self._bar._render()


def _task_label(job: MrMeseex) -> str:
    return job.task if isinstance(job.task, str) else f"Task {job.task}"


def _bar(percent: float, width: int) -> str:
    filled = int(width * max(0.0, min(1.0, percent)))
    return f"[{'=' * filled}{' ' * (width - filled)}] {percent * 100:.1f}%"


def _pct(part: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def _format_error(error: Optional[BaseException]) -> str:
    if not error:
        return ""
    text = str(error)
    task = getattr(error, "task", None)
    if task and f"Task '{task}'" not in text and str(task) not in text:
        text = f"Task '{task}': {text}"
    if len(text) > 200:
        return text[:197] + "..."
    return text


def _format_duration_ms(duration_ms: float) -> str:
    if duration_ms is None:
        return "n/a"
    duration = duration_ms / 1000.0
    if duration < 60:
        return f"{duration:.1f}s"
    if duration < 3600:
        minutes, seconds = divmod(int(duration), 60)
        return f"{minutes}m {seconds}s"
    hours, rem = divmod(int(duration), 3600)
    minutes, _ = divmod(rem, 60)
    return f"{hours}h {minutes}m"
