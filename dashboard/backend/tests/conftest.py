"""Shared test fixtures for dashboard backend tests.

Uses FastAPI dependency_overrides pattern to properly mock dependencies.
The override functions must match the original function signatures.
"""

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import deps
from app.main import app


# Disable rate limiting and auth for all tests
@pytest.fixture(autouse=True)
def disable_middleware_for_tests():
    """Disable rate limiting and authentication for tests."""
    # Find and disable rate limiter in the user_middleware list
    rate_limiter_config = None
    try:
        from app.middleware.rate_limit import RateLimitMiddleware

        # Find middleware in user_middleware and modify its config
        for mw in app.user_middleware:
            if mw.cls == RateLimitMiddleware:
                rate_limiter_config = mw.kwargs.get("config")
                if rate_limiter_config:
                    rate_limiter_config.enabled = False
                break
    except Exception:
        pass  # Rate limiter may not be present

    # Override auth dependency to allow all requests
    from app.auth import verify_api_key

    async def mock_verify_api_key(request=None, api_key=None):
        """Mock that matches the original verify_api_key signature."""
        return "test-mode"

    app.dependency_overrides[verify_api_key] = mock_verify_api_key

    yield

    # Clean up - re-enable rate limiter
    if rate_limiter_config:
        rate_limiter_config.enabled = True

    if verify_api_key in app.dependency_overrides:
        del app.dependency_overrides[verify_api_key]


# =============================================================================
# Mock fixtures
# =============================================================================


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with minimal structure."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # Create .workflow directory
    workflow_dir = project_dir / ".workflow"
    workflow_dir.mkdir()

    # Create phases directory
    phases_dir = workflow_dir / "phases"
    phases_dir.mkdir()

    # Create planning phase with empty plan
    planning_dir = phases_dir / "planning"
    planning_dir.mkdir()
    plan_data = {
        "tasks": [
            {
                "id": "T1",
                "title": "Test Task 1",
                "description": "A test task",
                "status": "pending",
                "priority": 1,
                "dependencies": [],
                "files_to_create": ["src/test.py"],
                "files_to_modify": [],
                "acceptance_criteria": ["Test passes"],
            },
            {
                "id": "T2",
                "title": "Test Task 2",
                "description": "Another test task",
                "status": "completed",
                "priority": 2,
                "dependencies": ["T1"],
                "files_to_create": [],
                "files_to_modify": ["src/test.py"],
                "acceptance_criteria": ["Integration works"],
            },
        ]
    }
    (planning_dir / "plan.json").write_text(json.dumps(plan_data))

    # Create state.json
    state_data = {
        "current_phase": 1,
        "status": "in_progress",
        "tasks": plan_data["tasks"],
    }
    (workflow_dir / "state.json").write_text(json.dumps(state_data))

    # Create PRODUCT.md
    (project_dir / "PRODUCT.md").write_text("# Test Product\n\nTest description.")

    return project_dir


@pytest.fixture
def mock_project_manager() -> MagicMock:
    """Create a mock ProjectManager."""
    mock_pm = MagicMock()
    mock_pm.list_projects.return_value = []
    mock_pm.get_project.return_value = Path("/tmp/test-project")
    mock_pm.get_project_status.return_value = {
        "name": "test-project",
        "path": "/tmp/test-project",
        "config": {},
        "state": {},
        "files": {"PRODUCT.md": True, "CLAUDE.md": False},
        "phases": {},
    }
    mock_pm.init_project.return_value = {"success": True}
    mock_pm.list_workspace_folders.return_value = []
    return mock_pm


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """Create a mock Orchestrator."""
    mock_orch = MagicMock()
    mock_orch.check_prerequisites.return_value = (True, [])
    mock_orch.run_langgraph.return_value = {"success": True}
    mock_orch.get_workflow_status.return_value = {"status": "idle", "current_phase": 0}
    return mock_orch


