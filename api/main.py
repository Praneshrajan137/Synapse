"""SYNAPSE API Gateway — FastAPI front door for demos + load tests.

Delegates to the orchestrator for decision routing, exposes lightweight
read-only queries against the audit trail, and surfaces agent status.

Wired with:
- JWT auth (python-jose) — enforced on every POST
- structlog JSON logging
- OpenTelemetry via `synapse_common.tracing.instrument_fastapi`
- Prometheus metrics via prometheus-fastapi-instrumentator

I-9: uses A2A (JSON-RPC) to talk to the orchestrator; MCP only for tool
calls. I-1: no paid APIs.
"""

from __future__ import annotations

import os

import structlog
from fastapi import FastAPI

from api.routers import (
    agents,
    auth,
    decisions,
    demo,
    firehose,
    orders,
    telemetry,
    topology,
)
from api.routers import metrics as metrics_router

try:
    from synapse_common.tracing import instrument_fastapi
except Exception:  # noqa: BLE001 — OTel optional

    def instrument_fastapi(app: FastAPI) -> None:  # type: ignore[misc]
        return None


logger = structlog.get_logger(__name__)

app = FastAPI(
    title="SYNAPSE API Gateway",
    version="1.0.0",
    description="Front door to the SYNAPSE multi-agent quick-commerce platform",
)

app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["decisions"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
# Also mount the JWKS endpoint at the standard RFC 8615 location.
app.include_router(auth.router, prefix="", tags=["auth"], include_in_schema=False)
# P2: per-agent metrics proxy + multiplexed Kafka firehose WS.
app.include_router(metrics_router.router, prefix="/api/v1/metrics", tags=["metrics"])
app.include_router(firehose.router, prefix="/ws", tags=["firehose"])
# P3: Neo4j supply network topology for Twin Lab.
app.include_router(topology.router, prefix="/api/v1", tags=["topology"])
# P4: demo runner + telemetry sink + CSP report endpoint.
app.include_router(demo.router, prefix="/api/v1/demo", tags=["demo"])
app.include_router(telemetry.router, prefix="/api/v1", tags=["telemetry"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "synapse-api"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {
        "status": "ready",
        "orchestrator": os.environ.get("SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085"),
    }


try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception as exc:  # noqa: BLE001
    logger.warning("prometheus_instrumentator_missing", error=str(exc))

instrument_fastapi(app)
