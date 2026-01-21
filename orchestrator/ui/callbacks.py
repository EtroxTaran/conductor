"""Callback protocol and handler for LangGraph integration.

Provides ProgressCallback protocol and UICallbackHandler implementation
for receiving workflow updates from LangGraph nodes.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..langgraph.state import WorkflowState
    from .display import WorkflowDisplay
    from .fallback import PlaintextDisplay


@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for receiving workflow progress updates.

    Implement this protocol to receive callbacks from the
    LangGraph workflow execution.
    """

    def on_node_start(self, node_name: str, state: "WorkflowState") -> None:
        """Called when a workflow node starts execution.

        Args:
            node_name: Name of the node (e.g., "planning", "cursor_validate")
            state: Current workflow state
        """
        ...

    def on_node_end(self, node_name: str, state: "WorkflowState") -> None:
        """Called when a workflow node completes execution.

        Args:
            node_name: Name of the node
            state: Updated workflow state
        """
        ...

    def on_ralph_iteration(
        self,
        task_id: str,
        iteration: int,
        max_iterations: int,
        tests_passed: int | None = None,
        tests_total: int | None = None,
    ) -> None:
        """Called when a Ralph loop iteration completes.

        Args:
            task_id: Current task ID
            iteration: Current iteration number
            max_iterations: Maximum iterations allowed
            tests_passed: Number of tests passing
            tests_total: Total number of tests
        """
        ...

    def on_task_start(self, task_id: str, task_title: str) -> None:
        """Called when a task starts execution.

        Args:
            task_id: Task identifier
            task_title: Task title
        """
        ...

    def on_task_complete(self, task_id: str, success: bool) -> None:
        """Called when a task completes.

        Args:
            task_id: Task identifier
            success: Whether the task succeeded
        """
        ...

    def on_metrics_update(
        self,
        tokens: int | None = None,
        cost: float | None = None,
        files_created: int | None = None,
        files_modified: int | None = None,
    ) -> None:
        """Called when metrics are updated.

        Args:
            tokens: Total tokens used
            cost: Total cost
            files_created: Number of files created
            files_modified: Number of files modified
        """
        ...


class UICallbackHandler:
    """Callback handler that updates the UI display.

    Bridges LangGraph workflow events to the UI display system.
    Handles both WorkflowDisplay and PlaintextDisplay.
    """

    # Map node names to user-friendly descriptions
    NODE_DESCRIPTIONS = {
        "prerequisites": "Checking prerequisites",
        "product_validation": "Validating PRODUCT.md",
        "planning": "Creating implementation plan",
        "cursor_validate": "Cursor validating plan",
        "gemini_validate": "Gemini validating plan",
        "validation_fan_in": "Merging validation feedback",
        "approval_gate": "Awaiting approval",
        "pre_implementation": "Pre-implementation checks",
        "task_breakdown": "Breaking down into tasks",
        "select_task": "Selecting next task",
        "implement_task": "Implementing task",
        "verify_task": "Verifying task",
        "implementation": "Implementing feature",
        "build_verification": "Verifying build",
        "cursor_review": "Cursor reviewing code",
        "gemini_review": "Gemini reviewing code",
        "verification_fan_in": "Merging code reviews",
        "coverage_check": "Checking test coverage",
        "security_scan": "Running security scan",
        "human_escalation": "Awaiting human input",
        "completion": "Completing workflow",
    }

    def __init__(self, display: "WorkflowDisplay | PlaintextDisplay"):
        """Initialize the callback handler.

        Args:
            display: Display instance to update
        """
        self._display = display
        self._current_task_id: str | None = None

    def on_node_start(self, node_name: str, state: "WorkflowState") -> None:
        """Handle node start event.

        Args:
            node_name: Name of the starting node
            state: Current workflow state
        """
        description = self.NODE_DESCRIPTIONS.get(node_name, f"Running {node_name}")
        self._display.log_event(f"Started: {description}", "info")
        self._display.update_state(state)

    def on_node_end(self, node_name: str, state: "WorkflowState") -> None:
        """Handle node completion event.

        Args:
            node_name: Name of the completed node
            state: Updated workflow state
        """
        description = self.NODE_DESCRIPTIONS.get(node_name, node_name)

        # Check for errors in state
        errors = state.get("errors", [])
        recent_errors = [e for e in errors if e.get("node") == node_name]

        if recent_errors:
            self._display.log_event(f"Failed: {description}", "error")
        else:
            self._display.log_event(f"Completed: {description}", "success")

        self._display.update_state(state)

    def on_ralph_iteration(
        self,
        task_id: str,
        iteration: int,
        max_iterations: int,
        tests_passed: int | None = None,
        tests_total: int | None = None,
    ) -> None:
        """Handle Ralph loop iteration event.

        Args:
            task_id: Current task ID
            iteration: Current iteration number
            max_iterations: Maximum iterations
            tests_passed: Tests passing
            tests_total: Total tests
        """
        self._display.update_ralph_iteration(
            task_id=task_id,
            iteration=iteration,
            max_iter=max_iterations,
            tests_passed=tests_passed,
            tests_total=tests_total,
        )

    def on_task_start(self, task_id: str, task_title: str) -> None:
        """Handle task start event.

        Args:
            task_id: Task identifier
            task_title: Task title
        """
        self._current_task_id = task_id
        self._display.log_event(f"Task {task_id} started: {task_title}", "info")

    def on_task_complete(self, task_id: str, success: bool) -> None:
        """Handle task completion event.

        Args:
            task_id: Task identifier
            success: Whether the task succeeded
        """
        level = "success" if success else "error"
        status = "completed" if success else "failed"
        self._display.log_event(f"Task {task_id} {status}", level)
        self._current_task_id = None

    def on_metrics_update(
        self,
        tokens: int | None = None,
        cost: float | None = None,
        files_created: int | None = None,
        files_modified: int | None = None,
    ) -> None:
        """Handle metrics update event.

        Args:
            tokens: Total tokens
            cost: Total cost
            files_created: Files created
            files_modified: Files modified
        """
        self._display.update_metrics(
            tokens=tokens,
            cost=cost,
            files_created=files_created,
            files_modified=files_modified,
        )


class NullCallback:
    """No-op callback implementation.

    Used when no UI display is configured.
    """

    def on_node_start(self, node_name: str, state: Any) -> None:
        pass

    def on_node_end(self, node_name: str, state: Any) -> None:
        pass

    def on_ralph_iteration(
        self,
        task_id: str,
        iteration: int,
        max_iterations: int,
        tests_passed: int | None = None,
        tests_total: int | None = None,
    ) -> None:
        pass

    def on_task_start(self, task_id: str, task_title: str) -> None:
        pass

    def on_task_complete(self, task_id: str, success: bool) -> None:
        pass

    def on_metrics_update(
        self,
        tokens: int | None = None,
        cost: float | None = None,
        files_created: int | None = None,
        files_modified: int | None = None,
    ) -> None:
        pass
