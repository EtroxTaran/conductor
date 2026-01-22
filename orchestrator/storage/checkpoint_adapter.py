"""Checkpoint storage adapter.

Provides unified interface for checkpoint management with automatic backend selection.
Uses SurrealDB when enabled, falls back to file-based storage otherwise.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .async_utils import run_async
from .base import CheckpointData, CheckpointStorageProtocol

logger = logging.getLogger(__name__)


class CheckpointStorageAdapter(CheckpointStorageProtocol):
    """Storage adapter for checkpoint management.

    Automatically selects between file-based and SurrealDB backends
    based on configuration. Provides a unified interface for checkpoint
    operations.

    Usage:
        adapter = CheckpointStorageAdapter(project_dir)

        # Create a checkpoint
        checkpoint = adapter.create_checkpoint("before-refactor", notes="Pre-refactor state")

        # List checkpoints
        checkpoints = adapter.list_checkpoints()

        # Rollback to checkpoint
        adapter.rollback_to_checkpoint(checkpoint_id, confirm=True)
    """

    def __init__(
        self,
        project_dir: Path,
        project_name: Optional[str] = None,
    ):
        """Initialize checkpoint storage adapter.

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
            from orchestrator.utils.checkpoint import CheckpointManager
            self._file_backend = CheckpointManager(self.project_dir)
        return self._file_backend

    def _get_db_backend(self) -> Any:
        """Get or create database backend."""
        if self._db_backend is None:
            from orchestrator.db.repositories.checkpoints import get_checkpoint_repository
            self._db_backend = get_checkpoint_repository(self.project_name)
        return self._db_backend

    def _get_current_state(self) -> dict:
        """Get current workflow state for checkpointing."""
        # Use file backend's method which handles StateProjector fallback
        file_backend = self._get_file_backend()
        return file_backend._get_current_state()

    def _get_task_progress(self, state: dict) -> dict:
        """Extract task progress from state."""
        file_backend = self._get_file_backend()
        return file_backend._get_task_progress(state)

    def create_checkpoint(
        self,
        name: str,
        notes: str = "",
        include_files: bool = False,
    ) -> CheckpointData:
        """Create a new checkpoint.

        Args:
            name: Human-readable checkpoint name
            notes: Optional notes about this checkpoint
            include_files: Whether to record file list

        Returns:
            Created CheckpointData
        """
        # Get current state
        state = self._get_current_state()
        task_progress = self._get_task_progress(state)
        phase = state.get("current_phase", 0)

        # Get files if requested
        files: list[str] = []
        if include_files:
            file_backend = self._get_file_backend()
            files = file_backend._get_tracked_files()

        if self._use_db:
            try:
                db = self._get_db_backend()
                checkpoint = run_async(
                    db.create_checkpoint(
                        name=name,
                        state_snapshot=state,
                        phase=phase,
                        notes=notes,
                        task_progress=task_progress,
                        files_snapshot=files,
                    )
                )
                return self._db_checkpoint_to_data(checkpoint)
            except Exception as e:
                logger.warning(f"Failed to create DB checkpoint, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        checkpoint = file_backend.create_checkpoint(name, notes, include_files)
        return self._file_checkpoint_to_data(checkpoint)

    def list_checkpoints(self) -> list[CheckpointData]:
        """List all checkpoints for this project.

        Returns:
            List of CheckpointData objects, sorted by creation time
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                checkpoints = run_async(db.list_checkpoints())
                return [self._db_checkpoint_to_data(c) for c in checkpoints]
            except Exception as e:
                logger.warning(f"Failed to list DB checkpoints, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        checkpoints = file_backend.list_checkpoints()
        return [self._file_checkpoint_to_data(c) for c in checkpoints]

    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Get checkpoint by ID.

        Args:
            checkpoint_id: Full or partial checkpoint ID

        Returns:
            CheckpointData if found
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                checkpoint = run_async(db.get_checkpoint(checkpoint_id))
                if checkpoint:
                    return self._db_checkpoint_to_data(checkpoint)
                return None
            except Exception as e:
                logger.warning(f"Failed to get DB checkpoint, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        checkpoint = file_backend.get_checkpoint(checkpoint_id)
        if checkpoint:
            return self._file_checkpoint_to_data(checkpoint)
        return None

    def rollback_to_checkpoint(self, checkpoint_id: str, confirm: bool = False) -> bool:
        """Rollback workflow state to a checkpoint.

        WARNING: This overwrites current state with checkpoint state.

        Args:
            checkpoint_id: Checkpoint ID to rollback to
            confirm: Must be True to actually perform rollback

        Returns:
            True if rollback successful
        """
        if not confirm:
            logger.warning("Rollback requires confirm=True")
            return False

        # Get checkpoint first to verify it exists
        checkpoint = self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            logger.error(f"Checkpoint not found: {checkpoint_id}")
            return False

        # For rollback, we always use the file-based approach since
        # it handles the actual state.json file on disk
        file_backend = self._get_file_backend()

        if self._use_db:
            # If using DB, we need to get the state snapshot and write it
            try:
                db = self._get_db_backend()
                db_checkpoint = run_async(db.get_checkpoint(checkpoint_id))
                if db_checkpoint and db_checkpoint.state_snapshot:
                    # Write the state to state.json
                    import json
                    import shutil

                    workflow_dir = self.project_dir / ".workflow"
                    current_state = workflow_dir / "state.json"

                    # Backup current state
                    if current_state.exists():
                        backup_name = f"state.json.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                        shutil.copy(current_state, workflow_dir / backup_name)
                        logger.info(f"Backed up current state to: {backup_name}")

                    # Write checkpoint state
                    current_state.write_text(json.dumps(db_checkpoint.state_snapshot, indent=2))
                    logger.info(f"Rolled back to checkpoint: {checkpoint.summary()}")
                    return True
            except Exception as e:
                logger.warning(f"Failed to rollback from DB, falling back to file: {e}")

        # File backend rollback
        return file_backend.rollback_to_checkpoint(checkpoint_id, confirm=True)

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID to delete

        Returns:
            True if deleted successfully
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                result = run_async(db.delete_checkpoint(checkpoint_id))
                if result:
                    return True
            except Exception as e:
                logger.warning(f"Failed to delete DB checkpoint, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.delete_checkpoint(checkpoint_id)

    def prune_old_checkpoints(self, keep_count: int = 10) -> int:
        """Remove old checkpoints, keeping the most recent ones.

        Args:
            keep_count: Number of checkpoints to keep

        Returns:
            Number of checkpoints deleted
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                return run_async(db.prune_old_checkpoints(keep_count))
            except Exception as e:
                logger.warning(f"Failed to prune DB checkpoints, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.prune_old_checkpoints(keep_count)

    def get_latest(self) -> Optional[CheckpointData]:
        """Get the most recent checkpoint.

        Returns:
            Latest CheckpointData or None
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                checkpoint = run_async(db.get_latest())
                if checkpoint:
                    return self._db_checkpoint_to_data(checkpoint)
                return None
            except Exception as e:
                logger.warning(f"Failed to get latest DB checkpoint, falling back to file: {e}")

        # File backend - get list and return last
        file_backend = self._get_file_backend()
        checkpoints = file_backend.list_checkpoints()
        if checkpoints:
            return self._file_checkpoint_to_data(checkpoints[-1])
        return None

    @staticmethod
    def _db_checkpoint_to_data(checkpoint: Any) -> CheckpointData:
        """Convert database checkpoint to data class."""
        return CheckpointData(
            id=checkpoint.id,
            name=checkpoint.name,
            notes=checkpoint.notes,
            phase=checkpoint.phase,
            task_progress=checkpoint.task_progress,
            state_snapshot=checkpoint.state_snapshot,
            files_snapshot=checkpoint.files_snapshot,
            created_at=checkpoint.created_at,
        )

    @staticmethod
    def _file_checkpoint_to_data(checkpoint: Any) -> CheckpointData:
        """Convert file checkpoint to data class."""
        return CheckpointData(
            id=checkpoint.id,
            name=checkpoint.name,
            notes=checkpoint.notes,
            phase=checkpoint.phase,
            task_progress=checkpoint.task_progress,
            state_snapshot=checkpoint.state_snapshot,
            files_snapshot=checkpoint.files_snapshot,
            created_at=checkpoint.created_at,
        )


# Cache of adapters per project
_checkpoint_adapters: dict[str, CheckpointStorageAdapter] = {}


def get_checkpoint_storage(
    project_dir: Path,
    project_name: Optional[str] = None,
) -> CheckpointStorageAdapter:
    """Get or create checkpoint storage adapter for a project.

    Args:
        project_dir: Project directory
        project_name: Project name (defaults to directory name)

    Returns:
        CheckpointStorageAdapter instance
    """
    key = str(Path(project_dir).resolve())

    if key not in _checkpoint_adapters:
        _checkpoint_adapters[key] = CheckpointStorageAdapter(project_dir, project_name)
    return _checkpoint_adapters[key]
