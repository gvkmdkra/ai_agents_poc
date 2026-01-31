"""
Webhook Security Middleware
Validates webhook signatures from Twilio and Ultravox
"""

import hmac
import hashlib
import base64
from typing import Optional
from urllib.parse import urlencode
from fastapi import Request

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import WebhookValidationError

logger = get_logger(__name__)


class TwilioWebhookValidator:
    """
    Validates Twilio webhook signatures
    https://www.twilio.com/docs/usage/security#validating-requests
    """

    def __init__(self, auth_token: Optional[str] = None):
        self.auth_token = auth_token or settings.twilio_auth_token

    def compute_signature(self, url: str, params: dict) -> str:
        """Compute expected Twilio signature"""
        # Sort parameters alphabetically
        sorted_params = sorted(params.items())
        param_string = urlencode(sorted_params)

        # Concatenate URL and parameters
        data = url + param_string

        # Create HMAC-SHA1 signature
        signature = hmac.new(
            self.auth_token.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha1
        )

        return base64.b64encode(signature.digest()).decode('utf-8')

    async def validate(self, request: Request) -> bool:
        """
        Validate Twilio webhook request

        Args:
            request: FastAPI request object

        Returns:
            True if valid, raises WebhookValidationError if invalid
        """
        # Get signature from header
        signature = request.headers.get("X-Twilio-Signature")
        if not signature:
            logger.warning("Missing Twilio signature header")
            raise WebhookValidationError("Missing X-Twilio-Signature header")

        # Get request URL (use forwarded URL if behind proxy)
        url = str(request.url)
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        forwarded_host = request.headers.get("X-Forwarded-Host")

        if forwarded_proto and forwarded_host:
            url = f"{forwarded_proto}://{forwarded_host}{request.url.path}"

        # Get form data
        try:
            form_data = await request.form()
            params = dict(form_data)
        except Exception:
            params = {}

        # Compute expected signature
        expected_signature = self.compute_signature(url, params)

        # Compare signatures
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Invalid Twilio signature")
            raise WebhookValidationError("Invalid Twilio signature")

        return True


class UltravoxWebhookValidator:
    """
    Validates Ultravox webhook signatures
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ultravox_api_key

    def compute_signature(self, payload: bytes, timestamp: str) -> str:
        """Compute expected Ultravox signature"""
        # Combine timestamp and payload
        signed_data = f"{timestamp}.{payload.decode('utf-8')}"

        # Create HMAC-SHA256 signature
        signature = hmac.new(
            self.api_key.encode('utf-8'),
            signed_data.encode('utf-8'),
            hashlib.sha256
        )

        return signature.hexdigest()

    async def validate(self, request: Request) -> bool:
        """
        Validate Ultravox webhook request

        Args:
            request: FastAPI request object

        Returns:
            True if valid, raises WebhookValidationError if invalid
        """
        # Get signature from header
        signature = request.headers.get("X-Ultravox-Signature")
        timestamp = request.headers.get("X-Ultravox-Timestamp")

        if not signature:
            # Ultravox might not always sign webhooks
            logger.debug("No Ultravox signature header - skipping validation")
            return True

        if not timestamp:
            raise WebhookValidationError("Missing X-Ultravox-Timestamp header")

        # Get raw body
        body = await request.body()

        # Compute expected signature
        expected_signature = self.compute_signature(body, timestamp)

        # Compare signatures
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Invalid Ultravox signature")
            raise WebhookValidationError("Invalid Ultravox signature")

        return True


class WebhookValidator:
    """
    Combined webhook validator for all providers
    """

    def __init__(self):
        self.twilio = TwilioWebhookValidator()
        self.ultravox = UltravoxWebhookValidator()

    async def validate_twilio(self, request: Request) -> bool:
        """Validate Twilio webhook"""
        # Skip validation in development mode
        if settings.debug and settings.environment == "development":
            logger.debug("Skipping Twilio webhook validation in development mode")
            return True
        return await self.twilio.validate(request)

    async def validate_ultravox(self, request: Request) -> bool:
        """Validate Ultravox webhook"""
        # Skip validation in development mode
        if settings.debug and settings.environment == "development":
            logger.debug("Skipping Ultravox webhook validation in development mode")
            return True
        return await self.ultravox.validate(request)


# Singleton instance
_webhook_validator: Optional[WebhookValidator] = None


def get_webhook_validator() -> WebhookValidator:
    """Get webhook validator singleton"""
    global _webhook_validator
    if _webhook_validator is None:
        _webhook_validator = WebhookValidator()
    return _webhook_validator


async def validate_twilio_webhook(request: Request):
    """
    Dependency for validating Twilio webhooks

    Usage:
        @router.post("/webhook")
        async def webhook(request: Request, _: bool = Depends(validate_twilio_webhook)):
            ...
    """
    validator = get_webhook_validator()
    return await validator.validate_twilio(request)


async def validate_ultravox_webhook(request: Request):
    """
    Dependency for validating Ultravox webhooks

    Usage:
        @router.post("/webhook")
        async def webhook(request: Request, _: bool = Depends(validate_ultravox_webhook)):
            ...
    """
    validator = get_webhook_validator()
    return await validator.validate_ultravox(request)
