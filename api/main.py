"""SYNAPSE API Gateway — FastAPI front door for demos + load tests.

Delegates to the orchestrator for decision routing, exposes lightweight
read-only queries against the audit trail, and surfaces agent status.

Sprint-7 wiring:
- ``Lifespan`` from ``synapse_common.lifespan`` for graceful SIGTERM.
- A shared ``SynapseProducer`` singleton stored on ``app.state.kafka_producer``.
- A shared async-SQLAlchemy ``session_factory`` on ``app.state.session_factory``.
- A shared ``httpx.AsyncClient`` (via ``synapse_common.clients``) for
  orchestrator proxying — replaces the prior synchronous ``requests`` call.

I-9: A2A (JSON-RPC) to talk to the orchestrator; MCP only for tool calls.
I-1: no paid APIs.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from synapse_common.clients import close_clients, get_client
from synapse_common.kafka_client import KafkaConfig, SynapseProducer
from synapse_common.lifespan import graceful_shutdown

from api.routers import agents, decisions, orders

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

try:
    from synapse_common.tracing import instrument_fastapi
except Exception:  # noqa: BLE001 — OTel optional

    def instrument_fastapi(app: FastAPI) -> None:  # type: ignore[misc]
        return None


logger = structlog.get_logger(__name__)


def _install_profiler(app: FastAPI) -> None:
    """Sprint 8 M16: when SYNAPSE_PROFILE=1, attach pyinstrument middleware.

    Off by default; only enabled in `make profile` runs. Sprint 9 wires the
    flamegraph export to a dashboard.
    """
    if os.environ.get("SYNAPSE_PROFILE", "").lower() not in {"1", "true", "yes"}:
        return
    try:
        from pyinstrument import Profiler
        from starlette.middleware.base import BaseHTTPMiddleware
    except ImportError:
        logger.warning("synapse_profile_requested_but_pyinstrument_missing")
        return

    class _ProfileMiddleware(BaseHTTPMiddleware):
        async def dispatch(  # type: ignore[no-untyped-def]  # noqa: ANN202
            self,
            request,  # noqa: ANN001
            call_next,  # noqa: ANN001
        ):
            profiler = Profiler(async_mode="enabled")
            profiler.start()
            response = await call_next(request)
            profiler.stop()
            request.state.profile_html = profiler.output_html()
            return response

    app.add_middleware(_ProfileMiddleware)
    logger.info("synapse_profile_middleware_installed")


def _postgres_dsn() -> str:
    return os.environ.get(
        "SYNAPSE_API_POSTGRES_DSN",
        "postgresql+asyncpg://synapse_app:synapse_app_2026@postgres:5432/synapse_audit",
    )


def _kafka_bootstrap() -> str:
    return os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Wire shared resources and register graceful shutdown hooks."""
    async with graceful_shutdown("api-gateway") as ls:
        engine = create_async_engine(_postgres_dsn(), pool_size=10, max_overflow=5)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        producer = SynapseProducer(KafkaConfig(bootstrap_servers=_kafka_bootstrap()))
        # Warm the orchestrator HTTP bulkhead so the first request doesn't pay
        # the connection-pool cost.
        await get_client("orchestrator")

        app.state.session_factory = session_factory
        app.state.kafka_producer = producer
        app.state.lifespan = ls

        ls.on_shutdown("httpx_bulkheads", close_clients)
        ls.on_shutdown("kafka_producer", lambda: _flush_producer(producer))
        ls.on_shutdown("postgres_engine", engine.dispose)
        logger.info("api_gateway_ready", postgres=_postgres_dsn(), kafka=_kafka_bootstrap())
        yield


async def _flush_producer(producer: SynapseProducer) -> None:
    producer.flush(timeout=5.0)
    producer.close()


app = FastAPI(
    title="SYNAPSE API Gateway",
    version="1.1.0",
    description="Front door to the SYNAPSE multi-agent quick-commerce platform",
    lifespan=lifespan,
)

app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["decisions"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])

_install_profiler(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "synapse-api"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    ls = getattr(app.state, "lifespan", None)
    is_ready = bool(ls.ready) if ls is not None else False
    return {
        "status": "ready" if is_ready else "starting",
        "orchestrator": os.environ.get("SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085"),
    }


try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception as exc:  # noqa: BLE001
    logger.warning("prometheus_instrumentator_missing", error=str(exc))

instrument_fastapi(app)
