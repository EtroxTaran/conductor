"""Workflow state storage adapter.

Provides unified interface for workflow state management using SurrealDB.
This is the DB-only version - no file fallback.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .async_utils import run_async
from .base import WorkflowStateData, WorkflowStorageProtocol

logger = logging.getLogger(__name__)


class WorkflowStorageAdapter(WorkflowStorageProtocol):
    """Storage adapter for workflow state management.

    Uses SurrealDB as the only storage backend. No file fallback.

    Usage:
        adapter = WorkflowStorageAdapter(project_dir)

        # Initialize state
        state = adapter.initialize_state(project_dir, execution_mode="afk")

        # Get current state
        state = adapter.get_state()

        # Update state
        adapter.update_state(current_phase=2, iteration_count=1)

        # Set phase
        adapter.set_phase(2, status="in_progress")
    """

    def __init__(
        self,
        project_dir: Path,
        project_name: Optional[str] = None,
    ):
        """Initialize workflow storage adapter.

        Args:
            project_dir: Project directory
            project_name: Project name (defaults to directory name)
        """
        self.project_dir = Path(project_dir)
        self.project_name = project_name or self.project_dir.name
        self._db_backend: Optional[Any] = None

    def _get_db_backend(self) -> Any:
        """Get or create database backend."""
        if self._db_backend is None:
            from orchestrator.db.repositories.workflow import get_workflow_repository
            self._db_backend = get_workflow_repository(self.project_name)
        return self._db_backend

    def get_state(self) -> Optional[WorkflowStateData]:
        """Get current workflow state.

        Returns:
            WorkflowStateData or None if not initialized
        """
        db = self._get_db_backend()
        state = run_async(db.get_state())
        if state:
            return self._db_state_to_data(state)
        return None

    def initialize_state(
        self,
        project_dir: str,
        execution_mode: str = "afk",
    ) -> WorkflowStateData:
        """Initialize workflow state for a new project.

        Args:
            project_dir: Project directory path
            execution_mode: Execution mode (afk or hitl)

        Returns:
            Initialized WorkflowStateData
        """
        db = self._get_db_backend()
        state = run_async(
            db.initialize_state(
                project_dir=project_dir,
                execution_mode=execution_mode,
            )
        )
        return self._db_state_to_data(state)

    def update_state(self, **updates: Any) -> Optional[WorkflowStateData]:
        """Update workflow state fields.

        Args:
            **updates: Fields to update

        Returns:
            Updated state
        """
        db = self._get_db_backend()
        state = run_async(db.update_state(**updates))
        if state:
            return self._db_state_to_data(state)
        return None

    def set_phase(
        self,
        phase: int,
        status: str = "in_progress",
    ) -> Optional[WorkflowStateData]:
        """Set current phase and status.

        Args:
            phase: Phase number (1-5)
            status: Phase status

        Returns:
            Updated state
        """
        db = self._get_db_backend()
        state = run_async(db.set_phase(phase, status))
        if state:
            return self._db_state_to_data(state)
        return None

    def reset_state(self) -> Optional[WorkflowStateData]:
        """Reset workflow state to initial.

        Returns:
            Reset state
        """
        db = self._get_db_backend()
        state = run_async(db.reset_state())
        if state:
            return self._db_state_to_data(state)
        return None

    def get_summary(self) -> dict[str, Any]:
        """Get workflow state summary.

        Returns:
            Summary dictionary
        """
        db = self._get_db_backend()
        return run_async(db.get_summary())

    def increment_iteration(self) -> int:
        """Increment iteration counter.

        Returns:
            New iteration count
        """
        db = self._get_db_backend()
        state = run_async(db.increment_iteration())
        if state:
            return state.iteration_count
        return 0

    def set_plan(self, plan: dict) -> Optional[WorkflowStateData]:
        """Set implementation plan.

        Args:
            plan: Plan dictionary

        Returns:
            Updated state
        """
        db = self._get_db_backend()
        state = run_async(db.set_plan(plan))
        if state:
            return self._db_state_to_data(state)
        return None

    def set_validation_feedback(
        self,
        agent: str,
        feedback: dict,
    ) -> Optional[WorkflowStateData]:
        """Set validation feedback from an agent.

        Args:
            agent: Agent identifier (cursor, gemini)
            feedback: Feedback dictionary

        Returns:
            Updated state
        """
        db = self._get_db_backend()
        state = run_async(db.set_validation_feedback(agent, feedback))
        if state:
            return self._db_state_to_data(state)
        return None

    def set_verification_feedback(
        self,
        agent: str,
        feedback: dict,
    ) -> Optional[WorkflowStateData]:
        """Set verification feedback from an agent.

        Args:
            agent: Agent identifier (cursor, gemini)
            feedback: Feedback dictionary

        Returns:
            Updated state
        """
        db = self._get_db_backend()
        state = run_async(db.set_verification_feedback(agent, feedback))
        if state:
            return self._db_state_to_data(state)
        return None

    def set_implementation_result(self, result: dict) -> Optional[WorkflowStateData]:
        """Set implementation result.

        Args:
            result: Implementation result dictionary

        Returns:
            Updated state
        """
        db = self._get_db_backend()
        state = run_async(db.set_implementation_result(result))
        if state:
            return self._db_state_to_data(state)
        return None

    def set_decision(self, decision: str) -> Optional[WorkflowStateData]:
        """Set next routing decision.

        Args:
            decision: Decision (continue, retry, escalate, abort)

        Returns:
            Updated state
        """
        return self.update_state(next_decision=decision)

    def record_git_commit(
        self,
        phase: int,
        commit_hash: str,
        message: str,
        task_id: Optional[str] = None,
        files_changed: Optional[list[str]] = None,
    ) -> dict:
        """Record a git commit.

        Args:
            phase: Phase number when commit was made
            commit_hash: Git commit hash
            message: Commit message
            task_id: Optional task ID
            files_changed: Optional list of changed files

        Returns:
            Created commit record
        """
        db = self._get_db_backend()
        return run_async(db.record_git_commit(phase, commit_hash, message, task_id, files_changed))

    def get_git_commits(
        self,
        phase: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> list[dict]:
        """Get git commits with optional filters.

        Args:
            phase: Optional phase filter
            task_id: Optional task ID filter

        Returns:
            List of commit records
        """
        db = self._get_db_backend()
        return run_async(db.get_git_commits(phase, task_id))

    def reset_to_phase(self, phase_num: int) -> Optional[WorkflowStateData]:
        """Reset workflow state to before a specific phase.

        Args:
            phase_num: Phase to reset to (this phase and later will be reset)

        Returns:
            Updated state
        """
        db = self._get_db_backend()
        state = run_async(db.reset_to_phase(phase_num))
        if state:
            return self._db_state_to_data(state)
        return None

    @staticmethod
    def _db_state_to_data(state: Any) -> WorkflowStateData:
        """Convert database state to data class."""
        return WorkflowStateData(
            project_dir=state.project_dir,
            current_phase=state.current_phase,
            phase_status=state.phase_status,
            iteration_count=state.iteration_count,
            plan=state.plan,
            validation_feedback=state.validation_feedback,
            verification_feedback=state.verification_feedback,
            implementation_result=state.implementation_result,
            next_decision=state.next_decision,
            execution_mode=state.execution_mode,
            discussion_complete=state.discussion_complete,
            research_complete=state.research_complete,
            research_findings=state.research_findings,
            token_usage=state.token_usage,
            created_at=state.created_at,
            updated_at=state.updated_at,
        )


# Cache of adapters per project
_workflow_adapters: dict[str, WorkflowStorageAdapter] = {}


def get_workflow_storage(
    project_dir: Path,
    project_name: Optional[str] = None,
) -> WorkflowStorageAdapter:
    """Get or create workflow storage adapter for a project.

    Args:
        project_dir: Project directory
        project_name: Project name (defaults to directory name)

    Returns:
        WorkflowStorageAdapter instance
    """
    key = str(Path(project_dir).resolve())

    if key not in _workflow_adapters:
        _workflow_adapters[key] = WorkflowStorageAdapter(project_dir, project_name)
    return _workflow_adapters[key]
