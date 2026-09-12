# Runbook — Train & Publish a Production Checkpoint ($0, free-GPU)

> **Scope:** the operator step of the Agent Reality Pattern (ADR-043). Turns "the
> serving code path is real" (proven by C42 on the CI smoke checkpoint) into "a
> real, calibrated model serves" (proven by **C46** on the published artifact).
> **Cost:** $0 (I-1) — free Colab/Kaggle GPU + the free Hugging Face Hub tier.

This runbook is currently written for **demand_prophet** (the flagship). The same
seven steps apply to every agent that follows the pattern — substitute the agent's
`SERVING_NAME`, training entrypoint, and HF repo.

> **Gate identifier.** This gate is **C46**, "A real, published production checkpoint
> serves at $0". Five places in this runbook previously called it **C43**, which is a
> different check — "All 8 agents expose POST /a2a for consensus". The mix-up has a
> traceable origin: `verify_claims.py`'s C46 SKIP branch once returned `cid="C43"`, so
> an unavailable published-checkpoint probe landed on another check's row. That was
> fixed in the code; this document was the surviving copy of the error.

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
   calibrated model. Check the `heldout_block_written` log line the training run emits:
   if `below_min_rows` is true, the block is shorter than the committed minimum and C46
   will report **unavailable** on the published artifact — which is not a pass. The same
   line reports `coverage_p90_over_published_rows`, which is the number C46 recomputes.
5. **Upload** both files to HF Hub (checkpoint + serving sidecar).

   **The sidecar must carry its `heldout` block.** `train.py` writes it (`HeldoutBlock`)
   and `infrastructure/quality/checkpoint-truth.yaml` declares its shape; C46 recomputes
   **both** `final_crps` and `coverage_p90` from it and reports **unavailable** — never a
   pass — for a sidecar that does not publish it (R9.13, R9.14). A recorded number nobody
   recomputed is not evidence. Before uploading, confirm the block is present and
   complete (in the same Colab/Kaggle runtime as every other step here):

   ```bash
   python - <<'PY'
   import json, pathlib
   p = pathlib.Path("artifacts/checkpoints/demand_prophet_hgt_tft.serving.json")
   block = json.loads(p.read_text(encoding="utf-8"))["heldout"]
   print("rows", block["rows"], ">= min_rows", block["min_rows"])
   print("raw band", block["raw_quantile_band"])
   print("adjusted band", block["conformal_adjusted_band"])
   for h, payload in block["horizons"].items():
       print(h, sorted(payload))
   PY
   ```

   Every horizon must list `actuals`, `lower_90`, `predictions`, `upper_90`. The
   `lower_90`/`upper_90` pair is the **conformal-adjusted 90%** band INV-DP-002 is about;
   `predictions` are the raw quantiles at `[0.1, 0.5, 0.9]`, which span a nominal **80%**
   band. They are two different intervals and neither substitutes for the other — the
   coverage recompute reads the adjusted pair and refuses rather than falling back.
6. **Record the result.** Copy the printed JSON entry into
   `infrastructure/ml/published_checkpoints.json` (deleting the `__placeholder__`
   object) and copy the same numbers into the "Operator step" section of
   `docs/quality_gates/flagship-slice-evidence.md`. Validate the record before
   committing — it is network-free, so it runs anywhere:

   ```bash
   python -m scripts.audit.published_checkpoint_truth --validate-registry --check
   ```

   It checks every required key (`repo`, `sha`, `coverage_p90`, `final_crps`,
   `trained_at`, `rows`) and rejects an implausible value (non-`owner/name` repo,
   non-hex sha, `coverage_p90 < 0.85`, negative CRPS, undated `trained_at`,
   non-positive `rows`). A still-unpublished placeholder reports `placeholder`, not a
   pass. Commit both files.
7. **Wire serving.** Set `DP_HF_REPO=<HF_REPO>` on the demand_prophet serving container
   (`docker-compose*.yml` env / Helm values). `ModelRegistry._resolve_checkpoint_path`
   downloads `{name}.pt` + `.serving.json` and `load_serving_model` restores the fitted
   calibrator — serving is now non-degraded.

## Verification

```bash
# Locally / in CI, with the registry recorded (DP_HF_REPO is an override, not a
# precondition: the gate fetches the repo the committed record names):
python -m scripts.audit.published_checkpoint_truth --check                # C46 -> PASS
make verify-claims        # C46 flips SKIP -> PASS; no other row regresses
```

`published_checkpoint_truth` (C46) fetches the published sidecar and evaluates seven
clauses, reporting `pass` / `fail` / `skip` / `unavailable` with exit codes `0 / 1 / 2 / 2`:

| clause | what it refuses |
|---|---|
| `policy` | `source.zero_cost` false (I-1) or `source.allow_local_substitution` true (R9.7) |
| `registry` | no validated non-placeholder entry for the serving name |
| `fetch` | a recorded sha that cannot be fetched — **naming the local candidate it refused** |
| `classification` | a `smoke` artifact (FAIL) or one carrying no declared marker at all (unavailable) |
| `coverage` | a recorded `calibrator.last_coverage_p90` below `0.85`, reporting both numbers |
| `coverage-recompute` | coverage **recomputed** from the published `lower_90`/`upper_90` below `0.85`; an unrecomputable block is unavailable |
| `sha-pin` | a recorded sha absent from the published `version` |
| `crps-recompute` | a recorded `final_crps` outside `max(0.05, 0.10 x abs(recorded))` of its recompute; an unrecomputable block is unavailable |

**A SKIP is not a PASS, and neither is an unavailable (I-7).** The gate reports `skip`
while the registry is still `__placeholder__` — no operator has published yet — and
`unavailable` when the evidence could not be read or recomputed: the remote is
unreachable, `huggingface_hub` is absent, the sidecar publishes no `heldout` block, or
that block is shorter than the committed minimum. So CI stays green without the secret and
turns into a live regression-guarded proof once you publish, **and** a published artifact
that cannot be recomputed is reported as unproven rather than as proven.

Since decision-quality-proof task 18.3 (AD-19), C46 registers
`published_checkpoint_truth.assess`, not the narrower legacy `evaluate`. That matters here:
`evaluate` acted on `Outcome.FAIL` alone, so an unavailable recompute fell through to `ok`
— a sidecar with no held-out block published a PASS. Do not point a gate at `evaluate`.

## Recorded production checkpoints

| Agent | HF repo | sha | coverage_p90 | final CRPS | trained_at |
|---|---|---|---|---|---|
| demand_prophet | _(pending first operator run)_ | — | — | — | — |

> Fill this row from the notebook's step-5 output. It is the single source of truth
> the C46 gate cross-checks against the live HF Hub artifact.
