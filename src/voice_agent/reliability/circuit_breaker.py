"""
Circuit Breaker & Failover Handling

Implements:
- Circuit breaker pattern for external services
- Failover to human agents
- Graceful degradation
- Retry strategies with exponential backoff
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3          # Successes to close from half-open
    timeout_seconds: float = 30.0       # Time before half-open
    half_open_max_calls: int = 3        # Max calls in half-open state


@dataclass
class CircuitStats:
    """Circuit breaker statistics"""
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.now)
    total_calls: int = 0
    total_failures: int = 0
    total_timeouts: int = 0


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    Usage:
        breaker = CircuitBreaker("ultravox", config)

        @breaker
        async def call_ultravox():
            ...
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0

    async def _should_allow_request(self) -> bool:
        """Check if request should be allowed"""
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if timeout has passed
                if self.stats.last_failure_time:
                    elapsed = (datetime.now() - self.stats.last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        self.state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
                        self.stats.last_state_change = datetime.now()
                        logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN")
                        return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    async def record_success(self):
        """Record a successful call"""
        async with self._lock:
            self.stats.successes += 1
            self.stats.total_calls += 1

            if self.state == CircuitState.HALF_OPEN:
                if self.stats.successes >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.stats.failures = 0
                    self.stats.successes = 0
                    self.stats.last_state_change = datetime.now()
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED")

    async def record_failure(self, error: Optional[Exception] = None):
        """Record a failed call"""
        async with self._lock:
            self.stats.failures += 1
            self.stats.total_failures += 1
            self.stats.total_calls += 1
            self.stats.last_failure_time = datetime.now()

            if error:
                logger.warning(f"Circuit {self.name} failure: {error}")

            if self.state == CircuitState.CLOSED:
                if self.stats.failures >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.stats.last_state_change = datetime.now()
                    logger.error(f"Circuit {self.name}: CLOSED -> OPEN")

            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.stats.successes = 0
                self.stats.last_state_change = datetime.now()
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN")

    def __call__(self, func: Callable) -> Callable:
        """Decorator for wrapping async functions"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not await self._should_allow_request():
                raise CircuitOpenError(f"Circuit {self.name} is open")

            try:
                result = await func(*args, **kwargs)
                await self.record_success()
                return result
            except Exception as e:
                await self.record_failure(e)
                raise

        return wrapper

    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.stats.failures,
            "successes": self.stats.successes,
            "total_calls": self.stats.total_calls,
            "total_failures": self.stats.total_failures,
            "last_failure": self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
            "last_state_change": self.stats.last_state_change.isoformat(),
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# ============================================================================
# FAILOVER MANAGER
# ============================================================================


@dataclass
class FailoverConfig:
    """Failover configuration"""
    ai_timeout_ms: int = 3000           # Max AI response time
    max_ai_retries: int = 2             # Retries before failover
    fallback_script_enabled: bool = True
    human_escalation_enabled: bool = True
    degraded_mode_enabled: bool = True


class FailoverManager:
    """
    Manages failover scenarios for the voice agent.

    Handles:
    - AI timeout fallback to scripts
    - Human escalation
    - Degraded mode operation
    """

    def __init__(self, config: Optional[FailoverConfig] = None):
        self.config = config or FailoverConfig()
        self._fallback_scripts = {}
        self._active_fallbacks = set()

    def register_fallback_script(self, scenario: str, script: list[str]):
        """
        Register a fallback script for a scenario.

        Args:
            scenario: Scenario name (e.g., "greeting", "qualification", "appointment")
            script: List of script lines to speak
        """
        self._fallback_scripts[scenario] = script
        logger.info(f"Registered fallback script for: {scenario}")

    def get_fallback_response(self, scenario: str, context: dict) -> Optional[str]:
        """
        Get a fallback response for a scenario.

        Args:
            scenario: Current conversation scenario
            context: Conversation context

        Returns:
            Fallback script line or None
        """
        if not self.config.fallback_script_enabled:
            return None

        scripts = self._fallback_scripts.get(scenario, [])
        if not scripts:
            # Default fallback
            return (
                "I apologize, but I'm having some technical difficulties. "
                "Let me connect you with a team member who can help. "
                "Please hold for just a moment."
            )

        # Get next script line based on context
        turn = context.get("turn", 0)
        if turn < len(scripts):
            return scripts[turn]

        return scripts[-1] if scripts else None

    async def should_escalate_to_human(
        self,
        ai_failures: int,
        sentiment_score: float,
        explicit_request: bool,
        conversation_turns: int,
    ) -> tuple[bool, str]:
        """
        Determine if conversation should escalate to human.

        Returns:
            (should_escalate, reason)
        """
        if not self.config.human_escalation_enabled:
            return False, ""

        if explicit_request:
            return True, "customer_request"

        if ai_failures >= self.config.max_ai_retries:
            return True, "ai_failure"

        if sentiment_score < -0.7:
            return True, "negative_sentiment"

        if conversation_turns > 20 and sentiment_score < 0:
            return True, "prolonged_negative"

        return False, ""

    def enter_degraded_mode(self, service: str):
        """Enter degraded mode for a service"""
        if self.config.degraded_mode_enabled:
            self._active_fallbacks.add(service)
            logger.warning(f"Entering degraded mode for: {service}")

    def exit_degraded_mode(self, service: str):
        """Exit degraded mode for a service"""
        self._active_fallbacks.discard(service)
        logger.info(f"Exiting degraded mode for: {service}")

    def is_degraded(self, service: str) -> bool:
        """Check if service is in degraded mode"""
        return service in self._active_fallbacks

    def get_degraded_services(self) -> list[str]:
        """Get list of services in degraded mode"""
        return list(self._active_fallbacks)


