"""Tests for session storage adapter."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from orchestrator.storage.session_adapter import (
    SessionStorageAdapter,
    get_session_storage,
)
from orchestrator.storage.base import SessionData


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        workflow_dir = project_dir / ".workflow"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "sessions").mkdir()
        yield project_dir


class TestSessionStorageAdapter:
    """Tests for SessionStorageAdapter."""

    def test_init(self, temp_project):
        """Test adapter initialization."""
        adapter = SessionStorageAdapter(temp_project)
        assert adapter.project_dir == temp_project
        assert adapter.project_name == temp_project.name

    def test_create_session(self, temp_project):
        """Test creating a new session."""
        adapter = SessionStorageAdapter(temp_project)
        session = adapter.create_session("T1", agent="claude")

        assert isinstance(session, SessionData)
        assert session.task_id == "T1"
        assert session.agent == "claude"
        assert session.status == "active"

    def test_get_active_session_none(self, temp_project):
        """Test get_active_session returns None when no session."""
        adapter = SessionStorageAdapter(temp_project)
        session = adapter.get_active_session("nonexistent")
        assert session is None

    def test_get_active_session_exists(self, temp_project):
        """Test get_active_session returns session when exists."""
        adapter = SessionStorageAdapter(temp_project)

        # Create session first
        created = adapter.create_session("T1")

        # Get it back
        session = adapter.get_active_session("T1")
        assert session is not None
        assert session.task_id == "T1"

    def test_get_resume_args_no_session(self, temp_project):
        """Test get_resume_args returns empty when no session."""
        adapter = SessionStorageAdapter(temp_project)
        args = adapter.get_resume_args("nonexistent")
        assert args == []

    def test_get_resume_args_with_session(self, temp_project):
        """Test get_resume_args returns args when session exists."""
        adapter = SessionStorageAdapter(temp_project)

        # Create session
        adapter.create_session("T1")

        # Get resume args
        args = adapter.get_resume_args("T1")
        assert len(args) == 2
        assert args[0] == "--resume"

    def test_get_session_id_args(self, temp_project):
        """Test get_session_id_args returns session id args."""
        adapter = SessionStorageAdapter(temp_project)

        args = adapter.get_session_id_args("T1")
        assert len(args) == 2
        assert args[0] == "--session-id"

    def test_get_or_create_session_creates(self, temp_project):
        """Test get_or_create_session creates if not exists."""
        adapter = SessionStorageAdapter(temp_project)

        session = adapter.get_or_create_session("T1")
        assert session is not None
        assert session.task_id == "T1"

    def test_get_or_create_session_returns_existing(self, temp_project):
        """Test get_or_create_session returns existing session."""
        adapter = SessionStorageAdapter(temp_project)

        # Create first
        adapter.create_session("T1")

        # Get or create should return existing
        session = adapter.get_or_create_session("T1")
        assert session is not None

    def test_close_session(self, temp_project):
        """Test closing a session."""
        adapter = SessionStorageAdapter(temp_project)

        # Create session
        adapter.create_session("T1")

        # Close it
        result = adapter.close_session("T1")
        assert result is True

        # Session should no longer be active
        session = adapter.get_active_session("T1")
        assert session is None

    def test_touch_session(self, temp_project):
        """Test touching a session updates timestamp."""
        adapter = SessionStorageAdapter(temp_project)

        # Create session
        adapter.create_session("T1")

        # Touch should not raise
        adapter.touch_session("T1")

    def test_record_invocation(self, temp_project):
        """Test recording an invocation."""
        adapter = SessionStorageAdapter(temp_project)

        # Create session
        adapter.create_session("T1")

        # Record invocation
        adapter.record_invocation("T1", cost_usd=0.05)


class TestGetSessionStorage:
    """Tests for get_session_storage factory function."""

    def test_returns_adapter(self, temp_project):
        """Test factory returns an adapter."""
        adapter = get_session_storage(temp_project)
        assert isinstance(adapter, SessionStorageAdapter)

    def test_caches_adapter(self, temp_project):
        """Test factory returns same adapter for same project."""
        adapter1 = get_session_storage(temp_project)
        adapter2 = get_session_storage(temp_project)
        assert adapter1 is adapter2
