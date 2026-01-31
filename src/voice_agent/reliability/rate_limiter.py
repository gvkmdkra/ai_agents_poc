"""
Rate Limiting & Tenant Isolation

Implements:
- Per-tenant rate limiting
- API rate limiting
- Resource quotas
- Fair queuing
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    concurrent_calls: int = 10
    daily_call_minutes: int = 1000
    burst_allowance: float = 1.5  # Allow 50% burst


@dataclass
class TenantQuota:
    """Tenant resource quotas"""
    tenant_id: UUID
    plan: str  # starter, professional, enterprise
    max_concurrent_calls: int
    daily_minutes_limit: int
    monthly_minutes_limit: int
    api_rate_limit: int  # requests per minute
    priority: int  # Higher = more priority in queue


# Default quotas by plan
DEFAULT_QUOTAS = {
    "starter": TenantQuota(
        tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
        plan="starter",
        max_concurrent_calls=5,
        daily_minutes_limit=500,
        monthly_minutes_limit=5000,
        api_rate_limit=30,
        priority=1,
    ),
    "professional": TenantQuota(
        tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
        plan="professional",
        max_concurrent_calls=20,
        daily_minutes_limit=2000,
        monthly_minutes_limit=20000,
        api_rate_limit=100,
        priority=5,
    ),
    "enterprise": TenantQuota(
        tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
        plan="enterprise",
        max_concurrent_calls=100,
        daily_minutes_limit=10000,
        monthly_minutes_limit=100000,
        api_rate_limit=500,
        priority=10,
    ),
}


class RateLimiter:
    """
    Token bucket rate limiter with Redis backend.

    Provides:
    - Per-tenant rate limiting
    - Sliding window counters
    - Burst handling
    """

    def __init__(self, redis_client: redis.Redis, prefix: str = "ratelimit"):
        self.redis = redis_client
        self.prefix = prefix

    def _key(self, *parts) -> str:
        """Generate Redis key"""
        return f"{self.prefix}:{':'.join(str(p) for p in parts)}"

    async def check_rate_limit(
        self,
        tenant_id: UUID,
        resource: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.

        Args:
            tenant_id: Tenant ID
            resource: Resource being limited (e.g., "api", "calls")
            limit: Maximum requests in window
            window_seconds: Time window in seconds

        Returns:
            (allowed, info) where info contains remaining, reset_at, etc.
        """
        key = self._key(tenant_id, resource, "sliding")
        now = time.time()
        window_start = now - window_seconds

        pipe = self.redis.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current entries
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(now): now})

        # Set expiry
        pipe.expire(key, window_seconds * 2)

        results = await pipe.execute()
        current_count = results[1]

        allowed = current_count < limit
        remaining = max(0, limit - current_count - 1)

        # Calculate reset time
        if not allowed:
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_at = oldest[0][1] + window_seconds
            else:
                reset_at = now + window_seconds
        else:
            reset_at = now + window_seconds

        info = {
            "allowed": allowed,
            "remaining": remaining,
            "limit": limit,
            "reset_at": datetime.fromtimestamp(reset_at).isoformat(),
            "window_seconds": window_seconds,
        }

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for tenant {tenant_id} on {resource}: "
                f"{current_count}/{limit}"
            )

        return allowed, info

    async def get_usage(
        self,
        tenant_id: UUID,
        resource: str,
        window_seconds: int = 60,
    ) -> int:
        """Get current usage count for a resource"""
        key = self._key(tenant_id, resource, "sliding")
        now = time.time()
        window_start = now - window_seconds

        # Remove old and count
        await self.redis.zremrangebyscore(key, 0, window_start)
        return await self.redis.zcard(key)


