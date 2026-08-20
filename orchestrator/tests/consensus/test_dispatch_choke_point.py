"""ADR-054 D1: one dispatch ratification choke point on every tier.

`_fast_path` used to run `_phase_collect -> argmax -> _build_decision ->
_phase_execute`, calling neither the guardrail engine nor the HITL gate, so the tier
router decided whether I-5 and I-6 applied (purpose-achievement-audit, Requirement 5).
Both routes now end at `_ratify_and_dispatch`.

These are example-class unit tests for the Tier-1 route, which is the route that had
no gate at all, plus the Tier-4 twin verdict the choke point now enforces (ADR-054 D3,
R13.4). The universal properties - the confidence gate applies on *every* tier
(Property 22, task 8.6) and selection/twin verdicts are consequential (Property 26,
task 8.8) - are `@pytest.mark.slow` and run in CI.

The collaborators here are the real ones wherever the assertion depends on them: the
real `GuardrailEngine` supplies the verdict and the real `HITLEscalation` awaits a
human future and dispatches nothing. Only Postgres and the A2A network are doubled,
and both are doubled by recording sinks so the tests observe what actually happened
rather than what a mock was told to say.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from synapse_common.models import (
    AgentName,
    AgentProposal,
    ConsensusDecision,
    DecisionTier,
)

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus import protocol as protocol_mod
from orchestrator.consensus.protocol import (
    ConsensusProtocol,
    TwinAvailability,
    TwinExceedAction,
    TwinVerdict,
)
from orchestrator.guardrails.rules import GuardrailEngine
from orchestrator.hitl.escalation import HITLEscalation, WebSocketManager

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID

# A cross-store raw demand payload: `order_ids` (raw) alongside two store identities
# and an explicit recipient. `privacy_boundary` is declared BLOCK, so this withholds
# dispatch irrespective of confidence (R5.2).
_CROSS_STORE_ACTION: dict[str, Any] = {
    "store_id": "blr_001",
    "target_store_id": "blr_002",
    "share_with": ["blr_002"],
    "order_ids": ["o-1", "o-2"],
}


class _RecordingAuditSink:
    """An `AuditLogger`-shaped append-only sink (I-4: append, never update).

    The real logger needs Postgres; what these tests assert is *how many* rows were
    appended and *what they said about dispatch*, which this records faithfully.
    """

    def __init__(self) -> None:
        self.rows: list[ConsensusDecision] = []

    async def log_decision(self, decision: ConsensusDecision) -> UUID:
        self.rows.append(decision)
        return uuid4()


class _TimingOutWaiter:
    """Timer-free waiter that times the human out immediately."""

    async def __call__(
        self,
        future: asyncio.Future[dict[str, Any]],
        *,
        timeout: float,
        decision_id: UUID,
    ) -> dict[str, Any]:
        del future, timeout, decision_id
        raise TimeoutError


def _protocol(audit: _RecordingAuditSink) -> ConsensusProtocol:
    cfg = OrchestratorConfig(postgresql_url="sqlite+aiosqlite:///", pinecone_api_key=None)
    return ConsensusProtocol(
        config=cfg,
        tier_router=MagicMock(),
        guardrails=GuardrailEngine(confidence_threshold=0.7),
        audit_logger=audit,  # type: ignore[arg-type]
        hitl_escalation=HITLEscalation(
            kafka_producer=None,
            ws_manager=WebSocketManager(),
            timeout_seconds=0.01,
            timeout_action="defer",
            waiter=_TimingOutWaiter(),
        ),
        context_builder=MagicMock(),
        ollama_client=MagicMock(),
        meta_rl=MagicMock(**{"get_weights.return_value": {"demand_accuracy": 1.0}}),
        semantic_cache=MagicMock(**{"available": False}),
    )


def _proposal(confidence: float, payload: dict[str, Any]) -> AgentProposal:
    return AgentProposal(
        agent_name=AgentName.INVENTORY_SENTINEL,
        decision_id=uuid4(),
        utility_score=0.9,
        confidence=confidence,
        justification_trace=["reorder below par"],
        payload=payload,
        tier=DecisionTier.TIER_1,
    )


def _decision(
    *,
    confidence: float,
    action: dict[str, Any],
    tier: DecisionTier = DecisionTier.TIER_1,
) -> ConsensusDecision:
    return ConsensusDecision(
        tier=tier,
        proposals=[_proposal(confidence, action)],
        selected_action=action,
        pareto_weights={"demand_accuracy": 1.0},
        confidence=confidence,
        audit_trace=[f"tier={tier.value}", "phase=4"],
    )


@pytest.fixture()
def dispatches(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Record every A2A call the protocol makes, and answer `execute` with a status."""
    seen: list[dict[str, Any]] = []

    async def fake_a2a(**kwargs: Any) -> Any:
        seen.append(kwargs)
        return MagicMock(error=None, result={"status": "ok"})

    monkeypatch.setattr(protocol_mod, "send_a2a_request", fake_a2a)
    yield seen


