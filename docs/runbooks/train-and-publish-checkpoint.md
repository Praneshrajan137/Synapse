# Runbook — Train & Publish a Production Checkpoint ($0, free-GPU)

> **Scope:** the operator step of the Agent Reality Pattern (ADR-043). Turns "the
> serving code path is real" (proven by C42 on the CI smoke checkpoint) into "a
> real, calibrated model serves" (proven by **C43** on the published artifact).
> **Cost:** $0 (I-1) — free Colab/Kaggle GPU + the free Hugging Face Hub tier.

This runbook is currently written for **demand_prophet** (the flagship). The same
seven steps apply to every agent that follows the pattern — substitute the agent's
`SERVING_NAME`, training entrypoint, and HF repo.

## Prerequisites

- A free Hugging Face account + a **write** token (`huggingface.co/settings/tokens`).
- Read access to the (private) repo — a read-only `GITHUB_TOKEN` for the clone.
- The notebook `notebooks/train_demand_prophet.ipynb` (drives every step below).

## Steps

1. **Open** `notebooks/train_demand_prophet.ipynb` in Colab or Kaggle (free GPU runtime).
2. **Set secrets** as environment variables in the runtime:
   - `GITHUB_TOKEN` — read-only, for cloning the private repo.
   - `HF_TOKEN` — your HF write token.
   - `HF_REPO`   — e.g. `Praneshrajan15/synapse-demand-prophet`.
   - (optional) `DP_EPOCHS` — default `50`.
3. **Run all cells.** The notebook clones the repo, installs the pinned stack, builds
   the 1.1M-row Bengaluru feature set, runs the **production** `train()` (real gradient
   steps; `assert_learned()` fails loudly if the loop did not learn), fits the conformal
   calibrator, and writes `demand_prophet_hgt_tft.pt` + `.serving.json`.
4. **Publish gate.** The notebook refuses to publish a `smoke` artifact or one whose
   held-out `coverage_p90 < 0.85` (INV-DP-002). Publishing only proceeds on a real,
   calibrated model.
5. **Upload** both files to HF Hub (checkpoint + serving sidecar).
6. **Record the result.** Copy the printed JSON entry into
   `infrastructure/ml/published_checkpoints.json` (replacing `__placeholder__`) and copy
   the same numbers into the "Operator step" section of
   `docs/quality_gates/flagship-slice-evidence.md`. Commit both.
7. **Wire serving.** Set `DP_HF_REPO=<HF_REPO>` on the demand_prophet serving container
   (`docker-compose*.yml` env / Helm values). `ModelRegistry._resolve_checkpoint_path`
   downloads `{name}.pt` + `.serving.json` and `load_serving_model` restores the fitted
   calibrator — serving is now non-degraded.

## Verification

```bash
# Locally / in CI, with DP_HF_REPO set and the registry recorded:
DP_HF_REPO=<HF_REPO> python -m scripts.audit.published_checkpoint_truth --check   # C43 -> PASS
make verify-claims        # C43 flips SKIP -> PASS; no other row regresses
```

`published_checkpoint_truth` (C43) fetches the published sidecar and asserts: it is
**not** a smoke artifact, `coverage_p90 >= 0.85`, and the recorded sha matches the
published `version`. It **SKIPs** (never fabricates a pass) when `DP_HF_REPO` is unset,
`huggingface_hub` is absent, or the registry is still a placeholder — so CI stays green
without the secret, and turns into a live regression-guarded proof once you publish.

## Recorded production checkpoints

| Agent | HF repo | sha | coverage_p90 | final CRPS | trained_at |
|---|---|---|---|---|---|
| demand_prophet | _(pending first operator run)_ | — | — | — | — |

> Fill this row from the notebook's step-5 output. It is the single source of truth
> the C43 gate cross-checks against the live HF Hub artifact.
