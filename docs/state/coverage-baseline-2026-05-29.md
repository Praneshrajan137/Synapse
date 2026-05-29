# SYNAPSE — Coverage / Mutation / Spec-Coverage Baseline (Pre-Sprint-13)

> **Dated:** 2026-05-29
> **HEAD:** `5e75226` (Sprint 12 — Round 4)
> **Plan:** [plans/i-want-the-coverage-vectorized-eagle.md](../../plans/i-want-the-coverage-vectorized-eagle.md)
> **Method:** Direct `pytest --cov-branch` invocations on a Windows 11 dev box (Python 3.14.0). Heavy ML deps (torch, lifelines, pymoo, torch_geometric) are NOT installed locally — the CI Linux runners will measure those packages authoritatively. Rows marked **(CI-must-measure)** carry zero local signal; the CI run after this plan's Phase 1.3 lands is the canonical source.

This file is the floor input to `infrastructure/quality/coverage-floors.yaml`. Every per-package floor in the YAML is set to `floor(measured) − 0.5` so the CI is green on day one but cannot regress. Floors only ratchet upward via `scripts/coverage_ratchet.py` after each test-PR.

The "84% target" and "ratchet" columns describe how far each package has to climb before it hits the spec destination. The math: `gap = target − measured`. Phases 3-5 of the plan are sized by the aggregate gap.

---

## Per-package coverage (line + branch combined, `--cov-branch`)

| Package | Measured line+branch % | Set CI floor | 84% target | Gap | Source |
| --- | --- | --- | --- | --- | --- |
| `packages/synapse_common` | **61.18** | 60.5 | 84 | +22.8 | local (clean) |
| `orchestrator` (subset — 3 tests excluded for missing pymoo/sse-starlette) | **30.11** | 30.0 | 84 | +53.9 | local (partial; CI run with full deps will be higher) |
| `agents/supplier_trust` (subset — 4 collection errors) | **3.69** | 3.0 | 84 | +80.3 | local (partial; CI-must-measure for true number) |
| `agents/demand_prophet` | _no local signal_ | TBD | 84 | TBD | **CI-must-measure** (torch required) |
| `agents/disruption_shield` | _no local signal_ | TBD | 84 | TBD | **CI-must-measure** (torch required) |
| `agents/freshness_guardian` | _no local signal_ | TBD | 84 | TBD | **CI-must-measure** (torch + lifelines) |
| `agents/inventory_sentinel` | _no local signal_ | TBD | 84 | TBD | **CI-must-measure** (torch required) |
| `agents/pricing_oracle` | _no local signal_ | TBD | 84 | TBD | **CI-must-measure** (torch required) |
| `agents/routing_navigator` | _no local signal_ | TBD | 84 | TBD | **CI-must-measure** (torch required) |
| `agents/sustainability_agent` | _no local signal_ | TBD | 84 | TBD | **CI-must-measure** (torch required) |

**Total tests collected (local):** 574 (vs. 600+ expected in CI). 29 collection errors are all missing-dep import failures, not real test failures.

### Synapse_common — modules contributing most to the 22.8-point gap

| Module | Stmts | Branch | % | Notes |
| --- | --- | --- | --- | --- |
| `budget.py` | 62 | 14 | **0%** | Pure tier-budget state machine. Highest yield in repo. |
| `dbc.py` | 13 | 0 | **0%** | Precondition/postcondition decorators. Trivial to test. |
| `dpdpa.py` | 82 | 18 | **0%** | DPDPA cascade helper. DB calls — needs mocks. |
| `langsmith_client.py` | 34 | 6 | **0%** | I/O wrapper (LangSmith). Low test value. |
| `outbox.py` | 16 | 0 | **0%** | Transactional outbox helpers. |
| `reward_shadow.py` | 26 | 8 | **0%** | Shadow-mode reward evaluator. Pure logic. |
| `schema_registry.py` | 109 | 24 | **0%** | JSON Schema registry. Pure load/validate/cache. |
| `tracing.py` | 114 | 12 | 25% | OpenTelemetry — mostly I/O to collectors. |
| `clients.py` | 57 | 8 | 66% | Feast/Neo4j/Redis client wrappers. |
| `kafka_client.py` | 81 | 16 | 64% | Used by retry tests; remaining gap is error paths. |
| `lifespan.py` | 107 | 12 | 75% | App lifespan; remaining gap is teardown paths. |

Closing the four pure-logic 0% modules (`budget`, `dbc`, `outbox`, `reward_shadow`, `schema_registry`) alone yields ~230 covered statements and pushes the package from 61 → ~80. Phase 3 targets these first.

### Orchestrator — modules contributing most to the 53.9-point gap

