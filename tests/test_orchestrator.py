"""Tests for the main orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from orchestrator.orchestrator import Orchestrator
from orchestrator.utils.state import PhaseStatus


class TestOrchestrator:
    """Tests for the Orchestrator class."""

    def test_initialization(self, temp_project_dir):
        """Test orchestrator initialization."""
        orch = Orchestrator(
            project_dir=temp_project_dir,
            max_retries=5,
            auto_commit=False,
        )

        assert orch.project_dir == temp_project_dir
        assert orch.max_retries == 5
        assert orch.auto_commit is False
        assert orch.state is not None
        assert orch.logger is not None

    def test_check_prerequisites_missing_product(self, temp_project_dir):
        """Test prerequisites check fails without PRODUCT.md."""
        (temp_project_dir / "PRODUCT.md").unlink()

        orch = Orchestrator(temp_project_dir)
        ok, errors = orch.check_prerequisites()

        assert ok is False
        assert any("PRODUCT.md" in e for e in errors)

    @patch("orchestrator.agents.claude_agent.ClaudeAgent.check_available")
    @patch("orchestrator.agents.cursor_agent.CursorAgent.check_available")
    @patch("orchestrator.agents.gemini_agent.GeminiAgent.check_available")
    def test_check_prerequisites_all_available(
        self, mock_gemini, mock_cursor, mock_claude, temp_project_dir
    ):
        """Test prerequisites check passes with all CLIs."""
        mock_claude.return_value = True
        mock_cursor.return_value = True
        mock_gemini.return_value = True

        orch = Orchestrator(temp_project_dir)
        ok, errors = orch.check_prerequisites()

        assert ok is True
        assert len(errors) == 0

    def test_status(self, temp_project_dir):
        """Test getting workflow status."""
        orch = Orchestrator(temp_project_dir)
        status = orch.status()

        assert "project" in status
        assert "current_phase" in status
        assert "phase_statuses" in status

    def test_reset_all(self, temp_project_dir):
        """Test resetting all phases."""
        orch = Orchestrator(temp_project_dir)

        # Simulate some progress
        orch.state.start_phase(1)
        orch.state.complete_phase(1)
        orch.state.start_phase(2)

        # Reset
        orch.reset()

        # Verify reset
        for phase_name, phase in orch.state.state.phases.items():
            assert phase.status == PhaseStatus.PENDING
            assert phase.attempts == 0

    def test_reset_single_phase(self, temp_project_dir):
        """Test resetting a single phase."""
        orch = Orchestrator(temp_project_dir)

        # Simulate progress
        orch.state.start_phase(1)
        orch.state.fail_phase(1, "test error")

        # Reset phase 1
        orch.reset(phase=1)

        # Verify
        phase = orch.state.get_phase(1)
        assert phase.status == PhaseStatus.PENDING
        assert phase.error is None

    @patch.object(Orchestrator, "check_prerequisites")
    def test_run_executes_workflow(
        self, mock_prereq, temp_project_dir
    ):
        """Test that run executes LangGraph workflow."""
        mock_prereq.return_value = (True, [])

        orch = Orchestrator(temp_project_dir, auto_commit=False)

        # Use AsyncMock which properly handles async functions
        orch.run_langgraph = AsyncMock(
            return_value={"success": True, "current_phase": 5, "status": "completed"}
        )

        result = orch.run()

        assert result["success"] is True
        orch.run_langgraph.assert_called_once()

    @patch.object(Orchestrator, "check_prerequisites")
    def test_run_handles_failure(
        self, mock_prereq, temp_project_dir
    ):
        """Test that run handles workflow failure."""
        mock_prereq.return_value = (True, [])

        orch = Orchestrator(temp_project_dir, auto_commit=False)
        orch.run_langgraph = AsyncMock(
            return_value={"success": False, "error": "Workflow failed", "current_phase": 2}
        )

        result = orch.run()

        assert result["success"] is False
        assert "error" in result

    @patch.object(Orchestrator, "check_prerequisites")
    def test_run_with_start_phase(
        self, mock_prereq, temp_project_dir
    ):
        """Test run accepts start_phase parameter (passed to LangGraph)."""
        mock_prereq.return_value = (True, [])

        orch = Orchestrator(temp_project_dir, auto_commit=False)
        orch.run_langgraph = AsyncMock(
            return_value={"success": True, "current_phase": 5}
        )

        # Note: start_phase is accepted but LangGraph manages its own state
        result = orch.run(start_phase=3)

        assert result["success"] is True
        orch.run_langgraph.assert_called_once()

    @patch.object(Orchestrator, "check_prerequisites")
    def test_run_with_options(
        self, mock_prereq, temp_project_dir
    ):
        """Test run accepts skip_validation parameter."""
        mock_prereq.return_value = (True, [])

        orch = Orchestrator(temp_project_dir, auto_commit=False)
        orch.run_langgraph = AsyncMock(
            return_value={"success": True, "current_phase": 5}
        )

        # Note: skip_validation is accepted but LangGraph manages validation
        result = orch.run(skip_validation=True)

        assert result["success"] is True

    @patch("subprocess.run")
    def test_auto_commit(self, mock_run, temp_project_dir):
        """Test auto-commit functionality."""
        # Mock git commands - optimized to use batched operations:
        # 1. is_git_repo() -> git rev-parse --is-inside-work-tree
        # 2. auto_commit() -> batched bash script (status + add + commit + hash)
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git rev-parse (is_git_repo check)
            MagicMock(returncode=0, stdout="abc123def456\n"),  # batched auto_commit script
        ]

        orch = Orchestrator(temp_project_dir, auto_commit=True)
        orch._auto_commit(1, "planning")

        # Verify batched git operations were called (2 subprocess calls total)
        assert mock_run.call_count == 2

    def test_resume(self, temp_project_dir):
        """Test resume calls LangGraph resume."""
        orch = Orchestrator(temp_project_dir, auto_commit=False)

        # Use AsyncMock for the async method
        orch.resume_langgraph = AsyncMock(
            return_value={"success": True, "current_phase": 5, "resumed_from": 3}
        )

        # Complete first two phases
        orch.state.load()
        orch.state.state.phases["planning"].status = PhaseStatus.COMPLETED
        orch.state.state.phases["validation"].status = PhaseStatus.COMPLETED
        orch.state.save()

        result = orch.resume()

        assert result["success"] is True
        orch.resume_langgraph.assert_called_once()
