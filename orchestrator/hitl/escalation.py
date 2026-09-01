"""
SYNAPSE Orchestrator — Confidence-gated HITL escalation (I-5).

When confidence < threshold or guardrails are violated, the decision is
published to a Kafka topic and pushed to the HITL React console via WebSocket.
The human has ``TIMEOUT_SECONDS`` to approve, reject, or modify.

Timeout fallback is configurable: DEFER (default), EXECUTE_TIER1, or
EXECUTE_LAST_KNOWN_GOOD (S-11 fix).

``escalate`` awaits a human future and dispatches nothing. Because of that, a
timeout record must never name an action as performed: ``human_override`` reports
``timeout_no_action`` unless ``execution_confirmations`` actually holds a matching
entry, in which case ``dispatched`` is True and the requested fallback is named
(R5.5). A timed-out escalation is resolved and its pending entry removed (R5.8),
per decision identifier, so two outstanding escalations resolve independently
(R5.9).
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Protocol

import structlog
from synapse_common.metrics import HITL_ESCALATIONS_TOTAL, HITL_OVERRIDES_TOTAL
from synapse_common.models import ConsensusDecision, HitlTimeoutAction, SynapseBaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

logger = structlog.get_logger(__name__)

_JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}

# ─────────────────────────────────────────────────────────────────────────────
# Honest timeout records (R5.5, R5.8, R5.9)
# ─────────────────────────────────────────────────────────────────────────────

#: ``human_override["action"]`` when nothing was dispatched.
TIMEOUT_NO_ACTION = "timeout_no_action"

#: ``human_override["action"]`` when the configured fallback is DEFER.
TIMEOUT_DEFERRED = "timeout_deferred"

#: Confirmation statuses that record an *absence* of enacted work. Under I-7 the
#: absence of proof is never treated as proof, so ``unknown`` counts as no
#: dispatch rather than as a dispatch.
_NON_DISPATCH_CONFIRMATIONS: frozenset[str] = frozenset(
    {
        "",
        "blocked",
        "deferred",
        "failed",
        "no_result",
        "rejected",
        "skipped",
        "unknown",
        "withheld",
    },
)

_ERROR_CONFIRMATION_PREFIX = "error:"


def has_dispatch_confirmation(confirmations: Sequence[str] | None) -> bool:
    """Return True when *confirmations* records at least one enacted action.

    Pure and timer-free: this is the seam that makes ``dispatched`` *derived*
    from ``execution_confirmations`` rather than asserted (R5.5). An error entry,
    an absence-of-result status, and an empty sequence are all "nothing was
    dispatched".
    """
    for entry in confirmations or ():
        status = entry.strip().lower()
        if status.startswith(_ERROR_CONFIRMATION_PREFIX):
            continue
        if status in _NON_DISPATCH_CONFIRMATIONS:
            continue
        return True
    return False


class HitlTimeoutRecord(SynapseBaseModel):
    """The ``human_override`` record written when an escalation times out.

    ``dispatched`` is True only when :func:`has_dispatch_confirmation` finds a
    matching entry in the decision's ``execution_confirmations``; ``action``
    names the requested fallback only in that case.
    """

    action: str
    requested: HitlTimeoutAction
    dispatched: bool
    reason: str

    def to_override(self) -> dict[str, Any]:
        """Render the record as the plain ``human_override`` mapping."""
        return {
            "action": self.action,
            "requested": str(self.requested.value),
            "dispatched": self.dispatched,
            "reason": self.reason,
        }


def build_timeout_record(
    *,
    requested: HitlTimeoutAction,
    timeout_seconds: float,
    confirmations: Sequence[str] | None,
) -> HitlTimeoutRecord:
    """Build the timeout record for *requested*, honest about what was dispatched.

    Pure: no clock, no timer, no I/O. Property 25 drives this directly.
    """
    dispatched = has_dispatch_confirmation(confirmations)
    if dispatched:
        return HitlTimeoutRecord(
            action=f"timeout_{requested.value}",
            requested=requested,
            dispatched=True,
            reason=(
                f"{timeout_seconds}s HITL timeout - {requested.value} dispatched and confirmed"
            ),
        )
    if requested is HitlTimeoutAction.DEFER:
        return HitlTimeoutRecord(
            action=TIMEOUT_DEFERRED,
            requested=requested,
            dispatched=False,
            reason=f"{timeout_seconds}s HITL timeout - decision deferred, no action taken",
        )
    return HitlTimeoutRecord(
        action=TIMEOUT_NO_ACTION,
        requested=requested,
        dispatched=False,
        reason=(
            f"{timeout_seconds}s HITL timeout - {requested.value} requested, no action dispatched"
        ),
    )


class HumanResponseWaiter(Protocol):
    """Awaits a human response, or raises ``TimeoutError``.

    Injectable so a test can exercise the timeout path (and per-decision timeout
    orderings) without a real timer.
    """

    async def __call__(
        self,
        future: asyncio.Future[dict[str, Any]],
        *,
        timeout: float,
        decision_id: UUID,
    ) -> dict[str, Any]: ...


async def wait_for_human_response(
    future: asyncio.Future[dict[str, Any]],
    *,
    timeout: float,
    decision_id: UUID,
) -> dict[str, Any]:
    """Default waiter: ``asyncio.wait_for`` against the wall clock.

    ``decision_id`` is unused here; it is part of the waiter contract so an
    injected waiter can time out per decision identifier without a timer.
    """
    del decision_id
    return await asyncio.wait_for(future, timeout=timeout)


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
        *,
        waiter: HumanResponseWaiter | None = None,
    ) -> None:
        self._kafka = kafka_producer
        self._ws_manager = ws_manager
        self._timeout = timeout_seconds
        self._timeout_action = HitlTimeoutAction(timeout_action)
        self._pending: dict[UUID, asyncio.Future[dict[str, Any]]] = {}
        self._waiter: HumanResponseWaiter = waiter or wait_for_human_response

    # ── Pending-escalation bookkeeping (R5.8, R5.9) ─────────────────────

    def pending_decision_ids(self) -> tuple[UUID, ...]:
        """Decision identifiers with an outstanding escalation."""
        return tuple(self._pending)

    def is_pending(self, decision_id: UUID) -> bool:
        """Whether *decision_id* still has an outstanding escalation."""
        return decision_id in self._pending

    def _resolve_pending(self, decision_id: UUID) -> None:
        """Resolve the escalation for *decision_id* and retain no pending entry.

        Only this identifier's entry is touched, so a second outstanding
        escalation stays addressable and resolves independently (R5.9).
        """
        future = self._pending.pop(decision_id, None)
        if future is not None and not future.done():
            future.cancel()

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

        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[decision.decision_id] = future

        try:
            human_response = await self._waiter(
                future,
                timeout=self._timeout,
                decision_id=decision.decision_id,
            )
            HITL_OVERRIDES_TOTAL.labels(action="approved").inc()
            return decision.model_copy(
                update={
                    "escalated_to_human": True,
                    "human_override": human_response,
                },
            )
        except TimeoutError:
            # Nothing is dispatched from here: the record is derived from the
            # decision's own execution_confirmations, never asserted (R5.5).
            record = build_timeout_record(
                requested=self._timeout_action,
                timeout_seconds=self._timeout,
                confirmations=decision.execution_confirmations,
            )
            logger.warning(
                "hitl_timeout",
                decision_id=str(decision.decision_id),
                requested=str(self._timeout_action.value),
                action=record.action,
                dispatched=record.dispatched,
            )
            HITL_OVERRIDES_TOTAL.labels(action="timeout").inc()
            return decision.model_copy(
                update={
                    "escalated_to_human": True,
                    "human_override": record.to_override(),
                },
            )
        finally:
            self._resolve_pending(decision.decision_id)

    async def receive_human_response(
        self,
        decision_id: UUID,
        response: dict[str, Any],
    ) -> bool:
        """Called when the human submits an override via WebSocket.

        Returns whether the response was accepted. While two escalations are
        outstanding, a response addressed to either identifier is accepted and
        affects only that identifier (R5.9).
        """
        future = self._pending.get(decision_id)
        if future is not None and not future.done():
            future.set_result(response)
            return True
        return False
