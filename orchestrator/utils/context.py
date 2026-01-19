"""Context management and versioning for the orchestration workflow.

Provides checksums and drift detection for context files to ensure
consistency across workflow phases.
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class FileChecksum:
    """Checksum information for a tracked file."""
    path: str
    checksum: str
    last_modified: str
    size: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FileChecksum":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ContextState:
    """State of all tracked context files."""
    files: dict[str, FileChecksum] = field(default_factory=dict)
    captured_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "files": {k: v.to_dict() for k, v in self.files.items()},
            "captured_at": self.captured_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContextState":
        """Create from dictionary."""
        files = {
            k: FileChecksum.from_dict(v)
            for k, v in data.get("files", {}).items()
        }
        return cls(
            files=files,
            captured_at=data.get("captured_at", datetime.now().isoformat()),
            version=data.get("version", "1.0"),
        )


@dataclass
class DriftResult:
    """Result of drift detection."""
    has_drift: bool
    changed_files: list[str] = field(default_factory=list)
    added_files: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    details: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class ContextManager:
    """Manages context file versioning and drift detection.

    Tracks important context files (AGENTS.md, PRODUCT.md, etc.) and
    detects when they change during a workflow execution.
    """

    # Files tracked by default
    TRACKED_FILES = {
        "agents": "AGENTS.md",
        "product": "PRODUCT.md",
        "cursor_rules": ".cursor/rules",
        "gemini": "GEMINI.md",
        "claude": "CLAUDE.md",
    }

    def __init__(self, project_dir: str | Path):
        """Initialize context manager.

        Args:
            project_dir: Root directory of the project
        """
        self.project_dir = Path(project_dir)
        self._tracked_files = self.TRACKED_FILES.copy()

    def add_tracked_file(self, key: str, relative_path: str) -> None:
        """Add a file to be tracked.

        Args:
            key: Unique identifier for the file
            relative_path: Path relative to project directory
        """
        self._tracked_files[key] = relative_path

    def remove_tracked_file(self, key: str) -> None:
        """Remove a file from tracking.

        Args:
            key: Identifier of the file to remove
        """
        self._tracked_files.pop(key, None)

    def compute_checksum(self, file_path: Path) -> str:
        """Compute SHA-256 checksum of a file.

        Args:
            file_path: Absolute path to the file

        Returns:
            Hexadecimal checksum string
        """
        if not file_path.exists():
            return ""

        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_file_info(self, file_path: Path) -> Optional[FileChecksum]:
        """Get checksum information for a file.

        Args:
            file_path: Absolute path to the file

        Returns:
            FileChecksum if file exists, None otherwise
        """
        if not file_path.exists():
            return None

        stat = file_path.stat()
        return FileChecksum(
            path=str(file_path.relative_to(self.project_dir)),
            checksum=self.compute_checksum(file_path),
            last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            size=stat.st_size,
        )

    def capture_context(self) -> ContextState:
        """Capture current state of all tracked files.

        Returns:
            ContextState with checksums of all tracked files
        """
        context = ContextState()

        for key, rel_path in self._tracked_files.items():
            file_path = self.project_dir / rel_path
            file_info = self.get_file_info(file_path)
            if file_info:
                context.files[key] = file_info

        return context

    def validate_context(self, stored_state: ContextState) -> DriftResult:
        """Validate current context against stored state.

        Args:
            stored_state: Previously captured context state

        Returns:
            DriftResult with details about any changes
        """
        current_state = self.capture_context()
        result = DriftResult(has_drift=False)

        stored_keys = set(stored_state.files.keys())
        current_keys = set(current_state.files.keys())

        # Check for added files
        added = current_keys - stored_keys
        if added:
            result.added_files = list(added)
            result.has_drift = True

        # Check for removed files
        removed = stored_keys - current_keys
        if removed:
            result.removed_files = list(removed)
            result.has_drift = True

        # Check for changed files
        for key in stored_keys & current_keys:
            stored_file = stored_state.files[key]
            current_file = current_state.files[key]

            if stored_file.checksum != current_file.checksum:
                result.changed_files.append(key)
                result.has_drift = True
                result.details[key] = {
                    "old_checksum": stored_file.checksum[:12] + "...",
                    "new_checksum": current_file.checksum[:12] + "...",
                    "old_modified": stored_file.last_modified,
                    "new_modified": current_file.last_modified,
                    "old_size": stored_file.size,
                    "new_size": current_file.size,
                }

        return result

    def sync_context(self, current_state: Optional[ContextState] = None) -> ContextState:
        """Sync and return current context state.

        If current_state is provided, it will be updated with current checksums.
        Otherwise, captures fresh state.

        Args:
            current_state: Optional existing state to update

        Returns:
            Updated ContextState
        """
        return self.capture_context()

    def get_drift_summary(self, drift_result: DriftResult) -> str:
        """Generate a human-readable summary of context drift.

        Args:
            drift_result: Result from validate_context

        Returns:
            Formatted summary string
        """
        if not drift_result.has_drift:
            return "No context drift detected."

        lines = ["Context drift detected:"]

        if drift_result.changed_files:
            lines.append(f"  Modified: {', '.join(drift_result.changed_files)}")
            for key, details in drift_result.details.items():
                lines.append(f"    - {key}: {details['old_size']}B -> {details['new_size']}B")

        if drift_result.added_files:
            lines.append(f"  Added: {', '.join(drift_result.added_files)}")

        if drift_result.removed_files:
            lines.append(f"  Removed: {', '.join(drift_result.removed_files)}")

        return "\n".join(lines)

    def save_context_snapshot(self, output_path: Path) -> ContextState:
        """Save current context state to a file.

        Args:
            output_path: Path to save the snapshot

        Returns:
            The captured ContextState
        """
        state = self.capture_context()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(state.to_dict(), f, indent=2)

        return state

    def load_context_snapshot(self, input_path: Path) -> Optional[ContextState]:
        """Load context state from a file.

        Args:
            input_path: Path to load the snapshot from

        Returns:
            ContextState if file exists, None otherwise
        """
        if not input_path.exists():
            return None

        with open(input_path, "r") as f:
            data = json.load(f)

        return ContextState.from_dict(data)
