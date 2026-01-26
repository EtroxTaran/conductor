"""Security utilities for the dashboard API."""

from .deletion import DeletionConfirmation, DeletionConfirmationManager, get_deletion_manager
from .sanitize import (
    SanitizationError,
    build_safe_claude_command,
    build_safe_slash_command,
    sanitize_chat_message,
    sanitize_command_args,
    sanitize_command_name,
)
from .validators import (
    validate_budget,
    validate_phase_number,
    validate_positive_float,
    validate_project_name,
)

__all__ = [
    # Sanitization
    "SanitizationError",
    "sanitize_chat_message",
    "sanitize_command_name",
    "sanitize_command_args",
    "build_safe_claude_command",
    "build_safe_slash_command",
    # Deletion
    "DeletionConfirmation",
    "DeletionConfirmationManager",
    "get_deletion_manager",
    # Validators
    "validate_project_name",
    "validate_positive_float",
    "validate_phase_number",
    "validate_budget",
]
