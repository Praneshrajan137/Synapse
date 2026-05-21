"""
SYNAPSE graceful-shutdown lifespan helper (WS-1 §6, ADR-025).

FastAPI services (api gateway, orchestrator, 8 agents) register
shutdown hooks for: Kafka consumer close, Kafka producer flush,
DB pool dispose, HTTP client close, outbox dispatcher stop.

On SIGTERM:
  1. set readiness = false (so the load balancer drains us)
  2. wait up to ``SHUTDOWN_GRACE_S`` for in-flight requests
  3. run shutdown hooks in reverse registration order
  4. log a summary

Designed so existing FastAPI ``lifespan`` async-contextmanagers wrap
this object — see ``orchestrator/inference/serve.py`` integration.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Final

import structlog

logger = structlog.get_logger(__name__)


SHUTDOWN_GRACE_S: Final[float] = float(os.environ.get("SYNAPSE_SHUTDOWN_GRACE_S", "25"))


ShutdownHook = Callable[[], Awaitable[None]]


class Lifespan:
    """Tracks readiness and runs ordered shutdown hooks on SIGTERM."""

    def __init__(self, service_name: str, shutdown_grace_s: float = SHUTDOWN_GRACE_S) -> None:
        self.service_name = service_name
        self.shutdown_grace_s = shutdown_grace_s
        self._hooks: list[tuple[str, ShutdownHook]] = []
        self._ready: bool = False
        self._shutting_down: bool = False
        self._installed_signals: bool = False

    @property
    def ready(self) -> bool:
        return self._ready and not self._shutting_down

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down

    def on_shutdown(self, name: str, hook: ShutdownHook) -> None:
        """Register a shutdown hook. Hooks run in reverse registration order."""
        self._hooks.append((name, hook))

    async def start(self) -> None:
        """Mark service ready and install SIGTERM/SIGINT handlers (POSIX only)."""
        self._ready = True
        self._install_signal_handlers()
        logger.info("lifespan_started", service=self.service_name, hooks=len(self._hooks))

    async def shutdown(self) -> None:
        """Drain readiness, await in-flight grace window, then run hooks LIFO."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self._ready = False
        logger.info(
            "lifespan_shutdown_begin",
            service=self.service_name,
            grace_s=self.shutdown_grace_s,
            hooks=len(self._hooks),
        )
        # In-flight drain: a brief sleep gives the load balancer time to
        # observe readiness=false. We rely on per-hook timeouts for hard caps.
        await asyncio.sleep(min(self.shutdown_grace_s, 1.0))
        start = time.monotonic()
        for name, hook in reversed(self._hooks):
            remaining = max(self.shutdown_grace_s - (time.monotonic() - start), 1.0)
            try:
                await asyncio.wait_for(hook(), timeout=remaining)
                logger.info("lifespan_hook_completed", service=self.service_name, hook=name)
            except TimeoutError:
                logger.error("lifespan_hook_timeout", service=self.service_name, hook=name)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "lifespan_hook_failed",
                    service=self.service_name,
                    hook=name,
                    error=str(exc),
                )
        logger.info("lifespan_shutdown_complete", service=self.service_name)

    def _install_signal_handlers(self) -> None:
        if self._installed_signals or sys.platform == "win32":
            # asyncio signal handlers are not supported on Windows event loops.
            # Container deployment uses POSIX runtimes; this is acceptable.
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_signal(s)),
            )
        self._installed_signals = True

    async def _handle_signal(self, sig: signal.Signals) -> None:
        logger.warning("lifespan_signal_received", service=self.service_name, signal=sig.name)
        await self.shutdown()


@asynccontextmanager
async def graceful_shutdown(
    service_name: str,
    hooks: list[tuple[str, ShutdownHook]] | None = None,
    shutdown_grace_s: float = SHUTDOWN_GRACE_S,
) -> AsyncIterator[Lifespan]:
    """Async context manager wrapping ``Lifespan.start``/``shutdown``.

    Typical FastAPI usage::

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with graceful_shutdown("orchestrator") as ls:
                ls.on_shutdown("ollama", lambda: ollama_client.close())
                ls.on_shutdown("kafka_producer", lambda: producer.close())
                app.state.lifespan = ls
                yield
    """
    ls = Lifespan(service_name=service_name, shutdown_grace_s=shutdown_grace_s)
    if hooks:
        for name, hook in hooks:
            ls.on_shutdown(name, hook)
    await ls.start()
    try:
        yield ls
    finally:
        await ls.shutdown()
