# ADR-043 — The Agent Reality Pattern (Runtime Substance + $0 Serving)

- **Status:** Accepted
- **Date:** 2026-05-31
- **Supersedes:** none
- **Amends:** ADR-041 (adds a $0 serving source to `ModelRegistry`; MLflow remains the lineage path)
- **Related:** ADR-040 (honest output provenance), ADR-042 (training-truth), C33 (static substance gate)

## Context

ADR-042 closed the *training* lie: `demand_prophet` now takes real gradient steps,
writes a content-hashed checkpoint, and the C37/C38/C40/C41 gates fail on regression.
But verifying the flagship **end to end, as an operator would exercise it**, surfaced
that the static gates (C33 `substance_truth.py`, C41 `confidence_basis_truth.py`) have a
structural blind spot: they AST-walk *source* and prove dishonest *shapes* are absent.
They cannot prove the model actually loads and runs. Reading the serving path directly
found two real defects that every gate and every test were green against — because every
test ran with `model=None`, so the real-operator path was never executed:

1. **Latent 500 on the real path.** `serve._build_pipeline` constructed a
   `ConformalCalibrator` but never `.fit()` it; the fitted CQR adjustments computed during
   training were discarded. The moment a real model loaded, `predict_intervals` raised
   `RuntimeError("not calibrated")` → unhandled → HTTP 500.
2. **Registry unreachable at $0.** `ModelRegistry` resolved models only through MLflow
   (`get_latest_versions`/`load_model`). The free-tier VM runs no MLflow server, so a
   trained checkpoint — even one published to HF Hub — was never loadable, and 100% of
   inference silently took the honest-but-hollow fallback.
3. **A disguised constant.** On the EMA fallback, every SKU's relative interval width was
   exactly `0.4`, so the "derived" `confidence = 1/(1+0.4) ≈ 0.714` was a constant for all
   inputs — and it sat *above* the 0.7 HITL threshold, silently suppressing I-5 escalation
   on degraded output. C33 cannot see this: the value is arithmetic, not a literal.

The lesson generalizes: **a static gate proves the code can't lie in a known shape; only a
runtime gate proves the code tells the truth when run.** Both are required.

## Decision

Establish the **Agent Reality Pattern** — the canonical, mechanically-gated sequence that
takes one agent from "honest about being hollow" to "genuinely real, proven at runtime" —
and make it the reusable template the remaining seven agents follow, one PR each.

### 1. Two complementary gates (static + runtime)

- **Static (runs everywhere, every PR):** C33 `substance_truth.py`, C37 `training_truth.py`,
  C39 `serving_truth.py`, C41 `confidence_basis_truth.py` — AST proofs that no dishonest
  *shape* exists.
- **Runtime (runs where torch + a smoke checkpoint exist — the CI `training-smoke` job):**
  C38 `checkpoint_truth.py`, C40 `calibration_truth.py`, and the new **C42
  `runtime_substance.py`**, which boots the trained checkpoint through the production
  serving path and asserts the output is real: `degraded=False`, `feature_source=FEAST`,
  `confidence_basis=CONFORMAL_INTERVAL`, confidence not collapsed to the floor. Both halves
  SKIP honestly rather than fabricate a pass when their prerequisites are absent.
  `substance_truth.py`'s docstring now states its static-only scope and points to C42.

### 2. A $0 serving source on the published `ModelRegistry` contract

`ModelRegistry.load() -> LoadedModel` is unchanged. We add a second *source* (not a second
published language): when no MLflow client resolves a model, the registry resolves
`{resolve_name(...)}.pt` from a local checkpoint dir and/or HF Hub, reads the sidecar into
`LoadedModel.meta`, and builds a concrete model via an **agent-injected `model_builder`** —
so the registry stays architecture-agnostic and never imports an agent. MLflow remains the
lineage path; this is the *serving* path for the $0/free-tier reality (I-1, ADR-037). It
degrades identically when absent (never raises, I-7).

### 3. Calibration travels with the checkpoint

The fitted calibrator is serialized (`ConformalCalibrator.to_state()`) into a deterministic
serving sidecar `{name}.serving.json` (alongside the architecture dims), written by
`train.py` and restored *fitted* at serve time onto the serving model. The model `.pt` stays
a pure state_dict, so C38's content hash is undisturbed. `pipeline.predict` guards the
interval call: an unfit/failed calibrator degrades to raw bands, never a 500.

### 4. Honest confidence on both paths

Real path: confidence is derived per-SKU from the conformal interval width (varies with
uncertainty). Degraded path: confidence is the explicit `FALLBACK_CONFIDENCE` floor (below
the HITL threshold so I-5 fires), never an arithmetic constant. Escalation keys off
`provenance.degraded`, the honest signal, not the float alone.

### The canonical sequence (every future agent)

```
train (real loop / analytical)               → C37
  └ persist checkpoint + calibrator sidecar   → C38, C40
register to HF Hub (operator/Colab, $0)
serve: ModelRegistry $0 source + builder      → C39
  └ restore fitted calibrator from sidecar
derive confidence from model uncertainty      → C41
runtime gate: real checkpoint → real output   → C42
consume in an orchestrator decision + UI       (WS-E/H, per-agent ratchet)
```

## Consequences

- **Positive.** The "passes but hollow at runtime" blind spot is closed by a mechanical
  gate; the flagship is reproducibly real for operators; the seven remaining agents have a
  proven, low-variance template; the $0 serving path needs no standing MLflow infra.
- **Negative / accepted.** A second model source adds resolution surface to `ModelRegistry`
  (mitigated: one contract, one private path resolver, full degradation tests). The full
  production checkpoint is an operator/Colab step outside CI; CI gates the smoke artifact and
  C42 on a fixture, and the full model's coverage is recorded in the runbook and re-checked
  by C40 — the seam (CI-smoke vs. operator-full) is documented, not hidden.
- **Ratchets.** `serving_truth` `BASELINE_UNWIRED` 7 → 0 and `training_truth` baselines
  decrement one per agent PR; C42's covered-agent set grows the same way.
