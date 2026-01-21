"""Rich-based live workflow display.

Provides WorkflowDisplay class that renders a live terminal UI
using Rich's Live display with automatic refresh.
"""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel

from .state_adapter import UIState
from .components import (
    render_header,
    render_phase_bar,
    render_task_tree,
    render_metrics_panel,
    render_event_log,
)

if TYPE_CHECKING:
    from ..langgraph.state import WorkflowState


class WorkflowDisplay:
    """Rich-based live workflow display.

    Provides a real-time terminal UI showing:
    - Header with project name and elapsed time
    - Phase progress bar
    - Task tree with status icons
    - Metrics (tokens, cost, files)
    - Event log

    Uses Rich's Live display for automatic refresh at 2Hz.
    """

    REFRESH_RATE = 2  # Updates per second

    def __init__(self, project_name: str):
        """Initialize the workflow display.

        Args:
            project_name: Name of the project being orchestrated
        """
        self.project_name = project_name
        self._state = UIState(project_name)
        self._console = Console()
        self._live: Live | None = None

    def _build_layout(self) -> Panel:
        """Build the complete layout for rendering.

        Returns:
            Rich Panel containing all components
        """
        snapshot = self._state.get_snapshot()

        # Build component stack
        components = Group(
            render_header(snapshot),
            render_phase_bar(snapshot),
            render_task_tree(snapshot),
            render_metrics_panel(snapshot),
            render_event_log(snapshot),
        )

        return Panel(
            components,
            border_style="cyan",
            title="[bold cyan]Workflow Progress[/bold cyan]",
            subtitle="[dim]Press Ctrl+C to abort[/dim]",
        )

    @contextmanager
    def start(self) -> Generator["WorkflowDisplay", None, None]:
        """Context manager for display lifecycle.

        Starts the Rich Live display and yields self for updates.
        Automatically cleans up on exit.

        Yields:
            Self for chaining

        Example:
            with display.start() as d:
                d.update_state(state)
                d.log_event("Starting...")
        """
        self._live = Live(
            self._build_layout(),
            console=self._console,
            refresh_per_second=self.REFRESH_RATE,
            transient=False,
        )

        try:
            with self._live:
                yield self
        finally:
            self._live = None

    def _refresh(self) -> None:
        """Refresh the display with current state."""
        if self._live:
            self._live.update(self._build_layout())

    def update_state(self, state: "WorkflowState") -> None:
        """Update display with new workflow state.

        Thread-safe update that triggers a refresh.

        Args:
            state: Current workflow state
        """
        self._state.update_from_workflow_state(state)
        self._refresh()

    def log_event(self, message: str, level: str = "info") -> None:
        """Log an event to the display.

        Thread-safe event logging that triggers a refresh.

        Args:
            message: Event message
            level: Log level (info, warning, error, success)
        """
        self._state.add_event(message, level)
        self._refresh()

    def update_ralph_iteration(
        self,
        task_id: str,
        iteration: int,
        max_iter: int,
        tests_passed: int | None = None,
        tests_total: int | None = None,
    ) -> None:
        """Update Ralph loop iteration display.

        Thread-safe update for Ralph loop progress.

        Args:
            task_id: Current task ID
            iteration: Current iteration number
            max_iter: Maximum iterations
            tests_passed: Number of tests passing (optional)
            tests_total: Total number of tests (optional)
        """
        self._state.update_ralph_iteration(
            task_id=task_id,
            iteration=iteration,
            max_iter=max_iter,
            tests_passed=tests_passed,
            tests_total=tests_total,
        )

        # Log the event
        if tests_passed is not None and tests_total is not None:
            self._state.add_event(
                f"Ralph iteration {iteration}: {tests_passed}/{tests_total} tests passing",
                "info" if tests_passed < tests_total else "success",
            )
        else:
            self._state.add_event(
                f"Ralph iteration {iteration}/{max_iter}",
                "info",
            )

        self._refresh()

    def update_metrics(
        self,
        tokens: int | None = None,
        cost: float | None = None,
        files_created: int | None = None,
        files_modified: int | None = None,
    ) -> None:
        """Update metrics display.

        Thread-safe metrics update.

        Args:
            tokens: Total tokens used
            cost: Total cost in dollars
            files_created: Number of files created
            files_modified: Number of files modified
        """
        self._state.update_metrics(
            tokens=tokens,
            cost=cost,
            files_created=files_created,
            files_modified=files_modified,
        )
        self._refresh()

    def show_completion(self, success: bool, message: str) -> None:
        """Show completion status.

        Updates the status and shows a final message.

        Args:
            success: Whether the workflow completed successfully
            message: Completion message
        """
        level = "success" if success else "error"
        self._state.add_event(message, level)
        self._state._status = "completed" if success else "failed"
        self._refresh()
