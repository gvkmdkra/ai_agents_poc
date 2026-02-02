"""
Redis Service for High-Performance Caching and Rate Limiting
"""
import os
import json
import asyncio
from typing import Any, Optional
from datetime import timedelta

import redis.asyncio as redis

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Global Redis pool
_redis_pool: Optional[redis.ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get Redis client with connection pooling"""
    global _redis_pool, _redis_client

    if _redis_client is None:
        _redis_pool = redis.ConnectionPool.from_url(
            REDIS_URL,
            max_connections=100,
            decode_responses=True
        )
        _redis_client = redis.Redis(connection_pool=_redis_pool)

    return _redis_client


async def close_redis():
    """Close Redis connection"""
    global _redis_pool, _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None

    if _redis_pool:
        await _redis_pool.disconnect()
        _redis_pool = None


class RateLimiter:
    """
    Token bucket rate limiter using Redis
    Allows bursting with sustained rate limiting
    """

    def __init__(
        self,
        key_prefix: str = "ratelimit",
        max_requests: int = 100,
        window_seconds: int = 60
    ):
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit

        Returns:
            (allowed: bool, info: dict with remaining, reset_at)
        """
        client = await get_redis()
        key = f"{self.key_prefix}:{identifier}"

        # Use Redis pipeline for atomic operations
        pipe = client.pipeline()

        # Increment counter
        pipe.incr(key)
        # Set expiry if new key
        pipe.expire(key, self.window_seconds)
        # Get TTL
        pipe.ttl(key)

        results = await pipe.execute()
        current_count = results[0]
        ttl = results[2]

        remaining = max(0, self.max_requests - current_count)
        allowed = current_count <= self.max_requests

        return allowed, {
            "remaining": remaining,
            "limit": self.max_requests,
            "reset_in_seconds": ttl if ttl > 0 else self.window_seconds
        }


class CallCache:
    """
    Redis-based cache for call data
    Reduces database load for frequently accessed data
    """

    def __init__(self, prefix: str = "call"):
        self.prefix = prefix
        self.default_ttl = 3600  # 1 hour

    async def get(self, call_id: str) -> Optional[dict]:
        """Get call data from cache"""
        client = await get_redis()
        key = f"{self.prefix}:{call_id}"

        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(
        self,
        call_id: str,
        data: dict,
        ttl: Optional[int] = None
    ):
        """Store call data in cache"""
        client = await get_redis()
        key = f"{self.prefix}:{call_id}"

        await client.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(data)
        )

    async def delete(self, call_id: str):
        """Remove call data from cache"""
        client = await get_redis()
        key = f"{self.prefix}:{call_id}"
        await client.delete(key)

    async def get_active_calls(self) -> list:
        """Get all active call IDs"""
        client = await get_redis()
        keys = await client.keys(f"{self.prefix}:*")
        return [k.split(":")[-1] for k in keys]


class CallQueue:
    """
    Redis-based call queue for managing concurrent calls
    """

    def __init__(self, queue_name: str = "call_queue"):
        self.queue_name = queue_name
        self.processing_set = f"{queue_name}:processing"

    async def enqueue(self, call_data: dict) -> str:
        """Add call to queue"""
        client = await get_redis()

        # Generate unique ID
        call_id = call_data.get("call_id") or f"call_{await client.incr('call_counter')}"
        call_data["call_id"] = call_id

        # Add to queue
        await client.lpush(self.queue_name, json.dumps(call_data))

        return call_id

    async def dequeue(self) -> Optional[dict]:
        """Get next call from queue"""
        client = await get_redis()

        # Blocking pop with timeout
        result = await client.brpoplpush(
            self.queue_name,
            self.processing_set,
            timeout=1
        )

        if result:
            return json.loads(result)
        return None

    async def complete(self, call_id: str):
        """Mark call as completed"""
        client = await get_redis()

        # Find and remove from processing set
        processing = await client.lrange(self.processing_set, 0, -1)
        for item in processing:
            data = json.loads(item)
            if data.get("call_id") == call_id:
                await client.lrem(self.processing_set, 1, item)
                break

    async def queue_length(self) -> int:
        """Get number of pending calls"""
        client = await get_redis()
        return await client.llen(self.queue_name)

    async def processing_count(self) -> int:
        """Get number of calls being processed"""
        client = await get_redis()
        return await client.llen(self.processing_set)


# Singleton instances
rate_limiter = RateLimiter(max_requests=1000, window_seconds=60)  # 1000 req/min
call_cache = CallCache()
call_queue = CallQueue()
