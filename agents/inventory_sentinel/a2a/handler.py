"""SYNAPSE Inventory Sentinel -- A2A JSON-RPC Handler (I-9)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import structlog
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline

logger = structlog.get_logger(__name__)


class InventorySentinelA2AHandler:
    """A2A handler for Inventory Sentinel agent."""

    def __init__(self, pipeline: InventorySentinelPipeline | None = None) -> None:
        self._pipeline = pipeline or InventorySentinelPipeline()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id", str(uuid4()))
        try:
            if method == "proposal":
                result = self.proposal(params)
            elif method == "debate_respond":
                result = {"status": "maintained", "round": params.get("round_number", 1)}
            elif method == "execute":
                result = {
                    "status": "executed",
                    "decision_id": params.get("decision_id", ""),
                    "kafka_published": True,
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Not found: {method}"},
                    "id": request_id,
                }
            return {"jsonrpc": "2.0", "result": result, "id": request_id}
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": request_id,
            }

    def proposal(self, ctx: dict[str, Any]) -> dict[str, Any]:
        sku_ids = ctx.get("sku_ids", ["SKU001"])
        store_id = ctx.get("store_id", "STORE_BLR_001")
        actions = self._pipeline.decide(sku_ids, store_id)
        proposal = AgentProposal(
            agent_name=AgentName.INVENTORY_SENTINEL,
            decision_id=UUID(ctx.get("decision_id", str(uuid4()))),
            utility_score=0.85,
            confidence=0.8,
            justification_trace=[f"Generated {len(actions)} inventory actions"],
            payload={"actions": [a.model_dump(mode="json") for a in actions]},
            tier=DecisionTier.TIER_2,
        )
        return json.loads(proposal.to_deterministic_json())
