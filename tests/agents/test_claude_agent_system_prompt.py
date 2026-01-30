"""Tests for Claude agent --system-prompt parameter support.

Regression test: Verifies that the worker role override (--system-prompt)
is correctly included in the built command when spawning workers.
"""

from unittest.mock import MagicMock, patch

import pytest

from orchestrator.agents.claude_agent import ClaudeAgent


class TestClaudeAgentSystemPrompt:
    """Test --system-prompt flag in ClaudeAgent.build_command()."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create a ClaudeAgent with session continuity disabled."""
        with patch(
            "orchestrator.agents.claude_agent.ClaudeAgent._find_schema_dir", return_value=None
        ):
            return ClaudeAgent(
                project_dir=tmp_path,
                enable_session_continuity=False,
            )

    def test_system_prompt_included_in_command(self, agent):
        """--system-prompt flag is added when system_prompt is provided."""
        cmd = agent.build_command(
            prompt="Implement the feature",
            system_prompt="You are a worker. Write code.",
        )

        assert "--system-prompt" in cmd
        idx = cmd.index("--system-prompt")
        assert cmd[idx + 1] == "You are a worker. Write code."

    def test_system_prompt_not_included_when_none(self, agent):
        """--system-prompt flag is NOT added when system_prompt is None."""
        cmd = agent.build_command(
            prompt="Implement the feature",
        )

        assert "--system-prompt" not in cmd

    def test_system_prompt_appears_before_allowed_tools(self, agent):
        """--system-prompt appears before --allowedTools in command."""
        cmd = agent.build_command(
            prompt="Implement the feature",
            system_prompt="Override role",
        )

        sp_idx = cmd.index("--system-prompt")
        tools_idx = cmd.index("--allowedTools")
        assert sp_idx < tools_idx

    def test_worker_role_override_constant_exists(self):
        """WORKER_ROLE_OVERRIDE constant is defined in implementation module."""
        from orchestrator.langgraph.nodes.implementation import WORKER_ROLE_OVERRIDE

        assert "IMPLEMENTER" in WORKER_ROLE_OVERRIDE
        assert "write" in WORKER_ROLE_OVERRIDE.lower()
        assert "IGNORE" in WORKER_ROLE_OVERRIDE

    def test_system_prompt_with_other_flags(self, agent):
        """--system-prompt works alongside other enhanced features."""
        cmd = agent.build_command(
            prompt="Implement feature",
            system_prompt="Worker override",
            use_plan_mode=True,
            budget_usd=1.0,
        )

        assert "--system-prompt" in cmd
        assert "--permission-mode" in cmd
        assert "--max-budget-usd" in cmd

    def test_run_passes_system_prompt_through(self, agent):
        """run() passes system_prompt to super().run()."""
        with patch.object(type(agent).__bases__[0], "run") as mock_run:
            mock_run.return_value = MagicMock(success=True, output="{}", parsed_output={})
            agent.run(
                prompt="Test",
                system_prompt="Override",
            )

            _, kwargs = mock_run.call_args
            assert kwargs.get("system_prompt") == "Override"
