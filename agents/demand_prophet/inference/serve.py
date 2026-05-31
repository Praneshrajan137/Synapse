"""
SYNAPSE Demand Prophet -- FastAPI Inference Server.
Endpoints: POST /predict, GET /health, GET /metrics
Port: 8001
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from synapse_common.model_registry import ModelRegistry
from synapse_common.models import DemandForecast

from agents.demand_prophet.config import DemandProphetConfig
from agents.demand_prophet.inference.pipeline import DemandProphetPipeline
from agents.demand_prophet.inference.serving_model import load_serving_model

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)

_pipeline: DemandProphetPipeline | None = None
_config: DemandProphetConfig | None = None


def _build_model_registry(config: DemandProphetConfig) -> ModelRegistry:
    """Construct the MLflow-backed registry. Never raises — degrades (I-7, ADR-041).

    A reachable MLflow tracking server yields an ``MlflowClient``; otherwise the
    registry is constructed with ``mlflow_client=None`` and every ``load`` returns
    a degraded handle, so serving falls back to the honest EMA path.
    """
    # Bound the HTTP timeout so an unreachable tracking server fails fast and
    # serving degrades within seconds instead of blocking startup (the MlflowClient
    # otherwise retries with a long default). Honest I-7 degradation needs to be
    # *prompt*, not just eventual.
    import os  # noqa: PLC0415

    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "3")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
    try:
        from mlflow.tracking import MlflowClient  # noqa: PLC0415

        client = MlflowClient(tracking_uri=config.mlflow_tracking_uri)
        return ModelRegistry(client, tracking_uri=config.mlflow_tracking_uri)
    except Exception as exc:  # noqa: BLE001 — MLflow absent/unreachable degrades (I-7)
        logger.warning("mlflow_unavailable", error=str(exc), fallback="degraded serving")
        return ModelRegistry(None)


def _build_pipeline(config: DemandProphetConfig) -> DemandProphetPipeline:
    """Load the trained model + conformal calibrator and wire the real pipeline.

    This is the C39 serving-truth path: serving now resolves a real checkpoint via
    ModelRegistry instead of always constructing ``model=None``. Any failure along
    the way degrades to the honest fallback rather than taking the agent down (I-7).
    """
    registry = _build_model_registry(config)
    model = load_serving_model(registry, city=getattr(config, "city", "bengaluru"))
    calibrator = None
    if model is not None:
        try:
            from agents.demand_prophet.training.conformal import (  # noqa: PLC0415
                ConformalCalibrator,
            )

            calibrator = ConformalCalibrator(
                alpha=config.conformal_alpha,
                coverage_target=config.conformal_coverage_target,
            )
        except Exception as exc:  # noqa: BLE001 — calibrator optional; serve point+raw band
            logger.warning("calibrator_init_failed", error=str(exc))
            calibrator = None
    return DemandProphetPipeline(model=model, conformal_calibrator=calibrator)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline, _config
    _config = DemandProphetConfig()
    _pipeline = _build_pipeline(_config)
    logger.info(
        "server_started",
        port=_config.port,
        model_loaded=_pipeline._model is not None,
    )
    yield


app = FastAPI(
    title="SYNAPSE Demand Prophet",
    version="1.0.0",
    description="Multi-horizon demand forecasting with conformal prediction intervals",
    lifespan=lifespan,
)


class PredictRequest(BaseModel):
    """Request schema for demand forecast."""

    sku_ids: list[str] = Field(..., min_length=1, max_length=500)
    store_id: str = Field(..., min_length=1)
    horizons: list[str] | None = Field(default=None)
    include_uncertainty: bool = Field(default=True)


class PredictResponse(BaseModel):
    """Response schema for demand forecast."""

    forecasts: list[DemandForecast]
    count: int
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    agent: str = "demand_prophet"
    model_loaded: bool
    feast_connected: bool
    neo4j_connected: bool


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    import time

    start = time.monotonic()

    try:
        horizons = set(request.horizons) if request.horizons else None
        forecasts = _pipeline.predict(
            sku_ids=request.sku_ids,
            store_id=request.store_id,
            horizons=horizons,
            include_uncertainty=request.include_uncertainty,
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        return PredictResponse(
            forecasts=forecasts,
            count=len(forecasts),
            latency_ms=round(elapsed_ms, 1),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        model_loaded=_pipeline is not None and _pipeline._model is not None,
        feast_connected=_pipeline is not None and _pipeline._feast is not None,
        neo4j_connected=_pipeline is not None and _pipeline._neo4j is not None,
    )


@app.get("/metrics")
async def metrics() -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    import uvicorn

    config = DemandProphetConfig()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
