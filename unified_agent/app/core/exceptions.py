"""
Unified Agent Exception Classes
Provides consistent error handling across all components
"""

from typing import Any, Dict, Optional


class UnifiedAgentException(Exception):
    """Base exception for Unified AI Agent"""

    def __init__(
        self,
        message: str,
        error_code: str = "UNIFIED_AGENT_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


class AuthenticationError(UnifiedAgentException):
    """Authentication/Authorization errors"""

    def __init__(
        self,
        message: str = "Authentication required",
        error_code: str = "AUTH_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=401,
            details=details
        )


class RateLimitError(UnifiedAgentException):
    """Rate limiting errors"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after_seconds: int = 60,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["retry_after_seconds"] = retry_after_seconds
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details
        )


class DatabaseError(UnifiedAgentException):
    """Database operation errors"""

    def __init__(
        self,
        message: str = "Database operation failed",
        error_code: str = "DATABASE_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=500,
            details=details
        )


class ExternalServiceError(UnifiedAgentException):
    """External service (Twilio, Ultravox, OpenAI, etc.) errors"""

    def __init__(
        self,
        service: str,
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["service"] = service
        super().__init__(
            message=message,
            error_code=f"{service.upper()}_ERROR",
            status_code=502,
            details=details
        )


class ValidationError(UnifiedAgentException):
    """Input validation errors"""

    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class TenantNotFoundError(UnifiedAgentException):
    """Tenant not found errors"""

    def __init__(
        self,
        tenant_id: str,
        message: Optional[str] = None
    ):
        super().__init__(
            message=message or f"Tenant not found: {tenant_id}",
            error_code="TENANT_NOT_FOUND",
            status_code=404,
            details={"tenant_id": tenant_id}
        )


class CallError(UnifiedAgentException):
    """Voice call operation errors"""

    def __init__(
        self,
        message: str = "Call operation failed",
        call_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if call_id:
            details["call_id"] = call_id
        super().__init__(
            message=message,
            error_code="CALL_ERROR",
            status_code=500,
            details=details
        )


class ChatError(UnifiedAgentException):
    """Chat operation errors"""

    def __init__(
        self,
        message: str = "Chat operation failed",
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if session_id:
            details["session_id"] = session_id
        super().__init__(
            message=message,
            error_code="CHAT_ERROR",
            status_code=500,
            details=details
        )


class TextToSQLError(UnifiedAgentException):
    """Text-to-SQL operation errors"""

    def __init__(
        self,
        message: str = "Text-to-SQL operation failed",
        query: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if query:
            details["query"] = query
        super().__init__(
            message=message,
            error_code="TEXT_TO_SQL_ERROR",
            status_code=500,
            details=details
        )
