"""Claude Code CLI agent wrapper."""

from pathlib import Path
from typing import Optional

from .base import BaseAgent


class ClaudeAgent(BaseAgent):
    """Wrapper for Claude Code CLI.

    Claude Code is used for planning and implementation phases.
    It reads context from CLAUDE.md and .claude/system.md.
    """

    name = "claude"

    def __init__(
        self,
        project_dir: str | Path,
        timeout: int = 600,
        allowed_tools: Optional[list[str]] = None,
        system_prompt_file: Optional[str] = None,
    ):
        """Initialize Claude agent.

        Args:
            project_dir: Root directory of the project
            timeout: Timeout in seconds (default 10 minutes for complex tasks)
            allowed_tools: List of allowed tool patterns
            system_prompt_file: Path to system prompt file relative to project
        """
        super().__init__(project_dir, timeout)
        self.allowed_tools = allowed_tools or [
            "Bash(git*)",
            "Bash(npm*)",
            "Bash(pytest*)",
            "Read",
            "Write",
            "Edit",
            "Glob",
            "Grep",
        ]
        self.system_prompt_file = system_prompt_file

    def get_cli_command(self) -> str:
        """Get the CLI command."""
        return "claude"

    def get_context_file(self) -> Optional[Path]:
        """Get Claude's context file."""
        return self.project_dir / "CLAUDE.md"

    def build_command(
        self,
        prompt: str,
        output_format: str = "json",
        max_turns: Optional[int] = None,
        **kwargs,
    ) -> list[str]:
        """Build the Claude CLI command.

        Args:
            prompt: The prompt to send
            output_format: Output format (json, text, stream-json)
            max_turns: Maximum number of agentic turns
            **kwargs: Additional arguments (ignored)

        Returns:
            Command as list of strings
        """
        command = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            output_format,
        ]

        # Add system prompt file if specified
        if self.system_prompt_file:
            system_path = self.project_dir / self.system_prompt_file
            if system_path.exists():
                command.extend([
                    "--append-system-prompt-file",
                    str(system_path),
                ])

        # Add allowed tools
        if self.allowed_tools:
            tools_str = ",".join(self.allowed_tools)
            command.extend(["--allowedTools", tools_str])

        # Add max turns if specified
        if max_turns:
            command.extend(["--max-turns", str(max_turns)])

        return command

    def run_planning(
        self,
        product_spec: str,
        output_file: Optional[Path] = None,
    ):
        """Run Claude for planning phase.

        Args:
            product_spec: Content of PRODUCT.md
            output_file: File to write plan to

        Returns:
            AgentResult with the plan
        """
        prompt = f"""You are a senior software architect. Analyze the following product specification and create a detailed implementation plan.

PRODUCT SPECIFICATION:
{product_spec}

Create a JSON response with the following structure:
{{
    "plan_name": "Name of the feature/project",
    "summary": "Brief summary of what will be built",
    "phases": [
        {{
            "phase": 1,
            "name": "Phase name",
            "tasks": [
                {{
                    "id": "T1",
                    "description": "Task description",
                    "files": ["list of files to create/modify"],
                    "dependencies": []
                }}
            ]
        }}
    ],
    "test_strategy": {{
        "unit_tests": ["List of unit test files"],
        "integration_tests": ["List of integration tests"],
        "test_commands": ["Commands to run tests"]
    }},
    "risks": ["List of potential risks"],
    "estimated_complexity": "low|medium|high"
}}

Focus on:
1. Breaking work into small, testable tasks
2. Identifying all files that need to be created or modified
3. Defining clear dependencies between tasks
4. Planning tests before implementation (TDD approach)"""

        return self.run(prompt, output_file=output_file)

    def run_implementation(
        self,
        plan: dict,
        feedback: Optional[dict] = None,
        output_file: Optional[Path] = None,
    ):
        """Run Claude for implementation phase.

        Args:
            plan: The approved plan from Phase 1
            feedback: Consolidated feedback from Phase 2
            output_file: File to write results to

        Returns:
            AgentResult with implementation details
        """
        feedback_section = ""
        if feedback:
            feedback_section = f"""

FEEDBACK TO ADDRESS:
{feedback}
"""

        prompt = f"""You are implementing a software feature based on an approved plan.

IMPLEMENTATION PLAN:
{plan}
{feedback_section}

INSTRUCTIONS:
1. Write tests FIRST (TDD approach)
2. Implement the code to make tests pass
3. Follow the task order and dependencies
4. Report progress as JSON

For each task you complete, output a JSON object:
{{
    "task_id": "T1",
    "status": "completed",
    "files_created": ["list of new files"],
    "files_modified": ["list of modified files"],
    "tests_written": ["list of test files"],
    "tests_passed": true,
    "notes": "Any implementation notes"
}}

At the end, provide a summary:
{{
    "implementation_complete": true,
    "all_tests_pass": true,
    "total_files_created": 5,
    "total_files_modified": 3,
    "test_results": {{
        "passed": 10,
        "failed": 0,
        "skipped": 0
    }}
}}"""

        return self.run(prompt, output_file=output_file, max_turns=50)
