"""SYNAPSE Orchestrator — HITL escalation flow tests (I-5)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from synapse_common.models import ConsensusDecision, DecisionTier, HitlTimeoutAction

from orchestrator.hitl.escalation import (
    TIMEOUT_DEFERRED,
    TIMEOUT_NO_ACTION,
    HITLEscalation,
    WebSocketManager,
    build_timeout_record,
    has_dispatch_confirmation,
)

if TYPE_CHECKING:
    from uuid import UUID


@pytest.fixture()
def ws_manager() -> WebSocketManager:
    return WebSocketManager()


@pytest.fixture()
def escalation(ws_manager: WebSocketManager) -> HITLEscalation:
    return HITLEscalation(
        kafka_producer=MagicMock(),
        ws_manager=ws_manager,
        timeout_seconds=0.2,
        timeout_action="defer",
    )


def _low_confidence_decision(
    confirmations: list[str] | None = None,
) -> ConsensusDecision:
    return ConsensusDecision(
        tier=DecisionTier.TIER_3,
        proposals=[],
        selected_action={"action": "test"},
        pareto_weights={"demand_accuracy": 1.0},
        confidence=0.5,
        audit_trace=["test"],
        execution_confirmations=confirmations or [],
    )


class _ScriptedWaiter:
    """Timer-free waiter: times out for the listed ids, awaits the rest."""

    def __init__(self, timeout_for: set[UUID]) -> None:
        self._timeout_for = timeout_for

    async def __call__(
        self,
        future: asyncio.Future[dict[str, Any]],
        *,
        timeout: float,
        decision_id: UUID,
    ) -> dict[str, Any]:
        if decision_id in self._timeout_for:
            raise TimeoutError
        return await future


class TestEscalationTimeout:
    @pytest.mark.asyncio()
    async def test_timeout_defers_by_default(self, escalation: HITLEscalation) -> None:
        decision = _low_confidence_decision()
        result = await escalation.escalate(decision)
        assert result.escalated_to_human is True
        assert result.human_override is not None
        assert "deferred" in str(result.human_override.get("action", ""))

    @pytest.mark.asyncio()
    async def test_timeout_with_tier1_fallback_records_no_action(
        self,
        ws_manager: WebSocketManager,
    ) -> None:
        """Nothing is dispatched, so the record must not name an action (R5.5)."""
        esc = HITLEscalation(
            kafka_producer=MagicMock(),
            ws_manager=ws_manager,
            timeout_seconds=0.1,
            timeout_action="execute_tier1",
        )
        decision = _low_confidence_decision()
        result = await esc.escalate(decision)
        assert result.escalated_to_human is True
        assert result.human_override is not None
        assert result.human_override["action"] == TIMEOUT_NO_ACTION
        assert result.human_override["requested"] == "execute_tier1"
        assert result.human_override["dispatched"] is False
        assert result.execution_confirmations == []

    @pytest.mark.asyncio()
    async def test_timeout_resolves_and_removes_pending_entry(
        self,
        ws_manager: WebSocketManager,
    ) -> None:
        """R5.8: a timed-out escalation leaves no pending entry behind."""
        decision = _low_confidence_decision()
        esc = HITLEscalation(
            kafka_producer=MagicMock(),
            ws_manager=ws_manager,
            timeout_seconds=999.0,
            timeout_action="execute_tier1",
            waiter=_ScriptedWaiter({decision.decision_id}),
        )
        await esc.escalate(decision)
        assert esc.is_pending(decision.decision_id) is False
        assert esc.pending_decision_ids() == ()

    @pytest.mark.asyncio()
    async def test_two_outstanding_escalations_resolve_independently(
        self,
        ws_manager: WebSocketManager,
    ) -> None:
        """R5.9: one escalation timing out neither blocks nor dispatches the other."""
        timing_out = _low_confidence_decision()
        answered = _low_confidence_decision()
        esc = HITLEscalation(
            kafka_producer=MagicMock(),
            ws_manager=ws_manager,
            timeout_seconds=999.0,
            timeout_action="execute_last_known_good",
            waiter=_ScriptedWaiter({timing_out.decision_id}),
        )

        answered_task = asyncio.create_task(esc.escalate(answered))
        await asyncio.sleep(0)
        timed_out_result = await esc.escalate(timing_out)

        assert await esc.receive_human_response(
            answered.decision_id,
            {"action": "approved"},
        )
        answered_result = await answered_task

        assert timed_out_result.human_override is not None
        assert timed_out_result.human_override["dispatched"] is False
        assert timed_out_result.execution_confirmations == []
        assert answered_result.human_override == {"action": "approved"}
        assert esc.pending_decision_ids() == ()


class TestTimeoutRecord:
    def test_dispatch_confirmation_requires_an_enacted_entry(self) -> None:
        assert has_dispatch_confirmation([]) is False
        assert has_dispatch_confirmation(None) is False
        assert has_dispatch_confirmation(["no_result", "unknown", ""]) is False
        assert has_dispatch_confirmation(["error:connection refused"]) is False
        assert has_dispatch_confirmation(["error:boom", "executed"]) is True

    def test_defer_records_deferral_without_dispatch(self) -> None:
        record = build_timeout_record(
            requested=HitlTimeoutAction.DEFER,
            timeout_seconds=300.0,
            confirmations=[],
        )
        assert record.action == TIMEOUT_DEFERRED
        assert record.dispatched is False
        assert record.to_override()["requested"] == "defer"

    def test_requested_fallback_named_only_with_a_matching_confirmation(self) -> None:
        without = build_timeout_record(
            requested=HitlTimeoutAction.EXECUTE_TIER1,
            timeout_seconds=300.0,
            confirmations=["error:agent unreachable"],
        )
        assert without.action == TIMEOUT_NO_ACTION
        assert without.dispatched is False

        with_entry = build_timeout_record(
            requested=HitlTimeoutAction.EXECUTE_TIER1,
            timeout_seconds=300.0,
            confirmations=["executed"],
        )
        assert with_entry.action == "timeout_execute_tier1"
        assert with_entry.dispatched is True


class TestEscalationApproval:
    @pytest.mark.asyncio()
    async def test_human_approval(self, escalation: HITLEscalation) -> None:
        decision = _low_confidence_decision()

        async def approve_after_delay() -> None:
            await asyncio.sleep(0.05)
            await escalation.receive_human_response(
                decision.decision_id,
                {"action": "approved", "notes": "looks good"},
            )

        task = asyncio.create_task(approve_after_delay())
        result = await escalation.escalate(decision)
        await task
        assert result.escalated_to_human is True
        assert result.human_override is not None
        assert result.human_override.get("action") == "approved"


class TestEscalationRejection:
    @pytest.mark.asyncio()
    async def test_human_rejection(self, escalation: HITLEscalation) -> None:
        decision = _low_confidence_decision()

        async def reject_after_delay() -> None:
            await asyncio.sleep(0.05)
            await escalation.receive_human_response(
                decision.decision_id,
                {"action": "rejected", "reason": "unsafe action"},
            )

        task = asyncio.create_task(reject_after_delay())
        result = await escalation.escalate(decision)
        await task
        assert result.human_override is not None
        assert result.human_override.get("action") == "rejected"
