"""
Database Base Module
Provides database session management and initialization
"""

from typing import Optional, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os

from app.core.config import settings
from app.core.logging import get_logger
from .models import Base

logger = get_logger(__name__)

# Global engine and session factory
_engine = None
_SessionLocal = None


def get_database_url() -> str:
    """Get the database URL based on configuration"""
    if settings.database_type == "turso" and settings.turso_database_url:
        # Turso/LibSQL connection
        url = settings.turso_database_url
        if settings.turso_auth_token:
            # Add auth token for remote Turso
            if "?" in url:
                url += f"&authToken={settings.turso_auth_token}"
            else:
                url += f"?authToken={settings.turso_auth_token}"
        return url

    elif settings.database_type == "postgres" and settings.postgres_url:
        return settings.postgres_url

    else:
        # Default to SQLite
        db_path = settings.sqlite_database_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return f"sqlite:///{db_path}"


def init_database() -> None:
    """Initialize the database engine and create tables"""
    global _engine, _SessionLocal

    db_url = get_database_url()
    logger.info(f"Initializing database: {settings.database_type}")

    # Create engine with appropriate settings
    if "sqlite" in db_url:
        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.debug
        )
        # Enable foreign keys for SQLite
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        _engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=settings.debug
        )

    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # Create all tables
    Base.metadata.create_all(bind=_engine)
    logger.info("Database tables created/verified")


def get_engine():
    """Get the database engine, initializing if needed"""
    global _engine
    if _engine is None:
        init_database()
    return _engine


def get_session_factory():
    """Get the session factory, initializing if needed"""
    global _SessionLocal
    if _SessionLocal is None:
        init_database()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session
    For use with FastAPI's Depends()
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions
    For use outside of FastAPI routes
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def close_database() -> None:
    """Close database connections"""
    global _engine
    if _engine:
        _engine.dispose()
        logger.info("Database connections closed")


class DatabaseManager:
    """
    Database manager for more complex database operations
    """

    def __init__(self):
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the database"""
        try:
            init_database()
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def create_session(self) -> Session:
        """Create a new database session"""
        return get_session_factory()()

    async def close(self) -> None:
        """Close database connections"""
        await close_database()
        self._initialized = False


# Global database manager instance
db_manager = DatabaseManager()