# ============================================================================
# RETRY STRATEGIES
# ============================================================================


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: tuple = (Exception,),
) -> Any:
    """
    Retry a function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to delays
        retry_exceptions: Exceptions that trigger retry

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    import random

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except retry_exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"All {max_retries} retries failed: {e}")
                raise

            # Calculate delay
            delay = min(base_delay * (exponential_base ** attempt), max_delay)

            if jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(
                f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}"
            )
            await asyncio.sleep(delay)

    raise last_exception


# ============================================================================
# TIMEOUT WRAPPER
# ============================================================================


async def with_timeout(
    coro,
    timeout_seconds: float,
    fallback: Optional[Callable] = None,
    fallback_value: Any = None,
) -> Any:
    """
    Execute a coroutine with timeout and optional fallback.

    Args:
        coro: Coroutine to execute
        timeout_seconds: Timeout in seconds
        fallback: Fallback function if timeout
        fallback_value: Fallback value if timeout (used if fallback is None)

    Returns:
        Result or fallback value
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {timeout_seconds}s")

        if fallback:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback()
            return fallback()

        return fallback_value


# ============================================================================
# GLOBAL CIRCUIT BREAKERS
# ============================================================================


# Pre-configured circuit breakers for critical services
CIRCUIT_BREAKERS = {
    "ultravox": CircuitBreaker(
        "ultravox",
        CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=60,
        )
    ),
    "openai": CircuitBreaker(
        "openai",
        CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=30,
        )
    ),
    "twilio": CircuitBreaker(
        "twilio",
        CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=60,
        )
    ),
    "odoo": CircuitBreaker(
        "odoo",
        CircuitBreakerConfig(
            failure_threshold=10,  # Higher threshold for CRM
            timeout_seconds=120,
        )
    ),
}


def get_circuit_breaker(service: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a service"""
    if service not in CIRCUIT_BREAKERS:
        CIRCUIT_BREAKERS[service] = CircuitBreaker(service)
    return CIRCUIT_BREAKERS[service]


def get_all_circuit_stats() -> dict:
    """Get statistics for all circuit breakers"""
    return {
        name: breaker.get_stats()
        for name, breaker in CIRCUIT_BREAKERS.items()
    }


# ============================================================================
# DEFAULT FALLBACK SCRIPTS
# ============================================================================


DEFAULT_FALLBACK_SCRIPTS = {
    "greeting": [
        "Hello, thank you for calling. I'm having a brief technical issue.",
        "Let me connect you with a team member who can assist you right away.",
        "Please hold for just a moment while I transfer your call.",
    ],
    "qualification": [
        "I appreciate you sharing that information with me.",
        "To better assist you, let me connect you with one of our specialists.",
        "They'll be able to answer all your questions in detail.",
    ],
    "appointment": [
        "I'd be happy to help schedule an appointment for you.",
        "Let me transfer you to someone who can check our availability.",
        "Please hold while I connect you.",
    ],
    "general": [
        "I apologize for the inconvenience.",
        "Let me get a team member to assist you directly.",
        "Your call is important to us. Please hold briefly.",
    ],
}
