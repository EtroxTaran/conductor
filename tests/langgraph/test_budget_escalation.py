"""Regression tests for budget check failure escalation (Fix 6).

Verifies that budget check exceptions return escalation instead of None,
preventing silent bypass of budget enforcement.
"""

from unittest.mock import MagicMock, patch

from orchestrator.langgraph.nodes.task.nodes import _check_budget_before_task


class TestBudgetCheckEscalation:
    """Verify budget check failures trigger escalation."""

    def test_attribute_error_escalates(self, tmp_path):
        """AttributeError in budget check should escalate, not return None."""
        # Create a budget manager that has config.enabled = True
        # but raises AttributeError when enforce_budget is called
        bad_manager = MagicMock()
        bad_manager.config.enabled = True
        bad_manager.enforce_budget = MagicMock(
            side_effect=AttributeError("'NoneType' has no attribute 'allowed'")
        )

        with patch(
            "orchestrator.langgraph.nodes.task.nodes.get_budget_storage",
            return_value=bad_manager,
        ):
            result = _check_budget_before_task(tmp_path, "T1")

        assert result is not None
        assert result["next_decision"] == "escalate"
        assert result["errors"][0]["type"] == "budget_check_error"

    def test_generic_exception_escalates(self, tmp_path):
        """Generic exception in budget check should escalate, not return None."""
        with patch(
            "orchestrator.langgraph.nodes.task.nodes.get_budget_storage",
            side_effect=RuntimeError("DB connection lost"),
        ):
            result = _check_budget_before_task(tmp_path, "T1")

        assert result is not None
        assert result["next_decision"] == "escalate"
        assert "Budget check failed" in result["errors"][0]["message"]

    def test_successful_budget_check_returns_none(self, tmp_path):
        """Successful budget check should still return None (OK to proceed)."""
        budget_result = MagicMock()
        budget_result.exceeded = False
        budget_result.allowed = True
        budget_result.should_abort = False
        budget_result.should_escalate = False

        manager = MagicMock()
        manager.config.enabled = True
        manager.enforce_budget.return_value = budget_result

        with patch(
            "orchestrator.langgraph.nodes.task.nodes.get_budget_storage",
            return_value=manager,
        ):
            result = _check_budget_before_task(tmp_path, "T1")

        assert result is None  # None means OK to proceed