def _execute_calls(seen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [call for call in seen if call.get("method") == "execute"]


class TestTier1WithholdsDispatch:
    """R5.1, R5.2: a Tier-1 decision that fails ratification dispatches nothing."""

    @pytest.mark.asyncio()
    async def test_sub_threshold_confidence_withholds_dispatch(
        self,
        dispatches: list[dict[str, Any]],
    ) -> None:
        audit = _RecordingAuditSink()
        proto = _protocol(audit)

        out = await proto._ratify_and_dispatch(
            _decision(confidence=0.5, action={"action_type": "reorder"}),
            tier=DecisionTier.TIER_1,
        )

        # Escalated to a human, and nothing was enacted on the world.
        assert out.escalated_to_human is True
        assert out.execution_confirmations == []
        assert _execute_calls(dispatches) == []
        # The audit row says the same thing (R5.1: escalated, zero dispatched).
        assert len(audit.rows) == 1
        assert audit.rows[0].escalated_to_human is True
        assert audit.rows[0].execution_confirmations == []
        assert "dispatch=withheld" in audit.rows[0].audit_trace

    @pytest.mark.asyncio()
    async def test_block_violation_withholds_dispatch_on_tier_1(
        self,
        dispatches: list[dict[str, Any]],
    ) -> None:
        audit = _RecordingAuditSink()
        proto = _protocol(audit)

        # High confidence: the only reason to withhold is the BLOCK guardrail.
        out = await proto._ratify_and_dispatch(
            _decision(confidence=0.99, action=dict(_CROSS_STORE_ACTION)),
            tier=DecisionTier.TIER_1,
        )

        assert out.execution_confirmations == []
        assert _execute_calls(dispatches) == []
        assert out.human_override is not None
        assert out.human_override["dispatched"] is False
        assert len(audit.rows) == 1
        assert audit.rows[0].execution_confirmations == []


class TestTier1Dispatches:
    """A ratified Tier-1 decision still dispatches, and is audited exactly once."""

    @pytest.mark.asyncio()
    async def test_passing_decision_dispatches_once_and_appends_one_row(
        self,
        dispatches: list[dict[str, Any]],
    ) -> None:
        audit = _RecordingAuditSink()
        proto = _protocol(audit)

        out = await proto._ratify_and_dispatch(
            _decision(confidence=0.95, action={"action_type": "reorder", "store_id": "blr_001"}),
            tier=DecisionTier.TIER_1,
        )

        assert out.escalated_to_human is False
        assert out.execution_confirmations == ["ok"]
        assert len(_execute_calls(dispatches)) == 1
        # One decision, one audit row: `_phase_execute` reuses the id the choke point
        # appended for `execute_consensus`'s @deal.post rather than logging again.
        assert len(audit.rows) == 1
        assert out.audit_id is not None


def _verdict(
    *,
    availability: TwinAvailability = TwinAvailability.VERIFIED,
    disagreement: float | None,
    bound: float = 0.25,
    action_on_exceed: TwinExceedAction = TwinExceedAction.ESCALATE,
) -> TwinVerdict:
    return TwinVerdict(
        availability=availability,
        bound=bound,
        action_on_exceed=action_on_exceed,
        disagreement=disagreement,
        compared_kpis=("orders",) if disagreement is not None else (),
    )


def _ratification(out: ConsensusDecision) -> dict[str, Any]:
    records = [
        m.content for m in out.context_messages if m.content.get("type") == "dispatch_ratification"
    ]
    assert records, "the choke point records every ratification"
    return records[-1]


class TestTwinVerdictIsConsequential:
    """ADR-054 D3 / R13.4: the Tier-4 twin can object, and dispatch honours it."""

    @pytest.mark.asyncio()
    async def test_disagreement_beyond_bound_escalates_and_withholds(
        self,
        dispatches: list[dict[str, Any]],
    ) -> None:
        audit = _RecordingAuditSink()
        proto = _protocol(audit)

        out = await proto._ratify_and_dispatch(
            _decision(
                confidence=0.95,  # passes the confidence floor and every guardrail
                action={"action_type": "reorder", "store_id": "blr_001"},
                tier=DecisionTier.TIER_4,
            ),
            tier=DecisionTier.TIER_4,
            twin_verdict=_verdict(disagreement=0.9),
        )

        # The twin's objection is the only reason nothing dispatched.
        assert _execute_calls(dispatches) == []
        assert out.execution_confirmations == []
        assert out.escalated_to_human is True
        assert "withheld_by=twin_disagreement" in out.audit_trace
        assert len(audit.rows) == 1
        assert audit.rows[0].execution_confirmations == []
        # R13.4: recorded as a consequence, not in `audit_trace` alone.
        record = _ratification(out)
        assert record["twin_veto"] is True
        assert record["twin_verdict_enforced"] is True
        assert any("twin_disagreement:" in r for r in record["reasons"])

    @pytest.mark.asyncio()
    async def test_withhold_action_queues_no_human(
        self,
        dispatches: list[dict[str, Any]],
    ) -> None:
        """The committed `action_on_exceed: withhold` withholds without a human."""
        audit = _RecordingAuditSink()
        proto = _protocol(audit)

        out = await proto._ratify_and_dispatch(
            _decision(
                confidence=0.95,
                action={"action_type": "reorder", "store_id": "blr_001"},
                tier=DecisionTier.TIER_4,
            ),
            tier=DecisionTier.TIER_4,
            twin_verdict=_verdict(disagreement=0.9, action_on_exceed=TwinExceedAction.WITHHOLD),
        )

        assert _execute_calls(dispatches) == []
        assert out.execution_confirmations == []
        assert out.escalated_to_human is False
        assert out.human_override is None
        assert "dispatch=withheld" in out.audit_trace

    @pytest.mark.asyncio()
    async def test_unavailable_twin_does_not_veto(
        self,
        dispatches: list[dict[str, Any]],
    ) -> None:
        """I-7: absence of a verdict is not a negative verdict.

        A dead twin must not become a global Tier-4 kill switch - the strongest
        alternative ADR-054 rejected.
        """
        audit = _RecordingAuditSink()
        proto = _protocol(audit)

        out = await proto._ratify_and_dispatch(
            _decision(
                confidence=0.95,
                action={"action_type": "reorder", "store_id": "blr_001"},
                tier=DecisionTier.TIER_4,
            ),
            tier=DecisionTier.TIER_4,
            twin_verdict=_verdict(
                availability=TwinAvailability.UNAVAILABLE,
                disagreement=None,
            ),
        )

        assert len(_execute_calls(dispatches)) == 1
        assert out.execution_confirmations == ["ok"]
        assert _ratification(out)["twin_veto"] is False

    @pytest.mark.asyncio()
    async def test_agreement_within_bound_dispatches(
        self,
        dispatches: list[dict[str, Any]],
    ) -> None:
        audit = _RecordingAuditSink()
        proto = _protocol(audit)

        out = await proto._ratify_and_dispatch(
            _decision(
                confidence=0.95,
                action={"action_type": "reorder", "store_id": "blr_001"},
                tier=DecisionTier.TIER_4,
            ),
            tier=DecisionTier.TIER_4,
            twin_verdict=_verdict(disagreement=0.1),
        )

        assert len(_execute_calls(dispatches)) == 1
        assert out.execution_confirmations == ["ok"]
        assert _ratification(out)["twin_veto"] is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
