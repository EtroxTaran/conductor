"""Event log component.

Displays recent workflow events with timestamps and level indicators.
"""

from rich.panel import Panel
from rich.text import Text

from ..state_adapter import UIStateSnapshot, EventLogEntry


def get_level_icon(level: str) -> tuple[str, str]:
    """Get icon and style for log level.

    Args:
        level: Log level string

    Returns:
        Tuple of (icon, style)
    """
    levels = {
        "info": ("\u2139", "blue"),      # Info icon
        "success": ("\u2713", "green"),  # Check mark
        "warning": ("\u26a0", "yellow"), # Warning icon
        "error": ("\u2717", "red"),      # X mark
    }
    return levels.get(level, ("\u2022", "white"))  # Bullet point default


def render_event(event: EventLogEntry) -> Text:
    """Render a single event line.

    Args:
        event: Event log entry

    Returns:
        Rich Text for the event line
    """
    text = Text()

    # Timestamp
    time_str = event.timestamp.strftime("%H:%M:%S")
    text.append(f"[{time_str}] ", style="dim")

    # Level icon
    icon, style = get_level_icon(event.level)
    text.append(f"{icon} ", style=style)

    # Message
    text.append(event.message, style=style if event.level in ("warning", "error") else "")

    return text


def render_event_log(snapshot: UIStateSnapshot, max_events: int = 4) -> Panel:
    """Render the event log panel.

    Displays recent workflow events with timestamps.

    Args:
        snapshot: Current UI state snapshot
        max_events: Maximum number of events to display

    Returns:
        Rich Panel renderable
    """
    content = Text()

    if not snapshot.recent_events:
        content.append("No events yet", style="dim")
    else:
        # Show most recent events
        events_to_show = snapshot.recent_events[-max_events:]

        for i, event in enumerate(events_to_show):
            if i > 0:
                content.append("\n")
            content.append_text(render_event(event))

    return Panel(
        content,
        border_style="dim",
        padding=(0, 1),
        title="Recent Events",
        title_align="left",
    )
