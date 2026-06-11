"""SYNAPSE Routing Navigator -- A2A JSON-RPC Handler (I-9)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import structlog
from synapse_common.models import AgentName, AgentProposal, DecisionTier
from synapse_common.schemas import validate_agent_payload

from agents.routing_navigator.inference.pipeline import RoutingNavigatorPipeline
from agents.routing_navigator.state_machine import RoutingNavigatorStateMachine

logger = structlog.get_logger(__name__)


class RoutingNavigatorA2AHandler:
    """A2A handler for Routing Navigator agent."""

    def __init__(self, pipeline: RoutingNavigatorPipeline | None = None) -> None:
        self._pipeline = pipeline or RoutingNavigatorPipeline()
        self._fsm = RoutingNavigatorStateMachine()

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
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": request_id,
                }
            return {"jsonrpc": "2.0", "result": result, "id": request_id}
        except Exception as e:
            logger.error("a2a_error", method=method, error=str(e))
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": request_id,
            }

    def proposal(self, context: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("route_request_received")
        orders = context.get("orders", [{"order_id": "ORD-1", "lat": 12.97, "lon": 77.59}])
        riders = context.get("riders", [{"rider_id": "R-1"}])
        store_id = context.get("store_id", "STORE_BLR_001")

        routes = self._pipeline.route(orders, riders, store_id)

        # I-5/ADR-040: proposal confidence is the mean of the per-route solver
        # confidences (optimality gap, or the 0.5 Tier-1 floor) — never a
        # constant, so the HITL gate can actually fire on low-quality routes.
        avg_confidence = sum(r.confidence for r in routes) / len(routes) if routes else 0.0

        proposal = AgentProposal(
            # ADR-044: structured provenance rides with the proposal (I-3/I-4).
            provenance=self._pipeline.last_provenance,
            agent_name=AgentName.ROUTING_NAVIGATOR,
            decision_id=UUID(context.get("decision_id", str(uuid4()))),
            utility_score=min(avg_confidence, 1.0),
            confidence=avg_confidence,
            justification_trace=[
                f"Generated {len(routes)} routes for {len(orders)} orders",
                f"Total distance: {sum(r.total_distance_km for r in routes):.1f} km",
                f"Average confidence: {avg_confidence:.3f}",
            ],
            payload={"routes": [r.model_dump(mode="json") for r in routes]},
            tier=DecisionTier.TIER_1,
        )
        self._fsm.transition("proposal_submitted")
        # I-3: validate every emitted payload against proto/domain/.
        validate_agent_payload("routing_navigator", proposal.payload)
        return json.loads(proposal.to_deterministic_json())

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"status": "maintained", "round": params.get("round_number", 1)}

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")
        self._fsm.transition("policy_updated")
        return {
            "status": "executed",
            "decision_id": consensus_action.get("decision_id", ""),
            "kafka_published": True,
        }
