"""Live Query support for real-time monitoring.

Provides event-driven subscriptions to database changes.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from .connection import get_connection, Connection

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Live query event types."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class LiveEvent:
    """A live query event.

    Attributes:
        event_type: Type of change (CREATE, UPDATE, DELETE)
        table: Table that changed
        record_id: ID of affected record
        data: Record data (current for CREATE/UPDATE, previous for DELETE)
        timestamp: When event occurred
    """

    event_type: EventType
    table: str
    record_id: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_surreal_event(cls, event: dict[str, Any]) -> "LiveEvent":
        """Create from SurrealDB live query notification."""
        action = event.get("action", "UPDATE").upper()
        result = event.get("result", {})

        # Extract record ID from SurrealDB format
        record_id = ""
        if "id" in result:
            # SurrealDB returns id as "table:id"
            full_id = str(result["id"])
            if ":" in full_id:
                record_id = full_id.split(":", 1)[1]
            else:
                record_id = full_id

        return cls(
            event_type=EventType(action) if action in EventType.__members__ else EventType.UPDATE,
            table=event.get("table", ""),
            record_id=record_id,
            data=result,
        )


EventCallback = Callable[[LiveEvent], None]
AsyncEventCallback = Callable[[LiveEvent], Any]


class LiveQueryManager:
    """Manages Live Query subscriptions.

    Provides a unified interface for subscribing to database changes
    with automatic reconnection and event dispatch.
    """

    def __init__(self, project_name: str):
        """Initialize live query manager.

        Args:
            project_name: Project for database selection
        """
        self.project_name = project_name
        self._subscriptions: dict[str, tuple[str, EventCallback | AsyncEventCallback]] = {}
        self._connection: Optional[Connection] = None
        self._running = False
        self._lock = asyncio.Lock()

    async def _ensure_connection(self) -> Connection:
        """Ensure we have an active connection."""
        async with self._lock:
            if self._connection is None or not self._connection.is_connected:
                # Get a new connection
                async with get_connection(self.project_name) as conn:
                    self._connection = conn
            return self._connection

    async def subscribe(
        self,
        table: str,
        callback: EventCallback | AsyncEventCallback,
        subscription_id: Optional[str] = None,
    ) -> str:
        """Subscribe to changes on a table.

        Args:
            table: Table name to watch
            callback: Function to call on changes
            subscription_id: Optional custom subscription ID

        Returns:
            Subscription ID for later unsubscription
        """
        conn = await self._ensure_connection()

        # Wrap callback to handle SurrealDB event format
        async def surreal_callback(event: dict[str, Any]) -> None:
            try:
                live_event = LiveEvent.from_surreal_event(event)
                live_event.table = table

                if asyncio.iscoroutinefunction(callback):
                    await callback(live_event)
                else:
                    callback(live_event)
            except Exception as e:
                logger.error(f"Error in live query callback: {e}")

        # Start live query
        live_id = await conn.live(table, surreal_callback)

        # Store subscription
        sub_id = subscription_id or f"{table}_{live_id}"
        self._subscriptions[sub_id] = (live_id, callback)

        logger.info(f"Subscribed to {table} changes: {sub_id}")
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from a live query.

        Args:
            subscription_id: Subscription to cancel

        Returns:
            True if unsubscribed
        """
        if subscription_id not in self._subscriptions:
            return False

        live_id, _ = self._subscriptions.pop(subscription_id)

        if self._connection and self._connection.is_connected:
            await self._connection.kill(live_id)

        logger.info(f"Unsubscribed: {subscription_id}")
        return True

    async def unsubscribe_all(self) -> int:
        """Unsubscribe from all live queries.

        Returns:
            Number of subscriptions cancelled
        """
        count = 0
        for sub_id in list(self._subscriptions.keys()):
            if await self.unsubscribe(sub_id):
                count += 1
        return count

    @property
    def active_subscriptions(self) -> list[str]:
        """Get list of active subscription IDs."""
        return list(self._subscriptions.keys())


class WorkflowMonitor:
    """High-level workflow monitoring using Live Queries.

    Provides convenient methods for monitoring workflow progress.
    """

    def __init__(self, project_name: str):
        """Initialize workflow monitor.

        Args:
            project_name: Project to monitor
        """
        self.project_name = project_name
        self._manager = LiveQueryManager(project_name)
        self._handlers: dict[str, list[EventCallback | AsyncEventCallback]] = {
            "workflow_state": [],
            "tasks": [],
            "audit_entries": [],
        }

    async def on_state_change(
        self,
        callback: EventCallback | AsyncEventCallback,
    ) -> str:
        """Subscribe to workflow state changes.

        Args:
            callback: Called when workflow state changes

        Returns:
            Subscription ID
        """
        self._handlers["workflow_state"].append(callback)
        return await self._manager.subscribe(
            "workflow_state",
            self._dispatch_state_change,
            "workflow_state",
        )

    async def _dispatch_state_change(self, event: LiveEvent) -> None:
        """Dispatch state change to all handlers."""
        for handler in self._handlers["workflow_state"]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"State change handler error: {e}")

    async def on_task_change(
        self,
        callback: EventCallback | AsyncEventCallback,
    ) -> str:
        """Subscribe to task changes.

        Args:
            callback: Called when any task changes

        Returns:
            Subscription ID
        """
        self._handlers["tasks"].append(callback)
        return await self._manager.subscribe(
            "tasks",
            self._dispatch_task_change,
            "tasks",
        )

    async def _dispatch_task_change(self, event: LiveEvent) -> None:
        """Dispatch task change to all handlers."""
        for handler in self._handlers["tasks"]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Task change handler error: {e}")

    async def on_audit_entry(
        self,
        callback: EventCallback | AsyncEventCallback,
    ) -> str:
        """Subscribe to new audit entries.

        Args:
            callback: Called when new audit entry is created

        Returns:
            Subscription ID
        """
        self._handlers["audit_entries"].append(callback)
        return await self._manager.subscribe(
            "audit_entries",
            self._dispatch_audit_entry,
            "audit_entries",
        )

    async def _dispatch_audit_entry(self, event: LiveEvent) -> None:
        """Dispatch audit entry to all handlers."""
        if event.event_type != EventType.CREATE:
            return  # Only dispatch new entries

        for handler in self._handlers["audit_entries"]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Audit entry handler error: {e}")

    async def stop(self) -> None:
        """Stop all monitoring subscriptions."""
        await self._manager.unsubscribe_all()
        for handlers in self._handlers.values():
            handlers.clear()

    async def __aenter__(self) -> "WorkflowMonitor":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()


def create_workflow_monitor(project_name: str) -> WorkflowMonitor:
    """Create a workflow monitor.

    Args:
        project_name: Project to monitor

    Returns:
        WorkflowMonitor instance
    """
    return WorkflowMonitor(project_name)


# Example usage:
#
# async def main():
#     async with create_workflow_monitor("my-project") as monitor:
#         # Subscribe to state changes
#         await monitor.on_state_change(lambda e: print(f"State changed: {e.data}"))
#
#         # Subscribe to task changes
#         await monitor.on_task_change(lambda e: print(f"Task {e.record_id}: {e.data.get('status')}"))
#
#         # Keep running
#         await asyncio.sleep(3600)
