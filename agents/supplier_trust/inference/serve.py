"""SYNAPSE Supplier Trust -- FastAPI Server. Port: 8007."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.supplier_trust.inference.pipeline import (
    SupplierTrustPipeline,
    TrustScoreResult,
)

logger = structlog.get_logger(__name__)
_pipeline: SupplierTrustPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline  # noqa: PLW0603
    _pipeline = SupplierTrustPipeline()
    logger.info("supplier_trust_started", port=8007)
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


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "healthy", "agent": "supplier_trust"}


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    return {
        "agent": "supplier_trust",
        "pipeline_loaded": _pipeline is not None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8007)
