"""Checkpoint repository.

Provides checkpoint management for workflow state snapshots.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..connection import get_connection
from .base import BaseRepository

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """Checkpoint representation.

    Compatible with existing Checkpoint dataclass.
    Note: project_name removed in schema v2.0.0 (per-project database isolation).
    """

    id: str
    name: str
    notes: str = ""
    phase: int = 0
    task_progress: dict = field(default_factory=dict)
    state_snapshot: dict = field(default_factory=dict)
    files_snapshot: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoint_id": self.id,
            "name": self.name,
            "notes": self.notes,
            "phase": self.phase,
            "task_progress": self.task_progress,
            "state_snapshot": self.state_snapshot,
            "files_snapshot": self.files_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        return cls(
            id=data.get("checkpoint_id", data.get("id", "")),
            name=data.get("name", ""),
            notes=data.get("notes", ""),
            phase=data.get("phase", 0),
            task_progress=data.get("task_progress", {}),
            state_snapshot=data.get("state_snapshot", {}),
            files_snapshot=data.get("files_snapshot", []),
            created_at=created_at,
        )

    def summary(self) -> str:
        """Get brief summary for listing."""
        progress = self.task_progress
        created = self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "unknown"
        return (
            f"[{self.id[:8]}] {self.name} - Phase {self.phase} "
            f"({progress.get('completed', 0)}/{progress.get('total', 0)} tasks) "
            f"- {created}"
        )


class CheckpointRepository(BaseRepository[Checkpoint]):
    """Repository for checkpoints."""

    table_name = "checkpoints"

    def _to_record(self, data: dict[str, Any]) -> Checkpoint:
        return Checkpoint.from_dict(data)

    def _from_record(self, checkpoint: Checkpoint) -> dict[str, Any]:
        return checkpoint.to_dict()

    @staticmethod
    def _generate_id(name: str, timestamp: datetime, project_name: str) -> str:
        """Generate unique checkpoint ID."""
        content = f"{name}-{timestamp.isoformat()}-{project_name}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    async def create_checkpoint(
        self,
        name: str,
        state_snapshot: dict,
        phase: int = 0,
        notes: str = "",
        task_progress: Optional[dict] = None,
        files_snapshot: Optional[list[str]] = None,
    ) -> Checkpoint:
        """Create a new checkpoint.

        Note: Database is already scoped to project (schema v2.0.0).

        Args:
            name: Checkpoint name
            state_snapshot: Complete workflow state
            phase: Current phase number
            notes: Optional notes
            task_progress: Task completion status
            files_snapshot: List of tracked files

        Returns:
            Created checkpoint
        """
        now = datetime.now()
        checkpoint_id = self._generate_id(name, now, self.project_name)

        checkpoint = Checkpoint(
            id=checkpoint_id,
            name=name,
            notes=notes,
            phase=phase,
            task_progress=task_progress or {},
            state_snapshot=state_snapshot,
            files_snapshot=files_snapshot or [],
            created_at=now,
        )

        # Use checkpoint_id as record ID (database is already project-scoped)
        await self.create(checkpoint.to_dict(), checkpoint_id)

        logger.info(f"Created checkpoint: {checkpoint.summary()}")
        return checkpoint

    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID (full or partial).

        Args:
            checkpoint_id: Full or partial checkpoint ID

        Returns:
            Checkpoint if found
        """
        async with get_connection(self.project_name) as conn:
            # Try exact match first
            results = await conn.query(
                """
                SELECT * FROM checkpoints
                WHERE checkpoint_id = $checkpoint_id
                LIMIT 1
                """,
                {"checkpoint_id": checkpoint_id},
            )

            if results:
                return self._to_record(results[0])

            # Try partial match
            results = await conn.query(
                """
                SELECT * FROM checkpoints
                WHERE string::startsWith(checkpoint_id, $prefix)
                """,
                {"prefix": checkpoint_id},
            )

            if len(results) == 1:
                return self._to_record(results[0])
            elif len(results) > 1:
                logger.warning(f"Ambiguous checkpoint ID: {checkpoint_id}")

            return None

    async def list_checkpoints(self) -> list[Checkpoint]:
        """List all checkpoints for this project.

        Returns:
            List of checkpoints, sorted by creation time
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                """
                SELECT * FROM checkpoints
                ORDER BY created_at ASC
                """,
            )
            return [self._to_record(r) for r in results]

    async def get_latest(self) -> Optional[Checkpoint]:
        """Get the most recent checkpoint.

        Returns:
            Latest checkpoint or None
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                """
                SELECT * FROM checkpoints
                ORDER BY created_at DESC
                LIMIT 1
                """,
            )
            if results:
                return self._to_record(results[0])
            return None

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID

        Returns:
            True if deleted
        """
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return False

        return await self.delete(checkpoint.id)

    async def prune_old_checkpoints(self, keep_count: int = 10) -> int:
        """Remove old checkpoints, keeping most recent.

        Args:
            keep_count: Number to keep

        Returns:
            Number deleted
        """
        checkpoints = await self.list_checkpoints()

        if len(checkpoints) <= keep_count:
            return 0

        to_delete = checkpoints[:-keep_count]
        deleted = 0

        for checkpoint in to_delete:
            if await self.delete_checkpoint(checkpoint.id):
                deleted += 1

        logger.info(f"Pruned {deleted} old checkpoints")
        return deleted


# Global repository cache
_checkpoint_repos: dict[str, CheckpointRepository] = {}


def get_checkpoint_repository(project_name: str) -> CheckpointRepository:
    """Get or create checkpoint repository for a project.

    Args:
        project_name: Project name

    Returns:
        CheckpointRepository instance
    """
    if project_name not in _checkpoint_repos:
        _checkpoint_repos[project_name] = CheckpointRepository(project_name)
    return _checkpoint_repos[project_name]
