"""Tests for review gating behavior."""

from unittest.mock import AsyncMock, patch

import pytest


def test_is_docs_only_changes():
    """Docs-only detection allows markdown/text changes."""
    from orchestrator.langgraph.nodes.verification import _is_docs_only_changes

    assert _is_docs_only_changes(["README.md", "docs/guide.txt"]) is True
    assert _is_docs_only_changes(["README.md", "src/app.py"]) is False


@pytest.mark.asyncio
async def test_review_gate_docs_only_skips(temp_project_dir):
    """Review gate skips for docs-only changes under conservative policy."""
    from orchestrator.langgraph.nodes import verification as verification_module

    state = {
        "project_dir": str(temp_project_dir),
        "project_name": "test",
    }

    with patch.object(
        verification_module,
        "_collect_changed_files",
        new_callable=AsyncMock,
        return_value=["README.md"],
    ):
        result = await verification_module.review_gate_node(state)

    assert result["review_skipped"] is True
    assert result["review_skipped_reason"] == "docs_only"


@pytest.mark.asyncio
async def test_review_gate_code_changes_runs(temp_project_dir):
    """Review gate runs reviews when code files change."""
    from orchestrator.langgraph.nodes import verification as verification_module

    state = {
        "project_dir": str(temp_project_dir),
        "project_name": "test",
    }

    with patch.object(
        verification_module,
        "_collect_changed_files",
        new_callable=AsyncMock,
        return_value=["src/main.py"],
    ):
        result = await verification_module.review_gate_node(state)

    assert result["review_skipped"] is False
