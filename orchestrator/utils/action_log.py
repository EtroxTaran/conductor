"""Unified action log for workflow observability.

Provides a single, append-only log of all significant workflow actions
with real-time console output and queryable persistence.
"""

import json
import sys
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any


class ActionType(str, Enum):
    """Types of actions that can be logged."""
    # Workflow level
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    WORKFLOW_PAUSE = "workflow_pause"
    WORKFLOW_RESUME = "workflow_resume"

    # Phase level
    PHASE_START = "phase_start"
    PHASE_COMPLETE = "phase_complete"
    PHASE_FAILED = "phase_failed"
    PHASE_RETRY = "phase_retry"

    # Agent level
    AGENT_INVOKE = "agent_invoke"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"
    AGENT_TIMEOUT = "agent_timeout"

    # Task level
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    TASK_BLOCKED = "task_blocked"
    TASK_SKIPPED = "task_skipped"

    # Validation/Verification
    VALIDATION_PASS = "validation_pass"
    VALIDATION_FAIL = "validation_fail"
    VERIFICATION_PASS = "verification_pass"
    VERIFICATION_FAIL = "verification_fail"

    # Human interaction
    ESCALATION = "escalation"
    HUMAN_INPUT = "human_input"
    CLARIFICATION_REQUEST = "clarification_request"
    CLARIFICATION_RESPONSE = "clarification_response"

    # Git operations
    GIT_COMMIT = "git_commit"
    GIT_ROLLBACK = "git_rollback"

    # System
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    CHECKPOINT = "checkpoint"


