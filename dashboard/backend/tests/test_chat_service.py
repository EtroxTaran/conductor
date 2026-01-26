"""Tests for chat service."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.chat_service import ChatHistory, ChatService


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    mock = MagicMock()
    mock.conductor_root = Path("/test/conductor")
    mock.claude_timeout = 300
    return mock


class TestChatService:
    """Tests for ChatService class."""

    def test_init_without_project(self, mock_settings: MagicMock):
        """Test ChatService initialization without project."""
        with patch("app.services.chat_service.get_settings", return_value=mock_settings):
            service = ChatService()

            assert service.project_dir is None

    def test_init_with_project(self, temp_project_dir: Path, mock_settings: MagicMock):
        """Test ChatService initialization with project."""
        with patch("app.services.chat_service.get_settings", return_value=mock_settings):
            service = ChatService(project_dir=temp_project_dir)

            assert service.project_dir == temp_project_dir

    def test_working_dir_with_project(self, temp_project_dir: Path, mock_settings: MagicMock):
        """Test working_dir returns project dir when set."""
        with patch("app.services.chat_service.get_settings", return_value=mock_settings):
            service = ChatService(project_dir=temp_project_dir)

            assert service.working_dir == temp_project_dir

    def test_working_dir_without_project(self, mock_settings: MagicMock):
        """Test working_dir returns conductor root when no project."""
        with patch("app.services.chat_service.get_settings", return_value=mock_settings):
            service = ChatService()

            assert service.working_dir == mock_settings.conductor_root


class TestGetContextSummary:
    """Tests for get_context_summary method."""

    @pytest.mark.asyncio
    async def test_get_context_summary_workspace(self, mock_settings: MagicMock):
        """Test get_context_summary for workspace."""
        with patch("app.services.chat_service.get_settings", return_value=mock_settings):
            service = ChatService()

            result = await service.get_context_summary()

            assert result["type"] == "workspace"
            assert result["path"] == str(mock_settings.conductor_root)

    @pytest.mark.asyncio
    async def test_get_context_summary_project(
        self, temp_project_dir: Path, mock_settings: MagicMock
    ):
        """Test get_context_summary for project."""
        # Create context files
        (temp_project_dir / "CLAUDE.md").write_text("# Claude Context")
        (temp_project_dir / "PRODUCT.md").write_text("# Product")

        with patch("app.services.chat_service.get_settings", return_value=mock_settings):
            service = ChatService(project_dir=temp_project_dir)

            result = await service.get_context_summary()

            assert result["type"] == "project"
            assert result["name"] == temp_project_dir.name
            assert result["has_claude_md"] is True
            assert result["has_product_md"] is True


class TestChatHistory:
    """Tests for ChatHistory class."""

    def test_init(self, temp_project_dir: Path):
        """Test ChatHistory initialization."""
        history = ChatHistory(temp_project_dir)

        assert history.project_dir == temp_project_dir
        assert history.history_file == temp_project_dir / ".workflow" / "chat_history.jsonl"

    def test_get_history_empty(self, temp_project_dir: Path):
        """Test get_history when no history exists."""
        history = ChatHistory(temp_project_dir)

        result = history.get_history()

        assert result == []

    def test_get_history_with_messages(self, temp_project_dir: Path):
        """Test get_history with existing messages."""
        history = ChatHistory(temp_project_dir)

        # Create history file
        history_dir = temp_project_dir / ".workflow"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "chat_history.jsonl"

        messages = [
            {"role": "user", "content": "Hello", "timestamp": 1.0},
            {"role": "assistant", "content": "Hi there!", "timestamp": 2.0},
        ]
        with open(history_file, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        result = history.get_history()

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_get_history_with_limit(self, temp_project_dir: Path):
        """Test get_history respects limit."""
        history = ChatHistory(temp_project_dir)

        # Create history file with many messages
        history_dir = temp_project_dir / ".workflow"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "chat_history.jsonl"

        with open(history_file, "w") as f:
            for i in range(10):
                f.write(json.dumps({"role": "user", "content": f"Message {i}"}) + "\n")

        result = history.get_history(limit=5)

        assert len(result) == 5
        # Should be the last 5 messages
        assert result[0]["content"] == "Message 5"

    def test_clear(self, temp_project_dir: Path):
        """Test clear removes history file."""
        history = ChatHistory(temp_project_dir)

        # Create history file
        history_dir = temp_project_dir / ".workflow"
        history_dir.mkdir(parents=True, exist_ok=True)
        history_file = history_dir / "chat_history.jsonl"
        history_file.write_text("test")

        assert history_file.exists()

        history.clear()

        assert not history_file.exists()

    def test_clear_no_file(self, temp_project_dir: Path):
        """Test clear when no history file exists."""
        history = ChatHistory(temp_project_dir)

        # Should not raise
        history.clear()
