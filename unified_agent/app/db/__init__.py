"""
Database Module
"""

from .base import (
    init_database,
    get_db,
    get_db_session,
    close_database,
    db_manager,
    DatabaseManager
)
from .models import (
    Base,
    Tenant,
    APIKey,
    Call,
    CallStatus,
    CallDirection,
    Conversation,
    Message,
    MessageRole,
    QueryMethod,
    Lead,
    AnalyticsEvent,
    generate_uuid,
    generate_short_id
)

__all__ = [
    # Base
    "init_database",
    "get_db",
    "get_db_session",
    "close_database",
    "db_manager",
    "DatabaseManager",
    # Models
    "Base",
    "Tenant",
    "APIKey",
    "Call",
    "CallStatus",
    "CallDirection",
    "Conversation",
    "Message",
    "MessageRole",
    "QueryMethod",
    "Lead",
    "AnalyticsEvent",
    "generate_uuid",
    "generate_short_id"
]