class ActionStatus(str, Enum):
    """Status of an action."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


@dataclass
class ErrorInfo:
    """Structured error information."""
    error_type: str
    message: str
    stack_trace: Optional[str] = None
    context: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "context": self.context,
        }

    @classmethod
    def from_exception(cls, exc: Exception, context: Optional[dict] = None) -> "ErrorInfo":
        """Create ErrorInfo from an exception."""
        import traceback
        return cls(
            error_type=type(exc).__name__,
            message=str(exc),
            stack_trace=traceback.format_exc(),
            context=context,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorInfo":
        return cls(**data)


@dataclass
class ActionEntry:
    """A single action log entry."""
    id: str
    timestamp: str
    action_type: ActionType
    message: str
    status: ActionStatus = ActionStatus.COMPLETED
    phase: Optional[int] = None
    agent: Optional[str] = None
    task_id: Optional[str] = None
    details: Optional[dict] = None
    error: Optional[ErrorInfo] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action_type": self.action_type.value,
            "message": self.message,
            "status": self.status.value,
            "phase": self.phase,
            "agent": self.agent,
            "task_id": self.task_id,
            "details": self.details,
            "error": self.error.to_dict() if self.error else None,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionEntry":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            action_type=ActionType(data["action_type"]),
            message=data["message"],
            status=ActionStatus(data.get("status", "completed")),
            phase=data.get("phase"),
            agent=data.get("agent"),
            task_id=data.get("task_id"),
            details=data.get("details"),
            error=ErrorInfo.from_dict(data["error"]) if data.get("error") else None,
            duration_ms=data.get("duration_ms"),
        )


# ANSI color codes for console output
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    "gray": "\033[90m",
}

# Status symbols
SYMBOLS = {
    ActionStatus.STARTED: ("▶", "blue"),
    ActionStatus.COMPLETED: ("✓", "green"),
    ActionStatus.FAILED: ("✗", "red"),
    ActionStatus.SKIPPED: ("⊘", "gray"),
    ActionStatus.PENDING: ("○", "yellow"),
}

# Action type formatting
ACTION_COLORS = {
    ActionType.WORKFLOW_START: "cyan",
    ActionType.WORKFLOW_END: "cyan",
    ActionType.PHASE_START: "blue",
    ActionType.PHASE_COMPLETE: "green",
    ActionType.PHASE_FAILED: "red",
    ActionType.AGENT_INVOKE: "magenta",
    ActionType.AGENT_COMPLETE: "green",
    ActionType.AGENT_ERROR: "red",
    ActionType.TASK_START: "blue",
    ActionType.TASK_COMPLETE: "green",
    ActionType.TASK_FAILED: "red",
    ActionType.ERROR: "red",
    ActionType.WARNING: "yellow",
    ActionType.ESCALATION: "yellow",
}


class ActionLog:
    """Unified action log for workflow observability.

    Thread-safe, append-only log with real-time console output
    and queryable persistence.
    """

    def __init__(
        self,
        workflow_dir: str | Path,
        console_output: bool = True,
        console_colors: bool = True,
    ):
        """Initialize the action log.

        Args:
            workflow_dir: Directory for log storage (.workflow/)
            console_output: Whether to output to console in real-time
            console_colors: Whether to use ANSI colors in console output
        """
        self.workflow_dir = Path(workflow_dir)
        self.log_file = self.workflow_dir / "action_log.jsonl"
        self.index_file = self.workflow_dir / "action_log_index.json"
        self.console_output = console_output
        self.console_colors = console_colors
        self._lock = threading.Lock()
        self._index: dict = {"total": 0, "by_phase": {}, "by_agent": {}, "errors": 0}
        self._ensure_dir()
        self._load_index()

    def _ensure_dir(self) -> None:
        """Ensure workflow directory exists."""
        self.workflow_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        """Load index from file if it exists."""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # Start with empty index

    def _save_index(self) -> None:
        """Save index to file."""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def _update_index(self, entry: ActionEntry) -> None:
        """Update the index with a new entry."""
        self._index["total"] += 1

        if entry.phase is not None:
            phase_key = str(entry.phase)
            self._index["by_phase"][phase_key] = self._index["by_phase"].get(phase_key, 0) + 1

        if entry.agent:
            self._index["by_agent"][entry.agent] = self._index["by_agent"].get(entry.agent, 0) + 1

        if entry.error or entry.status == ActionStatus.FAILED:
            self._index["errors"] += 1

        self._index["last_updated"] = datetime.now().isoformat()
        self._save_index()

    def _format_console(self, entry: ActionEntry) -> str:
        """Format entry for console output with colors."""
        timestamp = datetime.fromisoformat(entry.timestamp).strftime("%H:%M:%S")

        if self.console_colors:
            # Get status symbol and color
            symbol, symbol_color = SYMBOLS.get(entry.status, ("•", "white"))
            action_color = ACTION_COLORS.get(entry.action_type, "white")

            parts = [f"{COLORS['gray']}[{timestamp}]{COLORS['reset']}"]

            if entry.phase is not None:
                parts.append(f"{COLORS['cyan']}[P{entry.phase}]{COLORS['reset']}")

            if entry.agent:
                parts.append(f"{COLORS['magenta']}[{entry.agent}]{COLORS['reset']}")

            if entry.task_id:
                parts.append(f"{COLORS['blue']}[{entry.task_id}]{COLORS['reset']}")

            parts.append(f"{COLORS[symbol_color]}{symbol}{COLORS['reset']}")
            parts.append(f"{COLORS[action_color]}{entry.message}{COLORS['reset']}")

            if entry.duration_ms is not None:
                parts.append(f"{COLORS['gray']}({entry.duration_ms:.0f}ms){COLORS['reset']}")

            return " ".join(parts)
        else:
            # Plain text format
            parts = [f"[{timestamp}]"]

            if entry.phase is not None:
                parts.append(f"[P{entry.phase}]")

            if entry.agent:
                parts.append(f"[{entry.agent}]")

            if entry.task_id:
                parts.append(f"[{entry.task_id}]")

            symbol, _ = SYMBOLS.get(entry.status, ("•", "white"))
            parts.append(symbol)
            parts.append(entry.message)

            if entry.duration_ms is not None:
                parts.append(f"({entry.duration_ms:.0f}ms)")

            return " ".join(parts)

    def log(
        self,
        action_type: ActionType,
        message: str,
        status: ActionStatus = ActionStatus.COMPLETED,
        phase: Optional[int] = None,
        agent: Optional[str] = None,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
        error: Optional[ErrorInfo] = None,
        duration_ms: Optional[float] = None,
    ) -> ActionEntry:
        """Log an action.

        Args:
            action_type: Type of action
            message: Human-readable message
            status: Action status
            phase: Phase number (1-5)
            agent: Agent name (claude, cursor, gemini)
            task_id: Task identifier
            details: Additional structured data
            error: Error information if failed
            duration_ms: Duration in milliseconds

        Returns:
            The created ActionEntry
        """
        entry = ActionEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            action_type=action_type,
            message=message,
            status=status,
            phase=phase,
            agent=agent,
            task_id=task_id,
            details=details,
            error=error,
            duration_ms=duration_ms,
        )

        with self._lock:
            # Append to log file
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

            # Update index
            self._update_index(entry)

            # Console output
            if self.console_output:
                formatted = self._format_console(entry)
                output = sys.stderr if entry.status == ActionStatus.FAILED else sys.stdout
                print(formatted, file=output)

        return entry

    def get_recent(self, limit: int = 20) -> list[ActionEntry]:
        """Get the most recent log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of ActionEntry objects (newest first)
        """
        entries = []
        if not self.log_file.exists():
            return entries

        with self._lock:
            # Read all lines and take the last N
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in reversed(lines[-limit:]):
                if line.strip():
                    try:
                        data = json.loads(line)
                        entries.append(ActionEntry.from_dict(data))
                    except json.JSONDecodeError:
                        continue

        return entries

    def get_errors(self, since: Optional[str] = None) -> list[ActionEntry]:
        """Get all error entries.

        Args:
            since: ISO timestamp to filter errors after

        Returns:
            List of error ActionEntry objects
        """
        errors = []
        if not self.log_file.exists():
            return errors

        with self._lock:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            # Check if it's an error
                            if (
                                data.get("error")
                                or data.get("status") == "failed"
                                or data.get("action_type") in ["error", "agent_error", "phase_failed", "task_failed"]
                            ):
                                # Filter by timestamp if provided
                                if since and data.get("timestamp", "") < since:
                                    continue
                                errors.append(ActionEntry.from_dict(data))
                        except json.JSONDecodeError:
                            continue

        return errors

    def get_by_phase(self, phase: int) -> list[ActionEntry]:
        """Get all entries for a specific phase.

        Args:
            phase: Phase number (1-5)

        Returns:
            List of ActionEntry objects for the phase
        """
        entries = []
        if not self.log_file.exists():
            return entries

        with self._lock:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if data.get("phase") == phase:
                                entries.append(ActionEntry.from_dict(data))
                        except json.JSONDecodeError:
                            continue

        return entries

    def get_by_agent(self, agent: str) -> list[ActionEntry]:
        """Get all entries for a specific agent.

        Args:
            agent: Agent name (claude, cursor, gemini)

        Returns:
            List of ActionEntry objects for the agent
        """
        entries = []
        if not self.log_file.exists():
            return entries

        with self._lock:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if data.get("agent") == agent:
                                entries.append(ActionEntry.from_dict(data))
                        except json.JSONDecodeError:
                            continue

        return entries

    def get_by_task(self, task_id: str) -> list[ActionEntry]:
        """Get all entries for a specific task.

        Args:
            task_id: Task identifier

        Returns:
            List of ActionEntry objects for the task
        """
        entries = []
        if not self.log_file.exists():
            return entries

        with self._lock:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if data.get("task_id") == task_id:
                                entries.append(ActionEntry.from_dict(data))
                        except json.JSONDecodeError:
                            continue

        return entries

    def get_summary(self) -> dict:
        """Get a summary of the action log.

        Returns:
            Dictionary with summary statistics
        """
        with self._lock:
            return {
                "total_actions": self._index.get("total", 0),
                "actions_by_phase": self._index.get("by_phase", {}),
                "actions_by_agent": self._index.get("by_agent", {}),
                "error_count": self._index.get("errors", 0),
                "last_updated": self._index.get("last_updated"),
            }

    def clear(self) -> None:
        """Clear the action log (for testing/reset)."""
        with self._lock:
            if self.log_file.exists():
                self.log_file.unlink()
            self._index = {"total": 0, "by_phase": {}, "by_agent": {}, "errors": 0}
            self._save_index()


# Global action log instance
_action_log: Optional[ActionLog] = None


def get_action_log(workflow_dir: Optional[str | Path] = None) -> ActionLog:
    """Get or create the global action log instance.

    Args:
        workflow_dir: Workflow directory (defaults to .workflow/)

    Returns:
        ActionLog instance
    """
    global _action_log

    if _action_log is None:
        workflow_dir = workflow_dir or Path(".workflow")
        _action_log = ActionLog(workflow_dir)

    return _action_log


def reset_action_log() -> None:
    """Reset the global action log instance."""
    global _action_log
    _action_log = None
