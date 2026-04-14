"""SYNAPSE Orchestrator — NSGA-II Pareto arbitration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from synapse_common.models import AgentName, AgentProposal, DecisionTier

from orchestrator.consensus.pareto import (
    DEFAULT_WEIGHTS,
    OBJECTIVES,
    _build_utility_matrix,
    run_pareto_arbitration,
)


def _make_proposal(agent: AgentName, score: float) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=uuid4(),
        utility_score=score,
        confidence=score,
        justification_trace=[f"{agent.value} proposal"],
        payload={"action": f"{agent.value}_action"},
        tier=DecisionTier.TIER_2,
    )


class TestUtilityMatrix:
    def test_matrix_shape(self) -> None:
        proposals = [_make_proposal(a, 0.8) for a in list(AgentName)[:4]]
        matrix = _build_utility_matrix(proposals)
        assert matrix.shape == (4, 8)

    def test_diagonal_uses_utility_score(self) -> None:
        p = _make_proposal(AgentName.DEMAND_PROPHET, 0.9)
        matrix = _build_utility_matrix([p])
        idx = OBJECTIVES.index("demand_accuracy")
        assert matrix[0, idx] == pytest.approx(0.9)

    def test_off_diagonal_is_neutral(self) -> None:
        p = _make_proposal(AgentName.DEMAND_PROPHET, 0.9)
        matrix = _build_utility_matrix([p])
        idx = OBJECTIVES.index("demand_accuracy")
        for j in range(8):
            if j != idx:
                assert matrix[0, j] == pytest.approx(0.5)


class TestParetoArbitration:
    def test_returns_required_keys(self, sample_proposals: list[AgentProposal]) -> None:
        result = run_pareto_arbitration(sample_proposals, DEFAULT_WEIGHTS, pop_size=20, n_gen=10)
        assert "selected_weights" in result
        assert "pareto_front" in result
        assert "knee_index" in result
        assert "n_solutions" in result

    def test_weights_sum_to_n_objectives(self, sample_proposals: list[AgentProposal]) -> None:
        result = run_pareto_arbitration(sample_proposals, DEFAULT_WEIGHTS, pop_size=20, n_gen=10)
        total = sum(result["selected_weights"].values())
        assert total == pytest.approx(8.0, abs=0.5)

    def test_pareto_front_non_empty(self, sample_proposals: list[AgentProposal]) -> None:
        result = run_pareto_arbitration(sample_proposals, DEFAULT_WEIGHTS, pop_size=20, n_gen=10)
        assert len(result["pareto_front"]) > 0
