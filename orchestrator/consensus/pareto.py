"""
SYNAPSE Orchestrator — Pareto arbitration via NSGA-II (pymoo).

Given N agent proposals each evaluated against 8 objectives, finds the
Pareto-optimal weight vector and selects the knee point.

Sprint-7 elevation:
  * Returns a structured `ConsensusRationale` (ADR-028): dominated count,
    selected vs runner-up scores, trade-off vector, and weight-sensitivity.
  * Pre/post contracts (ADR-015 Layer 5) enforce input shape and result
    completeness at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import structlog
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.optimize import minimize

from synapse_common.dbc import post, pre

if TYPE_CHECKING:
    from synapse_common.models import AgentProposal

logger = structlog.get_logger(__name__)

OBJECTIVES: list[str] = [
    "demand_accuracy",
    "route_efficiency",
    "inventory_fill_rate",
    "freshness_score",
    "pricing_revenue",
    "disruption_readiness",
    "supplier_reliability",
    "carbon_efficiency",
]

DEFAULT_WEIGHTS: dict[str, float] = {
    "demand_accuracy": 1.0,
    "route_efficiency": 1.0,
    "inventory_fill_rate": 1.2,
    "freshness_score": 1.0,
    "pricing_revenue": 0.8,
    "disruption_readiness": 1.0,
    "supplier_reliability": 0.8,
    "carbon_efficiency": 0.6,
}

_AGENT_TO_OBJECTIVE: dict[str, str] = {
    "demand_prophet": "demand_accuracy",
    "routing_navigator": "route_efficiency",
    "inventory_sentinel": "inventory_fill_rate",
    "freshness_guardian": "freshness_score",
    "pricing_oracle": "pricing_revenue",
    "disruption_shield": "disruption_readiness",
    "supplier_trust": "supplier_reliability",
    "sustainability_agent": "carbon_efficiency",
}


def _build_utility_matrix(proposals: list[AgentProposal]) -> np.ndarray:
    """Build an (N x 8) utility matrix from agent proposals.

    Each row is one proposal evaluated against all 8 objectives.  The diagonal
    entry (the agent's own objective) uses its ``utility_score``; cross-entries
    use a neutral 0.5 baseline to avoid penalising agents for objectives they
    do not optimise.
    """
    n = len(proposals)
    matrix = np.full((n, 8), 0.5, dtype=np.float64)
    for i, proposal in enumerate(proposals):
        agent_key = str(proposal.agent_name)
        if agent_key in _AGENT_TO_OBJECTIVE:
            obj_idx = OBJECTIVES.index(_AGENT_TO_OBJECTIVE[agent_key])
            matrix[i, obj_idx] = float(proposal.utility_score)
    return matrix


class _WeightOptProblem(Problem):
    """Optimise the 8-D weight vector that blends proposal utilities."""

    def __init__(self, utility_matrix: np.ndarray) -> None:
        super().__init__(
            n_var=8,
            n_obj=8,
            n_constr=0,
            xl=0.01,
            xu=2.0,
        )
        self._U = utility_matrix  # (N, 8)

    def _evaluate(
        self,
        X: np.ndarray,  # noqa: N803
        out: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # X shape: (pop_size, 8) — candidate weight vectors
        # For each weight vector, compute weighted utility per objective
        F = np.zeros((X.shape[0], 8))  # noqa: N806
        for i, w in enumerate(X):
            normalised_w = w / (w.sum() + 1e-12)
            blended = self._U.T @ np.ones(self._U.shape[0])  # sum across proposals
            F[i] = -(normalised_w * blended)  # negate for minimisation
        out["F"] = F


def _build_rationale(
    pareto_front: np.ndarray,
    weighted_dist: np.ndarray,
    knee_idx: int,
    weights: dict[str, float],
) -> dict[str, Any]:
    """Construct a ConsensusRationale dict (ADR-028).

    `pareto_front` rows are negated objective values (minimised). We invert here
    so all reported scores are in the natural "higher is better" frame.
    """
    n = pareto_front.shape[0]
    selected_neg = pareto_front[knee_idx]
    selected_pos = (-selected_neg).tolist()

    # Runner-up = next-closest knee candidate by weighted_dist.
    if n > 1:
        order = np.argsort(weighted_dist)
        runner_up_idx = int(order[1])
        runner_up_pos = (-pareto_front[runner_up_idx]).tolist()
    else:
        runner_up_idx = knee_idx
        runner_up_pos = selected_pos

    # Trade-off: per-objective gap (selected - runner_up). Positive = selected
    # better on that objective; negative = it traded that objective away.
    tradeoff = [selected_pos[i] - runner_up_pos[i] for i in range(len(OBJECTIVES))]

    # Sensitivity: ∂selection / ∂weight, approximated by the partial derivative
    # of weighted_dist with respect to each weight at the knee. We compute it
    # analytically: dist² = Σ (wᵢ * normalisedᵢ)² → ∂(dist²)/∂wᵢ = 2 wᵢ normᵢ².
    ideal = pareto_front.min(axis=0)
    nadir = pareto_front.max(axis=0)
    denom = nadir - ideal + 1e-8
    normalised = (pareto_front[knee_idx] - ideal) / denom
    weight_arr = np.array([weights.get(o, 1.0) for o in OBJECTIVES], dtype=np.float64)
    sensitivity = (2.0 * weight_arr * (normalised**2)).tolist()

    return {
        "selected_scores": dict(zip(OBJECTIVES, selected_pos, strict=False)),
        "runner_up_scores": dict(zip(OBJECTIVES, runner_up_pos, strict=False)),
        "tradeoff_vector": dict(zip(OBJECTIVES, tradeoff, strict=False)),
        "sensitivity": dict(zip(OBJECTIVES, sensitivity, strict=False)),
        "dominated_alternatives": max(0, n - 1),
        "knee_distance": float(weighted_dist[knee_idx]),
        "weights_used": dict(weights),
    }


@pre(lambda proposals, weight_vector, pop_size=50, n_gen=100: len(proposals) > 0)
@pre(lambda proposals, weight_vector, pop_size=50, n_gen=100: pop_size > 0 and n_gen > 0)
@post(
    lambda result: (
        "selected_weights" in result
        and "pareto_front" in result
        and "rationale" in result
        and 0 <= result["knee_index"] < result["n_solutions"]
    )
)
def run_pareto_arbitration(
    proposals: list[AgentProposal],
    weight_vector: dict[str, float],
    pop_size: int = 50,
    n_gen: int = 100,
) -> dict[str, Any]:
    """Run NSGA-II and return Pareto front + knee-point selection + rationale.

    The returned `rationale` (ADR-028) is the audit-trail anchor for I-2: every
    Tier-3/4 decision must persist it so post-hoc challenges are answerable.
    """
    utility_matrix = _build_utility_matrix(proposals)

    problem = _WeightOptProblem(utility_matrix)
    algorithm = NSGA2(pop_size=pop_size)
    result = minimize(problem, algorithm, ("n_gen", n_gen), seed=42, verbose=False)

    pareto_front: np.ndarray = result.F
    pareto_solutions: np.ndarray = result.X

    ideal = pareto_front.min(axis=0)
    nadir = pareto_front.max(axis=0)
    denom = nadir - ideal + 1e-8
    normalised = (pareto_front - ideal) / denom

    weights_arr = np.array(
        [weight_vector.get(obj, 1.0) for obj in OBJECTIVES],
        dtype=np.float64,
    )
    weighted_dist = np.sqrt(np.sum((normalised * weights_arr) ** 2, axis=1))
    knee_idx = int(np.argmin(weighted_dist))

    selected_raw = pareto_solutions[knee_idx]
    selected_normalised = selected_raw / (selected_raw.sum() + 1e-12) * 8.0
    selected_weights = dict(zip(OBJECTIVES, selected_normalised.tolist(), strict=False))

    rationale = _build_rationale(pareto_front, weighted_dist, knee_idx, weight_vector)

    logger.info(
        "pareto_arbitration_complete",
        n_proposals=len(proposals),
        pareto_front_size=len(pareto_front),
        knee_index=knee_idx,
        knee_distance=rationale["knee_distance"],
    )

    return {
        "selected_weights": selected_weights,
        "pareto_front": [
            dict(zip(OBJECTIVES, (-row).tolist(), strict=False)) for row in pareto_front
        ],
        "knee_index": knee_idx,
        "n_solutions": len(pareto_front),
        "rationale": rationale,
    }
