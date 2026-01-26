"""Tests for workflow service."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.workflow_service import WorkflowService


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    mock = MagicMock()
    mock.status.return_value = {"current_phase": 2, "status": "running"}
    mock.status_langgraph = AsyncMock(return_value={"current_phase": 2, "status": "running"})
    mock.health_check.return_value = {"healthy": True}
    mock.check_prerequisites.return_value = (True, [])
    mock.run_langgraph = AsyncMock(return_value={"success": True})
    mock.resume_langgraph = AsyncMock(return_value={"success": True})
    mock.rollback_to_phase.return_value = {"success": True}
    mock.reset.return_value = None
    return mock


@pytest.fixture
def mock_connection_manager():
    """Create mock connection manager."""
    mock = MagicMock()
    mock.broadcast_to_project = AsyncMock()
    return mock


class TestWorkflowService:
    """Tests for WorkflowService class."""

    def test_init(self, temp_project_dir: Path):
        """Test WorkflowService initialization."""
        service = WorkflowService(temp_project_dir)

        assert service.project_dir == temp_project_dir
        assert service.project_name == temp_project_dir.name
        assert service._orchestrator is None

    def test_orchestrator_property(self, temp_project_dir: Path, mock_orchestrator: MagicMock):
        """Test orchestrator property creates instance."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            orch = service.orchestrator

            assert orch == mock_orchestrator

    def test_orchestrator_cached(self, temp_project_dir: Path, mock_orchestrator: MagicMock):
        """Test orchestrator is cached."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            orch1 = service.orchestrator
            orch2 = service.orchestrator

            assert orch1 is orch2


class TestGetStatus:
    """Tests for get_status method."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, temp_project_dir: Path, mock_orchestrator: MagicMock):
        """Test get_status success."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            result = await service.get_status()

            assert result["current_phase"] == 2

    @pytest.mark.asyncio
    async def test_get_status_fallback(self, temp_project_dir: Path, mock_orchestrator: MagicMock):
        """Test get_status falls back to basic status on error."""
        mock_orchestrator.status_langgraph = AsyncMock(side_effect=Exception("LangGraph error"))
        mock_orchestrator.status.return_value = {"current_phase": 1, "fallback": True}

        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            result = await service.get_status()

            assert result["fallback"] is True


class TestGetHealth:
    """Tests for get_health method."""

    def test_get_health(self, temp_project_dir: Path, mock_orchestrator: MagicMock):
        """Test get_health returns health check."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            result = service.get_health()

            assert result["healthy"] is True


class TestCheckPrerequisites:
    """Tests for check_prerequisites method."""

    def test_check_prerequisites_success(
        self, temp_project_dir: Path, mock_orchestrator: MagicMock
    ):
        """Test check_prerequisites success."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            success, errors = service.check_prerequisites()

            assert success is True
            assert errors == []

    def test_check_prerequisites_failure(
        self, temp_project_dir: Path, mock_orchestrator: MagicMock
    ):
        """Test check_prerequisites failure."""
        mock_orchestrator.check_prerequisites.return_value = (False, ["Missing PRODUCT.md"])

        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            success, errors = service.check_prerequisites()

            assert success is False
            assert "Missing PRODUCT.md" in errors


class TestStart:
    """Tests for start method."""

    @pytest.mark.asyncio
    async def test_start_success(
        self,
        temp_project_dir: Path,
        mock_orchestrator: MagicMock,
        mock_connection_manager: MagicMock,
    ):
        """Test start workflow success."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            with patch(
                "app.services.workflow_service.get_connection_manager",
                return_value=mock_connection_manager,
            ):
                service = WorkflowService(temp_project_dir)

                result = await service.start(
                    start_phase=1,
                    end_phase=5,
                    autonomous=True,
                )

                assert result["success"] is True
                # Verify broadcasts were sent
                assert mock_connection_manager.broadcast_to_project.call_count == 2

    @pytest.mark.asyncio
    async def test_start_error(
        self,
        temp_project_dir: Path,
        mock_orchestrator: MagicMock,
        mock_connection_manager: MagicMock,
    ):
        """Test start workflow error handling."""
        mock_orchestrator.run_langgraph = AsyncMock(side_effect=Exception("Workflow failed"))

        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            with patch(
                "app.services.workflow_service.get_connection_manager",
                return_value=mock_connection_manager,
            ):
                service = WorkflowService(temp_project_dir)

                with pytest.raises(Exception, match="Workflow failed"):
                    await service.start()


class TestResume:
    """Tests for resume method."""

    @pytest.mark.asyncio
    async def test_resume_success(
        self,
        temp_project_dir: Path,
        mock_orchestrator: MagicMock,
        mock_connection_manager: MagicMock,
    ):
        """Test resume workflow success."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            with patch(
                "app.services.workflow_service.get_connection_manager",
                return_value=mock_connection_manager,
            ):
                service = WorkflowService(temp_project_dir)

                result = await service.resume(autonomous=True)

                assert result["success"] is True


class TestRollbackAndReset:
    """Tests for rollback and reset methods."""

    def test_rollback(self, temp_project_dir: Path, mock_orchestrator: MagicMock):
        """Test rollback to phase."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            result = service.rollback(2)

            assert result["success"] is True
            mock_orchestrator.rollback_to_phase.assert_called_once_with(2)

    def test_reset(self, temp_project_dir: Path, mock_orchestrator: MagicMock):
        """Test reset workflow."""
        with patch("app.services.workflow_service.Orchestrator", return_value=mock_orchestrator):
            service = WorkflowService(temp_project_dir)

            service.reset()

            mock_orchestrator.reset.assert_called_once()
