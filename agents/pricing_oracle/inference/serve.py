"""
SYNAPSE Pricing Oracle -- FastAPI Inference Server.
Endpoints: POST /price, GET /health, GET /metrics, POST /a2a
Port: 8005
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from agents.pricing_oracle.a2a.handler import PricingOracleA2AHandler
from agents.pricing_oracle.config import PricingOracleConfig
from agents.pricing_oracle.inference.pipeline import PricingOraclePipeline

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)

_pipeline: PricingOraclePipeline | None = None
_config: PricingOracleConfig | None = None
_a2a_handler: PricingOracleA2AHandler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline, _config, _a2a_handler
    _config = PricingOracleConfig()
    _pipeline = PricingOraclePipeline()
    _a2a_handler = PricingOracleA2AHandler(pipeline=_pipeline)
    logger.info("server_started", port=_config.port)
    yield


app = FastAPI(
    title="SYNAPSE Pricing Oracle",
    version="1.0.0",
    description="Multi-agent RL pricing with essential cap enforcement and causal elasticity",
    lifespan=lifespan,
)


class PriceRequest(BaseModel):
    """Request schema for pricing optimization."""

    sku_ids: list[str] = Field(..., min_length=1, max_length=200)
    store_id: str = Field(..., min_length=1)
    categories: list[str] = Field(..., min_length=1)
    base_prices: list[float] = Field(..., min_length=1)
    demand_forecasts: list[float] | None = Field(default=None)


class PriceResponse(BaseModel):
    """Response schema for pricing optimization."""

    updates: list[dict[str, Any]]
    count: int
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    agent: str = "pricing_oracle"
    model_loaded: bool
    causal_fitted: bool
    feast_connected: bool
    neo4j_connected: bool


@app.post("/price", response_model=PriceResponse)
async def price(request: PriceRequest) -> PriceResponse:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    import time

    start = time.monotonic()

    try:
        updates = _pipeline.price(
            sku_ids=request.sku_ids,
            store_id=request.store_id,
            categories=request.categories,
            base_prices=request.base_prices,
            demand_forecasts=request.demand_forecasts,
        )
        elapsed_ms = (time.monotonic() - start) * 1000

        update_dicts = [
            {
                "sku_id": u.sku_id,
                "store_id": u.store_id,
                "category": u.category,
                "is_essential": u.is_essential,
                "base_price": u.base_price,
                "multiplier": u.multiplier,
                "final_price": u.final_price,
                "elasticity_estimate": u.elasticity_estimate,
                "confidence": u.confidence,
                "justification_trace": u.justification_trace,
            }
            for u in updates
        ]

        return PriceResponse(
            updates=update_dicts,
            count=len(updates),
            latency_ms=round(elapsed_ms, 1),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        model_loaded=_pipeline is not None and _pipeline._model is not None,
        causal_fitted=_pipeline is not None and _pipeline._causal is not None,
        feast_connected=_pipeline is not None and _pipeline._feast is not None,
        neo4j_connected=_pipeline is not None and _pipeline._neo4j is not None,
    )


@app.get("/metrics")
async def metrics() -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/a2a")
async def a2a(request: dict[str, Any]) -> dict[str, Any]:
    if _a2a_handler is None:
        raise HTTPException(status_code=503, detail="A2A handler not initialized")
    return _a2a_handler.handle_request(request)


def main() -> None:
    import uvicorn

    config = PricingOracleConfig()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
