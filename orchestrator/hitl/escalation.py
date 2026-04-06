"""
SYNAPSE Orchestrator — Confidence-gated HITL escalation (I-5).

When confidence < threshold or guardrails are violated, the decision is
published to a Kafka topic and pushed to the HITL React console via WebSocket.
The human has ``TIMEOUT_SECONDS`` to approve, reject, or modify.

Timeout fallback is configurable: DEFER (default), EXECUTE_TIER1, or
EXECUTE_LAST_KNOWN_GOOD (S-11 fix).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

import structlog

from synapse_common.metrics import HITL_ESCALATIONS_TOTAL, HITL_OVERRIDES_TOTAL
from synapse_common.models import ConsensusDecision, HitlTimeoutAction

logger = structlog.get_logger(__name__)

_JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}


class WebSocketManager:
    """Thin wrapper for broadcasting messages to connected WS clients."""

    def __init__(self) -> None:
        self._connections: list[Any] = []

    def register(self, ws: Any) -> None:
        self._connections.append(ws)

    def unregister(self, ws: Any) -> None:
        self._connections = [c for c in self._connections if c is not ws]

    async def broadcast(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, **_JSON_KWARGS)
        closed: list[Any] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                closed.append(ws)
        for ws in closed:
            self.unregister(ws)


class HITLEscalation:
    """Escalation manager with configurable timeout action."""

    def __init__(
        self,
        kafka_producer: Any,
        ws_manager: WebSocketManager,
        timeout_seconds: float = 300.0,
        timeout_action: str = "defer",
    ) -> None:
        self._kafka = kafka_producer
        self._ws_manager = ws_manager
        self._timeout = timeout_seconds
        self._timeout_action = HitlTimeoutAction(timeout_action)
        self._pending: dict[UUID, asyncio.Future[dict[str, Any]]] = {}

    async def escalate(
        self,
        decision: ConsensusDecision,
        violations: list[str] | None = None,
    ) -> ConsensusDecision:
        """Escalate *decision* to a human operator.  Blocks until response or timeout."""
        HITL_ESCALATIONS_TOTAL.labels(reason="low_confidence").inc()

        escalation_payload = {
            "type": "escalation",
            "decision_id": str(decision.decision_id),
            "confidence": decision.confidence,
            "proposals": [p.model_dump(mode="json") for p in decision.proposals],
            "recommended_action": decision.selected_action,
            "tier": str(decision.tier.value),
            "violations": violations or [],
        }

        if self._kafka is not None:
            self._kafka.produce(
                "synapse.orchestrator.escalation",
                value=escalation_payload,
                key=str(decision.decision_id),
            )

        await self._ws_manager.broadcast(escalation_payload)

        future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending[decision.decision_id] = future

        try:
            human_response = await asyncio.wait_for(future, timeout=self._timeout)
            HITL_OVERRIDES_TOTAL.labels(action="approved").inc()
            return decision.model_copy(
                update={
                    "escalated_to_human": True,
                    "human_override": human_response,
                },
            )
        except asyncio.TimeoutError:
            logger.warning(
                "hitl_timeout",
                decision_id=str(decision.decision_id),
                action=self._timeout_action.value,
            )
            HITL_OVERRIDES_TOTAL.labels(action="timeout").inc()

            if self._timeout_action == HitlTimeoutAction.DEFER:
                return decision.model_copy(
                    update={
                        "escalated_to_human": True,
                        "human_override": {
                            "action": "timeout_deferred",
                            "reason": f"{self._timeout}s HITL timeout — decision deferred",
                        },
                    },
                )

            return decision.model_copy(
                update={
                    "escalated_to_human": True,
                    "human_override": {
                        "action": f"timeout_{self._timeout_action.value}",
                        "reason": f"{self._timeout}s HITL timeout",
                    },
                },
            )
        finally:
            self._pending.pop(decision.decision_id, None)

    async def receive_human_response(
        self,
        decision_id: UUID,
        response: dict[str, Any],
    ) -> None:
        """Called when the human submits an override via WebSocket."""
        future = self._pending.get(decision_id)
        if future and not future.done():
            future.set_result(response)
