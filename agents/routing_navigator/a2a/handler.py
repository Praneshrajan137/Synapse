"""SYNAPSE Routing Navigator -- A2A JSON-RPC Handler (I-9)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from synapse_common.debate import build_debate_response
from synapse_common.models import AgentName, AgentProposal, DecisionTier
from synapse_common.schemas import SchemaValidationError, validate_agent_payload
from synapse_common.world import (
    ActuationItem,
    Actuator,
    WorldActionKind,
    actuate_items,
    honest_produce,
    resolve_actuator,
)

from agents.routing_navigator.inference.pipeline import RoutingNavigatorPipeline
from agents.routing_navigator.state_machine import RoutingNavigatorStateMachine

logger = structlog.get_logger(__name__)

# The dispatch lever is neutral at 1.0 and accelerates pick/pack above it
# (engine: ``mean = pick_pack_mean_min / dispatch_speed``). A ratified route that
# predicts a long delivery time warrants faster dispatch to claw back latency, so
# dispatch_speed scales from ~1.0 (instant route) to 2.0 (a route at the hard cap).
# The world clamps the lever at >= 0.1, and this mapping stays comfortably above it.
_HARD_TIME_CAP_MIN = 480.0


class RoutingNavigatorA2AHandler:
    """A2A handler for Routing Navigator agent."""

    def __init__(
        self,
        pipeline: RoutingNavigatorPipeline | None = None,
        *,
        actuator: Actuator | None = None,
        kafka_producer: Any = None,
    ) -> None:
        self._pipeline = pipeline or RoutingNavigatorPipeline()
        self._fsm = RoutingNavigatorStateMachine()
        # ADR-052: execute() adjusts the world's dispatch policy through this client
        # (real state change), and event-sources the ratified route through Kafka.
        self._actuator: Actuator = resolve_actuator(actuator)
        self._kafka = kafka_producer

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
        result: dict[str, Any] = json.loads(proposal.to_deterministic_json())
        return result

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        # ADR-052/R3: bounded rule-based concession toward the round consensus, with
        # any revised payload validated against proto/domain/ (I-3) via the shared helper.
        response = build_debate_response("routing_navigator", params)
        logger.info("debate_respond", round=response["round"], status=response["status"])
        return response

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        """Enact the ratified route ON THE WORLD (ADR-052 — real actuation).

        Replaces the status-dict stub that changed nothing. For every ratified route
        plan this applies a ``SET_POLICY`` ``WorldAction`` on the ``dispatch_speed`` lever
        (the world packs/dispatches faster, lowering delivery latency) and event-sources
        the route to ``synapse.routing.dispatch``. Returns the ACTUAL effect;
        ``kafka_published`` reflects a real produce (never a bare ``True``). Degrades
        honestly — status ``"diverged"``, empty ``world_effects``, ``kafka_published=False``
        — when the world or Kafka is unavailable, the city is missing, or no actionable
        route exists (I-7, R5/R7).
        """
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = str(consensus_action.get("decision_id") or uuid4())
        city = str(consensus_action.get("city") or "")
        proposal = consensus_action.get("ratified_proposal") or {}
        payload = proposal.get("payload", {}) if isinstance(proposal, dict) else {}
        routes = payload.get("routes", []) if isinstance(payload, dict) else []

        # I-3: validate the ratified payload against proto/domain/ before it drives the
        # world. An invalid payload is rejected (never propagated) and diverges honestly.
        try:
            validate_agent_payload(
                "routing_navigator", payload if isinstance(payload, dict) else {}
            )
        except SchemaValidationError as exc:
            logger.warning(
                "actuation_degraded", agent="routing_navigator", reason="invalid_payload"
            )
            return self._diverged(decision_id, city, "invalid_payload", error=str(exc))

        # One SET_POLICY(dispatch_speed) action per actionable item (a ratified route).
        items: list[ActuationItem] = []
        for route in routes:
            if not isinstance(route, dict):
                continue
            route_id = route.get("route_id") or route.get("rider_id")
            dispatch_speed = self._dispatch_speed_from_route(route)
            items.append(
                ActuationItem(
                    action_id=f"rn-{decision_id}-{route_id}",
                    params={"dispatch_speed": dispatch_speed},
                    store_id=str(route.get("store_id")) if route.get("store_id") else None,
                )
            )

        outcome = actuate_items(
            agent_name="routing_navigator",
            kind=WorldActionKind.SET_POLICY,
            city=city,
            decision_id=decision_id,
            items=items,
            actuator=self._actuator,
        )

        # Event-source only the routes the world actually applied (honest, never a stub True).
        applied_routes = [
            {"dispatch_speed": item.params["dispatch_speed"], "store_id": item.store_id}
            for item, effect in zip(items, outcome.world_effects, strict=False)
            if effect.get("applied")
        ]
        kafka_published = False
        if applied_routes:
            kafka_published = honest_produce(
                self._kafka,
                "synapse.routing.dispatch",
                value={
                    "decision_id": decision_id,
                    "city": city,
                    "routes": applied_routes,
                    "ts": datetime.now(UTC).isoformat(),
                },
                key=decision_id,
                agent_name="routing_navigator",
            )

        self._fsm.transition("policy_updated")
        logger.info(
            "routing_executed",
            decision_id=decision_id,
            city=city,
            status=outcome.status,
            applied=outcome.applied_count,
            kafka_published=kafka_published,
        )
        return {
            "status": outcome.status,
            "decision_id": decision_id,
            "city": city,
            "agent": "routing_navigator",
            "world_effects": outcome.world_effects,
            "kafka_published": kafka_published,
            "reason": outcome.reason,
        }

    @staticmethod
    def _dispatch_speed_from_route(route: dict[str, Any]) -> float:
        """Derive the dispatch-speed lever from the ratified route's ``total_time_min``.

        Longer predicted delivery times call for faster pick/pack to recover latency, so
        the lever scales from ~1.0 (an instant route) up to 2.0 (a route at the 480-min
        hard cap). The result is always >= 1.0 and therefore within the world's >= 0.1
        accepted range (R5.4).
        """
        total_time_min = float(route.get("total_time_min", 0.0))
        normalized = min(max(total_time_min, 0.0), _HARD_TIME_CAP_MIN) / _HARD_TIME_CAP_MIN
        return round(max(0.1, 1.0 + normalized), 4)

    def _diverged(
        self, decision_id: str, city: str, reason: str, *, error: str | None = None
    ) -> dict[str, Any]:
        """Build an honest divergence result (no world effect applied)."""
        result: dict[str, Any] = {
            "status": "diverged",
            "decision_id": decision_id,
            "city": city,
            "agent": "routing_navigator",
            "world_effects": [],
            "kafka_published": False,
            "reason": reason,
        }
        if error is not None:
            result["error"] = error
        return result
