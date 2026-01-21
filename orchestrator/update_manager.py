"""Project update management for meta-architect.

Handles version checking, update application, backup creation, and rollback
for projects created with meta-architect.
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class VersionInfo:
    """Version information parsed from semantic version string."""
    major: int
    minor: int
    patch: int

    @classmethod
    def from_string(cls, version_str: str) -> "VersionInfo":
        """Parse version string (e.g., '0.2.0') to VersionInfo."""
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version_str.strip())
        if not match:
            return cls(0, 0, 0)
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: "VersionInfo") -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionInfo):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __le__(self, other: "VersionInfo") -> bool:
        return self < other or self == other

    def is_breaking_update(self, other: "VersionInfo") -> bool:
        """Check if updating to 'other' would be a breaking change (major version bump)."""
        return other.major > self.major


@dataclass
class ChangelogEntry:
    """A single entry from the changelog."""
    version: str
    date: str
    sections: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class UpdateInfo:
    """Information about available updates for a project."""
    project_name: str
    current_version: str
    latest_version: str
    updates_available: bool
    is_breaking_update: bool
    changelog_entries: list[ChangelogEntry]
    files_to_update: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_name": self.project_name,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "updates_available": self.updates_available,
            "is_breaking_update": self.is_breaking_update,
            "changelog_entries": [
                {"version": e.version, "date": e.date, "sections": e.sections}
                for e in self.changelog_entries
            ],
            "files_to_update": self.files_to_update,
        }


@dataclass
class UpdateResult:
    """Result of an update operation."""
    success: bool
    backup_id: Optional[str] = None
    files_updated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "backup_id": self.backup_id,
            "files_updated": self.files_updated,
            "errors": self.errors,
            "message": self.message,
        }


class UpdateManager:
    """Manages project updates for meta-architect.

    Handles:
    - Version comparison between project and current meta-architect
    - Checking for available updates
    - Creating backups before updates
    - Applying updates to projects
    - Rolling back from backups
    """

    def __init__(self, root_dir: Optional[Path] = None):
        """Initialize the update manager.

        Args:
            root_dir: Meta-architect root directory. If None, auto-detect.
        """
        if root_dir is None:
            # Auto-detect root dir relative to this file
            self.root_dir = Path(__file__).parent.parent.resolve()
        else:
            self.root_dir = Path(root_dir).resolve()

        self.projects_dir = self.root_dir / "projects"
        self.templates_dir = self.root_dir / "project-templates"
        self.version_file = self.root_dir / "VERSION"
        self.changelog_file = self.root_dir / "CHANGELOG.md"

    def get_current_version(self) -> str:
        """Get the current meta-architect version from VERSION file."""
        if self.version_file.exists():
            return self.version_file.read_text().strip()
        return "0.0.0"

    def get_project_version(self, project_name: str) -> Optional[str]:
        """Get the meta-architect version stored in a project's config.

        Args:
            project_name: Name of the project

        Returns:
            Version string or None if not found
        """
        config = self._load_project_config(project_name)
        if not config:
            return None

        versioning = config.get("versioning", {})
        return versioning.get("meta_architect_version") or versioning.get("last_sync_version")

    def check_updates(self, project_name: str) -> UpdateInfo:
        """Check if updates are available for a project.

        Args:
            project_name: Name of the project to check

        Returns:
            UpdateInfo with details about available updates
        """
        current_version = self.get_current_version()
        project_version = self.get_project_version(project_name)

        if not project_version:
            project_version = "0.0.0"

        current_v = VersionInfo.from_string(current_version)
        project_v = VersionInfo.from_string(project_version)

        updates_available = project_v < current_v
        is_breaking = project_v.is_breaking_update(current_v)

        # Get changelog entries between versions
        changelog_entries = []
        if updates_available:
            changelog_entries = self._parse_changelog_between_versions(
                project_version, current_version
            )

        # Determine which files would be updated
        files_to_update = self._get_files_to_update(project_name) if updates_available else []

        return UpdateInfo(
            project_name=project_name,
            current_version=project_version,
            latest_version=current_version,
            updates_available=updates_available,
            is_breaking_update=is_breaking,
            changelog_entries=changelog_entries,
            files_to_update=files_to_update,
        )

    def create_backup(self, project_name: str) -> tuple[bool, str]:
        """Create a backup of a project before updating.

        Args:
            project_name: Name of the project to backup

        Returns:
            Tuple of (success, backup_id or error message)
        """
        project_dir = self.projects_dir / project_name
        if not project_dir.exists():
            return False, f"Project '{project_name}' not found"

        # Create backup directory
        backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = project_dir / ".workflow" / "backups" / backup_id

        try:
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Files to backup
            files_to_backup = [
                "CLAUDE.md",
                "GEMINI.md",
                ".cursor/rules",
                ".project-config.json",
            ]

            for file_path in files_to_backup:
                src = project_dir / file_path
                if src.exists():
                    dst = backup_dir / file_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

            # Save backup metadata
            metadata = {
                "backup_id": backup_id,
                "created_at": datetime.now().isoformat(),
                "project_name": project_name,
                "meta_architect_version": self.get_current_version(),
                "project_version": self.get_project_version(project_name),
                "files_backed_up": files_to_backup,
            }

            metadata_file = backup_dir / "backup_metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

            return True, backup_id

        except Exception as e:
            return False, str(e)

    def apply_updates(
        self,
        project_name: str,
        create_backup: bool = True,
        dry_run: bool = False,
    ) -> UpdateResult:
        """Apply updates to a project.

        Args:
            project_name: Name of the project to update
            create_backup: Whether to create a backup first (default True)
            dry_run: If True, show what would be changed without making changes

        Returns:
            UpdateResult with details of the update
        """
        project_dir = self.projects_dir / project_name
        if not project_dir.exists():
            return UpdateResult(
                success=False,
                errors=[f"Project '{project_name}' not found"],
            )

        # Check if updates are available
        update_info = self.check_updates(project_name)
        if not update_info.updates_available:
            return UpdateResult(
                success=True,
                message="Project is already up to date",
                files_updated=[],
            )

        # Create backup if requested
        backup_id = None
        if create_backup and not dry_run:
            success, backup_result = self.create_backup(project_name)
            if not success:
                return UpdateResult(
                    success=False,
                    errors=[f"Failed to create backup: {backup_result}"],
                )
            backup_id = backup_result

        if dry_run:
            return UpdateResult(
                success=True,
                message="Dry run - no changes made",
                files_updated=update_info.files_to_update,
            )

        # Apply updates using sync script
        files_updated = []
        errors = []

        try:
            # Run the sync script
            result = subprocess.run(
                [
                    "python",
                    str(self.root_dir / "scripts" / "sync-project-templates.py"),
                    "--project", project_name,
                ],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                errors.append(f"Sync script failed: {result.stderr}")
            else:
                # Parse output to find updated files
                for line in result.stdout.split("\n"):
                    if line.strip().startswith("-"):
                        files_updated.append(line.strip()[2:])

            # Update project config with new version
            self._update_project_version(project_name)

        except subprocess.TimeoutExpired:
            errors.append("Sync operation timed out")
        except Exception as e:
            errors.append(str(e))

        return UpdateResult(
            success=len(errors) == 0,
            backup_id=backup_id,
            files_updated=files_updated or update_info.files_to_update,
            errors=errors,
            message="Updates applied successfully" if not errors else "Updates failed",
        )

    def rollback(self, project_name: str, backup_id: str) -> UpdateResult:
        """Rollback a project to a previous backup.

        Args:
            project_name: Name of the project
            backup_id: ID of the backup to restore

        Returns:
            UpdateResult with details of the rollback
        """
        project_dir = self.projects_dir / project_name
        backup_dir = project_dir / ".workflow" / "backups" / backup_id

        if not backup_dir.exists():
            return UpdateResult(
                success=False,
                errors=[f"Backup '{backup_id}' not found"],
            )

        files_restored = []
        errors = []

        try:
            # Restore backed up files
            for src_path in backup_dir.rglob("*"):
                if src_path.is_file() and src_path.name != "backup_metadata.json":
                    rel_path = src_path.relative_to(backup_dir)
                    dst_path = project_dir / rel_path

                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    files_restored.append(str(rel_path))

        except Exception as e:
            errors.append(str(e))

        return UpdateResult(
            success=len(errors) == 0,
            files_updated=files_restored,
            errors=errors,
            message="Rollback successful" if not errors else "Rollback failed",
        )

    def list_backups(self, project_name: str) -> list[dict]:
        """List available backups for a project.

        Args:
            project_name: Name of the project

        Returns:
            List of backup metadata dictionaries
        """
        project_dir = self.projects_dir / project_name
        backups_dir = project_dir / ".workflow" / "backups"

        if not backups_dir.exists():
            return []

        backups = []
        for backup_dir in sorted(backups_dir.iterdir(), reverse=True):
            if backup_dir.is_dir():
                metadata_file = backup_dir / "backup_metadata.json"
                if metadata_file.exists():
                    with open(metadata_file) as f:
                        backups.append(json.load(f))

        return backups

    def check_remote_updates(self) -> dict:
        """Check if meta-architect repo has updates from remote.

        Returns:
            Dictionary with remote update information
        """
        try:
            # Fetch without merging
            result = subprocess.run(
                ["git", "fetch", "--dry-run"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check if there are updates
            result = subprocess.run(
                ["git", "status", "-uno"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )

            behind = "behind" in result.stdout.lower()

            return {
                "has_remote_updates": behind,
                "current_version": self.get_current_version(),
                "message": "Remote updates available" if behind else "Up to date with remote",
            }

        except Exception as e:
            return {
                "has_remote_updates": False,
                "error": str(e),
            }

    def _load_project_config(self, project_name: str) -> Optional[dict]:
        """Load a project's configuration file."""
        config_path = self.projects_dir / project_name / ".project-config.json"
        if not config_path.exists():
            return None

        with open(config_path) as f:
            return json.load(f)

    def _save_project_config(self, project_name: str, config: dict) -> None:
        """Save a project's configuration file."""
        config_path = self.projects_dir / project_name / ".project-config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    def _update_project_version(self, project_name: str) -> None:
        """Update a project's version tracking after sync."""
        config = self._load_project_config(project_name)
        if not config:
            return

        current_version = self.get_current_version()

        if "versioning" not in config:
            config["versioning"] = {}

        config["versioning"]["meta_architect_version"] = current_version
        config["versioning"]["last_sync_version"] = current_version
        config["last_synced"] = datetime.now().isoformat()

        self._save_project_config(project_name, config)

    def _get_files_to_update(self, project_name: str) -> list[str]:
        """Determine which files would be updated for a project."""
        config = self._load_project_config(project_name)
        if not config:
            return []

        template_name = config.get("template", "base")
        template_dir = self.templates_dir / template_name

        files = []

        if (template_dir / "CLAUDE.md.template").exists():
            files.append("CLAUDE.md")
        if (template_dir / "GEMINI.md.template").exists():
            files.append("GEMINI.md")
        if (template_dir / ".cursor" / "rules.template").exists():
            files.append(".cursor/rules")

        return files

    def _parse_changelog_between_versions(
        self,
        from_version: str,
        to_version: str,
    ) -> list[ChangelogEntry]:
        """Parse changelog entries between two versions."""
        if not self.changelog_file.exists():
            return []

        content = self.changelog_file.read_text()
        entries = []

        from_v = VersionInfo.from_string(from_version)
        to_v = VersionInfo.from_string(to_version)

        # Simple regex-based parsing of changelog
        version_pattern = r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})"
        section_pattern = r"^### (.+)$"
        item_pattern = r"^- (.+)$"

        current_entry = None
        current_section = None

        for line in content.split("\n"):
            # Check for version header
            version_match = re.match(version_pattern, line)
            if version_match:
                version_str = version_match.group(1)
                date_str = version_match.group(2)

                entry_v = VersionInfo.from_string(version_str)

                # Only include versions > from_version and <= to_version
                if from_v < entry_v <= to_v:
                    if current_entry:
                        entries.append(current_entry)

                    current_entry = ChangelogEntry(
                        version=version_str,
                        date=date_str,
                        sections={},
                    )
                    current_section = None
                else:
                    current_entry = None
                    current_section = None
                continue

            if current_entry is None:
                continue

            # Check for section header
            section_match = re.match(section_pattern, line)
            if section_match:
                current_section = section_match.group(1)
                current_entry.sections[current_section] = []
                continue

            # Check for list item
            item_match = re.match(item_pattern, line)
            if item_match and current_section:
                current_entry.sections[current_section].append(item_match.group(1))

        # Don't forget the last entry
        if current_entry:
            entries.append(current_entry)

        return entries


