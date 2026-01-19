"""Base agent class for CLI wrappers."""

import json
import subprocess
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


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
    ):
        """Initialize the agent.

        Args:
            project_dir: Root directory of the project
            timeout: Timeout in seconds for command execution
        """
        self.project_dir = Path(project_dir)
        self.timeout = timeout

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

    def run(
        self,
        prompt: str,
        output_file: Optional[Path] = None,
        **kwargs,
    ) -> AgentResult:
        """Execute the agent with the given prompt.

        Args:
            prompt: The prompt to send to the agent
            output_file: Optional file to write output to
            **kwargs: Additional arguments passed to build_command

        Returns:
            AgentResult with execution details
        """
        import time

        command = self.build_command(prompt, **kwargs)
        start_time = time.time()

        try:
            result = subprocess.run(
                command,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
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
                error=f"Command timed out after {self.timeout} seconds",
                exit_code=-1,
                duration_seconds=self.timeout,
            )
        except FileNotFoundError as e:
            return AgentResult(
                success=False,
                error=f"Command not found: {e}",
                exit_code=-1,
                duration_seconds=0,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"Execution error: {str(e)}",
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
