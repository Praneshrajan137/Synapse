"""
SYNAPSE Pricing Oracle -- FastAPI Inference Server.
Endpoints: POST /price, GET /health, GET /metrics, POST /a2a
Port: 8005
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from synapse_common.model_registry import ModelRegistry

from agents.pricing_oracle.a2a.handler import PricingOracleA2AHandler
from agents.pricing_oracle.config import PricingOracleConfig
from agents.pricing_oracle.inference.pipeline import PricingOraclePipeline
from agents.pricing_oracle.inference.serving_model import (
    build_pricing_model,
    load_serving_model,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)

_pipeline: PricingOraclePipeline | None = None
_config: PricingOracleConfig | None = None
_a2a_handler: PricingOracleA2AHandler | None = None

ROOT = Path(__file__).resolve().parents[3]
# Where train.py writes the trained actor (pricing_maddpg.pt + .serving.json).
SERVING_CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"


def _build_pipeline() -> PricingOraclePipeline:
    """Resolve the trained MADDPG actor + elasticity model and wire them (C39).

    The $0 ModelRegistry source resolves the actor checkpoint; an injected builder
    reconstructs the actor (torch) + the torch-free LinearElasticityModel. Both are
    passed to the pipeline so a fully-loaded serve is non-degraded on the action AND
    the elasticity. With no checkpoint, both are None → honest rule-based fallback (I-7).
    """
    registry = ModelRegistry(
        None,
        checkpoint_dir=SERVING_CHECKPOINT_DIR,
        hf_repo=os.environ.get("PO_HF_REPO") or None,
        model_builder=build_pricing_model,
    )
    serving_model = load_serving_model(registry)
    causal = serving_model.elasticity if serving_model is not None else None
    return PricingOraclePipeline(model=serving_model, causal_estimator=causal)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline, _config, _a2a_handler
    _config = PricingOracleConfig()
    _pipeline = _build_pipeline()
    _a2a_handler = PricingOracleA2AHandler(pipeline=_pipeline)
    logger.info("server_started", port=_config.port, model_loaded=_pipeline._model is not None)
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
