"""Session storage adapter.

Provides unified interface for session management with automatic backend selection.
Uses SurrealDB when enabled, falls back to file-based JSON otherwise.
"""

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .async_utils import run_async
from .base import SessionData, SessionStorageProtocol

logger = logging.getLogger(__name__)


class SessionStorageAdapter(SessionStorageProtocol):
    """Storage adapter for session management.

    Automatically selects between file-based and SurrealDB backends
    based on configuration. Provides a unified interface for session
    operations.

    Usage:
        adapter = SessionStorageAdapter(project_dir)

        # Create a new session
        session = adapter.create_session("T1", agent="claude")

        # Get resume arguments
        args = adapter.get_resume_args("T1")  # ["--resume", "session-id"] or []

        # Record an invocation
        adapter.record_invocation("T1", cost_usd=0.05)

        # Close session when done
        adapter.close_session("T1")
    """

    def __init__(
        self,
        project_dir: Path,
        project_name: Optional[str] = None,
    ):
        """Initialize session storage adapter.

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
            from orchestrator.agents.session_manager import SessionManager
            self._file_backend = SessionManager(self.project_dir)
        return self._file_backend

    def _get_db_backend(self) -> Any:
        """Get or create database backend."""
        if self._db_backend is None:
            from orchestrator.db.repositories.sessions import get_session_repository
            self._db_backend = get_session_repository(self.project_name)
        return self._db_backend

    def _generate_session_id(self, task_id: str) -> str:
        """Generate a unique session ID.

        Args:
            task_id: Task identifier

        Returns:
            Generated session ID
        """
        timestamp = datetime.now().isoformat()
        random_bytes = os.urandom(4).hex()
        hash_input = f"{task_id}-{timestamp}-{random_bytes}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        return f"{task_id}-{hash_value}"

    def create_session(self, task_id: str, agent: str = "claude") -> SessionData:
        """Create a new session for a task.

        Args:
            task_id: Task identifier
            agent: Agent identifier (default: claude)

        Returns:
            SessionData for the new session
        """
        session_id = self._generate_session_id(task_id)

        if self._use_db:
            try:
                db = self._get_db_backend()
                session = run_async(
                    db.create_session(
                        session_id=session_id,
                        task_id=task_id,
                        agent=agent,
                    )
                )
                return self._db_session_to_data(session)
            except Exception as e:
                logger.warning(f"Failed to create DB session, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        session = file_backend.create_session(task_id, session_id=session_id)
        return SessionData(
            id=session.session_id,
            task_id=session.task_id,
            agent=agent,
            status="active",
            invocation_count=session.iteration,
            total_cost_usd=0.0,
            created_at=session.created_at,
            updated_at=session.last_used_at,
        )

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            SessionData if found
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                session = run_async(db.get_session(session_id))
                if session:
                    return self._db_session_to_data(session)
                return None
            except Exception as e:
                logger.warning(f"Failed to get DB session, falling back to file: {e}")

        # File backend - search by session_id
        file_backend = self._get_file_backend()
        for session in file_backend.list_sessions(include_inactive=True):
            if session.session_id == session_id:
                return SessionData(
                    id=session.session_id,
                    task_id=session.task_id,
                    agent="claude",
                    status="active" if session.is_active else "closed",
                    invocation_count=session.iteration,
                    total_cost_usd=0.0,
                    created_at=session.created_at,
                    updated_at=session.last_used_at,
                )
        return None

    def get_active_session(self, task_id: str) -> Optional[SessionData]:
        """Get the active session for a task.

        Args:
            task_id: Task identifier

        Returns:
            Active SessionData if exists
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                session = run_async(db.get_active_session(task_id))
                if session:
                    return self._db_session_to_data(session)
                return None
            except Exception as e:
                logger.warning(f"Failed to get DB active session, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        session = file_backend.get_session(task_id)
        if session:
            return SessionData(
                id=session.session_id,
                task_id=session.task_id,
                agent="claude",
                status="active",
                invocation_count=session.iteration,
                total_cost_usd=0.0,
                created_at=session.created_at,
                updated_at=session.last_used_at,
            )
        return None

    def get_resume_args(self, task_id: str) -> list[str]:
        """Get CLI arguments to resume a session.

        If a valid session exists for the task, returns:
            ["--resume", "<session_id>"]

        Otherwise returns empty list (start fresh).

        Args:
            task_id: Task identifier

        Returns:
            CLI arguments list
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                session = run_async(db.get_active_session(task_id))
                if session:
                    return ["--resume", session.id]
                return []
            except Exception as e:
                logger.warning(f"Failed to get DB resume args, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.get_resume_args(task_id)

    def get_session_id_args(self, task_id: str) -> list[str]:
        """Get CLI arguments to set a new session ID.

        If a session exists, returns its ID. Otherwise creates one.
        Returns: ["--session-id", "<session_id>"]

        Args:
            task_id: Task identifier

        Returns:
            CLI arguments list
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                session = run_async(db.get_active_session(task_id))
                if session:
                    return ["--session-id", session.id]
                # Create new session
                new_session = self.create_session(task_id)
                return ["--session-id", new_session.id]
            except Exception as e:
                logger.warning(f"Failed to get DB session ID args, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.get_session_id_args(task_id)

    def touch_session(self, task_id: str) -> None:
        """Update the session's last used timestamp.

        Args:
            task_id: Task identifier
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                session = run_async(db.get_active_session(task_id))
                if session:
                    run_async(db.touch_session(session.id))
                return
            except Exception as e:
                logger.warning(f"Failed to touch DB session, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        file_backend.touch_session(task_id)

    def capture_session_id_from_output(self, task_id: str, output: str) -> Optional[str]:
        """Capture and record session ID from CLI output.

        Some CLI responses include a session ID that should be captured
        for future resume operations.

        Args:
            task_id: Task identifier
            output: CLI output that may contain session ID

        Returns:
            Extracted session ID if found
        """
        # For DB backend, sessions are managed internally
        if self._use_db:
            return None

        # File backend handles session ID extraction
        file_backend = self._get_file_backend()
        return file_backend.capture_session_id_from_output(task_id, output)

    def close_session(self, task_id: str) -> bool:
        """Close the session for a task.

        Args:
            task_id: Task identifier

        Returns:
            True if session was closed
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                result = run_async(db.close_task_sessions(task_id))
                return result is not None
            except Exception as e:
                logger.warning(f"Failed to close DB session, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.close_session(task_id)

    def record_invocation(self, task_id: str, cost_usd: float = 0.0) -> None:
        """Record an invocation in the current session.

        Args:
            task_id: Task identifier
            cost_usd: Cost of this invocation
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                # Get active session first
                session = run_async(db.get_active_session(task_id))
                if session:
                    run_async(db.record_invocation(session.id, cost_usd))
                return
            except Exception as e:
                logger.warning(f"Failed to record DB invocation, falling back to file: {e}")

        # File backend - just touch the session (file backend doesn't track cost)
        file_backend = self._get_file_backend()
        file_backend.touch_session(task_id)

    def get_or_create_session(
        self,
        task_id: str,
        agent: str = "claude",
    ) -> SessionData:
        """Get existing session or create new one.

        Args:
            task_id: Task identifier
            agent: Agent identifier (default: claude)

        Returns:
            SessionData
        """
        session = self.get_active_session(task_id)
        if session:
            return session
        return self.create_session(task_id, agent)

    def list_sessions(
        self,
        include_inactive: bool = False,
    ) -> list[SessionData]:
        """List all sessions.

        Args:
            include_inactive: Whether to include inactive sessions

        Returns:
            List of sessions
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                sessions = run_async(db.find_all())
                result = [self._db_session_to_data(s) for s in sessions]
                if not include_inactive:
                    result = [s for s in result if s.status == "active"]
                return result
            except Exception as e:
                logger.warning(f"Failed to list DB sessions, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        sessions = file_backend.list_sessions(include_inactive)
        return [
            SessionData(
                id=s.session_id,
                task_id=s.task_id,
                agent="claude",
                status="active" if s.is_active else "closed",
                invocation_count=s.iteration,
                total_cost_usd=0.0,
                created_at=s.created_at,
                updated_at=s.last_used_at,
            )
            for s in sessions
        ]

    def delete_session(self, task_id: str) -> bool:
        """Delete a session completely.

        Args:
            task_id: Task identifier

        Returns:
            True if deleted
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                session = run_async(db.get_active_session(task_id))
                if session:
                    run_async(db.delete(session.id))
                    return True
                return False
            except Exception as e:
                logger.warning(f"Failed to delete DB session, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.delete_session(task_id)

    @staticmethod
    def _db_session_to_data(session: Any) -> SessionData:
        """Convert database session to data class."""
        return SessionData(
            id=session.id,
            task_id=session.task_id,
            agent=session.agent,
            status=session.status,
            invocation_count=session.invocation_count,
            total_cost_usd=session.total_cost_usd,
            created_at=session.created_at,
            updated_at=session.updated_at,
            closed_at=session.closed_at,
        )


# Cache of adapters per project
_session_adapters: dict[str, SessionStorageAdapter] = {}


def get_session_storage(
    project_dir: Path,
    project_name: Optional[str] = None,
) -> SessionStorageAdapter:
    """Get or create session storage adapter for a project.

    Args:
        project_dir: Project directory
        project_name: Project name (defaults to directory name)

    Returns:
        SessionStorageAdapter instance
    """
    key = str(Path(project_dir).resolve())

    if key not in _session_adapters:
        _session_adapters[key] = SessionStorageAdapter(project_dir, project_name)
    return _session_adapters[key]
