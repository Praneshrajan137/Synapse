# ADR-042 — Training-Truth Contract & Substance Completion

- **Status:** Accepted
- **Date:** 2026-05-30
- **Supersedes:** none
- **Related:** ADR-040 (honest output provenance), ADR-041 (feature/model anti-corruption layer), C33 (substance gap)

## Context

Sprints 11–13 made SYNAPSE's *enforcement boundary* honest; the Substance Mandate
(ADR-040/041, C33) made the *runtime contract* honest — every served output records
whether it came from a real model or a degraded fallback, and confidence is derived,
never constant. One rung remained, verified by direct inspection:

- **No training loop executes.** `agents/demand_prophet/training/train.py` constructed an
  `AdamW` optimizer + cosine scheduler, discarded both, took **zero** gradient steps, and
  returned `{"status": "pipeline_validated"}`. The other seven agents had no `train.py` at
  all. No checkpoint existed anywhere in the repo.
- **Serving never loaded a model.** Every `agents/*/inference/serve.py` built its pipeline
  with `model=None`, so 100% of inference was the honest-but-degraded fallback. The
  `ModelRegistry` anti-corruption layer (ADR-041) was correct but **never called**.
- **A latent confidence lie.** `pricing_oracle` stamped
  `Provenance.real(confidence_basis=CRITIC_VALUE_SPREAD)` while computing `tanh(|elasticity|)`;
  `routing_navigator` emitted no confidence. C33 cannot catch a *wrongly-labelled* (vs.
  *constant*) confidence.

The honesty contract told the truth about degradation; it did not make the system stop
degrading. The intelligence was not real.

## Decision

Close the substance gap with the repository's founding discipline — *no claim is PASS
without a mechanical check that fails on regression* — extended for the first time from
**enforcement** to **intelligence**. Concretely:

1. **A training-truth contract** (`packages/synapse_common/training_contract.py`): the
   `TrainResult` frozen value object is the published language for "a training run actually
   happened." It records `gradient_steps`, `start_loss`/`end_loss`, the content-hashed
   `checkpoint_sha`, and held-out `metrics`; `assert_learned()` raises unless the loop took
   ≥1 step and the loss fell by ≥ `MIN_IMPROVEMENT` (5%). It is torch-optional (numpy/JSON
   checkpoints for non-torch agents) and deterministic (sha over canonical bytes).

2. **Five mechanical gates** in the `substance_truth.py` idiom, registered as C37–C41 in
   `verify_claims.py` and run by `make verify-intelligence`:
   - **C37 Training-Truth** — AST: no `train.py` returns `pipeline_validated` or builds an
     optimizer it never steps; runtime: smoke-train returns a `TrainResult` that learned.
   - **C38 Checkpoint-Truth** — the smoke checkpoint exists and its on-disk sha matches.
   - **C39 Serving-Truth** — AST: `serve.py` constructs `ModelRegistry().load(...)`; runtime:
     a present checkpoint yields a non-degraded provenance.
   - **C40 Calibration-Truth** — held-out interval coverage ≥ the agent's documented floor
     (the deepest check: uncertainty is real, not decorative).
   - **C41 Confidence-Basis-Truth** — the declared `ConfidenceBasis` equals the computed one.
   Each ratchets from a *measured* baseline (today: C37=2, C39 unwired=8, C41=2) toward 0/8/8.

3. **Two-tier training** (honors I-1 $0 and CI time):
   - **CI smoke-train** — CPU-only, tiny seeded subset, ≤2 epochs, ≤5 min — the
     mechanically-gated proof that the loop takes real gradient steps and learns. Writes a
     `TrainResult` + smoke checkpoint to `artifacts/training/` (gitignored).
   - **Operator full-train** — the free-tier Colab/Kaggle notebooks on the full 1.1M-row
     data, producing the registered production checkpoint with held-out metrics.
   The split is the honesty boundary: smoke = **loop-truth**, calibration = **quality-truth**,
   full-train = **production artifact**. None is presented as another.

### Agents without a gradient loop

The inventory newsvendor is closed-form optimal and the routing CVRPTW is an exact solver —
forcing a fake gradient loop onto them would itself be the anti-pattern this ADR exists to
prevent. Such agents construct `TrainResult.analytical(...)` (`kind="analytical"`, `learned`
True by construction) and satisfy the contract through **calibration-truth** (C40) and
**optimality-gap** confidence, not gradient steps. Honesty over uniformity.

## Consequences

- **Positive.** The first genuinely-real decisions the system can produce; degradation
  becomes a fallback rather than the only mode; every step of train→checkpoint→serve→
  calibrate is regression-proof; the latent confidence-basis lie is closed.
- **Negative / accepted.** Smoke-train proves the loop, not model quality — quality lives in
  C40 + the operator full-train, explicitly labelled. Twin-as-gym RL is sim-trained and
  labelled as such (`model_version=…_sim_trained`); the offline-RL-on-logged-data path
  (arXiv:2504.09831) is the documented higher-fidelity successor.
- **Ratchet.** Agents move through the contract one PR each (flagship `demand_prophet`
  first), mirroring the C33 violations-10→0 climb. Floors never regress.
