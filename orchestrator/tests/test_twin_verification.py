"""C7 (ADR-043): Tier-4 digital-twin verification + input-provenance recording.

Proves the orchestrator now invokes the digital twin's Monte-Carlo what-if at the
top tier (it was dead code before), records the verdict into the append-only audit
trail, degrades honestly when the twin is unreachable (I-7), and captures whether the
decision rested on real models or degraded fallbacks (ADR-040 substance in the audit).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus import protocol as protocol_mod
from orchestrator.consensus.protocol import ConsensusProtocol


@dataclass
class _FakeA2AResponse:
    result: dict[str, Any] | None = None
    error: str | None = None


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

    async def fake_a2a(*, target_url: str, method: str, params: dict, timeout: float):  # noqa: ANN202, ARG001
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
    out = asyncio.run(proto._phase_twin_verify(decision))

    assert any("twin=twin_verified" in t for t in out.audit_trace)
    twin_notes = [
        m for m in proto._context_messages if m.content.get("type") == "twin_verification"
    ]
    assert twin_notes and twin_notes[-1].content["kpi_means"] == {"orders_created": 100.0}


def test_twin_verify_degrades_when_twin_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    proto = _build_protocol()

    async def boom(**_: Any):  # noqa: ANN202
        raise ConnectionError("twin down")

    monkeypatch.setattr(protocol_mod, "send_a2a_request", boom)
    decision = proto._build_decision(
        proposals=[], tier=DecisionTier.TIER_4, phase_reached=4, pareto_weights={}
    )
    # Must NOT raise — an unreachable twin degrades honestly (I-7).
    out = asyncio.run(proto._phase_twin_verify(decision))
    assert any("twin=twin_unavailable" in t for t in out.audit_trace)


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
