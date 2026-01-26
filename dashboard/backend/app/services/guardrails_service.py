"""Guardrails service for managing project and global guardrails."""

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GuardrailRecord:
    """Represents a guardrail applied to a project."""

    item_id: str
    item_type: str
    enabled: bool = True
    delivery_method: str = "file"
    version_applied: int = 1
    applied_at: str = ""
    file_path: Optional[str] = None


@dataclass
class ToggleResult:
    """Result of toggling a guardrail."""

    item_id: str
    enabled: bool
    message: str


@dataclass
class PromoteResult:
    """Result of promoting a guardrail to global collection."""

    item_id: str
    promoted: bool
    source_project: str
    destination_path: Optional[str] = None
    message: str = ""
    errors: list[str] = field(default_factory=list)


class GuardrailsService:
    """Service for managing guardrails.

    Consolidates logic for listing, toggling, and promoting guardrails
    that was previously duplicated across projects.py and collection.py.
    """

    def __init__(self, conductor_root: Path):
        """Initialize the service.

        Args:
            conductor_root: Path to the conductor root directory
        """
        self.conductor_root = conductor_root
        self.collection_dir = conductor_root / "collection"

    async def list_project_guardrails(
        self,
        project_name: str,
        project_dir: Path,
    ) -> list[GuardrailRecord]:
        """List all guardrails applied to a project.

        Args:
            project_name: Name of the project
            project_dir: Path to the project directory

        Returns:
            List of guardrail records
        """
        guardrails = []

        # Try database first
        try:
            from orchestrator.db.connection import get_connection

            async with get_connection(project_name) as conn:
                results = await conn.query(
                    "SELECT * FROM project_guardrails WHERE project_id = $pid",
                    {"pid": project_name},
                )
                for record in results or []:
                    guardrails.append(
                        GuardrailRecord(
                            item_id=record.get("item_id", ""),
                            item_type=record.get("item_type", ""),
                            enabled=record.get("enabled", True),
                            delivery_method=record.get("delivery_method", "file"),
                            version_applied=record.get("version_applied", 1),
                            applied_at=record.get("applied_at", ""),
                            file_path=record.get("file_path"),
                        )
                    )
                return guardrails
        except Exception as e:
            logger.debug(f"Database not available, falling back to manifest: {e}")

        # Fallback: read from manifest file
        import json

        manifest_path = project_dir / ".conductor" / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                for item in manifest.get("items", []):
                    guardrails.append(
                        GuardrailRecord(
                            item_id=item.get("id", ""),
                            item_type=item.get("type", ""),
                            enabled=item.get("enabled", True),
                            delivery_method=item.get("delivery_method", "file"),
                            version_applied=item.get("version", 1),
                            applied_at=item.get("applied_at", ""),
                            file_path=item.get("file_path"),
                        )
                    )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read manifest: {e}")

        return guardrails

    async def toggle_guardrail(
        self,
        project_name: str,
        item_id: str,
        enabled: Optional[bool] = None,
    ) -> ToggleResult:
        """Toggle a guardrail's enabled status.

        Args:
            project_name: Name of the project
            item_id: ID of the guardrail to toggle
            enabled: Explicit enabled value, or None to toggle

        Returns:
            ToggleResult with new state

        Raises:
            ValueError: If guardrail not found
        """
        from orchestrator.db.connection import get_connection

        async with get_connection(project_name) as conn:
            # Find existing record
            results = await conn.query(
                "SELECT * FROM project_guardrails WHERE project_id = $pid AND item_id = $iid",
                {"pid": project_name, "iid": item_id},
            )

            if not results:
                raise ValueError(f"Guardrail '{item_id}' not found for project")

            record = results[0]
            current_enabled = record.get("enabled", True)

            # Determine new value
            new_enabled = not current_enabled if enabled is None else enabled

            # Update record
            await conn.query(
                "UPDATE project_guardrails SET enabled = $enabled WHERE project_id = $pid AND item_id = $iid",
                {"pid": project_name, "iid": item_id, "enabled": new_enabled},
            )

            return ToggleResult(
                item_id=item_id,
                enabled=new_enabled,
                message=f"Guardrail {'enabled' if new_enabled else 'disabled'}",
            )

    async def promote_to_global(
        self,
        project_name: str,
        project_dir: Path,
        item_id: str,
    ) -> PromoteResult:
        """Promote a project-specific guardrail to the global collection.

        Args:
            project_name: Name of the project
            project_dir: Path to the project directory
            item_id: ID of the guardrail to promote

        Returns:
            PromoteResult with promotion status
        """
        from orchestrator.db.connection import get_connection

        result = PromoteResult(
            item_id=item_id,
            promoted=False,
            source_project=project_name,
        )

        try:
            async with get_connection(project_name) as conn:
                # Get the project guardrail
                existing = await conn.query(
                    "SELECT * FROM project_guardrails WHERE project_id = $pid AND item_id = $iid",
                    {"pid": project_name, "iid": item_id},
                )

                if not existing:
                    result.message = f"Guardrail '{item_id}' not found for project"
                    return result

                record = existing[0]
                file_path = record.get("file_path")
                item_type = record.get("item_type", "rule")

                if not file_path:
                    result.message = "Cannot promote guardrail without file path"
                    return result

                # Find the source file
                source_file = project_dir / file_path
                if not source_file.exists():
                    result.message = f"Source file not found: {file_path}"
                    result.errors.append(f"File not found: {source_file}")
                    return result

                # Determine destination in collection
                dest_dir = self.collection_dir / item_type / "from_projects"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / f"{item_id}.md"

                # Copy file to collection
                shutil.copy2(source_file, dest_file)
                result.destination_path = str(dest_file.relative_to(self.conductor_root))

                # Create metadata in database
                try:
                    from orchestrator.collection.service import CollectionService

                    service = CollectionService()
                    content = dest_file.read_text()

                    # Create the item in the collection
                    await service.create_item(
                        name=item_id,
                        item_type=item_type,
                        category="from_projects",
                        content=content,
                        summary=f"Promoted from project {project_name}",
                    )
                except Exception as e:
                    result.errors.append(f"Failed to create collection metadata: {e}")

                # Mark as promoted in project_guardrails
                await conn.query(
                    "UPDATE project_guardrails SET promoted = true, promoted_at = $time WHERE project_id = $pid AND item_id = $iid",
                    {
                        "pid": project_name,
                        "iid": item_id,
                        "time": datetime.now().isoformat(),
                    },
                )

                result.promoted = True
                result.message = f"Guardrail '{item_id}' promoted to global collection"

        except Exception as e:
            logger.error(f"Failed to promote guardrail: {e}")
            result.message = str(e)
            result.errors.append(str(e))

        return result


# Singleton instance
_guardrails_service: Optional[GuardrailsService] = None


def get_guardrails_service() -> GuardrailsService:
    """Get the guardrails service singleton."""
    global _guardrails_service
    if _guardrails_service is None:
        from ..config import get_settings

        settings = get_settings()
        _guardrails_service = GuardrailsService(settings.conductor_root)
    return _guardrails_service
