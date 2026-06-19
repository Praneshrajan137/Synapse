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

from agents.pricing_oracle.inference.pipeline import PricingOraclePipeline
from agents.pricing_oracle.state_machine import PricingOracleStateMachine

logger = structlog.get_logger(__name__)


class PricingOracleA2AHandler:
    """A2A handler for Pricing Oracle agent. JSON-RPC 2.0 protocol."""

    def __init__(
        self,
        pipeline: PricingOraclePipeline | None = None,
        *,
        actuator: Actuator | None = None,
        kafka_producer: Any = None,
    ) -> None:
        self._pipeline = pipeline or PricingOraclePipeline()
        self._fsm = PricingOracleStateMachine()
        # ADR-052: execute() scales world demand through the price lever via this client
        # (real state change), and event-sources the ratified update through Kafka.
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
            # ADR-044: structured provenance rides with the proposal (I-3/I-4).
            provenance=self._pipeline.last_provenance,
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
        # ADR-052/R3: bounded rule-based concession toward the round consensus, with
        # any revised payload validated against proto/domain/ (I-3) via the shared helper.
        response = build_debate_response("pricing_oracle", params)
        logger.info("debate_respond", round=response["round"], status=response["status"])
        self._fsm.record_tool_call()
        return response

    def execute(self, consensus_action: dict[str, Any]) -> dict[str, Any]:
        """Enact the ratified pricing ON THE WORLD (ADR-052 — real actuation).

        Replaces the status-dict stub that changed nothing. For every ratified pricing
        update with a positive multiplier this applies a ``SET_PRICE_MULT`` ``WorldAction``
        (the world scales demand through its price lever) and event-sources the update to
        ``synapse.pricing.update``. Returns the ACTUAL effect; ``kafka_published`` reflects
        a real produce (never a bare ``True``). Degrades honestly — status ``"diverged"``,
        empty ``world_effects``, ``kafka_published=False`` — when the world or Kafka is
        unavailable, the city is missing, or no actionable update exists (I-7, R5/R7).
        """
        self._fsm.transition("consensus_reached")
        self._fsm.transition("execution_confirmed")

        decision_id = str(consensus_action.get("decision_id") or uuid4())
        city = str(consensus_action.get("city") or "")
        proposal = consensus_action.get("ratified_proposal") or {}
        payload = proposal.get("payload", {}) if isinstance(proposal, dict) else {}
        updates = payload.get("updates", []) if isinstance(payload, dict) else []

        # I-3: validate the ratified payload against proto/domain/ before it drives the
        # world. An invalid payload is rejected (never propagated) and diverges honestly.
        try:
            validate_agent_payload("pricing_oracle", payload if isinstance(payload, dict) else {})
        except SchemaValidationError as exc:
            logger.warning("actuation_degraded", agent="pricing_oracle", reason="invalid_payload")
            return self._diverged(decision_id, city, "invalid_payload", error=str(exc))

        # One SET_PRICE_MULT action per actionable item (a ratified update with price > 0).
        items: list[ActuationItem] = []
        for update in updates:
            if not isinstance(update, dict):
                continue
            price_mult = float(update.get("multiplier", 0.0))
            if price_mult <= 0.0:  # R5.2: the lever requires a strictly positive multiplier.
                continue
            sku = update.get("sku_id")
            store = update.get("store_id")
            items.append(
                ActuationItem(
                    action_id=f"po-{decision_id}-{sku}",
                    params={"price_mult": price_mult},
                    sku_id=str(sku) if sku is not None else None,
                    store_id=str(store) if store is not None else None,
                )
            )

        outcome = actuate_items(
            agent_name="pricing_oracle",
            kind=WorldActionKind.SET_PRICE_MULT,
            city=city,
            decision_id=decision_id,
            items=items,
            actuator=self._actuator,
        )

        # Event-source only the updates the world actually applied (honest, never a stub True).
        applied_updates = [
            {"sku_id": item.sku_id, "price_mult": item.params["price_mult"]}
            for item, effect in zip(items, outcome.world_effects, strict=False)
            if effect.get("applied")
        ]
        kafka_published = False
        if applied_updates:
            kafka_published = honest_produce(
                self._kafka,
                "synapse.pricing.update",
                value={
                    "decision_id": decision_id,
                    "city": city,
                    "updates": applied_updates,
                    "ts": datetime.now(UTC).isoformat(),
                },
                key=decision_id,
                agent_name="pricing_oracle",
            )

        self._fsm.transition("policy_updated")
        self._fsm.record_tool_call()
        logger.info(
            "pricing_executed",
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
            "agent": "pricing_oracle",
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
            "agent": "pricing_oracle",
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
