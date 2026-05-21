"""
SYNAPSE Graceful Shutdown (WS-1).

Every FastAPI service (api, orchestrator, 8 agents) registers a SIGTERM
handler that:

    1. Marks readiness=false so K8s / health checks stop sending traffic.
    2. Waits up to ``SHUTDOWN_GRACE_S`` for in-flight requests to finish.
    3. Closes Kafka consumers (drains then commits offsets).
    4. Flushes Kafka producers.
    5. Closes DB pools (Postgres, Redis).
    6. Closes bulkhead httpx clients (synapse_common.clients).

The single ``ShutdownCoordinator`` instance per process is created in the
FastAPI ``lifespan`` and consulted by health endpoints.

Usage
-----
    from synapse_common.lifespan import ShutdownCoordinator

    coordinator = ShutdownCoordinator(grace_seconds=25.0)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        coordinator.install_signal_handlers()
        coordinator.register("kafka_producer", producer.close)
        coordinator.register("kafka_consumer", consumer.close)
        coordinator.register("postgres_pool", pool.close)
        yield
        await coordinator.shutdown()

Each registered closer is awaited (or run sync if not a coroutine). Closers
are invoked in *reverse* registration order so consumers drain before
producers flush.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import signal
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_GRACE_SECONDS = float(os.environ.get("SYNAPSE_SHUTDOWN_GRACE_S", "25"))

Closer = Callable[[], "Awaitable[None] | None"]


class ShutdownCoordinator:
    """Coordinates graceful shutdown across Kafka, DB, HTTP clients."""

    def __init__(self, grace_seconds: float = DEFAULT_GRACE_SECONDS) -> None:
        self.grace_seconds = grace_seconds
        self._closers: list[tuple[str, Closer]] = []
        self._ready: bool = True
        self._shutting_down: bool = False
        self._lock = asyncio.Lock()

    @property
    def ready(self) -> bool:
        return self._ready and not self._shutting_down

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down

    def register(self, name: str, closer: Closer) -> None:
        """Register a resource to close on shutdown.

        Closers run in reverse registration order. Both async and sync
        closers are accepted.
        """
        self._closers.append((name, closer))
        logger.debug("shutdown_closer_registered", name=name)

    def install_signal_handlers(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Wire SIGTERM (and SIGINT in dev) to begin shutdown.

        On Windows, signal.SIGTERM behaviour differs; the handler still
        installs but Windows may not deliver it reliably. Production
        deployments are Linux containers where SIGTERM works as expected.
        """
        active_loop = loop or asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            handler: Callable[[], None] = self._make_signal_handler(sig)
            try:
                active_loop.add_signal_handler(sig, handler)
            except NotImplementedError:
                # Windows event loops don't support add_signal_handler for
                # all signals. The lifespan exit will still trigger shutdown.
                logger.warning("signal_handler_unsupported", signal=sig.name)

    def _make_signal_handler(self, sig: signal.Signals) -> Callable[[], None]:
        def _handle() -> None:
            asyncio.create_task(self._on_signal(sig))

        return _handle

    async def _on_signal(self, sig: signal.Signals) -> None:
        logger.info("shutdown_signal_received", signal=sig.name)
        await self.shutdown()

    async def shutdown(self) -> None:
        """Begin graceful shutdown. Idempotent."""
        async with self._lock:
            if self._shutting_down:
                return
            self._shutting_down = True
            self._ready = False

        logger.info("shutdown_started", grace_seconds=self.grace_seconds)
        deadline = time.monotonic() + self.grace_seconds

        for name, closer in reversed(self._closers):
            remaining = max(deadline - time.monotonic(), 0.5)
            try:
                await asyncio.wait_for(_run_closer(closer), timeout=remaining)
                logger.info("shutdown_closer_done", name=name)
            except TimeoutError:
                logger.warning("shutdown_closer_timeout", name=name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("shutdown_closer_failed", name=name, error=str(exc))

        logger.info("shutdown_complete")


async def _run_closer(closer: Closer) -> None:
    result = closer()
    if inspect.isawaitable(result):
        await result


def deep_health_check(
    *checks: Callable[[], Awaitable[bool]],
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Compose dependency checks into a single readiness probe.

    Each check is an awaitable returning ``True`` for healthy. The composed
    probe returns ``{"status": "ok"|"degraded", "checks": {...}}`` so
    operators can see *which* dependency is failing.
    """

    async def probe() -> dict[str, Any]:
        results: dict[str, bool] = {}
        all_ok = True
        for check in checks:
            name = getattr(check, "__name__", "anonymous")
            try:
                ok = await check()
            except Exception as exc:  # noqa: BLE001
                logger.warning("health_check_failed", name=name, error=str(exc))
                ok = False
            results[name] = ok
            if not ok:
                all_ok = False
        return {"status": "ok" if all_ok else "degraded", "checks": results}

    return probe
