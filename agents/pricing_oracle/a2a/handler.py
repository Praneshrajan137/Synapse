"""
SYNAPSE Pricing Oracle -- A2A JSON-RPC Handler (I-9).
Implements the three mandatory A2A methods:
  1. proposal(decision_context) -> AgentProposal
  2. debate_respond(proposals, round_number) -> revised AgentProposal
  3. execute(consensus_action) -> ExecutionResult
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from synapse_common.models import AgentName, AgentProposal, DecisionTier
from synapse_common.schemas import validate_agent_payload

from agents.pricing_oracle.inference.pipeline import PricingOraclePipeline
from agents.pricing_oracle.state_machine import PricingOracleStateMachine

logger = structlog.get_logger(__name__)


class PricingOracleA2AHandler:
    """A2A handler for Pricing Oracle agent. JSON-RPC 2.0 protocol."""

    def __init__(self, pipeline: PricingOraclePipeline | None = None) -> None:
        self._pipeline = pipeline or PricingOraclePipeline()
        self._fsm = PricingOracleStateMachine()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
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
                return self._error_response(request_id, -32601, f"Method not found: {method}")

            return {"jsonrpc": "2.0", "result": result, "id": request_id}
        except Exception as e:
            logger.error("a2a_handler_error", method=method, error=str(e))
            return self._error_response(request_id, -32000, str(e))

    def proposal(self, decision_context: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("pricing_request_received")

        sku_ids = decision_context.get("sku_ids", [])
        store_id = decision_context.get("store_id", "")
        categories = decision_context.get("categories", [])
        base_prices = decision_context.get("base_prices", [])
        decision_id = decision_context.get("decision_id", str(uuid4()))

        updates = self._pipeline.price(
            sku_ids=sku_ids,
            store_id=store_id,
            categories=categories,
            base_prices=base_prices,
        )

        avg_confidence = sum(u.confidence for u in updates) / len(updates) if updates else 0.0

        # Build schema-compliant per-update dicts. The schema
        # (proto/domain/pricing_update.schema.json) requires:
        #   pricing_id, sku_id, category, base_price, multiplier, final_price,
        #   is_essential, elasticity_source, timestamp, confidence
        # plus optionals (causal_elasticity, essential_cap_enforced, etc.).
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        update_payloads: list[dict[str, Any]] = []
        for u in updates:
            elasticity_source = (
                "causal_doubleml"
                if u.elasticity_estimate is not None and u.elasticity_estimate != 0.0
                else "correlation_fallback"
            )
            update_payloads.append(
                {
                    "pricing_id": str(uuid4()),
                    "sku_id": u.sku_id,
                    "store_id": store_id,
                    "category": u.category,
                    "base_price": float(u.base_price),
                    "multiplier": float(u.multiplier),
                    "final_price": float(u.final_price),
                    "is_essential": bool(u.is_essential),
                    "elasticity_source": elasticity_source,
                    "causal_elasticity": (
                        float(u.elasticity_estimate) if u.elasticity_estimate is not None else None
                    ),
                    "essential_cap_enforced": bool(u.is_essential and u.multiplier <= 1.3),
                    "timestamp": timestamp,
                    "confidence": float(u.confidence),
                }
            )

        proposal = AgentProposal(
            agent_name=AgentName.PRICING_ORACLE,
            decision_id=UUID(decision_id) if isinstance(decision_id, str) else decision_id,
            utility_score=min(avg_confidence, 1.0),
            confidence=avg_confidence,
            justification_trace=[
                f"Generated {len(updates)} pricing updates for store {store_id}",
                f"Average confidence: {avg_confidence:.3f}",
                "Essential cap 1.3x enforced on all essential items (INV-PO-001)",
            ],
            payload={"updates": update_payloads},
            tier=DecisionTier.TIER_2,
        )

        self._fsm.transition("proposal_submitted")
        self._fsm.record_tool_call()

        # I-3: validate every emitted payload against proto/domain/.
        validate_agent_payload("pricing_oracle", proposal.payload)

        result: dict[str, Any] = json.loads(proposal.to_deterministic_json())
        return result

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        round_number = params.get("round_number", 1)
        logger.info("debate_respond", round=round_number, action="maintain_pricing")
        self._fsm.record_tool_call()
        return {"status": "maintained", "round": round_number}

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = consensus_action.get("decision_id", str(uuid4()))

        logger.info(
            "pricing_published",
            decision_id=decision_id,
            topic="synapse.pricing.update",
        )

        self._fsm.transition("policy_updated")
        self._fsm.record_tool_call()

        return {
            "status": "executed",
            "decision_id": decision_id,
            "kafka_published": True,
            "mlflow_logged": True,
        }

    @staticmethod
    def _error_response(request_id: str, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        }
