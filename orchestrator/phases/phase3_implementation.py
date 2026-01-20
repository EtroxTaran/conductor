"""Phase 3: Implementation - Claude implements the plan with TDD approach."""

import json
import selectors
import subprocess
import time
from pathlib import Path
from typing import Optional

from .base import BasePhase

# Default timeout for test commands (5 minutes)
TEST_TIMEOUT = 300
# Maximum output size to capture (5KB)
MAX_OUTPUT_SIZE = 5000


class ImplementationPhase(BasePhase):
    """Phase 3: Implementation.

    Claude implements the plan:
    - Writes tests first (TDD)
    - Implements code to make tests pass
    - Runs tests and reports results

    Creates:
    - implementation-log.json: Detailed implementation log
    - implementation-results.json: Summary of results
    - test-results.json: Test execution results
    """

    phase_number = 3
    phase_name = "implementation"

    def execute(self) -> dict:
        """Execute the implementation phase.

        Returns:
            Dictionary with implementation results
        """
        # Get plan and feedback
        plan = self.get_plan()
        if not plan:
            return {
                "success": False,
                "error": "plan.json not found. Phase 1 must complete first.",
            }

        feedback = self.get_feedback()

        self.logger.info("Starting implementation", phase=3)
        self.logger.agent_start("claude", "Implementing with TDD approach", phase=3)

        # Run Claude implementation
        result = self.claude.run_implementation(
            plan=plan,
            feedback=feedback,
            output_file=self.phase_dir / "implementation-log.json",
        )

        if not result.success:
            self.logger.agent_error("claude", result.error or "Implementation failed", phase=3)
            return {
                "success": False,
                "error": result.error or "Claude implementation failed",
            }

        # Process implementation results
        impl_results = self._process_implementation(result)
        self.write_file(self.phase_dir / "implementation-results.json", impl_results)

        # Run tests to verify
        self.logger.info("Running tests to verify implementation", phase=3)
        test_results = self._run_tests(plan)
        self.write_file(self.phase_dir / "test-results.json", test_results)

        # Determine success
        tests_passed = test_results.get("all_passed", False)

        if tests_passed:
            self.logger.agent_complete("claude", "Implementation complete, all tests pass", phase=3)
        else:
            self.logger.warning("Implementation complete but some tests failed", phase=3)

        return {
            "success": True,
            "implementation_complete": impl_results.get("implementation_complete", False),
            "tests_passed": tests_passed,
            "test_results": test_results,
            "files_created": impl_results.get("files_created", []),
            "files_modified": impl_results.get("files_modified", []),
            "results_file": str(self.phase_dir / "implementation-results.json"),
        }

    def _process_implementation(self, result) -> dict:
        """Process implementation output from Claude."""
        impl_results = {
            "implementation_complete": False,
            "files_created": [],
            "files_modified": [],
            "tests_written": [],
            "task_log": [],
        }

        # Parse output
        if result.parsed_output:
            output = result.parsed_output
            if isinstance(output, dict):
                impl_results.update({
                    "implementation_complete": output.get("implementation_complete", False),
                    "files_created": output.get("total_files_created", output.get("files_created", [])),
                    "files_modified": output.get("total_files_modified", output.get("files_modified", [])),
                    "test_results": output.get("test_results", {}),
                })
            return impl_results

        # Try to extract from text output
        if result.output:
            try:
                # Look for task completion JSON objects
                import re
                task_pattern = r'\{[\s\S]*?"task_id"[\s\S]*?"status"[\s\S]*?\}'
                summary_pattern = r'\{[\s\S]*?"implementation_complete"[\s\S]*?\}'

                # Find task updates
                task_matches = re.findall(task_pattern, result.output)
                for match in task_matches:
                    try:
                        task = json.loads(match)
                        impl_results["task_log"].append(task)
                        if task.get("files_created"):
                            impl_results["files_created"].extend(task["files_created"])
                        if task.get("files_modified"):
                            impl_results["files_modified"].extend(task["files_modified"])
                        if task.get("tests_written"):
                            impl_results["tests_written"].extend(task["tests_written"])
                    except json.JSONDecodeError:
                        continue

                # Find summary
                summary_matches = re.findall(summary_pattern, result.output)
                if summary_matches:
                    try:
                        summary = json.loads(summary_matches[-1])
                        impl_results["implementation_complete"] = summary.get("implementation_complete", False)
                        impl_results["test_results"] = summary.get("test_results", {})
                    except json.JSONDecodeError:
                        pass

            except Exception as e:
                self.logger.warning(f"Error parsing implementation output: {e}", phase=3)

        # Deduplicate file lists
        impl_results["files_created"] = list(set(impl_results["files_created"]))
        impl_results["files_modified"] = list(set(impl_results["files_modified"]))
        impl_results["tests_written"] = list(set(impl_results["tests_written"]))

        return impl_results

    def _run_tests(self, plan: dict) -> dict:
        """Run tests based on plan's test strategy."""
        test_results = {
            "all_passed": False,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "command_outputs": [],
        }

        test_strategy = plan.get("test_strategy", {})
        test_commands = test_strategy.get("test_commands", [])

        # Default test commands if none specified
        if not test_commands:
            test_commands = self._detect_test_commands()

        if not test_commands:
            self.logger.warning("No test commands found", phase=3)
            test_results["errors"].append("No test commands configured")
            return test_results

        all_passed = True
        for cmd in test_commands:
            self.logger.info(f"Running: {cmd}", phase=3)
            try:
                # Use streaming subprocess for memory-efficient output capture
                output = self._run_tests_streaming(cmd)
                test_results["command_outputs"].append(output)

                if output["exit_code"] != 0:
                    all_passed = False
                    test_results["errors"].append(f"Command failed: {cmd}")

                # Try to parse test counts from output
                counts = self._parse_test_counts(output["stdout"])
                test_results["passed"] += counts.get("passed", 0)
                test_results["failed"] += counts.get("failed", 0)
                test_results["skipped"] += counts.get("skipped", 0)

            except Exception as e:
                all_passed = False
                test_results["errors"].append(f"Error running {cmd}: {str(e)}")

        test_results["all_passed"] = all_passed and test_results["failed"] == 0

        return test_results

    def _run_tests_streaming(
        self,
        cmd: str,
        max_output: int = MAX_OUTPUT_SIZE,
        timeout: int = TEST_TIMEOUT,
    ) -> dict:
        """Run tests with streaming output capture for memory efficiency.

        Instead of buffering the entire output and then truncating (which
        wastes memory for large outputs), this streams the output and
        stops capturing once the size limit is reached.

        Args:
            cmd: Shell command to run
            max_output: Maximum bytes to capture per stream (default 5KB)
            timeout: Command timeout in seconds (default 5 minutes)

        Returns:
            Dict with command, exit_code, stdout, stderr
        """
        process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=self.project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        stdout_size = 0
        stderr_size = 0

        try:
            sel = selectors.DefaultSelector()
            sel.register(process.stdout, selectors.EVENT_READ)
            sel.register(process.stderr, selectors.EVENT_READ)

            start_time = time.time()

            while process.poll() is None:
                # Check timeout
                if time.time() - start_time > timeout:
                    process.kill()
                    process.wait()
                    break

                # Wait for data with 1 second timeout
                ready = sel.select(timeout=1)
                for key, _ in ready:
                    data = key.fileobj.read(1024)
                    if not data:
                        continue

                    if key.fileobj == process.stdout:
                        if stdout_size < max_output:
                            remaining = max_output - stdout_size
                            stdout_chunks.append(data[:remaining])
                            stdout_size += len(data)
                    elif key.fileobj == process.stderr:
                        if stderr_size < max_output:
                            remaining = max_output - stderr_size
                            stderr_chunks.append(data[:remaining])
                            stderr_size += len(data)

            # Read any remaining data after process ends
            remaining_stdout = process.stdout.read()
            if remaining_stdout and stdout_size < max_output:
                remaining = max_output - stdout_size
                stdout_chunks.append(remaining_stdout[:remaining])

            remaining_stderr = process.stderr.read()
            if remaining_stderr and stderr_size < max_output:
                remaining = max_output - stderr_size
                stderr_chunks.append(remaining_stderr[:remaining])

            sel.close()

        except Exception:
            process.kill()
            process.wait()

        return {
            "command": cmd,
            "exit_code": process.returncode if process.returncode is not None else -1,
            "stdout": "".join(stdout_chunks),
            "stderr": "".join(stderr_chunks),
        }

    def _detect_test_commands(self) -> list[str]:
        """Detect test commands based on project structure."""
        commands = []

        # Check for package.json (Node.js)
        if (self.project_dir / "package.json").exists():
            try:
                with open(self.project_dir / "package.json") as f:
                    pkg = json.load(f)
                if "scripts" in pkg and "test" in pkg["scripts"]:
                    commands.append("npm test")
            except Exception:
                pass

        # Check for pytest (Python)
        if (self.project_dir / "pytest.ini").exists() or \
           (self.project_dir / "pyproject.toml").exists() or \
           (self.project_dir / "tests").is_dir():
            commands.append("pytest")

        # Check for go.mod (Go)
        if (self.project_dir / "go.mod").exists():
            commands.append("go test ./...")

        # Check for Cargo.toml (Rust)
        if (self.project_dir / "Cargo.toml").exists():
            commands.append("cargo test")

        return commands

    def _parse_test_counts(self, output: str) -> dict:
        """Parse test counts from command output."""
        counts = {"passed": 0, "failed": 0, "skipped": 0}

        if not output:
            return counts

        import re

        # pytest format: "X passed, Y failed, Z skipped"
        pytest_pattern = r"(\d+) passed"
        match = re.search(pytest_pattern, output)
        if match:
            counts["passed"] = int(match.group(1))

        pytest_failed = r"(\d+) failed"
        match = re.search(pytest_failed, output)
        if match:
            counts["failed"] = int(match.group(1))

        pytest_skipped = r"(\d+) skipped"
        match = re.search(pytest_skipped, output)
        if match:
            counts["skipped"] = int(match.group(1))

        # Jest/npm test format
        jest_pattern = r"Tests:\s+(\d+) passed"
        match = re.search(jest_pattern, output)
        if match:
            counts["passed"] = int(match.group(1))

        jest_failed = r"Tests:.*?(\d+) failed"
        match = re.search(jest_failed, output)
        if match:
            counts["failed"] = int(match.group(1))

        # Go test format
        go_pattern = r"ok\s+"
        counts["passed"] += len(re.findall(go_pattern, output))

        go_failed = r"FAIL\s+"
        counts["failed"] += len(re.findall(go_failed, output))

        return counts
