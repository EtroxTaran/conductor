"""Input sanitization for subprocess commands."""

import re
from typing import Optional

from ..constants import ALLOWED_CLAUDE_COMMANDS, SHELL_METACHARACTERS, SafetyLimits


class SanitizationError(Exception):
    """Raised when input fails sanitization checks."""

    def __init__(self, message: str, field: str = "input"):
        self.message = message
        self.field = field
        super().__init__(message)


def sanitize_chat_message(message: str) -> str:
    """Sanitize a chat message for use in subprocess commands.

    Blocks shell metacharacters that could enable command injection.

    Args:
        message: Raw user message

    Returns:
        Sanitized message

    Raises:
        SanitizationError: If message contains dangerous characters
    """
    if not message:
        raise SanitizationError("Message cannot be empty", "message")

    if len(message) > SafetyLimits.MAX_CHAT_MESSAGE_LENGTH:
        raise SanitizationError(
            f"Message exceeds maximum length of {SafetyLimits.MAX_CHAT_MESSAGE_LENGTH}",
            "message",
        )

    # Check for shell metacharacters
    dangerous_chars = set(message) & SHELL_METACHARACTERS
    if dangerous_chars:
        # Allow newlines in message content for multi-line prompts
        dangerous_chars.discard("\n")
        dangerous_chars.discard("\r")
        if dangerous_chars:
            raise SanitizationError(
                f"Message contains potentially dangerous characters: {sorted(dangerous_chars)}",
                "message",
            )

    # Check for null bytes (could cause truncation issues)
    if "\x00" in message:
        raise SanitizationError("Message contains null bytes", "message")

    return message


def sanitize_command_name(command: str) -> str:
    """Sanitize and validate a Claude slash command name.

    Args:
        command: Raw command name (without leading slash)

    Returns:
        Validated command name

    Raises:
        SanitizationError: If command is invalid or not in whitelist
    """
    if not command:
        raise SanitizationError("Command cannot be empty", "command")

    if len(command) > SafetyLimits.MAX_COMMAND_LENGTH:
        raise SanitizationError(
            f"Command exceeds maximum length of {SafetyLimits.MAX_COMMAND_LENGTH}",
            "command",
        )

    # Remove leading slash if present
    clean_command = command.lstrip("/")

    # Only allow alphanumeric and hyphens
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9-]*$", clean_command):
        raise SanitizationError(
            "Command name must start with a letter and contain only letters, numbers, and hyphens",
            "command",
        )

    # Check against whitelist
    if clean_command not in ALLOWED_CLAUDE_COMMANDS:
        raise SanitizationError(
            f"Command '{clean_command}' is not in the allowed commands list",
            "command",
        )

    return clean_command


def sanitize_command_args(args: list[str]) -> list[str]:
    """Sanitize command arguments.

    Args:
        args: List of command arguments

    Returns:
        Sanitized arguments list

    Raises:
        SanitizationError: If any argument is invalid
    """
    if not args:
        return []

    sanitized = []
    for i, arg in enumerate(args):
        if not isinstance(arg, str):
            raise SanitizationError(f"Argument {i} must be a string", "args")

        # Check for shell metacharacters
        dangerous_chars = set(arg) & SHELL_METACHARACTERS
        if dangerous_chars:
            raise SanitizationError(
                f"Argument {i} contains potentially dangerous characters",
                "args",
            )

        # Check for null bytes
        if "\x00" in arg:
            raise SanitizationError(f"Argument {i} contains null bytes", "args")

        sanitized.append(arg)

    return sanitized


def build_safe_claude_command(
    prompt: str,
    output_format: str = "text",
    extra_args: Optional[list[str]] = None,
) -> list[str]:
    """Build a safe Claude CLI command.

    Args:
        prompt: The prompt to send to Claude
        output_format: Output format (text, json, stream-json)
        extra_args: Additional CLI arguments

    Returns:
        List of command arguments safe for subprocess

    Raises:
        SanitizationError: If inputs fail validation
    """
    # Validate output format
    valid_formats = {"text", "json", "stream-json"}
    if output_format not in valid_formats:
        raise SanitizationError(
            f"Output format must be one of: {valid_formats}",
            "output_format",
        )

    # Sanitize the prompt
    clean_prompt = sanitize_chat_message(prompt)

    # Build command
    cmd = ["claude", "-p", clean_prompt, "--output-format", output_format]

    # Add extra args if provided
    if extra_args:
        sanitized_args = sanitize_command_args(extra_args)
        cmd.extend(sanitized_args)

    return cmd


def build_safe_slash_command(
    command: str,
    args: Optional[list[str]] = None,
    output_format: str = "text",
) -> list[str]:
    """Build a safe Claude slash command.

    Args:
        command: The slash command name
        args: Command arguments
        output_format: Output format

    Returns:
        List of command arguments safe for subprocess

    Raises:
        SanitizationError: If inputs fail validation
    """
    # Validate command name
    clean_command = sanitize_command_name(command)

    # Build the slash command prompt
    command_prompt = f"/{clean_command}"
    if args:
        sanitized_args = sanitize_command_args(args)
        command_prompt += " " + " ".join(sanitized_args)

    return build_safe_claude_command(command_prompt, output_format)
