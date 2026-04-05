"""
SYNAPSE Full Jitter Retry Utility (ADR-016).
ALL retries in SYNAPSE must use this module. Fixed-delay retries are a PR rejection.
Implementation: Full Jitter — sleep = random(0, min(cap, base * 2^attempt))
Reference: AWS Architecture Blog — Exponential Backoff and Jitter
"""
from __future__ import annotations

import asyncio
import functools
import logging
import random
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")


def full_jitter_delay(
    base_delay: float,
    attempt: int,
    cap: float = 60.0,
) -> float:
    """Compute Full Jitter delay: random(0, min(cap, base * 2^attempt))."""
    exponential = min(cap, base_delay * (2 ** attempt))
    return random.uniform(0, exponential)  # noqa: S311


def retry_with_jitter(
    max_retries: int = 3,
    base_delay: float = 0.5,
    cap: float = 60.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[..., Any]:
    """
    Decorator: retry with Full Jitter (ADR-016).
    Supports both sync and async functions.
    """
    if max_retries <= 0:
        raise ValueError("max_retries must be > 0")
    if base_delay <= 0:
        raise ValueError("base_delay must be > 0")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = full_jitter_delay(base_delay, attempt, cap)
                        logger.warning(
                            "Retry %d/%d for %s after %.2fs: %s",
                            attempt + 1,
                            max_retries,
                            func.__name__,
                            delay,
                            str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "All %d retries exhausted for %s: %s",
                            max_retries,
                            func.__name__,
                            str(e),
                        )
            raise last_exception  # type: ignore[misc]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time

            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = full_jitter_delay(base_delay, attempt, cap)
                        logger.warning(
                            "Retry %d/%d for %s after %.2fs: %s",
                            attempt + 1,
                            max_retries,
                            func.__name__,
                            delay,
                            str(e),
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "All %d retries exhausted for %s: %s",
                            max_retries,
                            func.__name__,
                            str(e),
                        )
            raise last_exception  # type: ignore[misc]

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
