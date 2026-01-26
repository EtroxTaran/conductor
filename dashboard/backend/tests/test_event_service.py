"""Tests for event service."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.event_service import EventService


@pytest.fixture
def mock_connection_manager():
    """Create mock connection manager."""
    mock = MagicMock()
    mock.broadcast_to_project = AsyncMock()
    return mock


class TestEventService:
    """Tests for EventService class."""

    def test_init(self, temp_project_dir: Path):
        """Test EventService initialization."""
        service = EventService(temp_project_dir)

        assert service.project_dir == temp_project_dir
        assert service.project_name == temp_project_dir.name
        assert service.workflow_dir == temp_project_dir / ".workflow"


class TestGetRecentEvents:
    """Tests for get_recent_events method."""

    def test_get_recent_events_no_log(self, temp_project_dir: Path):
        """Test get_recent_events when no log exists."""
        service = EventService(temp_project_dir)

        result = service.get_recent_events()

        assert result == []

    def test_get_recent_events_with_events(self, temp_project_dir: Path):
        """Test get_recent_events with existing events."""
        service = EventService(temp_project_dir)

        # Create log file
        log_dir = temp_project_dir / ".workflow"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "coordination.log"

        events = [
            {"type": "action", "message": "Started"},
            {"type": "action", "message": "Completed"},
        ]
        with open(log_file, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        result = service.get_recent_events()

        assert len(result) == 2

    def test_get_recent_events_with_limit(self, temp_project_dir: Path):
        """Test get_recent_events respects limit."""
        service = EventService(temp_project_dir)

        # Create log file with many events
        log_dir = temp_project_dir / ".workflow"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "coordination.log"

        with open(log_file, "w") as f:
            for i in range(10):
                f.write(json.dumps({"type": "action", "index": i}) + "\n")

        result = service.get_recent_events(limit=5)

        assert len(result) == 5
        # Should be the last 5 events
        assert result[0]["index"] == 5

    def test_get_recent_events_with_type_filter(self, temp_project_dir: Path):
        """Test get_recent_events filters by type."""
        service = EventService(temp_project_dir)

        # Create log file
        log_dir = temp_project_dir / ".workflow"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "coordination.log"

        events = [
            {"type": "action", "message": "Action 1"},
            {"type": "error", "message": "Error 1"},
            {"type": "action", "message": "Action 2"},
        ]
        with open(log_file, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        result = service.get_recent_events(event_type="error")

        assert len(result) == 1
        assert result[0]["type"] == "error"


class TestGetErrorEvents:
    """Tests for get_error_events method."""

    def test_get_error_events(self, temp_project_dir: Path):
        """Test get_error_events returns only errors."""
        service = EventService(temp_project_dir)

        # Create log file
        log_dir = temp_project_dir / ".workflow"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "coordination.log"

        events = [
            {"type": "action", "message": "Success"},
            {"type": "error", "message": "Failed"},
        ]
        with open(log_file, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        result = service.get_error_events()

        assert len(result) == 1
        assert result[0]["type"] == "error"


class TestStreamEvents:
    """Tests for stream_events method."""

    @pytest.mark.asyncio
    async def test_stream_events_no_log(self, temp_project_dir: Path):
        """Test stream_events when no log exists."""
        service = EventService(temp_project_dir)

        events = []
        async for event in service.stream_events():
            events.append(event)

        assert events == []

    @pytest.mark.asyncio
    async def test_stream_events_with_events(self, temp_project_dir: Path):
        """Test stream_events with existing events."""
        service = EventService(temp_project_dir)

        # Create log file
        log_dir = temp_project_dir / ".workflow"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "coordination.log"

        test_events = [
            {"type": "action", "message": "Event 1"},
            {"type": "action", "message": "Event 2"},
        ]
        with open(log_file, "w") as f:
            for event in test_events:
                f.write(json.dumps(event) + "\n")

        events = []
        async for event in service.stream_events():
            events.append(event)

        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_stream_events_with_since(self, temp_project_dir: Path):
        """Test stream_events filters by timestamp."""
        service = EventService(temp_project_dir)

        # Create log file
        log_dir = temp_project_dir / ".workflow"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "coordination.log"

        test_events = [
            {"type": "action", "message": "Old", "timestamp": "2026-01-01T10:00:00"},
            {"type": "action", "message": "New", "timestamp": "2026-01-26T10:00:00"},
        ]
        with open(log_file, "w") as f:
            for event in test_events:
                f.write(json.dumps(event) + "\n")

        since = datetime(2026, 1, 15)
        events = []
        async for event in service.stream_events(since=since):
            events.append(event)

        assert len(events) == 1
        assert events[0]["message"] == "New"


class TestStartStopWatching:
    """Tests for start_watching and stop_watching methods."""

    @pytest.mark.asyncio
    async def test_stop_watching(self, temp_project_dir: Path):
        """Test stop_watching sets stop event."""
        service = EventService(temp_project_dir)

        assert not service._stop_event.is_set()

        await service.stop_watching()

        assert service._stop_event.is_set()
