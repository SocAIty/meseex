from datetime import datetime, timezone
from typing import Dict, Set, Optional, List
from collections import defaultdict, Counter

from rich.console import Console, Group
from rich.text import Text
from rich.panel import Panel
from rich.live import Live
from rich import box
from rich.table import Table
from rich.columns import Columns

from meseex.mr_meseex import MrMeseex


class ProgressBar:
    """
    Manages progress display using the 'rich' library for concurrent
    Mr. Meseex instances in the console using Panels and Text.
    """
    def __init__(self):
        self._console = Console(highlight=False, color_system="auto", force_terminal=True)
        self._live: Optional[Live] = None
        self._completed_shown: Set[str] = set()
        self._failed_shown: Set[str] = set()
        self._spinner_frame = 0
        self._last_update = datetime.now(timezone.utc)
        self._update_interval = 0.1  # Interval for spinner animation update
        self._compact_mode = False   # Placeholder, not fully implemented in this version
        self._last_display_state = None  # Track last display state to avoid duplicates
        self._max_detailed_jobs = 15  # Maximum number of jobs to show in detailed view
        
        # Mr. Meeseeks spinner frames - use an even number for balanced animation
        self.SPINNER_FRAMES = [
            "╭◕‿◕╮", "\\◕‿◕/", "╰◕‿◕╯", "ᕦ◕‿◕ᕤ", "╰◕‿◕╯", "\\◕‿◕/"
        ]

    def _ensure_display_started(self):
        """Starts the rich Live display if not already running."""
        if self._live is None:
            self._live = Live(
                Text("Starting Mr. Meseex jobs..."),
                console=self._console,
                refresh_per_second=10,
                transient=False, # Keep display after exit
                auto_refresh=True
            )
            self._live.start()

    def _update_spinner(self):
        """Update the spinner frame index"""
        self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)

    def update_progress(
            self,
            meekz: Dict[str, MrMeseex],
            task_meekz: Dict[any, Set[str]],
            completed_meekz: Set[str],
            failed_meekz: Set[str]
    ):
        """
        Update the progress display using Rich Panels and Text.

        Args:
            meekz: Dictionary of meseex_id to Mr. Meseex objects
            task_meekz: The Mr. Meseex instances in each task by id
            completed_meekz: Set of completed Mr. Meseex instances
            failed_meekz: Set of failed Mr. Meseex instances
        """
        now = datetime.now(timezone.utc)
        # Update spinner frame index consistently regardless of throttling
        self._update_spinner()

        # Gather information about task state for quick initial check
        terminated_ids = completed_meekz.union(failed_meekz)
        all_ids = set(meekz.keys())
        all_finished = len(terminated_ids) == len(all_ids) and len(all_ids) > 0
        
        # Create a state digest to detect actual display changes
        current_state = {
            'all_finished': all_finished,
            'completed_count': len(completed_meekz),
            'failed_count': len(failed_meekz),
            'active_count': len(all_ids) - len(terminated_ids)
        }
        
        # Check if any real change happened (ignore spinner-only updates)
        is_real_change = self._last_display_state != current_state
        
        # Throttle the actual Rich update calls for performance
        is_update_due = (now - self._last_update).total_seconds() >= self._update_interval
        
        # Only update if either real state change or update is due
        if not (is_update_due or is_real_change):
            return
            
        # Save current state for future comparisons
        self._last_display_state = current_state
        self._last_update = now  # Reset timer for updates
        self._ensure_display_started()

        # Prepare renderables for display
        renderables = self._prepare_renderables(meekz, terminated_ids, completed_meekz, failed_meekz, all_finished)
        
        # Update the live display
        self._update_live_display(renderables)

    def _update_live_display(self, renderables: list):
        """Update the live display with the given renderables."""
        if self._live is not None:
            # Use a Group to manage the panels vertically
            display_group = Group(*renderables)
            # Clear the live display before updating to avoid stale content
            self._live.update(display_group)

    def _prepare_renderables(self, meekz, terminated_ids, completed_meekz, failed_meekz, all_finished):
        """Prepare renderables for display based on current state."""
        renderables = []
        
        if all_finished:
            all_completed_panel = self._prepare_all_completed_panel(meekz, terminated_ids, completed_meekz, failed_meekz)
            if all_completed_panel:
                renderables.append(all_completed_panel)
        else:
            terminated_panel = self._prepare_terminated_panel(meekz, terminated_ids, completed_meekz, failed_meekz)
            active_panel = self._prepare_active_panel(meekz, terminated_ids)
            
            # If both panels exist, show them side by side
            if terminated_panel and active_panel:
                # Use Rich Columns to display side by side, with equal width
                side_by_side = Columns([terminated_panel, active_panel], equal=True, expand=True)
                renderables.append(side_by_side)
            elif terminated_panel:
                renderables.append(terminated_panel)
            elif active_panel:
                renderables.append(active_panel)
        
        # If no renderables at all, show a message
        if not renderables:
            renderables.append(Text("No Meseex jobs currently running or completed."))
        
        return renderables

    def _prepare_all_completed_panel(self, meekz, terminated_ids, completed_meekz, failed_meekz):
        """Prepare panel for when all tasks are completed."""
        all_terminated_lines = []
        
        # If there are too many jobs, show a summary instead
        if len(terminated_ids) > self._max_detailed_jobs:
            return self._prepare_summary_completed_panel(meekz, terminated_ids, completed_meekz, failed_meekz)
        
        # Sort by name for consistent display
        for meseex_id in sorted(list(terminated_ids), key=lambda m_id: meekz.get(m_id).name if meekz.get(m_id) else m_id):
            meseex = meekz.get(meseex_id)
            if meseex:
                line = self._create_terminated_job_line(meseex, meseex_id, completed_meekz)
                all_terminated_lines.append(line)
        
        # Add the single "All Tasks Completed" panel
        if all_terminated_lines:
            terminated_content = Text("\n").join(all_terminated_lines)
            return Panel(
                terminated_content,
                title="All Tasks Completed",
                box=box.ROUNDED,
                border_style="bright_green",
                expand=True,
                width=None
            )
        return None

    def _prepare_summary_completed_panel(self, meekz, terminated_ids, completed_meekz, failed_meekz):
        """Prepare a summary panel for completed jobs when there are many jobs."""
        # Calculate statistics for completed jobs
        total_jobs = len(terminated_ids)
        completed_jobs = len(completed_meekz)
        failed_jobs = len(failed_meekz)
        
        # Calculate average runtime
        total_runtime = 0
        max_runtime = 0
        min_runtime = float('inf')
        
        # Group by task type
        task_counts = Counter()
        
        for meseex_id in terminated_ids:
            meseex = meekz.get(meseex_id)
            if meseex:
                runtime = meseex.total_duration_ms
                total_runtime += runtime
                max_runtime = max(max_runtime, runtime)
                min_runtime = min(min_runtime, runtime)
                
                # Count by task type
                task_type = str(meseex.tasks[0]) if meseex.tasks else "unknown"
                task_counts[task_type] += 1
        
        avg_runtime = total_runtime / total_jobs if total_jobs > 0 else 0
        
        # Create summary table
        table = Table(box=box.MINIMAL)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Total Jobs", str(total_jobs))
        table.add_row("Completed", f"{completed_jobs} ({completed_jobs/total_jobs*100:.1f}%)")
        table.add_row("Failed", f"{failed_jobs} ({failed_jobs/total_jobs*100:.1f}%)")
        table.add_row("Avg Runtime", self._format_duration_ms(avg_runtime))
        table.add_row("Max Runtime", self._format_duration_ms(max_runtime))
        table.add_row("Min Runtime", self._format_duration_ms(min_runtime))
        
        # Add task type distribution
        task_table = Table(title="Task Distribution", box=box.MINIMAL)
        task_table.add_column("Task Type", style="cyan")
        task_table.add_column("Count", style="green")
        
        # Show top 5 task types
        for task_type, count in task_counts.most_common(5):
            task_table.add_row(task_type, f"{count} ({count/total_jobs*100:.1f}%)")
        
        summary_group = Group(
            Text("Job Summary", style="bold cyan"),
            table,
            task_table
        )
        
        return Panel(
            summary_group,
            title=f"Completed Jobs Summary (Total: {total_jobs})",
            box=box.ROUNDED,
            border_style="bright_green",
            expand=True,  # Expand to fill available width
            width=None  # Allow width to be determined by parent container
        )

    def _prepare_terminated_panel(self, meekz, terminated_ids, completed_meekz, failed_meekz):
        """Prepare panel for terminated jobs."""
        terminated_lines = []
        
        # If there are too many jobs, show a summary instead
        if len(terminated_ids) > self._max_detailed_jobs:
            return self._prepare_summary_terminated_panel(meekz, terminated_ids, completed_meekz, failed_meekz)
        
        # Sort by name for consistent display
        for meseex_id in sorted(list(terminated_ids), key=lambda m_id: meekz.get(m_id).name if meekz.get(m_id) else m_id):
            meseex = meekz.get(meseex_id)
            if meseex:
                line = self._create_terminated_job_line(meseex, meseex_id, completed_meekz)
                terminated_lines.append(line)

        if terminated_lines:
            terminated_content = Text("\n").join(terminated_lines)
            return Panel(
                terminated_content,
                title="Terminated Jobs",
                box=box.ROUNDED,
                border_style="dim",
                expand=True,
                width=None
            )
        return None

    def _prepare_summary_terminated_panel(self, meekz, terminated_ids, completed_meekz, failed_meekz):
        """Prepare a summary panel for terminated jobs when there are many jobs."""
        # Similar to _prepare_summary_completed_panel but for terminated jobs
        total_terminated = len(terminated_ids)
        completed = len(completed_meekz)
        failed = len(failed_meekz)
        
        table = Table(box=box.MINIMAL)
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Percentage", style="magenta")
        
        table.add_row("Completed", str(completed), f"{completed/total_terminated*100:.1f}%")
        table.add_row("Failed", str(failed), f"{failed/total_terminated*100:.1f}%")
        
        # Show most recent 5 completed and failed jobs
        recent_completed = []
        recent_failed = []
        
        for meseex_id in terminated_ids:
            meseex = meekz.get(meseex_id)
            if not meseex:
                continue
                
            if meseex_id in completed_meekz:
                recent_completed.append((meseex, meseex.total_duration_ms))
            else:
                recent_failed.append((meseex, meseex.total_duration_ms))
        
        # Sort by most recent (highest duration)
        recent_completed.sort(key=lambda x: x[1], reverse=True)
        recent_failed.sort(key=lambda x: x[1], reverse=True)
        
        recent_table = Table(title="Most Recent Jobs", box=box.MINIMAL)
        recent_table.add_column("Name", style="cyan")
        recent_table.add_column("Status", style="green")
        recent_table.add_column("Runtime", style="magenta")
        
        # Add most recent completions
        for meseex, _ in recent_completed[:3]:
            recent_table.add_row(
                meseex.name,
                "✓ Completed",
                self._format_duration_ms(meseex.total_duration_ms)
            )
            
        # Add most recent failures
        for meseex, _ in recent_failed[:2]:
            recent_table.add_row(
                meseex.name,
                "✗ Failed",
                self._format_duration_ms(meseex.total_duration_ms)
            )
        
        summary_group = Group(
            table,
            recent_table
        )
        
        return Panel(
            summary_group,
            title=f"Terminated Jobs Summary (Total: {total_terminated})",
            box=box.ROUNDED,
            border_style="dim",
            expand=True,  # Expand to fill available width
            width=None  # Allow width to be determined by parent container
        )

    def _create_terminated_job_line(self, meseex, meseex_id, completed_meekz):
        """Create a line for a terminated job."""
        run_time = self._format_duration_ms(meseex.total_duration_ms)
        
        if meseex_id in completed_meekz:
            status = Text("✓ Completed", style="green")
            msg = ""
        else: # Failed
            status = Text("✗ Failed", style="red")
            msg = self._format_error(meseex.error)
        
        return Text.assemble(
            (f"{meseex.name:<20} ", "cyan"), 
            status, 
            (f" Runtime: {run_time:<10}", "magenta"), 
            (f" {msg}", "yellow")
        )

    def _prepare_active_panel(self, meekz, terminated_ids):
        """Prepare panel for active jobs."""
        active_lines = []
        active_meekz_list = []
        
        # Process active jobs by checking if they're actually active (not terminated)
        for meseex_id, meseex in meekz.items():
            if meseex_id not in terminated_ids and meseex:
                active_meekz_list.append(meseex)
        
        # Sort by name for consistent display
        active_meekz_list.sort(key=lambda m: m.name)
        
        # If there are too many active jobs, use the summary view
        if len(active_meekz_list) > self._max_detailed_jobs:
            return self._prepare_summary_active_panel(active_meekz_list)
        
        for meseex in active_meekz_list:
            line = self._create_active_job_line(meseex)
            active_lines.append(line)

        if active_lines:
            active_content = Text("\n").join(active_lines)
            return Panel(
                active_content, 
                title="Active Jobs", 
                box=box.ROUNDED, 
                border_style="blue",
                expand=True,
                width=None
            )
        return None

    def _prepare_summary_active_panel(self, active_meekz_list: List[MrMeseex]):
        """Prepare a summary panel for active jobs when there are many jobs."""
        total_active = len(active_meekz_list)
        
        # Group jobs by task
        task_groups = defaultdict(list)
        for meseex in active_meekz_list:
            current_task = str(meseex.task) if isinstance(meseex.task, str) else f"Task {meseex.task}"
            task_groups[current_task].append(meseex)
        
        # Calculate average progress
        avg_progress = sum(meseex.progress for meseex in active_meekz_list) / total_active if total_active > 0 else 0
        
        # Create progress bar for overall progress
        overall_width = 20  # Reduced for side-by-side view
        filled = int(overall_width * avg_progress)
        overall_bar = f"[{'=' * filled}{' ' * (overall_width - filled)}] {avg_progress * 100:.1f}%"
        
        # Create task distribution table
        task_table = Table(box=box.MINIMAL)
        task_table.add_column("Task", style="cyan")
        task_table.add_column("Count", style="green")
        task_table.add_column("Avg Progress", style="magenta")
        
        for task, task_meekz in sorted(task_groups.items()):
            task_avg_progress = sum(m.progress for m in task_meekz) / len(task_meekz)
            task_bar_width = 10  # Reduced for side-by-side view
            task_filled = int(task_bar_width * task_avg_progress)
            task_bar = f"[{'=' * task_filled}{' ' * (task_bar_width - task_filled)}] {task_avg_progress * 100:.1f}%"
            
            task_table.add_row(
                task,
                str(len(task_meekz)),
                task_bar
            )
        
        # Create spinner for animation
        spinner = self.SPINNER_FRAMES[self._spinner_frame]
        
        summary_group = Group(
            Text.assemble(
                ("Overall Progress: ", "bold cyan"),
                (overall_bar, "green")
            ),
            Text("\nActive Jobs by Task:", style="bold cyan"),
            task_table,
            Text.assemble(
                (f"\n{spinner} Processing {total_active} active jobs...", "yellow")
            )
        )
        
        return Panel(
            summary_group,
            title=f"Active Jobs Summary (Total: {total_active})",
            box=box.ROUNDED,
            border_style="blue",
            expand=True,  # Expand to fill available width
            width=None  # Allow width to be determined by parent container
        )

    def _create_active_job_line(self, meseex):
        """Create a line for an active job."""
        name = meseex.name
        current_task = str(meseex.task) if isinstance(meseex.task, str) else f"Task {meseex.task}"
        task_display = f"{current_task} ({meseex.current_task_index + 1}/{meseex.n_tasks})"
        progress_display = self._create_progress_display(meseex)
        running_time = self._format_duration_ms(meseex.total_duration_ms)
        total_progress = f"{meseex.progress * 100:.1f}%"
        message = meseex.task_progress.message if meseex.task_progress and meseex.task_progress.message else ""
        
        return Text.assemble(
            (f"{name:<20} ", "cyan"),
            (f"Task: {task_display:<20} ", "green"),
            (f"Progress: {progress_display:<25} ", "default"),
            (f"Running: {running_time:<10} ", "magenta"),
            (f"Total: {total_progress:<8} ", "blue"),
            (f"{message}", "yellow")
        )

    def _create_progress_display(self, meseex: MrMeseex) -> str:
        """Creates either a progress bar or spinner for task progress."""
        if meseex.task_progress and meseex.task_progress.percent is not None and meseex.task_progress.percent > 0.0:
            # Create a mini progress bar
            percent = meseex.task_progress.percent
            width = 15 # Reduced width for text display
            filled = int(width * percent)
            bar = f"[{'=' * filled}{' ' * (width - filled)}] {percent * 100:.1f}%"
            return bar
        else:
            # Show spinner
            spinner = self.SPINNER_FRAMES[self._spinner_frame]
            return f"{spinner} working..."
    
    def stop(self):
        """Stops the Rich Live display cleanly."""
        if self._live:
            self._live.stop()
            self._live = None
        # Clear internal tracking
        self._completed_shown.clear()
        self._failed_shown.clear()

    def _format_error(self, error: Optional[Exception]) -> str:
        """Formats error messages for display."""
        if not error:
            return ""
        error_msg = str(error)
        # Add task info if available and not already in message
        if hasattr(error, 'task') and error.task:
            task_str = str(error.task)
            if f"Task '{task_str}'" not in error_msg and task_str not in error_msg:
                error_msg = f"Task '{task_str}': {error_msg}"
        # Limit error message length
        max_len = 200
        if len(error_msg) > max_len:
            error_msg = error_msg[:max_len - 3] + "..."
        return error_msg

    def _format_duration_ms(self, duration_ms: float) -> str:
        """Format millisecond duration in a human-readable format"""
        if duration_ms is None:
            return "n/a"
            
        # Convert to seconds
        duration = duration_ms / 1000.0
        
        if duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            m, s = divmod(int(duration), 60)
            return f"{m}m {s}s"
        else:
            h, rem = divmod(int(duration), 3600)
            m, _ = divmod(rem, 60)
            return f"{h}h {m}m"

