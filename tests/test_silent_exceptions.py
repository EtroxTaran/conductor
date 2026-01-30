"""Regression tests for silent exception logging.

Verifies that critical paths log warnings on exceptions instead of
silently swallowing them with bare `except: pass`.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestGitOperationsLogging:
    """Verify git_operations.py logs warnings on exceptions."""

    def test_get_status_logs_warning_on_exception(self, caplog):
        from orchestrator.utils.git_operations import GitOperationsManager

        manager = GitOperationsManager(Path("/fake/project"))
        manager._is_repo = True  # Skip repo check

        with patch("orchestrator.utils.git_operations.subprocess.run", side_effect=OSError("fail")):
            with caplog.at_level(logging.WARNING, logger="orchestrator.utils.git_operations"):
                result = manager.get_status()

        assert result is None
        assert "git status failed" in caplog.text

    def test_reset_hard_logs_warning_on_exception(self, caplog):
        from orchestrator.utils.git_operations import GitOperationsManager

        manager = GitOperationsManager(Path("/fake/project"))
        manager._is_repo = True

        with patch("orchestrator.utils.git_operations.subprocess.run", side_effect=OSError("fail")):
            with caplog.at_level(logging.WARNING, logger="orchestrator.utils.git_operations"):
                result = manager.reset_hard("HEAD")

        assert result is False
        assert "git reset failed" in caplog.text

    def test_get_changed_files_logs_warning_on_exception(self, caplog):
        from orchestrator.utils.git_operations import GitOperationsManager

        manager = GitOperationsManager(Path("/fake/project"))
        manager._is_repo = True

        with patch("orchestrator.utils.git_operations.subprocess.run", side_effect=OSError("fail")):
            with caplog.at_level(logging.WARNING, logger="orchestrator.utils.git_operations"):
                result = manager.get_changed_files()

        assert result == []
        assert "git diff failed" in caplog.text

    def test_auto_commit_logs_warning_on_exception(self, caplog):
        from orchestrator.utils.git_operations import GitOperationsManager

        manager = GitOperationsManager(Path("/fake/project"))
        manager._is_repo = True

        with patch("orchestrator.utils.git_operations.subprocess.run", side_effect=OSError("fail")):
            with caplog.at_level(logging.WARNING, logger="orchestrator.utils.git_operations"):
                result = manager.auto_commit("test message")

        assert result is None
        assert "git auto_commit failed" in caplog.text

    def test_auto_commit_env_excludes_surreal_pass(self):
        """auto_commit must use git_env(), not os.environ, so SURREAL_PASS is excluded (Fix C1 regression)."""
        import os

        from orchestrator.utils.git_operations import GitOperationsManager

        manager = GitOperationsManager(Path("/fake/project"))
        manager._is_repo = True

        fake_env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "SURREAL_PASS": "super-secret",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            with patch("orchestrator.utils.git_operations.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="abc12345\n")
                manager.auto_commit("test message")

        # Check the env kwarg passed to subprocess.run
        called_env = mock_run.call_args.kwargs.get("env") or mock_run.call_args[1].get("env")
        assert called_env is not None
        assert "SURREAL_PASS" not in called_env
        assert "GIT_COMMIT_MSG" in called_env


class TestValidationRouterLogging:
    """Verify validation router logs warning when event emission fails."""

    def test_emitter_failure_logged(self, caplog):
        from orchestrator.langgraph.routers.validation import validation_router

        # Create state with a decision
        state = {"next_decision": "continue"}

        # Create a failing emitter
        def bad_emitter(**kwargs):
            raise RuntimeError("emitter broke")

        config = {"configurable": {"path_emitter": bad_emitter}}

        with caplog.at_level(logging.WARNING, logger="orchestrator.langgraph.routers.validation"):
            result = validation_router(state, config)

        assert result == "implementation"
        assert "Failed to emit path decision event" in caplog.text


class TestValidationUtilsLogging:
    """Verify validation.py logs warning when feedback parsing fails."""

    def test_parse_feedback_failure_logged(self, caplog):
        from orchestrator.utils.validation import validate_feedback

        # Pass a truthy non-dict that will cause from_dict to fail
        # (a list is truthy but .get() will raise AttributeError)
        with caplog.at_level(logging.WARNING, logger="orchestrator.utils.validation"):
            result = validate_feedback("cursor", ["not", "a", "dict"])

        assert result["reviewer"] == "cursor"
        assert result["score"] == 0
        assert "Failed to parse agent feedback" in caplog.text


class TestSecurityScannerLogging:
    """Verify security_scanner logs warning when file read fails."""

    def test_file_read_failure_logged(self, caplog):
        from orchestrator.validators.security_scanner import SecurityScanner

        scanner = SecurityScanner(Path("/fake/project"))

        # Create a path that will fail to read
        fake_path = Path("/nonexistent/file.py")

        with caplog.at_level(logging.WARNING, logger="orchestrator.validators.security_scanner"):
            findings = scanner._scan_file(fake_path)

        assert findings == []
        assert "Failed to read file for security scan" in caplog.text


class TestDependencyCheckerLogging:
    """Verify dependency_checker logs warning on version comparison failures."""

    def test_major_version_comparison_failure_logged(self, caplog):
        from orchestrator.validators.dependency_checker import NpmDependencyStrategy

        strategy = NpmDependencyStrategy()

        # Pass values that will cause an exception in comparison
        with caplog.at_level(logging.WARNING, logger="orchestrator.validators.dependency_checker"):
            # None values will cause attribute error on split
            result = strategy._is_major_update(None, "2.0.0")

        assert result is False
        assert "Version comparison failed" in caplog.text
