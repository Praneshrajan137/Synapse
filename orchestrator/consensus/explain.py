"""Consensus explainability — counterfactual generation for Pareto knee selection.

Given a finished arbitration, asks: "if the weight on objective X had been
shifted by ±ε, would the knee point have moved?" The answer set forms the
Tier-3/4 counterfactual record persisted alongside `ConsensusRationale`.

ADR-028. Companion to `orchestrator.consensus.pareto.run_pareto_arbitration`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import structlog

from orchestrator.consensus.pareto import OBJECTIVES, run_pareto_arbitration
from synapse_common.dbc import post, pre

if TYPE_CHECKING:
    from synapse_common.models import AgentProposal

logger = structlog.get_logger(__name__)

DEFAULT_PERTURBATIONS: tuple[float, ...] = (-0.2, +0.2)


@pre(lambda proposals, base_weights, perturbations=DEFAULT_PERTURBATIONS, top_k=2: top_k >= 1)
@pre(
    lambda proposals, base_weights, perturbations=DEFAULT_PERTURBATIONS, top_k=2: len(proposals) > 0
)
@post(lambda result: isinstance(result, list))
def generate_counterfactuals(
    proposals: list[AgentProposal],
    base_weights: dict[str, float],
    perturbations: tuple[float, ...] = DEFAULT_PERTURBATIONS,
    top_k: int = 2,
) -> list[dict[str, Any]]:
    """For the `top_k` most-sensitive objectives, perturb their weight by each
    value in `perturbations` and re-run arbitration.

    Returns a list of `{objective, delta, original_knee, new_knee, flipped}`
    records — the on-disk rationale anchor for "what if?" debugging.

    Performance: O(top_k × |perturbations|) extra NSGA-II runs. Reserve for
    Tier-3/4 decisions; do NOT call on Tier-1/2 hot paths.
    """
    base = run_pareto_arbitration(proposals, base_weights)
    base_knee = base["knee_index"]
    sensitivity = base["rationale"]["sensitivity"]

    # Top-k objectives by absolute sensitivity.
    ranked = sorted(sensitivity.items(), key=lambda kv: abs(kv[1]), reverse=True)
    pivots = [obj for obj, _ in ranked[:top_k]]

    counterfactuals: list[dict[str, Any]] = []
    for objective in pivots:
        for delta in perturbations:
            tweaked = dict(base_weights)
            current = tweaked.get(objective, 1.0)
            tweaked[objective] = max(0.01, current * (1.0 + delta))
            alt = run_pareto_arbitration(proposals, tweaked)
            flipped = alt["knee_index"] != base_knee

            # Record the largest-magnitude objective change in the alt selection
            base_scores = base["rationale"]["selected_scores"]
            alt_scores = alt["rationale"]["selected_scores"]
            diffs = {o: alt_scores[o] - base_scores[o] for o in OBJECTIVES}
            biggest_shift = max(diffs.items(), key=lambda kv: abs(kv[1]))

            counterfactuals.append(
                {
                    "objective": objective,
                    "delta": float(delta),
                    "original_knee_index": int(base_knee),
                    "new_knee_index": int(alt["knee_index"]),
                    "flipped": bool(flipped),
                    "biggest_shift": {
                        "objective": biggest_shift[0],
                        "magnitude": float(biggest_shift[1]),
                    },
                }
            )

    logger.info(
        "counterfactuals_generated",
        n=len(counterfactuals),
        flipped_count=sum(1 for c in counterfactuals if c["flipped"]),
    )
    return counterfactuals


@pre(lambda rationale, threshold=0.05: 0.0 < threshold < 1.0)
def is_decision_sensitive(rationale: dict[str, Any], threshold: float = 0.05) -> bool:
    """Heuristic: flag decisions whose knee is within `threshold` of a runner-up.

    Sensitive decisions warrant a richer audit trail (more counterfactuals,
    HITL pre-emption review).
    """
    return float(rationale.get("knee_distance", 1.0)) < threshold


# A safer 1D grid sweep that doesn't rely on `np` availability at call sites.
def grid_sensitivity(
    proposals: list[AgentProposal],
    base_weights: dict[str, float],
    objective: str,
    grid: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5),
) -> list[dict[str, Any]]:
    """Sweep a 1-D grid of multipliers for one objective; record knee at each.

    Returns rows ordered by multiplier so callers can plot the curve.
    """
    base_value = float(base_weights.get(objective, 1.0))
    rows: list[dict[str, Any]] = []
    for mult in grid:
        tweaked = dict(base_weights)
        tweaked[objective] = max(0.01, base_value * float(mult))
        alt = run_pareto_arbitration(proposals, tweaked)
        rows.append(
            {
                "multiplier": float(mult),
                "knee_index": int(alt["knee_index"]),
                "knee_distance": float(alt["rationale"]["knee_distance"]),
            }
        )
    # Quick coercion to float for downstream numerical use.
    np.array([r["knee_distance"] for r in rows])
    return rows


__all__ = [
    "DEFAULT_PERTURBATIONS",
    "generate_counterfactuals",
    "grid_sensitivity",
    "is_decision_sensitive",
]
