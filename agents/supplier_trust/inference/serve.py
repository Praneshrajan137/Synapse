"""SYNAPSE Supplier Trust -- FastAPI Server. Port: 8007."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from synapse_common.kafka_client import KafkaConfig, SynapseProducer
from synapse_common.model_registry import ModelRegistry

from agents.supplier_trust.inference.pipeline import (
    SupplierTrustPipeline,
    TrustScoreResult,
)
from agents.supplier_trust.inference.serving_model import (
    build_supplier_model,
    load_serving_model,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)
_pipeline: SupplierTrustPipeline | None = None
_producer: SynapseProducer | None = None

ROOT = Path(__file__).resolve().parents[3]
# Where train.py writes the SVI-fitted lead-time prior (supplier_bayesian.pt + sidecar).
SERVING_CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"


def _build_pipeline() -> SupplierTrustPipeline:
    """Resolve the SVI-fitted lead-time prior and wire it (C39, ADR-043).

    The $0 ModelRegistry source resolves the prior checkpoint; an injected builder
    turns it into a torch-free conjugate SupplierServingModel. With no checkpoint
    the serving model is None and scoring takes the per-call SVI fit fallback (I-7).
    """
    registry = ModelRegistry(
        None,
        checkpoint_dir=SERVING_CHECKPOINT_DIR,
        hf_repo=os.environ.get("ST_HF_REPO") or None,
        model_builder=build_supplier_model,
    )
    serving_model = load_serving_model(registry)
    return SupplierTrustPipeline(serving_model=serving_model)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline, _producer  # noqa: PLW0603
    _pipeline = _build_pipeline()
    # ADR-052: producer so execute() publishes the ratified score for real (guarded, I-7).
    try:
        _producer = SynapseProducer(
            KafkaConfig(bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"))
        )
    except Exception as exc:  # noqa: BLE001 — honest degradation (I-7)
        logger.warning("kafka_producer_unavailable", error=str(exc))
        _producer = None
    logger.info(
        "supplier_trust_started",
        port=8007,
        calibrated=_pipeline._serving_model is not None,
    )
    yield
    logger.info("supplier_trust_shutdown")


app = FastAPI(title="SYNAPSE Supplier Trust", version="1.0.0", lifespan=lifespan)


class ScoreRequest(BaseModel):
    supplier_id: str = Field(..., min_length=1)
    delivery_history: list[dict[str, Any]] = Field(default_factory=list)
    is_new_vendor: bool = Field(default=False)


class LeadTimePosteriorResponse(BaseModel):
    mean_days: float
    std_days: float
    p10_days: float
    p90_days: float


class ScoreResponse(BaseModel):
    supplier_id: str
    trust_score: float
    confidence: float
    lead_time_posterior: LeadTimePosteriorResponse
    is_new_vendor: bool


@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest) -> ScoreResponse:
    """Score a supplier's trustworthiness."""
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    result: TrustScoreResult = _pipeline.score(
        supplier_id=req.supplier_id,
        delivery_history=req.delivery_history,
        is_new_vendor=req.is_new_vendor,
    )
    return ScoreResponse(
        supplier_id=result.supplier_id,
        trust_score=result.trust_score,
        confidence=result.confidence,
        lead_time_posterior=LeadTimePosteriorResponse(**result.lead_time_posterior),
        is_new_vendor=result.is_new_vendor,
    )


@app.post("/a2a")
async def handle_a2a(request: dict[str, object]) -> dict[str, object]:
    """A2A JSON-RPC handler for Orchestrator consensus (mirrors freshness_guardian)."""
    from agents.supplier_trust.a2a.handler import SupplierTrustA2AHandler

    handler = SupplierTrustA2AHandler(_pipeline, kafka_producer=_producer)
    return handler.handle_request(request)  # type: ignore[arg-type]


@app.get("/health")
async def health() -> dict[str, Any]:
    # Honest readiness (P1.1): 503 when the pipeline never initialised.
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="pipeline not initialised")
    return {"status": "healthy", "agent": "supplier_trust", "pipeline_loaded": True}


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    return {
        "agent": "supplier_trust",
        "pipeline_loaded": _pipeline is not None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8007)
