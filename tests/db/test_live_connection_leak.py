"""Regression test for connection leak in LiveQueryManager._ensure_connection.

When connect() fails after pool acquire + counter increment, the connection
must be returned to the pool and the counter decremented.
"""

import asyncio
from dataclasses import dataclass

import pytest

from orchestrator.db.live import LiveQueryManager


@dataclass
class FakePoolStats:
    active_connections: int = 0


class FakePool:
    """Minimal fake connection pool for testing."""

    def __init__(self):
        self._initialized = True
        self._available = asyncio.Queue()
        self._stats = FakePoolStats()


class FakeConnection:
    """Minimal fake connection."""

    def __init__(self, *, connected: bool = False):
        self._connected = connected

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self):
        raise ConnectionError("Simulated connect failure")


@pytest.mark.asyncio
async def test_connect_failure_returns_connection_to_pool():
    """When connect() fails, connection must go back to pool and counter must decrement."""
    manager = LiveQueryManager("test-project")

    fake_pool = FakePool()
    fake_conn = FakeConnection(connected=False)
    await fake_pool._available.put(fake_conn)

    manager._pool = fake_pool

    with pytest.raises(ConnectionError, match="Simulated connect failure"):
        await manager._ensure_connection()

    # Connection should be returned to pool
    assert fake_pool._available.qsize() == 1
    returned_conn = await fake_pool._available.get()
    assert returned_conn is fake_conn

    # Active connections counter should be back to 0
    assert fake_pool._stats.active_connections == 0

    # Manager should have cleared its connection reference
    assert manager._connection is None


@pytest.mark.asyncio
async def test_subscribe_timeout_on_hanging_connection():
    """Subscribe must timeout if conn.live() hangs (Fix H3 regression)."""
    manager = LiveQueryManager("test-project")

    fake_pool = FakePool()

    class HangingConnection:
        _connected = True

        @property
        def is_connected(self):
            return self._connected

        async def live(self, table, callback):
            # Simulate hang — never returns
            await asyncio.sleep(999)
            return "never-reached"

    fake_conn = HangingConnection()
    await fake_pool._available.put(fake_conn)
    manager._pool = fake_pool
    manager._connection = fake_conn

    with pytest.raises(asyncio.TimeoutError):
        await manager.subscribe("test_table", lambda e: None)


@pytest.mark.asyncio
async def test_successful_connect_keeps_connection():
    """When connect() succeeds, connection stays acquired."""
    manager = LiveQueryManager("test-project")

    fake_pool = FakePool()

    class SuccessConnection:
        def __init__(self):
            self._connected = False

        @property
        def is_connected(self):
            return self._connected

        async def connect(self):
            self._connected = True

    fake_conn = SuccessConnection()
    await fake_pool._available.put(fake_conn)

    manager._pool = fake_pool

    result = await manager._ensure_connection()

    # Connection should be kept by manager, not returned to pool
    assert fake_pool._available.qsize() == 0
    assert fake_pool._stats.active_connections == 1
    assert result is fake_conn
    assert manager._connection is fake_conn
