"""
SYNAPSE Freshness Guardian -- A2A JSON-RPC Handler (I-9).
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

from agents.freshness_guardian.inference.pipeline import (
    FreshnessGuardianPipeline,
    FreshnessRequest,
)
from agents.freshness_guardian.state_machine import FreshnessGuardianStateMachine

logger = structlog.get_logger(__name__)


class FreshnessGuardianA2AHandler:
    """A2A handler for Freshness Guardian agent. JSON-RPC 2.0 protocol."""

    def __init__(
        self,
        pipeline: FreshnessGuardianPipeline | None = None,
        *,
        actuator: Actuator | None = None,
        kafka_producer: Any = None,
    ) -> None:
        self._pipeline = pipeline or FreshnessGuardianPipeline()
        self._fsm = FreshnessGuardianStateMachine()
        # ADR-052: execute() lowers spoilage exposure on the standing world through the
        # closest existing lever — SET_POLICY dispatch_speed (R6.3) — and event-sources the
        # ratified alert through Kafka. No direct spoilage-reduction lever exists, so faster
        # pick/pack (less time-at-risk per unit) is the honest, observable proxy.
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
            # ADR-044: structured provenance rides with the proposal (I-3/I-4).
            provenance=self._pipeline.last_provenance,
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

        # I-3: validate every emitted payload against proto/domain/.
        validate_agent_payload("freshness_guardian", proposal.payload)

        result: dict[str, Any] = json.loads(proposal.to_deterministic_json())
        return result

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        # ADR-052/R3: bounded rule-based concession toward the round consensus, with
        # any revised payload validated against proto/domain/ (I-3) via the shared helper.
        response = build_debate_response("freshness_guardian", params)
        logger.info("debate_respond", round=response["round"], status=response["status"])
        self._fsm.record_tool_call()
        return response

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        """Enact the ratified freshness decision ON THE WORLD (ADR-052 — real actuation).

        No direct spoilage-reduction lever exists, so this raises ``dispatch_speed`` via the
        closest existing lever — ``SET_POLICY`` (R6.3). Faster pick/pack lowers each unit's
        time-at-risk, reducing spoilage exposure (observable in ``perceive()`` KPIs). One
        ``WorldAction`` is applied per *spoilage-relevant* actionable item (an alert the
        pipeline already flagged with ``markdown_applied=True``); the raised ``dispatch_speed``
        is derived from that alert's ``markdown_pct`` (spoilage urgency) and clamped ``>= 0.1``.

        Falls back to an **Honest No-Op** — status ``"diverged"``, empty ``world_effects``,
        an honest reason — when no spoilage-relevant item exists, or degrades honestly when
        the world or Kafka is unavailable or the city is missing (I-7, R5/R6/R7). Returns the
        ACTUAL effect; ``kafka_published`` reflects a real produce (never a bare ``True``).
        """
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = str(consensus_action.get("decision_id") or uuid4())
        city = str(consensus_action.get("city") or "")
        proposal = consensus_action.get("ratified_proposal") or {}
        payload = proposal.get("payload", {}) if isinstance(proposal, dict) else {}
        alerts = payload.get("alerts", []) if isinstance(payload, dict) else []

        # I-3: validate the ratified payload against proto/domain/ before it drives the
        # world. An invalid payload is rejected (never propagated) and diverges honestly.
        try:
            validate_agent_payload(
                "freshness_guardian", payload if isinstance(payload, dict) else {}
            )
        except SchemaValidationError as exc:
            logger.warning(
                "actuation_degraded", agent="freshness_guardian", reason="invalid_payload"
            )
            return self._diverged(decision_id, city, "invalid_payload", error=str(exc))

        # One SET_POLICY dispatch_speed action per spoilage-relevant actionable item: an alert
        # the pipeline already flagged for spoilage mitigation (markdown_applied). With none,
        # actuate_items returns the Honest No-Op (diverged, empty effects) — R6.1/R6.4.
        items: list[ActuationItem] = []
        for alert in alerts:
            if not isinstance(alert, dict) or not alert.get("markdown_applied"):
                continue
            # Raise dispatch_speed proportional to spoilage urgency (markdown_pct, 0..100),
            # clamped >= 0.1 to stay within the world's accepted range (R6.3).
            dispatch_speed = max(0.1, 1.0 + float(alert.get("markdown_pct", 0.0)) / 100.0)
            sku = alert.get("sku_id")
            store = alert.get("store_id")
            items.append(
                ActuationItem(
                    action_id=f"fg-{decision_id}-{sku}",
                    params={"dispatch_speed": dispatch_speed},
                    sku_id=str(sku) if sku is not None else None,
                    store_id=str(store) if store is not None else None,
                )
            )

        outcome = actuate_items(
            agent_name="freshness_guardian",
            kind=WorldActionKind.SET_POLICY,
            city=city,
            decision_id=decision_id,
            items=items,
            actuator=self._actuator,
        )

        # Event-source only the items the world actually applied (honest, never a stub True).
        applied_items = [
            {"sku_id": item.sku_id, "dispatch_speed": item.params["dispatch_speed"]}
            for item, effect in zip(items, outcome.world_effects, strict=False)
            if effect.get("applied")
        ]
        kafka_published = False
        if applied_items:
            kafka_published = honest_produce(
                self._kafka,
                "synapse.freshness.alert",
                value={
                    "decision_id": decision_id,
                    "city": city,
                    "items": applied_items,
                    "ts": datetime.now(UTC).isoformat(),
                },
                key=decision_id,
                agent_name="freshness_guardian",
            )

        self._fsm.transition("policy_updated")
        self._fsm.record_tool_call()
        logger.info(
            "freshness_executed",
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
            "agent": "freshness_guardian",
            "world_effects": outcome.world_effects,
            "kafka_published": kafka_published,
            "reason": outcome.reason,
        }

    def _diverged(
        self, decision_id: str, city: str, reason: str, *, error: str | None = None
    ) -> dict[str, Any]:
        """Build an honest divergence result (no world effect applied)."""
        result: dict[str, Any] = {
            "status": "diverged",
            "decision_id": decision_id,
            "city": city,
            "agent": "freshness_guardian",
            "world_effects": [],
            "kafka_published": False,
            "reason": reason,
        }
        if error is not None:
            result["error"] = error
        return result

    @staticmethod
    def _error_response(request_id: str, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        }
