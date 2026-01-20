"""Main orchestrator for the multi-agent workflow."""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .utils.state import StateManager, PhaseStatus
from .utils.logging import OrchestrationLogger, LogLevel
from .utils.git_operations import GitOperationsManager
from .phases import (
    PlanningPhase,
    ValidationPhase,
    ImplementationPhase,
    VerificationPhase,
    CompletionPhase,
)


class Orchestrator:
    """Multi-agent workflow orchestrator.

    Coordinates Claude Code, Cursor CLI, and Gemini CLI through a 5-phase workflow:
    1. Planning (Claude)
    2. Validation (Cursor + Gemini parallel)
    3. Implementation (Claude)
    4. Verification (Cursor + Gemini parallel)
    5. Completion (Summary)

    Features:
    - Auto-retry on failures (configurable max attempts)
    - Auto-commit after each successful phase
    - State persistence for resumability
    - Structured logging
    """

    PHASES = [
        (1, "planning", PlanningPhase),
        (2, "validation", ValidationPhase),
        (3, "implementation", ImplementationPhase),
        (4, "verification", VerificationPhase),
        (5, "completion", CompletionPhase),
    ]

    def __init__(
        self,
        project_dir: str | Path,
        max_retries: int = 3,
        auto_commit: bool = True,
        console_output: bool = True,
        log_level: LogLevel = LogLevel.INFO,
    ):
        """Initialize the orchestrator.

        Args:
            project_dir: Root directory of the project
            max_retries: Maximum retry attempts per phase
            auto_commit: Whether to auto-commit after phases
            console_output: Whether to print to console
            log_level: Minimum log level
        """
        self.project_dir = Path(project_dir).resolve()
        self.max_retries = max_retries
        self.auto_commit = auto_commit

        # Initialize state manager
        self.state = StateManager(self.project_dir)
        self.state.ensure_workflow_dir()

        # Initialize logger
        self.logger = OrchestrationLogger(
            workflow_dir=self.state.workflow_dir,
            console_output=console_output,
            min_level=log_level,
        )

        # Initialize git operations manager for efficient batched git operations
        self.git = GitOperationsManager(self.project_dir)

    def check_prerequisites(self) -> tuple[bool, list[str]]:
        """Check that all prerequisites are met.

        Returns:
            Tuple of (success, list of errors)
        """
        errors = []

        # Check PRODUCT.md exists
        product_file = self.project_dir / "PRODUCT.md"
        if not product_file.exists():
            errors.append(
                "PRODUCT.md not found. Create it with your feature specification."
            )

        # Check CLI tools
        from .agents import ClaudeAgent, CursorAgent, GeminiAgent

        claude = ClaudeAgent(self.project_dir)
        cursor = CursorAgent(self.project_dir)
        gemini = GeminiAgent(self.project_dir)

        if not claude.check_available():
            errors.append("Claude CLI not found. Install with: npm install -g @anthropic/claude-cli")

        if not cursor.check_available():
            errors.append("Cursor CLI not found. Install with: curl https://cursor.com/install -fsSL | bash")

        if not gemini.check_available():
            errors.append("Gemini CLI not found. Install with: npm install -g @google/gemini-cli")

        return len(errors) == 0, errors

    def run(
        self,
        start_phase: int = 1,
        end_phase: int = 5,
        skip_validation: bool = False,
    ) -> dict:
        """Run the orchestration workflow.

        Args:
            start_phase: Phase to start from (1-5)
            end_phase: Phase to end at (1-5)
            skip_validation: Skip the validation phase (phase 2)

        Returns:
            Dictionary with workflow results
        """
        self.logger.banner("Multi-Agent Orchestration System")

        # Check prerequisites
        prereq_ok, prereq_errors = self.check_prerequisites()
        if not prereq_ok:
            for error in prereq_errors:
                self.logger.error(error)
            return {
                "success": False,
                "error": "Prerequisites not met",
                "details": prereq_errors,
            }

        # Load state
        self.state.load()
        self.logger.info(f"Project: {self.state.state.project_name}")
        self.logger.info(f"Workflow directory: {self.state.workflow_dir}")
        self.logger.separator()

        # Run phases
        results = {}
        for phase_num, phase_name, phase_class in self.PHASES:
            if phase_num < start_phase:
                continue
            if phase_num > end_phase:
                break
            if skip_validation and phase_num == 2:
                self.logger.info("Skipping validation phase", phase=2)
                continue

            # Check if phase is already completed
            phase_state = self.state.get_phase(phase_num)
            if phase_state.status == PhaseStatus.COMPLETED:
                self.logger.info(f"Phase {phase_num} already completed, skipping", phase=phase_num)
                continue

            # Run phase with retry logic
            result = self._run_phase_with_retry(phase_num, phase_name, phase_class)
            results[phase_name] = result

            if not result.get("success", False):
                self.logger.error(f"Workflow stopped at phase {phase_num}")
                return {
                    "success": False,
                    "stopped_at_phase": phase_num,
                    "error": result.get("error", "Phase failed"),
                    "results": results,
                }

            # Auto-commit after successful phase
            if self.auto_commit and phase_num < 5:  # Don't commit after completion
                self._auto_commit(phase_num, phase_name)

        self.logger.banner("Workflow Complete!")
        self.logger.info(f"Summary: {self.state.workflow_dir / 'phases' / 'completion' / 'COMPLETION.md'}")

        return {
            "success": True,
            "results": results,
            "summary": self.state.get_summary(),
        }

    def _run_phase_with_retry(
        self,
        phase_num: int,
        phase_name: str,
        phase_class: type,
    ) -> dict:
        """Run a phase with retry logic.

        Args:
            phase_num: Phase number (1-5)
            phase_name: Phase name
            phase_class: Phase class to instantiate

        Returns:
            Dictionary with phase results
        """
        phase_state = self.state.get_phase(phase_num)

        while self.state.can_retry(phase_num):
            # Print progress indicator
            self._print_progress(phase_num, phase_name.title(), "Starting...")

            # Create phase instance
            phase = phase_class(
                project_dir=self.project_dir,
                state_manager=self.state,
                logger=self.logger,
            )

            # Update max attempts from orchestrator config
            phase_state.max_attempts = self.max_retries

            # Log retry if not first attempt
            if phase_state.attempts > 0:
                self.logger.retry(phase_num, phase_state.attempts + 1, self.max_retries)

            # Run phase
            result = phase.run()

            if result.get("success", False):
                return result

            # Check if we should retry
            if not self.state.can_retry(phase_num):
                break

            # Reset phase for retry
            self.state.reset_phase(phase_num)

        return {
            "success": False,
            "error": f"Phase {phase_num} failed after {phase_state.attempts} attempts",
            "last_error": phase_state.error,
        }

    def _auto_commit(self, phase_num: int, phase_name: str) -> None:
        """Auto-commit changes after a phase.

        Uses GitOperationsManager for efficient batched git operations,
        reducing subprocess overhead from 5 calls to 1.

        Args:
            phase_num: Phase number
            phase_name: Phase name for commit message
        """
        try:
            if not self.git.is_git_repo():
                self.logger.debug("Not a git repository, skipping auto-commit")
                return

            commit_message = f"[orchestrator] Phase {phase_num}: {phase_name} complete"

            # Single batched operation: status check + add + commit + hash
            commit_hash = self.git.auto_commit(commit_message)

            if commit_hash:
                self.state.record_commit(phase_num, commit_hash, commit_message)
                self.logger.commit(phase_num, commit_hash, commit_message)
            else:
                self.logger.debug("No changes to commit")

        except Exception as e:
            self.logger.warning(f"Auto-commit failed: {e}", phase=phase_num)

    def resume(self) -> dict:
        """Resume workflow from last incomplete phase.

        Returns:
            Dictionary with workflow results
        """
        self.state.load()

        # Find first incomplete phase
        start_phase = 1
        for phase_num, phase_name, _ in self.PHASES:
            phase_state = self.state.get_phase(phase_num)
            if phase_state.status != PhaseStatus.COMPLETED:
                start_phase = phase_num
                break

        if start_phase > 5:
            self.logger.info("All phases already completed")
            return {"success": True, "message": "Workflow already complete"}

        self.logger.info(f"Resuming from phase {start_phase}")
        return self.run(start_phase=start_phase)

    def status(self) -> dict:
        """Get current workflow status.

        Returns:
            Dictionary with status information
        """
        self.state.load()
        return self.state.get_summary()

    def reset(self, phase: Optional[int] = None) -> None:
        """Reset workflow or a specific phase.

        Args:
            phase: Phase number to reset, or None to reset all
        """
        self.state.load()

        if phase:
            self.state.reset_phase(phase)
            self.logger.info(f"Reset phase {phase}")
        else:
            # Reset all phases
            for phase_num, _, _ in self.PHASES:
                phase_state = self.state.get_phase(phase_num)
                phase_state.status = PhaseStatus.PENDING
                phase_state.attempts = 0
                phase_state.blockers = []
                phase_state.error = None
                phase_state.started_at = None
                phase_state.completed_at = None

            self.state.state.current_phase = 1
            self.state.state.git_commits = []
            self.state.save()
            self.logger.info("Reset all phases")

    def rollback_to_phase(self, phase_num: int) -> dict:
        """Rollback to state before specified phase.

        Uses git commits recorded during workflow execution to restore
        the codebase to a previous state.

        Args:
            phase_num: Phase number to rollback to (will undo this phase and later)

        Returns:
            Dictionary with rollback results
        """
        self.state.load()
        commits = self.state.state.git_commits

        # Find commit before this phase
        target_commit = None
        for commit in reversed(commits):
            if commit.get("phase", 0) < phase_num:
                target_commit = commit.get("hash")
                break

        if not target_commit:
            return {
                "success": False,
                "error": f"No commit found before phase {phase_num}"
            }

        # Git reset to that commit using GitOperationsManager
        try:
            if self.git.reset_hard(target_commit):
                # Update state
                self.state.reset_to_phase(phase_num)

                self.logger.info(f"Rolled back to commit {target_commit[:8]} (before phase {phase_num})")

                return {
                    "success": True,
                    "rolled_back_to": target_commit,
                    "current_phase": phase_num - 1 if phase_num > 1 else 1,
                    "message": f"Successfully rolled back to state before phase {phase_num}"
                }
            else:
                return {
                    "success": False,
                    "error": "Git reset failed"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Rollback failed: {str(e)}"
            }

    def health_check(self) -> dict:
        """Return current health status.

        Checks the status of the workflow and availability of all agents.

        Returns:
            Dictionary with health status information
        """
        self.state.load()
        state = self.state.state

        # Check agent availability
        from .agents import ClaudeAgent, CursorAgent, GeminiAgent

        claude = ClaudeAgent(self.project_dir)
        cursor = CursorAgent(self.project_dir)
        gemini = GeminiAgent(self.project_dir)

        agents_status = {
            "claude": claude.check_available(),
            "cursor": cursor.check_available(),
            "gemini": gemini.check_available(),
        }

        # Determine overall health
        all_agents_available = all(agents_status.values())
        current_phase_status = None
        if state.current_phase:
            phase_state = self.state.get_phase(state.current_phase)
            current_phase_status = phase_state.status.value

        health_status = "healthy"
        if not all_agents_available:
            health_status = "degraded"
        if current_phase_status == "failed":
            health_status = "unhealthy"

        return {
            "status": health_status,
            "project": state.project_name,
            "current_phase": state.current_phase,
            "phase_status": current_phase_status,
            "iteration_count": state.iteration_count,
            "last_updated": state.updated_at,
            "agents": agents_status,
            "has_context": state.context is not None,
            "total_commits": len(state.git_commits),
        }

    def _print_progress(self, phase_num: int, phase_name: str, status: str) -> None:
        """Print progress indicator.

        Args:
            phase_num: Current phase number
            phase_name: Name of the current phase
            status: Status message
        """
        phases = ["Planning", "Validation", "Implementation", "Verification", "Completion"]

        # Build progress bar
        progress_parts = []
        for i, name in enumerate(phases, 1):
            if i < phase_num:
                progress_parts.append(f"[{i}]")  # Completed
            elif i == phase_num:
                progress_parts.append(f"[{i}*]")  # Current
            else:
                progress_parts.append(f"[ ]")  # Pending

        progress_bar = " ".join(progress_parts)

        if self.logger.console_output:
            print()
            print("=" * 60)
            print(f"Phase {phase_num}/5: {phase_name} - {status}")
            print(f"Progress: {progress_bar}")
            print("=" * 60)
            print()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Orchestration System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m orchestrator --start           Start workflow from phase 1
  python -m orchestrator --resume          Resume from last incomplete phase
  python -m orchestrator --status          Show current workflow status
  python -m orchestrator --health          Show health check status
  python -m orchestrator --reset           Reset all phases
  python -m orchestrator --rollback 3      Rollback to before phase 3
  python -m orchestrator --phase 3         Start from specific phase
        """,
    )

    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the workflow",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last incomplete phase",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show workflow status",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Show health check status",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset workflow",
    )
    parser.add_argument(
        "--rollback",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Rollback to state before specified phase",
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Start from specific phase",
    )
    parser.add_argument(
        "--end-phase",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=5,
        help="End at specific phase",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation phase",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Disable auto-commit",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries per phase (default: 3)",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        default=".",
        help="Project directory (default: current)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output",
    )

    args = parser.parse_args()

    # Determine log level
    log_level = LogLevel.INFO
    if args.quiet:
        log_level = LogLevel.WARNING
    elif args.debug:
        log_level = LogLevel.DEBUG

    # Create orchestrator
    orchestrator = Orchestrator(
        project_dir=args.project_dir,
        max_retries=args.max_retries,
        auto_commit=not args.no_commit,
        log_level=log_level,
    )

    # Execute command
    if args.status:
        status = orchestrator.status()
        print("\nWorkflow Status:")
        print(f"  Project: {status['project']}")
        print(f"  Current Phase: {status['current_phase']}")
        print(f"  Total Commits: {status['total_commits']}")
        print("\nPhase Statuses:")
        for phase, state in status['phase_statuses'].items():
            emoji = "✅" if state == "completed" else "❌" if state == "failed" else "⏳"
            print(f"  {emoji} {phase}: {state}")
        return

    if args.health:
        health = orchestrator.health_check()
        status_emoji = "✅" if health['status'] == "healthy" else "⚠️" if health['status'] == "degraded" else "❌"
        print(f"\nHealth Check: {status_emoji} {health['status'].upper()}")
        print(f"\n  Project: {health['project']}")
        print(f"  Current Phase: {health['current_phase']}")
        print(f"  Phase Status: {health['phase_status'] or 'N/A'}")
        print(f"  Iteration Count: {health['iteration_count']}")
        print(f"  Last Updated: {health['last_updated']}")
        print("\nAgent Availability:")
        for agent, available in health['agents'].items():
            emoji = "✅" if available else "❌"
            print(f"  {emoji} {agent}: {'Available' if available else 'Unavailable'}")
        return

    if args.rollback:
        result = orchestrator.rollback_to_phase(args.rollback)
        if result['success']:
            print(f"\n✅ Rollback successful!")
            print(f"  Rolled back to commit: {result['rolled_back_to'][:8]}")
            print(f"  Current phase: {result['current_phase']}")
        else:
            print(f"\n❌ Rollback failed: {result['error']}")
            sys.exit(1)
        return

    if args.reset:
        orchestrator.reset()
        print("Workflow reset.")
        return

    if args.resume:
        result = orchestrator.resume()
    elif args.start or args.phase:
        start = args.phase or 1
        result = orchestrator.run(
            start_phase=start,
            end_phase=args.end_phase,
            skip_validation=args.skip_validation,
        )
    else:
        parser.print_help()
        return

    # Exit with appropriate code
    sys.exit(0 if result.get("success", False) else 1)


if __name__ == "__main__":
    main()
