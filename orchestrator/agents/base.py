"""Base agent class for CLI wrappers."""

import json
import subprocess
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


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
    """Result from an agent execution."""
    success: bool
    output: Optional[str] = None
    parsed_output: Optional[dict] = None
    error: Optional[str] = None
    exit_code: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "parsed_output": self.parsed_output,
            "error": self.error,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
        }


class BaseAgent(ABC):
    """Base class for CLI agent wrappers."""

    name: str = "base"

    def __init__(
        self,
        project_dir: str | Path,
        timeout: int = 300,
        phase_timeouts: Optional[dict[int, int]] = None,
    ):
        """Initialize the agent.

        Args:
            project_dir: Root directory of the project
            timeout: Default timeout in seconds for command execution
            phase_timeouts: Optional per-phase timeout overrides
        """
        self.project_dir = Path(project_dir)
        self.timeout = timeout
        self.phase_timeouts = phase_timeouts or PHASE_TIMEOUTS.copy()

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
        **kwargs,
    ) -> AgentResult:
        """Execute the agent with the given prompt.

        Args:
            prompt: The prompt to send to the agent
            output_file: Optional file to write output to
            phase: Optional phase number for phase-specific timeout
            **kwargs: Additional arguments passed to build_command

        Returns:
            AgentResult with execution details
        """
        import time

        command = self.build_command(prompt, **kwargs)
        start_time = time.time()
        timeout = self.get_timeout_for_phase(phase)

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

            if result.returncode != 0:
                return AgentResult(
                    success=False,
                    output=output,
                    parsed_output=parsed_output,
                    error=result.stderr or f"Exit code: {result.returncode}",
                    exit_code=result.returncode,
                    duration_seconds=duration,
                )

            return AgentResult(
                success=True,
                output=output,
                parsed_output=parsed_output,
                exit_code=result.returncode,
                duration_seconds=duration,
            )

        except subprocess.TimeoutExpired:
            return AgentResult(
                success=False,
                error=f"Command timed out after {timeout} seconds",
                exit_code=-1,
                duration_seconds=timeout,
            )
        except FileNotFoundError as e:
            cli_cmd = self.get_cli_command()
            return AgentResult(
                success=False,
                error=f"CLI not found: {cli_cmd}. Is it installed? Error: {e}",
                exit_code=-1,
                duration_seconds=0,
            )
        except PermissionError as e:
            cli_cmd = self.get_cli_command()
            return AgentResult(
                success=False,
                error=f"Permission denied executing {cli_cmd}: {e}",
                exit_code=-1,
                duration_seconds=0,
            )
        except OSError as e:
            cli_cmd = self.get_cli_command()
            return AgentResult(
                success=False,
                error=f"OS error executing {cli_cmd}: {e}",
                exit_code=-1,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            # Log unexpected exceptions for debugging
            import logging
            cli_cmd = self.get_cli_command()
            logging.error(f"Unexpected error in {cli_cmd}: {type(e).__name__}: {e}")
            return AgentResult(
                success=False,
                error=f"Unexpected error: {type(e).__name__}: {e}",
                exit_code=-1,
                duration_seconds=time.time() - start_time,
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
