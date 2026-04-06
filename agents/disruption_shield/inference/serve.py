"""
SYNAPSE Disruption Shield -- FastAPI Inference Server.
Endpoints: POST /detect, GET /health, GET /metrics, POST /a2a
Port: 8006
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from agents.disruption_shield.config import DisruptionShieldConfig
from agents.disruption_shield.inference.pipeline import (
    DisruptionAlert,
    DisruptionRequest,
    DisruptionShieldPipeline,
)

logger = structlog.get_logger(__name__)

_pipeline: DisruptionShieldPipeline | None = None
_config: DisruptionShieldConfig | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline, _config
    _config = DisruptionShieldConfig()
    _pipeline = DisruptionShieldPipeline(config=_config)
    logger.info("server_started", port=_config.port)
    yield


app = FastAPI(
    title="SYNAPSE Disruption Shield",
    version="1.0.0",
    description="Supply chain disruption detection via anomaly ensemble, reasoning, and playbook retrieval",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, object]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "disruption_shield",
        "version": "1.0.0",
        "pipeline_loaded": _pipeline is not None,
    }


@app.post("/detect", response_model=DisruptionAlert)
async def detect_disruption(request: DisruptionRequest) -> DisruptionAlert:
    """Run disruption detection pipeline on supply chain signals."""
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        result = _pipeline.detect(request)
        logger.info(
            "disruption_detected",
            alert_level=result.alert_level,
            ensemble_score=result.ensemble_score,
            anomalous_nodes=len(result.anomalous_nodes),
            severity=result.severity,
        )
        return result
    except Exception as exc:
        logger.error("disruption_detection_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/a2a")
async def handle_a2a(request: dict[str, object]) -> dict[str, object]:
    """A2A JSON-RPC handler for Orchestrator consensus."""
    from agents.disruption_shield.a2a.handler import DisruptionShieldA2AHandler

    handler = DisruptionShieldA2AHandler(_pipeline)
    return handler.handle_request(request)  # type: ignore[arg-type]


@app.get("/metrics")
async def metrics() -> Response:
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    import uvicorn

    config = DisruptionShieldConfig()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
