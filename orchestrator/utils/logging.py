"""Logging utilities for the orchestration workflow."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from enum import Enum


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    PHASE = "PHASE"
    AGENT = "AGENT"


# ANSI color codes
COLORS = {
    LogLevel.DEBUG: "\033[90m",      # Gray
    LogLevel.INFO: "\033[37m",       # White
    LogLevel.WARNING: "\033[93m",    # Yellow
    LogLevel.ERROR: "\033[91m",      # Red
    LogLevel.SUCCESS: "\033[92m",    # Green
    LogLevel.PHASE: "\033[96m",      # Cyan
    LogLevel.AGENT: "\033[95m",      # Magenta
}
RESET = "\033[0m"
BOLD = "\033[1m"


class OrchestrationLogger:
    """Logger for multi-agent orchestration."""

    def __init__(
        self,
        workflow_dir: str | Path,
        console_output: bool = True,
        min_level: LogLevel = LogLevel.INFO,
    ):
        """Initialize the logger.

        Args:
            workflow_dir: Directory for log files
            console_output: Whether to print to console
            min_level: Minimum log level to record
        """
        self.workflow_dir = Path(workflow_dir)
        self.log_file = self.workflow_dir / "coordination.log"
        self.json_log_file = self.workflow_dir / "coordination.jsonl"
        self.console_output = console_output
        self.min_level = min_level
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        """Ensure log directory exists."""
        self.workflow_dir.mkdir(parents=True, exist_ok=True)

    def _get_level_priority(self, level: LogLevel) -> int:
        """Get numeric priority for log level."""
        priorities = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.SUCCESS: 1,
            LogLevel.PHASE: 1,
            LogLevel.AGENT: 1,
        }
        return priorities.get(level, 1)

    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on level."""
        return self._get_level_priority(level) >= self._get_level_priority(self.min_level)

    def _format_console(
        self,
        level: LogLevel,
        message: str,
        phase: Optional[int] = None,
        agent: Optional[str] = None,
    ) -> str:
        """Format message for console output with colors."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = COLORS.get(level, "")

        parts = [f"{COLORS[LogLevel.DEBUG]}[{timestamp}]{RESET}"]

        if phase is not None:
            parts.append(f"{COLORS[LogLevel.PHASE]}[P{phase}]{RESET}")

        if agent:
            parts.append(f"{COLORS[LogLevel.AGENT]}[{agent}]{RESET}")

        parts.append(f"{color}[{level.value}]{RESET}")
        parts.append(message)

        return " ".join(parts)

    def _format_file(
        self,
        level: LogLevel,
        message: str,
        phase: Optional[int] = None,
        agent: Optional[str] = None,
    ) -> str:
        """Format message for file output (plain text)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = [f"[{timestamp}]"]

        if phase is not None:
            parts.append(f"[P{phase}]")

        if agent:
            parts.append(f"[{agent}]")

        parts.append(f"[{level.value}]")
        parts.append(message)

        return " ".join(parts)

    def _format_json(
        self,
        level: LogLevel,
        message: str,
        phase: Optional[int] = None,
        agent: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """Format message as JSON."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "message": message,
        }

        if phase is not None:
            entry["phase"] = phase

        if agent:
            entry["agent"] = agent

        if extra:
            entry["extra"] = extra

        return entry

    def log(
        self,
        level: LogLevel,
        message: str,
        phase: Optional[int] = None,
        agent: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """Log a message.

        Args:
            level: Log level
            message: Message to log
            phase: Phase number (1-5)
            agent: Agent name (claude, cursor, gemini)
            extra: Additional structured data
        """
        if not self._should_log(level):
            return

        # Console output
        if self.console_output:
            formatted = self._format_console(level, message, phase, agent)
            print(formatted, file=sys.stderr if level == LogLevel.ERROR else sys.stdout)

        # File output (plain text)
        with open(self.log_file, "a") as f:
            formatted = self._format_file(level, message, phase, agent)
            f.write(formatted + "\n")

        # JSON log
        with open(self.json_log_file, "a") as f:
            entry = self._format_json(level, message, phase, agent, extra)
            f.write(json.dumps(entry) + "\n")

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self.log(LogLevel.ERROR, message, **kwargs)

    def success(self, message: str, **kwargs) -> None:
        """Log success message."""
        self.log(LogLevel.SUCCESS, message, **kwargs)

    def phase_start(self, phase_num: int, phase_name: str) -> None:
        """Log phase start."""
        self.log(
            LogLevel.PHASE,
            f"{'='*50}",
        )
        self.log(
            LogLevel.PHASE,
            f"Starting Phase {phase_num}: {phase_name.upper()}",
            phase=phase_num,
        )
        self.log(
            LogLevel.PHASE,
            f"{'='*50}",
        )

    def phase_complete(self, phase_num: int, phase_name: str) -> None:
        """Log phase completion."""
        self.log(
            LogLevel.SUCCESS,
            f"Phase {phase_num} ({phase_name}) completed successfully",
            phase=phase_num,
        )

    def phase_failed(self, phase_num: int, phase_name: str, error: str) -> None:
        """Log phase failure."""
        self.log(
            LogLevel.ERROR,
            f"Phase {phase_num} ({phase_name}) failed: {error}",
            phase=phase_num,
        )

    def agent_start(self, agent: str, task: str, phase: Optional[int] = None) -> None:
        """Log agent task start."""
        self.log(
            LogLevel.AGENT,
            f"Agent starting: {task}",
            phase=phase,
            agent=agent,
        )

    def agent_complete(self, agent: str, task: str, phase: Optional[int] = None) -> None:
        """Log agent task completion."""
        self.log(
            LogLevel.SUCCESS,
            f"Agent completed: {task}",
            phase=phase,
            agent=agent,
        )

    def agent_error(self, agent: str, error: str, phase: Optional[int] = None) -> None:
        """Log agent error."""
        self.log(
            LogLevel.ERROR,
            f"Agent error: {error}",
            phase=phase,
            agent=agent,
        )

    def retry(self, phase_num: int, attempt: int, max_attempts: int) -> None:
        """Log retry attempt."""
        self.log(
            LogLevel.WARNING,
            f"Retrying phase (attempt {attempt}/{max_attempts})",
            phase=phase_num,
        )

    def commit(self, phase_num: int, commit_hash: str, message: str) -> None:
        """Log git commit."""
        self.log(
            LogLevel.SUCCESS,
            f"Committed: {commit_hash[:8]} - {message}",
            phase=phase_num,
            extra={"commit_hash": commit_hash, "commit_message": message},
        )

    def separator(self) -> None:
        """Print a visual separator."""
        if self.console_output:
            print("-" * 60)

    def banner(self, text: str) -> None:
        """Print a banner message."""
        if self.console_output:
            print()
            print(f"{BOLD}{COLORS[LogLevel.PHASE]}{'='*60}{RESET}")
            print(f"{BOLD}{COLORS[LogLevel.PHASE]}{text.center(60)}{RESET}")
            print(f"{BOLD}{COLORS[LogLevel.PHASE]}{'='*60}{RESET}")
            print()
