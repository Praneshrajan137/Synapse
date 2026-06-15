"""
SYNAPSE Digital Twin — FastAPI inference server.

Endpoints:
  POST /simulate — What-If API (INV-TW-004: 10s SLA for 1000 scenarios)
  GET  /health   — Liveness/readiness probe
  GET  /metrics  — Prometheus metrics
  POST /a2a      — A2A JSON-RPC 2.0 handler (I-9)

Port: 8009
"""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from digital_twin.config import TwinConfig
from digital_twin.simulation.what_if import ScenarioSpec, WhatIfEngine, WhatIfResult
from synapse_common.a2a_sdk import A2ARequest, A2AResponse, AgentCard
from synapse_common.metrics import TWIN_SIMULATION_LATENCY, TWIN_SIMULATION_TOTAL
from synapse_common.models import AgentName

logger = structlog.get_logger(__name__)

_config: TwinConfig | None = None
_engine: WhatIfEngine | None = None

AGENT_CARD = AgentCard(
    name="digital_twin",
    description="Supply chain digital twin — simulation, Monte Carlo, and What-If analysis",
    version="1.0.0",
    url="http://digital-twin:8009",
    capabilities=["simulate", "monte_carlo", "what_if", "divergence_check"],
    supported_methods=["simulate", "monte_carlo", "health"],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _config, _engine
    _config = TwinConfig()
    _engine = WhatIfEngine(config=_config)
    logger.info("twin_server_started", port=_config.port)
    yield
    logger.info("twin_server_shutdown")


app = FastAPI(
    title="SYNAPSE Digital Twin",
    version="1.0.0",
    description="Supply chain digital twin with What-If scenario analysis",
    lifespan=lifespan,
)


class SimulateRequest(BaseModel):
    """Request schema for the What-If API."""

    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    demand_multiplier: float = Field(default=1.0, gt=0.0, le=5.0)
    lead_time_multiplier: float = Field(default=1.0, gt=0.0, le=5.0)
    failure_rate_multiplier: float = Field(default=1.0, ge=0.0, le=10.0)
    spoilage_rate_multiplier: float = Field(default=1.0, ge=0.0, le=10.0)
    n_scenarios: int = Field(default=1000, ge=1000)
    duration_hours: float = Field(default=4.0, gt=0.0)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    agent: str = "digital_twin"
    engine_ready: bool
    uptime_seconds: float


_start_time: float = time.monotonic()


@app.post("/simulate", response_model=WhatIfResult)
async def simulate(request: SimulateRequest) -> WhatIfResult:
    """What-If API endpoint. INV-TW-004: 10s SLA for 1000 scenarios."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    spec = ScenarioSpec(
        name=request.name,
        description=request.description,
        demand_multiplier=request.demand_multiplier,
        lead_time_multiplier=request.lead_time_multiplier,
        failure_rate_multiplier=request.failure_rate_multiplier,
        spoilage_rate_multiplier=request.spoilage_rate_multiplier,
        n_scenarios=request.n_scenarios,
        duration_hours=request.duration_hours,
    )

    try:
        result = _engine.simulate(spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return result


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        engine_ready=_engine is not None,
        uptime_seconds=round(time.monotonic() - _start_time, 1),
    )


@app.get("/metrics")
async def metrics() -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/a2a")
async def a2a_handler(request: A2ARequest) -> A2AResponse:
    """A2A JSON-RPC 2.0 endpoint (I-9)."""
    if request.method == "simulate" and _engine is not None:
        # PR-3: time + count every simulation by outcome. A cascade of twin
        # failures used to be invisible (no metric, no error log).
        start = time.monotonic()
        outcome = "ok"
        try:
            spec = ScenarioSpec(**request.params)
            result = _engine.simulate(spec)
            return A2AResponse(
                id=request.id,
                result=result.model_dump(mode="json"),
            )
        except (ValueError, TypeError) as e:
            outcome = "bad_request"
            return A2AResponse(
                id=request.id,
                error={"code": -32602, "message": str(e)},
            )
        finally:
            TWIN_SIMULATION_LATENCY.labels(method="simulate").observe(time.monotonic() - start)
            TWIN_SIMULATION_TOTAL.labels(method="simulate", outcome=outcome).inc()

    if request.method == "monte_carlo":
        # C7 (ADR-043): the orchestrator verifies a Tier-4 action against the twin's
        # Monte-Carlo what-if. Returns a MonteCarloOutput (consumer contract in
        # orchestrator/contracts/twin_simulation_contract.py). Honest failure on a
        # bad request or sim error — never a 500 that breaks the A2A envelope.
        start = time.monotonic()
        outcome = "ok"
        try:
            from digital_twin.simulation.monte_carlo import MonteCarloRunner

            n = int(request.params.get("n_scenarios", 1000))
            output = MonteCarloRunner().run_scenarios(n=n)
            return A2AResponse(id=request.id, result=output.to_dict())
        except (ValueError, TypeError) as e:
            outcome = "bad_request"
            return A2AResponse(id=request.id, error={"code": -32602, "message": str(e)})
        except Exception as e:  # noqa: BLE001 — sim/engine failure degrades (I-7)
            outcome = "error"
            # PR-3: was fully silent (no log, no metric). Surface it.
            logger.error("twin_monte_carlo_failed", error=str(e))
            return A2AResponse(
                id=request.id, error={"code": -32000, "message": f"monte_carlo failed: {e}"}
            )
        finally:
            TWIN_SIMULATION_LATENCY.labels(method="monte_carlo").observe(time.monotonic() - start)
            TWIN_SIMULATION_TOTAL.labels(method="monte_carlo", outcome=outcome).inc()

    if request.method == "health":
        return A2AResponse(
            id=request.id,
            result={"status": "healthy", "engine_ready": _engine is not None},
        )

    if request.method == "agent_card":
        return A2AResponse(
            id=request.id,
            result=AGENT_CARD.model_dump(mode="json"),
        )

    return A2AResponse(
        id=request.id,
        error={"code": -32601, "message": f"Method not found: {request.method}"},
    )


def main() -> None:
    import uvicorn

    config = TwinConfig()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
