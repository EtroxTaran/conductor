"""Base repository class with common functionality.

Note: Schema v2.0.0 uses per-project database isolation.
Each project gets its own database, so queries don't need project_name filters.
The project_name is used only for:
- Database/connection selection
- Logging and identification
"""

import logging
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from ...security import SecurityValidationError, validate_sql_field
from ..connection import Connection, get_connection

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations.

    Uses per-project database isolation - each project has its own database.
    The project_name determines which database to connect to.

    Attributes:
        project_name: Project this repository operates on (determines database)
        table_name: SurrealDB table name
    """

    table_name: str = ""

    def __init__(self, project_name: str):
        """Initialize repository.

        Args:
            project_name: Project name for database selection
        """
        self.project_name = project_name

    async def _get_connection(self) -> Connection:
        """Get database connection."""
        # This is a helper - actual usage should use context manager
        raise NotImplementedError("Use get_connection context manager")

    def _to_record(self, data: dict[str, Any]) -> T:
        """Convert database record to domain object.

        Override in subclasses for typed conversion.
        """
        return data  # type: ignore

    def _from_record(self, obj: T) -> dict[str, Any]:
        """Convert domain object to database record.

        Override in subclasses for typed conversion.
        """
        if hasattr(obj, "to_dict"):
            return obj.to_dict()  # type: ignore
        return dict(obj)  # type: ignore

    async def find_by_id(self, record_id: str) -> Optional[T]:
        """Find a record by ID.

        Args:
            record_id: Record identifier

        Returns:
            Record if found, None otherwise
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.select(f"{self.table_name}:{record_id}")
            if results:
                return self._to_record(results[0])
            return None

    async def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> list[T]:
        """Find all records with pagination.

        Note: Database is already scoped to project, no project_name filter needed.

        Args:
            limit: Maximum records to return
            offset: Number of records to skip
            order_by: Field to order by
            descending: Sort direction

        Returns:
            List of records
        """
        try:
            validated_order_by = validate_sql_field(order_by)
        except SecurityValidationError:
            validated_order_by = "created_at"
            logger.warning(f"Invalid order_by field '{order_by}', using 'created_at'")

        direction = "DESC" if descending else "ASC"
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                f"""
                SELECT * FROM {self.table_name}
                ORDER BY {validated_order_by} {direction}
                LIMIT $limit START $offset
                """,
                {
                    "limit": limit,
                    "offset": offset,
                },
            )
            return [self._to_record(r) for r in results]

    async def count(self) -> int:
        """Count total records.

        Returns:
            Total count
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                f"""
                SELECT count() as total FROM {self.table_name}
                GROUP ALL
                """,
            )
            if results:
                return int(results[0].get("total", 0))
            return 0

    async def create(self, data: dict[str, Any], record_id: Optional[str] = None) -> T:
        """Create a new record.

        Note: project_name is not stored in records (database is already scoped).

        Args:
            data: Record data
            record_id: Optional specific ID

        Returns:
            Created record
        """
        data["created_at"] = datetime.now().isoformat()

        async with get_connection(self.project_name) as conn:
            result = await conn.create(self.table_name, data, record_id)
            return self._to_record(result)

    async def update(self, record_id: str, data: dict[str, Any]) -> Optional[T]:
        """Update a record.

        Args:
            record_id: Record identifier
            data: Fields to update

        Returns:
            Updated record or None
        """
        data["updated_at"] = datetime.now().isoformat()

        async with get_connection(self.project_name) as conn:
            result = await conn.update(f"{self.table_name}:{record_id}", data)
            if result:
                return self._to_record(result)
            return None

    async def delete(self, record_id: str) -> bool:
        """Delete a record.

        Args:
            record_id: Record identifier

        Returns:
            True if deleted
        """
        async with get_connection(self.project_name) as conn:
            result = await conn.delete(f"{self.table_name}:{record_id}")
            return bool(result)

    async def delete_all(self) -> int:
        """Delete all records in this table.

        Note: Database is already scoped to project.

        Returns:
            Number of records deleted
        """
        async with get_connection(self.project_name) as conn:
            results = await conn.query(
                f"""
                DELETE FROM {self.table_name}
                RETURN BEFORE
                """,
            )
            return len(results)