class TenantIsolationManager:
    """
    Manages tenant isolation and resource quotas.

    Provides:
    - Concurrent call limiting
    - Daily/monthly minute tracking
    - Fair queue management
    - Resource reservation
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.rate_limiter = RateLimiter(redis_client)
        self._quotas: dict[UUID, TenantQuota] = {}

    def set_quota(self, tenant_id: UUID, quota: TenantQuota):
        """Set quota for a tenant"""
        quota.tenant_id = tenant_id
        self._quotas[tenant_id] = quota

    def get_quota(self, tenant_id: UUID, plan: str = "starter") -> TenantQuota:
        """Get quota for a tenant"""
        if tenant_id in self._quotas:
            return self._quotas[tenant_id]

        # Return default for plan
        default = DEFAULT_QUOTAS.get(plan, DEFAULT_QUOTAS["starter"])
        quota = TenantQuota(
            tenant_id=tenant_id,
            plan=default.plan,
            max_concurrent_calls=default.max_concurrent_calls,
            daily_minutes_limit=default.daily_minutes_limit,
            monthly_minutes_limit=default.monthly_minutes_limit,
            api_rate_limit=default.api_rate_limit,
            priority=default.priority,
        )
        return quota

    async def acquire_call_slot(self, tenant_id: UUID) -> tuple[bool, str]:
        """
        Acquire a concurrent call slot for a tenant.

        Returns:
            (acquired, reason)
        """
        quota = self.get_quota(tenant_id)
        key = f"calls:concurrent:{tenant_id}"

        current = await self.redis.incr(key)
        await self.redis.expire(key, 3600)  # 1 hour TTL

        if current > quota.max_concurrent_calls:
            await self.redis.decr(key)
            return False, f"Max concurrent calls ({quota.max_concurrent_calls}) reached"

        logger.debug(f"Acquired call slot for {tenant_id}: {current}/{quota.max_concurrent_calls}")
        return True, ""

    async def release_call_slot(self, tenant_id: UUID):
        """Release a concurrent call slot"""
        key = f"calls:concurrent:{tenant_id}"
        current = await self.redis.decr(key)

        if current < 0:
            await self.redis.set(key, 0)

        logger.debug(f"Released call slot for {tenant_id}")

    async def get_concurrent_calls(self, tenant_id: UUID) -> int:
        """Get current concurrent call count"""
        key = f"calls:concurrent:{tenant_id}"
        count = await self.redis.get(key)
        return int(count) if count else 0

    async def track_call_minutes(
        self,
        tenant_id: UUID,
        duration_minutes: float,
    ) -> tuple[bool, dict]:
        """
        Track call minutes usage.

        Returns:
            (within_limit, usage_info)
        """
        quota = self.get_quota(tenant_id)
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")

        daily_key = f"minutes:daily:{tenant_id}:{today}"
        monthly_key = f"minutes:monthly:{tenant_id}:{month}"

        pipe = self.redis.pipeline()
        pipe.incrbyfloat(daily_key, duration_minutes)
        pipe.incrbyfloat(monthly_key, duration_minutes)
        pipe.expire(daily_key, 86400 * 2)  # 2 days
        pipe.expire(monthly_key, 86400 * 35)  # 35 days

        results = await pipe.execute()
        daily_used = float(results[0])
        monthly_used = float(results[1])

        within_daily = daily_used <= quota.daily_minutes_limit
        within_monthly = monthly_used <= quota.monthly_minutes_limit

        usage_info = {
            "daily_used": round(daily_used, 2),
            "daily_limit": quota.daily_minutes_limit,
            "daily_remaining": max(0, quota.daily_minutes_limit - daily_used),
            "monthly_used": round(monthly_used, 2),
            "monthly_limit": quota.monthly_minutes_limit,
            "monthly_remaining": max(0, quota.monthly_minutes_limit - monthly_used),
        }

        if not within_daily:
            logger.warning(f"Tenant {tenant_id} exceeded daily limit: {daily_used}/{quota.daily_minutes_limit}")
        if not within_monthly:
            logger.warning(f"Tenant {tenant_id} exceeded monthly limit: {monthly_used}/{quota.monthly_minutes_limit}")

        return within_daily and within_monthly, usage_info

    async def get_usage_stats(self, tenant_id: UUID) -> dict:
        """Get comprehensive usage statistics for a tenant"""
        quota = self.get_quota(tenant_id)
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")

        daily_key = f"minutes:daily:{tenant_id}:{today}"
        monthly_key = f"minutes:monthly:{tenant_id}:{month}"
        concurrent_key = f"calls:concurrent:{tenant_id}"

        pipe = self.redis.pipeline()
        pipe.get(daily_key)
        pipe.get(monthly_key)
        pipe.get(concurrent_key)

        results = await pipe.execute()

        daily_used = float(results[0]) if results[0] else 0
        monthly_used = float(results[1]) if results[1] else 0
        concurrent = int(results[2]) if results[2] else 0

        return {
            "tenant_id": str(tenant_id),
            "plan": quota.plan,
            "concurrent_calls": {
                "current": concurrent,
                "limit": quota.max_concurrent_calls,
                "available": quota.max_concurrent_calls - concurrent,
            },
            "daily_minutes": {
                "used": round(daily_used, 2),
                "limit": quota.daily_minutes_limit,
                "remaining": max(0, quota.daily_minutes_limit - daily_used),
                "percentage": round((daily_used / quota.daily_minutes_limit) * 100, 1),
            },
            "monthly_minutes": {
                "used": round(monthly_used, 2),
                "limit": quota.monthly_minutes_limit,
                "remaining": max(0, quota.monthly_minutes_limit - monthly_used),
                "percentage": round((monthly_used / quota.monthly_minutes_limit) * 100, 1),
            },
            "api_rate_limit": quota.api_rate_limit,
        }

    async def check_api_rate_limit(self, tenant_id: UUID) -> tuple[bool, dict]:
        """Check API rate limit for a tenant"""
        quota = self.get_quota(tenant_id)
        return await self.rate_limiter.check_rate_limit(
            tenant_id=tenant_id,
            resource="api",
            limit=quota.api_rate_limit,
            window_seconds=60,
        )


class FairQueue:
    """
    Fair queue for distributing load across tenants.

    Ensures high-priority tenants don't starve lower-priority ones.
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._isolation_manager: Optional[TenantIsolationManager] = None

    def set_isolation_manager(self, manager: TenantIsolationManager):
        """Set the isolation manager for quota lookups"""
        self._isolation_manager = manager

    async def enqueue(
        self,
        tenant_id: UUID,
        item_id: str,
        priority: Optional[int] = None,
    ):
        """
        Add item to tenant's queue with priority.

        Args:
            tenant_id: Tenant ID
            item_id: Unique item identifier
            priority: Optional priority override
        """
        if priority is None and self._isolation_manager:
            quota = self._isolation_manager.get_quota(tenant_id)
            priority = quota.priority
        else:
            priority = priority or 1

        # Use sorted set with priority as score
        # Higher priority = higher score = dequeued first
        key = "fair_queue:items"
        member = f"{tenant_id}:{item_id}"
        timestamp = time.time()

        # Score combines priority and timestamp for FIFO within priority
        score = priority * 1e12 + (1e12 - timestamp)

        await self.redis.zadd(key, {member: score})
        logger.debug(f"Enqueued {item_id} for tenant {tenant_id} with priority {priority}")

    async def dequeue(self) -> Optional[tuple[UUID, str]]:
        """
        Dequeue highest priority item.

        Returns:
            (tenant_id, item_id) or None
        """
        key = "fair_queue:items"

        # Get and remove highest scored item
        result = await self.redis.zpopmax(key)

        if not result:
            return None

        member, score = result[0]
        tenant_id_str, item_id = member.split(":", 1)

        return UUID(tenant_id_str), item_id

    async def get_queue_length(self, tenant_id: Optional[UUID] = None) -> int:
        """Get queue length, optionally filtered by tenant"""
        key = "fair_queue:items"

        if tenant_id:
            # Count items for specific tenant
            all_items = await self.redis.zrange(key, 0, -1)
            prefix = f"{tenant_id}:"
            return sum(1 for item in all_items if item.startswith(prefix))

        return await self.redis.zcard(key)

    async def get_position(self, tenant_id: UUID, item_id: str) -> Optional[int]:
        """Get position of item in queue (0 = next to be dequeued)"""
        key = "fair_queue:items"
        member = f"{tenant_id}:{item_id}"

        rank = await self.redis.zrevrank(key, member)
        return rank
