"""Layer 5 (DbC) + Layer 4 (Metamorphic) for the Pareto knee selector.

Covers WS-7.2 (DbC contracts on `run_pareto_arbitration`) and WS-7.5
(`ConsensusRationale` + counterfactual sweep). ADR-028.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import deal
import pytest

from orchestrator.consensus.explain import (
    generate_counterfactuals,
    grid_sensitivity,
    is_decision_sensitive,
)
from orchestrator.consensus.pareto import (
    DEFAULT_WEIGHTS,
    OBJECTIVES,
    run_pareto_arbitration,
)
from synapse_common.models import (
    AgentName,
    AgentProposal,
    DecisionTier,
)

pytestmark = pytest.mark.dbc


def _proposal(agent: AgentName, utility: float = 0.8) -> AgentProposal:
    return AgentProposal(
        agent_name=agent,
        decision_id=uuid4(),
        utility_score=utility,
        confidence=0.9,
        justification_trace=["dbc-test"],
        payload={},
        tier=DecisionTier.TIER_3,
    )


def _eight_proposals() -> list[AgentProposal]:
    return [_proposal(a, 0.7 + 0.02 * i) for i, a in enumerate(AgentName)]


# -- Contracts --------------------------------------------------------------


def test_pre_rejects_empty_proposals() -> None:
    with pytest.raises(deal.PreContractError):
        run_pareto_arbitration([], DEFAULT_WEIGHTS)


def test_pre_rejects_zero_pop_size() -> None:
    with pytest.raises(deal.PreContractError):
        run_pareto_arbitration(_eight_proposals(), DEFAULT_WEIGHTS, pop_size=0)


def test_pre_rejects_zero_n_gen() -> None:
    with pytest.raises(deal.PreContractError):
        run_pareto_arbitration(_eight_proposals(), DEFAULT_WEIGHTS, n_gen=0)


def test_post_returns_well_formed_result() -> None:
    """Post-contract: the keystone shape every downstream consumer relies on."""
    result = run_pareto_arbitration(_eight_proposals(), DEFAULT_WEIGHTS, pop_size=12, n_gen=8)
    assert "selected_weights" in result
    assert "pareto_front" in result
    assert "rationale" in result
    assert 0 <= result["knee_index"] < result["n_solutions"]


# -- Rationale (ADR-028) ----------------------------------------------------


def test_rationale_has_required_fields() -> None:
    result = run_pareto_arbitration(_eight_proposals(), DEFAULT_WEIGHTS, pop_size=12, n_gen=8)
    rationale: dict[str, Any] = result["rationale"]
    for key in (
        "selected_scores",
        "runner_up_scores",
        "tradeoff_vector",
        "sensitivity",
        "dominated_alternatives",
        "knee_distance",
        "weights_used",
    ):
        assert key in rationale, f"missing rationale key: {key}"


def test_rationale_covers_every_objective() -> None:
    result = run_pareto_arbitration(_eight_proposals(), DEFAULT_WEIGHTS, pop_size=12, n_gen=8)
    for axis in (
        "selected_scores",
        "runner_up_scores",
        "tradeoff_vector",
        "sensitivity",
    ):
        d = result["rationale"][axis]
        assert set(d.keys()) == set(OBJECTIVES), f"{axis} missing objectives: {d.keys()}"


def test_rationale_dominated_alternatives_is_nonneg() -> None:
    result = run_pareto_arbitration(_eight_proposals(), DEFAULT_WEIGHTS, pop_size=12, n_gen=8)
    assert result["rationale"]["dominated_alternatives"] >= 0


def test_knee_distance_nonneg() -> None:
    result = run_pareto_arbitration(_eight_proposals(), DEFAULT_WEIGHTS, pop_size=12, n_gen=8)
    assert result["rationale"]["knee_distance"] >= 0.0


# -- Counterfactuals --------------------------------------------------------


def test_counterfactuals_emits_perturbation_per_top_objective() -> None:
    proposals = _eight_proposals()
    out = generate_counterfactuals(
        proposals, DEFAULT_WEIGHTS, perturbations=(-0.2, 0.2), top_k=2
    )
    # 2 objectives × 2 perturbations = 4 records.
    assert len(out) == 4
    for row in out:
        assert "objective" in row
        assert "delta" in row
        assert "flipped" in row
        assert "biggest_shift" in row


def test_counterfactuals_pre_rejects_zero_top_k() -> None:
    with pytest.raises(deal.PreContractError):
        generate_counterfactuals(_eight_proposals(), DEFAULT_WEIGHTS, top_k=0)


def test_counterfactuals_pre_rejects_empty_proposals() -> None:
    with pytest.raises(deal.PreContractError):
        generate_counterfactuals([], DEFAULT_WEIGHTS)


def test_grid_sensitivity_returns_one_row_per_grid_point() -> None:
    rows = grid_sensitivity(
        _eight_proposals(),
        DEFAULT_WEIGHTS,
        objective="freshness_score",
        grid=(0.5, 1.0, 1.5),
    )
    assert len(rows) == 3
    for row in rows:
        assert "multiplier" in row
        assert "knee_index" in row
        assert "knee_distance" in row


def test_is_decision_sensitive_threshold_validation() -> None:
    with pytest.raises(deal.PreContractError):
        is_decision_sensitive({"knee_distance": 0.1}, threshold=0.0)
    with pytest.raises(deal.PreContractError):
        is_decision_sensitive({"knee_distance": 0.1}, threshold=1.0)


def test_is_decision_sensitive_flags_close_knee() -> None:
    assert is_decision_sensitive({"knee_distance": 0.01}, threshold=0.05) is True
    assert is_decision_sensitive({"knee_distance": 0.5}, threshold=0.05) is False


# -- Metamorphic (ADR-015 Layer 4) ------------------------------------------


def test_metamorphic_weight_perturbation_continuity() -> None:
    """Tiny weight perturbations must not flip the knee — continuity check."""
    proposals = _eight_proposals()
    base = run_pareto_arbitration(proposals, DEFAULT_WEIGHTS, pop_size=20, n_gen=15)

    nudged = dict(DEFAULT_WEIGHTS)
    nudged["freshness_score"] = nudged["freshness_score"] * 1.001  # 0.1 % change
    alt = run_pareto_arbitration(proposals, nudged, pop_size=20, n_gen=15)

    # Same NSGA-II seed (=42) with same proposals → identical front.
    # A 0.1 % nudge to one weight may shift the knee by at most one rank.
    assert abs(alt["knee_index"] - base["knee_index"]) <= 1
