"""Tests for database service."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.db_service import DatabaseService


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    mock = MagicMock()
    mock.use_surrealdb = True
    return mock


@pytest.fixture
def mock_connection():
    """Create mock database connection."""
    mock = AsyncMock()
    mock.query = AsyncMock(return_value=[])
    mock.live_query = AsyncMock()
    return mock


class TestDatabaseService:
    """Tests for DatabaseService class."""

    def test_init(self):
        """Test DatabaseService initialization."""
        service = DatabaseService(project_name="test-project")

        assert service.project_name == "test-project"
        assert service._connection is None

    def test_is_enabled_true(self, mock_settings: MagicMock):
        """Test is_enabled when SurrealDB is enabled."""
        mock_settings.use_surrealdb = True

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            service = DatabaseService()
            assert service.is_enabled is True

    def test_is_enabled_false(self, mock_settings: MagicMock):
        """Test is_enabled when SurrealDB is disabled."""
        mock_settings.use_surrealdb = False

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            service = DatabaseService()
            assert service.is_enabled is False


class TestGetConnection:
    """Tests for get_connection method."""

    @pytest.mark.asyncio
    async def test_get_connection_disabled(self, mock_settings: MagicMock):
        """Test get_connection when SurrealDB is disabled."""
        mock_settings.use_surrealdb = False

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            service = DatabaseService()

            with pytest.raises(RuntimeError, match="SurrealDB is not enabled"):
                await service.get_connection()

    @pytest.mark.asyncio
    async def test_get_connection_success(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_connection success."""
        mock_settings.use_surrealdb = True

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                conn = await service.get_connection()

                assert conn == mock_connection

    @pytest.mark.asyncio
    async def test_get_connection_cached(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_connection returns cached connection."""
        mock_settings.use_surrealdb = True

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                conn1 = await service.get_connection()
                conn2 = await service.get_connection()

                assert conn1 is conn2


class TestQuery:
    """Tests for query method."""

    @pytest.mark.asyncio
    async def test_query_success(self, mock_settings: MagicMock, mock_connection: AsyncMock):
        """Test query execution."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = [{"id": "1", "name": "test"}]

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.query("SELECT * FROM test")

                assert result == [{"id": "1", "name": "test"}]
                mock_connection.query.assert_called_once_with("SELECT * FROM test", {})

    @pytest.mark.asyncio
    async def test_query_with_params(self, mock_settings: MagicMock, mock_connection: AsyncMock):
        """Test query with parameters."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = []

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                await service.query("SELECT * FROM test WHERE id = $id", {"id": "123"})

                mock_connection.query.assert_called_once_with(
                    "SELECT * FROM test WHERE id = $id", {"id": "123"}
                )


class TestGetWorkflowState:
    """Tests for get_workflow_state method."""

    @pytest.mark.asyncio
    async def test_get_workflow_state_found(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_workflow_state when state exists."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = [{"current_phase": 2, "status": "running"}]

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_workflow_state(Path("/test/project"))

                assert result == {"current_phase": 2, "status": "running"}

    @pytest.mark.asyncio
    async def test_get_workflow_state_not_found(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_workflow_state when state doesn't exist."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = []

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_workflow_state(Path("/test/project"))

                assert result is None


class TestGetTasks:
    """Tests for get_tasks method."""

    @pytest.mark.asyncio
    async def test_get_tasks_no_filter(self, mock_settings: MagicMock, mock_connection: AsyncMock):
        """Test get_tasks without status filter."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = [{"id": "T1"}, {"id": "T2"}]

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_tasks("test-project")

                assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_tasks_with_status(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_tasks with status filter."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = [{"id": "T1", "status": "pending"}]

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_tasks("test-project", status="pending")

                assert len(result) == 1


class TestGetAuditEntries:
    """Tests for get_audit_entries method."""

    @pytest.mark.asyncio
    async def test_get_audit_entries_basic(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_audit_entries basic query."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = [{"agent": "claude", "action": "test"}]

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_audit_entries("test-project")

                assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_audit_entries_with_filters(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_audit_entries with all filters."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = []

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_audit_entries(
                    "test-project",
                    agent="claude",
                    task_id="T1",
                    since=datetime(2026, 1, 1),
                    limit=50,
                )

                assert result == []


class TestGetAuditStatistics:
    """Tests for get_audit_statistics method."""

    @pytest.mark.asyncio
    async def test_get_audit_statistics_with_data(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_audit_statistics with data."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = [
            {
                "total": 100,
                "success_count": 80,
                "failed_count": 15,
                "timeout_count": 5,
                "total_cost_usd": 10.5,
                "total_duration_seconds": 3600,
                "avg_duration_seconds": 36,
            }
        ]

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_audit_statistics("test-project")

                assert result["total"] == 100
                assert result["success_rate"] == 0.8
                assert result["total_cost_usd"] == 10.5

    @pytest.mark.asyncio
    async def test_get_audit_statistics_empty(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_audit_statistics with no data."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = []

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_audit_statistics("test-project")

                assert result["total"] == 0
                assert result["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_get_audit_statistics_with_since(
        self, mock_settings: MagicMock, mock_connection: AsyncMock
    ):
        """Test get_audit_statistics with since filter."""
        mock_settings.use_surrealdb = True
        mock_connection.query.return_value = [{"total": 50, "success_count": 40}]

        with patch("app.services.db_service.get_settings", return_value=mock_settings):
            with patch(
                "orchestrator.db.get_connection",
                new_callable=AsyncMock,
                return_value=mock_connection,
            ):
                service = DatabaseService()
                result = await service.get_audit_statistics(
                    "test-project", since=datetime(2026, 1, 1)
                )

                assert result["total"] == 50
