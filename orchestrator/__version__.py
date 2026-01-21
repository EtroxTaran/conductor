"""Version information for meta-architect orchestrator."""

from pathlib import Path


def _read_version() -> str:
    """Read version from VERSION file at repo root."""
    # Try to find VERSION file relative to this module
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    # Fallback
    return "0.0.0"


__version__ = _read_version()
__version_info__ = tuple(int(x) for x in __version__.split("."))
