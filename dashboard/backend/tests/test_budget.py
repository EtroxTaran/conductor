"""Tests for budget API router."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestGetBudgetStatus:
    """Tests for GET /api/projects/{project_name}/budget endpoint."""

    def test_get_budget_status_default(self, client_with_mocks: TestClient):
        """Test getting default budget status."""
        response = client_with_mocks.get("/api/projects/test-project/budget")

        assert response.status_code == 200
        data = response.json()
        assert data["total_spent_usd"] == 0.0
        assert data["enabled"] is True

    def test_get_budget_status_with_spending(
        self,
        client_with_mocks: TestClient,
        mock_budget_manager: MagicMock,
    ):
        """Test getting budget status with spending."""
        # Update the mock to return spending data
        mock_budget_manager.get_budget_status.return_value = {
            "total_spent_usd": 15.50,
            "project_budget_usd": 100.0,
            "project_remaining_usd": 84.50,
            "project_used_percent": 15.5,
            "task_count": 5,
            "record_count": 20,
            "task_spent": {"T1": 5.00, "T2": 10.50},
            "updated_at": "2026-01-26T10:00:00",
            "enabled": True,
        }

        response = client_with_mocks.get("/api/projects/test-project/budget")

        assert response.status_code == 200
        data = response.json()
        assert data["total_spent_usd"] == 15.50
        assert data["project_budget_usd"] == 100.0


class TestGetBudgetReport:
    """Tests for GET /api/projects/{project_name}/budget/report endpoint."""

    def test_get_budget_report_empty(self, client_with_mocks: TestClient):
        """Test getting budget report with no spending."""
        response = client_with_mocks.get("/api/projects/test-project/budget/report")

        assert response.status_code == 200
        data = response.json()
        assert data["task_spending"] == []


class TestSetBudgetLimits:
    """Tests for budget limit endpoints."""

    def test_set_project_budget(
        self, client_with_mocks: TestClient, mock_budget_manager: MagicMock
    ):
        """Test setting project budget limit."""
        response = client_with_mocks.post(
            "/api/projects/test-project/budget/limit/project?limit_usd=50.0"
        )

        assert response.status_code == 200
        mock_budget_manager.set_project_budget.assert_called_once_with(50.0)

    def test_set_project_budget_unlimited(
        self, client_with_mocks: TestClient, mock_budget_manager: MagicMock
    ):
        """Test setting unlimited project budget."""
        response = client_with_mocks.post("/api/projects/test-project/budget/limit/project")

        assert response.status_code == 200
        mock_budget_manager.set_project_budget.assert_called_once_with(None)

    def test_set_task_budget(self, client_with_mocks: TestClient, mock_budget_manager: MagicMock):
        """Test setting task budget limit."""
        response = client_with_mocks.post(
            "/api/projects/test-project/budget/limit/task/T1?limit_usd=10.0"
        )

        assert response.status_code == 200
        mock_budget_manager.set_task_budget.assert_called_once_with("T1", 10.0)


class TestResetBudget:
    """Tests for budget reset endpoints."""

    def test_reset_budget(self, client_with_mocks: TestClient, mock_budget_manager: MagicMock):
        """Test resetting all budget spending."""
        response = client_with_mocks.post("/api/projects/test-project/budget/reset")

        assert response.status_code == 200
        mock_budget_manager.reset_all.assert_called_once()

    def test_reset_task_spending_success(
        self, client_with_mocks: TestClient, mock_budget_manager: MagicMock
    ):
        """Test resetting task spending."""
        mock_budget_manager.reset_task_spending.return_value = True

        response = client_with_mocks.post("/api/projects/test-project/budget/reset/task/T1")

        assert response.status_code == 200
        mock_budget_manager.reset_task_spending.assert_called_once_with("T1")

    def test_reset_task_spending_not_found(
        self, client_with_mocks: TestClient, mock_budget_manager: MagicMock
    ):
        """Test resetting non-existent task spending."""
        mock_budget_manager.reset_task_spending.return_value = False

        response = client_with_mocks.post(
            "/api/projects/test-project/budget/reset/task/NONEXISTENT"
        )

        assert response.status_code == 404
