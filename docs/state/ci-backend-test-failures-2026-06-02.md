# CI: pre-existing backend test failures (triage)

> **Context.** While bringing the SENSORIUM frontend PR (#13) to green after the
> GitHub Actions billing outage was resolved, the `SYNAPSE CI` →
> **Lint + Type Check + Unit Tests** job was repaired through six layers of
> pre-existing CI plumbing debt (Ruff, mypy/pathspec crash, 8 mypy `--strict`
> ndarray errors, `pip install -e packages/`, and two starlette pins). With
> those fixed, the unit-test step now **runs the full backend suite for the
> first time** and reports **900 passed, 17 failed, 170 skipped**.
>
> The 17 failures are **genuine pre-existing bugs/gaps in `main`'s backend
> (multi-agent ML) code** — none are related to the frontend PR, which changes
> zero Python application logic. They were invisible until now because CI never
> reached this step (it died at the billing gate, then at each plumbing layer).
>
> This document triages them for a **separate, backend-owned PR**.

## Summary by category

| # | Category | Count | Risk to fix |
| --- | --- | --- | --- |
| 1 | Reward-safety divergence counter not incrementing | 6 | Medium — RL reward shadow logic (ADR-031) |
| 2 | Torch model bugs (shape / soft-update / gradient) | 4 | High — ML correctness |
| 3 | Train-smoke missing data fixture | 4 | Low — CI data/fixture or skip-guard |
| 4 | Pricing reward returns NaN | 1 | High — reward math |
| 5 | `api/tests` needs `psycopg2` | 1 | Low — CI dependency |
| | **Total** | **17** | |

## 1. Reward-safety divergence counter (`assert 0 >= 1.0`) — 6 failures

All six assert that overriding a reward kwarg increments
`REWARD_WEIGHT_DIVERGENCE_TOTAL` (shadow-mode divergence counter, ADR-031), but
the counter stays at 0.

- `agents/demand_prophet/tests/test_reward_safety.py::test_kwarg_override_triggers_divergence_counter`
  — `… {key=crps_weight} to increment on kwarg override`
- `agents/disruption_shield/tests/test_reward_safety.py::test_kwarg_override_triggers_divergence`
- `agents/freshness_guardian/tests/test_reward_safety.py::test_kwarg_override_triggers_divergence`
- `agents/pricing_oracle/tests/test_reward_safety.py::test_essential_penalty_override_triggers_divergence_counter`
- `agents/routing_navigator/tests/test_reward_safety.py::test_kwarg_override_triggers_divergence`
- `agents/sustainability_agent/tests/test_reward_safety.py::test_kwarg_override_triggers_divergence`

**Likely cause:** the shadow-mode divergence instrumentation in the reward
functions (or its Prometheus counter wiring) regressed, or the tests were
written against an interface the reward modules no longer expose. Six agents
fail identically → a single shared root cause in `synapse_common.reward_shadow`
or the per-agent `rewards.py` override path. Owner should confirm whether the
counter or the test expectation is correct.

## 2. Torch model bugs — 4 failures

- `agents/demand_prophet/tests/test_model.py::TestTFT::test_forward_pass`
  — `RuntimeError: The size of tensor a (30) must match the size of tensor b (4) at non-singleton dimension 1`
- `agents/demand_prophet/tests/test_model.py::TestHybrid::test_forward_pass` — same shape error
- `agents/demand_prophet/tests/test_model.py::TestHybrid::test_deterministic_output` — same shape error
- `agents/pricing_oracle/tests/test_model.py::TestPricingMADDPG::test_soft_update`
  — `Target network should have changed after soft update` (target == source; soft update is a no-op)
- `agents/supplier_trust/tests/test_model.py::TestSupplierTrustGNN::test_gradient_flow`
  — `assert None is not None` (a parameter's `.grad` is `None` → no gradient reached it)

**Likely cause:** real ML implementation regressions (a tensor-shape mismatch in
the TFT/Hybrid forward pass; a broken `soft_update` τ-interpolation; a detached
parameter in the GNN). These require understanding the intended architecture —
**do not fix blind**; a wrong "fix" could mask a genuine model bug.

## 3. Train-smoke missing data fixture — 4 failures

All four:
`FileNotFoundError: …/data/bengaluru/demand_history.csv`

- `agents/demand_prophet/tests/test_train_smoke.py::test_smoke_train_takes_real_gradient_steps_and_learns`
- `…::test_smoke_train_writes_a_loadable_checkpoint`
- `…::test_smoke_train_reports_a_coverage_metric`
- `…::test_smoke_train_is_deterministic_checkpoint_sha`

**Likely cause:** the smoke-train tests need a seed dataset that CI does not
generate (`make seed` / `scripts/convert_to_parquet.py` is not run in the
unit-test job). ADR-042 E-S CURRENT.md note `C38/C40` references a dedicated
"Training Smoke" job — these tests may belong there (gated) rather than in the
always-on unit run, OR the job needs a `make seed` step / the tests need a
`skipif(not data.exists())` guard. **Lowest-risk** of the set.

## 4. Pricing reward NaN — 1 failure

- `agents/pricing_oracle/tests/test_reward.py::TestEssentialCapViolation::test_catastrophic_penalty_weight`
  — `assert nan < 0` (an essential-cap violation should make total reward
  negative, but the reward computes `NaN`).

**Likely cause:** a `log`/`div`-by-zero or an `inf - inf` in the
essential-cap penalty path produces NaN. Real reward-math bug (relates to I-6,
the essential-SKU price cap). High-value to fix but needs the reward author.

## 5. `api/tests` needs psycopg2 — 1 failure

- `api/tests/test_decisions_auth.py::test_recent_authorized_then_dsn_fail_fast`
  — `assert 'POSTGRES_DSN' in "audit unavailable: No module named 'psycopg2'"`

**Cause:** the `recent` decisions handler imports `psycopg2` lazily; with it
absent, the error message is the import error, not the expected "POSTGRES_DSN
not configured" fail-fast. `api/tests` was added to the gated pytest scope
(Plan v2 §Phase 4) but `psycopg2`/`psycopg2-binary` is not installed in the
unit-test job. **Low-risk CI fix:** add `psycopg2-binary` to the install step
(E-S5-09 notes `psycopg2-binary` is the dev/test variant). This is the one item
arguably adjacent to this PR (it newly enabled `api/tests`), but it is a backend
test against backend code, so it is grouped here for a single backend cleanup.

## What CI plumbing was already fixed (and is green)

These were repaired in PR #13 to make the failures above *visible* and are
**not** part of the backend cleanup:

- Ruff lint + format debt (`agents/*/tests`, `orchestrator/tests`)
- mypy crash on a transitively-downgraded `pathspec` (forced-upgrade last)
- 8 `mypy --strict` `[type-arg]` ndarray annotations
  (`pareto.py`, `meta_agent.py`, `monte_carlo.py`)
- `pip install -e packages/` so `synapse_common` imports in the unit-test step
- `starlette<0.38` pin (fastapi 0.111 compat) forced after `sse-starlette`
- pnpm `auditConfig.ignoreGhsas` for the dev-only vitest advisory
- `numpy`/`pandas` for the consumer-driven-contracts job

## Recommendation

Open a dedicated **`fix/backend-unit-test-failures`** PR owned by the
agents/ML maintainers. Suggested order (low→high risk):

1. Item 5 (psycopg2 install) + Item 3 (seed data or skip-guard) — CI/fixture.
2. Item 1 (the 6 reward-divergence counters) — one shared root cause.
3. Items 2 & 4 (torch model + NaN reward) — require ML-author review.
