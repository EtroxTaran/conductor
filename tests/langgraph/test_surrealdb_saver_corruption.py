"""Regression tests for checkpoint deserialization crash handling (Fix 4).

Verifies that corrupted JSON in checkpoints returns None from aget_tuple
and skips corrupted rows in alist, rather than crashing the workflow.
"""

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.langgraph.surrealdb_saver import SurrealDBSaver


class FakeSerde:
    """Fake serializer for testing."""

    def loads_typed(self, data):
        return {"deserialized": True}

    def dumps_typed(self, data):
        return ("pickle", b"fake-bytes")


@pytest.fixture
def saver():
    """Create a SurrealDBSaver with fake serde."""
    s = SurrealDBSaver.__new__(SurrealDBSaver)
    s.project_name = "test-project"
    s.serde = FakeSerde()
    return s


class TestDeserializeBlob:
    """Tests for _deserialize_blob helper."""

    def test_valid_blob_deserializes(self, saver):
        """Valid JSON+base64 blob should deserialize successfully."""
        import base64

        blob = json.dumps(
            {
                "type": "pickle",
                "data": base64.b64encode(b"test-data").decode("utf-8"),
            }
        )
        result = saver._deserialize_blob(blob, "test")
        assert result == {"deserialized": True}

    def test_invalid_json_raises_value_error(self, saver):
        """Invalid JSON should raise ValueError."""
        with pytest.raises(ValueError, match="Corrupted test"):
            saver._deserialize_blob("not-json{{{", "test")

    def test_missing_keys_raises_value_error(self, saver):
        """Missing 'type' or 'data' keys should raise ValueError."""
        blob = json.dumps({"wrong": "keys"})
        with pytest.raises(ValueError, match="Corrupted test"):
            saver._deserialize_blob(blob, "test")

    def test_invalid_base64_raises_value_error(self, saver):
        """Invalid base64 data should raise ValueError."""
        blob = json.dumps({"type": "pickle", "data": "not-valid-base64!!!"})
        # This might pass base64 decode but fail serde, either way should be ValueError
        saver_bad = SurrealDBSaver.__new__(SurrealDBSaver)
        saver_bad.project_name = "test"

        class BadSerde:
            def loads_typed(self, data):
                raise RuntimeError("corrupt data")

        saver_bad.serde = BadSerde()
        with pytest.raises(ValueError, match="Corrupted"):
            saver_bad._deserialize_blob(blob, "checkpoint")


class TestAgetTupleCorruption:
    """Tests for aget_tuple with corrupted data."""

    @pytest.mark.asyncio
    async def test_corrupted_checkpoint_returns_none(self, saver, caplog):
        """Corrupted checkpoint JSON should return None, not crash."""
        mock_conn = AsyncMock()
        mock_conn.query = AsyncMock(
            return_value=[
                {
                    "checkpoint": "corrupted-not-json",
                    "metadata": "also-corrupted",
                    "checkpoint_id": "cp-123",
                    "parent_checkpoint_id": None,
                }
            ]
        )

        config = {
            "configurable": {
                "thread_id": "test-thread",
                "checkpoint_ns": "",
            }
        }

        with patch("orchestrator.langgraph.surrealdb_saver.get_connection") as mock_get_conn:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_conn.return_value = mock_ctx

            with caplog.at_level(logging.ERROR, logger="orchestrator.langgraph.surrealdb_saver"):
                result = await saver.aget_tuple(config)

        assert result is None
        assert "Skipping corrupted checkpoint" in caplog.text


class TestAlistCorruption:
    """Tests for alist with corrupted data."""

    @pytest.mark.asyncio
    async def test_corrupted_rows_skipped_in_alist(self, saver, caplog):
        """Corrupted rows in alist should be skipped, not crash."""
        import base64

        valid_blob = json.dumps(
            {
                "type": "pickle",
                "data": base64.b64encode(b"valid").decode("utf-8"),
            }
        )

        mock_conn = AsyncMock()
        mock_conn.query = AsyncMock(
            return_value=[
                {
                    "checkpoint": "corrupted-json",
                    "metadata": "corrupted",
                    "checkpoint_id": "cp-bad",
                    "parent_checkpoint_id": None,
                },
                {
                    "checkpoint": valid_blob,
                    "metadata": valid_blob,
                    "checkpoint_id": "cp-good",
                    "parent_checkpoint_id": None,
                },
            ]
        )

        config = {
            "configurable": {
                "thread_id": "test-thread",
                "checkpoint_ns": "",
            }
        }

        with patch("orchestrator.langgraph.surrealdb_saver.get_connection") as mock_get_conn:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_get_conn.return_value = mock_ctx

            results = []
            with caplog.at_level(logging.ERROR, logger="orchestrator.langgraph.surrealdb_saver"):
                async for item in saver.alist(config):
                    results.append(item)

        # Bad row skipped, good row yielded
        assert len(results) == 1
        assert results[0].config["configurable"]["checkpoint_id"] == "cp-good"
        assert "Skipping corrupted checkpoint in list" in caplog.text
