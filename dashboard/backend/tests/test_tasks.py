"""Tests for tasks API router."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestListTasks:
    """Tests for GET /api/projects/{project_name}/tasks endpoint."""

    def test_list_tasks_with_fixture(self, client_with_mocks: TestClient):
        """Test listing tasks using the shared fixture with pre-populated tasks."""
        response = client_with_mocks.get("/api/projects/test-project/tasks")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # From conftest temp_project_dir
        assert len(data["tasks"]) == 2

    def test_list_tasks_filter_by_status(self, client_with_mocks: TestClient):
        """Test filtering tasks by status."""
        response = client_with_mocks.get("/api/projects/test-project/tasks?status=completed")

        assert response.status_code == 200
        data = response.json()
        # Should only return completed tasks from fixture
        assert all(t["status"] == "completed" for t in data["tasks"])


class TestGetTask:
    """Tests for GET /api/projects/{project_name}/tasks/{task_id} endpoint."""

    def test_get_task_success(self, client_with_mocks: TestClient):
        """Test getting a specific task."""
        response = client_with_mocks.get("/api/projects/test-project/tasks/T1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "T1"
        assert data["title"] == "Test Task 1"

    def test_get_task_not_found(self, client_with_mocks: TestClient):
        """Test getting a non-existent task."""
        response = client_with_mocks.get("/api/projects/test-project/tasks/NONEXISTENT")

        assert response.status_code == 404


class TestGetTaskHistory:
    """Tests for GET /api/projects/{project_name}/tasks/{task_id}/history endpoint."""

    def test_get_task_history_empty(self, client_with_mocks: TestClient):
        """Test getting task history when none exists."""
        response = client_with_mocks.get("/api/projects/test-project/tasks/T1/history")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_task_history_with_entries(
        self,
        client_with_mocks: TestClient,
        mock_audit_adapter: MagicMock,
    ):
        """Test getting task history with audit entries."""
        # Create mock audit entry
        mock_entry = MagicMock()
        mock_entry.id = "entry1"
        mock_entry.agent = "claude"
        mock_entry.task_id = "T1"
        mock_entry.session_id = "sess1"
        mock_entry.prompt_hash = "abc123"
        mock_entry.prompt_length = 100
        mock_entry.command_args = ["--task", "T1"]
        mock_entry.exit_code = 0
        mock_entry.status = "success"
        mock_entry.duration_seconds = 5.0
        mock_entry.output_length = 500
        mock_entry.error_length = 0
        mock_entry.parsed_output_type = "json"
        mock_entry.cost_usd = 0.01
        mock_entry.model = "claude-3"
        mock_entry.metadata = {}
        mock_entry.timestamp = None

        mock_audit_adapter.get_task_history.return_value = [mock_entry]

        response = client_with_mocks.get("/api/projects/test-project/tasks/T1/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "entry1"
        assert data[0]["agent"] == "claude"
