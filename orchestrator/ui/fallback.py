"""Fallback display for non-interactive environments.

Provides is_interactive() detection and PlaintextDisplay class
for CI/CD pipelines and piped output scenarios.
"""

import os
import sys
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generator

if TYPE_CHECKING:
    from ..langgraph.state import WorkflowState


def is_interactive() -> bool:
    """Detect if running in an interactive terminal.

    Returns False if:
    - stdout is not a TTY (piped output)
    - CI environment variables are set
    - TERM is 'dumb' or unset
    - NO_COLOR environment variable is set
    - --plain flag was passed (via ORCHESTRATOR_PLAIN_OUTPUT)

    Returns:
        True if running in interactive terminal, False otherwise
    """
    # Check for explicit plain output flag
    if os.environ.get("ORCHESTRATOR_PLAIN_OUTPUT", "").lower() in ("true", "1"):
        return False

    # Check for CI environments
    ci_vars = [
        "CI",
        "CONTINUOUS_INTEGRATION",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "CIRCLECI",
        "JENKINS_URL",
        "BUILDKITE",
        "TRAVIS",
        "TF_BUILD",  # Azure DevOps
    ]
    for var in ci_vars:
        if os.environ.get(var):
            return False

    # Check for NO_COLOR standard
    if os.environ.get("NO_COLOR") is not None:
        return False

    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False

    # Check TERM environment variable
    term = os.environ.get("TERM", "")
    if not term or term == "dumb":
        return False

    return True


class PlaintextDisplay:
    """Plaintext display for non-interactive environments.

    Provides the same interface as WorkflowDisplay but outputs
    plain text without ANSI codes or live updates.
    """

    def __init__(self, project_name: str):
        """Initialize plaintext display.

        Args:
            project_name: Name of the project being orchestrated
        """
        self.project_name = project_name
        self._start_time: datetime | None = None
        self._current_phase = 0
        self._total_phases = 5
        self._tasks_completed = 0
        self._tasks_total = 0
        self._current_task_id: str | None = None
        self._ralph_iteration = 0
        self._ralph_max_iter = 0

    @contextmanager
    def start(self) -> Generator["PlaintextDisplay", None, None]:
        """Context manager for display lifecycle.

        Yields:
            Self for chaining
        """
        self._start_time = datetime.now()
        print(f"[{self._timestamp()}] META-ARCHITECT: Starting workflow for {self.project_name}")
        print("-" * 60)
        try:
            yield self
        finally:
            elapsed = self._get_elapsed()
            print("-" * 60)
            print(f"[{self._timestamp()}] Workflow completed in {elapsed}")

    def update_state(self, state: "WorkflowState") -> None:
        """Update display with new workflow state.

        Args:
            state: Current workflow state
        """
        # Update phase
        new_phase = state.get("current_phase", 0)
        if new_phase != self._current_phase:
            self._current_phase = new_phase
            print(f"[{self._timestamp()}] Phase {new_phase}/{self._total_phases}")

        # Update tasks
        tasks = state.get("tasks", [])
        completed_ids = state.get("completed_task_ids", [])
        self._tasks_total = len(tasks)
        self._tasks_completed = len(completed_ids)

        # Track current task
        new_task_id = state.get("current_task_id")
        if new_task_id and new_task_id != self._current_task_id:
            self._current_task_id = new_task_id
            task = next((t for t in tasks if t.get("id") == new_task_id), None)
            if task:
                print(f"[{self._timestamp()}] Task: {new_task_id} - {task.get('title', 'Unknown')}")

    def log_event(self, message: str, level: str = "info") -> None:
        """Log an event to the display.

        Args:
            message: Event message
            level: Log level (info, warning, error, success)
        """
        prefix = {
            "info": "INFO",
            "warning": "WARN",
            "error": "ERROR",
            "success": "OK",
        }.get(level, "INFO")
        print(f"[{self._timestamp()}] [{prefix}] {message}")

    def update_ralph_iteration(
        self,
        task_id: str,
        iteration: int,
        max_iter: int,
        tests_passed: int | None = None,
        tests_total: int | None = None,
    ) -> None:
        """Update Ralph loop iteration display.

        Args:
            task_id: Current task ID
            iteration: Current iteration number
            max_iter: Maximum iterations
            tests_passed: Number of tests passing (optional)
            tests_total: Total number of tests (optional)
        """
        self._ralph_iteration = iteration
        self._ralph_max_iter = max_iter

        if tests_passed is not None and tests_total is not None:
            print(
                f"[{self._timestamp()}] Ralph iteration {iteration}/{max_iter}: "
                f"{tests_passed}/{tests_total} tests passing"
            )
        else:
            print(f"[{self._timestamp()}] Ralph iteration {iteration}/{max_iter}")

    def update_metrics(
        self,
        tokens: int | None = None,
        cost: float | None = None,
        files_created: int | None = None,
        files_modified: int | None = None,
    ) -> None:
        """Update metrics display.

        Args:
            tokens: Total tokens used
            cost: Total cost in dollars
            files_created: Number of files created
            files_modified: Number of files modified
        """
        parts = []
        if tokens is not None:
            parts.append(f"Tokens: {tokens:,}")
        if cost is not None:
            parts.append(f"Cost: ${cost:.2f}")
        if files_created is not None:
            parts.append(f"Files: +{files_created}")
        if files_modified is not None:
            parts.append(f"~{files_modified}")

        if parts:
            print(f"[{self._timestamp()}] Metrics: {' | '.join(parts)}")

    def _timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().strftime("%H:%M:%S")

    def _get_elapsed(self) -> str:
        """Get elapsed time string."""
        if not self._start_time:
            return "0s"

        elapsed = datetime.now() - self._start_time
        total_seconds = int(elapsed.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
