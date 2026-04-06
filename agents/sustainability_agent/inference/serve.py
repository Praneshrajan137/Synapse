"""
SYNAPSE Sustainability Agent -- FastAPI Inference Server.
Endpoints: POST /report, GET /health, GET /metrics
Port: 8008
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from agents.sustainability_agent.config import SustainabilityAgentConfig
from agents.sustainability_agent.inference.pipeline import CarbonReport, SustainabilityPipeline

logger = structlog.get_logger(__name__)

_pipeline: SustainabilityPipeline | None = None
_config: SustainabilityAgentConfig | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline, _config
    _config = SustainabilityAgentConfig()
    _pipeline = SustainabilityPipeline(
        carbon_pareto_weight=_config.carbon_pareto_weight,
    )
    logger.info("server_started", port=_config.port)
    yield


app = FastAPI(
    title="SYNAPSE Sustainability Agent",
    version="1.0.0",
    description="Carbon footprint tracking, waste prediction, and ESG reporting",
    lifespan=lifespan,
)


class ReportRequest(BaseModel):
    """Request schema for sustainability report."""

    fuel_liters: float = Field(..., ge=0.0)
    distance_km: float = Field(..., ge=0.0)
    days_ahead: int = Field(default=7, ge=1)
    items_wasted: int = Field(default=0, ge=0)
    items_total: int = Field(default=100, ge=1)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    agent: str = "sustainability_agent"
    carbon_tracker_ready: bool
    waste_model_ready: bool


@app.post("/report", response_model=CarbonReport)
async def report(request: ReportRequest) -> CarbonReport:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        return _pipeline.report(
            fuel_liters=request.fuel_liters,
            distance_km=request.distance_km,
            days_ahead=request.days_ahead,
            items_wasted=request.items_wasted,
            items_total=request.items_total,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        carbon_tracker_ready=_pipeline is not None and _pipeline._carbon is not None,
        waste_model_ready=_pipeline is not None and _pipeline._waste is not None,
    )


@app.get("/metrics")
async def metrics() -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    import uvicorn

    config = SustainabilityAgentConfig()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
