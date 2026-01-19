"""State management for the orchestration workflow."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field, asdict
from enum import Enum

if TYPE_CHECKING:
    from .context import ContextState, ContextManager


class PhaseStatus(str, Enum):
    """Status of a workflow phase."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class PhaseState:
    """State of a single phase."""
    name: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    blockers: list[str] = field(default_factory=list)
    approvals: dict[str, bool] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "PhaseState":
        """Create from dictionary."""
        data["status"] = PhaseStatus(data.get("status", "pending"))
        return cls(**data)


@dataclass
class WorkflowState:
    """Complete workflow state."""
    project_name: str
    current_phase: int = 1
    iteration_count: int = 0
    phases: dict[str, PhaseState] = field(default_factory=dict)
    context: Optional[dict] = None  # Stores ContextState.to_dict()
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    git_commits: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize phases if not provided."""
        if not self.phases:
            phase_names = [
                "planning",
                "validation",
                "implementation",
                "verification",
                "completion",
            ]
            self.phases = {
                name: PhaseState(name=name)
                for name in phase_names
            }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_name": self.project_name,
            "current_phase": self.current_phase,
            "iteration_count": self.iteration_count,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "git_commits": self.git_commits,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        """Create from dictionary."""
        phases = {
            k: PhaseState.from_dict(v)
            for k, v in data.get("phases", {}).items()
        }
        return cls(
            project_name=data["project_name"],
            current_phase=data.get("current_phase", 1),
            iteration_count=data.get("iteration_count", 0),
            phases=phases,
            context=data.get("context"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            git_commits=data.get("git_commits", []),
            metadata=data.get("metadata", {}),
        )


class StateManager:
    """Manages workflow state persistence."""

    PHASE_NAMES = ["planning", "validation", "implementation", "verification", "completion"]

    def __init__(self, project_dir: str | Path):
        """Initialize state manager.

        Args:
            project_dir: Root directory of the project
        """
        self.project_dir = Path(project_dir)
        self.workflow_dir = self.project_dir / ".workflow"
        self.state_file = self.workflow_dir / "state.json"
        self._state: Optional[WorkflowState] = None

    def ensure_workflow_dir(self) -> Path:
        """Ensure .workflow directory exists with proper structure."""
        self.workflow_dir.mkdir(exist_ok=True)

        # Create phase directories
        phases_dir = self.workflow_dir / "phases"
        phases_dir.mkdir(exist_ok=True)

        for phase_name in self.PHASE_NAMES:
            phase_dir = phases_dir / phase_name
            phase_dir.mkdir(exist_ok=True)

        return self.workflow_dir

    def load(self) -> WorkflowState:
        """Load state from file or create new."""
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                data = json.load(f)
            self._state = WorkflowState.from_dict(data)
        else:
            project_name = self.project_dir.name
            self._state = WorkflowState(project_name=project_name)
            self.save()
        return self._state

    def save(self) -> None:
        """Save state to file."""
        if self._state is None:
            raise RuntimeError("No state loaded")

        self.ensure_workflow_dir()
        self._state.updated_at = datetime.now().isoformat()

        with open(self.state_file, "w") as f:
            json.dump(self._state.to_dict(), f, indent=2)

    @property
    def state(self) -> WorkflowState:
        """Get current state, loading if necessary."""
        if self._state is None:
            self.load()
        return self._state

    def get_current_phase(self) -> PhaseState:
        """Get the current phase state."""
        phase_name = self.PHASE_NAMES[self.state.current_phase - 1]
        return self.state.phases[phase_name]

    def get_phase(self, phase_num: int) -> PhaseState:
        """Get phase state by number (1-indexed)."""
        if not 1 <= phase_num <= 5:
            raise ValueError(f"Invalid phase number: {phase_num}")
        phase_name = self.PHASE_NAMES[phase_num - 1]
        return self.state.phases[phase_name]

    def get_phase_dir(self, phase_num: int) -> Path:
        """Get directory for a phase."""
        phase_name = self.PHASE_NAMES[phase_num - 1]
        return self.workflow_dir / "phases" / phase_name

    def start_phase(self, phase_num: int) -> PhaseState:
        """Mark a phase as started."""
        phase = self.get_phase(phase_num)
        phase.status = PhaseStatus.IN_PROGRESS
        phase.started_at = datetime.now().isoformat()
        phase.attempts += 1
        self.state.current_phase = phase_num
        self.save()
        return phase

    def complete_phase(self, phase_num: int, outputs: Optional[dict] = None) -> PhaseState:
        """Mark a phase as completed."""
        phase = self.get_phase(phase_num)
        phase.status = PhaseStatus.COMPLETED
        phase.completed_at = datetime.now().isoformat()
        if outputs:
            phase.outputs.update(outputs)
        self.save()
        return phase

    def fail_phase(self, phase_num: int, error: str) -> PhaseState:
        """Mark a phase as failed."""
        phase = self.get_phase(phase_num)
        phase.status = PhaseStatus.FAILED
        phase.error = error
        self.save()
        return phase

    def block_phase(self, phase_num: int, blocker: str) -> PhaseState:
        """Add a blocker to a phase."""
        phase = self.get_phase(phase_num)
        phase.status = PhaseStatus.BLOCKED
        phase.blockers.append(blocker)
        self.save()
        return phase

    def add_approval(self, phase_num: int, agent: str, approved: bool) -> PhaseState:
        """Add an agent approval to a phase."""
        phase = self.get_phase(phase_num)
        phase.approvals[agent] = approved
        self.save()
        return phase

    def record_commit(self, phase_num: int, commit_hash: str, message: str) -> None:
        """Record a git commit for a phase."""
        self.state.git_commits.append({
            "phase": phase_num,
            "hash": commit_hash,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        })
        self.save()

    def can_retry(self, phase_num: int) -> bool:
        """Check if a phase can be retried."""
        phase = self.get_phase(phase_num)
        return phase.attempts < phase.max_attempts

    def reset_phase(self, phase_num: int) -> PhaseState:
        """Reset a phase for retry (keeps attempt count)."""
        phase = self.get_phase(phase_num)
        phase.status = PhaseStatus.PENDING
        phase.blockers = []
        phase.error = None
        self.save()
        return phase

    def get_summary(self) -> dict:
        """Get a summary of the workflow state."""
        return {
            "project": self.state.project_name,
            "current_phase": self.state.current_phase,
            "iteration_count": self.state.iteration_count,
            "phase_statuses": {
                name: phase.status.value
                for name, phase in self.state.phases.items()
            },
            "total_commits": len(self.state.git_commits),
            "created": self.state.created_at,
            "updated": self.state.updated_at,
            "has_context": self.state.context is not None,
        }

    # Iteration tracking methods

    def increment_iteration(self) -> int:
        """Increment the iteration count and return new value."""
        self.state.iteration_count += 1
        self.save()
        return self.state.iteration_count

    def get_iteration_count(self) -> int:
        """Get current iteration count."""
        return self.state.iteration_count

    def reset_iteration_count(self) -> None:
        """Reset iteration count to zero."""
        self.state.iteration_count = 0
        self.save()

    # Context management methods

    def capture_context(self) -> dict:
        """Capture current context state using ContextManager.

        Returns:
            Dictionary representation of ContextState
        """
        from .context import ContextManager

        ctx_manager = ContextManager(self.project_dir)
        context_state = ctx_manager.capture_context()
        self.state.context = context_state.to_dict()
        self.save()
        return self.state.context

    def get_context(self) -> Optional[dict]:
        """Get stored context state."""
        return self.state.context

    def check_context_drift(self) -> tuple[bool, list[str]]:
        """Check if context files have changed since capture.

        Returns:
            Tuple of (has_drift, list of changed file keys)
        """
        if not self.state.context:
            return False, []

        from .context import ContextManager, ContextState

        ctx_manager = ContextManager(self.project_dir)
        stored_state = ContextState.from_dict(self.state.context)
        drift_result = ctx_manager.validate_context(stored_state)

        changed = drift_result.changed_files + drift_result.added_files + drift_result.removed_files
        return drift_result.has_drift, changed

    def sync_context(self) -> dict:
        """Re-capture context state (sync after drift).

        Returns:
            Updated context state dictionary
        """
        return self.capture_context()

    def get_context_drift_details(self) -> Optional[dict]:
        """Get detailed drift information.

        Returns:
            Dictionary with drift details or None if no context stored
        """
        if not self.state.context:
            return None

        from .context import ContextManager, ContextState

        ctx_manager = ContextManager(self.project_dir)
        stored_state = ContextState.from_dict(self.state.context)
        drift_result = ctx_manager.validate_context(stored_state)

        return drift_result.to_dict()