| Module | Stmts | % | Notes |
| --- | --- | --- | --- |
| `audit/hash_chain.py` | 17 | **0%** | Crypto-critical. Phase 3 target. |
| `audit/logger.py` | 38 | **0%** | Deterministic serialization. Phase 3 target. |
| `audit/anchorer.py` | 49 | **0%** | Daily anchor publication. |
| `audit/archiver.py` | 72 | **0%** | Archive to MinIO. I/O-heavy. |
| `consensus/brownout.py` | 74 | **0%** | Tests exist but fail (config/registry issue — Phase 1.4). |
| `consensus/pareto.py` | 50 | **0%** | Needs pymoo (not installed locally). |
| `consensus/protocol.py` | 169 | **0%** | LangGraph consensus loop. Heavy. |
| `inference/serve.py` | 131 | **0%** | FastAPI app — integration territory. |
| `llm/ollama_client.py` | 88 | **0%** | I/O wrapper. |
| `replay/*` | 53 | **0%** | Decision replay machinery. |
| `state_machine.py` | 75 | **0%** | Orchestrator FSM. |

The orchestrator gap is dominated by `protocol.py`, `serve.py`, `state_machine.py`, and audit modules. Phase 3 targets audit first (hash_chain + logger = high crypto value, low LOC), then expands.

### Failing-not-erroring tests (orchestrator, local)

10 failures in `orchestrator/tests/test_brownout.py` + 1 in `test_deal_contracts.py` — these are **real test failures on local**, not collection errors. CI may pass these if the underlying issue is platform-specific. Plan Phase 1.4 includes investigating; if they fail in CI too they're a pre-existing red gate we inherited and must address before the coverage gate flip.

---

## Mutation testing baseline

### Frontend (Stryker)

| Field | Current | Plan target |
| --- | --- | --- |
| `frontend/stryker.conf.json:33` `break` | **26** | 50 |
| Last reported kill % (recon JSON) | ~34 (18/53 killed) | ≥50 |
| Workflow gating | PR + `v*` tags only (`.github/workflows/frontend.yml:165`) | unchanged |

Path to 50%: kill ~9 of the currently-surviving mutants in `jitter-retry.ts`, `http-client.ts`, `firehose.store.ts`. Phase 4.1 work item. **NOT measured by this plan execution** — requires local `pnpm exec stryker run` against the Chromium runtime; deferred to a follow-up PR with a fresh report.

### Python (mutmut)

| Target | CLAUDE.md spec | Current gating |
| --- | --- | --- |
| `agents/*/training/rewards.py` | < 15% survival | Sunday cron + dispatch only (NOT PR-blocking) |
| `orchestrator/guardrails/rules.py` | < 10% survival | same |
| `orchestrator/audit/logger.py` | < 10% survival | same |

**Local mutmut run was NOT executed** — `mutmut` on Windows is documented in the plan's §Risks-the-user-may-not-know as flaky; the canonical run is the CI Linux job. Phase 4.2 wires `mutation-fast` on PR for changed files, which becomes the first PR-blocking Python mutation gate (parity with frontend Stryker; closes C30).

---

## Spec-coverage baseline

`scripts/check_spec_coverage.py` runs in 0.4s and substring-matches every `INV-*` ID against `agents/*/tests/test_spec.py`. The current substring-mode aggregate is **claimed 100% in CLAUDE.md but unverified** — the script was never wired into CI as a blocker, so any regression has been silent.

| Agent | Invariants declared (from spec.yaml) | Substring-matched (today) | Assertion-matched (Phase 5.2 mode — to measure) |
| --- | --- | --- | --- |
| demand_prophet | ~9 | TBD on Phase 1.4 run | TBD |
| disruption_shield | ~5 | TBD | TBD |
| freshness_guardian | ~5 | TBD | TBD |
| inventory_sentinel | ~5 | TBD | TBD |
| pricing_oracle | ~7 | TBD | TBD |
| routing_navigator | ~5 | TBD | TBD |
| supplier_trust | ~5 | TBD | TBD |
| sustainability_agent | ~6 | TBD | TBD |
| **Aggregate** | **~47** | TBD | TBD |

Phase 1.4 runs the script and fills in the substring column. Phase 5.1-5.2 extends the script to compute the assertion-matched column (`ast` walk requiring an `assert` within 20 lines of an `INV-*` ID) and emit a percentage. The CI gate enters at `--threshold 50` (Phase 5.3), ratcheting toward 100.

---

## How this file evolves

- After Phase 1.3 lands the expanded CI scope, the **next CI run on `main` replaces every "CI-must-measure" row** with a real number. A PR that updates this file with those measurements is part of the Phase 2 PR.
- After every test-PR that closes part of the gap, `scripts/coverage_ratchet.py` bumps the floor in `infrastructure/quality/coverage-floors.yaml` — this file becomes the running narrative of the climb.
- When all 10 packages reach the 84% target, this file is renamed `coverage-baseline-FINAL.md` and the verify_claims C28 row flips to PASS at 84%.

This file is the WS-9-lesson made concrete: floors set against measured numbers, ratcheted, never aspirational.
