"""SYNAPSE API Gateway — FastAPI front door for demos + load tests.

Delegates to the orchestrator for decision routing, exposes lightweight
read-only queries against the audit trail, and surfaces agent status.

Wired with:
- JWT auth (python-jose) — enforced on every POST
- structlog JSON logging
- OpenTelemetry via `synapse_common.tracing.instrument_fastapi`
- Prometheus metrics via prometheus-fastapi-instrumentator
- Bulkheaded async clients + Kafka producer singleton + Postgres pool managed
  by a lifespan, with a graceful SIGTERM drain (WS-1).

I-9: uses A2A (JSON-RPC) to talk to the orchestrator; MCP only for tool
calls. I-1: no paid APIs.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI
from synapse_common import clients
from synapse_common.kafka_client import KafkaConfig, SynapseProducer
from synapse_common.lifespan import ShutdownCoordinator

from api.routers import agents, decisions, orders

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

try:
    from synapse_common.tracing import instrument_fastapi
except Exception:  # noqa: BLE001 — OTel optional

    def instrument_fastapi(app: FastAPI) -> None:  # type: ignore[misc]
        return None


logger = structlog.get_logger(__name__)

ORCHESTRATOR_URL = os.environ.get(
    "SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085"
)
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
POSTGRES_DSN = os.environ.get(
    "POSTGRES_DSN",
    "postgresql://synapse:synapse_audit_2026@postgres:5432/synapse_audit",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources, register graceful-shutdown closers."""
    coordinator = ShutdownCoordinator()
    coordinator.install_signal_handlers()
    app.state.shutdown = coordinator

    app.state.orchestrator_client = await clients.get_client("orchestrator")
    coordinator.register("bulkhead_clients", clients.close_all)

    producer = SynapseProducer(KafkaConfig(bootstrap_servers=KAFKA_BOOTSTRAP))
    app.state.producer = producer
    coordinator.register("kafka_producer", producer.close)

    pool: Any = None
    try:
        import asyncpg  # type: ignore[import-not-found]

        pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=10)
        coordinator.register("postgres_pool", pool.close)
        logger.info("postgres_pool_ready")
    except Exception as exc:  # noqa: BLE001
        # Postgres is read-only in this gateway; degrade rather than refuse boot.
        logger.warning("postgres_pool_unavailable", error=str(exc))
    app.state.postgres_pool = pool

    logger.info(
        "api_gateway_ready",
        orchestrator=ORCHESTRATOR_URL,
        kafka=KAFKA_BOOTSTRAP,
    )
    try:
        yield
    finally:
        await coordinator.shutdown()


app = FastAPI(
    title="SYNAPSE API Gateway",
    version="1.0.0",
    description="Front door to the SYNAPSE multi-agent quick-commerce platform",
    lifespan=lifespan,
)
app.state.orchestrator_url = ORCHESTRATOR_URL

app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["decisions"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])


@app.get("/health/live")
async def liveness() -> dict[str, str]:
    """Liveness probe — true while the process is up. Never blocks on deps."""
    return {"status": "ok", "service": "synapse-api"}


@app.get("/health/ready")
async def readiness() -> dict[str, Any]:
    """Readiness probe — false during shutdown, also reports dep state."""
    coordinator: ShutdownCoordinator | None = getattr(app.state, "shutdown", None)
    deps: dict[str, bool] = {
        "kafka_producer": getattr(app.state, "producer", None) is not None,
        "postgres_pool": getattr(app.state, "postgres_pool", None) is not None,
        "orchestrator_client": getattr(app.state, "orchestrator_client", None) is not None,
    }
    ready = all(deps.values()) and (coordinator is None or coordinator.ready)
    return {"status": "ready" if ready else "not_ready", "checks": deps}


# Backwards-compat aliases (existing dashboards / probes hit these paths).
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "synapse-api"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready", "orchestrator": ORCHESTRATOR_URL}


try:
    from prometheus_fastapi_instrumentator import (  # type: ignore[import-not-found]
        Instrumentator,
    )

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception as exc:  # noqa: BLE001
    logger.warning("prometheus_instrumentator_missing", error=str(exc))

instrument_fastapi(app)
