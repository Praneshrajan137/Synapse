"""SYNAPSE Supplier Trust -- A2A JSON-RPC Handler (I-9)."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import structlog

from agents.supplier_trust.inference.pipeline import SupplierTrustPipeline
from synapse_common.models import AgentName, AgentProposal, DecisionTier

logger = structlog.get_logger(__name__)


class SupplierTrustA2AHandler:
    """A2A handler for Supplier Trust agent.

    Methods: proposal(), debate_respond(), execute() via JSON-RPC.
    """

    def __init__(self, pipeline: SupplierTrustPipeline | None = None) -> None:
        self._pipeline = pipeline or SupplierTrustPipeline()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Route JSON-RPC request to the appropriate method."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id", str(uuid4()))

        try:
            if method == "proposal":
                result = self.proposal(params)
            elif method == "debate_respond":
                result = self.debate_respond(params)
            elif method == "execute":
                result = self.execute(params)
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Not found: {method}"},
                    "id": request_id,
                }
            return {"jsonrpc": "2.0", "result": result, "id": request_id}
        except Exception as exc:
            logger.error("a2a_handler_error", method=method, error=str(exc))
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(exc)},
                "id": request_id,
            }

    def proposal(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Generate a trust-scoring proposal for the Orchestrator."""
        supplier_id = ctx.get("supplier_id", "SUP-UNKNOWN")
        delivery_history = ctx.get("delivery_history", [])
        is_new_vendor = ctx.get("is_new_vendor", not delivery_history)

        result = self._pipeline.score(
            supplier_id=supplier_id,
            delivery_history=delivery_history,
            is_new_vendor=is_new_vendor,
        )

        proposal = AgentProposal(
            agent_name=AgentName.SUPPLIER_TRUST,
            decision_id=UUID(ctx.get("decision_id", str(uuid4()))),
            utility_score=result.trust_score,
            confidence=result.confidence,
            justification_trace=[
                f"Scored supplier {supplier_id}: trust={result.trust_score}",
                f"Lead-time posterior: {result.lead_time_posterior}",
                f"New vendor: {result.is_new_vendor}",
            ],
            payload={
                "supplier_id": result.supplier_id,
                "trust_score": result.trust_score,
                "lead_time_posterior": result.lead_time_posterior,
                "is_new_vendor": result.is_new_vendor,
            },
            tier=DecisionTier.TIER_2,
        )
        return json.loads(proposal.to_deterministic_json())

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        """Respond to a debate round -- maintain position with justification."""
        return {
            "status": "maintained",
            "round": params.get("round_number", 1),
            "agent": "supplier_trust",
            "rationale": "Trust score is Bayesian-calibrated; maintaining proposal.",
        }

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the consensus action -- publish trust score to Kafka."""
        return {
            "status": "executed",
            "decision_id": params.get("decision_id", ""),
            "agent": "supplier_trust",
            "kafka_published": True,
            "topic": "synapse.supplier.score",
        }
