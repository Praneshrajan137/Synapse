"""
SYNAPSE circuit breaker registry (WS-1 §2, ADR-025).

Wraps every external dependency call (Ollama, Neo4j, Pinecone, Feast,
Postgres audit, Kafka) so a sustained fault opens the circuit and the
caller fails fast instead of stalling the asyncio event loop.

Each breaker is a singleton keyed by name. State transitions emit a
Prometheus gauge ``synapse_breaker_state`` (0=closed, 1=half_open,
2=open) so brownout policy (WS-1 §5) can consult breaker state.

Native asyncio implementation, no external dep — keeps surface small
and avoids pulling in a transitive runtime that we'd have to wrap
anyway for Prometheus integration.
"""

from __future__ import annotations

import asyncio
import functools
import time
from enum import IntEnum
from typing import Any, TypeVar

import structlog

from synapse_common.metrics import BREAKER_STATE

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class BreakerState(IntEnum):
    """Breaker state — IntEnum so Prometheus gauge value is the state code."""

    CLOSED = 0
    HALF_OPEN = 1
    OPEN = 2


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a call is attempted on an open breaker."""

    def __init__(self, name: str) -> None:
        super().__init__(f"circuit breaker '{name}' is OPEN")
        self.name = name


class CircuitBreaker:
    """Async circuit breaker keyed by name. Thread-safe across asyncio tasks."""

    def __init__(
        self,
        name: str,
        fail_max: int = 5,
        reset_timeout: float = 30.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._expected = expected_exceptions
        self._state: BreakerState = BreakerState.CLOSED
        self._consecutive_failures: int = 0
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()
        BREAKER_STATE.labels(name=self.name).set(int(self._state))

    @property
    def state(self) -> BreakerState:
        return self._state

    def _set_state(self, new_state: BreakerState) -> None:
        if new_state == self._state:
            return
        logger.info(
            "breaker_state_change",
            name=self.name,
            from_state=self._state.name,
            to_state=new_state.name,
        )
        self._state = new_state
        BREAKER_STATE.labels(name=self.name).set(int(new_state))

    async def _maybe_half_open(self) -> None:
        if (
            self._state == BreakerState.OPEN
            and (time.monotonic() - self._opened_at) >= self.reset_timeout
        ):
            self._set_state(BreakerState.HALF_OPEN)

    async def call(self, func: Any, /, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        """Invoke ``func`` through the breaker. Raises ``CircuitBreakerOpenError`` when open."""
        async with self._lock:
            await self._maybe_half_open()
            if self._state == BreakerState.OPEN:
                raise CircuitBreakerOpenError(self.name)

        try:
            result = await func(*args, **kwargs)
        except self._expected as exc:
            await self._record_failure(exc)
            raise
        else:
            await self._record_success()
            return result

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state in (BreakerState.HALF_OPEN, BreakerState.OPEN):
                self._set_state(BreakerState.CLOSED)
            self._consecutive_failures = 0

    async def _record_failure(self, exc: BaseException) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            if self._state == BreakerState.HALF_OPEN or self._consecutive_failures >= self.fail_max:
                self._opened_at = time.monotonic()
                self._set_state(BreakerState.OPEN)
            logger.warning(
                "breaker_failure_recorded",
                name=self.name,
                consecutive=self._consecutive_failures,
                fail_max=self.fail_max,
                state=self._state.name,
                error=str(exc),
            )


_REGISTRY: dict[str, CircuitBreaker] = {}
_REGISTRY_LOCK = asyncio.Lock()


def get_breaker(
    name: str,
    fail_max: int = 5,
    reset_timeout: float = 30.0,
    expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> CircuitBreaker:
    """Return the named singleton breaker, creating it if missing."""
    existing = _REGISTRY.get(name)
    if existing is not None:
        return existing
    breaker = CircuitBreaker(
        name=name,
        fail_max=fail_max,
        reset_timeout=reset_timeout,
        expected_exceptions=expected_exceptions,
    )
    _REGISTRY[name] = breaker
    return breaker


def breaker(
    name: str,
    fail_max: int = 5,
    reset_timeout: float = 30.0,
    expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Any:  # noqa: ANN401
    """Decorator wrapping an async callable in the named breaker."""

    def decorator(func: Any) -> Any:  # noqa: ANN401
        cb = get_breaker(
            name=name,
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            expected_exceptions=expected_exceptions,
        )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await cb.call(func, *args, **kwargs)

        return wrapper

    return decorator


def reset_registry() -> None:
    """Clear the breaker registry. Test-only helper."""
    _REGISTRY.clear()
