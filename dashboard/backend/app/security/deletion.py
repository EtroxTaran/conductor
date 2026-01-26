"""Safe deletion with confirmation tokens."""

import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Optional

from ..constants import SafetyLimits


@dataclass
class DeletionConfirmation:
    """Represents a pending deletion confirmation."""

    token: str
    project_name: str
    files_to_delete: list[str]
    created_at: float = field(default_factory=time.time)
    remove_source: bool = False

    @property
    def is_expired(self) -> bool:
        """Check if the confirmation token has expired."""
        return time.time() - self.created_at > SafetyLimits.CONFIRMATION_TOKEN_EXPIRY_SECONDS


class DeletionConfirmationManager:
    """Manages deletion confirmation tokens.

    Thread-safe singleton for managing destructive operation confirmations.
    """

    _instance: Optional["DeletionConfirmationManager"] = None
    _lock = Lock()

    def __new__(cls) -> "DeletionConfirmationManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._confirmations: dict[str, DeletionConfirmation] = {}
                    cls._instance._confirmations_lock = Lock()
        return cls._instance

    def create_confirmation(
        self,
        project_name: str,
        project_dir: Path,
        remove_source: bool = False,
    ) -> DeletionConfirmation:
        """Create a new deletion confirmation token.

        Args:
            project_name: Name of the project to delete
            project_dir: Path to the project directory
            remove_source: Whether to also remove source files

        Returns:
            DeletionConfirmation with token and file list
        """
        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Build list of files/dirs to be deleted
        files_to_delete = []

        # Always include workflow state
        workflow_dir = project_dir / ".workflow"
        if workflow_dir.exists():
            files_to_delete.append(str(workflow_dir))

        config_file = project_dir / ".project-config.json"
        if config_file.exists():
            files_to_delete.append(str(config_file))

        # If removing source, list top-level items
        if remove_source:
            for item in project_dir.iterdir():
                if item.name not in {".workflow", ".project-config.json"}:
                    files_to_delete.append(str(item))

        confirmation = DeletionConfirmation(
            token=token,
            project_name=project_name,
            files_to_delete=files_to_delete,
            remove_source=remove_source,
        )

        # Clean up expired tokens and store new one
        with self._confirmations_lock:
            self._cleanup_expired()
            self._confirmations[token] = confirmation

        return confirmation

    def verify_and_consume(self, token: str) -> Optional[DeletionConfirmation]:
        """Verify a confirmation token and consume it.

        Args:
            token: The confirmation token

        Returns:
            DeletionConfirmation if valid, None otherwise
        """
        with self._confirmations_lock:
            confirmation = self._confirmations.pop(token, None)

        if confirmation is None:
            return None

        if confirmation.is_expired:
            return None

        return confirmation

    def _cleanup_expired(self) -> None:
        """Remove expired tokens. Must be called with lock held."""
        expired_tokens = [token for token, conf in self._confirmations.items() if conf.is_expired]
        for token in expired_tokens:
            del self._confirmations[token]


# Singleton accessor
def get_deletion_manager() -> DeletionConfirmationManager:
    """Get the deletion confirmation manager singleton."""
    return DeletionConfirmationManager()
