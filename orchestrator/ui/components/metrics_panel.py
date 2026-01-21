"""Metrics panel component.

Displays token count, cost, and file change statistics.
"""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..state_adapter import UIStateSnapshot


def format_tokens(tokens: int) -> str:
    """Format token count with K/M suffix.

    Args:
        tokens: Raw token count

    Returns:
        Formatted string (e.g., "45.2k", "1.2M")
    """
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}k"
    else:
        return str(tokens)


def format_cost(cost: float) -> str:
    """Format cost in dollars.

    Args:
        cost: Cost in dollars

    Returns:
        Formatted string (e.g., "$1.23", "$12.34")
    """
    if cost >= 100:
        return f"${cost:.0f}"
    elif cost >= 10:
        return f"${cost:.1f}"
    else:
        return f"${cost:.2f}"


def render_metrics_panel(snapshot: UIStateSnapshot) -> Panel:
    """Render the metrics panel.

    Displays in a compact horizontal format:
    - Token count
    - Cost
    - Files created/modified

    Args:
        snapshot: Current UI state snapshot

    Returns:
        Rich Panel renderable
    """
    table = Table.grid(expand=True)
    table.add_column(justify="left", ratio=1)
    table.add_column(justify="center", ratio=1)
    table.add_column(justify="right", ratio=1)

    # Tokens
    tokens_text = Text()
    tokens_text.append("\U0001f4b0 ", style="")  # Money bag emoji
    tokens_text.append("Tokens: ", style="dim")
    tokens_text.append(format_tokens(snapshot.tokens), style="bold")

    # Cost
    cost_text = Text()
    cost_text.append("Cost: ", style="dim")
    cost_text.append(format_cost(snapshot.cost), style="bold green")

    # Files
    files_text = Text()
    files_text.append("Files: ", style="dim")
    if snapshot.files_created > 0:
        files_text.append(f"+{snapshot.files_created}", style="green bold")
    else:
        files_text.append("+0", style="dim")
    files_text.append(" ")
    if snapshot.files_modified > 0:
        files_text.append(f"~{snapshot.files_modified}", style="yellow bold")
    else:
        files_text.append("~0", style="dim")

    table.add_row(tokens_text, cost_text, files_text)

    return Panel(
        table,
        border_style="dim",
        padding=(0, 1),
    )
