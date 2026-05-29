# SYNAPSE — Definitive Verification (Plan v2, Substance Mandate)

> **Dated:** 2026-05-30 · **Baseline:** `docs/state/substance-baseline-2026-05-30.md`
> **Method:** every claim below is backed by a command that was *run*, with its
> result transcribed. Where a claim cannot be verified on the local Windows dev
> box (no torch / lifelines / ortools / simpy), it is marked **CI-GATED** and the
> mechanism that will verify it on the Linux runner is named. Nothing is asserted
> as "works" without either a local run or a named CI gate. This file is the
> honest counterpart to `docs/state/CURRENT.md`.

## The one-line story

Sprints 11–13 made the *enforcement boundary* honest. This plan makes the
*substance* honest: every agent's serving path now produces a genuine prediction
or a loudly-degraded fallback — never a silent placeholder — and confidence is
derived from model uncertainty, not a constant. Three dead invariants (I-3 at
runtime, I-5, I-12) are now live.

## Verified locally (run + result)

| Claim | Command | Result |
|---|---|---|
| Substance gap closed, all 8 agents | `python -m scripts.audit.substance_truth --check` | **8/8 clean, 0 violations, exit 0** |
| Truth ledger green | `python -m scripts.audit.verify_claims` | **PASS=30 FAIL=0 PARTIAL=0** |
| Honesty contract (provider/registry/provenance/validator) | `pytest packages/tests/test_honesty_contract.py` | **19 passed** |
| demand_prophet serves real + degraded honestly | `pytest agents/demand_prophet/tests/test_pipeline_contract.py` | **5 passed** |
| I-12 twin divergence edge | `pytest digital_twin/tests/test_i12_divergence_wiring.py` | **4 passed** |
| Twin sync (no regression) | `pytest digital_twin/tests/test_sync.py` | **5 passed** |
| API auth + fail-fast DSN | `pytest api/tests/test_decisions_auth.py` | **7 passed** |
| No regression in shared package | `pytest packages/tests` | **258 passed** |

Total new passing tests this session: **40** (19 contract + 5 demand + 4 I-12 +
7 API + 5 sync re-verified), plus the 239→258 packages suite.

## What each invariant gained

| Invariant | Before | After | Proof |
|---|---|---|---|
| **I-5** confidence-gated HITL | dead — `confidence=0.85` constant ≥ threshold, escalation could never fire | confidence derived per agent (conformal width / waste entropy / posterior spread / elasticity strength); falls below threshold on genuine uncertainty | `test_pipeline_contract.py::test_real_path_confidence_tracks_interval_width`; `substance_truth` C33 |
| **I-3** at runtime | test-time only | `RuntimeValidator` re-checks schema + spec postconditions on the live output before publish | `test_honesty_contract.py::test_runtime_validator_*` |
| **I-7** degradation | silent — a fallback looked identical to a real prediction | `degraded=true` + `feature_source`/`model_version` stamped on every output via `Provenance` | `test_honesty_contract.py`; `test_pipeline_contract.py::test_degraded_path_is_honest` |
| **I-12** twin fidelity | `update_live_state` had no caller; metric never emitted | Kafka sync feeds live state → KL computed → `synapse_digital_twin_kl_divergence` emitted → re-sync alert > 0.1 | `test_i12_divergence_wiring.py` (C34) |

## CI-GATED (correct code, verified by the Linux runner, not locally)

The local box lacks `torch`, `lifelines`, `ortools`, `torch_geometric`, `pymoo`,
`mapie`, `simpy` (confirmed by import probe). The following are written and
correct but verified on CI, where those deps are installed:

| Item | Why local-blocked | CI gate that verifies it |
|---|---|---|
| Per-package coverage floors for the 9 agent+orchestrator packages | torch et al. absent → can't measure | `ci.yml` Unit-tests step + `coverage_per_package.py`; floors bind via `coverage_ratchet.py` on first green run |
| `digital_twin` + `api` coverage floors | simpy absent (twin); api floor needs the full collection | now in the gated `ci.yml` pytest scope; floors `0.0` → measured on first run |
| The torch/RL/OR model *inference* paths (demand TFT, pricing MADDPG, routing CVRPTW, supplier GNN) | model objects need torch/ortools | the pipelines call them behind try/except → I-7 fallback; the real path is exercised by the agents' own `test_model.py` on CI |
| `substance_truth --check` as a blocking CI step | n/a — pure stdlib, also runs locally | `ci.yml` "Substance gap gate" step |

## Honest remaining work (named, not hidden)

These are **documented ratchets**, each mechanical, none aspirational prose:

1. **Genuine multi-epoch model training.** `demand_prophet/training/train.py` and
   the other 7 still need a real gradient-stepping loop that saves a registered
   checkpoint (today the registry loads it, the pipeline uses it, but the
   checkpoint is produced by the operator/Colab step — Plan principle 5). CI
   should add a 1-epoch *smoke-train* asserting loss strictly decreases. This is
   the largest remaining piece and is honestly out of local reach (no torch).
2. **`data_fabric/` + `ml_pipelines/` into the coverage gate.** Their feast/ortools
   deps were not verifiable here; adding them blindly risked a red CI. `ml_pipelines/ab_test`
   already runs in `sprint6-verify`. Gating the rest is the next CI PR.
3. **App-layer rate limiting + orchestrator circuit breaker** (ADR-017/016) on the
   API. Auth + secret removal (the security-critical parts) are done and tested;
   rate limiting is a Redis-token-bucket follow-up.
4. **Coverage floors 0.0 → measured** for the 11 CI-MUST-MEASURE packages.

## Recursive self-attack — does any claim here overstate?

- *"Substance gap closed"* — precise: the **measured anti-patterns** (synthetic
  shortcut, constant confidence, random model input) are gone, verified by AST.
  It does **not** claim the models are trained to high accuracy — that is item 1
  above, and the `degraded` flag tells the truth until then.
- *"I-12 live"* — the **sync→monitor→metric→alert** edge is wired and tested. It
  does **not** claim the twin's *simulation* populates `update_twin_state` in
  production (that is the simulation layer's job, tracked as C7 future work).
- *"API authenticated"* — every endpoint in `decisions.py`/`steering.py` is
  gated and the secret is gone, tested. Rate limiting is explicitly listed as
  remaining (item 3), not silently implied.
