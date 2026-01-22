"""Environment variable loader for SurrealDB configuration.

Automatically loads .env files from multiple locations with precedence:
1. ~/.config/conductor/.env (user global config)
2. {repo_root}/.env (repository-level config)
3. Environment variables (highest priority, override all)

Usage:
    This module is automatically imported when the orchestrator package is loaded.
    No manual invocation is needed.

    # Manual loading if needed
    from orchestrator.utils.env_loader import load_env, reload_env
    load_env()  # Already called on import
    reload_env()  # Force reload
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Flag to track if environment has been loaded
_env_loaded = False


def find_repo_root() -> Optional[Path]:
    """Find the repository root by looking for key files.

    Searches upward from this file's location for:
    - pyproject.toml
    - .git directory
    - CLAUDE.md

    Returns:
        Path to repository root, or None if not found
    """
    current = Path(__file__).resolve()

    # Walk up the directory tree
    for parent in [current] + list(current.parents):
        # Check for repository markers
        if (parent / "pyproject.toml").exists():
            return parent
        if (parent / ".git").exists():
            return parent
        if (parent / "CLAUDE.md").exists():
            return parent

    return None


def get_global_config_path() -> Path:
    """Get the global configuration directory path.

    Returns:
        Path to ~/.config/conductor/
    """
    config_home = os.environ.get("XDG_CONFIG_HOME", "")
    if not config_home:
        config_home = str(Path.home() / ".config")

    return Path(config_home) / "conductor"


def load_env(force: bool = False) -> bool:
    """Load environment variables from .env files.

    Files are loaded in order of increasing priority:
    1. ~/.config/conductor/.env (user global)
    2. {repo_root}/.env (repository local)

    Later files override earlier ones. Environment variables
    set before calling this function take highest priority.

    Args:
        force: If True, reload even if already loaded

    Returns:
        True if any .env file was loaded
    """
    global _env_loaded

    if _env_loaded and not force:
        return True

    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.debug("python-dotenv not installed, skipping .env loading")
        _env_loaded = True
        return False

    loaded_any = False

    # Load global config first (lowest priority)
    global_env = get_global_config_path() / ".env"
    if global_env.exists():
        load_dotenv(global_env, override=False)
        logger.debug(f"Loaded global config from {global_env}")
        loaded_any = True

    # Load repo-level config (higher priority)
    repo_root = find_repo_root()
    if repo_root:
        repo_env = repo_root / ".env"
        if repo_env.exists():
            load_dotenv(repo_env, override=True)
            logger.debug(f"Loaded repo config from {repo_env}")
            loaded_any = True

    _env_loaded = True
    return loaded_any


def reload_env() -> bool:
    """Force reload environment from .env files.

    Returns:
        True if any .env file was loaded
    """
    return load_env(force=True)


def is_env_loaded() -> bool:
    """Check if environment has been loaded.

    Returns:
        True if load_env() has been called
    """
    return _env_loaded


def get_env_sources() -> dict[str, Optional[str]]:
    """Get information about loaded .env file sources.

    Useful for debugging configuration issues.

    Returns:
        Dictionary with:
        - global_path: Path to global .env (or None)
        - global_exists: Whether global .env exists
        - repo_path: Path to repo .env (or None)
        - repo_exists: Whether repo .env exists
        - repo_root: Detected repository root
    """
    global_path = get_global_config_path() / ".env"
    repo_root = find_repo_root()
    repo_path = repo_root / ".env" if repo_root else None

    return {
        "global_path": str(global_path),
        "global_exists": global_path.exists(),
        "repo_path": str(repo_path) if repo_path else None,
        "repo_exists": repo_path.exists() if repo_path else False,
        "repo_root": str(repo_root) if repo_root else None,
    }


# Auto-load on import
load_env()
