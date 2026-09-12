"""C7 (ADR-043): Tier-4 digital-twin verification + input-provenance recording.

Proves the orchestrator now invokes the digital twin's Monte-Carlo what-if at the
top tier (it was dead code before), records the verdict into the append-only audit
trail, degrades honestly when the twin is unreachable (I-7), and captures whether the
decision rested on real models or degraded fallbacks (ADR-040 substance in the audit).

ADR-054 D3 (purpose-achievement-audit R13.4) makes the verdict consequential:
``_phase_twin_verify`` returns a ``TwinVerdict`` beside the decision, judged against
the bound committed in ``infrastructure/quality/twin-verdict-bounds.yaml``. The
example classes here are: a verified twin that agrees, a verified twin that
contradicts the consensus prediction beyond the bound, and an unreachable twin -
which must still degrade honestly and veto **nothing**. The universal property is
Property 26 (task 8.8) and is ``@pytest.mark.slow``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, NoReturn
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus import protocol as protocol_mod
from orchestrator.consensus.protocol import (
    ConsensusProtocol,
    TwinAvailability,
    TwinDisagreementBounds,
    TwinExceedAction,
    load_twin_verdict_bounds,
)


@dataclass
class _FakeA2AResponse:
    result: dict[str, Any] | None = None
    error: str | None = None


def _bounds(
    *,
    max_relative_disagreement: float = 0.25,
    action_on_exceed: TwinExceedAction = TwinExceedAction.ESCALATE,
) -> TwinDisagreementBounds:
    """An explicit bound, so these examples do not move when the committed one is
    ratcheted. ``test_committed_bound_is_readable_and_pins_i7`` covers the real file."""
    return TwinDisagreementBounds(
        max_relative_disagreement=max_relative_disagreement,
        relative_floor=0.001,
        action_on_exceed=action_on_exceed,
        measured=False,
    )


def _build_protocol() -> ConsensusProtocol:
    cfg = OrchestratorConfig(postgresql_url="sqlite+aiosqlite:///", pinecone_api_key=None)
    return ConsensusProtocol(
        config=cfg,
        tier_router=MagicMock(),
        guardrails=MagicMock(),
        audit_logger=MagicMock(),
        hitl_escalation=MagicMock(),
        context_builder=MagicMock(),
        ollama_client=MagicMock(),
        meta_rl=MagicMock(**{"get_weights.return_value": {"demand_accuracy": 1.0}}),
        semantic_cache=MagicMock(**{"available": False}),
    )


def _proposal(agent: AgentName, *, degraded: bool) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=uuid4(),
        utility_score=0.8,
        confidence=0.7,
        justification_trace=["p"],
        payload={"action": "x", "provenance": {"degraded": degraded}},
        tier=DecisionTier.TIER_4,
    )


def test_twin_verify_records_monte_carlo_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    proto = _build_protocol()

    async def fake_a2a(
        *, target_url: str, method: str, params: dict[str, Any], timeout: float
    ) -> _FakeA2AResponse:  # noqa: ARG001
        assert target_url == protocol_mod.TWIN_ENDPOINT
        assert method == "monte_carlo"
        assert params["n_scenarios"] == protocol_mod.TWIN_SCENARIOS
        return _FakeA2AResponse(
            result={"n_scenarios": 1000, "kpi_means": {"orders_created": 100.0}}
        )

    monkeypatch.setattr(protocol_mod, "send_a2a_request", fake_a2a)
    decision = proto._build_decision(
        proposals=[], tier=DecisionTier.TIER_4, phase_reached=4, pareto_weights={}
    )
    out, verdict = asyncio.run(proto._phase_twin_verify(decision, bounds=_bounds()))

    assert any("twin=twin_verified" in t for t in out.audit_trace)
    assert verdict.availability is TwinAvailability.VERIFIED
    # `selected_action` is empty here, so no KPI key is comparable: not a
    # disagreement, and therefore not a veto (I-7).
    assert verdict.comparable is False
    assert verdict.exceeds_bound is False
    twin_notes = [
        m for m in proto._context_messages if m.content.get("type") == "twin_verification"
    ]
    assert twin_notes and twin_notes[-1].content["kpi_means"] == {"orders_created": 100.0}


def test_twin_disagreement_beyond_bound_vetoes(monkeypatch: pytest.MonkeyPatch) -> None:
    """R13.4: a measured contradiction beyond the bound is a veto, not a note."""
    proto = _build_protocol()

    async def fake_a2a(**_: Any) -> _FakeA2AResponse:
        # The consensus predicted 100 orders; the twin simulates 10.
        return _FakeA2AResponse(result={"n_scenarios": 1000, "kpi_means": {"orders": 10.0}})

    monkeypatch.setattr(protocol_mod, "send_a2a_request", fake_a2a)
    decision = proto._build_decision(
        proposals=[], tier=DecisionTier.TIER_4, phase_reached=4, pareto_weights={}
    ).model_copy(update={"selected_action": {"orders": 100.0, "action_type": "reorder"}})

    _out, verdict = asyncio.run(proto._phase_twin_verify(decision, bounds=_bounds()))

    assert verdict.disagreement == pytest.approx(0.9)
    assert verdict.compared_kpis == ("orders",)
    assert verdict.exceeds_bound is True
    reason = verdict.veto_reason()
    assert reason.startswith("twin_disagreement:")
    assert "bound:0.25" in reason
    assert reason.endswith("on orders")
    assert "twin_veto=escalate" in _out.audit_trace


def test_twin_agreement_within_bound_does_not_veto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary Monte-Carlo dispersion inside the bound must not withhold dispatch."""
    proto = _build_protocol()

    async def fake_a2a(**_: Any) -> _FakeA2AResponse:
        return _FakeA2AResponse(result={"n_scenarios": 1000, "kpi_means": {"orders": 110.0}})

    monkeypatch.setattr(protocol_mod, "send_a2a_request", fake_a2a)
    decision = proto._build_decision(
        proposals=[], tier=DecisionTier.TIER_4, phase_reached=4, pareto_weights={}
    ).model_copy(update={"selected_action": {"orders": 100.0}})

    _out, verdict = asyncio.run(proto._phase_twin_verify(decision, bounds=_bounds()))

    assert verdict.disagreement == pytest.approx(0.1)
    assert verdict.exceeds_bound is False
    assert verdict.veto_reason() == ""


