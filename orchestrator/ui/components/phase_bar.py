"""Phase progress bar component.

Displays current workflow phase with progress bar.
"""

from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

from ..state_adapter import UIStateSnapshot


def render_phase_bar(snapshot: UIStateSnapshot) -> Panel:
    """Render the phase progress bar.

    Displays:
    - Current phase (e.g., "Phase 3/5: Implementation")
    - Progress bar showing overall workflow progress
    - Percentage complete

    Args:
        snapshot: Current UI state snapshot

    Returns:
        Rich Panel renderable
    """
    table = Table.grid(expand=True)
    table.add_column(ratio=1)

    # Phase text
    phase_text = Text()
    phase_text.append(f"Phase {snapshot.current_phase}/{snapshot.total_phases}: ", style="bold")
    phase_text.append(snapshot.phase_name, style="cyan")

    # Progress bar using Rich's built-in progress bar rendering
    progress_pct = int(snapshot.phase_progress * 100)
    bar_width = 40
    filled = int(bar_width * snapshot.phase_progress)
    empty = bar_width - filled

    bar_text = Text()
    bar_text.append("[")
    bar_text.append("=" * filled, style="green")
    if filled < bar_width:
        bar_text.append(">", style="green")
        bar_text.append(" " * (empty - 1) if empty > 0 else "")
    bar_text.append("]")
    bar_text.append(f" {progress_pct}%", style="bold white")

    # Add phase indicators
    phase_indicators = Text()
    for i in range(1, snapshot.total_phases + 1):
        if i < snapshot.current_phase:
            phase_indicators.append(f"[{i}]", style="green")
        elif i == snapshot.current_phase:
            phase_indicators.append(f"[{i}]", style="cyan bold")
        else:
            phase_indicators.append(f"[{i}]", style="dim")
        if i < snapshot.total_phases:
            phase_indicators.append(" ")

    table.add_row(phase_text)
    table.add_row(bar_text)
    table.add_row(phase_indicators)

    return Panel(
        table,
        border_style="blue",
        padding=(0, 1),
    )