def format_update_check(update_info: UpdateInfo, use_colors: bool = True) -> str:
    """Format update check results for display.

    Args:
        update_info: UpdateInfo to format
        use_colors: Whether to use ANSI colors

    Returns:
        Formatted string for display
    """
    lines = []

    # Colors
    if use_colors:
        BOLD = "\033[1m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        RED = "\033[31m"
        RESET = "\033[0m"
        DIM = "\033[2m"
    else:
        BOLD = GREEN = YELLOW = RED = RESET = DIM = ""

    # Header
    lines.append(f"\n{BOLD}Update Check: {update_info.project_name}{RESET}")
    lines.append("-" * 50)

    # Version info
    lines.append(f"  Current version:  {update_info.current_version}")
    lines.append(f"  Latest version:   {update_info.latest_version}")

    # Status
    if update_info.updates_available:
        if update_info.is_breaking_update:
            lines.append(f"  Status:           {RED}Breaking update available{RESET}")
        else:
            lines.append(f"  Status:           {YELLOW}Updates available{RESET}")
    else:
        lines.append(f"  Status:           {GREEN}Up to date{RESET}")

    # Changelog
    if update_info.changelog_entries:
        lines.append("")
        lines.append(f"  {BOLD}Changes since {update_info.current_version}:{RESET}")
        for entry in update_info.changelog_entries:
            lines.append(f"  [{entry.version}] {entry.date}")
            for section, items in entry.sections.items():
                for item in items[:3]:  # Limit items shown
                    # Truncate long items
                    if len(item) > 60:
                        item = item[:57] + "..."
                    lines.append(f"    {DIM}- {item}{RESET}")
                if len(items) > 3:
                    lines.append(f"    {DIM}  ... and {len(items) - 3} more{RESET}")

    # Files to update
    if update_info.files_to_update:
        lines.append("")
        lines.append(f"  {BOLD}Files that would be updated:{RESET}")
        for f in update_info.files_to_update:
            lines.append(f"    - {f}")

    # Action hint
    if update_info.updates_available:
        lines.append("")
        lines.append(f"  Run '/update-project {update_info.project_name}' to apply updates.")

    lines.append("")

    return "\n".join(lines)
