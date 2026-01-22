"""Tests for checkpoint storage adapter."""

import json
import pytest
import tempfile
from pathlib import Path

from orchestrator.storage.checkpoint_adapter import (
    CheckpointStorageAdapter,
    get_checkpoint_storage,
)
from orchestrator.storage.base import CheckpointData


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        workflow_dir = project_dir / ".workflow"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "checkpoints").mkdir()

        # Create state.json for checkpoint to capture
        state_file = workflow_dir / "state.json"
        state_file.write_text(json.dumps({
            "project_name": project_dir.name,
            "current_phase": 2,
            "iteration_count": 1,
            "phases": {},
            "tasks": [],
            "metadata": {},
        }))

        yield project_dir


class TestCheckpointStorageAdapter:
    """Tests for CheckpointStorageAdapter."""

    def test_init(self, temp_project):
        """Test adapter initialization."""
        adapter = CheckpointStorageAdapter(temp_project)
        assert adapter.project_dir == temp_project
        assert adapter.project_name == temp_project.name

    def test_create_checkpoint(self, temp_project):
        """Test creating a checkpoint."""
        adapter = CheckpointStorageAdapter(temp_project)

        checkpoint = adapter.create_checkpoint(
            name="pre-refactor",
            notes="Before major refactoring",
        )

        assert isinstance(checkpoint, CheckpointData)
        assert checkpoint.name == "pre-refactor"
        assert checkpoint.notes == "Before major refactoring"
        assert checkpoint.id is not None

    def test_list_checkpoints_empty(self, temp_project):
        """Test listing checkpoints when none exist."""
        adapter = CheckpointStorageAdapter(temp_project)
        checkpoints = adapter.list_checkpoints()
        assert checkpoints == []

    def test_list_checkpoints_after_create(self, temp_project):
        """Test listing checkpoints after creating one."""
        adapter = CheckpointStorageAdapter(temp_project)

        adapter.create_checkpoint("checkpoint-1")
        adapter.create_checkpoint("checkpoint-2")

        checkpoints = adapter.list_checkpoints()
        assert len(checkpoints) == 2

    def test_get_checkpoint(self, temp_project):
        """Test getting a checkpoint by ID."""
        adapter = CheckpointStorageAdapter(temp_project)

        created = adapter.create_checkpoint("test-checkpoint")
        retrieved = adapter.get_checkpoint(created.id)

        assert retrieved is not None
        assert retrieved.name == "test-checkpoint"

    def test_get_checkpoint_not_found(self, temp_project):
        """Test getting non-existent checkpoint."""
        adapter = CheckpointStorageAdapter(temp_project)
        checkpoint = adapter.get_checkpoint("nonexistent")
        assert checkpoint is None

    def test_get_latest_none(self, temp_project):
        """Test get_latest returns None when no checkpoints."""
        adapter = CheckpointStorageAdapter(temp_project)
        latest = adapter.get_latest()
        assert latest is None

    def test_get_latest(self, temp_project):
        """Test get_latest returns most recent checkpoint."""
        adapter = CheckpointStorageAdapter(temp_project)

        adapter.create_checkpoint("first")
        adapter.create_checkpoint("second")
        adapter.create_checkpoint("third")

        latest = adapter.get_latest()
        assert latest is not None
        assert latest.name == "third"

    def test_delete_checkpoint(self, temp_project):
        """Test deleting a checkpoint."""
        adapter = CheckpointStorageAdapter(temp_project)

        created = adapter.create_checkpoint("to-delete")
        result = adapter.delete_checkpoint(created.id)

        assert result is True

        # Verify deleted
        checkpoint = adapter.get_checkpoint(created.id)
        assert checkpoint is None

    def test_prune_old_checkpoints(self, temp_project):
        """Test pruning old checkpoints."""
        adapter = CheckpointStorageAdapter(temp_project)

        # Create several checkpoints
        for i in range(5):
            adapter.create_checkpoint(f"checkpoint-{i}")

        # Prune keeping only 2
        deleted = adapter.prune_old_checkpoints(keep_count=2)

        assert deleted == 3

        # Verify only 2 remain
        checkpoints = adapter.list_checkpoints()
        assert len(checkpoints) == 2

    def test_rollback_without_confirm(self, temp_project):
        """Test rollback requires confirm=True."""
        adapter = CheckpointStorageAdapter(temp_project)

        created = adapter.create_checkpoint("test")
        result = adapter.rollback_to_checkpoint(created.id, confirm=False)

        assert result is False

    def test_rollback_with_confirm(self, temp_project):
        """Test rollback with confirm=True."""
        adapter = CheckpointStorageAdapter(temp_project)

        # Create checkpoint at phase 2
        created = adapter.create_checkpoint("phase-2")

        # Modify state
        state_file = temp_project / ".workflow" / "state.json"
        state = json.loads(state_file.read_text())
        state["current_phase"] = 4
        state_file.write_text(json.dumps(state))

        # Rollback
        result = adapter.rollback_to_checkpoint(created.id, confirm=True)
        assert result is True

        # Verify state was restored
        state = json.loads(state_file.read_text())
        assert state["current_phase"] == 2


class TestGetCheckpointStorage:
    """Tests for get_checkpoint_storage factory function."""

    def test_returns_adapter(self, temp_project):
        """Test factory returns an adapter."""
        adapter = get_checkpoint_storage(temp_project)
        assert isinstance(adapter, CheckpointStorageAdapter)

    def test_caches_adapter(self, temp_project):
        """Test factory returns same adapter for same project."""
        adapter1 = get_checkpoint_storage(temp_project)
        adapter2 = get_checkpoint_storage(temp_project)
        assert adapter1 is adapter2
