"""Regression tests for task loop iteration counting (Fix 8).

Verifies that task_loop_iterations only increments on retry of the same
task, not when selecting a new task. A workflow with 50 sequential tasks
should not hit the iteration limit.
"""

from unittest.mock import patch

import pytest

from orchestrator.langgraph.nodes.select_task import select_next_task_node


def _make_state(tmp_path, tasks, current_task_id=None, iterations=0):
    """Create minimal workflow state for select_task_node."""
    return {
        "project_name": "test-project",
        "project_dir": str(tmp_path),
        "tasks": tasks,
        "completed_task_ids": [],
        "failed_task_ids": [],
        "in_flight_task_ids": [],
        "current_task_id": current_task_id,
        "task_loop_iterations": iterations,
        "milestones": [],
    }


def _make_task(task_id, status="pending", deps=None):
    """Create a minimal task dict."""
    return {
        "id": task_id,
        "title": f"Task {task_id}",
        "status": status,
        "priority": "medium",
        "dependencies": deps or [],
        "files_to_create": [f"{task_id}.py"],
        "files_to_modify": [],
    }


@pytest.fixture
def mock_board_sync():
    """Mock board sync to prevent side effects."""
    with patch("orchestrator.langgraph.nodes.select_task.sync_board"):
        yield


class TestIterationCounting:
    """Verify iterations only increment on same-task retry."""

    @pytest.mark.asyncio
    async def test_new_task_does_not_increment(self, tmp_path, mock_board_sync):
        """Selecting a new task should NOT increment iteration counter."""
        tasks = [_make_task("T1"), _make_task("T2")]
        state = _make_state(tmp_path, tasks, current_task_id=None, iterations=5)

        result = await select_next_task_node(state)

        # Selected T1 (new task, not a retry) — iterations should stay at 5
        assert result["current_task_id"] == "T1"
        assert result["task_loop_iterations"] == 5

    @pytest.mark.asyncio
    async def test_same_task_retry_increments(self, tmp_path, mock_board_sync):
        """Retrying the same task SHOULD increment iteration counter."""
        tasks = [_make_task("T1")]
        state = _make_state(tmp_path, tasks, current_task_id="T1", iterations=5)

        result = await select_next_task_node(state)

        # Selected T1 again (retry) — iterations should be 6
        assert result["current_task_id"] == "T1"
        assert result["task_loop_iterations"] == 6

    @pytest.mark.asyncio
    async def test_different_task_does_not_increment(self, tmp_path, mock_board_sync):
        """Switching from one task to another should NOT increment."""
        tasks = [_make_task("T2")]
        state = _make_state(tmp_path, tasks, current_task_id="T1", iterations=10)

        result = await select_next_task_node(state)

        # Selected T2 (different from T1) — iterations should stay at 10
        assert result["current_task_id"] == "T2"
        assert result["task_loop_iterations"] == 10

    @pytest.mark.asyncio
    async def test_sequential_tasks_dont_exhaust_limit(self, tmp_path, mock_board_sync):
        """50 sequential tasks should not hit the default 50-iteration limit."""
        # This simulates what happens with many tasks in sequence
        iterations = 0
        for i in range(50):
            task_id = f"T{i+1}"
            prev_task_id = f"T{i}" if i > 0 else None
            tasks = [_make_task(task_id)]
            state = _make_state(
                tmp_path, tasks, current_task_id=prev_task_id, iterations=iterations
            )

            result = await select_next_task_node(state)
            iterations = result["task_loop_iterations"]

        # After 50 different tasks, iterations should still be 0
        assert iterations == 0

    @pytest.mark.asyncio
    async def test_all_done_does_not_increment(self, tmp_path, mock_board_sync):
        """When all tasks are done, iterations should not change."""
        tasks = [_make_task("T1", status="completed")]
        state = _make_state(tmp_path, tasks, current_task_id="T1", iterations=5)
        state["completed_task_ids"] = ["T1"]

        result = await select_next_task_node(state)

        # No task selected, iterations unchanged
        assert result["task_loop_iterations"] == 5
