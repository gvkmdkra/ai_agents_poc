"""Core module for configuration, settings, and shared utilities"""

from .config import settings, get_settings, Settings
from .logging import setup_logging, get_logger
from .exceptions import (
    CallingAgentException,
    AuthenticationError,
    AuthorizationError,
    InvalidAPIKeyError,
    TenantError,
    TenantNotFoundError,
    TenantInactiveError,
    CallError,
    CallNotFoundError,
    CallInitiationError,
    CallInProgressError,
    CallEndedError,
    InvalidPhoneNumberError,
    CallLimitExceededError,
    OutsideAllowedHoursError,
    ServiceError,
    TwilioServiceError,
    UltravoxServiceError,
    OpenAIServiceError,
    WebhookError,
    WebhookValidationError,
    RateLimitError,
    ValidationError
)

__all__ = [
    # Config
    "settings",
    "get_settings",
    "Settings",
    # Logging
    "setup_logging",
    "get_logger",
    # Exceptions
    "CallingAgentException",
    "AuthenticationError",
    "AuthorizationError",
    "InvalidAPIKeyError",
    "TenantError",
    "TenantNotFoundError",
    "TenantInactiveError",
    "CallError",
    "CallNotFoundError",
    "CallInitiationError",
    "CallInProgressError",
    "CallEndedError",
    "InvalidPhoneNumberError",
    "CallLimitExceededError",
    "OutsideAllowedHoursError",
    "ServiceError",
    "TwilioServiceError",
    "UltravoxServiceError",
    "OpenAIServiceError",
    "WebhookError",
    "WebhookValidationError",
    "RateLimitError",
    "ValidationError"
]
