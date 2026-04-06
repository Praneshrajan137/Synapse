"""
SYNAPSE Freshness Guardian -- FastAPI Inference Server.
Endpoints: POST /freshness, GET /health, GET /metrics, POST /a2a
Port: 8004
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from agents.freshness_guardian.config import FreshnessGuardianConfig
from agents.freshness_guardian.inference.pipeline import (
    FreshnessAlert,
    FreshnessGuardianPipeline,
    FreshnessRequest,
)

logger = structlog.get_logger(__name__)

_pipeline: FreshnessGuardianPipeline | None = None
_config: FreshnessGuardianConfig | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline, _config
    _config = FreshnessGuardianConfig()
    _pipeline = FreshnessGuardianPipeline()
    logger.info("server_started", port=_config.port)
    yield


app = FastAPI(
    title="SYNAPSE Freshness Guardian",
    version="1.0.0",
    description="Perishable inventory shelf life monitoring with FSSAI compliance",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, object]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "freshness_guardian",
        "version": "1.0.0",
        "model_loaded": _pipeline is not None,
    }


@app.post("/freshness", response_model=FreshnessAlert)
async def assess_freshness(request: FreshnessRequest) -> FreshnessAlert:
    """Assess freshness of a perishable SKU at a store."""
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        result = _pipeline.assess(request)
        logger.info(
            "freshness_assessed",
            store=request.store_id,
            sku=request.sku_id,
            quality=result.quality_score,
            markdown=result.markdown_pct,
            fssai=result.fssai_compliant,
        )
        return result
    except Exception as exc:
        logger.error("freshness_assessment_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/a2a")
async def handle_a2a(request: dict[str, object]) -> dict[str, object]:
    """A2A JSON-RPC handler for Orchestrator consensus."""
    from agents.freshness_guardian.a2a.handler import FreshnessGuardianA2AHandler

    handler = FreshnessGuardianA2AHandler(_pipeline)
    return handler.handle_request(request)  # type: ignore[arg-type]


@app.get("/metrics")
async def metrics() -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    import uvicorn

    config = FreshnessGuardianConfig()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
