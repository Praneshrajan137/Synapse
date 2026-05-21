# ADR-028: Explainable consensus — rationale + counterfactuals at the Pareto knee

## Status
Accepted (Sprint 7)

## Context
`run_pareto_arbitration(...)` selected a knee point on the Pareto front and
returned the chosen weight vector. It did **not** record:

- the dominated alternatives count,
- the runner-up's per-objective scores,
- the trade-off vector (selected − runner_up),
- the sensitivity (∂selection / ∂weights),
- nor any counterfactual ("what if freshness weight had been ±20 %?").

When a decision was challenged post-hoc — by HITL operators, by regulators,
or by sprint retro — the audit row was insufficient. I-2 (auditability) was
weaker than CLAUDE.md claimed.

## Decision
Two additions, both wired into the audit schema:

1. **`ConsensusRationale`** is computed inside `run_pareto_arbitration` and
   returned as `result["rationale"]`. It records the runner-up scores, the
   trade-off vector, an analytic sensitivity (`2 wᵢ normᵢ²`), the dominated
   alternatives count, and the knee distance. Persisted in
   `audit_consensus.rationale` JSONB.
2. **`orchestrator/consensus/explain.py`** generates counterfactuals for the
   top-K most-sensitive objectives by perturbing each weight ±20 % and
   re-running NSGA-II. Persisted in `audit_consensus.counterfactuals`.

Tier-3 / Tier-4 decisions persist both. Tier-1 / Tier-2 hot paths skip
counterfactuals (cost: O(K × |perturbations|) extra NSGA-II runs).

## Consequences
- Every Tier-3/4 audit row answers "why this and not that?" without
  re-running the orchestrator.
- The `is_decision_sensitive` heuristic flags tight-knee decisions for
  pre-emptive HITL review.
- `proto/domain/consensus_decision.schema.json` gains optional
  `rationale` and `counterfactuals` properties.
- Adds ~50 ms per Tier-3/4 decision for the counterfactual sweep — acceptable.

## Alternatives Rejected
- **SHAP / LIME** — built for ML predictions, not for multi-objective
  optimization knee selection. Wrong tool.
- **LLM-generated explanations** — costs ADR-002 budget and produces
  non-deterministic text; bad for audit reproducibility.
- **Counterfactuals on every tier** — overkill for Tier-1; the budget is
  100 ms total.
