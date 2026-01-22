"""Session repository.

Provides session management for CLI continuity tracking.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..connection import get_connection
from .base import BaseRepository

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Session representation for CLI continuity.

    Note: project_name removed in schema v2.0.0 (per-project database isolation).
    """

    id: str
    task_id: str
    agent: str
    status: str = "active"
    invocation_count: int = 0
    total_cost_usd: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.id,
            "task_id": self.task_id,
            "agent": self.agent,
            "status": self.status,
            "invocation_count": self.invocation_count,
            "total_cost_usd": self.total_cost_usd,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create from dictionary."""

        def parse_datetime(val: Any) -> Optional[datetime]:
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            return None

        return cls(
            id=data.get("session_id", data.get("id", "")),
            task_id=data.get("task_id", ""),
            agent=data.get("agent", ""),
            status=data.get("status", "active"),
            invocation_count=data.get("invocation_count", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            created_at=parse_datetime(data.get("created_at")),
            updated_at=parse_datetime(data.get("updated_at")),
            closed_at=parse_datetime(data.get("closed_at")),
        )


class SessionRepository(BaseRepository[Session]):
    """Repository for session management."""

    table_name = "sessions"

    def _to_record(self, data: dict[str, Any]) -> Session:
        return Session.from_dict(data)

    def _from_record(self, session: Session) -> dict[str, Any]:
        return session.to_dict()

    async def create_session(
        self,
        session_id: str,
        task_id: str,
        agent: str,
    ) -> Session:
        """Create a new session.

        Note: Database is already scoped to project (schema v2.0.0).

        Args:
            session_id: Unique session identifier
            task_id: Task this session belongs to
            agent: Agent identifier

        Returns:
            Created session
        """
        now = datetime.now()
        session = Session(
            id=session_id,
            task_id=task_id,
            agent=agent,
            created_at=now,
            updated_at=now,
        )

        # Use session_id as record ID (database is already project-scoped)
        await self.create(session.to_dict(), session_id)

        logger.debug(f"Created session {session_id} for task {task_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                """
                SELECT * FROM sessions
                WHERE session_id = $session_id
                LIMIT 1
                """,
                {"session_id": session_id},
            )
            if results:
                return self._to_record(results[0])
            return None

    async def get_active_session(self, task_id: str) -> Optional[Session]:
        """Get active session for a task.

        Args:
            task_id: Task identifier

        Returns:
            Active session if exists
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                """
                SELECT * FROM sessions
                WHERE task_id = $task_id
                    AND status = "active"
                ORDER BY created_at DESC
                LIMIT 1
                """,
                {"task_id": task_id},
            )
            if results:
                return self._to_record(results[0])
            return None

    async def record_invocation(
        self,
        session_id: str,
        cost_usd: float = 0.0,
    ) -> Optional[Session]:
        """Record an invocation in the session.

        Args:
            session_id: Session identifier
            cost_usd: Cost of this invocation

        Returns:
            Updated session
        """
        async with get_connection(self.project_name) as conn:
            result = await conn.query(
                """
                UPDATE sessions
                SET invocation_count += 1,
                    total_cost_usd += $cost_usd,
                    updated_at = time::now()
                WHERE session_id = $session_id
                RETURN AFTER
                """,
                {
                    "session_id": session_id,
                    "cost_usd": cost_usd,
                },
            )
            if result:
                return self._to_record(result[0])
            return None

    async def close_session(self, session_id: str) -> Optional[Session]:
        """Close a session.

        Args:
            session_id: Session identifier

        Returns:
            Closed session
        """
        async with get_connection(self.project_name) as conn:
            result = await conn.query(
                """
                UPDATE sessions
                SET status = "closed",
                    closed_at = time::now(),
                    updated_at = time::now()
                WHERE session_id = $session_id
                RETURN AFTER
                """,
                {"session_id": session_id},
            )
            if result:
                logger.debug(f"Closed session {session_id}")
                return self._to_record(result[0])
            return None

    async def close_task_sessions(self, task_id: str) -> int:
        """Close all sessions for a task.

        Args:
            task_id: Task identifier

        Returns:
            Number of sessions closed
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                """
                UPDATE sessions
                SET status = "closed",
                    closed_at = time::now(),
                    updated_at = time::now()
                WHERE task_id = $task_id
                    AND status = "active"
                RETURN BEFORE
                """,
                {"task_id": task_id},
            )
            return len(results)

    async def get_task_sessions(self, task_id: str) -> list[Session]:
        """Get all sessions for a task.

        Args:
            task_id: Task identifier

        Returns:
            List of sessions
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                """
                SELECT * FROM sessions
                WHERE task_id = $task_id
                ORDER BY created_at ASC
                """,
                {"task_id": task_id},
            )
            return [self._to_record(r) for r in results]

    async def get_total_cost(self, task_id: Optional[str] = None) -> float:
        """Get total cost across sessions.

        Args:
            task_id: Optional task filter

        Returns:
            Total cost in USD
        """
        async with get_connection(self.project_name) as conn:
            if task_id:
                results = await conn.query(
                    """
                    SELECT math::sum(total_cost_usd) as total
                    FROM sessions
                    WHERE task_id = $task_id
                    GROUP ALL
                    """,
                    {"task_id": task_id},
                )
            else:
                results = await conn.query(
                    """
                    SELECT math::sum(total_cost_usd) as total
                    FROM sessions
                    GROUP ALL
                    """,
                )

            if results:
                return results[0].get("total", 0) or 0
            return 0


# Global repository cache
_session_repos: dict[str, SessionRepository] = {}


def get_session_repository(project_name: str) -> SessionRepository:
    """Get or create session repository for a project.

    Args:
        project_name: Project name

    Returns:
        SessionRepository instance
    """
    if project_name not in _session_repos:
        _session_repos[project_name] = SessionRepository(project_name)
    return _session_repos[project_name]