@pytest.fixture
def mock_budget_manager() -> MagicMock:
    """Create a mock BudgetManager."""
    mock_bm = MagicMock()
    mock_bm.get_budget_status.return_value = {
        "total_spent_usd": 0.0,
        "project_budget_usd": None,
        "project_remaining_usd": None,
        "project_used_percent": None,
        "task_count": 0,
        "record_count": 0,
        "task_spent": {},
        "updated_at": None,
        "enabled": True,
    }
    mock_bm.get_task_spending_report.return_value = []
    return mock_bm


@pytest.fixture
def mock_audit_adapter() -> MagicMock:
    """Create a mock AuditStorageAdapter."""
    mock_adapter = MagicMock()
    mock_adapter.query.return_value = []
    mock_stats = MagicMock()
    mock_stats.total = 0
    mock_stats.success_count = 0
    mock_stats.failed_count = 0
    mock_stats.timeout_count = 0
    mock_stats.success_rate = 0.0
    mock_stats.total_cost_usd = 0.0
    mock_stats.total_duration_seconds = 0.0
    mock_stats.avg_duration_seconds = 0.0
    mock_stats.by_agent = {}
    mock_stats.by_status = {}
    mock_adapter.get_statistics.return_value = mock_stats
    mock_adapter.get_task_history.return_value = []
    return mock_adapter


@pytest.fixture
def client_with_mocks(
    temp_project_dir: Path,
    mock_project_manager: MagicMock,
    mock_budget_manager: MagicMock,
    mock_audit_adapter: MagicMock,
) -> Generator[TestClient, None, None]:
    """Create a test client with all dependencies mocked.

    Note: FastAPI dependency overrides must match the original signatures.
    For dependencies that take parameters, we create closures that return the mock.
    """

    # Store original overrides to restore later
    original_overrides = app.dependency_overrides.copy()

    # Set up dependency overrides with matching signatures
    mock_project_manager.get_project.return_value = temp_project_dir

    # Simple override - no params
    def override_get_project_manager():
        return mock_project_manager

    # Matching signature: get_project_dir(project_name: str, project_manager: ProjectManager)
    def override_get_project_dir(project_name: str, project_manager=None):
        return temp_project_dir

    # Matching signature: get_budget_manager(project_dir: Path)
    def override_get_budget_manager(project_dir: Path = None):
        return mock_budget_manager

    # Matching signature: get_audit_adapter(project_dir: Path)
    def override_get_audit_adapter(project_dir: Path = None):
        return mock_audit_adapter

    app.dependency_overrides[deps.get_project_manager] = override_get_project_manager
    app.dependency_overrides[deps.get_project_dir] = override_get_project_dir
    app.dependency_overrides[deps.get_budget_manager] = override_get_budget_manager
    app.dependency_overrides[deps.get_audit_adapter] = override_get_audit_adapter

    yield TestClient(app)

    # Restore original overrides
    app.dependency_overrides = original_overrides


@pytest.fixture
def client() -> TestClient:
    """Simple test client without mocks (for tests that do their own mocking)."""
    return TestClient(app)


# =============================================================================
# Helper functions for manual overrides in individual tests
# =============================================================================


def setup_overrides(
    mock_project_manager: MagicMock = None,
    temp_project_dir: Path = None,
    mock_budget_manager: MagicMock = None,
    mock_audit_adapter: MagicMock = None,
):
    """Set up dependency overrides with proper signatures."""
    if mock_project_manager:
        app.dependency_overrides[deps.get_project_manager] = lambda: mock_project_manager

    if temp_project_dir:

        def override_get_project_dir(project_name: str, project_manager=None):
            return temp_project_dir

        app.dependency_overrides[deps.get_project_dir] = override_get_project_dir

    if mock_budget_manager:

        def override_get_budget_manager(project_dir: Path = None):
            return mock_budget_manager

        app.dependency_overrides[deps.get_budget_manager] = override_get_budget_manager

    if mock_audit_adapter:

        def override_get_audit_adapter(project_dir: Path = None):
            return mock_audit_adapter

        app.dependency_overrides[deps.get_audit_adapter] = override_get_audit_adapter


def clear_overrides():
    """Clear all dependency overrides."""
    app.dependency_overrides.clear()
