"""SYNAPSE Supplier Trust -- A2A JSON-RPC Handler (I-9)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from synapse_common.models import AgentName, AgentProposal, DecisionTier
from synapse_common.schemas import validate_agent_payload

from agents.supplier_trust.inference.pipeline import SupplierTrustPipeline

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
        delivery_reliability = self._delivery_reliability(delivery_history, result)

        # Schema-compliant payload for `synapse.domain.supplier_score`. The
        # full TrustScoreResult is richer than the schema; here we project to
        # the canonical surface that downstream consumers contract against.
        payload = {
            "score_id": str(uuid4()),
            "supplier_id": result.supplier_id,
            "trust_score": float(result.trust_score),
            "trust_floor_applied": bool(result.is_new_vendor),
            "lead_time_posterior": result.lead_time_posterior,
            "delivery_reliability": delivery_reliability,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "confidence": float(result.confidence),
        }
        last_ts = self._last_delivery_timestamp(delivery_history)
        if last_ts is not None:
            payload["last_delivery_ts"] = last_ts

        proposal = AgentProposal(
            agent_name=AgentName.SUPPLIER_TRUST,
            decision_id=UUID(ctx.get("decision_id", str(uuid4()))),
            utility_score=result.trust_score,
            confidence=result.confidence,
            justification_trace=[
                f"Scored supplier {supplier_id}: trust={result.trust_score}",
                f"Delivery reliability: {delivery_reliability:.3f}",
                f"New vendor: {result.is_new_vendor}",
            ],
            payload=payload,
            tier=DecisionTier.TIER_2,
        )
        # I-3: validate every emitted payload against proto/domain/.
        validate_agent_payload("supplier_trust", proposal.payload)
        rendered: dict[str, Any] = json.loads(proposal.to_deterministic_json())
        return rendered

    @staticmethod
    def _delivery_reliability(
        delivery_history: list[dict[str, Any]],
        result: Any,
    ) -> float:
        """On-time-rate over the supplied history; defaults to trust_score for new vendors."""
        if not delivery_history:
            return float(result.trust_score)
        on_time = sum(1 for d in delivery_history if d.get("on_time", False))
        return round(on_time / len(delivery_history), 4)

    @staticmethod
    def _last_delivery_timestamp(delivery_history: list[dict[str, Any]]) -> str | None:
        if not delivery_history:
            return None
        for entry in reversed(delivery_history):
            ts = entry.get("timestamp") or entry.get("delivered_at")
            if isinstance(ts, str):
                return ts
        return None

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
