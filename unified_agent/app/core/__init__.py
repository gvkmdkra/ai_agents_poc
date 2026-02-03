"""
Core module for Unified AI Agent
"""

from .config import settings, get_settings
from .logging import setup_logging, get_logger
from .exceptions import (
    UnifiedAgentException,
    AuthenticationError,
    RateLimitError,
    DatabaseError,
    ExternalServiceError,
    ValidationError
)

__all__ = [
    "settings",
    "get_settings",
    "setup_logging",
    "get_logger",
    "UnifiedAgentException",
    "AuthenticationError",
    "RateLimitError",
    "DatabaseError",
    "ExternalServiceError",
    "ValidationError"
]
