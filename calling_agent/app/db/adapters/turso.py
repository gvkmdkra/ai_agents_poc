"""
Turso Database Adapter

Implementation of the DatabaseAdapter interface for Turso (libSQL).
Turso is a SQLite-compatible database with edge replicas.
"""

import json
import logging
import re
from typing import Optional, List, Dict, Any

from app.db.base import DatabaseAdapter
from app.db.models import TURSO_SCHEMA
from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import libsql_client
try:
    import libsql_client
    LIBSQL_AVAILABLE = True
except ImportError:
    LIBSQL_AVAILABLE = False
    logger.warning("libsql_client not installed. Run: pip install libsql-client")


class TursoAdapter(DatabaseAdapter):
    """
    Turso (libSQL) database adapter.

    Uses the libsql_client library for async database operations.
    Compatible with SQLite syntax.
    """

    def __init__(self, db_url: Optional[str] = None, auth_token: Optional[str] = None):
        """
        Initialize Turso adapter.

        Args:
            db_url: Turso database URL (defaults to settings.turso_db_url)
            auth_token: Turso auth token (defaults to settings.turso_db_auth_token)
        """
        self.db_url = db_url or settings.turso_db_url
        self.auth_token = auth_token or settings.turso_db_auth_token
        self._client = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish connection to Turso database."""
        if not LIBSQL_AVAILABLE:
            logger.error("Cannot connect: libsql_client not installed")
            return False

        if not self.db_url or not self.auth_token:
            logger.error("Cannot connect: Missing TURSO_DB_URL or TURSO_DB_AUTH_TOKEN")
            return False

        try:
            self._client = libsql_client.create_client(
                self.db_url,
                auth_token=self.auth_token
            )
            self._connected = True
            logger.info(f"Connected to Turso database: {self.db_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Turso: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close the Turso connection."""
        if self._client:
            try:
                close_fn = getattr(self._client, "close", None)
                if close_fn and callable(close_fn):
                    await close_fn()
            except Exception as e:
                logger.warning(f"Error closing Turso connection: {e}")
            finally:
                self._client = None
                self._connected = False
                logger.info("Disconnected from Turso database")

    async def initialize_schema(self) -> bool:
        """Create necessary tables if they don't exist."""
        if not self._connected or not self._client:
            logger.error("Cannot initialize schema: Not connected")
            return False

        try:
            # Remove SQL comments before splitting
            schema = re.sub(r'--.*$', '', TURSO_SCHEMA, flags=re.MULTILINE)

            # Split schema into individual statements
            statements = [
                stmt.strip()
                for stmt in schema.split(";")
                if stmt.strip()
            ]

            errors = []
            for stmt in statements:
                try:
                    await self._client.execute(stmt)
                except KeyError as e:
                    # libsql_client sometimes has KeyError issues with certain responses
                    # This is usually benign for CREATE TABLE/INDEX IF NOT EXISTS
                    logger.warning(f"KeyError during schema init (usually safe to ignore): {e}")
                    errors.append(str(e))
                except Exception as e:
                    logger.error(f"Error executing schema statement: {e}")
                    errors.append(str(e))

            # Verify tables were created by checking if they exist
            try:
                result = await self._client.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('call_records', 'call_transcripts', 'call_summaries')"
                )
                tables = [row[0] for row in result.rows]
                if len(tables) >= 3:
                    logger.info(f"Turso schema initialized successfully (tables: {tables})")
                    return True
                else:
                    logger.error(f"Schema initialization incomplete, only found tables: {tables}")
                    return False
            except Exception as e:
                logger.error(f"Could not verify schema: {e}")
                return len(errors) == 0

        except Exception as e:
            logger.error(f"Failed to initialize Turso schema: {e}")
            return False

    async def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a raw SQL query."""
        if not self._connected or not self._client:
            raise ConnectionError("Not connected to database")

        try:
            result = await self._client.execute(query, params)
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute query and return single row as dict."""
        if not self._connected or not self._client:
            raise ConnectionError("Not connected to database")

        try:
            result = await self._client.execute(query, params)
            rows = getattr(result, "rows", []) or []
            columns = getattr(result, "columns", []) or []

            if rows and columns:
                return dict(zip(columns, rows[0]))
            return None
        except KeyError as e:
            # libsql_client sometimes has KeyError issues, retry once
            logger.warning(f"KeyError in fetch_one, retrying: {e}")
            try:
                result = await self._client.execute(query, params)
                rows = getattr(result, "rows", []) or []
                columns = getattr(result, "columns", []) or []
                if rows and columns:
                    return dict(zip(columns, rows[0]))
                return None
            except Exception:
                return None
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise

    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and return all rows as list of dicts."""
        if not self._connected or not self._client:
            raise ConnectionError("Not connected to database")

        try:
            result = await self._client.execute(query, params)
            rows = getattr(result, "rows", []) or []
            columns = getattr(result, "columns", []) or []

            if columns:
                return [dict(zip(columns, row)) for row in rows]
            return []
        except KeyError as e:
            # libsql_client sometimes has KeyError issues, retry once
            logger.warning(f"KeyError in fetch_all, retrying: {e}")
            try:
                result = await self._client.execute(query, params)
                rows = getattr(result, "rows", []) or []
                columns = getattr(result, "columns", []) or []
                if columns:
                    return [dict(zip(columns, row)) for row in rows]
                return []
            except Exception:
                return []
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise

    def is_connected(self) -> bool:
        """Check if database connection is active."""
        return self._connected and self._client is not None

    # ==================== Helper Methods ====================

    def _serialize_json(self, data: Any) -> str:
        """Serialize data to JSON string for storage."""
        if data is None:
            return "{}" if isinstance(data, dict) else "[]"
        return json.dumps(data, default=str)

    def _deserialize_json(self, data: str) -> Any:
        """Deserialize JSON string from storage."""
        if not data:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
