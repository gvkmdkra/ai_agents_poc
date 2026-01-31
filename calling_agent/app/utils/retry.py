"""
Retry Utilities
Provides retry logic for external API calls with exponential backoff
"""

import asyncio
import time
from functools import wraps
from typing import Optional, Callable, Any, Type, Tuple, Union

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class RetryError(Exception):
    """Raised when all retry attempts fail"""
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


def retry_sync(
    max_retries: Optional[int] = None,
    delay: Optional[float] = None,
    backoff_multiplier: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    Synchronous retry decorator with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts (uses settings default if not provided)
        delay: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function called on each retry with (attempt, exception)
    """
    max_retries = max_retries or settings.api_max_retries
    delay = delay or settings.api_retry_delay

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} failed for {func.__name__}: {e}"
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    if attempt < max_retries:
                        logger.info(f"Retrying in {current_delay:.1f}s...")
                        time.sleep(current_delay)
                        current_delay *= backoff_multiplier
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}"
                        )

            raise RetryError(
                f"Failed after {max_retries} attempts",
                last_exception=last_exception
            )

        return wrapper
    return decorator


def retry_async(
    max_retries: Optional[int] = None,
    delay: Optional[float] = None,
    backoff_multiplier: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    Asynchronous retry decorator with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function called on each retry
    """
    max_retries = max_retries or settings.api_max_retries
    delay = delay or settings.api_retry_delay

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} failed for {func.__name__}: {e}"
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    if attempt < max_retries:
                        logger.info(f"Retrying in {current_delay:.1f}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_multiplier
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}"
                        )

            raise RetryError(
                f"Failed after {max_retries} attempts",
                last_exception=last_exception
            )

        return wrapper
    return decorator


async def retry_async_operation(
    operation: Callable,
    max_retries: Optional[int] = None,
    delay: Optional[float] = None,
    backoff_multiplier: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    operation_name: str = "operation"
) -> Any:
    """
    Execute an async operation with retry logic

    Args:
        operation: Async callable to execute
        max_retries: Maximum retry attempts
        delay: Initial delay between retries
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Exception types to catch
        operation_name: Name for logging purposes

    Returns:
        Result of the operation

    Raises:
        RetryError: If all attempts fail
    """
    max_retries = max_retries or settings.api_max_retries
    delay = delay or settings.api_retry_delay
    last_exception = None
    current_delay = delay

    for attempt in range(1, max_retries + 1):
        try:
            return await operation()
        except exceptions as e:
            last_exception = e
            logger.warning(
                f"Attempt {attempt}/{max_retries} failed for {operation_name}: {e}"
            )

            if attempt < max_retries:
                logger.info(f"Retrying {operation_name} in {current_delay:.1f}s...")
                await asyncio.sleep(current_delay)
                current_delay *= backoff_multiplier
            else:
                logger.error(f"All {max_retries} attempts failed for {operation_name}")

    raise RetryError(
        f"Failed {operation_name} after {max_retries} attempts",
        last_exception=last_exception
    )


def retry_sync_operation(
    operation: Callable,
    max_retries: Optional[int] = None,
    delay: Optional[float] = None,
    backoff_multiplier: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    operation_name: str = "operation"
) -> Any:
    """
    Execute a sync operation with retry logic

    Args:
        operation: Callable to execute
        max_retries: Maximum retry attempts
        delay: Initial delay between retries
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Exception types to catch
        operation_name: Name for logging purposes

    Returns:
        Result of the operation

    Raises:
        RetryError: If all attempts fail
    """
    max_retries = max_retries or settings.api_max_retries
    delay = delay or settings.api_retry_delay
    last_exception = None
    current_delay = delay

    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except exceptions as e:
            last_exception = e
            logger.warning(
                f"Attempt {attempt}/{max_retries} failed for {operation_name}: {e}"
            )

            if attempt < max_retries:
                logger.info(f"Retrying {operation_name} in {current_delay:.1f}s...")
                time.sleep(current_delay)
                current_delay *= backoff_multiplier
            else:
                logger.error(f"All {max_retries} attempts failed for {operation_name}")

    raise RetryError(
        f"Failed {operation_name} after {max_retries} attempts",
        last_exception=last_exception
    )
