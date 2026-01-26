"""Tests for projects API router."""

from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app import deps
from app.main import app


class TestListProjects:
    """Tests for GET /api/projects endpoint."""

    def test_list_projects_empty(self, mock_project_manager: MagicMock):
        """Test listing projects when none exist."""
        mock_project_manager.list_projects.return_value = []

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.get("/api/projects")

            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    def test_list_projects_with_projects(self, mock_project_manager: MagicMock):
        """Test listing projects when projects exist."""
        mock_project_manager.list_projects.return_value = [
            {
                "name": "project1",
                "path": "/tmp/project1",
                "current_phase": 1,
                "has_documents": True,
                "has_product_spec": True,
                "has_claude_md": True,
                "has_gemini_md": False,
                "has_cursor_rules": False,
                "created_at": None,
            },
            {
                "name": "project2",
                "path": "/tmp/project2",
                "current_phase": 0,
                "has_documents": False,
                "has_product_spec": False,
                "has_claude_md": False,
                "has_gemini_md": False,
                "has_cursor_rules": False,
                "created_at": None,
            },
        ]

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.get("/api/projects")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["name"] == "project1"
            assert data[1]["name"] == "project2"
        finally:
            app.dependency_overrides.clear()


class TestGetProject:
    """Tests for GET /api/projects/{project_name} endpoint."""

    def test_get_project_success(self, mock_project_manager: MagicMock):
        """Test getting project details successfully."""
        mock_project_manager.get_project_status.return_value = {
            "name": "test-project",
            "path": "/tmp/test-project",
            "config": {},
            "state": {"current_phase": 1},
            "files": {"PRODUCT.md": True, "CLAUDE.md": True},
            "phases": {"planning": {"exists": True, "has_output": True}},
        }

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.get("/api/projects/test-project")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test-project"
            assert data["files"]["PRODUCT.md"] is True
        finally:
            app.dependency_overrides.clear()

    def test_get_project_not_found(self, mock_project_manager: MagicMock):
        """Test getting non-existent project."""
        # The API checks for "error" key in the status dict
        mock_project_manager.get_project_status.return_value = {
            "error": "Project 'nonexistent' not found"
        }

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.get("/api/projects/nonexistent")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestInitProject:
    """Tests for POST /api/projects/{project_name}/init endpoint."""

    def test_init_project_success(self, mock_project_manager: MagicMock):
        """Test initializing a new project."""
        mock_project_manager.init_project.return_value = {
            "success": True,
            "project_path": "/tmp/new-project",
            "files_created": ["PRODUCT.md", ".workflow/"],
        }

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.post("/api/projects/new-project/init")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_init_project_already_exists(self, mock_project_manager: MagicMock):
        """Test initializing when project already exists."""
        # The API checks for success=False, not exception
        mock_project_manager.init_project.return_value = {
            "success": False,
            "error": "Project already exists",
        }

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.post("/api/projects/existing-project/init")

            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()


class TestDeleteProject:
    """Tests for DELETE /api/projects/{project_name} endpoint."""

    def test_delete_project_success(self, temp_project_dir: Path, mock_project_manager: MagicMock):
        """Test deleting a project."""
        mock_project_manager.get_project.return_value = temp_project_dir

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.delete("/api/projects/test-project")

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_delete_project_not_found(self, mock_project_manager: MagicMock):
        """Test deleting non-existent project."""
        mock_project_manager.get_project.return_value = None

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.delete("/api/projects/nonexistent")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestListWorkspaceFolders:
    """Tests for GET /api/projects/workspace/folders endpoint."""

    def test_list_folders_empty(self, tmp_path: Path, mock_project_manager: MagicMock):
        """Test listing folders when workspace is empty."""
        # Need to mock the settings to point to empty temp dir
        from unittest.mock import patch

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            with patch("app.routers.projects.get_settings") as mock_settings:
                mock_settings.return_value.projects_path = tmp_path

                client = TestClient(app)
                response = client.get("/api/projects/workspace/folders")

                assert response.status_code == 200
                assert response.json() == []
        finally:
            app.dependency_overrides.clear()

    def test_list_folders_with_folders(self, tmp_path: Path, mock_project_manager: MagicMock):
        """Test listing folders with existing folders."""
        from unittest.mock import patch

        # Create some test folders
        (tmp_path / "project1").mkdir()
        (tmp_path / "project1" / ".workflow").mkdir()
        (tmp_path / "project1" / "PRODUCT.md").write_text("# Test")
        (tmp_path / "random-folder").mkdir()

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            with patch("app.routers.projects.get_settings") as mock_settings:
                mock_settings.return_value.projects_path = tmp_path

                client = TestClient(app)
                response = client.get("/api/projects/workspace/folders")

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 2
                # Find project1 in results
                project1 = next((f for f in data if f["name"] == "project1"), None)
                assert project1 is not None
                assert project1["has_workflow"] is True
        finally:
            app.dependency_overrides.clear()


class TestProjectGuardrails:
    """Tests for project guardrails endpoints.

    Note: These endpoints interact with the database and are harder to mock.
    Integration tests would be more appropriate for full coverage.
    """

    def test_list_project_guardrails_project_not_found(
        self,
        mock_project_manager: MagicMock,
    ):
        """Test listing guardrails for non-existent project."""
        mock_project_manager.get_project.return_value = None

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.get("/api/projects/nonexistent/guardrails")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_toggle_guardrail_project_not_found(
        self,
        mock_project_manager: MagicMock,
    ):
        """Test toggling guardrail for non-existent project."""
        mock_project_manager.get_project.return_value = None

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

        try:
            client = TestClient(app)
            response = client.post("/api/projects/nonexistent/guardrails/guard1/toggle")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
