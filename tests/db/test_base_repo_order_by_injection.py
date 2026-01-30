"""Regression tests for SQL injection via order_by in BaseRepository.

Verifies that the order_by parameter in find_all() is validated
against the allowed fields allowlist, and malicious values fall
back to 'created_at'.
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.db.repositories.base import BaseRepository


class TestOrderByInjectionRegression:
    """Regression: order_by must be validated to prevent SQL injection."""

    @pytest.fixture
    def repo(self):
        """Create a BaseRepository instance for testing."""
        repo = BaseRepository(project_name="test-project")
        repo.table_name = "phase_outputs"
        return repo

    @pytest.mark.asyncio
    async def test_valid_order_by_passes_through(self, repo):
        """Valid field names should be used as-is."""
        mock_conn = AsyncMock()
        mock_conn.query = AsyncMock(return_value=[])

        with patch("orchestrator.db.repositories.base.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            await repo.find_all(order_by="created_at")

            query_str = mock_conn.query.call_args[0][0]
            assert "ORDER BY created_at" in query_str

    @pytest.mark.asyncio
    async def test_malicious_order_by_falls_back_to_created_at(self, repo, caplog):
        """Malicious order_by values must fall back to 'created_at'."""
        mock_conn = AsyncMock()
        mock_conn.query = AsyncMock(return_value=[])

        with patch("orchestrator.db.repositories.base.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            with caplog.at_level(logging.WARNING):
                await repo.find_all(order_by="created_at; DELETE FROM tasks")

            query_str = mock_conn.query.call_args[0][0]
            assert "ORDER BY created_at" in query_str
            assert "DELETE" not in query_str
            assert "Invalid order_by field" in caplog.text

    @pytest.mark.asyncio
    async def test_drop_table_injection_blocked(self, repo, caplog):
        """DROP TABLE injection via order_by must be blocked."""
        mock_conn = AsyncMock()
        mock_conn.query = AsyncMock(return_value=[])

        with patch("orchestrator.db.repositories.base.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            with caplog.at_level(logging.WARNING):
                await repo.find_all(order_by="id; DROP TABLE workflow_state")

            query_str = mock_conn.query.call_args[0][0]
            assert "DROP" not in query_str
            assert "ORDER BY created_at" in query_str

    @pytest.mark.asyncio
    async def test_unknown_field_falls_back(self, repo, caplog):
        """Fields not in the allowlist should fall back."""
        mock_conn = AsyncMock()
        mock_conn.query = AsyncMock(return_value=[])

        with patch("orchestrator.db.repositories.base.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=False)

            with caplog.at_level(logging.WARNING):
                await repo.find_all(order_by="nonexistent_field_xyz")

            query_str = mock_conn.query.call_args[0][0]
            assert "ORDER BY created_at" in query_str
