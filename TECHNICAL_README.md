# Meseex Technical README

## TL;DR
`meseex` is a lightweight workflow runtime for Python jobs that need to mix synchronous code, asynchronous I/O, and simple state tracking.

At runtime:
- A `MeseexBox` owns the execution environment.
- Each submitted job is represented by a `MrMeseex` instance.
- Each `MrMeseex` moves through an ordered list of tasks.
- Tasks may be regular functions or async functions.
- Sync tasks run in a thread pool.
- Async tasks run on a dedicated event loop in a background thread.
- Results, progress, errors, and cancellation state live on the `MrMeseex`.

The package is intentionally small: it is not a general distributed workflow engine, but a local orchestration layer for many concurrent jobs.

## Mental Model
Think of the package as three layers:

1. `MrMeseex`
   - The per-job state machine.
   - Stores task order, current task, progress, task outputs, errors, and termination state.

2. `MeseexBox`
   - The scheduler and lifecycle manager.
   - Pulls queued jobs, starts their next task, handles transitions, and updates the progress UI.

3. `TaskExecutor`
   - The execution backend.
   - Routes async callables to `AsyncTaskExecutor` and sync callables to `ThreadPoolTaskExecutor`.

## Core Flow
Typical execution looks like this:

1. Create a `MeseexBox` with a mapping of task names to callables.
2. Call `summon(...)` or `summon_meseex(...)`.
3. The job enters the queue in `MeseexStore`.
4. The background worker in `MeseexBox` dequeues the job and advances it with `next_task()`.
5. The selected task is submitted through `TaskExecutor`.
6. When the task finishes:
   - a normal value becomes the task output and the next task starts
   - a `Repeat` signal re-schedules the same task later
   - an exception marks the job as failed
7. When no tasks remain, the job reaches `TerminationState.SUCCESS`.

## Main Types
### `MrMeseex`
Important responsibilities:
- hold task-local and job-level state
- expose convenience accessors like `input`, `prev_task_output`, `result`, `error`, and `progress`
- support waiting from sync code via `wait_for_result()`
- support awaiting from async code via `__await__`
- own terminal lifecycle flags: `SUCCESS`, `FAILED`, `CANCELLED`

### `MeseexBox`
Important responsibilities:
- queue and start jobs
- call task functions in the right executor
- manage task-to-task transitions
- track working/completed/failed jobs in `MeseexStore`
- coordinate cancellation and binding custom handlers

### `MeseexStore`
Thread-safe in-memory state store for:
- queued jobs
- working jobs
- terminated jobs
- task-to-job mappings used by the progress bar

### `TaskExecutor`
Facade that hides whether a task is sync or async:
- `AsyncTaskExecutor` runs coroutines on a dedicated event loop thread
- `ThreadPoolTaskExecutor` runs regular functions in a thread pool

## Control Flow
The package supports lightweight workflow control through signals.

The main built-in pattern is polling:
- `@polling_task(...)` wraps a task
- returning `PollAgain(...)` becomes a `Repeat(delay_s=...)`
- `MeseexBox` sees `Repeat` and schedules the same task again later

This keeps polling logic inside the task while the orchestration loop stays generic.

## Progress And Outputs
Progress is stored per task in `TaskMeta` and exposed through:
- `task_progress`
- `set_task_progress(...)`
- `progress`
- `total_duration_ms`

Task outputs are also stored per task, which enables chained workflows:
- task N can read `prev_task_output`
- consumers can inspect outputs by task name or index

## Error Model
Errors are normalized into `TaskException`.

Important behavior:
- task exceptions are captured by `MeseexBox`
- they are stored on the `MrMeseex`
- the job becomes `FAILED`
- the last error is exposed via `error`
- all collected errors are available via `get_errors()`

## How Cancellation Works
Cancellation is cooperative and lifecycle-aware.

### High-level behavior
- `MrMeseex.cancel()` is the public entry point.
- `MrMeseex` stores cancellation intent with `request_cancel()`.
- `MeseexBox.cancel_meseex(...)` is the execution-level cancellation coordinator.
- Final cancellation is represented by `TerminationState.CANCELLED`.

### What happens for each state
- Queued job:
  - It is marked cancelled immediately and removed from active processing.

- Running async task:
  - `MeseexBox` asks the active `AsyncTask` to cancel.
  - The underlying `asyncio.Task` is cancelled on the loop thread.
  - The job is finalized as cancelled.

- Running sync task:
  - Python threads cannot be forcefully interrupted safely.
  - The job is marked as cancellation-requested.
  - `MeseexBox` prevents any further task transitions once the current function returns.

### Important implication
Cancellation is immediate for queued jobs, usually fast for async I/O, and best-effort for CPU-bound or blocking sync functions.

### Cooperative Cancellation in Synchronous Tasks
For synchronous tasks, which cannot be forcefully interrupted safely in Python, `MrMeseex` provides the `cancel_requested` property. Tasks can periodically check this property to detect if a cancellation has been initiated and then exit gracefully. This allows for controlled cleanup and prevents unexpected behavior.

Example:
```python
import time
from meseex.mr_meseex import MrMeseex

def my_cancellable_task(meseex: MrMeseex):
    for i in range(100):
        if meseex.cancel_requested:
            print(f"Task {meseex.name}: Cancellation requested. Exiting gracefully.")
            # Perform any necessary cleanup here
            return "Task cancelled cooperatively"
        print(f"Task {meseex.name}: Working on item {i}")
        time.sleep(0.1)
    return "Task completed"
```

## Design Strengths
- Small surface area
- Works from sync and async user code
- Good fit for many I/O-heavy jobs in parallel
- Control-flow extensions can stay local to task code

## Current Constraints
- State is in-memory only
- No persistence or cross-process coordination
- Sync task cancellation cannot preempt already running Python code
- Cancellation is modeled together with failed jobs in the store/progress bookkeeping

## Where To Extend
Common extension points:
- add new control-flow helpers in `control_flow`
- add richer termination semantics on `MrMeseex`
- improve `MeseexStore` if cancelled jobs should be tracked separately from failed jobs
- add structured instrumentation around task submission and transitions
