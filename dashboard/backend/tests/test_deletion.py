"""Tests for safe deletion with confirmation tokens."""

import time
from pathlib import Path

from app.security.deletion import (
    DeletionConfirmation,
    DeletionConfirmationManager,
    get_deletion_manager,
)


class TestDeletionConfirmation:
    """Tests for DeletionConfirmation dataclass."""

    def test_is_expired_false_when_fresh(self):
        """Fresh confirmation should not be expired."""
        conf = DeletionConfirmation(
            token="test-token",
            project_name="test-project",
            files_to_delete=["/path/to/file"],
        )
        assert conf.is_expired is False

    def test_is_expired_true_when_old(self):
        """Old confirmation should be expired."""
        conf = DeletionConfirmation(
            token="test-token",
            project_name="test-project",
            files_to_delete=["/path/to/file"],
            created_at=time.time() - 400,  # 400 seconds ago (> 300 limit)
        )
        assert conf.is_expired is True


class TestDeletionConfirmationManager:
    """Tests for DeletionConfirmationManager."""

    def test_singleton_pattern(self):
        """Manager should be a singleton."""
        manager1 = DeletionConfirmationManager()
        manager2 = DeletionConfirmationManager()
        assert manager1 is manager2

    def test_create_confirmation(self, tmp_path: Path):
        """Should create a confirmation with token and file list."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        # Create some files
        (project_dir / ".workflow").mkdir()
        (project_dir / ".project-config.json").write_text("{}")
        (project_dir / "src").mkdir()
        (project_dir / "src" / "main.py").write_text("# code")

        manager = get_deletion_manager()
        conf = manager.create_confirmation(
            project_name="test-project",
            project_dir=project_dir,
            remove_source=True,
        )

        assert conf.token is not None
        assert len(conf.token) > 20  # Secure token should be long
        assert conf.project_name == "test-project"
        assert conf.remove_source is True
        assert len(conf.files_to_delete) > 0
        assert any(".workflow" in f for f in conf.files_to_delete)

    def test_verify_and_consume_valid_token(self, tmp_path: Path):
        """Valid token should be verified and consumed."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".workflow").mkdir()

        manager = get_deletion_manager()
        conf = manager.create_confirmation(
            project_name="test-project",
            project_dir=project_dir,
            remove_source=False,
        )

        # First verification should succeed
        result = manager.verify_and_consume(conf.token)
        assert result is not None
        assert result.project_name == "test-project"

        # Second verification should fail (consumed)
        result2 = manager.verify_and_consume(conf.token)
        assert result2 is None

    def test_verify_invalid_token(self):
        """Invalid token should return None."""
        manager = get_deletion_manager()
        result = manager.verify_and_consume("invalid-token-12345")
        assert result is None

    def test_verify_expired_token(self, tmp_path: Path):
        """Expired token should return None."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".workflow").mkdir()

        manager = get_deletion_manager()
        conf = manager.create_confirmation(
            project_name="test-project",
            project_dir=project_dir,
            remove_source=False,
        )

        # Manually expire the token
        manager._confirmations[conf.token].created_at = time.time() - 400

        result = manager.verify_and_consume(conf.token)
        assert result is None

    def test_safe_deletion_files_list(self, tmp_path: Path):
        """Safe deletion should only list workflow files."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".workflow").mkdir()
        (project_dir / ".project-config.json").write_text("{}")
        (project_dir / "src").mkdir()
        (project_dir / "src" / "main.py").write_text("# code")

        manager = get_deletion_manager()
        conf = manager.create_confirmation(
            project_name="test-project",
            project_dir=project_dir,
            remove_source=False,  # Safe deletion
        )

        # Should only include workflow files, not source files
        assert any(".workflow" in f for f in conf.files_to_delete)
        assert any(".project-config.json" in f for f in conf.files_to_delete)
        assert not any("src" in f for f in conf.files_to_delete)


class TestGetDeletionManager:
    """Tests for get_deletion_manager helper."""

    def test_returns_singleton(self):
        """Should always return the same instance."""
        manager1 = get_deletion_manager()
        manager2 = get_deletion_manager()
        assert manager1 is manager2
