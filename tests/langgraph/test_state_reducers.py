"""Regression tests for state reducer mutation safety and conflict detection.

Verifies that _merge_task_fields does not mutate original task objects,
preventing shared-reference race conditions in parallel execution.
Also tests conflict detection expansion (Fix 12) and truncation logging (Fix 13).
"""

import logging
from typing import Any, cast

from orchestrator.langgraph.state import (
    MAX_EXECUTION_HISTORY,
    Task,
    _append_executions,
    _detect_task_conflict,
    _merge_task_fields,
)


def _make_task(**kwargs: Any) -> Task:
    """Helper to create a minimal Task dict."""
    base: dict[str, Any] = {
        "id": "test-task",
        "title": "Test",
        "status": "pending",
        "attempts": 0,
    }
    base.update(kwargs)
    return cast(Task, base)


class TestMergeTaskFieldsMutationSafety:
    """Ensure _merge_task_fields never mutates originals."""

    def test_original_list_not_mutated_after_merge(self):
        """Lists in the existing task must not be modified by merge."""
        original_files = ["file_a.py", "file_b.py"]
        existing = _make_task(files_to_create=list(original_files))
        new = _make_task(files_to_create=["file_c.py"])

        _merge_task_fields(existing, new)

        # The original task's list must be untouched
        assert existing["files_to_create"] == original_files

    def test_original_dict_not_mutated_after_merge(self):
        """Dicts in the existing task must not be modified by merge."""
        original_metadata = {"key": "value"}
        existing = _make_task(metadata=dict(original_metadata))
        new = _make_task(metadata={"key": "new_value", "key2": "value2"})

        merged = _merge_task_fields(existing, new)

        # Original dict must be untouched
        assert existing["metadata"] == original_metadata
        # Merged should have the new values
        assert merged["metadata"]["key"] == "new_value"

    def test_higher_attempt_count_preserved(self):
        """The higher attempt count between existing and new should win."""
        existing = _make_task(attempts=3)
        new = _make_task(attempts=1)

        merged = _merge_task_fields(existing, new)
        assert merged["attempts"] == 3

        existing2 = _make_task(attempts=1)
        new2 = _make_task(attempts=5)

        merged2 = _merge_task_fields(existing2, new2)
        assert merged2["attempts"] == 5

    def test_list_merge_deduplicates(self):
        """Merging lists should not create duplicates."""
        existing = _make_task(tags=["a", "b"])
        new = _make_task(tags=["b", "c"])

        merged = _merge_task_fields(existing, new)
        assert sorted(merged["tags"]) == ["a", "b", "c"]

    def test_new_none_values_do_not_overwrite(self):
        """None values in 'new' should not overwrite existing values."""
        existing = _make_task(title="Original Title")
        new = _make_task(title=None)

        merged = _merge_task_fields(existing, new)
        assert merged["title"] == "Original Title"

    def test_parallel_merge_isolation(self):
        """Simulate parallel merges to verify no cross-contamination."""
        shared_existing = _make_task(
            files_to_create=["shared.py"],
            acceptance_criteria=["criterion_a"],
        )

        # Two parallel "new" tasks merging into the same existing
        new_a = _make_task(files_to_create=["a.py"])
        new_b = _make_task(files_to_create=["b.py"])

        merged_a = _merge_task_fields(shared_existing, new_a)
        merged_b = _merge_task_fields(shared_existing, new_b)

        # Each merged result should be independent
        assert "a.py" in merged_a["files_to_create"]
        assert "b.py" not in merged_a["files_to_create"]

        assert "b.py" in merged_b["files_to_create"]
        assert "a.py" not in merged_b["files_to_create"]

        # Original must be untouched
        assert shared_existing["files_to_create"] == ["shared.py"]


class TestDetectTaskConflictExpanded:
    """Tests for expanded conflict detection (Fix 12)."""

    def test_conflict_detected_when_both_set_error(self):
        """Conflict when both updates set different error values (Fix H8 regression)."""
        existing = _make_task(error="timeout on line 42")
        new = _make_task(error="assertion failed on line 99")

        assert _detect_task_conflict(existing, new) is True

    def test_conflict_detected_when_both_set_files_modified(self):
        """Conflict when both updates set different files_modified."""
        existing = _make_task(files_modified=["a.py", "b.py"])
        new = _make_task(files_modified=["c.py"])

        assert _detect_task_conflict(existing, new) is True

    def test_no_conflict_when_only_one_has_error(self):
        """No conflict when only one update has an error field."""
        existing = _make_task()  # No error field
        new = _make_task(error="some error")

        assert _detect_task_conflict(existing, new) is False

    def test_no_conflict_when_error_values_match(self):
        """No conflict when error values are identical."""
        existing = _make_task(error="same error")
        new = _make_task(error="same error")

        assert _detect_task_conflict(existing, new) is False

    def test_no_conflict_when_one_error_is_none(self):
        """No conflict when one error is None (initial state)."""
        existing = _make_task(error=None)
        new = _make_task(error="new error")

        assert _detect_task_conflict(existing, new) is False

    def test_conflict_detected_files_created(self):
        """Conflict when both set different files_created."""
        existing = _make_task(files_created=["x.py"])
        new = _make_task(files_created=["y.py"])

        assert _detect_task_conflict(existing, new) is True

    def test_conflict_detected_test_results(self):
        """Conflict when both set different test_results."""
        existing = _make_task(test_results={"passed": 5})
        new = _make_task(test_results={"passed": 3})

        assert _detect_task_conflict(existing, new) is True


class TestExecutionHistoryTruncation:
    """Tests for execution history truncation logging (Fix 13)."""

    def test_truncation_logs_warning(self, caplog):
        """Truncation should log a warning with drop count (Fix H10 regression)."""
        # Create a list that exceeds MAX_EXECUTION_HISTORY
        existing = [{"id": f"exec-{i}"} for i in range(MAX_EXECUTION_HISTORY)]
        new = [{"id": f"exec-new-{i}"} for i in range(5)]

        with caplog.at_level(logging.WARNING, logger="orchestrator.langgraph.state"):
            result = _append_executions(existing, new)

        assert len(result) == MAX_EXECUTION_HISTORY
        assert "Execution history truncated" in caplog.text
        assert "dropped 5 oldest" in caplog.text

    def test_no_warning_within_limit(self, caplog):
        """No warning should be logged when within limit."""
        existing = [{"id": f"exec-{i}"} for i in range(10)]
        new = [{"id": "exec-new"}]

        with caplog.at_level(logging.WARNING, logger="orchestrator.langgraph.state"):
            result = _append_executions(existing, new)

        assert len(result) == 11
        assert "truncated" not in caplog.text
