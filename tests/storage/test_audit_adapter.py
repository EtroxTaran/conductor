"""Tests for audit storage adapter."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from orchestrator.storage.audit_adapter import (
    AuditStorageAdapter,
    AuditRecordContext,
    get_audit_storage,
)
from orchestrator.storage.base import AuditEntryData, AuditStatisticsData


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        workflow_dir = project_dir / ".workflow"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "audit").mkdir()
        yield project_dir


class TestAuditStorageAdapter:
    """Tests for AuditStorageAdapter."""

    def test_init(self, temp_project):
        """Test adapter initialization."""
        adapter = AuditStorageAdapter(temp_project)
        assert adapter.project_dir == temp_project
        assert adapter.project_name == temp_project.name
        assert adapter._file_backend is None
        assert adapter._db_backend is None

    def test_init_with_project_name(self, temp_project):
        """Test adapter initialization with custom project name."""
        adapter = AuditStorageAdapter(temp_project, project_name="custom-name")
        assert adapter.project_name == "custom-name"

    @patch("orchestrator.db.is_surrealdb_enabled")
    def test_use_db_when_disabled(self, mock_enabled, temp_project):
        """Test _use_db returns False when SurrealDB not enabled."""
        mock_enabled.return_value = False
        adapter = AuditStorageAdapter(temp_project)
        assert not adapter._use_db

    @patch("orchestrator.db.is_surrealdb_enabled")
    def test_use_db_when_enabled(self, mock_enabled, temp_project):
        """Test _use_db returns True when SurrealDB enabled."""
        mock_enabled.return_value = True
        adapter = AuditStorageAdapter(temp_project)
        assert adapter._use_db

    def test_record_context_manager_file_backend(self, temp_project):
        """Test record context manager uses file backend."""
        adapter = AuditStorageAdapter(temp_project)

        with adapter.record("claude", "T1", "test prompt") as ctx:
            assert ctx is not None
            ctx.set_result(success=True, exit_code=0)

    def test_get_task_history_empty(self, temp_project):
        """Test get_task_history returns empty list for new task."""
        adapter = AuditStorageAdapter(temp_project)
        history = adapter.get_task_history("T1")
        assert history == []

    def test_get_statistics_empty(self, temp_project):
        """Test get_statistics returns zero stats for empty audit."""
        adapter = AuditStorageAdapter(temp_project)
        stats = adapter.get_statistics()

        assert isinstance(stats, AuditStatisticsData)
        assert stats.total == 0
        assert stats.success_count == 0

    def test_query_empty(self, temp_project):
        """Test query returns empty list for empty audit."""
        adapter = AuditStorageAdapter(temp_project)
        results = adapter.query()
        assert results == []


class TestAuditRecordContext:
    """Tests for AuditRecordContext."""

    def test_context_init(self):
        """Test context initialization."""
        mock_adapter = MagicMock()
        ctx = AuditRecordContext(
            adapter=mock_adapter,
            agent="claude",
            task_id="T1",
            prompt="test prompt",
        )
        # Context stores values in private attributes
        assert ctx._agent == "claude"
        assert ctx._task_id == "T1"
        assert ctx._prompt == "test prompt"

    def test_set_result(self):
        """Test setting result updates context."""
        mock_adapter = MagicMock()
        ctx = AuditRecordContext(
            adapter=mock_adapter,
            agent="claude",
            task_id="T1",
            prompt="test prompt",
        )

        ctx.set_result(
            success=True,
            exit_code=0,
            output_length=100,
            cost_usd=0.05,
        )

        # Result values stored in private attributes
        assert ctx._success is True
        assert ctx._exit_code == 0
        assert ctx._output_length == 100
        assert ctx._cost_usd == 0.05


class TestGetAuditStorage:
    """Tests for get_audit_storage factory function."""

    def test_returns_adapter(self, temp_project):
        """Test factory returns an adapter."""
        adapter = get_audit_storage(temp_project)
        assert isinstance(adapter, AuditStorageAdapter)

    def test_caches_adapter(self, temp_project):
        """Test factory returns same adapter for same project."""
        adapter1 = get_audit_storage(temp_project)
        adapter2 = get_audit_storage(temp_project)
        assert adapter1 is adapter2

    def test_different_projects_different_adapters(self):
        """Test different projects get different adapters."""
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            adapter1 = get_audit_storage(Path(tmp1))
            adapter2 = get_audit_storage(Path(tmp2))
            assert adapter1 is not adapter2
