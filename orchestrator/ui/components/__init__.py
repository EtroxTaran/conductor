"""Rich UI components for workflow display.

Each component is a function that returns a Rich renderable
based on the current UIStateSnapshot.
"""

from .header import render_header
from .phase_bar import render_phase_bar
from .task_tree import render_task_tree
from .metrics_panel import render_metrics_panel
from .event_log import render_event_log

__all__ = [
    "render_header",
    "render_phase_bar",
    "render_task_tree",
    "render_metrics_panel",
    "render_event_log",
]
