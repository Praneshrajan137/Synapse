"""SYNAPSE Inventory Sentinel -- FastAPI Server. Port: 8003."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from synapse_common.model_registry import ModelRegistry
from synapse_common.models import InventoryAction

from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline
from agents.inventory_sentinel.inference.serving_model import (
    build_inventory_model,
    load_serving_model,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)
_pipeline: InventorySentinelPipeline | None = None

ROOT = Path(__file__).resolve().parents[3]
SERVING_CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline
    registry = ModelRegistry(
        None,
        checkpoint_dir=SERVING_CHECKPOINT_DIR,
        hf_repo=os.environ.get("IS_HF_REPO") or None,
        model_builder=build_inventory_model,
    )
    serving_model = load_serving_model(registry)
    _pipeline = InventorySentinelPipeline(serving_model=serving_model)
    logger.info("inventory_sentinel_started", port=8003, model_loaded=serving_model is not None)
    yield


app = FastAPI(title="SYNAPSE Inventory Sentinel", version="1.0.0", lifespan=lifespan)


class ReorderRequest(BaseModel):
    sku_ids: list[str] = Field(..., min_length=1, max_length=1000)
    store_id: str = Field(..., min_length=1)


class ReorderResponse(BaseModel):
    actions: list[InventoryAction]
    count: int


@app.post("/reorder", response_model=ReorderResponse)
async def reorder(req: ReorderRequest) -> ReorderResponse:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    actions = _pipeline.decide(req.sku_ids, req.store_id)
    return ReorderResponse(actions=actions, count=len(actions))


@app.post("/a2a")
async def handle_a2a(request: dict[str, object]) -> dict[str, object]:
    """A2A JSON-RPC handler for Orchestrator consensus (mirrors freshness_guardian)."""
    from agents.inventory_sentinel.a2a.handler import InventorySentinelA2AHandler

    handler = InventorySentinelA2AHandler(_pipeline)
    return handler.handle_request(request)  # type: ignore[arg-type]


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "healthy", "agent": "inventory_sentinel"}
