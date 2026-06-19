"""
SYNAPSE Disruption Shield -- A2A JSON-RPC Handler (I-9).
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

from agents.disruption_shield.inference.pipeline import (
    DisruptionRequest,
    DisruptionShieldPipeline,
)
from agents.disruption_shield.state_machine import DisruptionShieldStateMachine

logger = structlog.get_logger(__name__)


class DisruptionShieldA2AHandler:
    """A2A handler for Disruption Shield agent. JSON-RPC 2.0 protocol."""

    def __init__(
        self,
        pipeline: DisruptionShieldPipeline | None = None,
        *,
        actuator: Actuator | None = None,
        kafka_producer: Any = None,
    ) -> None:
        self._pipeline = pipeline or DisruptionShieldPipeline()
        self._fsm = DisruptionShieldStateMachine()
        # ADR-052: execute() adjusts the world's lead-time policy through this client
        # (real state change), and event-sources the ratified mitigation through Kafka.
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
        self._fsm.transition("disruption_signal_received")

        node_ids = decision_context.get("node_ids", ["unknown"])
        features = decision_context.get("features", [[0.0] * 12])
        decision_id = decision_context.get("decision_id", str(uuid4()))

        req = DisruptionRequest(
            node_ids=node_ids,
            tabular_features=features,
            anomaly_threshold=decision_context.get("threshold", 0.65),
        )
        alert = self._pipeline.detect(req)

        # Build a payload that matches `synapse.domain.disruption_alert`.
        # The pipeline's DisruptionAlert is a richer internal model; the
        # schema is the canonical wire format for downstream consumers.
        affected_nodes = list(alert.anomalous_nodes) or ["unknown"]
        # Pipeline alert_level is 0-3; schema is 1-10. Map linearly.
        scaled_level = max(1, min(10, alert.alert_level * 3 + 1))
        playbook_id = alert.playbooks[0].id if alert.playbooks else f"NO-PLAYBOOK-{alert.alert_id}"
        playbook_actions = alert.playbooks[0].title if alert.playbooks else "no_playbook_matched"
        schema_payload: dict[str, Any] = {
            "alert_id": alert.alert_id,
            "alert_level": scaled_level,
            "anomaly_scores": {
                "isolation_forest": float(alert.isolation_forest_score),
                "lstm_autoencoder": float(alert.lstm_autoencoder_score),
                "gnn_structural": float(alert.gnn_structural_score),
                "ensemble_weighted": float(alert.ensemble_score),
            },
            "affected_nodes": affected_nodes,
            "disruption_type": alert.severity,
            "playbook_id": playbook_id,
            "playbook_actions": playbook_actions,
            "reasoning_chain": "\n".join(alert.reasoning_chain),
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "confidence": float(alert.confidence),
        }

        proposal = AgentProposal(
            # ADR-044: structured provenance rides with the proposal (I-3/I-4).
            provenance=self._pipeline.last_provenance,
            agent_name=AgentName.DISRUPTION_SHIELD,
            decision_id=UUID(decision_id) if isinstance(decision_id, str) else decision_id,
            utility_score=min(alert.ensemble_score, 1.0),
            confidence=alert.confidence,
            justification_trace=[
                f"Ensemble score: {alert.ensemble_score:.4f}",
                f"Alert level: {scaled_level}",
                f"Affected nodes: {len(affected_nodes)}",
                f"Severity: {alert.severity}",
                "INV-DS-001: anomaly -> alert verified",
                "INV-DS-003: reasoning chain attached",
            ],
            payload=schema_payload,
            tier=DecisionTier.TIER_2,
        )

        self._fsm.transition("proposal_submitted")
        self._fsm.record_tool_call()

        # I-3: validate every emitted payload against proto/domain/.
        validate_agent_payload("disruption_shield", proposal.payload)

        result: dict[str, Any] = json.loads(proposal.to_deterministic_json())
        return result

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        # ADR-052/R3: bounded rule-based concession toward the round consensus, with
        # any revised payload validated against proto/domain/ (I-3) via the shared helper.
        response = build_debate_response("disruption_shield", params)
        logger.info("debate_respond", round=response["round"], status=response["status"])
        self._fsm.record_tool_call()
        return response

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        """Enact the ratified mitigation ON THE WORLD (ADR-052 — real actuation).

        Replaces the status-dict stub that changed nothing. The ratified disruption alert
        supplies a lead-time signal: a more severe disruption lengthens supplier lead times,
        so this maps the alert's ``alert_level`` (1-10) to a ``lead_time_mult`` lever value
        (``>= 0.1``) and applies one ``SET_POLICY`` ``WorldAction`` (the world's restock
        lead time scales by that multiplier), then event-sources the mitigation to
        ``synapse.disruption.alert``. Returns the ACTUAL effect; ``kafka_published`` reflects
        a real produce (never a bare ``True``). Degrades honestly — status ``"diverged"``,
        empty ``world_effects``, ``kafka_published=False`` — when the world or Kafka is
        unavailable, the city is missing, or no actionable mitigation exists (I-7, R5/R7).
        """
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = str(consensus_action.get("decision_id") or uuid4())
        city = str(consensus_action.get("city") or "")
        proposal = consensus_action.get("ratified_proposal") or {}
        payload = proposal.get("payload", {}) if isinstance(proposal, dict) else {}
        if not isinstance(payload, dict):
            payload = {}

        # I-3: validate the ratified payload against proto/domain/ before it drives the
        # world. An invalid payload is rejected (never propagated) and diverges honestly.
        try:
            validate_agent_payload("disruption_shield", payload)
        except SchemaValidationError as exc:
            logger.warning(
                "actuation_degraded", agent="disruption_shield", reason="invalid_payload"
            )
            return self._diverged(decision_id, city, "invalid_payload", error=str(exc))

        # The ratified alert is a single actionable item: its severity (alert_level, 1-10)
        # sets how much the disruption stretches lead time. alert_level/5 maps a baseline
        # level-5 alert to 1.0x and a level-10 alert to 2.0x; the sim clamps to >= 0.1.
        items: list[ActuationItem] = []
        alert_level = payload.get("alert_level")
        if isinstance(alert_level, (int, float)) and float(alert_level) > 0.0:
            lead_time_mult = max(0.1, float(alert_level) / 5.0)
            items.append(
                ActuationItem(
                    action_id=f"ds-{decision_id}",
                    params={"lead_time_mult": lead_time_mult},
                )
            )

        outcome = actuate_items(
            agent_name="disruption_shield",
            kind=WorldActionKind.SET_POLICY,
            city=city,
            decision_id=decision_id,
            items=items,
            actuator=self._actuator,
        )

        # Event-source only when the world actually applied the mitigation (never a stub True).
        kafka_published = False
        if outcome.applied_count > 0:
            kafka_published = honest_produce(
                self._kafka,
                "synapse.disruption.alert",
                value={
                    "decision_id": decision_id,
                    "city": city,
                    "alert_id": payload.get("alert_id"),
                    "lead_time_mult": items[0].params["lead_time_mult"],
                    "ts": datetime.now(UTC).isoformat(),
                },
                key=decision_id,
                agent_name="disruption_shield",
            )

        self._fsm.transition("policy_updated")
        self._fsm.record_tool_call()
        logger.info(
            "disruption_executed",
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
            "agent": "disruption_shield",
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
            "agent": "disruption_shield",
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
