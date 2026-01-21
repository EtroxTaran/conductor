"""UI module for workflow monitoring and progress display."""

import os
import sys
from typing import Optional

from orchestrator.ui.state_adapter import TaskUIInfo, EventLogEntry, UIStateSnapshot
from orchestrator.ui.callbacks import NullCallback, ProgressCallback, UICallbackHandler
from orchestrator.ui.display import PlaintextDisplay, WorkflowDisplay, UIState


def is_interactive() -> bool:
    """
    Check if the current environment supports interactive display.

    Returns:
        True if interactive mode is supported, False otherwise
    """
    # Check CI environment variables
    ci_vars = [
        "CI",
        "CONTINUOUS_INTEGRATION",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "CIRCLECI",
        "JENKINS_URL",
        "BUILDKITE",
        "TRAVIS",
        "TF_BUILD",
    ]
    for var in ci_vars:
        if os.environ.get(var):
            return False

    # Check explicit flags
    if os.environ.get("ORCHESTRATOR_PLAIN_OUTPUT"):
        return False

    if os.environ.get("NO_COLOR"):
        return False

    # Check if stdout is a TTY
    if not sys.stdout.isatty():
        return False

    return True


def create_display(
    project_name: str,
    interactive: Optional[bool] = None,
) -> "PlaintextDisplay | WorkflowDisplay":
    """
    Create appropriate display based on environment.

    Args:
        project_name: Name of the project
        interactive: Force interactive mode (auto-detect if None)

    Returns:
        Display instance
    """
    if interactive is None:
        interactive = is_interactive()

    if interactive:
        return WorkflowDisplay(project_name)
    else:
        return PlaintextDisplay(project_name)


__all__ = [
    "create_display",
    "is_interactive",
    "PlaintextDisplay",
    "WorkflowDisplay",
    "UIState",
    "UICallbackHandler",
    "ProgressCallback",
    "NullCallback",
    "TaskUIInfo",
    "EventLogEntry",
    "UIStateSnapshot",
]
