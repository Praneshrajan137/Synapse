# ADR-031: Spec-Driven Reward Weights — Shadow Mode (Phase 1)

## Status
Accepted (Sprint 8, 2026-05-17)

## Context

Reward weights in `agents/<name>/training/rewards.py` are currently
hardcoded kwargs (e.g.
[agents/demand_prophet/training/rewards.py:79-81](agents/demand_prophet/training/rewards.py:79-81)).
A weight change is a one-line Python edit with no review trail and no
visibility from `agents/<name>/spec.yaml`. The Sprint-7 ADR-027 phase-1
committed to promoting spec.yaml to source-of-truth for reward weights
across Sprint 8/9, but a direct cutover is risky: a typo in spec.yaml
silently changes RL training behaviour.

## Decision

**Sprint 8 ships shadow mode.** Three pieces:

1. **`reward:` block in every `agents/*/spec.yaml`.** Schema extended
   in [docs/specs/agent_spec_schema.json](docs/specs/agent_spec_schema.json:103);
   `weights` is required, `scale` and `notes` optional. Six agents
   ship real weights; `inventory_sentinel` and `supplier_trust` ship
   empty `weights: {}` placeholders until Sprint 9 promotes their
   inline magic numbers to named weights.
2. **`agents/<name>/training/reward_config.py` auto-generated** from
   spec by `scripts/spec_cli.py generate-reward-config`. Sorted-key
   dict literal, deterministic float repr, AUTO-GENERATED header. CI
   gate via `scripts/spec_cli.py generate-reward-config --check`.
3. **Runtime divergence counter.** Each agent's `compute_reward`
   imports its `reward_config.WEIGHTS` and calls
   `synapse_common.reward_shadow.shadow_check(...)`. Mismatch between
   runtime kwargs and spec weights increments
   `synapse_reward_weight_divergence_total{agent, key}` — silent,
   non-blocking, but observable in Prometheus.

**Sprint 9 cuts over** to source-of-truth: kwargs become optional
overrides, `reward_config.WEIGHTS` becomes the default, the divergence
counter becomes an Alertmanager-routed warning.

## Consequences

**Easier:**
- Reward weight changes now require a spec.yaml PR (ADR-style review).
- Drift between spec and runtime kwargs is observable, not silent.
- Sprint 9 cutover is mechanical — the seam already exists.

**Harder:**
- Two sources of truth coexist for one sprint. Acceptance: this is
  explicitly the "shadow mode" tradeoff.
- The divergence counter requires every agent's reward function to
  call `shadow_check`. Adding a new agent without this call is silent
  until the spec-coverage gate (`scripts/check_spec_coverage.py`)
  catches missing reward-key coverage.

## Alternatives Rejected

1. **Direct cutover in Sprint 8.** Higher risk — a wrong weight in
   spec.yaml silently changes RL training.
2. **Skip spec promotion entirely; keep hardcoded weights.** Defeats
   ADR-027's spec-as-source-of-truth roadmap.
3. **Make divergence a hard fail.** Blocks legitimate experimentation
   (e.g., a researcher temporarily overriding `crps_weight`).

## References

- ADR-027: Spec-as-Source-of-Truth Promotion (Sprint 7)
- `scripts/spec_cli.py` — generator with `--check` mode
- `packages/synapse_common/reward_shadow.py` — runtime divergence helper
- `agents/demand_prophet/tests/test_reward_safety.py`,
  `agents/pricing_oracle/tests/test_reward_safety.py` — counterfactual gates
