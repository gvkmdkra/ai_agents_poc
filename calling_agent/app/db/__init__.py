"""
Database Abstraction Layer

This module provides a clean abstraction for database operations,
making it easy to switch between different database backends
(Turso, PostgreSQL, SQLite, etc.) with minimal code changes.

Usage:
    from app.db import get_repository

    repo = get_repository()
    await repo.save_call(call_record)
    call = await repo.get_call(call_id)
"""

from app.db.repository import (
    DatabaseRepository,
    get_repository,
    CallRepository,
)
from app.db.models import (
    CallRecordDB,
    CallTranscriptDB,
    CallSummaryDB,
)

__all__ = [
    "DatabaseRepository",
    "get_repository",
    "CallRepository",
    "CallRecordDB",
    "CallTranscriptDB",
    "CallSummaryDB",
]
