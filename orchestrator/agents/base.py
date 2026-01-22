"""Base agent class for CLI wrappers with audit trail integration."""

import json
import logging
import subprocess
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default timeouts by phase (in seconds)
PHASE_TIMEOUTS = {
    1: 900,   # Planning: 15 minutes
    2: 600,   # Validation: 10 minutes
    3: 1800,  # Implementation: 30 minutes
    4: 600,   # Verification: 10 minutes
    5: 300,   # Completion: 5 minutes
}


@dataclass
class AgentResult:
    """Result from an agent execution.

    Attributes:
        success: Whether the execution succeeded
        output: Raw stdout output
        parsed_output: Parsed JSON output if available
        error: Error message if failed
        exit_code: Process exit code
        duration_seconds: Execution duration
        session_id: Session ID if using session continuity
        cost_usd: Estimated cost if available
        model: Model used if known
    """

    success: bool
    output: Optional[str] = None
    parsed_output: Optional[dict] = None
    error: Optional[str] = None
    exit_code: int = 0
    duration_seconds: float = 0.0
    session_id: Optional[str] = None
    cost_usd: Optional[float] = None
    model: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "parsed_output": self.parsed_output,
            "error": self.error,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "session_id": self.session_id,
            "cost_usd": self.cost_usd,
            "model": self.model,
        }


