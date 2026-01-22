"""Budget storage adapter.

Provides unified interface for budget tracking with automatic backend selection.
Uses SurrealDB when enabled, falls back to file-based JSON otherwise.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .async_utils import run_async
from .base import BudgetRecordData, BudgetStorageProtocol, BudgetSummaryData

logger = logging.getLogger(__name__)


class BudgetStorageAdapter(BudgetStorageProtocol):
    """Storage adapter for budget tracking.

    Automatically selects between file-based and SurrealDB backends
    based on configuration. Provides a unified interface for budget
    operations.

    Note: This adapter focuses on the storage operations. For budget
    enforcement logic (can_spend checks, limits), use BudgetManager
    which wraps this adapter.

    Usage:
        adapter = BudgetStorageAdapter(project_dir)

        # Record spending
        adapter.record_spend("T1", "claude", 0.05, model="sonnet")

        # Get task spending
        spent = adapter.get_task_spent("T1")

        # Check remaining budget
        remaining = adapter.get_task_remaining("T1", budget_limit=5.0)

        # Get summary
        summary = adapter.get_summary()
    """

    def __init__(
        self,
        project_dir: Path,
        project_name: Optional[str] = None,
    ):
        """Initialize budget storage adapter.

        Args:
            project_dir: Project directory
            project_name: Project name (defaults to directory name)
        """
        self.project_dir = Path(project_dir)
        self.project_name = project_name or self.project_dir.name

        # Lazy-initialized backends
        self._file_backend: Optional[Any] = None
        self._db_backend: Optional[Any] = None

    @property
    def _use_db(self) -> bool:
        """Check if SurrealDB should be used."""
        try:
            from orchestrator.db import is_surrealdb_enabled
            return is_surrealdb_enabled()
        except ImportError:
            return False

    def _get_file_backend(self) -> Any:
        """Get or create file backend."""
        if self._file_backend is None:
            from orchestrator.agents.budget import BudgetManager
            self._file_backend = BudgetManager(self.project_dir)
        return self._file_backend

    def _get_db_backend(self) -> Any:
        """Get or create database backend."""
        if self._db_backend is None:
            from orchestrator.db.repositories.budget import get_budget_repository
            self._db_backend = get_budget_repository(self.project_name)
        return self._db_backend

    def record_spend(
        self,
        task_id: str,
        agent: str,
        cost_usd: float,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        model: Optional[str] = None,
    ) -> None:
        """Record a spending event.

        Args:
            task_id: Task that incurred the cost
            agent: Agent that incurred the cost
            cost_usd: Cost in USD
            tokens_input: Input token count
            tokens_output: Output token count
            model: Model used
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                run_async(
                    db.record_spend(
                        agent=agent,
                        cost_usd=cost_usd,
                        task_id=task_id,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        model=model,
                    )
                )
                return
            except Exception as e:
                logger.warning(f"Failed to record DB spend, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        file_backend.record_spend(
            task_id=task_id,
            agent=agent,
            amount_usd=cost_usd,
            model=model,
            prompt_tokens=tokens_input,
            completion_tokens=tokens_output,
        )

    def get_task_spent(self, task_id: str) -> float:
        """Get total spent for a task.

        Args:
            task_id: Task identifier

        Returns:
            Total spent in USD
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                return run_async(db.get_task_cost(task_id))
            except Exception as e:
                logger.warning(f"Failed to get DB task cost, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend.get_task_spent(task_id)

    def get_task_remaining(self, task_id: str) -> Optional[float]:
        """Get remaining budget for a task.

        Args:
            task_id: Task identifier

        Returns:
            Remaining budget in USD, or None if unlimited
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                # DB backend doesn't track task budgets the same way
                # Return None to indicate unlimited
                return None
            except Exception as e:
                logger.warning(f"Failed to get DB remaining, falling back to file: {e}")

        # File backend has task budget tracking
        file_backend = self._get_file_backend()
        return file_backend.get_task_remaining(task_id)

    def can_spend(
        self,
        task_id: str,
        amount_usd: float,
        raise_on_exceeded: bool = False,
    ) -> bool:
        """Check if spending amount is within budget.

        Args:
            task_id: Task identifier
            amount_usd: Amount to spend
            raise_on_exceeded: Whether to raise BudgetExceeded if over limit

        Returns:
            True if within budget
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                task_cost = run_async(db.get_task_cost(task_id))
                # Use a default budget limit if not tracked in DB
                # This is a simplification - could be enhanced
                return True  # DB doesn't enforce limits by default
            except Exception as e:
                logger.warning(f"Failed to check DB budget, falling back to file: {e}")

        # File backend has full budget enforcement logic
        file_backend = self._get_file_backend()
        return file_backend.can_spend(task_id, amount_usd, raise_on_exceeded)

    def get_invocation_budget(self, task_id: str, default: float = 1.0) -> float:
        """Get the per-invocation budget for a task.

        This returns the budget to pass to --max-budget-usd.

        Args:
            task_id: Task identifier
            default: Default budget if not configured

        Returns:
            Per-invocation budget in USD
        """
        # For now, we use a simple approach
        # Could be enhanced to check project config or task complexity
        if self._use_db:
            # DB backend doesn't have invocation budget concept
            return default

        # File backend has invocation budget config
        file_backend = self._get_file_backend()
        return file_backend.get_invocation_budget(task_id)

    def get_summary(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> BudgetSummaryData:
        """Get budget summary.

        Args:
            since: Start time
            until: End time

        Returns:
            BudgetSummaryData summary
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                summary = run_async(db.get_summary(since=since, until=until))
                return BudgetSummaryData(
                    total_cost_usd=summary.total_cost_usd,
                    total_tokens_input=summary.total_tokens_input,
                    total_tokens_output=summary.total_tokens_output,
                    record_count=summary.record_count,
                    by_agent=summary.by_agent,
                    by_task=summary.by_task,
                    by_model=summary.by_model,
                )
            except Exception as e:
                logger.warning(f"Failed to get DB summary, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        status = file_backend.get_budget_status()
        task_report = file_backend.get_task_spending_report()

        # Build by_agent from records
        by_agent: dict[str, float] = {}
        by_model: dict[str, float] = {}
        for record in file_backend._state.records:
            agent = record.get("agent", "unknown")
            by_agent[agent] = by_agent.get(agent, 0) + record.get("amount_usd", 0)
            model = record.get("model")
            if model:
                by_model[model] = by_model.get(model, 0) + record.get("amount_usd", 0)

        return BudgetSummaryData(
            total_cost_usd=status.get("total_spent_usd", 0.0),
            total_tokens_input=0,  # File backend doesn't aggregate tokens
            total_tokens_output=0,
            record_count=status.get("record_count", 0),
            by_agent=by_agent,
            by_task=status.get("task_spent", {}),
            by_model=by_model,
        )

    def get_total_spent(
        self,
        since: Optional[datetime] = None,
    ) -> float:
        """Get total amount spent.

        Args:
            since: Optional start time filter

        Returns:
            Total spent in USD
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                return run_async(db.get_total_cost(since=since))
            except Exception as e:
                logger.warning(f"Failed to get DB total, falling back to file: {e}")

        # File backend
        file_backend = self._get_file_backend()
        return file_backend._state.total_spent_usd

    def get_daily_costs(self, days: int = 7) -> list[dict]:
        """Get daily cost breakdown.

        Args:
            days: Number of days to include

        Returns:
            List of daily cost records
        """
        if self._use_db:
            try:
                db = self._get_db_backend()
                return run_async(db.get_daily_costs(days))
            except Exception as e:
                logger.warning(f"Failed to get DB daily costs, falling back to file: {e}")

        # File backend - aggregate from records
        file_backend = self._get_file_backend()
        daily: dict[str, dict] = {}

        for record in file_backend._state.records:
            timestamp = record.get("timestamp", "")
            if not timestamp:
                continue

            # Extract date
            date = timestamp[:10]  # YYYY-MM-DD
            if date not in daily:
                daily[date] = {"date": date, "cost_usd": 0.0, "invocations": 0}

            daily[date]["cost_usd"] += record.get("amount_usd", 0)
            daily[date]["invocations"] += 1

        # Sort by date
        return sorted(daily.values(), key=lambda x: x["date"])

    @property
    def config(self):
        """Get budget configuration (delegates to file backend).

        Note: SurrealDB backend doesn't have the same config concept,
        so this always returns the file backend's config.
        """
        file_backend = self._get_file_backend()
        return file_backend.config

    def enforce_budget(
        self,
        task_id: str,
        amount_usd: float,
        soft_limit_percent: float = 90.0,
    ):
        """Check budget with detailed result for workflow decisions.

        Delegates to file backend for full enforcement logic.

        Args:
            task_id: Task identifier
            amount_usd: Amount to spend
            soft_limit_percent: Percentage at which to escalate

        Returns:
            BudgetEnforcementResult with detailed status
        """
        # Use file backend for enforcement logic
        # DB backend doesn't have the same enforcement concept
        file_backend = self._get_file_backend()
        return file_backend.enforce_budget(task_id, amount_usd, soft_limit_percent)


# Cache of adapters per project
_budget_adapters: dict[str, BudgetStorageAdapter] = {}


def get_budget_storage(
    project_dir: Path,
    project_name: Optional[str] = None,
) -> BudgetStorageAdapter:
    """Get or create budget storage adapter for a project.

    Args:
        project_dir: Project directory
        project_name: Project name (defaults to directory name)

    Returns:
        BudgetStorageAdapter instance
    """
    key = str(Path(project_dir).resolve())

    if key not in _budget_adapters:
        _budget_adapters[key] = BudgetStorageAdapter(project_dir, project_name)
    return _budget_adapters[key]
