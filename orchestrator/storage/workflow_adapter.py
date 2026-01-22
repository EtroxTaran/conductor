"""Workflow state storage adapter.

Provides unified interface for workflow state management with automatic backend selection.
Uses SurrealDB when enabled, falls back to file-based JSON otherwise.
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

    Automatically selects between file-based and SurrealDB backends
    based on configuration. Provides a unified interface for workflow
    state operations.

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

        # Lazy-initialized backends
        self._file_backend: Optional[Any] = None
        self._db_backend: Optional[Any] = None

    @property
    def _use_db(self) -> bool:
        """Check if SurrealDB should be used."""
        try:
            from orchestrator.db import is_surrealdb_enabled
            return is_surrealdb_enabled()
        except ImportError:
            return False

    def _get_file_backend(self) -> Any:
        """Get or create file backend."""
        if self._file_backend is None:
            from orchestrator.utils.state import StateManager
            self._file_backend = StateManager(self.project_dir)
        return self._file_backend

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
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.get_state())
                if state:
                    return self._db_state_to_data(state)
                return None
            except Exception as e:
                logger.warning(f"Failed to get DB state, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        if not file_backend.state_file.exists():
            return None

        state = file_backend.state
        return self._file_state_to_data(state)

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
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(
                    db.initialize_state(
                        project_dir=project_dir,
                        execution_mode=execution_mode,
                    )
                )
                return self._db_state_to_data(state)
            except Exception as e:
                logger.warning(f"Failed to initialize DB state, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        file_backend.ensure_workflow_dir()
        state = file_backend.load()

        # Set execution mode in metadata
        state.metadata["execution_mode"] = execution_mode
        file_backend.save()

        return self._file_state_to_data(state)

    def update_state(self, **updates: Any) -> Optional[WorkflowStateData]:
        """Update workflow state fields.

        Args:
            **updates: Fields to update

        Returns:
            Updated state
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.update_state(**updates))
                if state:
                    return self._db_state_to_data(state)
                return None
            except Exception as e:
                logger.warning(f"Failed to update DB state, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        state = file_backend.state

        # Apply updates to file backend state
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
            elif key in state.metadata:
                state.metadata[key] = value
            else:
                state.metadata[key] = value

        file_backend.save()
        return self._file_state_to_data(state)

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
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.set_phase(phase, status))
                if state:
                    return self._db_state_to_data(state)
                return None
            except Exception as e:
                logger.warning(f"Failed to set DB phase, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()

        if status == "in_progress":
            file_backend.start_phase(phase)
        elif status == "completed":
            file_backend.complete_phase(phase)
        elif status == "failed":
            file_backend.fail_phase(phase, "Unknown error")
        elif status == "pending":
            file_backend.reset_phase(phase)

        return self._file_state_to_data(file_backend.state)

    def reset_state(self) -> Optional[WorkflowStateData]:
        """Reset workflow state to initial.

        Returns:
            Reset state
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.reset_state())
                if state:
                    return self._db_state_to_data(state)
                return None
            except Exception as e:
                logger.warning(f"Failed to reset DB state, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        file_backend.reset_to_phase(1)
        file_backend.reset_iteration_count()
        return self._file_state_to_data(file_backend.state)

    def get_summary(self) -> dict[str, Any]:
        """Get workflow state summary.

        Returns:
            Summary dictionary
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                return run_async(db.get_summary())
            except Exception as e:
                logger.warning(f"Failed to get DB summary, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.get_summary()

    def increment_iteration(self) -> int:
        """Increment iteration counter.

        Returns:
            New iteration count
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.increment_iteration())
                if state:
                    return state.iteration_count
            except Exception as e:
                logger.warning(f"Failed to increment DB iteration, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.increment_iteration()

    def set_plan(self, plan: dict) -> Optional[WorkflowStateData]:
        """Set implementation plan.

        Args:
            plan: Plan dictionary

        Returns:
            Updated state
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.set_plan(plan))
                if state:
                    return self._db_state_to_data(state)
                return None
            except Exception as e:
                logger.warning(f"Failed to set DB plan, falling back to file: {e}")

        # File backend - store plan in metadata
        return self.update_state(plan=plan)

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
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.set_validation_feedback(agent, feedback))
                if state:
                    return self._db_state_to_data(state)
                return None
            except Exception as e:
                logger.warning(f"Failed to set DB validation feedback, falling back to file: {e}")

        # File backend - store in phase outputs
        file_backend = self._get_file_backend()
        phase = file_backend.get_phase(2)  # Validation is phase 2
        if "validation_feedback" not in phase.outputs:
            phase.outputs["validation_feedback"] = {}
        phase.outputs["validation_feedback"][agent] = feedback
        file_backend.save()
        return self._file_state_to_data(file_backend.state)

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
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.set_verification_feedback(agent, feedback))
                if state:
                    return self._db_state_to_data(state)
                return None
            except Exception as e:
                logger.warning(f"Failed to set DB verification feedback, falling back to file: {e}")

        # File backend - store in phase outputs
        file_backend = self._get_file_backend()
        phase = file_backend.get_phase(4)  # Verification is phase 4
        if "verification_feedback" not in phase.outputs:
            phase.outputs["verification_feedback"] = {}
        phase.outputs["verification_feedback"][agent] = feedback
        file_backend.save()
        return self._file_state_to_data(file_backend.state)

    def set_implementation_result(self, result: dict) -> Optional[WorkflowStateData]:
        """Set implementation result.

        Args:
            result: Implementation result dictionary

        Returns:
            Updated state
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                state = run_async(db.set_implementation_result(result))
                if state:
                    return self._db_state_to_data(state)
                return None
            except Exception as e:
                logger.warning(f"Failed to set DB implementation result, falling back to file: {e}")

        # File backend - store in phase outputs
        file_backend = self._get_file_backend()
        phase = file_backend.get_phase(3)  # Implementation is phase 3
        phase.outputs["implementation_result"] = result
        file_backend.save()
        return self._file_state_to_data(file_backend.state)

    def set_decision(self, decision: str) -> Optional[WorkflowStateData]:
        """Set next routing decision.

        Args:
            decision: Decision (continue, retry, escalate, abort)

        Returns:
            Updated state
        """
        return self.update_state(next_decision=decision)

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

    @staticmethod
    def _file_state_to_data(state: Any) -> WorkflowStateData:
        """Convert file state to data class."""
        # Build phase_status from file backend's phase objects
        phase_status = {}
        phase_names = ["planning", "validation", "implementation", "verification", "completion"]
        for i, name in enumerate(phase_names, 1):
            phase = state.phases.get(name)
            if phase:
                phase_status[str(i)] = {
                    "status": phase.status.value,
                    "attempts": phase.attempts,
                    "started_at": phase.started_at,
                    "completed_at": phase.completed_at,
                }

        # Extract values from metadata and phase outputs
        plan = state.metadata.get("plan")
        validation_feedback = state.metadata.get("validation_feedback")
        verification_feedback = state.metadata.get("verification_feedback")
        implementation_result = state.metadata.get("implementation_result")

        # Also check phase outputs
        if not validation_feedback and state.phases.get("validation"):
            validation_feedback = state.phases["validation"].outputs.get("validation_feedback")
        if not verification_feedback and state.phases.get("verification"):
            verification_feedback = state.phases["verification"].outputs.get("verification_feedback")
        if not implementation_result and state.phases.get("implementation"):
            implementation_result = state.phases["implementation"].outputs.get("implementation_result")

        # Parse timestamps
        created_at = None
        updated_at = None
        if state.created_at:
            try:
                created_at = datetime.fromisoformat(state.created_at)
            except (ValueError, TypeError):
                pass
        if state.updated_at:
            try:
                updated_at = datetime.fromisoformat(state.updated_at)
            except (ValueError, TypeError):
                pass

        return WorkflowStateData(
            project_dir=str(state.project_name),
            current_phase=state.current_phase,
            phase_status=phase_status,
            iteration_count=state.iteration_count,
            plan=plan,
            validation_feedback=validation_feedback,
            verification_feedback=verification_feedback,
            implementation_result=implementation_result,
            next_decision=state.metadata.get("next_decision"),
            execution_mode=state.metadata.get("execution_mode", "afk"),
            discussion_complete=state.metadata.get("discussion_complete", False),
            research_complete=state.metadata.get("research_complete", False),
            research_findings=state.metadata.get("research_findings"),
            token_usage=state.metadata.get("token_usage"),
            created_at=created_at,
            updated_at=updated_at,
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
