"""Tests for budget storage adapter."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from orchestrator.storage.budget_adapter import (
    BudgetStorageAdapter,
    get_budget_storage,
)
from orchestrator.storage.base import BudgetSummaryData


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        workflow_dir = project_dir / ".workflow"
        workflow_dir.mkdir(parents=True)
        yield project_dir


@pytest.fixture
def temp_project_with_budget(temp_project):
    """Create a temporary project with budget config."""
    budget_file = temp_project / ".workflow" / "budget.json"
    budget_file.write_text(json.dumps({
        "config": {
            "enabled": True,
            "task_budget_usd": 5.0,
            "invocation_budget_usd": 1.0,
            "project_budget_usd": 50.0,
            "task_budgets": {},
            "warn_at_percent": 80.0,
        },
        "records": [],
        "task_spent": {},
        "total_spent_usd": 0.0,
    }))
    return temp_project


class TestBudgetStorageAdapter:
    """Tests for BudgetStorageAdapter."""

    def test_init(self, temp_project):
        """Test adapter initialization."""
        adapter = BudgetStorageAdapter(temp_project)
        assert adapter.project_dir == temp_project
        assert adapter.project_name == temp_project.name

    def test_record_spend(self, temp_project_with_budget):
        """Test recording spend."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        adapter.record_spend(
            task_id="T1",
            agent="claude",
            cost_usd=0.05,
            model="sonnet",
        )

        # Verify spend was recorded
        spent = adapter.get_task_spent("T1")
        assert spent == 0.05

    def test_get_task_spent_none(self, temp_project_with_budget):
        """Test get_task_spent returns 0 for unknown task."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)
        spent = adapter.get_task_spent("nonexistent")
        assert spent == 0.0

    def test_get_task_spent_after_record(self, temp_project_with_budget):
        """Test get_task_spent returns accumulated spend."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        adapter.record_spend("T1", "claude", 0.05)
        adapter.record_spend("T1", "claude", 0.10)

        spent = adapter.get_task_spent("T1")
        assert spent == pytest.approx(0.15)

    def test_get_task_remaining(self, temp_project_with_budget):
        """Test get_task_remaining returns remaining budget."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        # Spend some
        adapter.record_spend("T1", "claude", 1.0)

        # Get remaining
        remaining = adapter.get_task_remaining("T1")
        # Default task budget is 5.0, remaining should be 4.0
        assert remaining == 4.0

    def test_can_spend_true(self, temp_project_with_budget):
        """Test can_spend returns True when within budget."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        result = adapter.can_spend("T1", 0.50)
        assert result is True

    def test_can_spend_after_spending(self, temp_project_with_budget):
        """Test can_spend returns True after some spending."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        adapter.record_spend("T1", "claude", 2.0)
        result = adapter.can_spend("T1", 0.50)
        assert result is True

    def test_get_invocation_budget(self, temp_project_with_budget):
        """Test get_invocation_budget returns configured budget."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        budget = adapter.get_invocation_budget("T1")
        assert budget == 1.0

    def test_get_summary_empty(self, temp_project_with_budget):
        """Test get_summary returns empty summary."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        summary = adapter.get_summary()
        assert isinstance(summary, BudgetSummaryData)
        assert summary.total_cost_usd == 0.0

    def test_get_summary_with_records(self, temp_project_with_budget):
        """Test get_summary includes recorded spend."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        adapter.record_spend("T1", "claude", 0.05)
        adapter.record_spend("T1", "gemini", 0.03)

        summary = adapter.get_summary()
        assert summary.total_cost_usd == 0.08

    def test_get_total_spent(self, temp_project_with_budget):
        """Test get_total_spent returns total."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        adapter.record_spend("T1", "claude", 0.05)
        adapter.record_spend("T2", "claude", 0.10)

        total = adapter.get_total_spent()
        assert total == pytest.approx(0.15)

    def test_config_property(self, temp_project_with_budget):
        """Test config property returns budget config."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        config = adapter.config
        assert config is not None
        assert config.enabled is True

    def test_enforce_budget(self, temp_project_with_budget):
        """Test enforce_budget returns result."""
        adapter = BudgetStorageAdapter(temp_project_with_budget)

        result = adapter.enforce_budget("T1", 0.50)
        assert result is not None
        assert result.allowed is True


class TestGetBudgetStorage:
    """Tests for get_budget_storage factory function."""

    def test_returns_adapter(self, temp_project):
        """Test factory returns an adapter."""
        adapter = get_budget_storage(temp_project)
        assert isinstance(adapter, BudgetStorageAdapter)

    def test_caches_adapter(self, temp_project):
        """Test factory returns same adapter for same project."""
        adapter1 = get_budget_storage(temp_project)
        adapter2 = get_budget_storage(temp_project)
        assert adapter1 is adapter2
