"""ADR-052 end-to-end: binding Pareto arbitration overrides raw-``argmax`` (R9.6).

Drives a FULL Tier-3 decision through the real ``ConsensusProtocol.run_consensus``
pipeline (collect → arbitrate → build → execute → learn) with only the network
seams stubbed: the agent A2A ``proposal``/``execute`` calls and the NSGA-II
``run_pareto_arbitration`` are replaced with deterministic in-process fakes.

What it proves: when the highest-``utility_score`` proposal is NOT the Pareto-knee
selection, the ratified ``selected_action`` is the knee-selected payload and DIFFERS
from the raw-``argmax`` proposal's payload — the knee weights actually govern the
decision instead of being discarded for a raw ``argmax`` (R1.1/R1.2/R9.6).

The divergence construction mirrors ``orchestrator/tests/consensus/test_binding_fastpath.py``:
``demand_prophet`` carries the higher raw utility while a ``pricing_revenue``-weighted
knee flips the binding winner to ``pricing_oracle``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from synapse_common.a2a_sdk import A2AResponse
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus.models import TierClassification
from orchestrator.consensus.pareto import OBJECTIVES
from orchestrator.consensus.protocol import AGENT_ENDPOINTS, ConsensusProtocol

# Reverse map so the stubbed A2A transport can resolve the requested agent from
# the target URL the protocol dials (mirrors AGENT_ENDPOINTS in protocol.py).
_URL_TO_AGENT: dict[str, str] = {url: name for name, url in AGENT_ENDPOINTS.items()}


def _proposal(agent: AgentName, utility: float, decision_id: object) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=decision_id,  # type: ignore[arg-type]
        utility_score=utility,
        confidence=0.8,
        justification_trace=[f"{agent.value} proposal"],
        payload={"action": f"action_{agent.value}", "utility": utility},
        tier=DecisionTier.TIER_3,
    )


def _divergent_case() -> tuple[dict[str, AgentProposal], dict[str, float]]:
    """Craft proposals + knee weights where binding selection != raw ``argmax``.

    Binding score reduces to ``argmax w_own*(utility - 0.5)`` (the shared ``Σw``
    term cancels), so ``demand_prophet`` wins the raw ``utility_score`` race while a
    knee that weights ``pricing_revenue`` heavily flips the binding winner to
    ``pricing_oracle``.
    """
    decision_id = uuid4()
    proposals = {
        AgentName.DEMAND_PROPHET.value: _proposal(
            AgentName.DEMAND_PROPHET, 0.90, decision_id
        ),  # raw argmax
        AgentName.PRICING_ORACLE.value: _proposal(
            AgentName.PRICING_ORACLE, 0.70, decision_id
        ),  # knee winner
    }
    weights = {obj: 1.0 for obj in OBJECTIVES}
    weights["demand_accuracy"] = 0.1
    weights["pricing_revenue"] = 5.0
    return proposals, weights


def _build_protocol() -> ConsensusProtocol:
    cfg = OrchestratorConfig(
        postgresql_url="sqlite+aiosqlite:///",
        pinecone_api_key=None,
    )
    # Tier-3 routing → the full path (collect → arbitrate → execute → learn); no LLM
    # model so the (unreached) debate phase never dials an Ollama backend.
    tier_router = MagicMock()
    tier_router.classify.return_value = TierClassification(
        tier=DecisionTier.TIER_3,
        confidence=0.9,
        reasons=["e2e binding divergence"],
        model=None,
        latency_budget_ms=60_000,
    )
    return ConsensusProtocol(
        config=cfg,
        tier_router=tier_router,
        guardrails=MagicMock(**{"validate_decision.return_value": (True, [])}),
        audit_logger=MagicMock(log_decision=AsyncMock(return_value=uuid4())),
        hitl_escalation=MagicMock(),
        context_builder=MagicMock(),
        ollama_client=MagicMock(),
        meta_rl=MagicMock(**{"get_weights.return_value": {obj: 1.0 for obj in OBJECTIVES}}),
        semantic_cache=MagicMock(
            available=False, store_decision=AsyncMock(return_value=None)
        ),
    )


@pytest.mark.asyncio
async def test_binding_arbitration_overrides_argmax_e2e() -> None:
    proposals_by_agent, knee_weights = _divergent_case()
    proto = _build_protocol()

    # Stub the A2A transport: `proposal` returns the two crafted proposals (every
    # other agent is honestly unavailable), `execute` reports an applied effect.
    async def _fake_send_a2a_request(
        *, target_url: str, method: str, **_kwargs: Any
    ) -> A2AResponse:
        if method == "proposal":
            agent = _URL_TO_AGENT.get(target_url, "")
            proposal = proposals_by_agent.get(agent)
            if proposal is None:
                return A2AResponse(error={"message": f"{agent} unavailable"}, id="rpc")
            return A2AResponse(result=proposal.model_dump(mode="json"), id="rpc")
        if method == "execute":
            return A2AResponse(result={"status": "executed"}, id="rpc")
        return A2AResponse(result={}, id="rpc")

    # Stub NSGA-II so the knee weights are the crafted divergent vector — the real
    # binding selector (`select_binding_action`) still runs on the real proposals.
    def _fake_run_pareto_arbitration(
        _proposals: list[AgentProposal], _weights: dict[str, float]
    ) -> dict[str, Any]:
        return {
            "selected_weights": knee_weights,
            "pareto_front": [],
            "knee_index": 0,
            "n_solutions": 1,
        }

    import orchestrator.consensus.protocol as protocol_module

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(protocol_module, "send_a2a_request", _fake_send_a2a_request)
        mp.setattr(protocol_module, "run_pareto_arbitration", _fake_run_pareto_arbitration)

        decision = await proto.run_consensus({"city": "bengaluru"})

    knee_payload = proposals_by_agent[AgentName.PRICING_ORACLE.value].payload
    argmax_payload = proposals_by_agent[AgentName.DEMAND_PROPHET.value].payload

    # The full path was taken (Tier 3, both proposals collected and arbitrated).
    assert decision.tier == DecisionTier.TIER_3
    assert {str(p.agent_name) for p in decision.proposals} == {
        AgentName.DEMAND_PROPHET.value,
        AgentName.PRICING_ORACLE.value,
    }

    # R9.6: the ratified action is the Pareto-knee selection, NOT the raw-argmax one.
    assert decision.selected_action == knee_payload
    assert decision.selected_action != argmax_payload

    # The divergence is real: demand_prophet held the higher raw utility_score.
    raw_argmax = max(decision.proposals, key=lambda p: p.utility_score)
    assert raw_argmax.agent_name == AgentName.DEMAND_PROPHET
    assert raw_argmax.payload == argmax_payload

    # The binding selection is recorded in the append-only audit trace (R2.2).
    assert f"binding_selected={AgentName.PRICING_ORACLE.value}" in decision.audit_trace
