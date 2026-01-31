"""
Cost Optimization Manager

Implements:
- Response caching
- Smart model routing (use smaller models when possible)
- Token usage optimization
- Silence detection to reduce ASR/TTS costs
- Per-tenant cost tracking and alerts
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import redis.asyncio as redis

logger = logging.getLogger(__name__)


# ============================================================================
# COST CONFIGURATION
# ============================================================================


@dataclass
class ModelCosts:
    """Cost per unit for different models/services"""
    # OpenAI costs (per 1M tokens)
    gpt4o_input: float = 2.50
    gpt4o_output: float = 10.00
    gpt4o_mini_input: float = 0.15
    gpt4o_mini_output: float = 0.60

    # ASR costs (per minute)
    deepgram_nova: float = 0.0043
    whisper: float = 0.006

    # TTS costs (per 1K characters)
    elevenlabs: float = 0.30
    playht: float = 0.20
    azure_tts: float = 0.016

    # Twilio costs (per minute)
    twilio_voice_inbound: float = 0.0085
    twilio_voice_outbound: float = 0.014
    twilio_whatsapp: float = 0.005  # per message


DEFAULT_COSTS = ModelCosts()


# ============================================================================
# RESPONSE CACHING
# ============================================================================


class ResponseCache:
    """
    Cache for AI responses to reduce LLM costs.

    Caches:
    - FAQ responses
    - Common greetings
    - Standard qualification questions
    - Product information responses
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        default_ttl: int = 3600,  # 1 hour
        prefix: str = "response_cache",
    ):
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.prefix = prefix
        self._hit_count = 0
        self._miss_count = 0

    def _cache_key(self, tenant_id: UUID, query_hash: str) -> str:
        """Generate cache key"""
        return f"{self.prefix}:{tenant_id}:{query_hash}"

    def _hash_query(self, query: str, context: Optional[dict] = None) -> str:
        """
        Create a hash of the query for cache lookup.

        Normalizes the query to improve cache hit rate.
        """
        # Normalize: lowercase, remove extra spaces
        normalized = " ".join(query.lower().split())

        # Include relevant context
        if context:
            relevant_keys = ["intent", "stage", "product_category"]
            context_str = json.dumps(
                {k: v for k, v in context.items() if k in relevant_keys},
                sort_keys=True,
            )
            normalized += f"|{context_str}"

        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    async def get(
        self,
        tenant_id: UUID,
        query: str,
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Get cached response.

        Returns:
            Cached response or None if not found
        """
        query_hash = self._hash_query(query, context)
        key = self._cache_key(tenant_id, query_hash)

        cached = await self.redis.get(key)

        if cached:
            self._hit_count += 1
            logger.debug(f"Cache hit for query hash {query_hash}")
            return cached.decode()

        self._miss_count += 1
        return None

    async def set(
        self,
        tenant_id: UUID,
        query: str,
        response: str,
        context: Optional[dict] = None,
        ttl: Optional[int] = None,
        confidence: float = 1.0,
    ):
        """
        Cache a response.

        Args:
            tenant_id: Tenant ID
            query: Original query
            response: Response to cache
            context: Query context
            ttl: Time to live in seconds
            confidence: Response confidence (higher = cache longer)
        """
        # Only cache high-confidence responses
        if confidence < 0.8:
            return

        query_hash = self._hash_query(query, context)
        key = self._cache_key(tenant_id, query_hash)

        # Adjust TTL based on confidence
        ttl = ttl or self.default_ttl
        ttl = int(ttl * confidence)

        await self.redis.setex(key, ttl, response)
        logger.debug(f"Cached response for query hash {query_hash}, TTL={ttl}s")

    async def invalidate(self, tenant_id: UUID, pattern: Optional[str] = None):
        """Invalidate cached responses for a tenant"""
        if pattern:
            keys = await self.redis.keys(f"{self.prefix}:{tenant_id}:*{pattern}*")
        else:
            keys = await self.redis.keys(f"{self.prefix}:{tenant_id}:*")

        if keys:
            await self.redis.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cached responses for tenant {tenant_id}")

    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0

        return {
            "hits": self._hit_count,
            "misses": self._miss_count,
            "hit_rate": round(hit_rate, 3),
            "estimated_savings_usd": round(self._hit_count * 0.002, 2),  # ~$0.002 per cached response
        }


# ============================================================================
# SMART MODEL ROUTING
# ============================================================================


class ModelRouter:
    """
    Routes requests to appropriate models based on complexity.

    Uses smaller, cheaper models for simple tasks:
    - Simple greetings → GPT-4o-mini
    - FAQ matching → Embeddings + lookup
    - Complex reasoning → GPT-4o
    """

    def __init__(
        self,
        response_cache: ResponseCache,
        costs: ModelCosts = DEFAULT_COSTS,
    ):
        self.cache = response_cache
        self.costs = costs

        # Simple patterns that can use smaller models
        self.simple_patterns = [
            # Greetings
            r"^(hi|hello|hey|good morning|good afternoon|good evening)",
            # Yes/No responses
            r"^(yes|no|yeah|nope|sure|okay|ok)$",
            # Confirmations
            r"^(that's right|correct|exactly|that works)",
            # Simple questions
            r"^(what|how) (is|are|do|does) (your|the) (name|hours|address|location)",
        ]

        # Complex patterns that need full model
        self.complex_patterns = [
            # Multi-part questions
            r"and also|additionally|furthermore",
            # Comparisons
            r"compared to|difference between|better than",
            # Negotiations
            r"discount|negotiate|best price|deal",
            # Technical questions
            r"specifications|technical|how does .+ work",
        ]

    def classify_complexity(self, query: str, context: dict) -> str:
        """
        Classify query complexity.

        Returns:
            "simple", "medium", or "complex"
        """
        import re

        query_lower = query.lower()

        # Check for complex patterns first
        for pattern in self.complex_patterns:
            if re.search(pattern, query_lower):
                return "complex"

        # Check for simple patterns
        for pattern in self.simple_patterns:
            if re.search(pattern, query_lower):
                return "simple"

        # Check context
        turn_count = context.get("turn_count", 0)
        sentiment = context.get("sentiment", 0)

        # Early conversation turns are usually simpler
        if turn_count <= 2:
            return "simple"

        # Negative sentiment might need more careful handling
        if sentiment < -0.3:
            return "complex"

        return "medium"

    def select_model(self, query: str, context: dict) -> dict:
        """
        Select the appropriate model for a query.

        Returns:
            Model configuration dict
        """
        complexity = self.classify_complexity(query, context)

        if complexity == "simple":
            return {
                "model": "gpt-4o-mini",
                "temperature": 0.5,
                "max_tokens": 150,
                "estimated_cost_per_1k": 0.0002,
            }

        elif complexity == "medium":
            return {
                "model": "gpt-4o-mini",
                "temperature": 0.7,
                "max_tokens": 300,
                "estimated_cost_per_1k": 0.0003,
            }

        else:  # complex
            return {
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 500,
                "estimated_cost_per_1k": 0.005,
            }

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a request"""
        if model == "gpt-4o":
            input_cost = (input_tokens / 1_000_000) * self.costs.gpt4o_input
            output_cost = (output_tokens / 1_000_000) * self.costs.gpt4o_output
        else:  # gpt-4o-mini
            input_cost = (input_tokens / 1_000_000) * self.costs.gpt4o_mini_input
            output_cost = (output_tokens / 1_000_000) * self.costs.gpt4o_mini_output

        return input_cost + output_cost


# ============================================================================
# SILENCE DETECTION
# ============================================================================


class SilenceDetector:
    """
    Detects silence in audio streams to optimize costs.

    Reduces:
    - ASR processing during silence
    - Unnecessary LLM calls
    - TTS generation
    """

    def __init__(
        self,
        silence_threshold_db: float = -40,
        min_silence_duration_ms: int = 500,
        max_silence_duration_ms: int = 5000,
    ):
        self.silence_threshold_db = silence_threshold_db
        self.min_silence_ms = min_silence_duration_ms
        self.max_silence_ms = max_silence_duration_ms

        self._silence_start: Optional[datetime] = None
        self._total_silence_ms = 0
        self._total_speech_ms = 0

    def process_audio_frame(
        self,
        audio_level_db: float,
        frame_duration_ms: int = 20,
    ) -> dict:
        """
        Process an audio frame and detect silence.

        Returns:
            Status dict with silence detection results
        """
        is_silent = audio_level_db < self.silence_threshold_db
        now = datetime.now()

        result = {
            "is_silent": is_silent,
            "silence_duration_ms": 0,
            "should_pause_asr": False,
            "timeout_warning": False,
        }

        if is_silent:
            if self._silence_start is None:
                self._silence_start = now

            silence_duration = (now - self._silence_start).total_seconds() * 1000
            result["silence_duration_ms"] = silence_duration

            # Pause ASR after min silence to save costs
            if silence_duration >= self.min_silence_ms:
                result["should_pause_asr"] = True

            # Warn about timeout
            if silence_duration >= self.max_silence_ms * 0.8:
                result["timeout_warning"] = True

            self._total_silence_ms += frame_duration_ms
        else:
            self._silence_start = None
            self._total_speech_ms += frame_duration_ms

        return result

    def get_stats(self) -> dict:
        """Get silence detection statistics"""
        total = self._total_silence_ms + self._total_speech_ms
        silence_ratio = self._total_silence_ms / total if total > 0 else 0

        return {
            "total_silence_ms": self._total_silence_ms,
            "total_speech_ms": self._total_speech_ms,
            "silence_ratio": round(silence_ratio, 3),
            "estimated_asr_savings_pct": round(silence_ratio * 100, 1),
        }


# ============================================================================
# COST TRACKER
# ============================================================================


class CostTracker:
    """
    Tracks costs per tenant and generates alerts.

    Features:
    - Real-time cost tracking
    - Budget alerts
    - Cost analytics
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        costs: ModelCosts = DEFAULT_COSTS,
    ):
        self.redis = redis_client
        self.costs = costs

    async def record_cost(
        self,
        tenant_id: UUID,
        cost_type: str,
        amount_usd: float,
        metadata: Optional[dict] = None,
    ):
        """
        Record a cost event.

        Args:
            tenant_id: Tenant ID
            cost_type: Type of cost (llm, asr, tts, telephony)
            amount_usd: Cost in USD
            metadata: Additional metadata
        """
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")

        pipe = self.redis.pipeline()

        # Daily cost by type
        pipe.hincrbyfloat(f"costs:daily:{tenant_id}:{today}", cost_type, amount_usd)
        pipe.expire(f"costs:daily:{tenant_id}:{today}", 86400 * 7)  # 7 days

        # Daily total
        pipe.incrbyfloat(f"costs:daily:total:{tenant_id}:{today}", amount_usd)
        pipe.expire(f"costs:daily:total:{tenant_id}:{today}", 86400 * 7)

        # Monthly cost
        pipe.incrbyfloat(f"costs:monthly:{tenant_id}:{month}", amount_usd)
        pipe.expire(f"costs:monthly:{tenant_id}:{month}", 86400 * 35)

        await pipe.execute()

    async def record_llm_usage(
        self,
        tenant_id: UUID,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ):
        """Record LLM token usage and cost"""
        if model == "gpt-4o":
            cost = (
                (input_tokens / 1_000_000) * self.costs.gpt4o_input +
                (output_tokens / 1_000_000) * self.costs.gpt4o_output
            )
        else:
            cost = (
                (input_tokens / 1_000_000) * self.costs.gpt4o_mini_input +
                (output_tokens / 1_000_000) * self.costs.gpt4o_mini_output
            )

        await self.record_cost(tenant_id, "llm", cost, {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })

    async def record_telephony_usage(
        self,
        tenant_id: UUID,
        direction: str,
        duration_minutes: float,
    ):
        """Record telephony usage and cost"""
        if direction == "inbound":
            rate = self.costs.twilio_voice_inbound
        else:
            rate = self.costs.twilio_voice_outbound

        cost = duration_minutes * rate
        await self.record_cost(tenant_id, "telephony", cost, {
            "direction": direction,
            "duration_minutes": duration_minutes,
        })

    async def record_asr_usage(
        self,
        tenant_id: UUID,
        duration_minutes: float,
        provider: str = "deepgram",
    ):
        """Record ASR usage and cost"""
        rate = self.costs.deepgram_nova if provider == "deepgram" else self.costs.whisper
        cost = duration_minutes * rate

        await self.record_cost(tenant_id, "asr", cost, {
            "provider": provider,
            "duration_minutes": duration_minutes,
        })

    async def record_tts_usage(
        self,
        tenant_id: UUID,
        characters: int,
        provider: str = "elevenlabs",
    ):
        """Record TTS usage and cost"""
        if provider == "elevenlabs":
            rate = self.costs.elevenlabs
        elif provider == "playht":
            rate = self.costs.playht
        else:
            rate = self.costs.azure_tts

        cost = (characters / 1000) * rate
        await self.record_cost(tenant_id, "tts", cost, {
            "provider": provider,
            "characters": characters,
        })

    async def get_daily_costs(self, tenant_id: UUID, date: Optional[str] = None) -> dict:
        """Get daily cost breakdown"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        key = f"costs:daily:{tenant_id}:{date}"

        costs = await self.redis.hgetall(key)
        total = await self.redis.get(f"costs:daily:total:{tenant_id}:{date}")

        return {
            "date": date,
            "breakdown": {k.decode(): float(v) for k, v in costs.items()},
            "total_usd": float(total) if total else 0,
        }

    async def get_monthly_costs(self, tenant_id: UUID, month: Optional[str] = None) -> dict:
        """Get monthly total cost"""
        month = month or datetime.now().strftime("%Y-%m")
        key = f"costs:monthly:{tenant_id}:{month}"

        total = await self.redis.get(key)

        return {
            "month": month,
            "total_usd": float(total) if total else 0,
        }

    async def check_budget(
        self,
        tenant_id: UUID,
        daily_budget: float,
        monthly_budget: float,
    ) -> dict:
        """
        Check if tenant is within budget.

        Returns:
            Budget status with warnings
        """
        daily = await self.get_daily_costs(tenant_id)
        monthly = await self.get_monthly_costs(tenant_id)

        daily_usage = daily["total_usd"] / daily_budget if daily_budget > 0 else 0
        monthly_usage = monthly["total_usd"] / monthly_budget if monthly_budget > 0 else 0

        alerts = []

        if daily_usage >= 1.0:
            alerts.append({"level": "critical", "message": "Daily budget exceeded"})
        elif daily_usage >= 0.8:
            alerts.append({"level": "warning", "message": "80% of daily budget used"})

        if monthly_usage >= 1.0:
            alerts.append({"level": "critical", "message": "Monthly budget exceeded"})
        elif monthly_usage >= 0.8:
            alerts.append({"level": "warning", "message": "80% of monthly budget used"})

        return {
            "daily": {
                "used": daily["total_usd"],
                "budget": daily_budget,
                "percentage": round(daily_usage * 100, 1),
            },
            "monthly": {
                "used": monthly["total_usd"],
                "budget": monthly_budget,
                "percentage": round(monthly_usage * 100, 1),
            },
            "alerts": alerts,
            "within_budget": len(alerts) == 0 or all(a["level"] != "critical" for a in alerts),
        }


# ============================================================================
# COST OPTIMIZATION MANAGER
# ============================================================================


class CostOptimizationManager:
    """
    Central manager for all cost optimization features.

    Combines:
    - Response caching
    - Model routing
    - Silence detection
    - Cost tracking
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        costs: ModelCosts = DEFAULT_COSTS,
    ):
        self.redis = redis_client
        self.costs = costs

        self.cache = ResponseCache(redis_client)
        self.router = ModelRouter(self.cache, costs)
        self.tracker = CostTracker(redis_client, costs)

        # Per-call silence detectors
        self._silence_detectors: dict[UUID, SilenceDetector] = {}

    def get_silence_detector(self, call_id: UUID) -> SilenceDetector:
        """Get or create silence detector for a call"""
        if call_id not in self._silence_detectors:
            self._silence_detectors[call_id] = SilenceDetector()
        return self._silence_detectors[call_id]

    def remove_silence_detector(self, call_id: UUID):
        """Remove silence detector when call ends"""
        self._silence_detectors.pop(call_id, None)

    async def optimize_request(
        self,
        tenant_id: UUID,
        query: str,
        context: dict,
    ) -> dict:
        """
        Optimize an AI request for cost.

        Returns optimization recommendations and cached response if available.
        """
        result = {
            "cached_response": None,
            "model_config": None,
            "optimizations_applied": [],
        }

        # Try cache first
        cached = await self.cache.get(tenant_id, query, context)
        if cached:
            result["cached_response"] = cached
            result["optimizations_applied"].append("response_cache")
            return result

        # Select optimal model
        model_config = self.router.select_model(query, context)
        result["model_config"] = model_config
        result["optimizations_applied"].append(f"model_routing:{model_config['model']}")

        return result

    async def get_optimization_stats(self, tenant_id: UUID) -> dict:
        """Get optimization statistics for a tenant"""
        cache_stats = self.cache.get_stats()
        daily_costs = await self.tracker.get_daily_costs(tenant_id)
        monthly_costs = await self.tracker.get_monthly_costs(tenant_id)

        return {
            "cache": cache_stats,
            "costs": {
                "daily": daily_costs,
                "monthly": monthly_costs,
            },
            "estimated_savings": {
                "from_caching_usd": cache_stats.get("estimated_savings_usd", 0),
                "from_model_routing_pct": 30,  # Estimated savings from using smaller models
            },
        }
