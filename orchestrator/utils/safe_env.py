"""Safe environment filtering for subprocess execution.

Filters os.environ to strip sensitive variables (DB passwords, cloud secrets)
before passing to subprocesses, reducing the risk of credential leakage.
"""

import os
from typing import Optional

# Variables explicitly blocked even if their prefix would otherwise match.
_BLOCKED_VARS: frozenset[str] = frozenset(
    {
        # Database credentials
        "SURREAL_PASS",
        "SURREAL_PASSWORD",
        "DATABASE_URL",
        "DATABASE_PASSWORD",
        "DB_PASSWORD",
        "DB_PASS",
        "PGPASSWORD",
        "MYSQL_PWD",
        "MONGO_PASSWORD",
        "REDIS_PASSWORD",
        # Cloud secrets
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AZURE_CLIENT_SECRET",
        "AZURE_TENANT_ID",
        "GCP_SERVICE_ACCOUNT_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        # Generic secrets
        "SECRET_KEY",
        "PRIVATE_KEY",
        "ENCRYPTION_KEY",
        "JWT_SECRET",
        "SESSION_SECRET",
        "COOKIE_SECRET",
    }
)

# Prefixes allowed for agent subprocesses (API keys for LLM providers, runtime paths).
_AGENT_ALLOWED_PREFIXES: tuple[str, ...] = (
    "ANTHROPIC_",
    "OPENAI_",
    "GOOGLE_AI_",
    "GEMINI_",
    "MISTRAL_",
    "CURSOR_",
    "CLAUDE_",
)

# Runtime variables always included for agent subprocesses.
_AGENT_RUNTIME_VARS: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "TMP",
        "TEMP",
        "XDG_RUNTIME_DIR",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "PYTHONPATH",
        "NODE_PATH",
        "SURREAL_URL",
        "ORCHESTRATOR_USE_LANGGRAPH",
        "USE_RALPH_LOOP",
        "PARALLEL_WORKERS",
    }
)

# Variables allowed for git subprocesses.
_GIT_ALLOWED_PREFIXES: tuple[str, ...] = (
    "GIT_",
    "SSH_",
)

_GIT_RUNTIME_VARS: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "TMP",
        "TEMP",
        "EDITOR",
        "VISUAL",
        "GPG_AGENT_INFO",
        "GPG_TTY",
        "GNUPGHOME",
    }
)


def _is_blocked(key: str) -> bool:
    """Check if a variable is explicitly blocked."""
    return key in _BLOCKED_VARS


def _filter_extra(extra: dict[str, str]) -> dict[str, str]:
    """Remove blocked vars from extra dict.

    Prevents callers from bypassing _BLOCKED_VARS filtering
    by passing sensitive variables through the extra parameter.
    """
    return {k: v for k, v in extra.items() if not _is_blocked(k)}


def agent_env(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    """Build a filtered environment dict for agent subprocesses.

    Includes LLM API keys, runtime paths, and SURREAL_URL (connection only,
    not credentials). Excludes database passwords, cloud secrets, and other
    sensitive variables.

    Args:
        extra: Additional variables to include (overrides filtering).

    Returns:
        Filtered environment dict safe for agent subprocesses.
    """
    env: dict[str, str] = {}

    for key, value in os.environ.items():
        if _is_blocked(key):
            continue

        if key in _AGENT_RUNTIME_VARS:
            env[key] = value
            continue

        for prefix in _AGENT_ALLOWED_PREFIXES:
            if key.startswith(prefix):
                env[key] = value
                break

    # Always set TERM=dumb to avoid ANSI escape issues in captured output.
    env["TERM"] = "dumb"

    if extra:
        env.update(_filter_extra(extra))

    return env


def git_env(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    """Build a filtered environment dict for git subprocesses.

    Includes PATH, HOME, GIT_*, SSH_*. Excludes all API keys
    and database credentials.

    Args:
        extra: Additional variables to include (overrides filtering).

    Returns:
        Filtered environment dict safe for git subprocesses.
    """
    env: dict[str, str] = {}

    for key, value in os.environ.items():
        if _is_blocked(key):
            continue

        if key in _GIT_RUNTIME_VARS:
            env[key] = value
            continue

        for prefix in _GIT_ALLOWED_PREFIXES:
            if key.startswith(prefix):
                env[key] = value
                break

    if extra:
        env.update(_filter_extra(extra))

    return env
