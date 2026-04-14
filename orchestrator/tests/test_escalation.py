"""SYNAPSE Orchestrator — HITL escalation flow tests (I-5)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from synapse_common.models import ConsensusDecision, DecisionTier

from orchestrator.hitl.escalation import HITLEscalation, WebSocketManager


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


def _low_confidence_decision() -> ConsensusDecision:
    return ConsensusDecision(
        tier=DecisionTier.TIER_3,
        proposals=[],
        selected_action={"action": "test"},
        pareto_weights={"demand_accuracy": 1.0},
        confidence=0.5,
        audit_trace=["test"],
    )


class TestEscalationTimeout:
    @pytest.mark.asyncio()
    async def test_timeout_defers_by_default(self, escalation: HITLEscalation) -> None:
        decision = _low_confidence_decision()
        result = await escalation.escalate(decision)
        assert result.escalated_to_human is True
        assert result.human_override is not None
        assert "deferred" in str(result.human_override.get("action", ""))

    @pytest.mark.asyncio()
    async def test_timeout_with_tier1_fallback(self, ws_manager: WebSocketManager) -> None:
        esc = HITLEscalation(
            kafka_producer=MagicMock(),
            ws_manager=ws_manager,
            timeout_seconds=0.1,
            timeout_action="execute_tier1",
        )
        decision = _low_confidence_decision()
        result = await esc.escalate(decision)
        assert result.escalated_to_human is True
        assert "tier1" in str(result.human_override.get("action", "")).lower()


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
