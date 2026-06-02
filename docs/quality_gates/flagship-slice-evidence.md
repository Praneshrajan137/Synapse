# Flagship Reality Slice — Evidence (demand_prophet)

**Date:** 2026-05-31 · **ADR:** [ADR-043](../adr/ADR-043-agent-reality-pattern.md) · **Ledger:** [CURRENT.md](../state/CURRENT.md) (C37–C42)

This document is the honest, reproducible record of making **one** agent genuinely
real end-to-end. It deliberately separates what is **proven locally** (torch-free,
on any machine) from what is **gated in CI** (needs the ML stack + a smoke
checkpoint) from what is an **operator step** (free-GPU full train). It does **not**
claim the other seven agents are real — they follow the same pattern, one PR each.

## What "real" means here (the bar)

A forecast is real iff, at runtime: a trained model loads (`degraded=False`),
features come from the store (`feature_source=FEAST`), the prediction intervals
come from a *fitted* conformal calibrator (`confidence_basis=CONFORMAL_INTERVAL`),
and confidence varies with per-SKU uncertainty rather than being a constant. Anything
short of that must be *labelled* degraded — and now also *caught* by a gate.

## Two defects this slice found and fixed (both invisible to the static gates)

| # | Defect | Why no test caught it | Fix | Now gated by |
|---|--------|-----------------------|-----|--------------|
| 1 | Real model + **unfit calibrator** → `RuntimeError` → HTTP 500 on the first real request | every test ran `model=None`, so the calibrator branch never executed | calibrator is fitted in training, persisted in the serving sidecar, restored fitted at serve; `predict` guards the call | C42 + `test_serving_calibration.py::test_real_model_with_unfit_calibrator_degrades_not_crashes` |
| 2 | `ModelRegistry` was **MLflow-only** → checkpoint never loadable at $0 → permanent fallback | static gates check *shape*, not whether a model loads at runtime | added a $0 checkpoint source (local dir / HF Hub) + agent-injected builder, same `load()` contract | C42 + `test_model_registry_checkpoint.py` |
| 3 | **Disguised-constant** degraded confidence `≈0.714` sat *above* the 0.7 HITL threshold → I-5 never fired | the value is arithmetic, not a literal — `substance_truth` is blind to it | degraded confidence is the explicit `FALLBACK_CONFIDENCE` floor (< threshold); derived confidence reserved for the real path | `test_serving_calibration.py::test_degraded_confidence_is_floor_and_would_escalate` |

## Proven locally (torch-free, deterministic) — run now

```bash
python -m pytest packages/tests/test_model_registry_checkpoint.py \
  packages/tests/test_honesty_contract.py \
  agents/demand_prophet/tests/test_serving_calibration.py \
  agents/demand_prophet/tests/test_serve_wiring.py \
  agents/demand_prophet/tests/test_pipeline_contract.py \
  agents/demand_prophet/tests/test_conformal_coverage.py -q
# → 68 passed
python -m scripts.audit.verify_claims        # → PASS=33 FAIL=0 SKIP=3 (C38/C40/C42 runtime)
python -m scripts.audit.substance_truth --check   # → 0 violations, 8/8 clean
```

- Registry $0 checkpoint source: real-vs-degraded, MLflow→checkpoint fallthrough, builder-failure degradation.
- Calibrator state round-trips and travels on the serving model; unfit calibrator refuses to serialize.
- The latent-500 regression, the honest-floor escalation, and the disguised-constant detector.

## Gated in CI (`training-smoke` job — torch + smoke checkpoint present)

`SYNAPSE_SMOKE_RUN=1 python scripts/smoke_train.py` writes
`artifacts/checkpoints/demand_prophet_hgt_tft.pt` + `…serving.json` and
`artifacts/training/demand_prophet.json`, then:

- **C37** training-truth — real gradient steps, loss fell ≥5%.
- **C38** checkpoint-truth — checkpoint exists, sha matches (determinism).
- **C40** calibration-truth — held-out `coverage_p90 ≥ 0.85`.
- **C42** runtime-substance — the just-trained checkpoint, loaded through the production
  serving path, yields `degraded=False`, `feature_source=FEAST`,
  `confidence_basis=CONFORMAL_INTERVAL`, non-floor confidence. RED on a `model=None` slice.

## Operator step (free-GPU, $0 — gated by C43)

Full train on the 1.1M-row Bengaluru series and publish the checkpoint + sidecar to HF Hub
under `demand_prophet_hgt_tft`, then set `DP_HF_REPO` on the serving container so
`ModelRegistry` resolves it.

- **Notebook:** [`notebooks/train_demand_prophet.ipynb`](../../notebooks/train_demand_prophet.ipynb)
  — runs the production `train()` unchanged, fits the calibrator, refuses to publish a
  smoke / under-covered artifact, uploads to HF Hub, and prints the registry entry.
- **Runbook:** [`docs/runbooks/train-and-publish-checkpoint.md`](../runbooks/train-and-publish-checkpoint.md)
  — the seven steps + verification.
- **Gate (C43):** `scripts/audit/published_checkpoint_truth.py` fetches the published
  sidecar and asserts non-smoke + `coverage_p90 >= 0.85` + recorded-sha == published-sha.
  SKIPs when `DP_HF_REPO` is unset or the registry is a placeholder (CI stays green without
  the secret); flips to PASS once an operator publishes and records the result in
  `infrastructure/ml/published_checkpoints.json`.

**Recorded production checkpoint:** _pending the first operator run_ (CRPS / coverage / sha
go in the runbook table + `published_checkpoints.json`). The local + CI proofs above already
exercise the entire code path with the smoke checkpoint; C43 is what makes the *published*
model a live, regression-guarded proof.

## Honest status

- **Done & proven:** the serving code path is real end-to-end on the smoke checkpoint;
  three real defects fixed; C42 runtime gate added; ADR-043 pattern documented.
- **Remaining (named, not hidden):** orchestrator consumes the forecast + Tier-4 twin
  invocation (C7); the production full-train checkpoint published to HF; the same pattern
  applied to the other 7 agents (one PR each, decrementing the serving/training baselines).
