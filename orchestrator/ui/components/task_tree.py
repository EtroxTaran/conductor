"""Task tree component.

Displays hierarchical task list with status icons and Ralph loop iterations.
"""

from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from ..state_adapter import UIStateSnapshot, TaskUIInfo


def get_status_icon(status: str) -> str:
    """Get status icon for a task.

    Args:
        status: Task status string

    Returns:
        Unicode icon character
    """
    icons = {
        "completed": "\u2713",    # Check mark
        "in_progress": "\u26a1",  # Lightning bolt
        "pending": "\u25cb",      # Empty circle
        "failed": "\u2717",       # X mark
        "blocked": "\u23f8",      # Pause icon
    }
    return icons.get(status, "\u25cb")


def get_status_style(status: str) -> str:
    """Get Rich style for a task status.

    Args:
        status: Task status string

    Returns:
        Rich style string
    """
    styles = {
        "completed": "green",
        "in_progress": "yellow bold",
        "pending": "dim",
        "failed": "red",
        "blocked": "yellow",
    }
    return styles.get(status, "white")


def render_task_line(task: TaskUIInfo, is_current: bool) -> Text:
    """Render a single task line.

    Args:
        task: Task UI info
        is_current: Whether this is the current task

    Returns:
        Rich Text for the task line
    """
    text = Text()

    # Status icon
    icon = get_status_icon(task.status)
    style = get_status_style(task.status)
    text.append(f"{icon} ", style=style)

    # Task ID and title
    text.append(f"{task.id} ", style="bold" if is_current else "")
    text.append(task.title, style=style)

    # Add iteration info for in-progress tasks
    if task.status == "in_progress" and task.iteration > 0:
        text.append(f" [iter {task.iteration}/{task.max_iterations}]", style="cyan")

        # Add test status if available
        if task.tests_passed is not None and task.tests_total is not None:
            passed_style = "green" if task.tests_passed == task.tests_total else "yellow"
            text.append(f" ({task.tests_passed}/{task.tests_total} tests)", style=passed_style)

    return text


def render_task_tree(snapshot: UIStateSnapshot) -> Panel:
    """Render the task tree panel.

    Displays:
    - Task count summary (e.g., "Tasks: 4/7 complete")
    - Tree view of all tasks with status icons
    - Ralph loop iteration info for current task

    Args:
        snapshot: Current UI state snapshot

    Returns:
        Rich Panel renderable
    """
    # Summary line
    summary = Text()
    summary.append("\U0001f4cb ", style="")  # Clipboard emoji
    summary.append("Tasks: ", style="bold")
    summary.append(f"{snapshot.tasks_completed}/{snapshot.tasks_total}", style="green")
    summary.append(" complete")

    if not snapshot.tasks:
        # No tasks yet
        content = Text()
        content.append_text(summary)
        content.append("\n")
        content.append("  No tasks defined yet", style="dim")
        return Panel(content, border_style="blue", padding=(0, 1))

    # Build tree
    tree = Tree(summary)

    for task in snapshot.tasks:
        is_current = task.id == snapshot.current_task_id
        task_line = render_task_line(task, is_current)

        # Add prefix for tree structure
        prefix = "\u251c\u2500 " if task != snapshot.tasks[-1] else "\u2514\u2500 "
        prefixed = Text(prefix, style="dim")
        prefixed.append_text(task_line)

        tree.add(prefixed)

    return Panel(
        tree,
        border_style="blue",
        padding=(0, 1),
    )
