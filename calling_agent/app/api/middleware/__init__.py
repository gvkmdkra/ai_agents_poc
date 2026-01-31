"""API Middleware"""

from .auth import (
    get_api_key,
    authenticate_request,
    get_current_tenant,
    optional_tenant,
    require_permission
)

from .rate_limit import (
    RateLimiter,
    RateLimitConfig,
    get_rate_limiter,
    check_rate_limit,
    check_call_rate_limit
)

from .webhook_security import (
    WebhookValidator,
    TwilioWebhookValidator,
    UltravoxWebhookValidator,
    get_webhook_validator,
    validate_twilio_webhook,
    validate_ultravox_webhook
)

__all__ = [
    # Auth
    "get_api_key",
    "authenticate_request",
    "get_current_tenant",
    "optional_tenant",
    "require_permission",
    # Rate limiting
    "RateLimiter",
    "RateLimitConfig",
    "get_rate_limiter",
    "check_rate_limit",
    "check_call_rate_limit",
    # Webhook security
    "WebhookValidator",
    "TwilioWebhookValidator",
    "UltravoxWebhookValidator",
    "get_webhook_validator",
    "validate_twilio_webhook",
    "validate_ultravox_webhook"
]
