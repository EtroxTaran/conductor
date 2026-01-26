"""Application constants and enums."""

from enum import IntEnum


class WorkflowPhase(IntEnum):
    """Workflow phase numbers."""

    PREREQUISITES = 0
    PLANNING = 1
    VALIDATION = 2
    IMPLEMENTATION = 3
    VERIFICATION = 4
    COMPLETION = 5


class SafetyLimits:
    """Safety limits for file operations and queries."""

    MAX_SESSION_FILES = 1000
    MAX_AUDIT_ENTRIES = 1000
    DEFAULT_PAGE_SIZE = 100
    MAX_PAGE_SIZE = 1000
    CONFIRMATION_TOKEN_EXPIRY_SECONDS = 300  # 5 minutes
    MAX_CHAT_MESSAGE_LENGTH = 32000
    MAX_COMMAND_LENGTH = 1000


# Allowed Claude slash commands (whitelist)
ALLOWED_CLAUDE_COMMANDS = frozenset(
    [
        "help",
        "status",
        "clear",
        "compact",
        "config",
        "cost",
        "doctor",
        "init",
        "login",
        "logout",
        "memory",
        "mcp",
        "model",
        "permissions",
        "pr-comments",
        "review",
        "terminal-setup",
        "vim",
        # Conductor-specific skills
        "orchestrate",
        "plan",
        "plan-feature",
        "validate-plan",
        "implement-task",
        "verify-code",
        "call-cursor",
        "call-gemini",
        "resolve-conflict",
        "phase-status",
        "list-projects",
        "sync-rules",
        "add-lesson",
        "skills",
        "status",
        "task",
        "discover",
        "workflow-manager",
    ]
)

# Characters that are dangerous in shell contexts
SHELL_METACHARACTERS = frozenset(
    [
        ";",
        "&",
        "|",
        "`",
        "$",
        "(",
        ")",
        "{",
        "}",
        "<",
        ">",
        "\n",
        "\r",
        "\x00",
        "\\",
    ]
)

# Valid project name pattern
PROJECT_NAME_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$"
