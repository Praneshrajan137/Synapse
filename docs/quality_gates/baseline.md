# Backend Elevation — Phase 0 Baseline (Ground Truth)

**Date:** 2026-05-22
**Branch:** main @ ff2f4e0
**Purpose:** Honest measurement of the backend *before* the elevation work, so
every later gate ratchets from a real number instead of an aspirational one.
No behavior was changed to produce this document.

---

## How this was measured

- Python 3.11.15 in `.venv`, run on Windows 11.
- The `.venv` shipped with only the lightweight `packages/` tooling. The heavy
  ML/infra stack (torch, fastapi, simpy, mlflow, sklearn, pandas, scipy, pyro,
  lifelines, econml, …) had to be installed to even *collect* the agent,
  orchestrator, and digital-twin tests. **CI installs only
  `packages/requirements.txt` + `packages/requirements-dev.txt`** — so CI is not
  provisioned to run those tests at all (see Finding F-1).
- Dependency ranges in `agents/*/requirements.txt` are wide and unpinned
  (`torch>=2.2.0,<3.0`, etc.). The install resolved to current versions
  (`torch 2.12.0+cpu`, `schemathesis 3.39.16`), which differ from what the tests
  were authored against — the source of several failures below (Finding F-5).

---

## Headline numbers

| Metric | Value | CI gate today | Reality |
|--------|-------|---------------|---------|
| Backend test result | **631 passed / 8 failed / 245 skipped / 1 xfailed** | only 88 `packages/` tests run | agent/orch/twin tests never gate a PR |
| Backend line coverage | **58.9%** (5690 stmts, 2338 missed) | `--cov-fail-under=80` on `synapse_common` only | ~30K LOC unmeasured by CI |
| Skipped tests | **245 / ~885 (28%)** | — | many are silent `pytest.skip` |
| `mypy --strict agents/` | **92 errors / 47 files** | `continue-on-error: true` | CI command also mis-resolves modules → emits *zero* signal |
| `ruff check` (7 backend dirs) | **86 errors** | lints only 3 of 7 dirs | digital_twin/data_fabric/ml_pipelines/api unlinted |
| `kv-cache-check` hook | **11 violations** in 3 files | hook exists, never enforced on tree | proves pre-commit is not run on the repo |
| Full-surface runtime | 7.5 min (plain) / 9.9 min (with coverage) | — | acceptable for a PR gate |

---

## Coverage by area

| Area | Statements | Coverage |
|------|-----------:|---------:|
| api | 117 | **0.0%** |
| data_fabric | 170 | **0.0%** |
| ml_pipelines | 593 | 19.1% |
| orchestrator | 967 | 52.4% |
| digital_twin | 559 | 59.0% |
| agents/sustainability_agent | 302 | 61.9% |
| agents/inventory_sentinel | 202 | 64.4% |
| agents/disruption_shield | 489 | 69.3% |
| agents/pricing_oracle | 466 | 69.7% |
| agents/routing_navigator | 284 | 71.1% |
| agents/demand_prophet | 489 | 75.5% |
| agents/freshness_guardian | 309 | 80.3% |
| agents/supplier_trust | 298 | 81.5% |
| packages | 445 | 80.7% |
| **TOTAL** | **5690** | **58.9%** |

`packages/` reads 80.7% here (vs ~99% in CI) because this whole-tree run includes
`synapse_common/langsmith_client.py` and `tracing.py` at 0% — both never imported
by any test.

---

## The 8 failing tests (triaged)

CI has never seen any of these, because it does not run agent or `tests/` suites.

| Test | Root cause | Category |
|------|-----------|----------|
| `demand_prophet…TestTFT::test_forward_pass` | `tft.py:58` tensor shape mismatch (30 vs 4) | **real model bug** |
| `demand_prophet…TestHybrid::test_forward_pass` | same TFT root cause (Hybrid wraps TFT) | **real model bug** |
| `demand_prophet…TestHybrid::test_deterministic_output` | same TFT root cause | **real model bug** |
| `pricing_oracle…TestPricingMADDPG::test_soft_update` | target net unchanged after soft update — likely test missing `.clone()` | **test bug** |
| `pricing_oracle…test_catastrophic_penalty_weight` | `rewards.py:48,55` `.std()` on degenerate (1-elem) input → `NaN` reward | **real reward bug** |
| `supplier_trust…TestSupplierTrustGNN::test_gradient_flow` | a parameter has no `.grad` after backward | **real / setup** |
| `tests/api_fuzz…test_schemathesis_import` | `schemathesis.from_url` removed in 3.3x→3.39 | **dependency skew** |
| `tests/dbc…test_log_decision_returns_audit_id…` | `deal.PostContractError` — needs a live Postgres | **mis-categorized infra test** |

Summary: **5 genuine code bugs**, 1 test bug, 1 dependency skew, 1 test that needs
live infra but sits in the unit-layer `tests/dbc/`.

---

## Enforcement-gap findings

- **F-1 — CI is not provisioned to run the backend.** `ci.yml` installs only the
  `packages/` requirements and runs `cd packages && pytest tests/`. Even if the
  test command were widened, imports would fail: the agents need torch et al.
  Fixing CI means *also* fixing dependency installation.
- **F-2 — The 80% coverage gate covers one package.** Real backend coverage is
  58.9%. ~30K LOC sits outside the gate; `api/` and `data_fabric/` are at 0%.
- **F-3 — The agent `mypy` step emits no signal.** `mypy --strict agents/` aborts
  on a "source file found twice" module-resolution error, and the step is
  `continue-on-error: true`. With correct flags there are 92 real errors.
- **F-4 — Pre-commit hooks are not enforced on the tree.** The `kv-cache-check`
  hook is written to reject f-strings / `.format()` / `datetime.now()` in 3
  files, yet 11 such lines are committed. `pre-commit run --all-files` is not a
  CI step.
- **F-5 — Agent dependencies are not reproducible.** `agents/*/requirements.txt`
  use multi-minor-version ranges. `orchestrator/requirements.txt` pins exactly.
  The inconsistency means a CI install is non-deterministic and can silently
  break the model tests (it did — see the table above).
- **F-6 — `check_spec_coverage.py` is satisfied by skipped tests.** It checks
  only that an invariant *ID string* appears in `test_spec.py`; a `pytest.skip`
  body still counts as "covered".
- **F-7 — The 7-layer topology is partly PR-wired but soft.** `integration.yml`
  *does* run on PRs, but its `contracts` job treats "no tests collected" as a
  pass and its `metamorphic`/`e2e` jobs depend on `agents/requirements-sprint3.txt`.
  `mutation.yml` is schedule-only. `security.yml` runs only on dependency/
  Dockerfile changes and every scanner is `|| true` / `exit-code: 0`.

---

## Ratchet targets this baseline sets for Phase 1

- `--cov-fail-under` starts at **58%** (one point below measured, to absorb
  noise) and only ever rises. It is *not* set to 80% — that would block the very
  PR that makes CI honest.
- The 8 failing tests must be triaged: real bugs fixed (Phase 1a / Phase 3),
  the dependency skew pinned (Phase 1), the infra test re-homed to the
  integration layer (Phase 2).
- `mypy --strict` on agents: 92 → target 0, then flip the step to blocking.
- `ruff`: 86 → 0 across all 7 backend dirs.
- `kv-cache-check`: 11 → 0; add `pre-commit run --all-files` as a CI step.
- Mutation survival: to be measured on the fixed reward/guardrail/audit surface
  during Phase 1 (the nightly `mutation.yml` is the current only data point).
