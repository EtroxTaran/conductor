"""Regression test for SQL injection via unvalidated table_name in BaseRepository.

Verifies that:
1. Malicious table names are rejected at construction time.
2. Valid table names are accepted.
3. All existing repository subclasses construct successfully.
"""

import pytest

from orchestrator.db.repositories.base import BaseRepository
from orchestrator.security import SecurityValidationError


class MaliciousRepo(BaseRepository):
    """Repository with a SQL-injection table name."""

    table_name = "users; DROP TABLE workflow_state;--"


class ValidRepo(BaseRepository):
    """Repository with a valid table name."""

    table_name = "workflow_state"


class EmptyTableRepo(BaseRepository):
    """Repository with no table name (base class default)."""

    table_name = ""


class TestBaseRepoTableValidation:
    """Verify table_name validation in BaseRepository.__init__."""

    def test_malicious_table_name_raises_security_error(self):
        """Constructing a repo with SQL injection table name must fail."""
        with pytest.raises(SecurityValidationError):
            MaliciousRepo("test-project")

    def test_unknown_table_name_raises_security_error(self):
        """Table names not in the allowlist must be rejected."""

        class UnknownRepo(BaseRepository):
            table_name = "not_a_real_table"

        with pytest.raises(SecurityValidationError):
            UnknownRepo("test-project")

    def test_valid_table_name_accepted(self):
        """A table name from the allowlist should be accepted."""
        repo = ValidRepo("test-project")
        assert repo._validated_table == "workflow_state"

    def test_empty_table_name_accepted(self):
        """Empty table name (base class) should be accepted with empty validated."""
        repo = EmptyTableRepo("test-project")
        assert repo._validated_table == ""

    def test_all_existing_repos_construct_successfully(self):
        """Every repository subclass in the codebase should pass validation."""
        from orchestrator.db.repositories.audit import AuditRepository
        from orchestrator.db.repositories.budget import BudgetRepository
        from orchestrator.db.repositories.checkpoints import CheckpointRepository
        from orchestrator.db.repositories.evaluation import EvaluationRepository
        from orchestrator.db.repositories.logs import LogsRepository
        from orchestrator.db.repositories.phase_outputs import PhaseOutputRepository
        from orchestrator.db.repositories.prompts import (
            GoldenExampleRepository,
            OptimizationHistoryRepository,
            PromptVersionRepository,
        )
        from orchestrator.db.repositories.sessions import SessionRepository
        from orchestrator.db.repositories.tasks import TaskRepository
        from orchestrator.db.repositories.workflow import WorkflowRepository

        repos = [
            AuditRepository,
            BudgetRepository,
            CheckpointRepository,
            EvaluationRepository,
            LogsRepository,
            PhaseOutputRepository,
            PromptVersionRepository,
            GoldenExampleRepository,
            OptimizationHistoryRepository,
            SessionRepository,
            TaskRepository,
            WorkflowRepository,
        ]

        for repo_cls in repos:
            repo = repo_cls("test-project")
            assert repo._validated_table == repo_cls.table_name, (
                f"{repo_cls.__name__} table_name '{repo_cls.table_name}' " f"should pass validation"
            )
