"""SYNAPSE Inventory Sentinel -- A2A JSON-RPC Handler (I-9)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from synapse_common.debate import build_debate_response
from synapse_common.models import AgentName, AgentProposal, DecisionTier
from synapse_common.schemas import validate_agent_payload
from synapse_common.world import Actuator, WorldAction, WorldActionKind, WorldActuator

from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline

logger = structlog.get_logger(__name__)


class InventorySentinelA2AHandler:
    """A2A handler for Inventory Sentinel agent."""

    def __init__(
        self,
        pipeline: InventorySentinelPipeline | None = None,
        *,
        actuator: Actuator | None = None,
        kafka_producer: Any = None,
    ) -> None:
        self._pipeline = pipeline or InventorySentinelPipeline()
        # ADR-052: execute() actuates the standing world through this client (real state
        # change), and event-sources the reorder through the injected Kafka producer.
        self._actuator: Actuator = actuator if actuator is not None else WorldActuator()
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
                    "error": {"code": -32601, "message": f"Not found: {method}"},
                    "id": request_id,
                }
            return {"jsonrpc": "2.0", "result": result, "id": request_id}
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": request_id,
            }

    def proposal(self, ctx: dict[str, Any]) -> dict[str, Any]:
        sku_ids = ctx.get("sku_ids", ["SKU001"])
        store_id = ctx.get("store_id", "STORE_BLR_001")
        actions = self._pipeline.decide(sku_ids, store_id)
        # I-5/ADR-040: proposal confidence is the mean of the per-action
        # confidences (forecast volatility) — never a constant, so the HITL
        # gate can actually fire on low-confidence decisions.
        avg_confidence = sum(a.confidence for a in actions) / len(actions) if actions else 0.0
        proposal = AgentProposal(
            # ADR-044: structured provenance rides with the proposal (I-3/I-4).
            provenance=self._pipeline.last_provenance,
            agent_name=AgentName.INVENTORY_SENTINEL,
            decision_id=UUID(ctx.get("decision_id", str(uuid4()))),
            utility_score=min(avg_confidence, 1.0),
            confidence=avg_confidence,
            justification_trace=[
                f"Generated {len(actions)} inventory actions",
                f"Average confidence: {avg_confidence:.3f}",
            ],
            payload={"actions": [a.model_dump(mode="json") for a in actions]},
            tier=DecisionTier.TIER_2,
        )
        # I-3: validate every emitted payload against proto/domain/.
        validate_agent_payload("inventory_sentinel", proposal.payload)
        return json.loads(proposal.to_deterministic_json())

    def debate_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        # ADR-052/R3: bounded rule-based concession toward the round consensus, with
        # any revised payload validated against proto/domain/ (I-3) via the shared helper.
        response = build_debate_response("inventory_sentinel", params)
        logger.info("debate_respond", round=response["round"], status=response["status"])
        return response

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Enact the ratified reorder ON THE WORLD (ADR-052 — real actuation).

        Replaces the status-dict stub that changed nothing. For every ratified
        ``reorder`` action this calls the twin's ``apply_action`` (inventory genuinely
        rises) and event-sources the reorder to ``synapse.inventory.reorder``. Returns
        the ACTUAL effect; ``kafka_published`` reflects a real produce (never a bare
        ``True``). Degrades honestly if the world or Kafka is unavailable (I-7).
        """
        decision_id = str(params.get("decision_id", ""))
        city = str(params.get("city") or "bengaluru")
        proposal = params.get("ratified_proposal") or {}
        payload = proposal.get("payload", {}) if isinstance(proposal, dict) else {}
        actions = payload.get("actions", []) if isinstance(payload, dict) else []

        world_effects: list[dict[str, Any]] = []
        reordered: list[str] = []
        attempted = 0
        for action in actions:
            if not isinstance(action, dict) or action.get("action_type") != "reorder":
                continue
            qty = float(action.get("quantity", 0.0))
            sku = action.get("sku_id")
            if qty <= 0.0 or not sku:
                continue
            attempted += 1
            applied = self._actuator.apply(
                WorldAction(
                    action_id=f"is-{decision_id}-{sku}",
                    kind=WorldActionKind.REORDER,
                    city=city,
                    sku_id=str(sku),
                    params={"quantity": qty},
                    decision_id=decision_id,
                )
            )
            world_effects.append({"sku_id": sku, "quantity": qty, **applied})
            if applied.get("applied"):
                reordered.append(str(sku))

        kafka_published = self._publish_reorders(decision_id, city, reordered)
        # HONEST confirmation (ADR-052): "diverged" when we had reorders to make but the
        # world applied NONE — so the outcome scorer's execution-confirmation signal is
        # backed by real actuation, not the old always-"executed" stub.
        status = "diverged" if (attempted > 0 and not reordered) else "executed"
        return {
            "status": status,
            "decision_id": decision_id,
            "city": city,
            "world_effects": world_effects,
            "reordered_skus": reordered,
            "kafka_published": kafka_published,
        }

    def _publish_reorders(self, decision_id: str, city: str, reordered: list[str]) -> bool:
        """Event-source the reorder; return True only if a produce actually happened."""
        if self._kafka is None or not reordered:
            return False
        try:
            self._kafka.produce(
                "synapse.inventory.reorder",
                value={
                    "decision_id": decision_id,
                    "city": city,
                    "skus": reordered,
                    "ts": datetime.now(UTC).isoformat(),
                },
                key=decision_id,
            )
            return True
        except Exception as exc:  # noqa: BLE001 — a Kafka outage degrades honestly (I-7)
            logger.warning("inventory_reorder_publish_failed", error=str(exc))
            return False
