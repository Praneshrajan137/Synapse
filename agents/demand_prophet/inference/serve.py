"""
SYNAPSE Demand Prophet -- FastAPI Inference Server.
Endpoints: POST /predict, GET /health, GET /metrics
Port: 8001
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from synapse_common.model_registry import ModelRegistry
from synapse_common.models import DemandForecast

from agents.demand_prophet.config import DemandProphetConfig
from agents.demand_prophet.inference.pipeline import DemandProphetPipeline
from agents.demand_prophet.inference.serving_model import (
    build_demand_prophet_model,
    load_serving_model,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)

_pipeline: DemandProphetPipeline | None = None
_config: DemandProphetConfig | None = None


ROOT = Path(__file__).resolve().parents[3]
# Where train.py writes the serving artifact (``{name}.pt`` + ``{name}.serving.json``).
SERVING_CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"


def _build_model_registry(config: DemandProphetConfig) -> ModelRegistry:
    """Construct the registry with a lineage path AND a $0 serving path (ADR-043).

    Lineage: a reachable MLflow tracking server yields an ``MlflowClient``.
    Serving ($0): a checkpoint resolved from the local ``artifacts/checkpoints``
    dir and/or an HF Hub repo (``DP_HF_REPO``), built into a concrete model by
    :func:`build_demand_prophet_model`. With neither reachable, every ``load``
    returns a degraded handle and serving falls back to the honest EMA path (I-7).
    """
    # Bound the HTTP timeout so an unreachable tracking server fails fast and
    # serving degrades within seconds instead of blocking startup (the MlflowClient
    # otherwise retries with a long default). Honest I-7 degradation needs to be
    # *prompt*, not just eventual.
    import os  # noqa: PLC0415

    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "3")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
    hf_repo = os.environ.get("DP_HF_REPO") or None
    client = None
    try:
        from mlflow.tracking import MlflowClient  # noqa: PLC0415

        client = MlflowClient(tracking_uri=config.mlflow_tracking_uri)
    except Exception as exc:  # noqa: BLE001 — MLflow absent/unreachable degrades (I-7)
        logger.warning("mlflow_unavailable", error=str(exc), fallback="checkpoint/EMA serving")
    return ModelRegistry(
        client,
        tracking_uri=config.mlflow_tracking_uri,
        checkpoint_dir=SERVING_CHECKPOINT_DIR,
        hf_repo=hf_repo,
        model_builder=build_demand_prophet_model,
    )


def _build_pipeline(config: DemandProphetConfig) -> DemandProphetPipeline:
    """Resolve the trained model (which carries its fitted calibrator) and wire it.

    This is the C39 serving-truth path: serving resolves a real checkpoint via
    ModelRegistry instead of always constructing ``model=None``. The calibrator is
    restored *fitted* from the checkpoint sidecar and travels on the serving model
    (ADR-043) — no unfit calibrator is ever constructed (the latent-500 fix). Any
    failure degrades to the honest fallback rather than taking the agent down (I-7).
    """
    registry = _build_model_registry(config)
    model = load_serving_model(registry, city=getattr(config, "city", "bengaluru"))
    calibrator = getattr(model, "calibrator", None) if model is not None else None
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