class BaseAgent(ABC):
    """Base class for CLI agent wrappers.

    Provides common functionality for all CLI agent wrappers:
    - Command building and execution
    - Timeout management
    - Output parsing
    - Audit trail integration (optional)
    """

    name: str = "base"

    def __init__(
        self,
        project_dir: str | Path,
        timeout: int = 300,
        phase_timeouts: Optional[dict[int, int]] = None,
        enable_audit: bool = True,
    ):
        """Initialize the agent.

        Args:
            project_dir: Root directory of the project
            timeout: Default timeout in seconds for command execution
            phase_timeouts: Optional per-phase timeout overrides
            enable_audit: Whether to enable audit trail logging
        """
        self.project_dir = Path(project_dir)
        self.timeout = timeout
        self.phase_timeouts = phase_timeouts or PHASE_TIMEOUTS.copy()
        self.enable_audit = enable_audit

        # Lazily initialized audit trail
        self._audit_trail = None

    @property
    def audit_trail(self):
        """Get or create the audit trail."""
        if self._audit_trail is None and self.enable_audit:
            try:
                from ..audit import get_project_audit_trail
                self._audit_trail = get_project_audit_trail(self.project_dir)
            except ImportError:
                logger.debug("Audit trail not available")
        return self._audit_trail

    @abstractmethod
    def build_command(self, prompt: str, **kwargs) -> list[str]:
        """Build the CLI command to execute.

        Args:
            prompt: The prompt to send to the agent
            **kwargs: Additional arguments

        Returns:
            Command as list of strings
        """
        pass

    def get_timeout_for_phase(self, phase_num: Optional[int] = None) -> int:
        """Get the timeout for a specific phase.

        Args:
            phase_num: Phase number (1-5), or None for default timeout

        Returns:
            Timeout in seconds
        """
        if phase_num is not None and phase_num in self.phase_timeouts:
            return self.phase_timeouts[phase_num]
        return self.timeout

    def run(
        self,
        prompt: str,
        output_file: Optional[Path] = None,
        phase: Optional[int] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs,
    ) -> AgentResult:
        """Execute the agent with the given prompt.

        Args:
            prompt: The prompt to send to the agent
            output_file: Optional file to write output to
            phase: Optional phase number for phase-specific timeout
            task_id: Optional task ID for audit trail
            session_id: Optional session ID for continuity
            **kwargs: Additional arguments passed to build_command

        Returns:
            AgentResult with execution details
        """
        command = self.build_command(prompt, **kwargs)
        start_time = time.time()
        timeout = self.get_timeout_for_phase(phase)

        # Start audit entry if enabled
        audit_entry = None
        if self.audit_trail and task_id:
            audit_entry = self.audit_trail.start_entry(
                agent=self.name,
                task_id=task_id,
                prompt=prompt,
                session_id=session_id,
                command=command,
                metadata={"phase": phase, **{k: str(v)[:100] for k, v in kwargs.items() if v}},
            )

        try:
            result = subprocess.run(
                command,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "TERM": "dumb"},
            )

            duration = time.time() - start_time
            output = result.stdout
            stderr = result.stderr

            # Try to parse JSON output
            parsed_output = None
            if output:
                try:
                    parsed_output = json.loads(output)
                except json.JSONDecodeError:
                    # Output is not JSON, that's fine
                    pass

            # Write to output file if specified
            if output_file and output:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "w") as f:
                    if parsed_output:
                        json.dump(parsed_output, f, indent=2)
                    else:
                        f.write(output)

            # Extract additional info from parsed output
            cost_usd = None
            model = None
            if parsed_output:
                cost_usd = parsed_output.get("cost_usd") or parsed_output.get("usage", {}).get("cost_usd")
                model = parsed_output.get("model")

            if result.returncode != 0:
                agent_result = AgentResult(
                    success=False,
                    output=output,
                    parsed_output=parsed_output,
                    error=stderr or f"Exit code: {result.returncode}",
                    exit_code=result.returncode,
                    duration_seconds=duration,
                    session_id=session_id,
                    cost_usd=cost_usd,
                    model=model,
                )

                # Record in audit trail
                if audit_entry:
                    audit_entry.set_result(
                        success=False,
                        exit_code=result.returncode,
                        output=output,
                        error=stderr,
                        parsed_output=parsed_output,
                        cost_usd=cost_usd,
                    )
                    self.audit_trail.commit_entry(audit_entry)

                return agent_result

            agent_result = AgentResult(
                success=True,
                output=output,
                parsed_output=parsed_output,
                exit_code=result.returncode,
                duration_seconds=duration,
                session_id=session_id,
                cost_usd=cost_usd,
                model=model,
            )

            # Record in audit trail
            if audit_entry:
                audit_entry.set_result(
                    success=True,
                    exit_code=result.returncode,
                    output=output,
                    error=stderr,
                    parsed_output=parsed_output,
                    cost_usd=cost_usd,
                )
                self.audit_trail.commit_entry(audit_entry)

            return agent_result

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time

            if audit_entry:
                audit_entry.set_timeout(duration)
                self.audit_trail.commit_entry(audit_entry)

            return AgentResult(
                success=False,
                error=f"Command timed out after {timeout} seconds",
                exit_code=-1,
                duration_seconds=duration,
            )

        except FileNotFoundError as e:
            cli_cmd = self.get_cli_command()
            error_msg = f"CLI not found: {cli_cmd}. Is it installed? Error: {e}"

            if audit_entry:
                audit_entry.set_error(error_msg)
                self.audit_trail.commit_entry(audit_entry)

            return AgentResult(
                success=False,
                error=error_msg,
                exit_code=-1,
                duration_seconds=0,
            )

        except PermissionError as e:
            cli_cmd = self.get_cli_command()
            error_msg = f"Permission denied executing {cli_cmd}: {e}"

            if audit_entry:
                audit_entry.set_error(error_msg)
                self.audit_trail.commit_entry(audit_entry)

            return AgentResult(
                success=False,
                error=error_msg,
                exit_code=-1,
                duration_seconds=0,
            )

        except OSError as e:
            cli_cmd = self.get_cli_command()
            error_msg = f"OS error executing {cli_cmd}: {e}"
            duration = time.time() - start_time

            if audit_entry:
                audit_entry.set_error(error_msg)
                self.audit_trail.commit_entry(audit_entry)

            return AgentResult(
                success=False,
                error=error_msg,
                exit_code=-1,
                duration_seconds=duration,
            )

        except Exception as e:
            # Log unexpected exceptions for debugging
            cli_cmd = self.get_cli_command()
            error_msg = f"Unexpected error: {type(e).__name__}: {e}"
            duration = time.time() - start_time
            logger.error(f"Unexpected error in {cli_cmd}: {type(e).__name__}: {e}")

            if audit_entry:
                audit_entry.set_error(error_msg)
                self.audit_trail.commit_entry(audit_entry)

            return AgentResult(
                success=False,
                error=error_msg,
                exit_code=-1,
                duration_seconds=duration,
            )

    def check_available(self) -> bool:
        """Check if the CLI tool is available."""
        try:
            result = subprocess.run(
                [self.get_cli_command(), "--version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @abstractmethod
    def get_cli_command(self) -> str:
        """Get the main CLI command name."""
        pass

    def get_context_file(self) -> Optional[Path]:
        """Get the context file path for this agent."""
        return None

    def read_context_file(self) -> Optional[str]:
        """Read the context file content if it exists."""
        context_file = self.get_context_file()
        if context_file and context_file.exists():
            return context_file.read_text()
        return None
