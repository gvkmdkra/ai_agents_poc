"""
MySQL Service
Database abstraction layer with SSH tunnel support for customer data queries
"""

import re
from typing import List, Dict, Any, Optional, Generator
from contextlib import contextmanager
from decimal import Decimal
from datetime import datetime, date
import pymysql
from sshtunnel import SSHTunnelForwarder

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import DatabaseError

logger = get_logger(__name__)


class MySQLService:
    """
    MySQL database service with SSH tunnel support
    Used for Text-to-SQL queries against customer databases
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ):
        """
        Initialize MySQL service

        Args:
            host: Database host (uses settings if not provided)
            port: Database port (uses settings if not provided)
            user: Database user (uses settings if not provided)
            password: Database password (uses settings if not provided)
            database: Database name (uses settings if not provided)
        """
        self.host = host or settings.mysql_host
        self.port = port or settings.mysql_port
        self.user = user or settings.mysql_user
        self.password = password or settings.mysql_password
        self.database = database or settings.mysql_database

        # SSH tunnel settings
        self.ssh_host = settings.ssh_host
        self.ssh_port = settings.ssh_port
        self.ssh_user = settings.ssh_user
        self.ssh_key_path = settings.ssh_key_path

        self._tunnel = None

    @contextmanager
    def get_connection(self) -> Generator[pymysql.Connection, None, None]:
        """
        Get a database connection with optional SSH tunnel

        Yields:
            Database connection
        """
        tunnel = None
        connection = None

        try:
            # Use SSH tunnel if configured
            if self.ssh_host and self.ssh_key_path:
                tunnel = SSHTunnelForwarder(
                    (self.ssh_host, self.ssh_port),
                    ssh_username=self.ssh_user,
                    ssh_pkey=self.ssh_key_path,
                    remote_bind_address=(self.host, self.port),
                    local_bind_address=('127.0.0.1',)
                )
                tunnel.start()

                connection = pymysql.connect(
                    host='127.0.0.1',
                    port=tunnel.local_bind_port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=30
                )
            else:
                # Direct connection
                connection = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=30
                )

            yield connection

        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseError(f"Connection failed: {e}")

        finally:
            if connection:
                connection.close()
            if tunnel:
                tunnel.close()

    def execute_query(
        self,
        sql: str,
        params: Optional[tuple] = None,
        max_rows: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query safely

        Args:
            sql: SQL query (SELECT only)
            params: Query parameters
            max_rows: Maximum rows to return

        Returns:
            Query results
        """
        # Security check - SELECT only
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise DatabaseError("Only SELECT queries are allowed")

        # Add LIMIT if not present
        if "LIMIT" not in sql_upper:
            sql = f"{sql.rstrip(';')} LIMIT {max_rows}"

        try:
            with self.get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    results = cursor.fetchall()

                    # Sanitize results
                    return self._sanitize_results(results)

        except pymysql.Error as e:
            logger.error(f"Query execution failed: {e}")
            raise DatabaseError(f"Query failed: {e}")

    def _sanitize_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sanitize query results for JSON serialization

        Args:
            results: Raw query results

        Returns:
            Sanitized results
        """
        sanitized = []

        for row in results:
            clean_row = {}
            for key, value in row.items():
                if isinstance(value, Decimal):
                    clean_row[key] = float(value)
                elif isinstance(value, (datetime, date)):
                    clean_row[key] = value.isoformat()
                elif isinstance(value, bytes):
                    clean_row[key] = value.decode('utf-8', errors='ignore')
                else:
                    clean_row[key] = value
            sanitized.append(clean_row)

        return sanitized

    def get_schema(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get database schema (tables and columns)

        Returns:
            Dictionary of table names to column info
        """
        try:
            with self.get_connection() as connection:
                with connection.cursor() as cursor:
                    # Get tables
                    cursor.execute("SHOW TABLES")
                    tables = [list(row.values())[0] for row in cursor.fetchall()]

                    schema = {}
                    for table in tables:
                        cursor.execute(f"DESCRIBE `{table}`")
                        columns = cursor.fetchall()
                        schema[table] = [
                            {
                                "name": col["Field"],
                                "type": col["Type"],
                                "nullable": col["Null"] == "YES",
                                "key": col["Key"],
                                "default": col["Default"]
                            }
                            for col in columns
                        ]

                    return schema

        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            return {}

    def get_table_sample(
        self,
        table_name: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get sample data from a table

        Args:
            table_name: Table name
            limit: Number of rows

        Returns:
            Sample data
        """
        # Sanitize table name
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise DatabaseError(f"Invalid table name: {table_name}")

        return self.execute_query(f"SELECT * FROM `{table_name}` LIMIT {limit}")

    def test_connection(self) -> bool:
        """
        Test database connectivity

        Returns:
            True if connection successful
        """
        try:
            with self.get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_view_names(self) -> List[str]:
        """
        Get list of available views

        Returns:
            List of view names
        """
        try:
            with self.get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT TABLE_NAME
                        FROM information_schema.VIEWS
                        WHERE TABLE_SCHEMA = %s
                    """, (self.database,))
                    return [row["TABLE_NAME"] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get views: {e}")
            return []
