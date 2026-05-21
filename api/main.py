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

from api.middleware.session import SessionMiddleware
from api.routers import agents, audit, auth, decisions, orders, rum, sse

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

# BFF session resolver. Runs before routers; gates protected paths and stashes
# session payload on request.state.session. See api/middleware/session.py
# and ADR-027 (BFF cookie session over JWT-in-memory).
app.add_middleware(SessionMiddleware)

# Atlas Console BFF auth. Login / logout / refresh / session / reauth.
# Path-prefixed at /auth/* (PUBLIC in SessionMiddleware so login itself is
# reachable without a session).
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# Atlas Console SSE bridge — Kafka topic tail. Plan §11/B1.
# Protected by SessionMiddleware (path starts with /api/v1/stream/).
app.include_router(sse.router, prefix="/api/v1/stream", tags=["stream"])

app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["decisions"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])

# Audit Vault — deterministic PDF evidence pack (plan §5.6 / S5).
# Protected by SessionMiddleware (PROTECTED_PREFIXES already covers
# /api/v1/audit). The export endpoint is byte-deterministic so two
# pulls of the same decision_id are identical for FSSAI / DPDPA.
app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])

# RUM ingest (web-vitals beacon + CSP report-to). Public — browser can
# beacon before login. Plan §11/B4 + B7. See SessionMiddleware PUBLIC list.
app.include_router(rum.router, prefix="/api/v1/rum", tags=["rum"])


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
