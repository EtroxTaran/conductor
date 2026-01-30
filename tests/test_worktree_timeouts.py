"""Regression test for subprocess timeout kwargs in WorktreeManager.

Verifies that all subprocess.run() calls in worktree.py include a timeout
argument to prevent indefinitely-hanging git operations.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from orchestrator.utils.worktree import (
    GIT_TIMEOUT_FAST,
    GIT_TIMEOUT_HEAVY,
    GIT_TIMEOUT_WRITE,
    WorktreeManager,
)


def _make_run_result(returncode=0, stdout="", stderr=""):
    """Create a mock CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestWorktreeTimeouts:
    """Verify timeout kwarg is present on subprocess.run calls."""

    @patch("orchestrator.utils.worktree.subprocess.run")
    def test_is_git_repo_has_timeout(self, mock_run):
        """_is_git_repo should use GIT_TIMEOUT_FAST."""
        mock_run.return_value = _make_run_result(returncode=0)

        try:
            WorktreeManager(Path("/fake/project"))
        except Exception:
            pass

        # First call is _is_git_repo
        assert mock_run.call_count >= 1
        first_call = mock_run.call_args_list[0]
        assert first_call.kwargs.get("timeout") == GIT_TIMEOUT_FAST

    @patch("orchestrator.utils.worktree.subprocess.run")
    def test_create_worktree_has_heavy_timeout(self, mock_run):
        """create_worktree should use GIT_TIMEOUT_HEAVY."""
        # First call: _is_git_repo (fast)
        # Then: worktree add (heavy), rev-parse HEAD (fast)
        mock_run.side_effect = [
            _make_run_result(returncode=0),  # _is_git_repo
            _make_run_result(returncode=0),  # worktree add
            _make_run_result(returncode=0, stdout="abc123\n"),  # rev-parse HEAD
        ]

        manager = WorktreeManager.__new__(WorktreeManager)
        manager.project_dir = Path("/fake/project")
        manager.worktrees = []
        manager._lock = __import__("threading").Lock()

        with patch.object(manager, "_is_git_repo", return_value=True):
            mock_run.reset_mock()
            mock_run.side_effect = [
                _make_run_result(returncode=0),  # worktree add
                _make_run_result(returncode=0, stdout="abc123\n"),  # rev-parse HEAD
            ]

            try:
                manager.create_worktree("test-suffix")
            except Exception:
                pass

            if mock_run.call_count >= 1:
                # worktree add call should have HEAVY timeout
                worktree_add_call = mock_run.call_args_list[0]
                assert worktree_add_call.kwargs.get("timeout") == GIT_TIMEOUT_HEAVY

    @patch("orchestrator.utils.worktree.subprocess.run")
    def test_remove_worktree_has_heavy_timeout(self, mock_run):
        """remove_worktree should use GIT_TIMEOUT_HEAVY."""
        mock_run.return_value = _make_run_result(returncode=0)

        manager = WorktreeManager.__new__(WorktreeManager)
        manager.project_dir = Path("/fake/project")
        manager.worktrees = []
        manager._lock = __import__("threading").Lock()

        manager.remove_worktree(Path("/fake/project-worker-test"))

        assert mock_run.call_count == 1
        assert mock_run.call_args.kwargs.get("timeout") == GIT_TIMEOUT_HEAVY

    @patch("orchestrator.utils.worktree.subprocess.run")
    def test_list_worktrees_has_fast_timeout(self, mock_run):
        """list_worktrees should use GIT_TIMEOUT_FAST."""
        mock_run.return_value = _make_run_result(returncode=0, stdout="")

        manager = WorktreeManager.__new__(WorktreeManager)
        manager.project_dir = Path("/fake/project")
        manager.worktrees = []
        manager._lock = __import__("threading").Lock()

        manager.list_worktrees()

        assert mock_run.call_count == 1
        assert mock_run.call_args.kwargs.get("timeout") == GIT_TIMEOUT_FAST

    def test_timeout_constants_are_positive(self):
        """All timeout constants must be positive integers."""
        assert GIT_TIMEOUT_FAST > 0
        assert GIT_TIMEOUT_WRITE > 0
        assert GIT_TIMEOUT_HEAVY > 0
        assert GIT_TIMEOUT_FAST < GIT_TIMEOUT_WRITE < GIT_TIMEOUT_HEAVY
