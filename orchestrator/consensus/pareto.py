"""
SYNAPSE Orchestrator — Pareto arbitration via NSGA-II (pymoo).

Given N agent proposals each evaluated against 8 objectives, finds the
Pareto-optimal weight vector and selects the knee point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
import structlog
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.optimize import minimize

if TYPE_CHECKING:
    from synapse_common.models import AgentProposal

# Float matrices/vectors throughout the NSGA-II arbitration. Parametrised so
# `mypy --strict` is satisfied (bare `np.ndarray` is a missing-type-args error).
FloatArray = npt.NDArray[np.float64]

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


@dataclass(frozen=True)
class BindingSelection:
    """Deterministic, auditable outcome of binding Pareto-knee selection.

    Attributes:
        selected_agent: Mapped agent of the winning proposal; ``None`` when no
            eligible candidate exists.
        selected_index: Index into the *input* ``proposals`` list of the winner;
            ``None`` when no eligible candidate exists.
        weighted_scores: ``agent_name -> Σ knee_weight[obj]·utility`` for every
            *evaluated* (eligible) candidate. Recorded for audit (R2.2).
        excluded_agents: Candidates with no ``_AGENT_TO_OBJECTIVE`` entry; these
            are recorded without a fabricated score (R1.5, I-7).
        tie_break_applied: ``True`` when two or more eligible candidates tied on
            weighted score within ``tolerance`` and a deterministic tie-break ran.
        tie_break_reason: Empty string when no tie occurred; otherwise the
            deterministic outcome, e.g. ``"objective_order:demand_accuracy"`` or
            ``"agent_name:demand_prophet"`` (R2.5).
    """

    selected_agent: str | None
    selected_index: int | None
    weighted_scores: dict[str, float]
    excluded_agents: list[str]
    tie_break_applied: bool
    tie_break_reason: str


def select_binding_action(
    proposals: list[AgentProposal],
    knee_weights: dict[str, float],
    *,
    neutral_baseline: float = 0.5,
    tolerance: float = 1e-9,
) -> BindingSelection:
    """Select the ratified action by applying Pareto-knee weights (pure).

    For each proposal, the per-objective utility vector mirrors
    ``_build_utility_matrix``: the agent's own objective contributes its
    ``utility_score`` and every other objective contributes ``neutral_baseline``
    (0.5). The weighted score therefore collapses to::

        score = knee_weight[own_obj]·utility_score
              + neutral_baseline · Σ_{obj ≠ own_obj} knee_weight[obj]

    The eligible proposal with the highest score is selected. Ties (scores equal
    within ``tolerance``) are broken deterministically by preferring the proposal
    whose mapped objective appears earliest in ``OBJECTIVES``, then by ascending
    agent name (R1.4). Proposals whose agent has no ``_AGENT_TO_OBJECTIVE`` entry
    are excluded without a fabricated score (R1.5, I-7).

    This function is pure: it performs no I/O and mutates no globals, so repeated
    evaluation with identical inputs yields the identical result (R2.1).
    """
    weighted_scores: dict[str, float] = {}
    excluded_agents: list[str] = []
    # Each eligible entry: (original_index, agent_name, objective, score).
    eligible: list[tuple[int, str, str, float]] = []

    for index, proposal in enumerate(proposals):
        agent_name = str(proposal.agent_name)
        objective = _AGENT_TO_OBJECTIVE.get(agent_name)
        if objective is None:
            excluded_agents.append(agent_name)
            continue
        own_weight = knee_weights.get(objective, 0.0)
        others_weight = sum(knee_weights.get(obj, 0.0) for obj in OBJECTIVES if obj != objective)
        score = own_weight * float(proposal.utility_score) + neutral_baseline * others_weight
        weighted_scores[agent_name] = score
        eligible.append((index, agent_name, objective, score))

    if not eligible:
        return BindingSelection(
            selected_agent=None,
            selected_index=None,
            weighted_scores=weighted_scores,
            excluded_agents=excluded_agents,
            tie_break_applied=False,
            tie_break_reason="",
        )

    # Stable sort over (-score, OBJECTIVES.index(obj), agent_name) so selection
    # is identical across runs and processes (R1.4, R2.1).
    eligible.sort(key=lambda entry: (-entry[3], OBJECTIVES.index(entry[2]), entry[1]))

    winner_index, winner_agent, winner_obj, winner_score = eligible[0]

    # A tie occurred when another eligible candidate's score equals the winner's
    # within tolerance. Determine which deterministic rule resolved it.
    tied = [entry for entry in eligible if abs(entry[3] - winner_score) <= tolerance]
    tie_break_applied = len(tied) > 1
    tie_break_reason = ""
    if tie_break_applied:
        _, runner_agent, runner_obj, _ = eligible[1]
        if OBJECTIVES.index(winner_obj) < OBJECTIVES.index(runner_obj):
            tie_break_reason = f"objective_order:{winner_obj}"
        else:
            tie_break_reason = f"agent_name:{winner_agent}"

    return BindingSelection(
        selected_agent=winner_agent,
        selected_index=winner_index,
        weighted_scores=weighted_scores,
        excluded_agents=excluded_agents,
        tie_break_applied=tie_break_applied,
        tie_break_reason=tie_break_reason,
    )


def _build_utility_matrix(proposals: list[AgentProposal]) -> FloatArray:
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


class _WeightOptProblem(Problem):  # type: ignore[misc]  # pymoo ships no type stubs
    """Optimise the 8-D weight vector that blends proposal utilities."""

    def __init__(self, utility_matrix: FloatArray) -> None:
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
        X: FloatArray,  # noqa: N803
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


def run_pareto_arbitration(
    proposals: list[AgentProposal],
    weight_vector: dict[str, float],
    pop_size: int = 50,
    n_gen: int = 100,
) -> dict[str, Any]:
    """Run NSGA-II and return Pareto front with knee-point selection."""
    utility_matrix = _build_utility_matrix(proposals)

    problem = _WeightOptProblem(utility_matrix)
    algorithm = NSGA2(pop_size=pop_size)
    result = minimize(problem, algorithm, ("n_gen", n_gen), seed=42, verbose=False)

    pareto_front: FloatArray = result.F
    pareto_solutions: FloatArray = result.X

    # Knee-point selection: weighted distance to ideal
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

    logger.info(
        "pareto_arbitration_complete",
        n_proposals=len(proposals),
        pareto_front_size=len(pareto_front),
        knee_index=knee_idx,
    )

    return {
        "selected_weights": selected_weights,
        "pareto_front": [
            dict(zip(OBJECTIVES, (-row).tolist(), strict=False)) for row in pareto_front
        ],
        "knee_index": knee_idx,
        "n_solutions": len(pareto_front),
    }
