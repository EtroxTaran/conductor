"""Tests for workflow storage adapter."""

import json
import pytest
import tempfile
from pathlib import Path

from orchestrator.storage.workflow_adapter import (
    WorkflowStorageAdapter,
    get_workflow_storage,
)
from orchestrator.storage.base import WorkflowStateData


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        workflow_dir = project_dir / ".workflow"
        workflow_dir.mkdir(parents=True)
        yield project_dir


@pytest.fixture
def temp_project_with_state(temp_project):
    """Create a temporary project with workflow state."""
    state_file = temp_project / ".workflow" / "state.json"
    state_file.write_text(json.dumps({
        "project_name": temp_project.name,
        "current_phase": 1,
        "iteration_count": 0,
        "phases": {
            "planning": {"status": "pending", "attempts": 0},
            "validation": {"status": "pending", "attempts": 0},
            "implementation": {"status": "pending", "attempts": 0},
            "verification": {"status": "pending", "attempts": 0},
            "completion": {"status": "pending", "attempts": 0},
        },
        "tasks": [],
        "metadata": {},
    }))
    return temp_project


class TestWorkflowStorageAdapter:
    """Tests for WorkflowStorageAdapter."""

    def test_init(self, temp_project):
        """Test adapter initialization."""
        adapter = WorkflowStorageAdapter(temp_project)
        assert adapter.project_dir == temp_project
        assert adapter.project_name == temp_project.name

    def test_get_state_none(self, temp_project):
        """Test get_state returns None when no state exists."""
        adapter = WorkflowStorageAdapter(temp_project)
        state = adapter.get_state()
        assert state is None

    def test_get_state_exists(self, temp_project_with_state):
        """Test get_state returns state when exists."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)
        state = adapter.get_state()

        assert state is not None
        assert isinstance(state, WorkflowStateData)
        assert state.current_phase == 1

    def test_initialize_state(self, temp_project):
        """Test initializing workflow state."""
        adapter = WorkflowStorageAdapter(temp_project)

        state = adapter.initialize_state(
            project_dir=str(temp_project),
            execution_mode="hitl",
        )

        assert state is not None
        assert state.execution_mode == "hitl"

    def test_update_state(self, temp_project_with_state):
        """Test updating workflow state."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        state = adapter.update_state(
            current_phase=2,
            iteration_count=1,
        )

        assert state is not None
        assert state.current_phase == 2
        assert state.iteration_count == 1

    def test_set_phase_in_progress(self, temp_project_with_state):
        """Test setting phase to in_progress."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        state = adapter.set_phase(1, status="in_progress")

        assert state is not None

    def test_set_phase_completed(self, temp_project_with_state):
        """Test setting phase to completed."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        # Start phase first
        adapter.set_phase(1, status="in_progress")

        # Complete it
        state = adapter.set_phase(1, status="completed")
        assert state is not None

    def test_reset_state(self, temp_project_with_state):
        """Test resetting workflow state."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        # Update state first
        adapter.update_state(current_phase=3, iteration_count=5)

        # Reset
        state = adapter.reset_state()

        assert state is not None
        assert state.current_phase == 1
        assert state.iteration_count == 0

    def test_get_summary(self, temp_project_with_state):
        """Test getting workflow summary."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        summary = adapter.get_summary()

        assert isinstance(summary, dict)
        assert "current_phase" in summary

    def test_increment_iteration(self, temp_project_with_state):
        """Test incrementing iteration counter."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        count = adapter.increment_iteration()
        assert count == 1

        count = adapter.increment_iteration()
        assert count == 2

    def test_set_plan(self, temp_project_with_state):
        """Test setting implementation plan."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        plan = {
            "name": "Test Plan",
            "tasks": [{"id": "T1", "title": "Task 1"}],
        }

        state = adapter.set_plan(plan)
        assert state is not None

    def test_set_validation_feedback(self, temp_project_with_state):
        """Test setting validation feedback."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        feedback = {
            "score": 8,
            "approved": True,
            "comments": "Looks good",
        }

        state = adapter.set_validation_feedback("cursor", feedback)
        assert state is not None

    def test_set_verification_feedback(self, temp_project_with_state):
        """Test setting verification feedback."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        feedback = {
            "score": 9,
            "approved": True,
            "comments": "Code is solid",
        }

        state = adapter.set_verification_feedback("gemini", feedback)
        assert state is not None

    def test_set_implementation_result(self, temp_project_with_state):
        """Test setting implementation result."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        result = {
            "success": True,
            "files_created": ["src/main.py"],
            "tests_passed": True,
        }

        state = adapter.set_implementation_result(result)
        assert state is not None

    def test_set_decision(self, temp_project_with_state):
        """Test setting next routing decision."""
        adapter = WorkflowStorageAdapter(temp_project_with_state)

        state = adapter.set_decision("continue")
        assert state is not None


class TestGetWorkflowStorage:
    """Tests for get_workflow_storage factory function."""

    def test_returns_adapter(self, temp_project):
        """Test factory returns an adapter."""
        adapter = get_workflow_storage(temp_project)
        assert isinstance(adapter, WorkflowStorageAdapter)

    def test_caches_adapter(self, temp_project):
        """Test factory returns same adapter for same project."""
        adapter1 = get_workflow_storage(temp_project)
        adapter2 = get_workflow_storage(temp_project)
        assert adapter1 is adapter2
