"""Thread-safe UI state adapter.

Provides UIState class that converts WorkflowState to a format
suitable for rendering, with thread-safe updates.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..langgraph.state import WorkflowState, Task, TaskStatus, PhaseStatus


@dataclass
class TaskUIInfo:
    """UI-friendly task information."""

    id: str
    title: str
    status: str  # pending, in_progress, completed, failed, blocked
    iteration: int = 0
    max_iterations: int = 10
    tests_passed: int | None = None
    tests_total: int | None = None


@dataclass
class EventLogEntry:
    """Single event log entry."""

    timestamp: datetime
    message: str
    level: str = "info"  # info, warning, error, success


@dataclass
class UIStateSnapshot:
    """Immutable snapshot of UI state for rendering."""

    project_name: str
    elapsed_seconds: int
    current_phase: int
    total_phases: int
    phase_progress: float  # 0.0 to 1.0
    phase_name: str
    tasks: list[TaskUIInfo]
    tasks_completed: int
    tasks_total: int
    current_task_id: str | None
    tokens: int
    cost: float
    files_created: int
    files_modified: int
    recent_events: list[EventLogEntry]
    status: str  # running, paused, completed, failed


class UIState:
    """Thread-safe UI state container.

    Converts WorkflowState updates into a format suitable for
    Rich rendering, with lock protection for thread safety.
    """

    PHASE_NAMES = {
        1: "Planning",
        2: "Validation",
        3: "Implementation",
        4: "Verification",
        5: "Completion",
    }

    def __init__(self, project_name: str):
        """Initialize UI state.

        Args:
            project_name: Name of the project
        """
        self._lock = threading.Lock()
        self._project_name = project_name
        self._start_time = datetime.now()
        self._current_phase = 0
        self._total_phases = 5
        self._tasks: list[TaskUIInfo] = []
        self._tasks_completed = 0
        self._tasks_total = 0
        self._current_task_id: str | None = None
        self._tokens = 0
        self._cost = 0.0
        self._files_created = 0
        self._files_modified = 0
        self._events: list[EventLogEntry] = []
        self._max_events = 10
        self._status = "running"

    def update_from_workflow_state(self, state: "WorkflowState") -> None:
        """Update UI state from WorkflowState.

        Thread-safe update of internal state.

        Args:
            state: Current workflow state
        """
        with self._lock:
            # Update phase
            self._current_phase = state.get("current_phase", 0)

            # Update tasks
            tasks = state.get("tasks", [])
            completed_ids = set(state.get("completed_task_ids", []))
            failed_ids = set(state.get("failed_task_ids", []))

            self._tasks_total = len(tasks)
            self._tasks_completed = len(completed_ids)
            self._current_task_id = state.get("current_task_id")

            # Convert tasks to UI format
            self._tasks = []
            for task in tasks:
                task_id = task.get("id", "")
                status = "pending"
                if task_id in completed_ids:
                    status = "completed"
                elif task_id in failed_ids:
                    status = "failed"
                elif task_id == self._current_task_id:
                    status = "in_progress"
                elif task.get("status"):
                    status = str(task.get("status").value if hasattr(task.get("status"), "value") else task.get("status"))

                self._tasks.append(TaskUIInfo(
                    id=task_id,
                    title=task.get("title", "Unknown"),
                    status=status,
                    iteration=task.get("attempts", 0),
                    max_iterations=task.get("max_attempts", 3),
                ))

            # Update status based on phase state
            phase_status = state.get("phase_status", {})
            current_phase_state = phase_status.get(str(self._current_phase))
            if current_phase_state:
                if hasattr(current_phase_state, "status"):
                    ps = current_phase_state.status
                    if hasattr(ps, "value"):
                        ps = ps.value
                    if ps == "completed" and self._current_phase == 5:
                        self._status = "completed"
                    elif ps == "failed":
                        self._status = "failed"
                    elif ps == "blocked":
                        self._status = "paused"

    def add_event(self, message: str, level: str = "info") -> None:
        """Add an event to the log.

        Thread-safe event addition.

        Args:
            message: Event message
            level: Log level
        """
        with self._lock:
            self._events.append(EventLogEntry(
                timestamp=datetime.now(),
                message=message,
                level=level,
            ))
            # Keep only recent events
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def update_ralph_iteration(
        self,
        task_id: str,
        iteration: int,
        max_iter: int,
        tests_passed: int | None = None,
        tests_total: int | None = None,
    ) -> None:
        """Update Ralph loop iteration for a task.

        Thread-safe update.

        Args:
            task_id: Task ID
            iteration: Current iteration
            max_iter: Maximum iterations
            tests_passed: Tests passing
            tests_total: Total tests
        """
        with self._lock:
            for task in self._tasks:
                if task.id == task_id:
                    task.iteration = iteration
                    task.max_iterations = max_iter
                    task.tests_passed = tests_passed
                    task.tests_total = tests_total
                    break

    def update_metrics(
        self,
        tokens: int | None = None,
        cost: float | None = None,
        files_created: int | None = None,
        files_modified: int | None = None,
    ) -> None:
        """Update metrics.

        Thread-safe update.

        Args:
            tokens: Total tokens
            cost: Total cost
            files_created: Files created count
            files_modified: Files modified count
        """
        with self._lock:
            if tokens is not None:
                self._tokens = tokens
            if cost is not None:
                self._cost = cost
            if files_created is not None:
                self._files_created = files_created
            if files_modified is not None:
                self._files_modified = files_modified

    def get_snapshot(self) -> UIStateSnapshot:
        """Get immutable snapshot of current state.

        Thread-safe snapshot for rendering.

        Returns:
            UIStateSnapshot for rendering
        """
        with self._lock:
            elapsed = datetime.now() - self._start_time
            phase_name = self.PHASE_NAMES.get(self._current_phase, "Unknown")

            # Calculate phase progress
            phase_progress = 0.0
            if self._current_phase > 0:
                # Base progress from completed phases
                base = (self._current_phase - 1) / self._total_phases

                # Add progress within current phase based on task completion
                if self._tasks_total > 0 and self._current_phase == 3:
                    # Implementation phase - use task progress
                    task_progress = self._tasks_completed / self._tasks_total
                    phase_progress = base + (task_progress / self._total_phases)
                else:
                    phase_progress = base + (0.5 / self._total_phases)  # Assume halfway through phase

            return UIStateSnapshot(
                project_name=self._project_name,
                elapsed_seconds=int(elapsed.total_seconds()),
                current_phase=self._current_phase,
                total_phases=self._total_phases,
                phase_progress=min(1.0, phase_progress),
                phase_name=phase_name,
                tasks=list(self._tasks),  # Copy
                tasks_completed=self._tasks_completed,
                tasks_total=self._tasks_total,
                current_task_id=self._current_task_id,
                tokens=self._tokens,
                cost=self._cost,
                files_created=self._files_created,
                files_modified=self._files_modified,
                recent_events=list(self._events),  # Copy
                status=self._status,
            )
