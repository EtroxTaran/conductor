"""Tests for project service."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.project_service import ProjectService


@pytest.fixture
def mock_project_manager():
    """Create mock project manager."""
    mock = MagicMock()
    mock.list_projects.return_value = []
    mock.get_project.return_value = None
    mock.get_project_status.return_value = {}
    mock.init_project.return_value = {"success": True}
    return mock


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    mock = MagicMock()
    mock.conductor_root = Path("/test/conductor")
    mock.projects_path = Path("/test/projects")
    return mock


class TestProjectService:
    """Tests for ProjectService class."""

    def test_init_with_manager(self, mock_project_manager: MagicMock):
        """Test ProjectService initialization with manager."""
        service = ProjectService(project_manager=mock_project_manager)

        assert service._project_manager == mock_project_manager

    def test_init_without_manager(self, mock_settings: MagicMock):
        """Test ProjectService initialization without manager."""
        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService()

            assert service._project_manager is None

    def test_project_manager_property(
        self, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test project_manager property creates instance."""
        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            with patch(
                "app.services.project_service.ProjectManager", return_value=mock_project_manager
            ):
                service = ProjectService()

                pm = service.project_manager

                assert pm == mock_project_manager


class TestListProjects:
    """Tests for list_projects method."""

    def test_list_projects_empty(self, mock_settings: MagicMock, mock_project_manager: MagicMock):
        """Test list_projects with no projects."""
        mock_project_manager.list_projects.return_value = []

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.list_projects()

            assert result == []

    def test_list_projects_with_projects(
        self, temp_project_dir: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test list_projects with existing projects."""
        mock_project_manager.list_projects.return_value = [
            {"name": "project1", "path": str(temp_project_dir)}
        ]

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.list_projects()

            assert len(result) == 1
            assert "workflow_status" in result[0]
            assert "last_activity" in result[0]


class TestGetProject:
    """Tests for get_project method."""

    def test_get_project_not_found(self, mock_settings: MagicMock, mock_project_manager: MagicMock):
        """Test get_project when project doesn't exist."""
        mock_project_manager.get_project.return_value = None

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.get_project("nonexistent")

            assert result is None

    def test_get_project_error(self, mock_settings: MagicMock, mock_project_manager: MagicMock):
        """Test get_project when status has error."""
        mock_project_manager.get_project.return_value = Path("/test")
        mock_project_manager.get_project_status.return_value = {"error": "Not found"}

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.get_project("test")

            assert result is None

    def test_get_project_success(
        self, temp_project_dir: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test get_project success."""
        mock_project_manager.get_project.return_value = temp_project_dir
        mock_project_manager.get_project_status.return_value = {"name": "test"}

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.get_project("test")

            assert result is not None
            assert "workflow_status" in result


class TestInitProject:
    """Tests for init_project method."""

    def test_init_project(self, mock_settings: MagicMock, mock_project_manager: MagicMock):
        """Test init_project."""
        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.init_project("new-project")

            assert result["success"] is True
            mock_project_manager.init_project.assert_called_once_with("new-project")


class TestGetProjectDir:
    """Tests for get_project_dir method."""

    def test_get_project_dir(self, mock_settings: MagicMock, mock_project_manager: MagicMock):
        """Test get_project_dir."""
        expected_path = Path("/test/project")
        mock_project_manager.get_project.return_value = expected_path

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.get_project_dir("test")

            assert result == expected_path


class TestListWorkspaceFolders:
    """Tests for list_workspace_folders method."""

    def test_list_workspace_folders_not_exists(
        self, tmp_path: Path, mock_project_manager: MagicMock
    ):
        """Test list_workspace_folders when workspace doesn't exist."""
        mock_settings = MagicMock()
        mock_settings.projects_path = tmp_path / "nonexistent"

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.list_workspace_folders()

            assert result == []

    def test_list_workspace_folders_with_folders(
        self, tmp_path: Path, mock_project_manager: MagicMock
    ):
        """Test list_workspace_folders with folders."""
        # Create test folders
        (tmp_path / "project1").mkdir()
        (tmp_path / "project1" / ".workflow").mkdir()
        (tmp_path / "project1" / "PRODUCT.md").write_text("# Product")
        (tmp_path / "project2").mkdir()
        (tmp_path / ".hidden").mkdir()  # Should be excluded

        mock_settings = MagicMock()
        mock_settings.projects_path = tmp_path

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service.list_workspace_folders()

            assert len(result) == 2
            project1 = next(f for f in result if f["name"] == "project1")
            assert project1["has_workflow"] is True
            assert project1["has_product_md"] is True


class TestHelperMethods:
    """Tests for helper methods."""

    def test_has_product_md_root(
        self, tmp_path: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test _has_product_md with PRODUCT.md in root."""
        (tmp_path / "PRODUCT.md").write_text("# Product")

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service._has_product_md(tmp_path)

            assert result is True

    def test_has_product_md_docs(
        self, tmp_path: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test _has_product_md with PRODUCT.md in Docs."""
        (tmp_path / "Docs").mkdir()
        (tmp_path / "Docs" / "PRODUCT.md").write_text("# Product")

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service._has_product_md(tmp_path)

            assert result is True

    def test_get_workflow_status_not_started(
        self, tmp_path: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test _get_workflow_status when not started."""
        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service._get_workflow_status(tmp_path)

            assert result == "not_started"

    def test_get_workflow_status_in_progress(
        self, tmp_path: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test _get_workflow_status when in progress."""
        state_dir = tmp_path / ".workflow"
        state_dir.mkdir()
        (state_dir / "state.json").write_text(json.dumps({"current_phase": 3}))

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service._get_workflow_status(tmp_path)

            assert result == "in_progress"

    def test_get_last_activity(
        self, tmp_path: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test _get_last_activity."""
        state_dir = tmp_path / ".workflow"
        state_dir.mkdir()
        (state_dir / "state.json").write_text(json.dumps({"updated_at": "2026-01-26T12:00:00"}))

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service._get_last_activity(tmp_path)

            assert result == "2026-01-26T12:00:00"

    def test_get_task_summary_empty(
        self, tmp_path: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test _get_task_summary with no plan."""
        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service._get_task_summary(tmp_path)

            assert result["total"] == 0

    def test_get_task_summary_with_tasks(
        self, tmp_path: Path, mock_settings: MagicMock, mock_project_manager: MagicMock
    ):
        """Test _get_task_summary with tasks."""
        plan_dir = tmp_path / ".workflow" / "phases" / "planning"
        plan_dir.mkdir(parents=True)
        plan = {
            "tasks": [
                {"status": "completed"},
                {"status": "in_progress"},
                {"status": "pending"},
            ]
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan))

        with patch("app.services.project_service.get_settings", return_value=mock_settings):
            service = ProjectService(project_manager=mock_project_manager)

            result = service._get_task_summary(tmp_path)

            assert result["total"] == 3
            assert result["completed"] == 1
            assert result["in_progress"] == 1
            assert result["pending"] == 1
