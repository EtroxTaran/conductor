"""Rich-based progress visualization for meta-architect workflow.

This module provides a live terminal UI for displaying workflow progress,
task status, and metrics. Automatically falls back to plaintext output
in non-interactive environments (CI/CD, piped output).

Public API:
    create_display: Factory function that returns appropriate display type
    WorkflowDisplay: Rich-based interactive display
    PlaintextDisplay: Fallback for non-interactive environments
    ProgressCallback: Protocol for receiving workflow updates
    UICallbackHandler: Callback handler for LangGraph integration
"""

from .fallback import is_interactive, PlaintextDisplay
from .state_adapter import UIState
from .display import WorkflowDisplay
from .callbacks import ProgressCallback, UICallbackHandler


def create_display(
    project_name: str,
    interactive: bool | None = None,
) -> WorkflowDisplay | PlaintextDisplay:
    """Create the appropriate display for the current environment.

    Args:
        project_name: Name of the project being orchestrated
        interactive: Force interactive mode (True/False) or auto-detect (None)

    Returns:
        WorkflowDisplay for interactive terminals, PlaintextDisplay otherwise
    """
    if interactive is None:
        interactive = is_interactive()

    if interactive:
        return WorkflowDisplay(project_name)
    else:
        return PlaintextDisplay(project_name)


__all__ = [
    "create_display",
    "WorkflowDisplay",
    "PlaintextDisplay",
    "UIState",
    "ProgressCallback",
    "UICallbackHandler",
    "is_interactive",
]
