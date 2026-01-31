"""
Rate Limiting Middleware
Prevents abuse and ensures fair usage across tenants
"""

import time
from typing import Dict, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from fastapi import Request

from app.core.logging import get_logger
from app.core.exceptions import RateLimitError

logger = get_logger(__name__)


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting"""
    tokens: float
    last_update: float
    max_tokens: int
    refill_rate: float  # tokens per second

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens, return True if successful"""
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens
        self.tokens = min(
            self.max_tokens,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: int = 1) -> float:
        """Calculate time until tokens are available"""
        if self.tokens >= tokens:
            return 0
        needed = tokens - self.tokens
        return needed / self.refill_rate


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    # Requests per minute
    requests_per_minute: int = 60
    # Calls per hour
    calls_per_hour: int = 100
    # Concurrent calls
    max_concurrent_calls: int = 10
    # Burst allowance
    burst_multiplier: float = 1.5


class RateLimiter:
    """
    Rate limiter with multiple limit types per tenant
    """

    def __init__(self):
        # Buckets per tenant per limit type
        self.request_buckets: Dict[str, RateLimitBucket] = {}
        self.call_buckets: Dict[str, RateLimitBucket] = {}
        self.concurrent_calls: Dict[str, int] = defaultdict(int)

        # Default config
        self.default_config = RateLimitConfig()
        self.tenant_configs: Dict[str, RateLimitConfig] = {}

    def get_config(self, tenant_id: str) -> RateLimitConfig:
        """Get rate limit config for tenant"""
        return self.tenant_configs.get(tenant_id, self.default_config)

    def set_tenant_config(self, tenant_id: str, config: RateLimitConfig):
        """Set custom rate limit config for tenant"""
        self.tenant_configs[tenant_id] = config

    def _get_request_bucket(self, tenant_id: str) -> RateLimitBucket:
        """Get or create request rate limit bucket"""
        if tenant_id not in self.request_buckets:
            config = self.get_config(tenant_id)
            self.request_buckets[tenant_id] = RateLimitBucket(
                tokens=config.requests_per_minute * config.burst_multiplier,
                last_update=time.time(),
                max_tokens=int(config.requests_per_minute * config.burst_multiplier),
                refill_rate=config.requests_per_minute / 60.0
            )
        return self.request_buckets[tenant_id]

    def _get_call_bucket(self, tenant_id: str) -> RateLimitBucket:
        """Get or create call rate limit bucket"""
        if tenant_id not in self.call_buckets:
            config = self.get_config(tenant_id)
            self.call_buckets[tenant_id] = RateLimitBucket(
                tokens=config.calls_per_hour * config.burst_multiplier,
                last_update=time.time(),
                max_tokens=int(config.calls_per_hour * config.burst_multiplier),
                refill_rate=config.calls_per_hour / 3600.0
            )
        return self.call_buckets[tenant_id]

    def check_request_limit(self, tenant_id: str) -> bool:
        """Check if request is within rate limit"""
        bucket = self._get_request_bucket(tenant_id)
        return bucket.consume(1)

    def check_call_limit(self, tenant_id: str) -> bool:
        """Check if new call is within rate limit"""
        bucket = self._get_call_bucket(tenant_id)
        return bucket.consume(1)

    def check_concurrent_limit(self, tenant_id: str) -> bool:
        """Check if concurrent calls are within limit"""
        config = self.get_config(tenant_id)
        return self.concurrent_calls[tenant_id] < config.max_concurrent_calls

    def increment_concurrent(self, tenant_id: str):
        """Increment concurrent call count"""
        self.concurrent_calls[tenant_id] += 1

    def decrement_concurrent(self, tenant_id: str):
        """Decrement concurrent call count"""
        if self.concurrent_calls[tenant_id] > 0:
            self.concurrent_calls[tenant_id] -= 1

    def get_retry_after(self, tenant_id: str, limit_type: str = "request") -> int:
        """Get seconds until rate limit resets"""
        if limit_type == "request":
            bucket = self._get_request_bucket(tenant_id)
        else:
            bucket = self._get_call_bucket(tenant_id)

        return int(bucket.time_until_available(1)) + 1

    def get_current_usage(self, tenant_id: str) -> Dict:
        """Get current rate limit usage for tenant"""
        config = self.get_config(tenant_id)
        request_bucket = self._get_request_bucket(tenant_id)
        call_bucket = self._get_call_bucket(tenant_id)

        return {
            "requests": {
                "remaining": int(request_bucket.tokens),
                "limit": config.requests_per_minute,
                "reset_seconds": int(request_bucket.time_until_available(config.requests_per_minute))
            },
            "calls": {
                "remaining": int(call_bucket.tokens),
                "limit": config.calls_per_hour,
                "reset_seconds": int(call_bucket.time_until_available(config.calls_per_hour))
            },
            "concurrent": {
                "current": self.concurrent_calls[tenant_id],
                "limit": config.max_concurrent_calls
            }
        }


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter singleton"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def check_rate_limit(request: Request, tenant_id: str):
    """
    Check rate limits for a request

    Raises:
        RateLimitError: If rate limit exceeded
    """
    limiter = get_rate_limiter()

    if not limiter.check_request_limit(tenant_id):
        retry_after = limiter.get_retry_after(tenant_id, "request")
        logger.warning(f"Rate limit exceeded for tenant {tenant_id}")
        raise RateLimitError(retry_after=retry_after)


async def check_call_rate_limit(tenant_id: str):
    """
    Check rate limits for initiating a call

    Raises:
        RateLimitError: If rate limit exceeded
    """
    limiter = get_rate_limiter()

    # Check call rate limit
    if not limiter.check_call_limit(tenant_id):
        retry_after = limiter.get_retry_after(tenant_id, "call")
        logger.warning(f"Call rate limit exceeded for tenant {tenant_id}")
        raise RateLimitError(retry_after=retry_after)

    # Check concurrent limit
    if not limiter.check_concurrent_limit(tenant_id):
        logger.warning(f"Concurrent call limit exceeded for tenant {tenant_id}")
        raise RateLimitError(retry_after=60)
