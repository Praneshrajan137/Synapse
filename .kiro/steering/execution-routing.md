---
inclusion: always
---

# Execution Routing — where a workload runs, decided by table not by judgement

Subordinate to `local-compute-budget.md` (I-0). **I-0 governs how much; this governs where.**

## The measured machine

Measured 2026-09-11 with `Get-CimInstance`, not asserted. Both prior figures were wrong: a
session claimed 14 GB and I-0 claimed 16 GB.

| | Measured |
|---|---|
| Model | Lenovo 83GS |
| RAM | **15.71 GB** physical and OS-visible; **6.86 GB free** at measurement |
| CPU | i5-12450HX — **8 physical / 12 logical** (hybrid P/E cores) |
| GPU | RTX 3050 **6 GB** Laptop + Intel UHD integrated |

**Two consequences that are easy to get wrong.** Only ~44% of RAM was free, so the binding
limit is often *available* memory, not total. And **no workload in this repository needs the
GPU** — it is Python, TypeScript and SimPy — so reserve no budget for it and treat any GPU
workload as out of scope for the laptop entirely.

## The asymmetry this document exists to exploit

One thermally-throttling laptop. **GitHub Actions is free and unmetered** (public repo,
standard runners) **and runs jobs in parallel at no extra cost.**

> **CI is the execution substrate. The laptop is an authoring and reading terminal.**

Unused headroom, from committed `timeout-minutes`: `quality-gates` 15, `uplift-verify` **60**
(using ~27), `truth-gates` 25, `integration` 15–40, `twin-regret` 120, `uplift-proof` 350.

**But know what CI actually buys.** CI gates **discharge**, not **authoring**. Adding runner
capacity does not make a leaf get written; it makes a written leaf get judged. Optimise
authoring with parallel agents and discharge with CI, and do not confuse the two.

## The cost metric is core-seconds

Thermal throttling tracks **sustained** load. A 3-second `ruff` and a 20-minute `pytest` are
not the same workload at the same core count, and a kind-based taxonomy cannot say so.

> **cost = cores × wall-seconds.** I-0's five categories remain as fast heuristics.

Reference points measured on this machine: a 3-file scoped `pytest` at `dev` ≈ 50 core-seconds;
the same at `ci` (500 examples) ≈ 90; `mypy --strict -m uplift.regret` ≈ 60; a cheap gate ≈ 1.
A repo-wide `pytest` saturating 12 threads for 20 minutes ≈ **14,400** — a ~290× spread, which
is what makes the metric worth having.

**No session ceiling is stated here, deliberately.** Inventing one before measuring would be
the fabrication this project refuses. Record actual core-seconds each session; the ceiling is
set from the first three readings under this rule.

## THIS TABLE IS AN ALLOW-LIST. Unlisted or UNMEASURED means CI.

Finding 55's lesson applied to compute: **a deny-list is fail-open by construction.** An agent
may run locally **only** what appears here as LOCAL. Absence is not permission.

### The 35 audit gates in `scripts/audit/`

| Verdict | Gates |
|---|---|
| **LOCAL** — pure file/AST readers, ~1s each | `gate_surface` · `pin_extractor_truth` · `sweep_budget_truth` · `dataset_licence_truth` · `task_claim_truth` · `workflow_shape_truth` · `spec_ledger_census` · `command_path_truth` · `ratchet_truth` · `required_checks_truth` · `module_liveness` |
| **LOCAL** — stdlib AST only, per `ci.yml`'s own step comment | `substance_truth` · `training_truth` · `serving_truth` · `confidence_basis_truth` |
| **LOCAL, seam or pure function only** | `replay_metrics` through its `measurers` seam · `doc_truth.documented_value` and `.extract_source_values` as **pure functions** — never the module's CLI |
| **NEVER LOCAL** — each executes the whole Check_Registry or a sweep | `verify_claims` · `doc_truth` (CLI) · `ledger_gen` · `readme_gen` · `registry_gate` · `gate_fault_injection --sweep` |
| **UNMEASURED → treat as CI** until one run records its cost | `agency_truth` · `anchor_truth` · `calibration_truth` · `checkpoint_truth` · `feed_provenance` · `oracle_truth` · `outbox_schema_truth` · `outcome_truth` · `published_checkpoint_truth` · `runtime_substance` · `topic_consumer_truth` · `topic_service_truth` · `uplift_truth` |

**A gate missing from this table is a defect in the table, not a licence to run it.** Thirteen
of thirty-five are unclassified; classifying one is a small, real contribution.

### Tests

| Verdict | Workload |
|---|---|
| **LOCAL** | one bounded invocation, `-m "not slow"`, at most ~3 named files or one narrow directory |
| **LOCAL, and do it** | a scoped **pure-arithmetic** file at `HYPOTHESIS_PROFILE=ci` — ~5–90 s, and it catches what `dev` cannot. Findings 56 and 58's property both failed at 500 and passed at 10 |
| **CI ONLY** | anything `-m slow` · repo-wide `pytest` · `--cov` · `-n auto`/`-j` · `mutmut` · the `nightly` profile |
| **CI ONLY** | `vitest` at all · Playwright · Schemathesis · `docker compose` · anything binding a port · any `MIN_SCENARIOS`-scale twin run |

**Verify at the budget that will judge you.** For a file with no twin and no network, the `ci`
profile costs seconds. Two consecutive findings were bought by CI that a local `ci` run would
have caught first.

### Lint, types, build

| Verdict | Workload |
|---|---|
| **LOCAL** | `ruff check` / `ruff format --check` on changed files, or at CI's exact scope (386 files, ~2 s) |
| **LOCAL** | `mypy --strict -m <dotted non-test module>` |
| **CI ONLY** | `mypy --strict` over `tests/**` — the closure drags `uplift/__init__` → `scipy`, exceeding a 120 s budget. **No CI step type-checks `tests/` either; say so rather than implying coverage** |
| **CI ONLY** | `pnpm` anything · `vite build` · full-project `tsc` |

Mixing `scripts/audit/*.py` and `tests/**` in one `mypy` invocation fails instantly with
"Source file found twice".

## Two committed footguns — measured, not suspected

1. **`conftest.py` loads `default` = 500 examples when `HYPOTHESIS_PROFILE` is unset.**
   Verified by importing `conftest` itself: unset → **500**, `dev` → 10, `heavy` → 100,
   `ci` → 500. **An unexported variable is a 50× local load.** Always set it explicitly, in
   the same command.
2. **`pyproject.toml`'s `testpaths` omits `digital_twin`**, which `ci.yml::uplift-verify`'s slow
   step collects explicitly. So a bare `pytest` and CI **disagree about what the suite is**, and
   a local green over `testpaths` says nothing about `digital_twin/tests`.

Also: `addopts` carries `-v`, so every local run is verbose by default. That is why one job-log
read cost 112 KB of truncated output — filter reads, never dump them.

## Escalation, cheapest first

1. **Add a parallel job** to an existing workflow. Jobs are free and concurrent; a serial step
   inside one job is the expensive shape.
2. Add a step to an existing job.
3. GCP runner / VM (`cd-gcp.yml`, ADR-036 window).
4. Only then ask — stating expected wall-clock **and core-seconds**, and wait for an explicit yes.
