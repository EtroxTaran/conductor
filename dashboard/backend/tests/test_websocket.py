"""Tests for WebSocket connection manager."""

from datetime import datetime
from enum import Enum
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.websocket.manager import (
    ConnectionManager,
    WebSocketJSONEncoder,
    _serialize_for_websocket,
    get_connection_manager,
)


class TestSerializeForWebSocket:
    """Tests for _serialize_for_websocket helper function."""

    def test_serialize_none(self):
        """Test serializing None."""
        assert _serialize_for_websocket(None) is None

    def test_serialize_primitive_types(self):
        """Test serializing primitive types."""
        assert _serialize_for_websocket("hello") == "hello"
        assert _serialize_for_websocket(42) == 42
        assert _serialize_for_websocket(3.14) == 3.14
        assert _serialize_for_websocket(True) is True

    def test_serialize_enum(self):
        """Test serializing enum values."""

        class Status(Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        assert _serialize_for_websocket(Status.ACTIVE) == "active"

    def test_serialize_datetime(self):
        """Test serializing datetime."""
        dt = datetime(2026, 1, 26, 12, 0, 0)
        assert _serialize_for_websocket(dt) == "2026-01-26T12:00:00"

    def test_serialize_dict(self):
        """Test serializing dictionary with nested values."""
        data = {"name": "test", "count": 5, "nested": {"key": "value"}}
        result = _serialize_for_websocket(data)
        assert result == {"name": "test", "count": 5, "nested": {"key": "value"}}

    def test_serialize_list(self):
        """Test serializing list."""
        data = [1, "two", {"three": 3}]
        result = _serialize_for_websocket(data)
        assert result == [1, "two", {"three": 3}]

    def test_serialize_object_with_to_dict(self):
        """Test serializing object with to_dict method."""
        mock_obj = MagicMock()
        mock_obj.to_dict.return_value = {"key": "value"}

        result = _serialize_for_websocket(mock_obj)
        assert result == {"key": "value"}


class TestWebSocketJSONEncoder:
    """Tests for WebSocketJSONEncoder."""

    def test_encode_enum(self):
        """Test encoding enum."""

        class Color(Enum):
            RED = "red"

        encoder = WebSocketJSONEncoder()
        result = encoder.default(Color.RED)
        assert result == "red"

    def test_encode_datetime(self):
        """Test encoding datetime."""
        encoder = WebSocketJSONEncoder()
        dt = datetime(2026, 1, 26, 10, 30, 0)
        result = encoder.default(dt)
        assert result == "2026-01-26T10:30:00"

    def test_encode_object_with_to_dict(self):
        """Test encoding object with to_dict."""
        mock_obj = MagicMock()
        mock_obj.to_dict.return_value = {"data": "value"}

        encoder = WebSocketJSONEncoder()
        result = encoder.default(mock_obj)
        assert result == {"data": "value"}


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance."""
        return ConnectionManager(heartbeat_interval=30)

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.client_state = MagicMock()
        return ws

    def test_init(self, manager: ConnectionManager):
        """Test ConnectionManager initialization."""
        assert manager.heartbeat_interval == 30
        assert manager._connections == {}
        assert manager._global_connections == []
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_connect_global(self, manager: ConnectionManager, mock_websocket: AsyncMock):
        """Test connecting a global websocket."""
        await manager.connect(mock_websocket)

        mock_websocket.accept.assert_called_once()
        assert mock_websocket in manager._global_connections
        assert manager.connection_count == 1

    @pytest.mark.asyncio
    async def test_connect_project(self, manager: ConnectionManager, mock_websocket: AsyncMock):
        """Test connecting a project-specific websocket."""
        await manager.connect(mock_websocket, project_name="test-project")

        mock_websocket.accept.assert_called_once()
        assert "test-project" in manager._connections
        assert mock_websocket in manager._connections["test-project"]
        assert manager.get_project_connection_count("test-project") == 1

    @pytest.mark.asyncio
    async def test_disconnect_global(self, manager: ConnectionManager, mock_websocket: AsyncMock):
        """Test disconnecting a global websocket."""
        await manager.connect(mock_websocket)
        assert manager.connection_count == 1

        await manager.disconnect(mock_websocket)
        assert mock_websocket not in manager._global_connections
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_project(self, manager: ConnectionManager, mock_websocket: AsyncMock):
        """Test disconnecting a project websocket."""
        await manager.connect(mock_websocket, project_name="test-project")
        assert manager.get_project_connection_count("test-project") == 1

        await manager.disconnect(mock_websocket, project_name="test-project")
        assert manager.get_project_connection_count("test-project") == 0

    def test_connection_count(self, manager: ConnectionManager):
        """Test connection count property."""
        assert manager.connection_count == 0

        manager._global_connections.append(MagicMock())
        assert manager.connection_count == 1

        manager._connections["project1"] = [MagicMock(), MagicMock()]
        assert manager.connection_count == 3

    def test_get_project_connection_count(self, manager: ConnectionManager):
        """Test get_project_connection_count method."""
        assert manager.get_project_connection_count("nonexistent") == 0

        manager._connections["test"] = [MagicMock()]
        assert manager.get_project_connection_count("test") == 1


class TestGetConnectionManager:
    """Tests for get_connection_manager singleton."""

    def test_get_connection_manager_returns_manager(self):
        """Test that get_connection_manager returns a ConnectionManager."""
        # Reset singleton for testing
        import app.websocket.manager as mgr_module

        mgr_module._manager = None

        manager = get_connection_manager()

        assert isinstance(manager, ConnectionManager)

    def test_get_connection_manager_singleton(self):
        """Test that get_connection_manager returns same instance."""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()

        assert manager1 is manager2
