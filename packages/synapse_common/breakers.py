"""
SYNAPSE Circuit Breakers (WS-1).

Async-first, named, Prometheus-instrumented. One breaker per external
dependency (Ollama, Neo4j, Pinecone, Postgres, Redis, Kafka). Wrap every
external call so a single dependency outage cannot fan out into the whole
orchestrator.

State machine
-------------
CLOSED   --(fail_max consecutive failures)--> OPEN
OPEN     --(reset_timeout elapses)--------->  HALF_OPEN
HALF_OPEN --(success)---------------------->  CLOSED
HALF_OPEN --(failure)----------------------->  OPEN

Usage
-----
    breaker = get_breaker("ollama", fail_max=5, reset_timeout=30.0)
    async with breaker.guard():
        return await ollama_client.chat(...)

Or as a decorator:
    @breaker.protect()
    async def call_ollama(...) -> str:
        ...

When OPEN, the breaker raises ``BreakerOpenError`` immediately rather than
calling the protected function. Callers should catch it and degrade
gracefully (cached response, brownout, fallback model).
"""

from __future__ import annotations

import asyncio
import functools
import time
from contextlib import asynccontextmanager
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

import structlog
from prometheus_client import Counter, Gauge

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


_STATE_VALUE: dict[BreakerState, int] = {
    BreakerState.CLOSED: 0,
    BreakerState.OPEN: 1,
    BreakerState.HALF_OPEN: 2,
}


class BreakerOpenError(RuntimeError):
    """Raised when a call is rejected because the breaker is OPEN."""

    def __init__(self, name: str, retry_after_seconds: float) -> None:
        super().__init__(
            f"circuit breaker '{name}' is OPEN; retry after {retry_after_seconds:.1f}s"
        )
        self.name = name
        self.retry_after_seconds = retry_after_seconds


BREAKER_STATE_GAUGE: Gauge = Gauge(
    "synapse_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["name"],
)

BREAKER_TRANSITIONS_TOTAL: Counter = Counter(
    "synapse_breaker_transitions_total",
    "Circuit breaker state transitions",
    ["name", "from_state", "to_state"],
)

BREAKER_REJECTIONS_TOTAL: Counter = Counter(
    "synapse_breaker_rejections_total",
    "Calls rejected because the breaker was OPEN",
    ["name"],
)


class AsyncBreaker:
    """Async circuit breaker.

    Concurrency-safe: state transitions are guarded by ``asyncio.Lock``.
    Prometheus metrics are emitted on every transition and rejection so
    operators can correlate dependency outages with shed traffic.
    """

    def __init__(
        self,
        name: str,
        *,
        fail_max: int = 5,
        reset_timeout: float = 30.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        if fail_max <= 0:
            raise ValueError("fail_max must be > 0")
        if reset_timeout <= 0:
            raise ValueError("reset_timeout must be > 0")
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.expected_exceptions = expected_exceptions
        self._state: BreakerState = BreakerState.CLOSED
        self._failures: int = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()
        BREAKER_STATE_GAUGE.labels(name=self.name).set(_STATE_VALUE[BreakerState.CLOSED])

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def failures(self) -> int:
        return self._failures

    async def _transition(self, to_state: BreakerState) -> None:
        if to_state is self._state:
            return
        from_state = self._state
        self._state = to_state
        BREAKER_STATE_GAUGE.labels(name=self.name).set(_STATE_VALUE[to_state])
        BREAKER_TRANSITIONS_TOTAL.labels(
            name=self.name,
            from_state=from_state.value,
            to_state=to_state.value,
        ).inc()
        logger.warning(
            "breaker_transition",
            name=self.name,
            from_state=from_state.value,
            to_state=to_state.value,
            failures=self._failures,
        )

    async def _maybe_half_open(self) -> None:
        """If OPEN and the reset window has elapsed, move to HALF_OPEN."""
        if (
            self._state is BreakerState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self.reset_timeout
        ):
            await self._transition(BreakerState.HALF_OPEN)

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state is BreakerState.HALF_OPEN:
                await self._transition(BreakerState.CLOSED)
            self._failures = 0
            self._opened_at = None

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._state is BreakerState.HALF_OPEN or self._failures >= self.fail_max:
                self._opened_at = time.monotonic()
                await self._transition(BreakerState.OPEN)

    @asynccontextmanager
    async def guard(self) -> AsyncIterator[None]:
        """Async context manager; raises BreakerOpenError when OPEN."""
        async with self._lock:
            await self._maybe_half_open()
            if self._state is BreakerState.OPEN:
                BREAKER_REJECTIONS_TOTAL.labels(name=self.name).inc()
                retry_after = self.reset_timeout - (
                    time.monotonic() - (self._opened_at or time.monotonic())
                )
                raise BreakerOpenError(self.name, max(retry_after, 0.0))
        try:
            yield
        except self.expected_exceptions:
            await self._record_failure()
            raise
        else:
            await self._record_success()

    def protect(self) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
        """Decorator form. Wraps an async function with this breaker."""

        def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> T:
                async with self.guard():
                    return await func(*args, **kwargs)

            return wrapper

        return decorator

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Invoke an async ``func`` under this breaker.

        Equivalent to::

            async with breaker.guard():
                return await func(*args, **kwargs)

        Provided as a sugar surface for callers that prefer a one-shot
        invocation rather than a context manager (used by the A2A SDK
        and other call-site-heavy producers).
        """
        async with self.guard():
            return await func(*args, **kwargs)


_REGISTRY: dict[str, AsyncBreaker] = {}
_REGISTRY_LOCK = asyncio.Lock()


def get_breaker(
    name: str,
    *,
    fail_max: int = 5,
    reset_timeout: float = 30.0,
    expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> AsyncBreaker:
    """Return the named breaker, creating it on first call.

    Names should match the dependency: ``ollama``, ``neo4j``, ``pinecone``,
    ``postgres``, ``redis``, ``kafka``. Re-calling with the same name returns
    the existing instance and ignores the params (the first registration
    wins; this matches breaker semantics where state must persist across
    callers).
    """
    existing = _REGISTRY.get(name)
    if existing is not None:
        return existing
    breaker = AsyncBreaker(
        name,
        fail_max=fail_max,
        reset_timeout=reset_timeout,
        expected_exceptions=expected_exceptions,
    )
    _REGISTRY[name] = breaker
    return breaker


def all_breakers() -> dict[str, AsyncBreaker]:
    """Snapshot of every registered breaker, keyed by dependency name.

    ADR-044: read-only posture surface — the orchestrator's
    ``GET /api/v1/status/posture`` reports each breaker's state so the
    operator UI can show *which* dependency is degrading the system instead
    of a mute green/red dot. Returns a copy; callers cannot mutate the
    registry through it.
    """
    return dict(_REGISTRY)


def reset_registry() -> None:
    """Test helper: clear all registered breakers. Do not call in prod."""
    _REGISTRY.clear()
