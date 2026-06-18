"""
SYNAPSE Sustainability Agent -- A2A JSON-RPC Handler (I-9).
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
from synapse_common.schemas import validate_agent_payload

from agents.sustainability_agent.inference.pipeline import SustainabilityPipeline
from agents.sustainability_agent.state_machine import SustainabilityAgentStateMachine

# Honest No-Op event-source topic (R6.2/R6.5): records that no carbon lever exists in the
# standing world, so the gate marks this agent converted without any fabricated actuation.
CARBON_TOPIC = "synapse.sustainability.carbon"

# India grid emission factor: ~0.79 kg CO2 / kWh (Central Electricity Authority,
# Apr-2025 baseline). Used to derive energy_kwh from the compute CO2 component.
INDIA_GRID_KG_CO2_PER_KWH = 0.79

logger = structlog.get_logger(__name__)


class SustainabilityAgentA2AHandler:
    """A2A handler for Sustainability Agent. JSON-RPC 2.0 protocol."""

    def __init__(
        self,
        pipeline: SustainabilityPipeline | None = None,
        *,
        kafka_producer: Any = None,
    ) -> None:
        self._pipeline = pipeline or SustainabilityPipeline()
        self._fsm = SustainabilityAgentStateMachine()
        # ADR-052/R6.2: carbon_efficiency has NO natural world-mutation lever in the
        # standing WorldRuntime, so execute() is an Honest No-Op — it constructs no
        # fabricated effect and only event-sources the ratified result through Kafka.
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
        except Exception as e:
            logger.error("a2a_handler_error", method=method, error=str(e))
            return self._error_response(request_id, -32000, str(e))

    def proposal(self, decision_context: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("carbon_report_requested")

        fuel_liters = float(decision_context.get("fuel_estimate_liters", 0.0))
        distance_km = float(decision_context.get("total_distance_km", 0.0))
        decision_id = decision_context.get("decision_id", str(uuid4()))

        report = self._pipeline.report(
            fuel_liters=fuel_liters,
            distance_km=distance_km,
        )

        # Project the rich internal CarbonReport down to the canonical
        # `synapse.domain.carbon_report` shape that downstream consumers
        # contract against. The full report is still emitted on the
        # synapse.sustainability.carbon Kafka topic for analytics.
        timestamp_iso = (
            report.timestamp.isoformat().replace("+00:00", "Z")
            if hasattr(report.timestamp, "isoformat")
            else str(report.timestamp)
        )
        energy_kwh = round(report.compute_co2_kg / INDIA_GRID_KG_CO2_PER_KWH, 6)
        carbon_pareto_weight = float(
            report.pareto_weights.get("carbon", 0.25) if report.pareto_weights else 0.25
        )
        survival_probability = max(0.0, 1.0 - float(report.waste_probability))

        schema_payload: dict[str, Any] = {
            "report_id": report.report_id,
            "scope": "aggregate",
            "co2_kg": float(report.total_co2_kg),
            "energy_kwh": energy_kwh,
            "timestamp": timestamp_iso,
            "waste_prediction": {
                "predicted_waste_kg": 0.0,
                "survival_probability": survival_probability,
                "recommended_action": ("markdown" if report.waste_probability > 0.5 else "monitor"),
            },
            "pareto_weight": carbon_pareto_weight,
        }

        proposal = AgentProposal(
            # ADR-044: structured provenance rides with the proposal (I-3/I-4).
            provenance=self._pipeline.last_provenance,
            agent_name=AgentName.SUSTAINABILITY_AGENT,
            decision_id=UUID(decision_id) if isinstance(decision_id, str) else decision_id,
            utility_score=min(report.confidence, 1.0),
            confidence=report.confidence,
            justification_trace=[
                f"Delivery CO2: {report.delivery_co2_kg:.4f} kg",
                f"Compute CO2: {report.compute_co2_kg:.6f} kg",
                f"Compute energy: {energy_kwh:.6f} kWh (India grid factor)",
                f"Waste probability: {report.waste_probability:.4f}",
                "Carbon is first-class Pareto objective (INV-SA-001)",
                f"Provenance chain length: {len(report.provenance_chain)}",
            ],
            payload=schema_payload,
            tier=DecisionTier.TIER_2,
        )

        self._fsm.transition("proposal_submitted")
        self._fsm.record_tool_call()

        # I-3: validate every emitted payload against proto/domain/.
        validate_agent_payload("sustainability_agent", proposal.payload)

        result: dict[str, Any] = json.loads(proposal.to_deterministic_json())
        return result

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        # ADR-052/R3: bounded rule-based concession toward the round consensus, with
        # any revised payload validated against proto/domain/ (I-3) via the shared helper.
        response = build_debate_response("sustainability_agent", params)
        logger.info("debate_respond", round=response["round"], status=response["status"])
        self._fsm.record_tool_call()
        return response

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        """Honest No-Op for carbon_efficiency (ADR-052 — R6.1/R6.2/R6.4/R6.5/R7.4).

        The standing ``WorldRuntime`` has no carbon lever, so this agent constructs NO
        fabricated effect and never returns ``"executed"``. It returns status
        ``"diverged"`` with empty ``world_effects`` and ``reason="no_carbon_lever"``,
        leaving the world observed via ``perceive()`` unchanged. It still performs one
        honest event-source ``produce`` (recording that no carbon lever exists) so the
        anti-regression gate marks the agent converted, not a stub. ``kafka_published``
        reflects a REAL produce (never a bare ``True``) and a Kafka outage degrades
        honestly to ``False`` without raising (I-7, R7.2).
        """
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = str(consensus_action.get("decision_id") or uuid4())
        city = str(consensus_action.get("city") or "")

        # Honest event-source: no world mutation, just a truthful record of the no-op.
        # A direct guarded ``self._kafka.produce`` (the gate's converted marker, R8.6) so
        # ``kafka_published`` reflects a REAL produce (never a bare ``True``); a Kafka
        # outage degrades honestly to ``False`` without raising into the caller
        # (I-7, R5.7, R7.2).
        kafka_published = False
        if self._kafka is not None:
            try:
                self._kafka.produce(
                    CARBON_TOPIC,
                    value={
                        "decision_id": decision_id,
                        "city": city,
                        "agent": "sustainability_agent",
                        "status": "diverged",
                        "reason": "no_carbon_lever",
                        "world_effects": [],
                        "ts": datetime.now(UTC).isoformat(),
                    },
                    key=decision_id,
                )
                kafka_published = True
            except Exception as exc:  # noqa: BLE001 — a Kafka outage degrades honestly (I-7)
                logger.warning(
                    "publish_failed",
                    agent="sustainability_agent",
                    topic=CARBON_TOPIC,
                    error=str(exc),
                )

        self._fsm.transition("policy_updated")
        self._fsm.record_tool_call()
        logger.info(
            "sustainability_diverged",
            decision_id=decision_id,
            city=city,
            reason="no_carbon_lever",
            kafka_published=kafka_published,
        )
        return {
            "status": "diverged",
            "decision_id": decision_id,
            "city": city,
            "agent": "sustainability_agent",
            "world_effects": [],
            "kafka_published": kafka_published,
            "reason": "no_carbon_lever",
        }

    @staticmethod
    def _error_response(request_id: str, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        }
