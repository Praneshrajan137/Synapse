"""Fast-path retention and binding-vs-argmax divergence unit tests.

These exercise the two ends of the selection seam introduced by the binding
Pareto-arbitration work:

* R1.6 — the Tier-1/2 *fast path* must keep selecting the ratified action by a
  raw ``utility_score`` argmax (``_fast_path`` → ``_build_decision(fast_best=...)``).
* R1.2 — the *full path* must NOT select by raw ``utility_score`` argmax; the
  Pareto-knee binding selection drives the ratified action even when the
  knee-weighted winner differs from the raw-argmax winner.

These are example/edge unit tests; the universal properties live in
``test_binding_arbitration_pbt.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.config import OrchestratorConfig
from orchestrator.consensus.pareto import OBJECTIVES, select_binding_action
from orchestrator.consensus.protocol import ConsensusProtocol


def _build_protocol() -> ConsensusProtocol:
    cfg = OrchestratorConfig(
        postgresql_url="sqlite+aiosqlite:///",
        pinecone_api_key=None,
    )
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


def _proposal(agent: AgentName, utility: float, decision_id: object) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=decision_id,  # type: ignore[arg-type]
        utility_score=utility,
        confidence=0.8,
        justification_trace=[f"{agent.value} proposal"],
        payload={"action": f"action_{agent.value}", "utility": utility},
        tier=DecisionTier.TIER_2,
    )


def _equal_weights() -> dict[str, float]:
    return {obj: 1.0 for obj in OBJECTIVES}


class TestFastPathArgmaxRetention:
    """R1.6: Tier-1/2 fast path still selects by raw ``utility_score`` argmax."""

    @pytest.mark.asyncio
    async def test_fast_path_selects_raw_utility_argmax(self) -> None:
        proto = _build_protocol()
        decision_id = uuid4()
        # The highest raw utility_score is the routing_navigator proposal.
        proposals = [
            _proposal(AgentName.DEMAND_PROPHET, 0.40, decision_id),
            _proposal(AgentName.ROUTING_NAVIGATOR, 0.95, decision_id),
            _proposal(AgentName.PRICING_ORACLE, 0.55, decision_id),
        ]

        # Isolate selection: stub the surrounding phases so only the fast-path
        # argmax + _build_decision wiring is under test.
        async def _collect(_request: object, _tier: object) -> list[AgentProposal]:
            return proposals

        async def _execute(decision: object) -> object:
            return decision

        async def _learn(_decision: object) -> None:
            return None

        proto._phase_collect = _collect  # type: ignore[method-assign,assignment]
        proto._phase_execute = _execute  # type: ignore[method-assign,assignment]
        proto._phase_learn = _learn  # type: ignore[method-assign,assignment]

        decision = await proto._fast_path({"city": "bengaluru"}, DecisionTier.TIER_1)

        raw_argmax = max(proposals, key=lambda p: p.utility_score)
        assert raw_argmax.agent_name == AgentName.ROUTING_NAVIGATOR
        assert decision.selected_action == raw_argmax.payload
        assert decision.confidence == raw_argmax.confidence
        # The fast path never runs binding arbitration, so no binding-trace lines.
        assert not any(line.startswith("binding_selected=") for line in decision.audit_trace)

    def test_build_decision_fast_best_keeps_argmax_payload(self) -> None:
        proto = _build_protocol()
        decision_id = uuid4()
        proposals = [
            _proposal(AgentName.DEMAND_PROPHET, 0.30, decision_id),
            _proposal(AgentName.PRICING_ORACLE, 0.88, decision_id),
        ]
        fast_best = max(proposals, key=lambda p: p.utility_score)

        decision = proto._build_decision(
            proposals=proposals,
            tier=DecisionTier.TIER_2,
            phase_reached=4,
            pareto_weights=_equal_weights(),
            fast_best=fast_best,
        )

        assert decision.selected_action == fast_best.payload
        # No binding selection on the fast path → no binding audit lines.
        assert not any("binding" in line for line in decision.audit_trace)


class TestBindingDivergesFromArgmax:
    """R1.2: the full path selects the knee proposal, not the raw argmax."""

    @staticmethod
    def _divergent_case() -> tuple[list[AgentProposal], dict[str, float]]:
        """Craft proposals + knee weights where binding ≠ raw argmax.

        Binding score reduces to ``0.5*Σw + w_own*(utility - 0.5)`` (the shared
        ``Σw`` term cancels in argmax), so the winner is ``argmax w_own*(u-0.5)``.
        ``demand_prophet`` has the higher raw utility, but a knee that weights
        ``pricing_revenue`` heavily flips the binding winner to ``pricing_oracle``.
        """
        decision_id = uuid4()
        proposals = [
            _proposal(AgentName.DEMAND_PROPHET, 0.90, decision_id),  # raw argmax
            _proposal(AgentName.PRICING_ORACLE, 0.70, decision_id),  # knee winner
        ]
        weights = {obj: 1.0 for obj in OBJECTIVES}
        weights["demand_accuracy"] = 0.1
        weights["pricing_revenue"] = 5.0
        return proposals, weights

    def test_selector_picks_knee_not_argmax(self) -> None:
        proposals, weights = self._divergent_case()

        raw_argmax = max(proposals, key=lambda p: p.utility_score)
        assert raw_argmax.agent_name == AgentName.DEMAND_PROPHET

        selection = select_binding_action(proposals, weights)
        # demand_prophet: 0.1*(0.9-0.5)=0.04 ; pricing_oracle: 5.0*(0.7-0.5)=1.0.
        assert selection.selected_agent == AgentName.PRICING_ORACLE.value
        assert selection.selected_index == 1
        assert selection.selected_agent != raw_argmax.agent_name.value

    def test_build_decision_ratifies_knee_proposal(self) -> None:
        proto = _build_protocol()
        proposals, weights = self._divergent_case()
        selection = select_binding_action(proposals, weights)

        decision = proto._build_decision(
            proposals=proposals,
            tier=DecisionTier.TIER_4,
            phase_reached=4,
            pareto_weights=weights,
            selection=selection,
        )

        knee_proposal = proposals[1]
        raw_argmax = max(proposals, key=lambda p: p.utility_score)

        # The ratified action is the knee selection, NOT the raw-argmax proposal.
        assert decision.selected_action == knee_proposal.payload
        assert decision.selected_action != raw_argmax.payload
        # Binding selection is recorded in the append-only audit trace (R2.2).
        assert f"binding_selected={AgentName.PRICING_ORACLE.value}" in decision.audit_trace
