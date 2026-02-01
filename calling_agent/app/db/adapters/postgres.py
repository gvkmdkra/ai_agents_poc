"""
PostgreSQL Database Adapter (Stub)

Implementation of the DatabaseAdapter interface for PostgreSQL.
This is a stub for future implementation when scaling beyond Turso.

To use PostgreSQL:
1. Install: pip install asyncpg
2. Configure: Set DATABASE_URL in .env
3. Update config.py to add postgres_url setting
"""

import logging
from typing import Optional, List, Dict, Any

from app.db.base import DatabaseAdapter
from app.db.models import POSTGRES_SCHEMA

logger = logging.getLogger(__name__)

# Try to import asyncpg
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False


class PostgresAdapter(DatabaseAdapter):
    """
    PostgreSQL database adapter.

    Uses asyncpg for async database operations.
    This is a stub implementation for future use.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize PostgreSQL adapter.

        Args:
            database_url: PostgreSQL connection URL
                         Format: postgresql://user:password@host:port/database
        """
        self.database_url = database_url
        self._pool = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish connection pool to PostgreSQL database."""
        if not ASYNCPG_AVAILABLE:
            logger.error("Cannot connect: asyncpg not installed. Run: pip install asyncpg")
            return False

        if not self.database_url:
            logger.error("Cannot connect: Missing DATABASE_URL")
            return False

        try:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
            )
            self._connected = True
            logger.info("Connected to PostgreSQL database")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close the PostgreSQL connection pool."""
        if self._pool:
            try:
                await self._pool.close()
            except Exception as e:
                logger.warning(f"Error closing PostgreSQL pool: {e}")
            finally:
                self._pool = None
                self._connected = False
                logger.info("Disconnected from PostgreSQL database")

    async def initialize_schema(self) -> bool:
        """Create necessary tables if they don't exist."""
        if not self._connected or not self._pool:
            logger.error("Cannot initialize schema: Not connected")
            return False

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(POSTGRES_SCHEMA)
            logger.info("PostgreSQL schema initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL schema: {e}")
            return False

    async def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a raw SQL query."""
        if not self._connected or not self._pool:
            raise ConnectionError("Not connected to database")

        try:
            async with self._pool.acquire() as conn:
                # Convert ? placeholders to $1, $2, etc. for asyncpg
                converted_query = self._convert_placeholders(query)
                result = await conn.execute(converted_query, *params)
                return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute query and return single row as dict."""
        if not self._connected or not self._pool:
            raise ConnectionError("Not connected to database")

        try:
            async with self._pool.acquire() as conn:
                converted_query = self._convert_placeholders(query)
                row = await conn.fetchrow(converted_query, *params)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise

    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and return all rows as list of dicts."""
        if not self._connected or not self._pool:
            raise ConnectionError("Not connected to database")

        try:
            async with self._pool.acquire() as conn:
                converted_query = self._convert_placeholders(query)
                rows = await conn.fetch(converted_query, *params)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise

    def is_connected(self) -> bool:
        """Check if database connection is active."""
        return self._connected and self._pool is not None

    def _convert_placeholders(self, query: str) -> str:
        """
        Convert SQLite-style ? placeholders to PostgreSQL $1, $2, etc.

        This allows using the same queries across both databases.
        """
        result = []
        param_index = 1
        i = 0
        while i < len(query):
            if query[i] == "?":
                result.append(f"${param_index}")
                param_index += 1
            else:
                result.append(query[i])
            i += 1
        return "".join(result)
