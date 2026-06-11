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

from api.middleware.ratelimit import RateLimitMiddleware
from api.routers import (
    agents,
    auth,
    decisions,
    firehose,
    orders,
    steering,
    system,
    telemetry,
    topology,
)

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
    """Resolve the async audit DSN. Fail-fast — never embed a credential.

    Plan v2 / Phase 5: removes the hardcoded ``synapse_app:<password>@…``
    default. Prefers ``SYNAPSE_API_POSTGRES_DSN``; falls back to the sync
    ``POSTGRES_DSN`` (rewritten to asyncpg) that the GCP compose already sets so
    the deploy path keeps working without a baked-in secret. Unset → startup
    fails loudly rather than silently using a known password.
    """
    dsn = os.environ.get("SYNAPSE_API_POSTGRES_DSN")
    if dsn:
        return dsn
    sync_dsn = os.environ.get("POSTGRES_DSN")
    if sync_dsn:
        return sync_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    raise RuntimeError(
        "SYNAPSE_API_POSTGRES_DSN (or POSTGRES_DSN) must be set — no embedded credential default"
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

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["decisions"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(steering.router, prefix="/api/v1/steering", tags=["steering"])
# ADR-044: degradation posture (brownout + breaker states) for the FE's
# DegradedBanner — the system-level honesty channel.
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
# Previously-unmounted routers (the module-liveness audit found these defined but
# never included → the frontend's real-time firehose, twin topology graph, and
# browser telemetry/CSP beacons all 404'd/403'd). firehose.router defines
# `/firehose` → mount under `/ws` (nginx proxies `/ws/`); topology + telemetry
# define `/api/v1`-relative paths the frontend calls.
app.include_router(firehose.router, prefix="/ws", tags=["firehose"])
app.include_router(topology.router, prefix="/api/v1", tags=["topology"])
app.include_router(telemetry.router, prefix="/api/v1", tags=["telemetry"])

# Application-layer rate limiting (token bucket per client IP). nginx limits at
# the edge; this protects the gateway when reached directly. Health/metrics exempt.
app.add_middleware(RateLimitMiddleware)

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


@app.get("/version")
async def version() -> dict[str, str]:
    # ADR-039: deployed-version truth. The values are baked in at image-build
    # time by cd-gcp.yml's build-args. `unknown`/`dev` means the image was not
    # built by the official pipeline (local dev, manual build, etc.).
    return {
        "service": "api-gateway",
        "version": app.version,
        "git_sha": os.environ.get("SYNAPSE_BUILD_SHA", "dev"),
        "build_time": os.environ.get("SYNAPSE_BUILD_TIME", "unknown"),
    }


try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception as exc:  # noqa: BLE001
    logger.warning("prometheus_instrumentator_missing", error=str(exc))

instrument_fastapi(app)
