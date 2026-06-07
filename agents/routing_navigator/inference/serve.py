"""SYNAPSE Routing Navigator -- FastAPI Inference Server. Port: 8002."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from synapse_common.models import RoutePlan

from agents.routing_navigator.inference.pipeline import RoutingNavigatorPipeline

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)
_pipeline: RoutingNavigatorPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline
    _pipeline = RoutingNavigatorPipeline()
    logger.info("routing_navigator_started", port=8002)
    yield


app = FastAPI(title="SYNAPSE Routing Navigator", version="1.0.0", lifespan=lifespan)


class RouteRequest(BaseModel):
    orders: list[dict[str, Any]] = Field(..., min_length=1, max_length=200)
    riders: list[dict[str, Any]] = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    use_student: bool = Field(default=True)


class RouteResponse(BaseModel):
    routes: list[RoutePlan]
    count: int
    latency_ms: float | None = None


@app.post("/route", response_model=RouteResponse)
async def route(request: RouteRequest) -> RouteResponse:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    start = time.monotonic()
    try:
        routes = _pipeline.route(
            request.orders, request.riders, request.store_id, request.use_student
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        return RouteResponse(routes=routes, count=len(routes), latency_ms=round(elapsed_ms, 1))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/a2a")
async def handle_a2a(request: dict[str, object]) -> dict[str, object]:
    """A2A JSON-RPC handler for Orchestrator consensus (mirrors freshness_guardian)."""
    from agents.routing_navigator.a2a.handler import RoutingNavigatorA2AHandler

    handler = RoutingNavigatorA2AHandler(_pipeline)
    return handler.handle_request(request)  # type: ignore[arg-type]


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "agent": "routing_navigator",
        "model_loaded": _pipeline is not None,
    }
