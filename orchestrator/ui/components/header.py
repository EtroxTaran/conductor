"""Header panel component.

Displays project name, elapsed time, and status indicator.
"""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..state_adapter import UIStateSnapshot


def format_elapsed(seconds: int) -> str:
    """Format elapsed time as human-readable string.

    Args:
        seconds: Total elapsed seconds

    Returns:
        Formatted time string (e.g., "2m 34s", "1h 23m")
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes, secs = divmod(seconds, 60)
        return f"{minutes}m {secs:02d}s"
    else:
        hours, remainder = divmod(seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes:02d}m"


def get_status_indicator(status: str) -> Text:
    """Get status indicator with color.

    Args:
        status: Status string (running, paused, completed, failed)

    Returns:
        Rich Text with appropriate styling
    """
    indicators = {
        "running": ("RUNNING", "green"),
        "paused": ("PAUSED", "yellow"),
        "completed": ("DONE", "green bold"),
        "failed": ("FAILED", "red bold"),
    }
    text, style = indicators.get(status, ("UNKNOWN", "white"))
    return Text(text, style=style)


def render_header(snapshot: UIStateSnapshot) -> Panel:
    """Render the header panel.

    Displays:
    - META-ARCHITECT title
    - Project name
    - Elapsed time
    - Status indicator

    Args:
        snapshot: Current UI state snapshot

    Returns:
        Rich Panel renderable
    """
    table = Table.grid(expand=True)
    table.add_column(justify="left", ratio=1)
    table.add_column(justify="center", ratio=2)
    table.add_column(justify="right", ratio=1)

    # Left: Title
    title = Text("META-ARCHITECT", style="bold cyan")

    # Center: Project name
    project = Text(snapshot.project_name, style="bold white")

    # Right: Time and status
    elapsed = format_elapsed(snapshot.elapsed_seconds)
    status_indicator = get_status_indicator(snapshot.status)
    right_text = Text()
    right_text.append(elapsed, style="dim")
    right_text.append(" | ")
    right_text.append_text(status_indicator)

    table.add_row(title, project, right_text)

    return Panel(
        table,
        border_style="cyan",
        padding=(0, 1),
    )
