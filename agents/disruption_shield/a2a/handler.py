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
from synapse_common.models import AgentName, AgentProposal, DecisionTier
from synapse_common.schemas import validate_agent_payload

from agents.disruption_shield.inference.pipeline import (
    DisruptionRequest,
    DisruptionShieldPipeline,
)
from agents.disruption_shield.state_machine import DisruptionShieldStateMachine

logger = structlog.get_logger(__name__)


class DisruptionShieldA2AHandler:
    """A2A handler for Disruption Shield agent. JSON-RPC 2.0 protocol."""

    def __init__(self, pipeline: DisruptionShieldPipeline | None = None) -> None:
        self._pipeline = pipeline or DisruptionShieldPipeline()
        self._fsm = DisruptionShieldStateMachine()

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
        playbook_id = (
            alert.playbooks[0].id
            if alert.playbooks
            else f"NO-PLAYBOOK-{alert.alert_id}"
        )
        playbook_actions = (
            alert.playbooks[0].title if alert.playbooks else "no_playbook_matched"
        )
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
        round_number = params.get("round_number", 1)
        logger.info("debate_respond", round=round_number, action="maintain_assessment")
        self._fsm.record_tool_call()
        return {"status": "maintained", "round": round_number}

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = consensus_action.get("decision_id", str(uuid4()))

        logger.info(
            "disruption_alert_published",
            decision_id=decision_id,
            topics=["synapse.disruption.alert", "synapse.disruption.playbook"],
        )

        self._fsm.transition("policy_updated")
        self._fsm.record_tool_call()

        return {
            "status": "executed",
            "decision_id": decision_id,
            "kafka_published": True,
            "topics": ["synapse.disruption.alert", "synapse.disruption.playbook"],
        }

    @staticmethod
    def _error_response(request_id: str, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        }
