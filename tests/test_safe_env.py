"""Tests for orchestrator.utils.safe_env environment filtering."""

import os
from unittest.mock import patch

from orchestrator.utils.safe_env import agent_env, git_env


class TestAgentEnv:
    """Tests for agent_env() helper."""

    def test_excludes_db_credentials(self):
        """DB passwords must never appear in agent env."""
        fake_env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "SURREAL_PASS": "secret123",
            "SURREAL_PASSWORD": "secret456",
            "DATABASE_URL": "postgres://user:pass@host/db",
            "DATABASE_PASSWORD": "dbpass",
            "DB_PASSWORD": "dbpass2",
            "PGPASSWORD": "pgpass",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = agent_env()

        assert "SURREAL_PASS" not in env
        assert "SURREAL_PASSWORD" not in env
        assert "DATABASE_URL" not in env
        assert "DATABASE_PASSWORD" not in env
        assert "DB_PASSWORD" not in env
        assert "PGPASSWORD" not in env

    def test_excludes_cloud_secrets(self):
        """Cloud secrets must never appear in agent env."""
        fake_env = {
            "PATH": "/usr/bin",
            "AWS_SECRET_ACCESS_KEY": "aws-secret",
            "AWS_SESSION_TOKEN": "aws-token",
            "AZURE_CLIENT_SECRET": "azure-secret",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = agent_env()

        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "AWS_SESSION_TOKEN" not in env
        assert "AZURE_CLIENT_SECRET" not in env

    def test_includes_api_keys(self):
        """LLM API keys should be included for agent subprocesses."""
        fake_env = {
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "sk-ant-xxx",
            "OPENAI_API_KEY": "sk-xxx",
            "GEMINI_API_KEY": "gemini-xxx",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = agent_env()

        assert env["ANTHROPIC_API_KEY"] == "sk-ant-xxx"
        assert env["OPENAI_API_KEY"] == "sk-xxx"
        assert env["GEMINI_API_KEY"] == "gemini-xxx"

    def test_includes_runtime_paths(self):
        """Runtime variables like PATH, HOME should be included."""
        fake_env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "SURREAL_URL": "ws://localhost:8000",
            "VIRTUAL_ENV": "/home/user/.venv",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = agent_env()

        assert env["PATH"] == "/usr/bin"
        assert env["HOME"] == "/home/user"
        assert env["SURREAL_URL"] == "ws://localhost:8000"
        assert env["VIRTUAL_ENV"] == "/home/user/.venv"

    def test_sets_term_dumb(self):
        """TERM should always be set to dumb."""
        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            env = agent_env()

        assert env["TERM"] == "dumb"

    def test_extra_overrides(self):
        """Extra dict should override filtered values."""
        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            env = agent_env(extra={"CUSTOM_VAR": "custom"})

        assert env["CUSTOM_VAR"] == "custom"

    def test_extra_blocked_vars_stripped(self):
        """Blocked vars in extra dict must be stripped (Fix C4 regression)."""
        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            env = agent_env(
                extra={
                    "CUSTOM_VAR": "ok",
                    "SURREAL_PASS": "secret",
                    "AWS_SECRET_ACCESS_KEY": "aws-secret",
                    "DATABASE_PASSWORD": "dbpass",
                }
            )

        assert env["CUSTOM_VAR"] == "ok"
        assert "SURREAL_PASS" not in env
        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "DATABASE_PASSWORD" not in env

    def test_unknown_vars_excluded(self):
        """Variables not matching any allowed prefix or runtime set should be excluded."""
        fake_env = {
            "PATH": "/usr/bin",
            "RANDOM_VAR": "random",
            "MY_APP_SECRET": "secret",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = agent_env()

        assert "RANDOM_VAR" not in env
        assert "MY_APP_SECRET" not in env


class TestGitEnv:
    """Tests for git_env() helper."""

    def test_excludes_api_keys(self):
        """API keys must not appear in git env."""
        fake_env = {
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "sk-ant-xxx",
            "OPENAI_API_KEY": "sk-xxx",
            "GEMINI_API_KEY": "gemini-xxx",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = git_env()

        assert "ANTHROPIC_API_KEY" not in env
        assert "OPENAI_API_KEY" not in env
        assert "GEMINI_API_KEY" not in env

    def test_excludes_db_credentials(self):
        """DB credentials must not appear in git env."""
        fake_env = {
            "PATH": "/usr/bin",
            "SURREAL_PASS": "secret123",
            "DATABASE_URL": "postgres://user:pass@host/db",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = git_env()

        assert "SURREAL_PASS" not in env
        assert "DATABASE_URL" not in env

    def test_includes_git_and_ssh_vars(self):
        """GIT_* and SSH_* variables should be included."""
        fake_env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "GIT_AUTHOR_NAME": "Test User",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_EDITOR": "vim",
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            "SSH_AGENT_PID": "12345",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = git_env()

        assert env["GIT_AUTHOR_NAME"] == "Test User"
        assert env["GIT_COMMITTER_EMAIL"] == "test@example.com"
        assert env["GIT_EDITOR"] == "vim"
        assert env["SSH_AUTH_SOCK"] == "/tmp/ssh-agent.sock"
        assert env["SSH_AGENT_PID"] == "12345"

    def test_includes_runtime_paths(self):
        """PATH and HOME should be included."""
        fake_env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
        }
        with patch.dict(os.environ, fake_env, clear=True):
            env = git_env()

        assert env["PATH"] == "/usr/bin"
        assert env["HOME"] == "/home/user"

    def test_no_term_dumb(self):
        """git_env should NOT force TERM=dumb."""
        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            env = git_env()

        assert "TERM" not in env

    def test_extra_overrides(self):
        """Extra dict should be merged in."""
        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            env = git_env(extra={"GIT_EDITOR": "true"})

        assert env["GIT_EDITOR"] == "true"

    def test_extra_blocked_vars_stripped(self):
        """Blocked vars in git_env extra dict must be stripped (Fix C4 regression)."""
        with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
            env = git_env(
                extra={
                    "GIT_COMMIT_MSG": "test message",
                    "SURREAL_PASS": "secret",
                    "DATABASE_URL": "postgres://leaked",
                }
            )

        assert env["GIT_COMMIT_MSG"] == "test message"
        assert "SURREAL_PASS" not in env
        assert "DATABASE_URL" not in env
