"""SYNAPSE Inventory Sentinel -- FastAPI Server. Port: 8003."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from synapse_common.models import InventoryAction

from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)
_pipeline: InventorySentinelPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _pipeline
    _pipeline = InventorySentinelPipeline()
    logger.info("inventory_sentinel_started", port=8003)
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


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "healthy", "agent": "inventory_sentinel"}
