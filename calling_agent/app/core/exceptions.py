"""
Custom Exceptions for the Calling Agent
Provides structured error handling across the application
"""

from typing import Optional, Dict, Any


class CallingAgentException(Exception):
    """Base exception for all calling agent errors"""

    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


# Authentication & Authorization Exceptions
class AuthenticationError(CallingAgentException):
    """Raised when authentication fails"""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="AUTH_FAILED",
            details=details,
            status_code=401
        )


class AuthorizationError(CallingAgentException):
    """Raised when authorization fails"""

    def __init__(self, message: str = "Access denied", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="ACCESS_DENIED",
            details=details,
            status_code=403
        )


class InvalidAPIKeyError(AuthenticationError):
    """Raised when API key is invalid"""

    def __init__(self, message: str = "Invalid or expired API key"):
        super().__init__(message=message, details={"hint": "Check your API key"})


# Tenant Exceptions
class TenantError(CallingAgentException):
    """Base exception for tenant-related errors"""
    pass


class TenantNotFoundError(TenantError):
    """Raised when tenant is not found"""

    def __init__(self, tenant_id: str):
        super().__init__(
            message=f"Tenant not found: {tenant_id}",
            error_code="TENANT_NOT_FOUND",
            details={"tenant_id": tenant_id},
            status_code=404
        )


class TenantInactiveError(TenantError):
    """Raised when tenant is inactive"""

    def __init__(self, tenant_id: str):
        super().__init__(
            message=f"Tenant is inactive: {tenant_id}",
            error_code="TENANT_INACTIVE",
            details={"tenant_id": tenant_id},
            status_code=403
        )


# Call Exceptions
class CallError(CallingAgentException):
    """Base exception for call-related errors"""
    pass


class CallNotFoundError(CallError):
    """Raised when call is not found"""

    def __init__(self, call_id: str):
        super().__init__(
            message=f"Call not found: {call_id}",
            error_code="CALL_NOT_FOUND",
            details={"call_id": call_id},
            status_code=404
        )


class CallInitiationError(CallError):
    """Raised when call initiation fails"""

    def __init__(self, message: str, phone_number: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="CALL_INITIATION_FAILED",
            details={"phone_number": phone_number} if phone_number else {},
            status_code=500
        )


class CallInProgressError(CallError):
    """Raised when trying to modify an active call incorrectly"""

    def __init__(self, call_id: str, message: str = "Call is currently in progress"):
        super().__init__(
            message=message,
            error_code="CALL_IN_PROGRESS",
            details={"call_id": call_id},
            status_code=409
        )


class CallEndedError(CallError):
    """Raised when trying to interact with an ended call"""

    def __init__(self, call_id: str):
        super().__init__(
            message=f"Call has already ended: {call_id}",
            error_code="CALL_ENDED",
            details={"call_id": call_id},
            status_code=410
        )


class InvalidPhoneNumberError(CallError):
    """Raised when phone number is invalid"""

    def __init__(self, phone_number: str):
        super().__init__(
            message=f"Invalid phone number format: {phone_number}",
            error_code="INVALID_PHONE_NUMBER",
            details={
                "phone_number": phone_number,
                "hint": "Use E.164 format (e.g., +14155551234)"
            },
            status_code=400
        )


class CallLimitExceededError(CallError):
    """Raised when call limits are exceeded"""

    def __init__(self, limit_type: str, current: int, maximum: int):
        super().__init__(
            message=f"Call limit exceeded: {limit_type}",
            error_code="CALL_LIMIT_EXCEEDED",
            details={
                "limit_type": limit_type,
                "current": current,
                "maximum": maximum
            },
            status_code=429
        )


class OutsideAllowedHoursError(CallError):
    """Raised when trying to call outside allowed hours"""

    def __init__(self, current_hour: int, allowed_start: int, allowed_end: int):
        super().__init__(
            message="Calls not allowed at this time",
            error_code="OUTSIDE_ALLOWED_HOURS",
            details={
                "current_hour": current_hour,
                "allowed_start": allowed_start,
                "allowed_end": allowed_end
            },
            status_code=400
        )


# Service Exceptions
class ServiceError(CallingAgentException):
    """Base exception for external service errors"""
    pass


class TwilioServiceError(ServiceError):
    """Raised when Twilio service fails"""

    def __init__(self, message: str, twilio_code: Optional[int] = None):
        super().__init__(
            message=f"Twilio error: {message}",
            error_code="TWILIO_ERROR",
            details={"twilio_code": twilio_code} if twilio_code else {},
            status_code=502
        )


class UltravoxServiceError(ServiceError):
    """Raised when Ultravox service fails"""

    def __init__(self, message: str, ultravox_status: Optional[int] = None):
        super().__init__(
            message=f"Ultravox error: {message}",
            error_code="ULTRAVOX_ERROR",
            details={"status_code": ultravox_status} if ultravox_status else {},
            status_code=502
        )


class OpenAIServiceError(ServiceError):
    """Raised when OpenAI service fails"""

    def __init__(self, message: str):
        super().__init__(
            message=f"OpenAI error: {message}",
            error_code="OPENAI_ERROR",
            status_code=502
        )


# Webhook Exceptions
class WebhookError(CallingAgentException):
    """Base exception for webhook errors"""
    pass


class WebhookValidationError(WebhookError):
    """Raised when webhook signature validation fails"""

    def __init__(self, message: str = "Invalid webhook signature"):
        super().__init__(
            message=message,
            error_code="WEBHOOK_VALIDATION_FAILED",
            status_code=401
        )


# Rate Limiting
class RateLimitError(CallingAgentException):
    """Raised when rate limit is exceeded"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after_seconds": retry_after},
            status_code=429
        )


# Validation Exceptions
class ValidationError(CallingAgentException):
    """Raised when input validation fails"""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field} if field else {},
            status_code=400
        )
