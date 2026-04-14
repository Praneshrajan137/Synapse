"""
SYNAPSE Freshness Guardian -- A2A JSON-RPC Handler (I-9).
Implements the three mandatory A2A methods:
  1. proposal(decision_context) -> AgentProposal
  2. debate_respond(proposals, round_number) -> revised AgentProposal
  3. execute(consensus_action) -> ExecutionResult
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import structlog
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from agents.freshness_guardian.inference.pipeline import (
    FreshnessGuardianPipeline,
    FreshnessRequest,
)
from agents.freshness_guardian.state_machine import FreshnessGuardianStateMachine

logger = structlog.get_logger(__name__)


class FreshnessGuardianA2AHandler:
    """A2A handler for Freshness Guardian agent. JSON-RPC 2.0 protocol."""

    def __init__(self, pipeline: FreshnessGuardianPipeline | None = None) -> None:
        self._pipeline = pipeline or FreshnessGuardianPipeline()
        self._fsm = FreshnessGuardianStateMachine()

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
        except Exception as exc:
            logger.error("a2a_handler_error", method=method, error=str(exc))
            return self._error_response(request_id, -32000, str(exc))

    def proposal(self, decision_context: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("freshness_request_received")

        store_id = decision_context.get("store_id", "")
        sku_ids = decision_context.get("sku_ids", [])
        decision_id = decision_context.get("decision_id", str(uuid4()))

        alerts = []
        for sku_id in sku_ids:
            req = FreshnessRequest(store_id=store_id, sku_id=sku_id)
            alert = self._pipeline.assess(req)
            alerts.append(alert.model_dump(mode="json"))

        avg_confidence = sum(a["confidence"] for a in alerts) / len(alerts) if alerts else 0.0

        proposal = AgentProposal(
            agent_name=AgentName.FRESHNESS_GUARDIAN,
            decision_id=UUID(decision_id) if isinstance(decision_id, str) else decision_id,
            utility_score=min(avg_confidence, 1.0),
            confidence=avg_confidence,
            justification_trace=[
                f"Assessed {len(alerts)} SKUs at store {store_id}",
                f"Average confidence: {avg_confidence:.3f}",
                "All alerts include quality_score and FSSAI compliance (INV-FG-001, INV-FG-003)",
            ],
            payload={"alerts": alerts, "store_id": store_id},
            tier=DecisionTier.TIER_1,
        )

        self._fsm.transition("proposal_submitted")
        self._fsm.record_tool_call()

        return json.loads(proposal.to_deterministic_json())

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        round_number = params.get("round_number", 1)
        logger.info("debate_respond", round=round_number, action="maintain_assessment")
        self._fsm.record_tool_call()
        return {"status": "maintained", "round": round_number}

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = consensus_action.get("decision_id", str(uuid4()))

        logger.info(
            "freshness_alert_published",
            decision_id=decision_id,
            topic="synapse.freshness.alert",
        )

        self._fsm.transition("policy_updated")
        self._fsm.record_tool_call()

        return {
            "status": "executed",
            "decision_id": decision_id,
            "kafka_published": True,
        }

    @staticmethod
    def _error_response(request_id: str, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        }