def test_twin_verify_degrades_when_twin_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    proto = _build_protocol()

    async def boom(**_: Any) -> NoReturn:
        raise ConnectionError("twin down")

    monkeypatch.setattr(protocol_mod, "send_a2a_request", boom)
    decision = proto._build_decision(
        proposals=[], tier=DecisionTier.TIER_4, phase_reached=4, pareto_weights={}
    ).model_copy(update={"selected_action": {"orders": 100.0}})
    # Must NOT raise — an unreachable twin degrades honestly (I-7).
    out, verdict = asyncio.run(proto._phase_twin_verify(decision, bounds=_bounds()))
    assert any("twin=twin_unavailable" in t for t in out.audit_trace)
    # I-7 / ADR-054 D3: absence of a verdict is not a negative verdict. A dead twin
    # must not become a global Tier-4 kill switch.
    assert verdict.availability is TwinAvailability.UNAVAILABLE
    assert verdict.disagreement is None
    assert verdict.exceeds_bound is False


def test_committed_bound_is_readable_and_pins_i7() -> None:
    """AD-13: the bound is committed configuration, and the loader pins I-7."""
    bounds = load_twin_verdict_bounds()
    assert bounds.max_relative_disagreement > 0.0
    assert bounds.relative_floor > 0.0
    assert bounds.action_on_exceed in tuple(TwinExceedAction)


def test_record_input_provenance_flags_degraded_agents() -> None:
    proto = _build_protocol()
    proposals = [
        _proposal(AgentName.DEMAND_PROPHET, degraded=False),
        _proposal(AgentName.PRICING_ORACLE, degraded=True),
    ]
    proto._record_input_provenance(proposals)
    note = proto._context_messages[-1].content
    assert note["type"] == "input_provenance"
    assert note["all_real"] is False
    assert "pricing_oracle" in note["degraded_agents"]
    assert "demand_prophet" not in note["degraded_agents"]


def test_record_input_provenance_all_real_when_no_degraded() -> None:
    proto = _build_protocol()
    proposals = [_proposal(AgentName.DEMAND_PROPHET, degraded=False)]
    proto._record_input_provenance(proposals)
    note = proto._context_messages[-1].content
    assert note["all_real"] is True
    assert note["degraded_agents"] == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
