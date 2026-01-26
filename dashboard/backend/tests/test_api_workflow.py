"""Tests for workflow API router."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import deps
from app.main import app


class TestStartWorkflow:
    """Tests for POST /api/projects/{project_name}/start endpoint."""

    def test_start_workflow_success(self, temp_project_dir: Path, mock_project_manager: MagicMock):
        """Test starting workflow successfully."""
        mock_orch = MagicMock()
        mock_orch.check_prerequisites.return_value = (True, [])
        mock_orch.run_langgraph.return_value = {"success": True}

        mock_project_manager.get_project.return_value = temp_project_dir

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager
        app.dependency_overrides[deps.get_project_dir] = lambda project_name: temp_project_dir
        app.dependency_overrides[deps.get_orchestrator] = lambda project_dir: mock_orch

        try:
            with patch("app.routers.workflow.Orchestrator", return_value=mock_orch):
                client = TestClient(app)
                response = client.post(
                    "/api/projects/test-project/start",
                    json={
                        "start_phase": 1,
                        "end_phase": 5,
                        "skip_validation": False,
                        "autonomous": False,
                    },
                )

                assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_start_workflow_prerequisites_failed(
        self, temp_project_dir: Path, mock_project_manager: MagicMock
    ):
        """Test starting workflow when prerequisites fail."""
        mock_orch = MagicMock()
        mock_orch.check_prerequisites.return_value = (False, ["Missing PRODUCT.md"])

        mock_project_manager.get_project.return_value = temp_project_dir

        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager
        app.dependency_overrides[deps.get_project_dir] = lambda project_name: temp_project_dir

        try:
            with patch("app.routers.workflow.Orchestrator", return_value=mock_orch):
                client = TestClient(app)
                response = client.post(
                    "/api/projects/test-project/start", json={"start_phase": 1, "end_phase": 5}
                )

                assert response.status_code == 400
                data = response.json()
                assert "error" in data["detail"]
                assert data["detail"]["error"] == "Prerequisites not met"
        finally:
            app.dependency_overrides.clear()


class TestGetWorkflowStatus:
    """Tests for GET /api/projects/{project_name}/status endpoint."""

    def test_get_workflow_status(self, client_with_mocks: TestClient):
        """Test getting workflow status."""
        response = client_with_mocks.get("/api/projects/test-project/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestGetWorkflowGraph:
    """Tests for GET /api/projects/{project_name}/graph endpoint."""

    def test_get_workflow_graph(self, client_with_mocks: TestClient):
        """Test getting workflow graph definition."""
        response = client_with_mocks.get("/api/projects/test-project/graph")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data


class TestPauseWorkflow:
    """Tests for POST /api/projects/{project_name}/pause endpoint."""

    def test_pause_workflow(self, client_with_mocks: TestClient):
        """Test pausing workflow."""
        response = client_with_mocks.post("/api/projects/test-project/pause")

        assert response.status_code == 200


class TestResetWorkflow:
    """Tests for POST /api/projects/{project_name}/reset endpoint."""

    def test_reset_workflow(self, client_with_mocks: TestClient):
        """Test resetting workflow."""
        response = client_with_mocks.post("/api/projects/test-project/reset")

        assert response.status_code == 200


class TestResumeWorkflow:
    """Tests for POST /api/projects/{project_name}/resume endpoint."""

    def test_resume_workflow(self, client_with_mocks: TestClient):
        """Test resuming workflow."""
        response = client_with_mocks.post("/api/projects/test-project/resume")

        assert response.status_code == 200
