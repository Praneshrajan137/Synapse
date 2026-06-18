"""
SYNAPSE Demand Prophet -- A2A JSON-RPC Handler (I-9).
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

from agents.demand_prophet.inference.pipeline import DemandProphetPipeline
from agents.demand_prophet.state_machine import DemandProphetStateMachine

logger = structlog.get_logger(__name__)

# Canonical horizon ordering: the shortest available horizon drives the live demand
# policy lever (it is the most relevant to the world's current arrival rate).
_HORIZON_ORDER: tuple[str, ...] = ("15min", "1h", "6h", "24h", "7d")


class DemandProphetA2AHandler:
    """A2A handler for Demand Prophet agent. JSON-RPC 2.0 protocol."""

    def __init__(
        self,
        pipeline: DemandProphetPipeline | None = None,
        *,
        actuator: Actuator | None = None,
        kafka_producer: Any = None,
    ) -> None:
        self._pipeline = pipeline or DemandProphetPipeline()
        self._fsm = DemandProphetStateMachine()
        # ADR-052: execute() adjusts the world's demand policy through the demand_mult
        # lever (real state change) and event-sources the ratified forecast to Kafka.
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
        except Exception as e:
            logger.error("a2a_handler_error", method=method, error=str(e))
            return self._error_response(request_id, -32000, str(e))

    def proposal(self, decision_context: dict[str, Any]) -> dict[str, Any]:
        self._fsm.transition("forecast_request_received")

        sku_ids = decision_context.get("sku_ids", [])
        store_id = decision_context.get("store_id", "")
        decision_id = decision_context.get("decision_id", str(uuid4()))

        forecasts = self._pipeline.predict(sku_ids, store_id)

        avg_confidence = sum(f.confidence for f in forecasts) / len(forecasts) if forecasts else 0.0

        proposal = AgentProposal(
            # ADR-044: structured provenance rides with the proposal (I-3/I-4).
            provenance=self._pipeline.last_provenance,
            agent_name=AgentName.DEMAND_PROPHET,
            decision_id=UUID(decision_id) if isinstance(decision_id, str) else decision_id,
            utility_score=min(avg_confidence, 1.0),
            confidence=avg_confidence,
            justification_trace=[
                f"Generated {len(forecasts)} forecasts for store {store_id}",
                f"Average confidence: {avg_confidence:.3f}",
                "All forecasts include conformal intervals (INV-DP-001)",
            ],
            payload={
                "forecasts": [f.model_dump(mode="json") for f in forecasts],
                "store_id": store_id,
                "num_skus": len(sku_ids),
            },
            tier=DecisionTier.TIER_2,
        )

        self._fsm.transition("proposal_submitted")
        self._fsm.record_tool_call()

        # I-3: validate every emitted payload against proto/domain/ before
        # leaving the handler. Schema mismatch raises SchemaValidationError
        # which surfaces as a JSON-RPC error rather than corrupting consensus.
        validate_agent_payload("demand_prophet", proposal.payload)

        result: dict[str, Any] = json.loads(proposal.to_deterministic_json())
        return result

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        # ADR-052/R3: revise the proposal via bounded rule-based concession toward the
        # round consensus, validating any revised payload against proto/domain/ (I-3).
        # The shared helper keeps all eight agents' concession behaviour identical.
        response = build_debate_response("demand_prophet", params)
        logger.info("debate_respond", round=response["round"], status=response["status"])
        self._fsm.record_tool_call()
        return response

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        """Adjust the world's demand policy from the ratified forecast (ADR-052 — real
        actuation).

        Replaces the status-dict stub that changed nothing. For every ratified forecast
        with a positive point demand this applies a ``SET_POLICY`` ``WorldAction`` on the
        ``demand_mult`` lever (the world scales its arrival rate through it) and
        event-sources the forecast to ``synapse.demand.forecast``. The ``demand_mult`` is
        derived from the forecast's expected demand relative to its conservative 90% lower
        bound (a genuine surge factor), clamped to the lever's accepted range (``>= 0.01``).
        Returns the ACTUAL effect; ``kafka_published`` reflects a real produce (never a bare
        ``True``). Degrades honestly — status ``"diverged"``, empty ``world_effects``,
        ``kafka_published=False`` — when the world or Kafka is unavailable, the city is
        missing, or no actionable forecast exists (I-7, R5/R7).
        """
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = str(consensus_action.get("decision_id") or uuid4())
        city = str(consensus_action.get("city") or "")
        proposal = consensus_action.get("ratified_proposal") or {}
        payload = proposal.get("payload", {}) if isinstance(proposal, dict) else {}
        forecasts = payload.get("forecasts", []) if isinstance(payload, dict) else []

        # I-3: validate the ratified payload against proto/domain/ before it drives the
        # world. An invalid payload is rejected (never propagated) and diverges honestly.
        try:
            validate_agent_payload("demand_prophet", payload if isinstance(payload, dict) else {})
        except SchemaValidationError as exc:
            logger.warning("actuation_degraded", agent="demand_prophet", reason="invalid_payload")
            return self._diverged(decision_id, city, "invalid_payload", error=str(exc))

        # One SET_POLICY(demand_mult) action per actionable forecast (positive point demand).
        items: list[ActuationItem] = []
        for forecast in forecasts:
            if not isinstance(forecast, dict):
                continue
            demand_mult = self._demand_mult(forecast)
            if demand_mult is None:  # no positive point demand → not actionable.
                continue
            sku = forecast.get("sku_id")
            store = forecast.get("store_id")
            items.append(
                ActuationItem(
                    action_id=f"dp-{decision_id}-{sku}",
                    params={"demand_mult": demand_mult},
                    sku_id=str(sku) if sku is not None else None,
                    store_id=str(store) if store is not None else None,
                )
            )

        outcome = actuate_items(
            agent_name="demand_prophet",
            kind=WorldActionKind.SET_POLICY,
            city=city,
            decision_id=decision_id,
            items=items,
            actuator=self._actuator,
        )

        # Event-source only the forecasts the world actually applied (honest, never a stub).
        applied_forecasts = [
            {"sku_id": item.sku_id, "demand_mult": item.params["demand_mult"]}
            for item, effect in zip(items, outcome.world_effects, strict=False)
            if effect.get("applied")
        ]
        kafka_published = False
        if applied_forecasts:
            kafka_published = honest_produce(
                self._kafka,
                "synapse.demand.forecast",
                value={
                    "decision_id": decision_id,
                    "city": city,
                    "forecasts": applied_forecasts,
                    "ts": datetime.now(UTC).isoformat(),
                },
                key=decision_id,
                agent_name="demand_prophet",
            )

        self._fsm.transition("policy_updated")
        self._fsm.record_tool_call()
        logger.info(
            "demand_executed",
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
            "agent": "demand_prophet",
            "world_effects": outcome.world_effects,
            "kafka_published": kafka_published,
            "reason": outcome.reason,
        }

    @staticmethod
    def _demand_mult(forecast: dict[str, Any]) -> float | None:
        """Derive the ``demand_mult`` lever from a ratified forecast (``None`` if inactive).

        Uses the shortest available horizon's point demand as the ratified expectation and
        its 90% conservative lower bound as the baseline; the surge ratio
        ``point / lower_90`` is how much expected demand exceeds the safe floor. With no
        usable lower bound the lever stays neutral (``1.0``). The result is clamped to the
        lever's accepted range (``>= 0.01``); a non-positive point demand is not actionable.
        """
        horizons = forecast.get("horizons")
        if not isinstance(horizons, dict):
            return None
        lower = forecast.get("lower_90") if isinstance(forecast.get("lower_90"), dict) else {}
        for horizon in _HORIZON_ORDER:
            if horizon not in horizons:
                continue
            point = float(horizons[horizon])
            if point <= 0.0:
                return None
            baseline = float(lower.get(horizon, 0.0)) if isinstance(lower, dict) else 0.0
            mult = point / baseline if baseline > 0.0 else 1.0
            return max(0.01, mult)
        return None

    def _diverged(
        self, decision_id: str, city: str, reason: str, *, error: str | None = None
    ) -> dict[str, Any]:
        """Build an honest divergence result (no world effect applied)."""
        result: dict[str, Any] = {
            "status": "diverged",
            "decision_id": decision_id,
            "city": city,
            "agent": "demand_prophet",
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
