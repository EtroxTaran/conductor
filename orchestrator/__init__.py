"""Multi-Agent Orchestration System.

Coordinates Claude Code, Cursor CLI, and Gemini CLI through a 5-phase workflow.
"""

from .orchestrator import Orchestrator

__version__ = "0.1.0"

__all__ = ["Orchestrator", "__version__"]
