# SYNAPSE — Intelligence Baseline (Substance Completion, Phase 0)

> **Dated:** 2026-05-30
> **HEAD:** `feat/substance-completion-intelligence`
> **Method:** Direct code inspection + the five new `*_truth.py` gates run with
> `--check`. Numbers below are *measured*, not asserted.

This is the honest starting line for the Substance Completion Plan. The Substance
Mandate (ADR-040/041, C33) made the *runtime contract* honest — degradation is
tracked, confidence is derived, no synthetic shortcuts. This baseline measures
the one thing that contract never checked: whether the system **ever operates in
a non-degraded mode at all**. It does not — yet.

## Measured intelligence gap (today)

| Surface | Gate | Measured today | Ratchet target |
| --- | --- | --- | --- |
| Real gradient training loops | C37 training_truth | **0/8 agents**; 2 violations (demand_prophet `pipeline_validated` + hollow optimizer) | 8/8, 0 violations |
| Loadable, hashed checkpoints | C38 checkpoint_truth | **0** (no checkpoint exists in the repo; SKIP until smoke job) | ≥1 per gradient agent |
| Serving loads via ModelRegistry | C39 serving_truth | **0/8 wired**; every serve.py builds `model=None` | 8/8 wired |
| Interval coverage (calibration) | C40 calibration_truth | **unmeasured** (SKIP until smoke job) | ≥ per-agent floor |
| Declared = computed conf. basis | C41 confidence_basis_truth | **2 mismatches** (pricing `CRITIC_VALUE_SPREAD`≠elasticity; routing emits none) | 0 |

**The substance facts (all confirmed by `file:line`):**
- `agents/demand_prophet/training/train.py:101-123` — builds `AdamW` + cosine
  scheduler, discards both, returns `{"status":"pipeline_validated"}`. Zero
  gradient steps. The only `train.py` in the repo; the other 7 agents have none.
- Every `agents/*/inference/serve.py` constructs its pipeline with no `model=`
  argument → `model is None` → the EMA / rule-based / greedy fallback runs 100%
  of the time. `ModelRegistry.load()` (ADR-041) is never called in serving.
- `data_fabric/feast/` views are declared but `feast apply`/`materialize` is never
  run, and Bengaluru's `data/demand_signals.parquet` does not exist → even
  features are always `FeatureSource.FALLBACK`.
- `digital_twin/training/rl_sandbox.py:143-162` — `SupplyChainGymEnv.step()`
  **ignores its `action`**, and `engine.py:205-216` `run()` re-initializes state
  every call → the RL environment is action-blind and stateless-across-steps; any
  RL trained against it learns nothing (the env-truth test in Phase 3 closes this).
- `agents/pricing_oracle/inference/pipeline.py:356-380` — stamps
  `ConfidenceBasis.CRITIC_VALUE_SPREAD` but computes `tanh(|elasticity|)`.

## Ratchet wired (regression-proof from day one)

- `packages/synapse_common/training_contract.py` — `TrainResult` value object + `--`able gates.
- `scripts/audit/{training,checkpoint,serving,calibration,confidence_basis}_truth.py` —
  `--json` / `--check` (exit 1 on regression past baseline).
- `verify_claims.py` **C37–C41** registered; `make verify-intelligence` wraps all five.
- `make verify-claims` after wiring: **PASS=33 FAIL=0 SKIP=2** (C38/C40 SKIP until the
  `training-smoke` CI job produces artifacts) — green and honest.

## What Phase 0 deliberately did NOT do

Per the "measure before changing" discipline, Phase 0 fabricated nothing:
- No checkpoint floors were invented — C38/C40 SKIP until the smoke job measures them.
- The 9 placeholder `0.0` coverage floors stay `0.0` until the first CI Linux run with the
  full torch/ortools/pymoo stack binds them (Phase 0's `training-smoke` job).
- No agent was claimed "real" — C37 still reads 0/8. Phase 1 makes `demand_prophet` the
  first true entry and ratchets its baselines down.
