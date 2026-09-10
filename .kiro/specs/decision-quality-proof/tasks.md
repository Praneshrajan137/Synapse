# Implementation Plan: Decision Quality Proof

> ## SESSION PROTOCOL — READ FIRST
>
> **Work on this spec is batched: at most THIRTY leaf tasks per session, in three waves of about
> ten, then STOP. The ceiling is expected never to bind — barriers and phase boundaries are what
> stop a session.**
>
> The binding agreement, the batch plan, the two CI checkpoints, the verification sweep and the
> resolved tasks-11→12 circularity all live in
> [`SESSION_PROTOCOL.md`](./SESSION_PROTOCOL.md). The prompt to paste when opening a new session is
> [`NEXT_SESSION_PROMPT.md`](./NEXT_SESSION_PROMPT.md).
>
> **No count is written here.** Derive it:
> `python -m scripts.audit.spec_ledger_census --next 30`. That command is the census; every
> document cites it and none transcribes it. It also names every **barrier** the offered batch
> steps over — an open CI-gated checkpoint with offered ids behind it. Answer each one.
>
> **Three marks, because the honesty contract has three states (I-7).**
> `[ ]` open · `[~]` **authored, discharge pending** — the work is on disk and the proof is owed
> by the job named in its `discharge:` line · `[x]` done **and** discharged. A `[~]` is not a
> pass. "Authored and diagnostics-clean, not executed" is a legitimate result; recording it as
> `[x]` is the I-7 violation. An open leaf carrying a `discharge:` line is CI-gated and is not
> offered as authorable work.
>
> **DISK OUTRANKS THIS LEDGER.** Session 1 opened with eight tasks fully implemented on disk and
> still showing `[ ]`. Run `--files` before authoring, verify a task's artifacts do not already
> exist, and read the cited requirement criteria rather than treating file existence as
> completion.

## Overview

This plan covers all five elements. **Phases 0-2** (tasks 1-14) are **E0** (instrument hygiene,
R2/R3/R4), **E1** (gate falsifiability, R1), **E4a** (feed admission,
R8.1/R8.2/R8.16/R8.17), and **E2a / E2b / E2c** (twin decision-relevance, R5). **Phases 3-5**
(tasks 15-25) are **E3** (controlled experiment, R6/R7), **E4** (train, benchmark, publish,
R8.5-R8.15/R8.18/R9) and **E5** (measured uplift, ratchet, external anchor, R7/R10).

**Execution order, and the two edges that must not be reordered.**

```
E0  ->  E1  ->  { E2a , E4a }  ->  E2b  ->  E2c  ->  { E3 , E4 }  ->  E5
```

- **E2a before E2b** is load-bearing. Instrument the twin first, or the null is an
  instrumentation artefact rather than a measurement (R5.35, AD-17's separation clause). All
  six KPI fields are blind to stock availability today, so a regret of zero measured before
  E2a says nothing about the world.
- **E2b before E2c** is load-bearing, and it is deliberate: the `(s, S)`-regret test can
  **falsify Finding 4** and shrink R5's entire scope (R5.3, R5.4). It is sequenced early
  specifically to try to kill this spec's central claim before the project spends its largest
  single block of work on a premise it declined to test.
- **E4a before E2c** follows CF-7: R5.11 calibrates the demand shape from Real_Data_Feed
  statistics, so the licence artifact and the statistics extraction must land before
  structure 1.

**I-0 (local compute budget) is a first-class constraint on this plan.** Nothing here is
runnable on the dev box. Every heavy step names the CI job that owns it:

| Workload | Owning job | Category under I-0 |
|---|---|---|
| Falsification sweep (30 gate subprocesses over a tree copy) | `truth-gates.yml::falsification-sweep` (NEW) | 2/3 — CI Linux only, R1.13, precedent E-S13-05 |
| Fast Python properties | `ci.yml::uplift-verify` fast step (`-m "not slow"`, `HYPOTHESIS_PROFILE=ci`) | 5 |
| Slow Python properties (real SimPy twin) | `ci.yml::uplift-verify` slow step (`HYPOTHESIS_PROFILE=heavy`) | 3 — CI only |
| `digital_twin` non-slow properties | `ci.yml::quality-gates` (`-m "not slow"`, `default` budget) | 5 |
| Console properties | `frontend.yml::quality` | 2 — CI only |
| Twin measurement sweeps, regret comparator, utilisation ladder | `uplift.yml` (R5.32) | 4 — CI only |

**`-m "slow"` is a selector, not a path filter.** Every slow-marked property below names the
job that both *collects its path* and *selects on the marker*. Verified while authoring:
`ci.yml::uplift-verify`'s slow step already runs
`pytest tests/uplift tests/verify orchestrator/tests/consensus digital_twin/tests -m "slow"`,
so the four paths this plan places properties under are collected today. No path widening is
needed — but any property placed outside those four paths would be selected by **no job at
all**, which is the failure mode `ci.yml`'s own comment records.

**Example budgets are inherited, never hardcoded.** Every Python property inherits
`max_examples` from the root `conftest.py` profiles (`dev`=10, `heavy`=100, `ci`/`default`=500,
`nightly`=5000) via `HYPOTHESIS_PROFILE`. Every TypeScript property inherits `numRuns` from
`fc.configureGlobal` in `frontend/src/test/setup.ts` (task 1.2). **No task below may write a
literal `max_examples=` or a per-call `numRuns`** — that is what amplified the original I-0
incident, and CF-13 records that the tree already carries more violations than the steering
file states.

**Properties: 38-79.** Each gets its own sub-task, tagged
`# Feature: decision-quality-proof, Property {N}: {title}`. Properties 38-59 land in phases 0-2;
properties 60-79 land in phases 3-5. Properties **68** and **69** belong to E4a's subject but are
numbered inside E4's block, so they land in task 19 rather than task 7 — task 7.5 carries unit
tests in the interim, and that is a stated sequencing gap, not an omission.

---

## Tasks

### Phase 0 — E0: instrument hygiene (R2, R3, R4)

- [x] 1. Make the console property surface visible to CI and make its budget inherit a profile
  - Implements **AD-13's inheritance rule** and the design's "Hypothesis budget" reuse row:
    the fast-check analogue of `conftest.py`'s profiles, resolved from the same variable.
  - Sub-tasks 1.2, 1.3 and 1.4 are a **single logical move**: R3.8 requires the
    gate's `>= MIN_NUM_RUNS` clause and its no-`numRuns` clause never to coexist, because the
    two rules are contradictory and a half-move leaves the gate red on the files 1.3 just
    corrected.

  - [x] 1.1 Commit the five declared console property files
    - Files: `frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts`,
      `frontend/spec/effectiveness/__tests__/scorecard-completeness.property.test.ts`,
      `frontend/spec/effectiveness/__tests__/ratchet-sensitivity.property.test.ts`,
      `frontend/spec/effectiveness/__tests__/interruption-precision-responsiveness.property.test.ts`,
      `frontend/spec/effectiveness/__tests__/baseline-measurement.property.test.ts`
    - All five are untracked-but-not-ignored (`git check-ignore` returns nothing for any),
      so CI cannot see them at all. This is the precondition for every other E0 sub-task.
    - _Requirements: 2.1_

  - [x] 1.2 Add the fast-check budget resolver to the vitest setup file
    - **DISCHARGED on PR #84, run for `85ed97a`. `frontend.yml::quality` is GREEN — all ten steps,
      including step 6 Biome lint, step 7 TypeScript strict, and step 8 `Vitest unit + property
      tests`.** That is the job this task's `discharge:` line named, so the mark is earned rather
      than asserted. It took two repair commits to get there, and the `[~]` mark is what kept the
      claim honest in between.
    - **The route to green, because it is the record of what the third ledger state bought.** Session
      1r marked this `[~]` rather than `[x]` because no run or gate had ever judged it. PR #84's
      first run then failed on Biome, naming ONE finding. Session 2p repaired that and claimed the
      job would go green. **It did not** — CI reported `Found 3 errors`, and reading the run
      job-by-job found **four** error-level findings in total, all authored by this branch's own
      commit `5db5eb1`:
      1. `frontend/src/test/setup.ts` — `organizeImports`. Biome 1.9.4 sorts named specifiers by
         ASCII code point with the `type` keyword ignored, so SCREAMING_CASE precedes camelCase.
      2. `frontend/src/test/fc-budget.ts:163` — `lint/complexity/useLiteralKeys`. **This task's own
         module**, and the finding was unrecorded.
      3. `frontend/src/test/fc-budget.ts` — two `format` violations, on an LF file, so real on CI.
      4. `frontend/src/surfaces/operations/SloBurnBoard.tsx:114` — `lint/complexity/noUselessTernary`,
         attributed to `5db5eb1` by `git blame -L 112,116`.
      Plus three more format errors found only by reading the CI log against the local run:
      `DataPathNotice.tsx`, `surfaces/data-paths.ts`, `lib/interruption-precision.ts`.
    - **Two corrections to what was recorded about the CI run.** The finding attributed to PR #77 —
      `noNonNullAssertion` at `primary-surfaces.property.test.ts:33` — is configured `warn`, and
      `biome check` on that file exits **0**. It never failed anything. And "zero error-level
      findings remain" was wrong: it came from over-generalising a single proof that one of 40 local
      format errors was a `core.autocrlf` artifact.
    - **The mechanical proof that replaced the over-generalisation:** `biome format --write ./src`
      reports "Fixed 40 files" while `git diff` shows exactly **3** changed, because git normalises
      line endings under autocrlf. The 37 are line-ending-only; the 3 are the ones CI named.
    - **A trap for whoever lints this tree on Windows.** `biome check ./src` reports ~40
      `needs to be formatted` errors that do not exist on CI, for that same reason. **Do not "fix"
      them** — a `format --write` sweep commits line-ending churn across untouched files and changes
      nothing about the gate. A local Biome run is admissible evidence per file, on LF files, and not
      as a whole-tree exit code.
    - File: `frontend/src/test/setup.ts` (already wired as `setupFiles` in
      `frontend/vitest.config.ts:26`, and contains no fast-check configuration today, so this
      is a net addition rather than a change to an existing knob).
    - Resolve `fc.configureGlobal({ numRuns })` from `HYPOTHESIS_PROFILE` using the same
      profile names `conftest.py` registers. Unset or unknown resolves to `dev` = 10 (R3.2's
      deliberate asymmetry with the Python side's `default` = 500: an unset variable is the
      local case, and the local case must be the cheap one under I-0).
    - Report the effective count into the run record so a silently failed global is
      distinguishable from one that applied (R3.9) — fast-check's own fallback is reportedly
      100, which would look CI-legal while costing a laptop ten times the intended budget.
    - _Requirements: 3.1, 3.2, 3.5, 3.9_

  - [x] 1.3 Remove every per-call `numRuns` from the five declared files
    - Files: the five files named in 1.1.
    - A per-call value overrides `configureGlobal`, so 1.2 changes nothing until this lands.
      Only `degradation-rendering.property.test.ts` was re-verified during requirements
      authoring (10 occurrences, all `{ numRuns: 100 }`); the other four counts are
      unverified, so the sub-task is "remove all occurrences found", not "remove 10".
    - _Requirements: 3.3_

  - [x] 1.4 Invert the inventory gate's TypeScript budget clause and give it a counting rule
    - File: `tests/verify/test_property_inventory_consistency.py`
    - Remove `test_every_typescript_property_test_states_a_run_budget_of_at_least_100`
      (`:624`) and the no-`numRuns`-declared failure at `:637`/`:639`; add a rule that fails on
      **any** `numRuns` option in a declared TypeScript property file, literal or computed,
      mirroring the existing `max_examples` rule for Python (`:599`).
    - Add the executable-only counting rule for `_HARDCODED_MAX_EXAMPLES_RE` (`:233`) so
      docstring and comment occurrences are excluded — the regex currently matches a docstring
      line at `tests/uplift/test_baseline_determinism_conformance.py:22`, so without the rule
      two testers get two totals. Report the count and name each offending file and line; do
      **not** assert a total (CF-13).
    - _Requirements: 3.4, 3.6, 3.7, 3.8_

  - [x] 1.5 Write property test for the fast-check budget resolver
    - **DISCHARGED on PR #84, run for `85ed97a`, by step 8 `Vitest unit + property tests` of a green
      `frontend.yml::quality`.** Discharged by **execution**, which for this file is the only route
      there was — and that is worth stating precisely, because three separate local checks cannot
      reach it:
      - `biome check ./src` **never scans `frontend/spec/`**, so this file is not linted by that
        step at all.
      - `frontend/tsconfig.json`'s `include` names only `frontend/spec/effectiveness/harness.ts`
        and `frontend/spec/effectiveness/e2e-entry.ts`, **not**
        `frontend/spec/effectiveness/__tests__/**`. So the `pnpm typecheck` pass that went green
        for 1.2 did **not** compile this file. The only job that type-checks it is
        `frontend.yml::spec-typecheck`, which is **still red** and remains out of scope for repair
        (R2.15: a prediction is not a dispensation).
      - `frontend/vitest.config.ts`'s `include` **does** cover
        `frontend/spec/effectiveness/__tests__/**`, which is why the vitest step is what discharged
        it — and why I-0's ban on `vitest` meant nothing local could ever have judged this task.
    - **So this task is the clearest case in the spec for why `[~]` exists.** It was authored in
      session 1, could not be verified locally by construction, and sat behind two other steps'
      failures for three CI runs before its own step ever executed. An `[x]` at authoring time
      would have claimed a pass that nothing had produced.
    - `# Feature: decision-quality-proof, Property 42: The fast-check budget is a total function of the profile name`
    - File: `frontend/spec/effectiveness/__tests__/fc-budget-profile.property.test.ts`
    - Budget inherited from `fc.configureGlobal` in `frontend/src/test/setup.ts`. No per-call
      `numRuns` in this file either — the property under test is the global itself, so it reads
      the resolver as a pure function rather than configuring one.
    - Locus: `frontend.yml::quality`.
    - _Requirements: 3.1, 3.2, 3.5, 3.9_

  - [x] 1.6 Write property test for the inventory gate's budget rules
    - `# Feature: decision-quality-proof, Property 43: The inventory gate rejects any in-place budget and counts only executable assignments`
    - File: `tests/verify/test_inventory_budget_rule_property.py`
    - Budget inherited from the root `conftest.py` profile via `HYPOTHESIS_PROFILE`.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 3.4, 3.6, 3.7_

- [x] 2. Turn the console run record into a per-file verdict
  - Implements the design's "Console run record" row: the record already exists as a
    configuration (`vitest.config.ts` `reporters: ["default","json"]` ->
    `artifacts/test-reports/vitest.json`); what is missing is a **reader with an `unavailable`
    state**. A file that matches no include pattern produces no entry at all rather than a
    zero count, which is why R2.8 is stated against the record and not against the config.

  - [x] 2.1 Make both type-check steps propagate, and the spec type-check job report honestly
    - File: `.github/workflows/frontend.yml`
    - `pnpm typecheck` in `quality` (`:48`) and `pnpm typecheck:spec` in `spec-typecheck`
      (`:114`) must carry no `continue-on-error` and no construct that discards exit status.
    - While `spec-typecheck` is red, the declared files under `frontend/spec/` are reported
      **not type-checked** — `tsconfig.spec.json`'s own header predicts red on the first run,
      and a prediction is not a dispensation (R2.15).
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.15_

  - [x] 2.2 Add the per-file executed-assertion reader with an `unavailable` state
    - Files: `frontend/spec/check_fe_invariants.py`,
      `infrastructure/quality/fe-invariant-attestation.yaml`
    - For each of the five declared files, read executed, non-skipped assertion counts from
      the machine-readable run record. Absent entry, zero-count entry, `skipped`/`todo`
      status, or an absent/unparseable record each produce a non-passing result — never a
      pass (I-7). A shrunk counterexample names the file, the property title and the minimal
      failing input, and generators are not weakened in response (R2.9, R2.10).
    - Any document referring to a declared file with no CI run record describes it as
      **authored but not executed**; a local `getDiagnostics` probe is inconclusive, not
      evidence (R2.12, R2.13).
    - _Requirements: 2.6, 2.7, 2.8, 2.9, 2.10, 2.12, 2.13, 2.14, 2.16_

  - [x] 2.3 Write property test for the run-record verdict
    - `# Feature: decision-quality-proof, Property 44: The console run record decides five per-file verdicts, and absence is non-passing`
    - File: `tests/verify/test_console_run_record_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 2.6, 2.7, 2.8, 2.9, 2.14, 2.16_

- [x] 3. Make the workflow-shape verdict green under every rule, not just one
  - Implements the design's "Workflow shape" row. C64's verdict is the **disjunction of four
    rules** (`workflow_shape_truth.py::_RULES`) plus the AD-12 bundle assertion, so a fix
    under `unlabelled-advisory` that creates a `blocking-unresolved` finding is not a fix.
  - This task is E0's reason for preceding E1: adding a gating job to an already-red shape
    gate makes the new job's own shape unattributable.

  - [x] 3.1 Correct `terminal_discarding_construct`'s continuation-joined reading
    - File: `scripts/audit/workflow_shape_truth.py`
    - `effective_command_lines` joins continuations into one logical line and
      `terminal_discarding_construct` then runs an unanchored `re.search` over it, so a step
      whose final command *does* decide its exit status is misclassified — same class as the
      `strip_js_comments` fix already recorded in that module. `cd-gcp.yml:404`
      (`deploy-to-vm`::"Pull + restart stack", `|| true` at `:428-431` inside one
      continuation-joined logical line) is the instance. Correcting the reading removes the
      finding without touching `cd-gcp.yml`; attaching an advisory marker to a step whose
      final command decides its exit status would be a false label (I-7).
    - _Requirements: 4.12_

  - [x] 3.2 Resolve the six unrecorded non-propagating steps
    - Files: `.github/workflows/security.yml` (`:67` "Secret detection via gitleaks",
      `continue-on-error` at `:71`), `.github/workflows/terraform-validate.yml` (`:78`
      "tflint (optional, won't block)", `continue-on-error` at `:80` — honest prose carrying
      neither marker word), `.github/workflows/sprint6-e2e-oracle.yml` (`:56` "Preflight — VM
      resources", `:151` "Capture evidence artifacts", `:175` "Teardown (preserve volumes)"),
      `.github/workflows/cd-gcp.yml` (`:404`, if 3.1 did not already clear it),
      `infrastructure/quality/blocking-steps.yaml`
    - Each step is either made to propagate, or labelled at the scope that owns the
      construct — step name for a step-scoped construct, **job display name** for a
      job-scoped one, matched case-insensitively against `ADVISORY_MARKERS`
      (`workflow_shape_truth.py:88`, mirrored in `tests/verify/strategies.py:433`). Precedent
      for the job-scoped form: `ci.yml`'s `v4-compliance` (`:378`, `:381`).
    - **A rename and its declaration move in one commit.** `blocking-steps.yaml` declares step
      names by string, and a rename makes those declarations resolve to no step — which the
      same gate fails on as `blocking-unresolved`.
    - _Requirements: 4.1, 4.2, 4.3, 4.10, 4.13_

  - [x] 3.3 Resolve the three recorded-and-still-findings steps and drop the over-stating entry
    - Files: `.github/workflows/ci.yml` (`:210` `quality-gates`::"Contract tests", `|| echo`
      at `:212`; `training-smoke`::"Measure per-package coverage under full ML stack (binds the
      0.0 floors)", `continue-on-error` at `:553` plus `|| true` at `:562`),
      `.github/workflows/frontend.yml` (`:135` `build`::"Size budget", `|| true` at `:136`),
      `infrastructure/quality/blocking-steps.yaml`
    - Remove the stale `frontend.yml:317` `e2e-visual`::"Generate + commit Linux baselines"
      entry: its `|| true` at `:330` is intermediate and the script's last effective line is
      `fi`, a block terminator, so the step already classifies as propagating and the recorded
      entry over-states.
    - The ledger row reads `unlabelled-advisory=10`; static re-derivation yields **9** across
      6 files. The residual tenth is not reproducible by reading. Do not invent it — let the
      first green run of the corrected gate report the true count.
    - _Requirements: 4.1, 4.10, 4.13_

  - [x] 3.4 Write property test for the shape verdict and label scoping
    - `# Feature: decision-quality-proof, Property 45: The shape verdict is the disjunction of every rule, and a label attaches by construct scope`
    - File: `tests/verify/test_workflow_shape_rule_disjunction_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 4.1, 4.2, 4.10, 4.12, 4.13_

  - [x] 3.5 Write property test for declared-step rename resolution
    - `# Feature: decision-quality-proof, Property 46: A declared step's rename resolves in the tree that renamed it`
    - File: `tests/verify/test_declared_step_rename_property.py`
    - An `exact`-match entry breaks on punctuation alone, which is the whole reason the rename
      and the declaration must land in one commit.
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 4.3_

- [x] 4. Make the published headline a projection of the execution that enforces it
  - Implements **AD-21**. The defect is narrower than "generate the README": **no code path
    writes `README.md`** today. `ledger_gen`'s document constant is `docs/state/CURRENT.md`,
    and `:324` renders the README headline *into CURRENT.md's own generated region*. The
    transcription step is literally "copy `CURRENT.md:119` into `README.md:24`".
  - `README.md:24` (51/3/0/10/64) and `CURRENT.md:119` (52/3/0/9/64) are **two different
    executions**. A generator projecting the top-level counts would make C56 FAIL by exactly
    the recursion-guard delta. AD-21 also rejects the tempting alternative — deriving nested
    counts from the top-level verdict by applying a known one-check delta — as unsound, not
    merely inelegant: at `--write` time top-level C56 is FAIL, so the compensation would be
    computed from a status the write is about to change.

  - [x] 4.1 Promote the nested suite-counts helper to a public function
    - File: `scripts/audit/doc_truth.py`
    - `_suite_counts` becomes `nested_suite_counts() -> tuple[NestedVerdict | None, str]`
      returning the parsed `--json` payload (`{"summary": ..., "checks": ...}`), bounded by the
      existing `_SUITE_TIMEOUT_S = 900.0` and carrying `env[_NESTED_ENV] = "1"`. One execution
      semantics, one implementation, no second model of the guard.
    - _Requirements: 4.4_

  - [x] 4.2 Add the README generator
    - File: `scripts/audit/readme_gen.py` (new)
    - Renders the README's generated region from `nested_suite_counts()`. Imports
      `GENERATED_BEGIN` / `GENERATED_END` from `scripts/audit/gate_surface.py` and reuses
      `ledger_gen`'s `_standalone_marker_offsets` -> `generated_region_bounds`. `--check` is
      the default and diffs at exit 1; `--write` never creates the document; every byte
      outside the region survives, including prose quoting the markers. Zero, multiple, or
      out-of-order markers produce `LedgerMarkersError` -> `unavailable` -> exit 2 with the
      document left byte-identical.
    - Two mechanically checked constraints: the rendered counts line must match
      `doc_truth._VERIFY_CLAIMS_MENTION` (**import the pattern, do not restate it**) or
      `_readme_headline_line` returns `None` and C56 silently **skips**; and R4.8's
      compensation sentence is rendered **in words**, never with digits, so it cannot out-rank
      the counts line under `_extract_count`. Assert the counts line is the unique richest
      candidate in the document just written.
    - Accept `--counts-json PATH` so one nested execution serves both this step and
      `doc_truth --check` — `truth-gates.yml::truth-gates` carries `timeout-minutes: 25` sized
      for a single registry pass.
    - _Requirements: 4.4, 4.5, 4.8, 4.11_

  - [x] 4.3 Add the README generated region and wire the ordered steps
    - Files: `README.md`, `.github/workflows/truth-gates.yml`,
      `infrastructure/quality/blocking-steps.yaml`
    - Insert one standalone `<!-- generated:begin -->` / `<!-- generated:end -->` pair around
      the headline at `README.md:24`, preserving the disclosure prose at `:26`.
    - The two steps are **ordered and the ordering is load-bearing**: `doc_truth --check`
      produces the payload, `readme_gen --check` consumes it. Record the ordering in
      `blocking-steps.yaml` alongside the step names, in the same commit as the step names.
    - _Requirements: 4.4, 4.5, 4.8, 4.11_

  - [x] 4.4 Add the recursion-guard status test
    - File: `tests/verify/test_recursion_guard_status.py` (new)
    - Asserts that with `SYNAPSE_DOC_TRUTH_NESTED` set, the headline-counts claim reports a
      non-passing `required` status naming the guard as the cause — **without executing the
      Check_Registry suite**. A grep for `SYNAPSE_DOC_TRUTH_NESTED`, "recursion" and "nested"
      across `tests/**/*.py` returns no reference today, so R4.9 is genuinely unmet.
    - _Requirements: 4.9_

  - [x] 4.5 Write property test for the README region projection
    - `# Feature: decision-quality-proof, Property 47: The README region is a projection of the comparing execution`
    - File: `tests/verify/test_readme_region_projection_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 4.4, 4.5, 4.8, 4.11_
    - **Attribution conflict, surfaced not resolved:** the design's cross-cutting AD-13
      section states the extractor-resolution clause "is Property 47's second clause", while
      the property index assigns extractor resolution to **Property 48** (R5.2, R5.11, R5.12,
      R6.3) and Property 47 to the README region only. This plan follows the index and lands
      extractor resolution in task 8.3. Raise the discrepancy rather than silently picking a
      side.
  - R4.6 and R4.7 are **already discharged** and are regression pins, not work: every
    `doc_truth` claim carries `required`, and a required claim that cannot be evaluated forces
    the aggregate to `unavailable` with exit 2. The owning obligation is
    `purpose-achievement-audit` R1.4/R1.6. Nothing in E0 re-implements them.

### Phase 1 — E1: gate falsifiability (R1)

- [x] 5. Make the falsification sweep gate a job, with a committed cost budget
  - Implements **AD-22**. The harness already exists (`--sweep`, `--gate`, `--operator`,
    `--timeout`, `--no-baseline`, four-value `Outcome`, `FaultInjectionReport`); what is
    missing is one gating job, a cost budget, and per-operator accountability. A search of
    `.github/workflows/*.yml` and `Makefile` for `gate_fault_injection` or `--sweep` returns
    no match.
  - **The unit of work is an operator, not a check.** 14 declared checks carry 16 operators
    (C44 and C56 declare two each), so every count and every failure message is per-operator —
    per-check reporting cannot identify which of C44's two mutations survived.
  - **AD-22 uses the third option OQ-5 misses.** `truth-gates.yml` carries an unfiltered
    `push: [main, develop, "sprint-*"]` with a comment recording "Deliberately NO paths-ignore
    / paths", **and** an unfiltered `pull_request: [main]`, and its `truth-gates` job is
    already in `required:`. A job there satisfies R1.1 and R1.14 **jointly** with no trade
    (CF-8). `ci.yml`'s `paths-ignore` for `**.md` makes R1.1 literally unsatisfiable there.

  - [x] 5.1 Commit the sweep cost budget as a pinned arithmetic claim
    - File: `infrastructure/quality/gate-mutations.yaml`
    - Add `sweep_budget` with `per_subprocess_timeout_s: 90` (**not** the 900 default),
      `install_budget_s: 420`, `job_timeout_minutes: 60`, and the invariant it must satisfy:
      `(baselines + operators) * per_subprocess_timeout_s + install_budget_s <=
      job_timeout_minutes * 60`, i.e. `30 * 90 + 420 = 3120 <= 3600`.
    - State honestly in the file that lowering 900 to 90 is a reduction from a bound nobody
      measured to a bound nobody measured; a gate that cannot answer inside it reports
      `indeterminate` naming the timeout, which is non-passing and therefore surfaces.
    - _Requirements: 1.11_

  - [x] 5.2 Read the committed budget and refuse baseline suppression
    - File: `scripts/audit/gate_fault_injection.py`
    - Under `--sweep`, read `per_subprocess_timeout_s` from the declaration instead of taking
      `DEFAULT_TIMEOUT_S`. Add `FaultInjectionReport.baseline_suppressed: bool`; a report
      carrying it true has verdict `unavailable` naming baseline suppression as the reason,
      because without a baseline an already-red gate reads as falsified. `--no-baseline`
      remains available for diagnosis.
    - A sweep that cannot start, exceeds the per-gate bound, is signal-terminated, or emits an
      unparseable report records a non-passing result.
    - _Requirements: 1.11, 1.16_

  - [x] 5.3 Register the budget-inequality check
    - Files: `scripts/audit/sweep_budget_truth.py` (new),
      `scripts/audit/verify_claims.py` (`@register`)
    - Asserts the inequality over the declaration's own `declared_gates` and operator count,
      so the budget cannot silently stop fitting when a fifteenth gate declares a mutation.
      This is AD-13 applied to a schedule: the number is committed, read rather than inlined,
      and pinned.
    - _Requirements: 1.11_

  - [x] 5.4 Report per-operator outcomes, derive the counts, and never assert them
    - File: `scripts/audit/gate_fault_injection.py`
    - Per probed operator: check id, operator id, exactly one of `falsified`, `survived`,
      `indeterminate`, `not-applied` (`:364`, pinned as `OUTCOMES` in
      `tests/verify/test_declared_falsification_property.py:112-118`; the report field is
      `falsified_ids` — `killed` is mutmut's word and does not appear here).
    - `survived` or `not-applied` -> exit non-zero naming check **and** operator.
      `indeterminate` -> report which condition caused it: a non-passing unmutated baseline
      **naming that baseline's exit status**, a timeout, or a subprocess that could not start.
      Any non-`falsified` operator excludes its check from the falsified-check count.
    - Report probed count and declared count **in the same unit**; unprobed declarations are
      reported **unproven** (absence of proof is never a pass, I-7); undeclared checks are
      reported undeclared and excluded from PASS-eligibility. The 49 undeclared operators stay
      undeclared — E1 makes the gap visible, it does not close it by invention.
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.15_

  - [x] 5.5 Make the C72 row project the counts of the run that produced it
    - File: `scripts/audit/verify_claims.py`
    - Replace the fixed `no falsification was probed` detail with the probed count, the
      falsified-check count and the unproven count observed in that same job.
    - _Requirements: 1.12_

  - [x] 5.6 Add the `falsification-sweep` job and its declarations in one commit
    - **A THIRD HALF OF THE COUPLING WAS MISSED, AND SESSION 2p REPAIRED IT.** The two
      declarations below landed; the *generated* record of them did not.
      `scripts/audit/gate_surface.py` projects every job and every step of every workflow into
      `docs/state/GATE_SURFACE.md`, so adding a job makes that document stale and flips
      registered check **C63** to FAIL — and `blocking-steps.yaml` says so in its own prose at
      the point where it declines to add two other entries. The committed document named
      neither this job nor `uplift.yml::twin-regret` (task 10.3), and carried
      `52 job(s), 357 step(s)` and `8 declared-blocking entries` against a tree with 54, 370
      and 10. So C63 was red on PR #84 while `docs/state/CURRENT.md:94` records it **PASS**,
      which drifts `ledger_gen --check` too — up to four registered gates from one missed
      regeneration, and `HANDOFF.md`'s CI decomposition had it hidden inside "Truth Gates
      (enforcement spine), predicted red".
      **Repaired by `python -m scripts.audit.gate_surface --write` (+50/-5 lines);
      `--check` now exits 0.** The generator is pure file reads, which is why this was
      affordable under I-0 — `ledger_gen --write` and `readme_gen --write` are **not**, because
      each executes the whole Check_Registry in-process. They should also be unnecessary here:
      `CURRENT.md` already records C63 as PASS, so restoring PASS restores agreement rather
      than moving a count. **That last sentence is a prediction from reading the committed
      ledger, not a verified fact** — verifying it is the escalation the session close records.
    - Files: `.github/workflows/truth-gates.yml`,
      `infrastructure/quality/blocking-steps.yaml`,
      `infrastructure/quality/required-checks.yaml`,
      `docs/state/GATE_SURFACE.md` (generated; added in session 2p)
    - New job, separate from `truth-gates` (whose 25-minute budget is sized for stdlib gates):
      `runs-on: ubuntu-latest` only (R1.13, precedent E-S13-05 — the sweep copies the tree and
      spawns gate subprocesses, a category-2/3 workload, never the Windows dev box); the same
      dependency closure as `truth-gates` (several checks import an optional dependency inside
      `try/except` and SKIP when absent, and a thinner environment turns a probeable baseline
      into an indeterminate one); `concurrency: {group: falsification-sweep-${{ github.ref }},
      cancel-in-progress: false}` following `uplift.yml`'s recorded reasoning that "an
      abandoned run reports nothing, which is not a pass either"; one step,
      `python -m scripts.audit.gate_fault_injection --sweep --check`, with no
      `continue-on-error` and no discarding construct.
    - **Same-commit declaration coupling (R1.14).** The step goes into `blocking-steps.yaml`
      and the job name goes into `required-checks.yaml` — in `required:` since it reports on
      every pull request targeting `main` — **in the same commit as the job**, because
      `required_checks_truth` resolves declared job names against the workflow tree and either
      half alone is a red gate.
    - Do **not** take the `--shard K/N` route yet: matrix jobs produce dynamic status-check
      names, an aggregator without `if: always()` does not run when a shard fails, and a
      skipped job reports its required status check as satisfied. Take the unsharded job
      first, because its measurement is what tells you whether the trade is needed at all.
    - R7.9 is **not** satisfiable here: `gate-mutations.yaml` records that C60's falsification
      "moves to the generating job", so the `is_proven_uplift` operator is probed by a
      `--gate C60` invocation inside `uplift.yml::uplift-proof` in a later pass. The sweep
      reports C60 as `indeterminate`, naming the non-passing baseline.
    - _Requirements: 1.1, 1.2, 1.13, 1.14_

  - [x] 5.7 Write property test for sweep outcome classification
    - `# Feature: decision-quality-proof, Property 38: Sweep outcome classification is total, four-valued and per-operator`
    - File: `tests/verify/test_sweep_outcome_totality_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 1.3, 1.4, 1.5_

  - [x] 5.8 Write property test for derived counts and PASS-eligibility
    - `# Feature: decision-quality-proof, Property 39: The falsified-check count and PASS-eligibility are derived, never asserted`
    - File: `tests/verify/test_sweep_count_derivation_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 1.6, 1.7, 1.8, 1.9, 1.10, 1.15_

  - [x] 5.9 Write property test for a sweep that could not observe
    - `# Feature: decision-quality-proof, Property 40: A sweep that could not observe is non-passing`
    - File: `tests/verify/test_sweep_unobservable_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 1.11, 1.16_

  - [x] 5.10 Write property test for the C72 row projection
    - `# Feature: decision-quality-proof, Property 41: The C72 row projects the counts of the run that produced it`
    - File: `tests/verify/test_c72_row_projection_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 1.12_

- [x] 6. Checkpoint — review the sweep's survivor list
  - discharge: truth-gates.yml::falsification-sweep
  - Ensure all tests pass, ask the user if questions arise.
  - **REVIEWED AND ACCEPTED BY THE OPERATOR, session 2q. This closes E1.** The list below was
    measured by the declared discharge job and the review it was waiting on has happened, so the
    mark is earned rather than asserted. The operator's disposition, recorded verbatim rather than
    paraphrased: *"the disclosed survivor is not a finding against the sweep; C28's real repair
    waits on `coverage_per_package.py --require-measured-floors`, which is not this spec's."*
    - **No mutation was weakened, and none may be.** The survivor stands recorded as a survivor.
      The repair belongs to C28's owner and lands when `--require-measured-floors` does; until
      then C28 is a gate proven not to enforce its own floor property, and that fact is now
      readable in this ledger rather than only in a CI log.
    - **What the acceptance rests on, stated so it can be checked:** `UNPROVEN=0` — the clause this
      task's success criterion actually names — and **no undisclosed survivor**. Those two together
      are what make the sweep's own numbers supportable. Had either failed, acceptance would have
      been unavailable regardless of the survivor count.
    - **What it does NOT license.** The sweep is not green and E1's completion criterion never
      asked it to be: "E1 is complete when the sweep's exit status gates a job and every
      non-`falsified` outcome is attributed to a check and an operator — **not** when the sweep is
      green." Both hold. `truth-gates.yml::falsification-sweep` stays red on PR #84 and that red is
      attributed, disclosed and expected.
    - **The 7-not-8 shortfall is the argument the operator acted on separately.** C56's red baseline
      removed C56 from the probeable set, so the drift cost measurement power and not just a tick.
      That is now parent task **26**'s subject: a `workflow_dispatch` CI job regenerates
      `CURRENT.md` and the README headline on a runner and uploads them, because CI runs the
      generators with `--check` and cannot repair what it detects (I-0 escalation step 1).
    - **Still recorded and still unrepaired:** `gate-mutations.yaml`'s survivor shape for C16 at
      line `26` is **misattributed** — nobody declared that mutation, and C16's declared operator
      sets `$.thresholds.break` to `10` and must fire. Ticking this task does not absorb that.
  - **THE LIST, as measured on PR #84, run `33513528766`, sha `77df3ef`.**
    ```
    Checks:    REGISTERED=67 DECLARED=14 FALSIFIED=6 PASS_ELIGIBLE=6 EXCLUDED=53
    Operators: DECLARED=16 PROBED=16 UNPROVEN=0
    ```
    - **Exactly one survivor, and it is the disclosed one.** `C28/zero-a-floor` — "gate exited 0
      under the declared mutation: it does not gate this property". **No undisclosed survivor**, so
      no number reported elsewhere in the repo is invalidated by this run.
    - **Six gates proven to bite:** C16 `lower-stryker-break`, C57 `neutralise-one-actuator`,
      C61 `shrink-the-allowlist-subject`, C65 `rename-a-declared-required-job`,
      C66 `unresolvable-registry-gate-module`, C68 `hollow-out-the-external-feed`.
    - **`UNPROVEN=0`** — every declared operator was probed. That is R1.16's obligation discharged,
      and it is the clause this task's own success criterion names.
    - **Eight indeterminate, every one for the declared reason** (the gate does not pass on its
      unmutated baseline, so its exit 1 under mutation attributes nothing): C44 x2, C56 x2, C60,
      C69, C70, C71, C72.
  - **The prediction below said 8 probeable. The actual is 7, and the missing one is C56 — because
    the README headline drift makes C56's own baseline red.** So session 1's unregenerated README did
    not merely fail a gate: it **removed a gate from the falsification measurement**. That is a
    stronger reason to run `readme_gen --write` than the red tick was, and it is recorded in
    `HANDOFF.md`'s owed list rather than acted on unilaterally.
  - **Expect red, and read the red correctly.** The honest expectation stated before the run:
    at most **8 of 14** declared checks are probeable on this tree (C16, C28, C56, C57, C61,
    C65, C66, C68 have `PASS` baselines; C44 and C69 are `FAIL`; C60, C70, C71, C72 are
    `SKIP`), because `falsifies()` reports `indeterminate` when the gate does not pass on the
    unmutated copy — a check that is already red proves nothing by staying red.
  - **C28's `zero-a-floor` is the disclosed survivor.** `gate-mutations.yaml` records it:
    C28 asserts floors `>= 0` and a `0.0` floor satisfies it until
    `coverage_per_package.py --require-measured-floors` lands. C28's baseline is `PASS`, so it
    **is** probed, and it is expected to report `survived`. That is a defect against C28, not
    against the sweep. Note also that `gate-mutations.yaml`'s recorded survivor shape for C16
    at `26` is **misattributed** — nobody declared that mutation; C16's declared operator sets
    `$.thresholds.break` to `10` and must fire.
  - **A survivor may invalidate a claim made elsewhere in the repo.** Present the survivor
    list to the user before deciding what to fix: a gate proven not to enforce means every
    number that gate reported is unsupported, and some of those numbers are quoted in
    `docs/state/CURRENT.md`, `README.md` and other specs' completed task records. Do not
    weaken a mutation to clear a survivor.
  - E1 is complete when the sweep's exit status gates a job and every non-`falsified` outcome
    is attributed to a check and an operator — **not** when the sweep is green.

### Phase 2 — E4a and E2a (parallel), then E2b, then E2c

- [x] 7. E4a — feed admission: licence, registered check, ingestion record, statistics
  - Implements **CF-7**'s split: R8's first four criteria become E4a and precede E2c, because
    R5.11 requires the demand-intensity shape to be calibrated from Real_Data_Feed statistics
    rather than invented literals. R8.5-R8.15 and R8.18 keep their stated position in E4
    (second pass). Nothing is deferred; R8 is recognised as two independently sequenced
    obligations.
  - `git grep -i "m5\|walmart"` across `*.md`, `*.py`, `*.yaml` returns no dataset reference
    anywhere in the tree: M5 is a **new** dependency and its licence terms are confirmed before
    ingestion, not after.
  - **Path note, stated rather than assumed:** the exact artifact paths below are derived from
    the neighbouring declaration files' naming convention, not read from R8's text (R8 is
    outside this pass's bounded reading). Confirm each against R8.1/R8.2/R8.16/R8.17 at
    implementation time and correct without ceremony if they differ.

  - [x] 7.1 Commit the feed licence artifact
    - File: `infrastructure/data/dataset-licences.yaml` (new) + its schema under
      `infrastructure/data/schemas/`
    - **Conflict B, resolved forward rather than moved later.** This task originally named
      `infrastructure/quality/feed-licence.yaml`, derived from neighbouring convention with an
      explicit note to "correct without ceremony if they differ". They differ: design **E4a.1**
      names `infrastructure/data/dataset-licences.yaml`, and R8.1's six fields (`dataset_id`,
      `licence_id`, `licence_text_uri`, `read_date`, `permitted_use`, `dataset_revision`) were
      confirmed by reading the criterion. Landing at the design's path here makes **task 19.1 a
      verification instead of a migration**. The companion modules land at the design's names
      too: `data_fabric/licence.py::DatasetLicence`, `data_fabric/ingest/m5.py::M5IngestRecord`,
      `scripts/audit/dataset_licence_truth.py`.
    - **The licence terms cannot be confirmed from inside this repo.** They live behind Kaggle
      competition rules requiring acceptance — an operator step. The artifact lands with fields
      **explicitly marked unconfirmed**, and the registered check reports `unavailable` -> SKIP
      until an operator confirms. That is what R8.2 and I-7 prescribe. **Do not invent a
      `licence_id`.**
    - Records the licence terms, the source URL, the retrieved-at timestamp, and the
      redistribution disposition. Every field is explicit; an absent field is **named** rather
      than defaulted, so a missing term cannot read as a permissive one.
    - _Requirements: 8.1, 8.2_

  - [x] 7.2 Register the licence check
    - Files: `scripts/audit/dataset_licence_truth.py` (new),
      `scripts/audit/verify_claims.py` (`@register`)
    - **Path corrected.** This sub-task declared `scripts/audit/feed_licence_truth.py`; the
      module landed as `dataset_licence_truth.py` to match Conflict B's artifact name, and is
      registered as **C74**. The stale name is recorded here rather than quietly swapped,
      because the census reads declared paths and a wrong one reads as an absent artifact.
    - Schema-total over the artifact; any absent or unparseable field yields `unavailable` ->
      SKIP, never PASS (`verify_claims.py::GATE_STATUS`, `"unavailable": "SKIP"`).
    - Locus: `truth-gates.yml::truth-gates`.
    - _Requirements: 8.1, 8.2_

  - [x] 7.3 Add the ingestion record and the first-ingestion reporting rule
    - Files: `data_fabric/ingest/m5.py` (new — **design E4a.3's path and single-module
      shape**, not `tasks.md`'s `data_fabric/etl/m5_ingest.py` + `m5_statistics.py` split;
      the statistics are a product of an ingestion and carry the same identity fields, so
      splitting them would put the dataset revision in two files kept in step by hand)
    - **Conflict recorded, not resolved silently:** `tasks.md` also asked for an
      "ingestion-record block" *inside* the licence declaration. Not implemented, and
      deliberately: the declaration is a committed statement of terms, and writing runtime
      ingestion facts back into it would make the artifact that ingestion is checked against
      mutable by ingestion. The binding runs the other way — the record pins the artifact's
      `sha256:` digest.
    - `record_ingestion` **refuses** rather than annotates in three cases (I-6, a hard
      guardrail over a learned policy): the register declares no entry for the dataset; the
      entry is not confirmed (naming every unestablished field, so the message is a work list);
      or the entry's `dataset_revision` disagrees with the revision being ingested.
    - Records what was consumed: row count, file digests, the licence artifact digest in force
      at ingestion time. A first ingestion is reported as such rather than silently folded into
      a steady-state path.
    - **The straddle R8 names, carried here so it is not discovered late:** the Real_Data_Feed
      is a **training-row** source, while the tree's only provenance-bearing external seam
      (`ExternalFeedSource`) reads **Kafka topics** into `WorldState`. These are two unrelated
      ingestion paths and only the world seam carries a provenance field today. This task
      touches the training-row path; do not conflate them.
    - _Requirements: 8.16, 8.17_

  - [x] 7.4 Extract the M5 aggregate statistics structure 1 will calibrate against
    - File: `data_fabric/ingest/m5.py` (merged per design E4a.3 — see 7.3)
    - **FINDING, and it constrains task 12.1: the intra-day intensity shape is NOT derivable
      from M5.** M5's observation columns are **daily** totals per series, and an hour-of-day
      shape cannot be recovered from daily aggregates by any amount of arithmetic. R5.11 asks
      for a shape "calibrated from statistics derived from the Real_Data_Feed rather than from
      invented literals", so emitting a plausible intra-day curve — a lunch peak and an
      evening peak — would be exactly the invention R5.11 forbids while *appearing* to satisfy
      it. `extract_statistics` therefore reports that shape `unavailable` naming the
      granularity gap, and `ShapeEstimate` structurally forbids an `unavailable` shape from
      carrying values so no downstream reader can pick numbers out of it.
    - **Task 12.1 must not assume this input exists.** Whatever calibrates the intra-day shape
      has to come from elsewhere, and that decision belongs to 12.1 with this evidence in hand.
      This is also the sharpest single piece of evidence for R8.12's documented domain gap
      between daily grocery demand and 10-minute quick-commerce demand.
    - Derivable and derived: the **day-of-week** shape, and the **promotion-uplift** shape
      (through a declared price proxy, labelled as one).
    - Runs in `ci.yml::training-smoke`, never locally: a bulk streaming read over ~42,000
      hierarchical daily series is a category-3/4 workload under I-0. Written import-safe and
      fixture-testable — nothing runs at import, every path is a parameter, every reader
      streams (no pandas, no full-file materialisation).
    - Every failure names its subject and yields `unavailable`: a missing column, a
      non-numeric observation cell, a short row, a degenerate normaliser. **None returns a
      shape with zeros in it** — a zero-filled shape is a measurement claim, and defaulting an
      unreadable cell to zero would silently flatten the very shape being measured (I-7).
    - Derives the intra-day intensity shape, the day-of-week shape and the promotion uplift
      shape as **aggregate statistics**, written to the R5.12 policy file by task 12.1. The
      extraction runs in CI (`ci.yml::training-smoke`), not on the dev box: it is a bulk file
      read over roughly 42,000 hierarchical daily series.
    - This is the artefact that makes R5.11's "calibrated rather than invented" checkable.
    - _Requirements: 8.16, 8.17_

  - [x] 7.5 Write unit tests for licence schema totality and the ingestion record
    - File: `tests/verify/test_feed_licence_admission.py` (new)
    - Cover: every absent field named; an unparseable artifact yields `unavailable`; the
      ingestion record's digest binding.
    - Locus: `ci.yml::uplift-verify` fast step.
    - **No property sub-task here by design.** E4a's properties are **68** (licence schema
      totality) and **69** (provenanced ingestion, slow) — both numbered inside E4's block and
      appended by the second pass. This pass lands 38-59 only, so E4a carries unit tests now
      and its properties later. Recording that as a deliberate gap rather than an omission.
    - _Requirements: 8.1, 8.2, 8.16, 8.17_

- [x] 8. E2a — record the decision and commit the thresholds before touching the engine
  - **ADR-055 is committed before any change to `digital_twin/simulation/engine.py` made under
    R5** (R5.7). This is not ceremony: R5.5 and R5.6 require the record to state the
    inventory-theory argument, the five structures, the agent decision each structure unlocks,
    and the falsifiable claim that a base-stock `(s, S)` policy becomes measurably sub-optimal
    — so the phase is falsifiable rather than aesthetic. ADR-054 is the highest committed ADR,
    so 055 is the next free identifier.

  - [x] 8.1 Author and commit ADR-055
    - File: `docs/adr/ADR-055-twin-decision-relevance.md` (new)
    - States: the inventory-theory argument (stationary Poisson demand + independent identical
      items + i.i.d. lead times uncorrelated with demand + no capacity coupling => base-stock
      `(s, S)` is provably near-optimal, and `Par_Level_Reorder` **is** that policy); the five
      structures and the agent decision each unlocks; the falsifiable post-phase claim (R5.6).
    - Declares the **scalar regret objective** (R5.33): its KPI terms, each term's sign, the
      aggregation over replicates, and the weights — committed at declaration time, before the
      R5.1 run. `uplift/metric_contract.yaml` declares per-KPI hypothesis tests and
      `MetricContract.classify` returns a three-valued `Outcome`, **not a cost**, so regret has
      no units, no sign convention and no aggregation rule until this lands.
    - Records, **per KPI named in the objective**, whether that KPI is observably sensitive to
      the inventory policy on the unmodified twin (R5.34). Today the honest answer for all six
      is *no* — that is the finding E2a exists to fix, and recording it is what makes R5.35
      enforceable.
    - Records `spoilage_rate`'s change of meaning under R5.25/R5.26 rather than absorbing it:
      `orders_spoiled` increments **per SKU per tick**, so the ratio is a tick count and not a
      spoiled-units fraction.
    - Also names the reference policy set R5.28's Pareto comparison is taken against — without
      it R5.28 is unsatisfiable, since the Pareto frontier of a finite non-empty set is
      non-empty by construction.
    - _Requirements: 5.5, 5.6, 5.7, 5.33, 5.34_

  - [x] 8.2 Create the twin policy file, pin it, and add its ratchet entry
    - **Landed:** `digital_twin/simulation/policy.yaml` (new, design E2c.2's path — Conflict A
      above), four pins in `doc-number-pins.yaml`, two ratchet entries in `ratchets.json`.
    - **Four pins, verified by execution not assumption:** `regret-weight-shortage` (8.0),
      `regret-weight-holding` (1.0), `negative-control-seed-sets` (20),
      `negative-control-rate-tolerance` (0.20). C75 reports 13/13 pins resolving on both
      sides, and `resolve_pin` confirms all four *agree* (`8.0 == 8.0`, `1.0 == 1.0`,
      `20 == 20`, `0.20 == 0.20`). Only values ADR-055 **actually states** were pinned — a pin
      whose document side can never resolve is the dead-extractor shape C75 exists to catch.
    - **Only TWO ratchet entries, and the omission is a decision.** A ratchet asserts a
      monotonic better-direction. `negative-control-seed-sets` has one (`up` — more seed sets
      is strictly more power, so 20 is a floor) and `negative-control-rate-tolerance` has one
      (`down` — a false-positive ceiling may only tighten). The two regret **weights do not**:
      8.0 is not "safer" than 9.0, it is the newsvendor critical ratio the repo already
      commits. Inventing a `direction` for them would be the fabrication `ratchets.json`'s own
      header forbids ("Nothing here was invented"). Recorded in a
      `$note_on_absent_siblings` key so the absence reads as a decision, not an oversight;
      they are guarded by their pins and by C75.
    - Both new ratchets read as `status: unmeasured` / `outcome: skip` — correct, because they
      are **pre-registered design parameters, not observations**. Only a run that measured
      something may write `measured_at` (I-7, CF-3).
    - _Requirements: 5.2, 5.12, 5.36_
    - Files: `digital_twin/simulation/policy.yaml` (new),
      `infrastructure/quality/doc-number-pins.yaml`,
      `infrastructure/quality/ratchets.json`
    - **Conflict A, surfaced then decided — do not re-litigate.** This task originally named
      `infrastructure/quality/twin-decision-relevance.yaml`; design **E2c.2** names
      `digital_twin/simulation/policy.yaml`. **No task in this plan reconciled it** (19.1 covers
      only the licence artifact), and six requirements read from this file (R5.12, R5.18, R5.19,
      R5.27, R5.28, R5.36), so a silent pick would have stranded them. Decision: the design's
      path. `design.md` is the architecture authority and `tasks.md` derives from it, and the
      design's own reasoning — "the single committed policy file ... so no literal lands in
      `engine.py`" — argues for co-location with the engine that reads it. The pin table can
      point anywhere, so nothing is lost by leaving `infrastructure/quality/` for gate
      declarations.
    - Every threshold this phase introduces goes into the policy file, read rather than
      inlined, and pinned by AD-3's pin table (AD-13). The values this pass adds: the
      comparator restock threshold (R5.36) now; the `(s, S)` materiality margin (R5.2) after
      task 10.4 measures it; the utilisation ladder and near-saturation band (R5.18, R5.19),
      the substitution fraction (R5.27) and the objective weights (R5.33) as E2c lands them.
    - Each threshold gets a `ratchets.json` entry. **Several are deliberately committed after a
      first measuring run writes a report** — R5.2 says so in its own text, and R5.19 inherits
      the pattern. Committed-after-measurement is not committed-late; what is forbidden is
      judging a run against a threshold committed after that run.
    - _Requirements: 5.2, 5.12, 5.36_

  - [x] 8.3 Make pin extractors resolve, and verify each by running it
    - Files: `scripts/audit/doc_truth.py`,
      `scripts/audit/pin_extractor_truth.py` (new),
      `scripts/audit/verify_claims.py` (**registered as C75**),
      `infrastructure/quality/doc-number-pins.yaml` (retired a resolved drift entry)
    - **Narrower than the task assumed, and the narrowing is recorded.** `compare: string`
      and `compare: numeric` already raised on an empty extraction (`_single_source_value`
      refuses a non-singleton set), so those two were never vulnerable. The live hole was
      `compare: count` with a documented **zero**: an empty extraction produced `len == 0`,
      matched the claim, and returned `ok` — comparing nothing to nothing. That one case now
      raises, because it cannot distinguish "the source genuinely declares none" from "the
      extractor no longer resolves". Everywhere else an empty extraction remains the honest
      count `0` that FAILs a non-zero claim; that documented contract is unchanged.
    - **The real gap was reachability, not comparison.** `doc_truth` only reaches a source
      extractor once the DOCUMENT anchor has resolved, so a dead `yaml_path:` sitting behind a
      reworded sentence is never exercised at all. `pin_extractor_truth` probes both sides
      **independently and unconditionally** — that is Property 48's load-bearing clause.
    - **DISCOVERED, pre-existing, and fixed:** the `drift:` block recorded `stryker-break` as
      live drift (`document_value: 26` vs `source_value: 50`) while its own recorded
      remediation was already complete — the pin resolves `ok` and `ratchet_truth` reports
      `guard_value: 50.0, agrees_with_shipped: true`. Two tests
      (`test_every_recorded_drift_entry_is_still_mechanically_real`,
      `test_the_recorded_stryker_drift_matches_the_shipped_configuration`) were **already
      failing** before this task. Retired the entry to a note per the block's own documented
      convention that `drift:` records only live drift (`cov-fail-under` precedent). A record
      claiming a hole that has been closed is the stale-claim class this spec exists to
      eliminate; the repair is the subject, never the test (R2.10).
    - _Requirements: 5.2, 5.11, 5.12_
    - **AD-13's one-word addition: extractors are verified by running them.** A pin is a triple
      (document anchor, mechanical source, extractor). The predecessor's Property 5 asserts the
      extracted values agree and that extraction is idempotent — it does **not** assert the
      extractor *resolves*. A `yaml_path:` naming a missing key, or a `json_path:` into a
      restructured file, yields `None` on both sides, and `None == None`: two absent values
      agree and a pin that compares nothing reports green.
    - Three obligations: `doc_truth`'s pin evaluation reports `unavailable` (never `ok`) when
      **either** side's extractor resolves to nothing, naming which side and which extractor; a
      registered check **runs every declared extractor against its declared source at gate
      time** and fails on any that resolves to nothing; a pin whose document side sits inside a
      generated region is `kind: generated` and skipped, because comparing a generated
      projection against its own source compares a mechanism to itself (the defect AD-21
      rejects).
    - Not marked optional: this is where the "every new threshold gets a `ratchets.json` entry
      whose extractor is verified by running it" obligation actually lands. Skipping it means
      every threshold this phase commits is pinned by a comparison that may compare nothing.
    - _Requirements: 5.2, 5.11, 5.12_

  - [x] 8.4 Write property test for pin extractor resolution
    - `# Feature: decision-quality-proof, Property 48: Every declared pin's extractor resolves on both sides`
    - File: `tests/verify/test_pin_extractor_resolution_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 5.2, 5.11, 5.12_

- [x] 9. E2a — instrument the twin so a KPI can see an inventory decision at all
  - Implements **AD-17** (a stockout costs something; the KPI change is separated from the
    physics change) and **AD-18** (foresight is a recorded trace; the comparator disables the
    twin's own `(s, S)`; named RNG substreams).
  - **The separation that makes E2b honest, and how it is checked.** These changes alter what
    the world *records*, not what it *does*: no timeout changes, no draw is added or removed on
    the delivered path, and the RNG consumption order on that path is unchanged because the SKU
    draw already happens at that point in `_delivery`. So "the unmodified twin" in R5.1 means
    "the twin with E2a's instrumentation and none of E2c's structures", and that claim is made
    **mechanically checkable** by Property 49's second clause rather than asserted.
  - Sub-tasks 9.1-9.5 all edit `digital_twin/simulation/engine.py` and are deliberately
    sequenced one per wave rather than batched — they are separable by design (AD-17 calls them
    "deliberately minimal and deliberately separable") and a single combined commit would make
    the substream churn indistinguishable from the metric change.

  - [x] 9.1 Make `_delivery` stock-conditional and add `unmet_demand_events`
    - **MEASURED, not asserted:** `fill_rate` falls **0.8556 -> 0.3592** (`stockout_rate`
      0.1444 -> 0.6408) at seed 42 over 24h with the endogenous restock disabled. Before this
      it could not fall at all. `avg_on_hand_units` responds too (1016.0 -> 202.1).
    - `demand_events` is a SEPARATE counter from `orders_created`: an order created near the
      end of a run may never reach fulfilment, and dividing unmet demand by arrivals would
      understate the rate by counting orders that were never tried.
    - Both time totals now accumulate **only on a fulfilled delivery**. Accumulating an
      unfilled order's pick/pack effort into the numerator while excluding it from the
      denominator would inflate `avg_delivery_time_min` exactly when service degraded.
    - File: `digital_twin/simulation/engine.py`
    - Draw the SKU **first**; if its level is zero, increment a new
      `SimulationMetrics.unmet_demand_events` and return **without** touching
      `orders_delivered` or `total_delivery_time_min`. Today both increment unconditionally
      before `self._inventory[sku] = max(0.0, ... - 1.0)`, so a stockout costs nothing
      measurable and all six KPI fields are blind to stock availability.
    - This resolves the documented-versus-implemented contradiction in favour of
      `uplift/kpi.py`'s docstring and in favour of `digital_twin/world/runtime.py:18-21`'s
      claim that with auto-restock disabled "stock genuinely runs out and `fill_rate` falls" —
      which is false today.
    - The refused alternative, named so it is not revisited: leaving `_delivery` unconditional
      and deriving stockouts harness-side is the **current** state, and the current state is a
      KPI vector that cannot see its subject.
    - _Requirements: 5.38_

  - [x] 9.2 Make demand events name the SKU they demand
    - File: `digital_twin/simulation/engine.py`
    - `_delivery` currently picks the depleting SKU by
      `self._rng.choice(list(self._inventory.keys()))` **after** delivery, so demand never
      names a SKU and there is no per-SKU demand path to forecast or price. Move the naming to
      demand generation.
    - _Requirements: 5.39_

  - [x] 9.3 Add the time-weighted on-hand inventory measure
    - Integrated **lazily** at every mutation and every advance boundary rather than by a
      sampling process, deliberately: a new SimPy process would add events to the queue and
      could reorder same-timestamp callbacks -- the incidental perturbation 9.4 exists to
      eliminate. Accrued BEFORE each mutation, so the level integrated is the level that
      actually held over the interval.
    - File: `digital_twin/simulation/engine.py`
    - `SimulationMetrics.inventory_minutes: float` accumulates `sum(levels) * dt` on each
      `advance` boundary and each mutation, exposed as
      `avg_on_hand_units = inventory_minutes / max(1.0, sim_time_min)`. Pure accounting.
    - This is the holding term in R5.33's objective and the KPI R5.28's third
      single-objective policy minimises; `SimulationMetrics` carries six counters and no
      inventory-time term today, so the classic `(s, S)` cost objective is not derivable
      without it.
    - _Requirements: 5.40_

  - [x] 9.4 Replace the single RNG with named substreams
    - Six streams via `SeedSequence(seed).spawn(6)`; `SUBSTREAM_NAMES` order is fixed and
      documented as un-reorderable, because `spawn` derives each child from the parent entropy
      plus its INDEX -- inserting a name mid-list silently re-seeds every stream after it.
    - **Evidence of independence:** `demand_events` is identical (2784, and 799 in the 8h
      cold-start check) across policies that produce wildly different fulfilment, and the
      recorded trace length is identical (2855). The demand path is provably unaffected by
      what any arm does.
    - File: `digital_twin/simulation/engine.py`
    - `np.random.SeedSequence(seed).spawn(n)`, one substream per process: `demand`,
      `pick_pack`, `travel`, `restock`, `spoilage`, `sku_choice`. The engine has exactly one
      `self._rng = np.random.default_rng(seed)` today, consumed by `_order_arrival`,
      `_pick_pack_dispatch`, `_delivery` (three draws), `_restock` and the SKU `choice`, so the
      realised demand path is a function of the **global draw order across all five
      processes**.
    - This is the change that makes E2c *possible*: without it, adding a queue in structure 2
      perturbs the demand stream and every seeded expectation in the PRESERVE list breaks for
      a reason unrelated to the structure being added. With it,
      `tests/uplift/test_seeded_demand_identity_property.py::test_arms_receive_identical_seeded_demand`
      becomes **stronger** — the demand substream is provably independent of any arm's actions.
    - **Stated cost:** substreams change every realised number on the seeded path. This is the
      single largest expected-value churn in the design.
    - _Requirements: 5.30, 5.37_

  - [x] 9.5 Record the demand path as a replayable trace
    - `DemandTrace` / `DemandEvent` in `engine.py`, recorded AT GENERATION TIME (before any
      fulfilment outcome is known) so an event that is generated but never fulfilled is still
      demand. A trace built from fulfilments would silently omit exactly the stockouts the
      experiment is about. Injected orders record on the same terms as endogenous arrivals.
    - Files: `digital_twin/simulation/engine.py`, `digital_twin/world/runtime.py`
    - `DemandTrace` accumulates `(t_min, sku, units)` events **as they are generated** and is
      emitted per scenario. A perfect-foresight policy is constructed *from a completed trace*,
      not by re-deriving the generator.
    - Do **not** use `start(external_demand=True)` + `inject_orders(n)` as the foresight seam:
      it takes a bare count and **replaces** the demand process, so a run using it is not the
      unmodified twin.
    - _Requirements: 5.37_

  - [x] 9.6 Move the stockout numerator into the twin and disable the comparator's endogenous restock
    - Files: `uplift/harness.py`, **`digital_twin/simulation/policy.py` (new reader)**
    - Deleted the per-step `sum(1 for level in sim.inventory.values() if level <= 0.0)`; the
      twin now counts unmet demand per demand event. `stockout_count` in the per-step
      `Observation` reads `metrics.unmet_demand_events` so the observation is arm-symmetric.
    - `_build_twin` calls `sim.set_policy(restock_threshold=comparator_restock_threshold())`,
      **read** from the policy file (AD-13). Verified `0.0`, which disables the endogenous
      `(s, S)` rather than lowering it. The reader **refuses to default a missing key** and
      raises `PolicyUnavailableError` naming it -- a default would substitute an unreviewed
      number for a committed one.
    - **BUG EXPOSED AND FIXED, and it is the reason this task matters.**
      `_apply_cold_start` used `sim._inventory.clear()`, deleting the catalogue. Once a
      stockout costs something, that became wrong: with no SKUs to draw, NO demand event is
      recorded, so `demand_events == 0` and **both** `fill_rate` and `stockout_rate` report
      `0.0` for a city where every single order fails. Now the levels are zeroed and the keys
      kept, and cold start correctly measures **`stockout_rate = 1.0000`, `fill_rate =
      0.0000`** over 799 demand events. An empty *catalogue* remains distinct from empty
      *stock* -- nothing is demanded of a catalogue that does not exist (`WorldRuntime`'s
      non-seeded path). This defect was invisible before 9.1 because a stockout cost nothing
      either way.
    - _Requirements: 5.36, 5.38_
    - Files: `uplift/harness.py`, `uplift/kpi.py`
    - Delete `uplift/harness.py`'s per-step
      `sum(1 for level in sim.inventory.values() if level <= 0.0)` — a per-step count of SKUs
      at zero whose numerator scales with `n_steps * |SKU|` before `_clamp_fraction` saturates
      it — and populate `AppliedDecisions.unmet_demand_events` from
      `SimulationMetrics.unmet_demand_events`. `stockout_rate` then measures unmet demand
      events over demand events, which is what `uplift/kpi.py:85-86` already documents.
    - In `_build_twin`, one line after `sim.start()`:
      `sim.set_policy(restock_threshold=_comparator_restock_threshold())`, read from the task
      8.2 policy file, and write the resolved value into `UpliftProvenance`. `start()` leaves
      `_restock_threshold` at its constructor default `50.0`, so through the harness a compared
      `(s, S)` policy is measured **stacked on top of the twin's own `(s, S)`**, biasing regret
      toward zero independently of whether the world is easy. `set_policy` clamps with
      `max(0.0, ...)`, so `0.0` is reachable and `if level < safety_stock` is then false for
      every clamped level. **A run whose recorded threshold differs from the committed one is
      inadmissible.**
    - _Requirements: 5.36, 5.38_

  - [x] 9.7 Update every committed expectation these changes move, stating each new expectation
    - **Outcome: almost nothing moved, and that is itself the finding.** All **33**
      `digital_twin/tests` pass unchanged, as do the three PRESERVE-list tests
      (`test_seed_reproducibility_property`, `test_seeded_demand_identity_property`,
      `test_nonsynthetic_ingestion_replay_property`). The named casualties
      (`test_run_produces_valid_metrics`, `test_perceive_after_start_is_full_stock`,
      `test_demand_depletes_inventory_and_auto_restock_is_disabled`, `test_longer_run_more_orders`,
      `TestMonteCarlo::test_shock_params_affect_output`) all survive because their assertions are
      genuinely comparative or structural — the ledger said to "read them before assuming", and
      reading them was correct.
    - **The one expectation that DID move was not in the predicted list:** `_apply_cold_start`.
      See 9.6 — it deleted the catalogue, which silently zeroed both `fill_rate` and
      `stockout_rate` for a scenario in which every order fails. Repaired, with its new expected
      values stated: `stockout_rate = 1.0000`, `fill_rate = 0.0000` over 799 demand events.
    - **`digital_twin/tests/test_env_response.py` CANNOT be verified on this machine**, and the
      reason is not I-0: it carries `pytest.importorskip("gymnasium")` at module level (line 17)
      and gymnasium is not installed here, so it collects **0 items / 1 skipped**. It runs in CI
      where the ML stack is present. `test_good_action_beats_bad_over_seeds` asserts
      `mean(fast) > mean(slow)`, which is comparative and should survive — but there is a **real
      new interaction to watch**: faster dispatch now consumes stock sooner, which can raise
      stockouts, so the reward ordering is no longer guaranteed by dispatch latency alone.
      **Authored unchanged, not executed.**
    - `test_run_deterministic_with_seed` passes, as predicted: substreams preserve
      same-seed reproducibility.
    - _Requirements: 5.30, 5.31_
    - Files: `digital_twin/tests/test_simulation.py`, `digital_twin/tests/test_env_response.py`,
      `digital_twin/tests/test_world_runtime.py`
    - `fill_rate` falls on the unmodified twin the moment 9.1 lands, so every expectation
      reading `orders_delivered` or `fill_rate` moves. Named casualties:
      `test_world_runtime.py::test_demand_depletes_inventory_and_auto_restock_is_disabled`
      (this **repairs** its intent), `test_env_response.py::test_good_action_beats_bad_over_seeds`,
      `test_simulation.py::TestSimPyEngine::test_run_produces_valid_metrics`, and
      `test_world_runtime.py::test_perceive_after_start_is_full_stock` (depends on the
      `{f"sku_{i}": 100.0 for i in range(10)}` literal).
    - `test_run_deterministic_with_seed` should still pass — it asserts two runs at one seed
      agree, which substreams preserve. `test_longer_run_more_orders` and
      `TestMonteCarlo::test_shock_params_affect_output` survive only if their assertions are
      genuinely comparative, which static reading suggests but **did not confirm** (the
      assertion bodies were not read). Read them before assuming.
    - Also keep green: `tests/uplift/test_seed_reproducibility_property.py`,
      `tests/uplift/test_seeded_demand_identity_property.py`,
      `tests/verify/test_nonsynthetic_ingestion_replay_property.py`.
    - Each updated expectation states its **new** value and why it moved. Do not weaken an
      assertion to absorb a change (R5.31).
    - _Requirements: 5.30, 5.31_

  - [x] 9.8 Write property test for the stockout cost and the instrumentation-only claim
    - **8 tests, all passing.** `@pytest.mark.slow`, locus `ci.yml::uplift-verify` slow step.
    - **Clause 2 is stated in an equivalent invariant form, and the substitution is recorded.**
      The task text frames it as "equals the sequence produced by the pre-change engine". That
      comparison is not constructible — the pre-change engine no longer exists, and
      reconstructing it in a test would mean maintaining a second copy of the physics whose
      fidelity nobody checks, a worse foundation than the claim it supports. Instead: *the demand
      path is invariant to fulfilment* — for one seed under two policies with divergent outcomes,
      `orders_created` is identical, the `DemandTrace` is identical event-for-event, and
      `demand_events == orders_delivered + unmet_demand_events` **exactly** (the accounting form
      of "differs only on zero-stock events"). Non-vacuity is asserted separately.
    - **A first draft of this file failed, and the failure was informative.** It asserted
      strictly lower fill rate at an 8h horizon; falsifying example `seed=62, hours=8.0` showed
      only 889 demand events against 1000 opening units, so nothing ran out and both arms tied at
      1.0. The precondition was wrong, not the subject: split into a universal *never improves*
      claim and a strict claim at a horizon that provably exhausts the shelf (R2.10 — fix the
      assertion, not the subject).
    - `# Feature: decision-quality-proof, Property 49: A stockout costs something, and the instrumentation changed only what is recorded`
    - File: `digital_twin/tests/test_stockout_instrumentation_property.py`
    - **Second clause is the load-bearing check of AD-17:** for any seed, the sequence of
      `(sim_time_min, inventory, orders_created)` triples produced by the instrumented engine
      equals the sequence produced by the pre-change engine on the same seed, with
      `orders_delivered` differing **only** on events whose drawn SKU was at zero.
    - `@pytest.mark.slow`. Selected by **`ci.yml::uplift-verify`'s slow step**, whose path list
      already collects `digital_twin/tests` and whose selector is `-m "slow"` at
      `HYPOTHESIS_PROFILE=heavy`. A slow-marked test placed outside those four paths is
      selected by no job at all.
    - Budget inherited from the profile; no `max_examples` literal.
    - _Requirements: 5.38, 5.39_

  - [x] 9.9 Write property test for the on-hand integral
    - **6 tests, all passing in 4.6s.** Correctly **NOT** slow-marked; locus
      `ci.yml::quality-gates`, verified as the job that collects `digital_twin` without the marker.
    - Cheapness is by construction, not luck: every case uses `start(external_demand=True)` with
      **no injected orders**, so the demand process is off and inventory is constant. The integral
      then has a closed form (`sum(levels) * elapsed`), which makes the assertions **exact
      equalities** rather than tolerances. A slow-marked test placed here would be excluded by
      `quality-gates`' own `-m "not slow"` filter, so the marker decision is not cosmetic.
    - Includes the accrue-before-mutate clause: stock added midway accrues only over the
      remaining horizon. Accruing after the mutation would attribute the new higher level to the
      interval the old level actually held, overstating holding cost.
    - `# Feature: decision-quality-proof, Property 50: The time-weighted on-hand measure is a correct integral`
    - File: `digital_twin/tests/test_on_hand_integral_property.py`
    - **Not** slow-marked. Locus: `ci.yml::quality-gates` (`-m "not slow"` over
      `packages/tests agents orchestrator digital_twin api`, `default` budget) — verified as
      the job that collects `digital_twin` without the marker.
    - Budget inherited from the profile.
    - _Requirements: 5.40_

  - [x] 9.10 Write property test for demand-path replay
    - 6 tests passing. `@pytest.mark.slow`, `ci.yml::uplift-verify` slow step. Covers same-seed
      replay, generation-order and horizon bounds, one-event-per-created-order accounting, the
      per-SKU decomposition `demand_prophet` will forecast, trace reset on `start()`, and that an
      injected order records on the same terms as an endogenous arrival.
    - `# Feature: decision-quality-proof, Property 51: The demand path replays exactly`
    - File: `digital_twin/tests/test_demand_trace_replay_property.py`
    - `@pytest.mark.slow`; selected by `ci.yml::uplift-verify`'s slow step
      (`-m "slow"`, `HYPOTHESIS_PROFILE=heavy`, `digital_twin/tests` already collected).
    - Budget inherited from the profile.
    - _Requirements: 5.37_

  - [x] 9.11 Write property test for substream independence
    - 7 tests passing. `@pytest.mark.slow`. **`SUBSTREAM_NAMES`' order is asserted, not merely
      documented** — `SeedSequence.spawn` derives children by INDEX, so inserting a name
      mid-list silently re-seeds every stream after it, changing every realised number on the
      seeded path without touching a line of physics. A comment cannot fail; this does.
    - The behavioural clause is the one the comparator depends on: two runs at one seed under
      policies that consume `pick_pack`/`travel`/`restock` differently generate **identical
      demand**. Under a single shared generator that is false by construction.
    - `# Feature: decision-quality-proof, Property 52: Named RNG substreams are independent`
    - File: `digital_twin/tests/test_rng_substream_independence_property.py`
    - This is what makes the two-pass comparator protocol sound: pass two's demand must be
      identical to pass one's despite a different policy consuming different draws elsewhere.
    - `@pytest.mark.slow`; selected by `ci.yml::uplift-verify`'s slow step.
    - Budget inherited from the profile.
    - _Requirements: 5.30, 5.37_

  - [x] 9.12 Write property test for the comparator's recorded restock configuration
    - 6 tests passing. `@pytest.mark.slow` (`tests/uplift` is in that step's path list).
    - Asserts on **behaviour, not the private attribute**: `restocks_triggered == 0` over a 24h
      comparator run, plus a positive control that the twin genuinely runs out
      (`orders_delivered <= 1000`). A threshold that is set but not honoured would satisfy an
      attribute check and still bias the measurement.
    - Also pins the cold-start repair (`stockout_rate == 1.0`), that the value is **read** from
      the committed file, that a missing key is **refused rather than defaulted**, and that every
      `deferred:` entry is prose naming its owning task rather than a placeholder number — a
      placeholder would be judged against, which R5.2 forbids.
    - `# Feature: decision-quality-proof, Property 53: The comparator runs with the twin's own restock disabled and recorded`
    - File: `tests/uplift/test_comparator_restock_disabled_property.py`
    - `@pytest.mark.slow`; selected by `ci.yml::uplift-verify`'s slow step
      (`tests/uplift` is in that step's path list).
    - Budget inherited from the profile.
    - _Requirements: 5.36_

- [ ] 10. E2b — measure `(s, S)` regret on the unmodified twin, and try to kill Finding 4
  - **This task is sequenced here deliberately, to attempt to falsify this spec's central
    claim before the project builds on it.** Finding 4 is *analytical, not measured*: it rests
    on reading `engine.py` plus inventory theory, and it is recorded as *plausible but
    unverified*. R5.1-R5.4 are the criteria that falsify it. If the measured regret is at or
    above the R5.2 margin, Finding 4 is **falsified**, R5's remaining scope shrinks
    substantially, and this spec is **re-cut rather than executed as written** (R5.3, R5.4).
  - "Unmodified" means "with E2a's instrumentation and none of E2c's structures" — E2a changed
    what the world records, not what it does, and Property 49's second clause is what makes
    that claim checkable rather than asserted.

  - [x] 10.1 Implement the scalar regret objective declared in ADR-055
    - `uplift/regret.py`. Five cost terms, every weight/normaliser/aggregation rule **read**
      from `policy.yaml`; `MetricContract.classify` untouched. **Verified ranking:** starved
      cost 11.55 > replenished 4.43 on the task-9 measurement pair.
    - The loader **refuses** a missing weight, a non-positive normaliser, an unrecognised
      aggregation rule, an unpaired replicate comparison, and — per ADR-055 D3 — a
      `sensitive: true` with no `demonstrated_by` citation. A bare `true` is an assertion.
    - **Found a gap in my own policy file:** the loader rejected the objective because
      `unmet_service` (the `1 - fill_rate` term) had no sensitivity record. Added explicitly
      rather than inferred from `fill_rate`, since an unrecorded term must never be treated as
      sensitive (I-7).

  - [x] 10.5 Make an insensitive instrument outrank a null
    - Implemented as `RegretVerdict` / `classify_regret` inside `uplift/regret.py`, four-valued:
      `material` | `sub-margin` | `inconclusive` | `unavailable`. `confirms_finding_4` is true
      for **exactly one** verdict and never while an insensitive KPI is on record.
    - **The consequence, recorded before the run it decides.** `spoilage_rate` and
      `delivery_latency` are still `sensitive: false` — `_spoilage` reads neither inventory nor
      order size, `_delivery` draws travel time from an independent uniform. So **task 11
      cannot confirm Finding 4**: it can only *falsify* it by measuring material regret, or
      report `inconclusive`. Verified: `classify_regret(0.0, margin=1.0)` returns
      `inconclusive`, `confirms_finding_4=False`. Structures 2 and 4 (tasks 12.3, 13.3) earn
      the flips.
    - `material` requires the **interval to exclude** the margin, not merely the point estimate
      to exceed it — otherwise noise could falsify Finding 4.
    - _Requirements: 5.3, 5.14, 5.34, 5.35_
    - File: `uplift/regret.py` (new)
    - Total function over the `KpiVector` with the terms, signs, weights and replicate
      aggregation ADR-055 declares. `MetricContract.classify` stays untouched — it is a
      three-valued hypothesis outcome, not a cost, and conflating them is how a regret number
      acquires units nobody declared.
    - _Requirements: 5.1, 5.33_

  - [x] 10.2 Implement the two-pass foresight comparator
    - `uplift/foresight.py`: `NoOpRecordingPolicy` (pass one, observes), `ForesightPolicy`
      (pass two, built **from the completed trace**), `run_two_pass`.
    - **Soundness invariant is recorded, not assumed:** `TwoPassResult.demand_identical`
      compares pass two's trace against pass one's, and `usable` is false when they differ. A
      replicate whose passes saw different demand is excluded rather than averaged in. Verified
      `demand_identical=True` over a 2855-event trace at seed 42.
    - **Measured:** foresight cost 2.93 / fill 0.9149 vs no-op 11.79 / fill 0.3592.
    - **The oracle's limit is stated, not implied:** with a non-zero lead time the true optimum
      would order earlier, so `ForesightPolicy` is a *lower bound* on achievable performance and
      the regret it induces is therefore **conservative** — it can only understate how much room
      intelligence has, never overstate it. That is the safe direction.
    - `inject_orders` is explicitly **not** used as the foresight seam: it takes a bare count,
      discards per-SKU identity, and replaces the demand process, so a run through it is not the
      unmodified twin.
    - _Requirements: 5.1, 5.37_

  - [x] 10.3 Add the regret measurement job
    - `.github/workflows/uplift.yml::twin-regret` (its own job, `timeout-minutes: 120`,
      `ubuntu-latest`, no `continue-on-error`), plus a `python -m uplift.regret` CLI and the
      **same-commit** declaration in `blocking-steps.yaml`. Verified: the workflow parses, C64
      reports `verdict=pass` over 370 steps with the new declaration resolving.
    - Its own job rather than a step inside `uplift-proof`, because the two-pass protocol
      doubles per-replicate cost and `uplift-proof` already sits at 350 minutes against a ~360
      ceiling — folding it in would let one measurement time out the other.
    - **Honest scope, carried in the report's own `comparator` field:** the contrast is
      no-op vs perfect-foresight, which is **not yet** the `(s, S)` regret R5.1 asks for.
      `Par_Level_Reorder` is owned by `decision-integrity-uplift-proof` and is a
      **precondition**, not a deliverable here. What this job establishes is the comparator's
      own headroom, which bounds the `(s, S)` regret from above.
    - **AMENDED IN SESSION 2p, BEFORE THE FIRST DISPATCH: the report now carries an interval,
      and the job can be dispatched alone.** Two changes, neither of which alters what is
      measured:
      - `_measure` estimates a paired percentile bootstrap over the per-seed costs
        (`uplift/interval.py`, design E3.1) at `1 - alpha` from the committed Metric_Contract,
        reports `interval_low/high/point/alpha/method/resamples/seed` plus
        `interval_excludes_rule_margin`, and passes the bounds to `classify_regret`. The
        interval's point estimate is **pinned** against `objective.regret`'s rather than
        trusted to agree. A measurement whose dispersion cannot be estimated now reports
        `status: unavailable` and the CLI exits 2, which fails the job -- it is never
        downgraded to a point-estimate verdict. **Why this had to land before checkpoint A is
        recorded under task 11.**
      - `uplift.yml` gained `workflow_dispatch.inputs.job` with an `if:` guard per job, so
        `twin-regret` dispatches without also spending `uplift-proof`'s ~350 runner-minutes.
        `default: both` preserves the previous behaviour and the schedule is unaffected. No
        step was added, so no new `blocking-steps.yaml` entry is owed; the existing
        declaration still resolves, re-verified at C64 `verdict=pass` over 370 steps.
      - **THREE DEFECTS IN THIS JOB, FOUND ONLY BY RUNNING IT (session 4, once the repository
        went public and CI could start at all). Two are repaired in `245d0dc`; the third is
        open.** Recorded here because this sub-task owns the job.
        1. **The measure step reported `success` while measuring nothing.** Under `bash -e` a
           pipeline's status is its LAST command's, so `python -m uplift.regret ... | tee <file>`
           returns `tee`'s success even when the Python crashed. Run `34364879758`: the
           measurement died at import, `tee` wrote a **zero-byte** artifact, and the step was
           **green** while `blocking-steps.yaml` declares it `role: producer` emitting canonical
           JSON. **The job was red only because the DISCLOSURE step below it — explicitly "not a
           gate" — failed on the same root cause. Without that step this job would have been
           GREEN with no measurement in it.** Repaired with `set -o pipefail`. `| tee` kept: the
           JSON in the log is what lets a reader check the artifact against the run, and with
           `pipefail` that visibility is free.
           - **`scripts/audit/workflow_shape_truth.py` CANNOT CATCH THIS.** Its
             `DISCARDING_CONSTRUCTS` is four literals — `|| true`, `|| echo`, `; exit 0`, bare
             `exit 0` — and an unguarded pipeline is none of them, so a declared-blocking step
             can discard its exit status with **C64 reporting pass**. Its own docstring is "A gate
             whose exit status is discarded is not a gate." `| tee` occurs **exactly once** in
             the workflow tree (this step), so the exposure is closed here; **extending the gate
             is a registered-check change and is the operator's call, not this task's.**
        2. **`scipy` was missing from the install closure, and the proof that it was not was
           wrong in an instructive way.** The step's comment claimed a static walk of the 9
           first-party modules reachable from `uplift.regret` found `pydantic-settings` as "the
           ONLY gap". The walk followed imports *from* `uplift.regret`, but `python -m` executes
           the **package initialiser** first, and `uplift/__init__.py` → `uplift.consensus_arm`
           → `uplift.harness` → `uplift.contract` → `from scipy import stats` is nowhere in that
           graph. **Correct about the module graph, wrong about the entry point's import
           closure. A closure proof must start at the command the job actually runs.** This is
           also HANDOFF defect 14 recurring: that defect named this exact import, and the repair
           taken then routed `uplift/interval.py` around `load_contract` instead of widening the
           closure, leaving the import on the package-initialisation path. Fixed narrowly, this
           job only, per defect 22's precedent. `scipy` is pinned in **no** requirements file in
           the repository (`policy.yml` installs it bare), so `>=1.11,<2.0` is a **choice**,
           flagged as one.
        3. **OPEN — the artifact is not canonical JSON.** Run `34366766968` uploaded
           **215,293,577 bytes**: the twin's `structlog` writes to stdout, so `tee` captured a
           debug flood with the report on the final line. `json.load` on the artifact raises
           `JSONDecodeError: Extra data: line 1 column 5`, while `blocking-steps.yaml` declares
           this step `emits: "artifacts/uplift/twin-regret.json (canonical JSON, --json)"` —
           **so that declaration is false as written.** The number was recovered from the last
           line, which is why task 10.4 has figures at all. Not repaired in `245d0dc` because
           the repair is a choice between suppressing twin logging in the measurement path
           (`structlog.configure(wrapper_class=make_filtering_bound_logger(logging.ERROR))`, the
           documented idiom) and writing the report to the file directly instead of through
           stdout — and the second loses the log visibility `pipefail` was just made safe for.
           **Downstream consumers matter here: tasks 17.x, 22.3 and 25 read uplift artifacts
           with a JSON parser, and a 90-day retention on 215 MB per run is its own cost.**
    - _Requirements: 5.1, 5.32_
    - Files: `uplift/foresight.py` (new), `uplift/harness.py`
    - Pass one runs the twin with a no-op policy at seed `s` and records the `DemandTrace`;
      pass two replays the **same seed** with a perfect-foresight policy reading pass one's
      trace. `DecisionPolicy.decide(obs)` sees only present state, so foresight cannot exist
      without the recorded trace.
    - **Stated cost:** the two-pass protocol doubles the twin cost of every comparator
      replicate. That is why the measurement gets its own job rather than sharing
      `uplift-proof`'s 350-minute budget.
    - _Requirements: 5.1, 5.37_

  - [~] 10.4 Commit the materiality margin **after** the first run measures it
    - discharge: uplift.yml::twin-regret (checkpoint A)
    - **HALF LANDED, HALF OWED — read this before re-authoring anything.** Session 1r committed
      the *derivation rule*; the *value* is still `null` and is owed at checkpoint A. That split
      is the whole point (ADR-055 D2.5) and is not an unfinished edit.
      - **Landed and locally verified:** ADR-055 **D2.5**; `regret_objective.materiality_margin`
        in `digital_twin/simulation/policy.yaml` with `value: null` plus its `derivation`,
        `bracketing` and `must_be_below_measured_headroom` blocks;
        `policy.py::materiality_margin_rule` and `::materiality_margin`;
        `uplift/regret.py::_measure` now *reads* the margin instead of hardcoding `None` and
        reports the rule beside the measurement; pin
        `materiality-margin-service-points` (C75 reports **14/14** resolving on both sides);
        a `ratchets.json` entry with `direction: down`;
        `tests/uplift/test_materiality_margin_rule.py` (13 tests passing).
      - **Owed at checkpoint A:** read the reported regret, instantiate
        `materiality_margin.value` **from the rule** (`service_points * 0.01 *
        weights.unmet_service`), record the measured headroom it was checked against, and add
        the pin for the derived value itself.
      - **MEASURED, SESSION 4 — run `34366766968`, sha `245d0dc`, `uplift.yml::twin-regret` via
        the `measure-twin-regret` label. The first real measurement this spec has ever
        produced.** `status: measured`, **200 of 200** replicates usable, `unusable_seeds: []`,
        24.0 h per replicate.

        | field | measured |
        |---|---|
        | `mean_baseline_cost` | `11.835228527152536` |
        | `mean_foresight_cost` | `2.897339574184977` |
        | `comparator_headroom` | `8.937888952967558` |
        | `regret` | `8.937888952967558` |
        | `interval_low` / `interval_high` | `8.916389405913677` / `8.958204644600675` |
        | `interval_point` | `8.937888952967558` (agrees with `regret`) |
        | `interval_method` / `alpha` / `resamples` / `seed` | `paired_percentile_bootstrap` / `0.05` / `2000` / `0` |
        | `margin_rule_derives` | `0.4` |
        | `margin_rule_below_headroom` | `true` |
        | `interval_excludes_rule_margin` | `true` |
        | `margin_committed` | `null` |
        | `verdict` | `unavailable` — exactly as finding 16 predicted |
        | `insensitive_kpis` | `["spoilage_rate", "delivery_latency"]` |

      - **THE HEADROOM MOVED, so the D2.5 amendment owes the `bracketing.upper` correction.**
        D2.5 and `policy.yaml`'s `bracketing.upper` both record `11.79 - 2.93 = 8.86`; the
        measurement is `11.835228527152536 - 2.897339574184977 = 8.937888952967558`. That is
        prose and is not pinned, but it is a recorded number that no longer matches the tree.
      - **DO NOT COMMIT THE MARGIN YET. Committing any value inside D2.5's own bracket forces
        `verdict: material`, which instructs a reader to declare Finding 4 falsified and stop
        the spec — on a measurement of the WRONG COMPARATOR. See conflict M under task 11.**
        The value the rule derives is confirmed as `0.40` and the guard would accept it; that
        is precisely what makes this dangerous rather than merely incomplete.
    - Files: `digital_twin/simulation/policy.yaml`,
      `infrastructure/quality/ratchets.json`,
      `infrastructure/quality/doc-number-pins.yaml`
    - **Path corrected.** This sub-task originally named
      `infrastructure/quality/twin-decision-relevance.yaml`; Conflict A decided the single
      committed twin-parameter file is `digital_twin/simulation/policy.yaml` (design E2c.2), and
      that file exists while the other deliberately does not.
    - **The conflict this sub-task had to resolve, surfaced rather than absorbed.** R5.2 says
      the margin is committed *only after it has been measured*. Every other threshold in this
      plan is pinned *before* the run judged against it (tasks 12.4, 16.2). Taken naively the
      two rules license choosing the margin with the number already in hand, which decides task
      11's verdict by the choice of margin — the pattern task 25's pre-commitment forbids.
    - **Resolution, landed.** The rule is pre-registered; only the magnitude is measured.
      `policy.py::materiality_margin` **re-derives** a committed value from the rule and refuses
      one that disagrees, so the pre-registration is enforced rather than decorative. It also
      refuses a margin at or above the measured comparator headroom, which would be
      unfalsifiable by construction. The ratchet direction is **down**, because raising the
      margin is the self-serving move: it makes `material` harder to reach, which makes Finding
      4 harder to falsify. **A margin that could not have been written down before the number
      existed is not admissible.**
    - _Requirements: 5.2_

  - [x] 10.6 Write property test for regret totality and the insensitivity precedence
    - `tests/uplift/test_regret_totality_property.py` — **16 tests passing**, not slow-marked
      (pure arithmetic over a policy-file read; locus `ci.yml::uplift-verify` fast step).
    - The precedence clause is asserted as an **implication over the whole verdict space**
      rather than a case analysis, so adding a fifth verdict later cannot quietly open a path to
      confirmation.
    - `test_today_a_sub_margin_regret_cannot_confirm_finding_4` pins the insensitive set to
      exactly `{spoilage_rate, delivery_latency}` **on purpose**: when structures 2 and 4 earn
      those flips, this test fails and forces the reader to notice that what task 11 may conclude
      has changed. A note would not fail.
    - `# Feature: decision-quality-proof, Property 54: Regret is total against the declared objective, and an insensitive KPI outranks a null`
    - File: `tests/uplift/test_regret_totality_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 5.1, 5.3, 5.14, 5.33, 5.34, 5.35_

- [ ] 11. Checkpoint — did the regret test falsify Finding 4?
  - discharge: uplift.yml::twin-regret (checkpoint A)
  - Ensure all tests pass, ask the user if questions arise.
  - **Decision point, not a status report.** If the measured `(s, S)` regret on the unmodified
    twin is already **materially positive** — at or above the R5.2 margin, with its interval
    excluding the margin — then **Finding 4 is falsified**. Stop. Do not begin task 12. R5's
    remaining scope shrinks substantially and R5 must be **re-cut** before implementation
    continues (R5.3, R5.4). Report the falsification plainly; it is a good outcome, not a
    failure of the plan.
  - If regret is below the margin, check R5.35 **before** reading the result as confirmation:
    if any KPI in the objective is recorded under R5.34 as not observably sensitive, the
    result is **inconclusive**, and the repair is to the instrument, not to the twin's physics.
  - Only a regret below the margin **with every objective KPI recorded sensitive** licenses
    task 12.
  - **The verdict is four-valued, and the fourth value is the one this tree is in.**
    `uplift/regret.py` returns `material` | `sub-margin` | `inconclusive` | `unavailable`, and
    today it returns `unavailable`, because task 10.4 has not committed a margin. `unavailable`
    is **not** `inconclusive`: one is a measurement that could not decide, the other is the
    absence of a measurement, and I-7 forbids reading absence as either a pass or a null.
    `SESSION_PROTOCOL.md`'s checkpoint-A table states what each of the four licenses. Checkpoint
    A exists to move this task off `unavailable` **before** task 12 is authored — which is the
    sequencing `## Overview` calls load-bearing.
  - **A THIRD CONFLICT, FOUND AND CLOSED IN SESSION 2p BEFORE THE MEASURING RUN.** Three
    sources disagreed about what `material` requires, and the disagreement decided whether this
    spec could be stopped by a number with no dispersion.
    - `RegretVerdict`'s docstring and `SESSION_PROTOCOL.md`'s checkpoint-A table both define
      `material` as regret at or above the margin **with its interval excluding it**.
    - **R5.3 does not.** It says: at or above the margin, therefore falsified. The interval
      clause is **R5.13**, which governs the *non-stationary* twin at task 13.7 — not this run.
    - And `_measure` supplied **no interval at all**. `classify_regret`'s material branch reads
      `regret >= margin and (interval is None or excludes_margin)`, so an absent interval was
      not a missing precondition, it was a *satisfied* one. On a point estimate alone, this
      checkpoint could have reported Finding 4 falsified and ended the spec.
    - **Resolved in favour of the stricter reading, and by changing the instrument rather than
      the standard.** `uplift/interval.py` (design E3.1's estimator, landed early out of task
      15.2) now supplies a paired bootstrap interval at `1 - alpha` from the committed
      Metric_Contract, and `_measure` passes it. `classify_regret`'s logic is **unchanged** —
      supplying a non-`None` interval is what makes `excludes_margin` load-bearing, so all 17
      of task 10.6's pinned properties still hold. A run whose dispersion cannot be estimated
      reports `status: unavailable` and exits 2 rather than falling back.
    - **This is stricter than R5.3 requires, deliberately.** Adopting a standard the criterion
      does not demand is only legitimate in the direction that makes falsification *harder to
      claim*, never easier; the reverse would be metric-shopping. Recorded here rather than
      absorbed, because a reader comparing this run to R5.3 should find the deviation stated.
  - **This task's own precondition conflicts with task 12's, and the conflict is in this file.**
    Task 12's preconditions say only "task 11 did not falsify Finding 4", which an
    `inconclusive` satisfies; the licensing clause above requires every objective KPI recorded
    sensitive, which is unreachable until tasks 12.3 and 13.3 land. Resolved in favour of task
    12's precondition, on task 11's own words that "the repair is to the instrument" — E2c *is*
    that repair. Recorded in `SESSION_PROTOCOL.md`; not to be re-litigated silently.

  - **CONFLICT M — SESSION 4. THE INSTRUMENT CAN NOW ONLY RETURN `material`, AND `material`
    WOULD BE A CLAIM ABOUT A COMPARATOR THIS TASK IS NOT ABOUT. Read this before committing a
    margin; it is the reason task 10.4's remaining half was NOT taken when it became possible.**

    Run `34366766968` (sha `245d0dc`) measured `regret = 8.937888952967558` with interval
    `[8.916389405913677, 8.958204644600675]`. Run 1 correctly reports `verdict: unavailable`
    because no margin is committed. But trace what run 2 must return:

    - `classify_regret`: `regret >= margin` → `8.9379 >= 0.40` → **true**;
      `excludes_margin = interval_low > margin` → `8.9164 > 0.40` → **true**;
      therefore **`material`** → "FINDING 4 IS FALSIFIED" → this task says **STOP**.

    **Two independent reasons that verdict would be wrong, and the second is structural.**

    1. **The baseline arm is a NO-OP, not a base-stock `(s, S)` policy.** `uplift/foresight.py`
       pass one is `NoOpRecordingPolicy` — its own docstring is "Pass one: change nothing" — and
       the run reports `restock_threshold: 0.0`. The artifact's own `comparator` field states it
       outright: *"this is NOT yet the (s, S) regret R5.1 asks for -- Par_Level_Reorder is owned
       by decision-integrity-uplift-proof and is a PRECONDITION. This job measures the
       comparator's own headroom, which bounds it"*. This task, R5.1 and Finding 4 are all about
       the `(s, S)` policy's regret. **8.9379 is the regret of doing nothing**, which bounds the
       `(s, S)` regret from above and does not equal it. In service-point equivalents it is
       `8.9379 / 0.08` ≈ **112 points**, against an incumbent whose recorded shortfall against
       its own newsvendor target is about **3.3** points — the number is describing a different
       subject, not a surprising result about this one.

    2. **`regret` and `comparator_headroom` are the SAME EXPRESSION, so the guard that exists to
       keep `material` reachable-but-not-inevitable is vacuous here.**
       `RegretObjective.regret(policy, reference)` is `aggregate(policy) - aggregate(reference)`,
       and `_measure` computes `headroom = mean_baseline - mean_foresight` — identical, and the
       run confirms it: `regret == comparator_headroom == interval_point` to every digit.
       `policy.py::materiality_margin`'s `must_be_below_measured_headroom` therefore admits
       exactly the margins that are **below the regret it will be compared against**. Any
       admissible margin below `interval_low` satisfies both `material` clauses by construction.
       D2.5's own bracket is 3.3–8.86 **service points** = `0.264`–`0.709` objective units, all
       far below `8.9164`. **Inside its own declared bracket, this task can return nothing but
       `material`.**

    **That is the mirror of this project's own rule.** "A number that cannot fail is not a
    number"; a verdict that cannot be anything else is not a verdict. The guard was written to
    prevent an unfalsifiable margin in one direction and is blind to the other, because it
    checks the margin against the very quantity being judged rather than against an independent
    bound.

    **Not resolved here, because both candidate resolutions are the operator's** (authority
    rule: surface, never silently resolve). Recorded so the next reader does not commit `0.40`
    and read the result as the end of the spec:

    - **Land the real comparator.** `Par_Level_Reorder` is the `(s, S)` arm R5.1 names and is a
      declared **precondition** owned by `.kiro/specs/decision-integrity-uplift-proof/`. With it
      in place, `regret` and `comparator_headroom` stop being the same expression, the guard
      regains its discriminating power, and the verdict becomes a claim about the right subject.
      This is the repair the design already implies.
    - **Or give the guard an independent bound**, so a margin is checked against a contrast other
      than the one it judges. Cheaper, and it changes a committed pre-registered rule, which is
      exactly the kind of change D2.5 requires to land *before* the run judged against it.

    **Until one of them lands, task 11's honest state is `unavailable` on a run that succeeded**
    — not `inconclusive`, and emphatically not `material`. I-7: the measurement happened, and
    what it measured is not what this task asks.

  - **SESSION 5 — CONFLICT M's FIRST REASON IS REPAIRED, AND CONFLICT N IS WHY IT WAS CHEAPER
    THAN COSTED. This task is still `[ ]`: no margin is committed and no run has been made
    against the new comparator.**

    **CONFLICT N — the repair option was costed against a false premise, twice.**

    1. `SESSION_PROTOCOL.md:285` recorded `Par_Level_Reorder` as "a declared precondition owned
       by another spec and **has not landed**", and `NEXT_SESSION_PROMPT.md` as "another spec's
       **unlanded** precondition". **It had landed.** It is on disk at
       `uplift/baselines/par_level_reorder.py`;
       `.kiro/specs/decision-integrity-uplift-proof/tasks.md` marks its tasks **2, 2.1 and
       2.2 `[x]`**; and `tests/uplift/test_par_level_reorder_properties.py` already runs
       Property 1 against it on `uplift-verify`'s fast step. Ownership is that spec's and is
       not adopted here. **Availability was never the blocker: `run_two_pass` invoked no
       `DecisionPolicy` at all.** The gap was wiring, not a missing deliverable.
    2. **`HANDOFF.md`'s repair note was wrong in its second half.** It said landing the arm
       would make `regret` and `comparator_headroom` "stop being the same expression". It would
       not: `regret` is `aggregate(policy) - aggregate(reference)` and the headroom was
       `mean_baseline - mean_foresight` over the same two arms, so whatever pass one became the
       two coincided. **They separate only if the no-op arm is RETAINED as a third pass.**
       Repair option (b) alone would have fixed reason 1 and left reason 2 intact.

    **FINDING 40 — the line where the wrong comparator entered, and why `restock_threshold`
    needed no amendment.** `comparator.restock_threshold: 0.0`'s committed rationale is about
    `uplift/harness.py`, where an arm supplies its own `(s, S)` through `decide()` so the twin's
    own must be off. `uplift/regret.py::_measure` reused the same key in a path that drove **no
    policy**, so `0.0` there did not de-stack an arm — it deleted the incumbent. Supplying the
    `(s, S)` arm through `decide()` with the threshold still `0.0` is exactly the configuration
    that rationale calls correct, so R5.36 is unamended and Property 53 is untouched.

    **FINDING 39 — the instrument at the centre of this checkpoint had no test.**
    `run_two_pass` had one consumer and **no test file in the tree imported
    `uplift.foresight`**. `NoOpRecordingPolicy` was instantiated nowhere and
    `ForesightPolicy.decide` was never called, so both documented arms were prose rather than
    behaviour. That is why a no-op reference arm sat at the centre of this spec for four
    sessions with nothing objecting.

    **What landed (commit `4b9d0d4`).** Three arms per replicate at one seed and one cadence:
    **A** no-op (`NoOpRecordingPolicy`, now the mechanism) supplying
    `comparator_headroom = A - C`; **B** the committed `(s, S)` reference arm supplying
    `regret = B - C`; **C** the foresight oracle. The interval is estimated over the **judged**
    contrast. `headroom >= regret` was a tautology under two arms and is now a claim about the
    world, with `_measure` reporting `unavailable` and exiting 2 if it fails. Both levels are
    **read** — `s = 50` from `engine.py::_restock_threshold`, `S = 100` from its initial-stock
    literal — so the comparator introduces no chosen constant. ADR-055 gained an amendment-log
    line and **D2.5.1**, in the same commit as the code, per D2.5's own ordering rule; its
    `bracketing.upper` moved from session 1's four-replicate `11.79 - 2.93 = 8.86` to the
    measured `8.937888952967558` from run `34366766968`.

    **What did NOT land, deliberately.** `regret_objective.materiality_margin.value` is still
    `null`; the parked derived-margin pin is still parked; no second label was added. The two
    new `s`/`S` pins are **parked** in `pending_pins:` rather than landed, because landing them
    moves `doc_truth`'s claim set and can move C56, and a second regeneration is already owed
    for the inverted `ledger_gen`/`readme_gen` order — one diff should not carry two causes.

    **The unproven claim, stated so nobody assumes it.** That `Par_Level_Reorder(s=50, S=100)`
    *reproduces* the twin's endogenous restock is **not** proven: an internal engine guard
    versus an external order-up-to decision on the comparator's cadence. D2.5's lower bracket
    (`fill_rate = 0.8556`) is a comparable reference for this arm, not a measurement of it.

    **WHAT THIS TASK STILL NEEDS, and the verdict may still be `material`.** Run 1 by label on
    the new comparator, then the D2.5 amendment stating the derived literal, then the margin
    commit, then run 2. A `material` verdict on the reference arm would be an **admissible**
    falsification about the right subject — which is a good outcome under this spec's own
    design — as distinct from the inadmissible one conflict M prevented.

  - **SESSION 6 — CHECKPOINT A WAS DELIBERATELY NOT RUN. This is a recorded decision, not an
    oversight, and the next session should not read it as one.**

    Nothing was taken from this task: `regret_objective.materiality_margin.value` is still
    `null`, the derived-margin pin is still parked, the two `s`/`S` pins are still parked, no
    D2.5 amendment landed, and no label was added. `pin_extractor_truth` reports **14** declared
    at close — not 15, not 16 — which is the mechanical statement of all three.

    **The reason, by explicit operator decision.** The instrument this checkpoint judges sat in
    a tree whose own property surface was red in nine places, eight of them this spec's. A
    `material` verdict read off that tree would be a claim about a comparator standing in a
    suite that nothing had ever executed — weaker evidence than the same verdict read off a
    green one, and this spec exists to refuse exactly that kind of weak evidence. Session 6
    spent itself on the surface instead, and the whole of checkpoint A's remaining procedure —
    run 1 by label, the D2.5 amendment, the margin commit, run 2 — carries over **unchanged and
    in that order**, D2.5's own rule still putting the amendment before the run judged against
    it.

    **What changed in its favour anyway.** `quality-gates` step 18's repair (task 27.5, session
    6) is predicted to unblock steps 19–23, and the fast property surface has had its first
    repair pass. Neither is a precondition of this checkpoint — `twin-regret` has no `needs:` —
    but both mean the next reading of a `material` verdict happens against a tree whose gates
    report something.

- [ ] 12. E2c — structures 1 and 2: non-stationary demand, and capacity that binds
  - Implements the first two of ADR-055's five structures. **Every structure names the agent
    decision it unlocks; nothing is added for realism's sake.**
  - Preconditions: **checkpoint A has run and task 11's verdict is not `material`** — not
    merely "task 11 did not falsify Finding 4", because an unrun task 11 falsifies nothing by
    never having looked (I-7). ADR-055 is committed (8.1); E4a's statistics exist (7.4).

  - [ ] 12.1 Structure 1 — non-stationary demand calibrated from the real feed
    - Files: `digital_twin/simulation/engine.py`,
      `digital_twin/simulation/policy.yaml`
    - **Path corrected before session 2 could act on it.** This sub-task declared
      `infrastructure/quality/twin-decision-relevance.yaml`, which Conflict A decided against:
      the single committed twin-parameter file is `digital_twin/simulation/policy.yaml` (design
      E2c.2), `policy.py` reads it, and `pin_extractor_truth` (C75) resolves its 13 pins.
      Creating the other file here would fork the twin's parameters across two artifacts.
    - *Unlocks the Demand_Forecaster: forecasting has zero value under stationary demand.*
      `_order_arrival` currently draws
      `self._rng.exponential(1.0 / (order_arrival_rate * demand_mult))` — stationary Poisson.
    - Intensity varies within a simulated day, across days of the simulated week, and rises for
      a configured promotion's duration. The shape is **calibrated from task 7.4's statistics,
      not invented literals**, and the calibrated parameters are **committed to the policy
      file, not embedded in `engine.py`**.
    - _Requirements: 5.8, 5.9, 5.10, 5.11, 5.12_

  - [ ] 12.2 Write property test for the demand-intensity shape
    - `# Feature: decision-quality-proof, Property 55: Demand intensity varies by hour, by weekday and under promotion, from the committed policy`
    - File: `digital_twin/tests/test_demand_intensity_shape_property.py`
    - `@pytest.mark.slow`; selected by `ci.yml::uplift-verify`'s slow step (`-m "slow"`,
      `HYPOTHESIS_PROFILE=heavy`, `digital_twin/tests` in the path list).
    - Budget inherited from the profile.
    - _Requirements: 5.8, 5.9, 5.10, 5.11_

  - [ ] 12.3 Structure 2 — a finite rider pool and finite pick stations that queue
    - File: `digital_twin/simulation/engine.py`
    - *Unlocks `routing_navigator` and dispatch prioritisation: with infinite capacity,
      dispatch policy is a no-op.* `git grep
      "simpy.Resource\|simpy.Container\|simpy.Store\|PriorityResource"` across `*.py` returns
      **no match** — there is no contended resource anywhere in the twin today.
    - Model both pools as contended resources and make the delivery wait a **function of the
      queue state** rather than the independent `self._rng.uniform(10.0, 45.0)` draw.
    - Replace the OSRM travel-time claim in **both** the `SupplyChainSimulation` class
      docstring and the `_delivery` docstring with a description of the travel time the code
      actually produces. Do **not** bind the twin to the repository's OSRM container
      (`docker/docker-compose.mumbai.yml::osrm-mumbai`): that would make every twin run a
      category-1 workload under I-0.
    - **Flip `delivery_latency` to `sensitive: true` in `digital_twin/simulation/policy.yaml`
      in this same commit, and move the pin that reads it.** This obligation was unassigned
      until now: `SESSION_PROTOCOL.md` recorded that structures 2 and 4 *earn* the two
      sensitivity flips, but no sub-task instructed the edit, and `policy.py` refuses to
      default a missing key. The flip is what makes task 11's `sub-margin` verdict reachable at
      all, so leaving it implicit leaves the whole R5.35 precedence chain resting on nothing.
      Record the evidence for the flip — the utilisation-wait relationship task 12.4 measures —
      rather than asserting it.
    - **Same-commit coupling.**
      `tests/uplift/test_regret_totality_property.py::test_today_a_sub_margin_regret_cannot_confirm_finding_4`
      pins the *current* insensitivity and **fails the moment this flip lands**, deliberately:
      it exists to force whoever earns the flip to notice that what task 11 may conclude has
      changed. Update it in the same commit and state the new expectation in its docstring.
      This is a **precondition correction, not an assertion weakening** — R2.10 forbids the
      latter, and the distinction is that the subject changed, not the standard.
    - _Requirements: 5.15, 5.16, 5.17, 5.20_

  - [ ] 12.4 Write property test for the utilisation-wait relationship
    - `# Feature: decision-quality-proof, Property 56: Wait time is non-decreasing in utilisation and its increments rise in the declared band`
    - File: `digital_twin/tests/test_utilisation_wait_property.py`
    - The ladder levels and the near-saturation band boundaries are read from the task 8.2
      policy file and are **committed before the run judged against them** — the same deferral
      R5.2 uses. No value is stated in the property.
    - `@pytest.mark.slow`; selected by `ci.yml::uplift-verify`'s slow step.
    - Budget inherited from the profile.
    - _Requirements: 5.15, 5.16, 5.17, 5.18, 5.19_

- [ ] 13. E2c — structures 3, 4 and 5, and the Pareto guard that can cancel the experiment

  - [ ] 13.1 Structure 3 — correlated lead times and observable supplier state
    - Files: `digital_twin/simulation/engine.py`, `digital_twin/world/runtime.py`
    - *Unlocks `supplier_trust` and `inventory_sentinel` safety-stock decisions: under i.i.d.
      lead times a static safety stock is optimal.* `_restock` currently draws
      `self._rng.uniform(30.0, 120.0) * lead_time_mult` — i.i.d. and uncorrelated with demand.
    - Correlate lead time with concurrent demand; auto-correlate across consecutive simulated
      days; attribute each restock to a **named supplier** and expose that supplier's realised
      lead-time history in the `Observation` presented to **every arm**, so `supplier_trust`'s
      reliability scoring has an observable subject.
    - _Requirements: 5.21, 5.22, 5.23_

  - [ ] 13.2 Write property test for lead-time correlation and supplier attribution
    - `# Feature: decision-quality-proof, Property 57: Lead time is demand-correlated, day-autocorrelated and supplier-attributed`
    - File: `digital_twin/tests/test_lead_time_correlation_property.py`
    - `@pytest.mark.slow`; selected by `ci.yml::uplift-verify`'s slow step.
    - Budget inherited from the profile.
    - _Requirements: 5.21, 5.22, 5.23_

  - [ ] 13.3 Structures 4 and 5 — perishability coupling and substitution
    - File: `digital_twin/simulation/engine.py`
    - *Unlocks `freshness_guardian` and `pricing_oracle`, and creates the multi-objective
      tension.* `_spoilage` currently applies `decay_rate = 0.01 * spoilage_rate_multiplier`
      against a fixed `0.3` threshold with freshness keys frozen at `start()`, reading neither
      inventory nor order size.
    - Make spoilage a function of **age-at-arrival** and of **order size**, so bulk ordering
      raises spoilage. When a demand event names a SKU whose stock is zero, divert the
      **substitution fraction committed in the task 8.2 policy file** to that SKU's declared
      substitutes, giving `pricing_oracle`'s cross-SKU pricing and `freshness_guardian`'s
      markdown decisions a channel to act on.
    - State `spoilage_rate`'s change of meaning in ADR-055 rather than absorbing it (8.1
      already records the obligation): `orders_spoiled` increments per SKU per tick, so the
      ratio is a tick count, not a spoiled-units fraction.
    - **Flip `spoilage_rate` to `sensitive: true` in `digital_twin/simulation/policy.yaml` in
      this same commit**, on the same reasoning as task 12.3's flip of `delivery_latency`, and
      with the same coupling to
      `tests/uplift/test_regret_totality_property.py::test_today_a_sub_margin_regret_cannot_confirm_finding_4`.
      With both flips landed, that test's premise is spent and its replacement states the new
      one. Record what makes `spoilage_rate` sensitive — that spoilage now reads age-at-arrival
      and order size — rather than asserting the flag.
    - _Requirements: 5.25, 5.26, 5.27_

  - [ ] 13.4 Write property test for spoilage coupling and the substitution channel
    - `# Feature: decision-quality-proof, Property 58: Spoilage rises with age and order size, and a stockout diverts the declared substitution fraction`
    - File: `digital_twin/tests/test_spoilage_substitution_property.py`
    - `@pytest.mark.slow`; selected by `ci.yml::uplift-verify`'s slow step.
    - Budget inherited from the profile.
    - _Requirements: 5.25, 5.26, 5.27_

  - [ ] 13.5 Implement the four single-objective policies and interval-aware Pareto dominance
    - Files: `uplift/single_objective_arms.py` (new), `uplift/pareto.py` (new)
    - The four policies: minimise `stockout_rate`; minimise `spoilage_rate`; minimise the
      R5.40 on-hand measure; minimise `avg_delivery_time_min`. (R5.28 as originally written
      named "minimise holding cost", which exists nowhere in the tree, and "maximise SLA",
      which is not a `KpiVector` field — hence the R5.40 term from task 9.3.)
    - Dominance is **interval-aware**: one policy dominates another only if it is no worse on
      every KPI named in the R5.33 objective and strictly better on at least one **with their
      reported intervals disjoint**. Evaluate the four **together with the reference policy set
      declared in ADR-055** — the Pareto frontier of a finite non-empty set is non-empty, so
      evaluating only the four makes R5.28 unsatisfiable by construction.
    - The Baseline_Policy suite itself (`Par_Level_Reorder`, `Static_Pricing`,
      `Greedy_Routing`, `No_Op_Disruption`) is owned by
      `.kiro/specs/decision-integrity-uplift-proof/` and is a **precondition**, not a
      deliverable here.
    - _Requirements: 5.28, 5.29_

  - [ ] 13.6 Write property test for interval-aware Pareto dominance
    - `# Feature: decision-quality-proof, Property 59: Interval-aware Pareto dominance is correct and excludes the single-objective set`
    - File: `tests/uplift/test_pareto_dominance_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 5.28, 5.29_

  - [ ] 13.7 Wire E2c's comparative measurements into CI
    - Files: `.github/workflows/uplift.yml`,
      `infrastructure/quality/blocking-steps.yaml`
    - Four measurements, each a category-4 workload and each CI-only (R5.32): `(s, S)` regret
      on the **non-stationary** twin exceeding the R5.2 margin with its interval excluding it
      (R5.13), and its converse — a regret that is not strictly positive is reported as
      *non-stationarity too weak to make forecasting pay* (R5.14); the utilisation ladder's
      mean wait times (R5.18, R5.19); the supplier-aware versus supplier-blind comparison on
      the same replicate seeds, better on every objective KPI with intervals disjoint on at
      least one (R5.24); and the Pareto evaluation of task 13.5 (R5.28).
    - Declare every new step in `blocking-steps.yaml` in the same commit as the step names.
    - _Requirements: 5.13, 5.14, 5.18, 5.19, 5.24, 5.28, 5.32_

- [ ] 14. Checkpoint — is consensus provably unnecessary?
  - discharge: uplift.yml, task 13.7's E2c measurement steps (checkpoint B)
  - Ensure all tests pass, ask the user if questions arise.
  - **Decision point with a stop condition.** If **any** single-objective policy is
    Pareto-optimal on the modified twin under R5.29's interval-aware dominance, then the
    consensus experiment is reported as **having no room to win and must NOT be run**. A
    Pareto-optimal single-objective policy is a proof that consensus is unnecessary. Do not
    proceed to E3 in that case; report the finding and re-scope.
  - Also review before proceeding: every PRESERVE-list expectation from task 9.7 still holds
    or has a stated new expectation (R5.31); ADR-055's falsifiable claim (R5.6) — that a
    base-stock `(s, S)` policy is now measurably sub-optimal on this twin — is supported by
    task 13.7's regret measurement; and every threshold committed in tasks 8.2, 10.4, 12.x and
    13.x has a `ratchets.json` entry whose extractor was verified **by running it**.

### Phase 3 — E3: the controlled experiment (R6, R7)

- [ ] 15. E3 — the interval, the schema that carries it, and the explicit comparator
  - Implements **AD-15** and **AD-16**. R6.1, R6.2 and R7.14 are each judged on a 95% interval,
    and **no interval exists anywhere in `uplift/`**: a grep for
    `bootstrap|confidence_interval|ci_low|ci_high|percentile(` returns no match, and
    `tests/uplift/test_uplift_null_arm_property.py:67` states outright that "no interval is
    estimated here at all". Three criteria are therefore judged on a quantity nothing produces.
  - **AD-15 is affordable for exactly one reason:** `arm_aggregates_digest` is SHA-256 over
    `canonical_arm_aggregates`, which serialises **only** the `ArmAggregate` sequence, so an
    interval block leaves the digest byte-identical and predecessor Property 15 (cross-process
    byte identity, R6.11) does not move. That is what makes this a tractable schema change on an
    `extra="forbid"`, `frozen=True` model rather than a chain-rewrite-shaped one.
  - **AD-16 changes reachability, not behaviour.** `_resolve_baseline_arms` keeps its pooling
    semantics; what changes is that pooling must be asked for. `cli.py::main` never passes
    `baseline_arm=` today, so R6.1's premise — two identical policies compared — fails before the
    run starts: a `Par_Level_Reorder` copy of the consensus arm is still compared against a pool
    of four.

  - [ ] 15.1 Add the versioned interval block to `UpliftArtifact`
    - Files: `uplift/harness.py`,
      `tests/uplift/test_uplift_artifact_canonical_roundtrip_property.py`, every committed
      artifact fixture under `tests/uplift/`
    - Frozen `ArtifactInterval` (`method`, `alpha`, `resamples`, `seed`, `low`, `high`, `point`)
      plus a top-level `schema_version: int`, `extra="forbid"` preserved on both. `point` equals
      `headline_uplift` and is **pinned against it**, not computed twice.
    - `from_canonical_json` accepts `schema_version: 1` payloads with `interval: null` and
      refuses to report them proof-grade for the interval clause; `schema_version: 2` requires
      the block for a completed powered run. `unavailable_reasons` gains one entry naming the
      absence, so an artifact can state honestly that its interval could not be estimated (I-7).
    - **Same-commit coupling.** The round-trip property's expected key set and every fixture's
      `schema_version` move with the model, because that property enumerates rejection cases
      including "an unknown fidelity field" and "a restated `arm_aggregates_digest`" — an
      unknown key inside `interval` must become a *rejection*, which makes the property more
      discriminating, not less. Wide but shallow; this is AD-15's stated price for putting the
      interval inside the byte-pinned model rather than in a second file nobody keeps in sync.
    - _Requirements: 6.13, 7.14, 7.17_

  - [ ] 15.2 Implement the interval estimator and read `alpha` from the contract
    - Files: `uplift/interval.py` (new), `uplift/harness.py` (the `assemble_uplift_result` call
      site)
    - `alpha` is **read** from `uplift/metric_contract.yaml` (a committed `0.05`), never inlined
      — the `95%` in R6.1 and R6.2 is `1 - alpha` from that contract and is not an invented
      number (AD-13). The resampling `seed` is recorded so the interval replays.
    - **HALF LANDED EARLY, IN SESSION 2p. LEFT OPEN ON PURPOSE — read this before authoring.**
      The estimator exists and is executed; the wiring does not and cannot yet. Left `[ ]`
      rather than `[~]` because the owed half is *authoring blocked on task 15.1*, not a proof
      owed by a CI job, and a `discharge:` line naming a job would be false — it would also make
      the census stop offering this as authorable work, which is exactly what session 3 needs
      it to do.
      - **Landed and executed:** `uplift/interval.py` — `paired_difference_interval`,
        `headline_interval` (E3.1's declared name, a thin alias), a frozen `Interval` carrying
        the seven fields `ArtifactInterval` declares, `contract_alpha`, and `resamples_for`.
        `tests/uplift/test_interval_estimation_property.py` (task 15.3) is **20 tests passing at
        both `dev` and `heavy`**. `uplift/regret.py::_measure` is the first consumer.
      - **Still owed here:** the `uplift/harness.py::assemble_uplift_result` call site, which
        needs task **15.1**'s `ArtifactInterval` and `schema_version` to exist first.
      - **Three deviations from the design, all recorded in design.md E3.1 rather than absorbed:**
        the return type is `uplift.interval.Interval` and not `ArtifactInterval` (importing
        `harness.py` would drag the twin and numpy into `regret.py`'s light import path);
        `alpha` is read with `yaml` and not through `uplift.contract.load_contract` (which
        imports `scipy`, absent from `uplift.yml::twin-regret`'s install closure — the two
        readers are pinned together by a test); and **the design's order-invariance mechanism
        was wrong** and is corrected there.
      - **Why it came forward:** see task 11's third conflict. Without an interval,
        `classify_regret` reached `material` on a point estimate, and `material` stops the spec.
    - _Requirements: 6.13, 7.14_

  - [x] 15.3 Write property test for the interval estimator
    - `# Feature: decision-quality-proof, Property 60: The interval is estimated at 1 - alpha, brackets the point estimate and is order-invariant`
    - File: `tests/uplift/test_interval_estimation_property.py`
    - **20 tests passing**, executed at `HYPOTHESIS_PROFILE=dev` **and re-verified at `heavy`**.
      Not slow-marked (pure arithmetic over stdlib `random`; locus `ci.yml::uplift-verify` fast
      step). Landed early with 15.2's estimator half; ticked because it is both authored and
      executed, not because the estimator exists.
    - All three declared clauses are asserted, and the third found a design defect: E3.1 claimed
      sorting the resample statistics gives input-order invariance, which it does not — the
      seeded index stream is fixed, so a permutation changes which values each resample draws.
      The subject sorts the paired differences *before* resampling and the statistics *after*;
      design.md E3.1 now records the correction.
    - Bracketing is asserted **unconditionally**, with no tolerated-exception disjunct: the
      percentile bootstrap of a mean does not guarantee it as a theorem, so a counterexample
      would be a finding about the estimator (R2.10). The refusal path is proven separately by
      constructing an inadmissible `Interval` directly, because "no generated example triggered
      it" is not evidence that a guard works.
    - Carries the **two-reader agreement test** that stops `contract_alpha` drifting from
      `MetricContract.alpha`. It runs here rather than in `twin-regret` because `scipy` is
      present in this job's closure and absent from that one — which is the whole reason the
      narrow read exists.
    - **A lesson worth carrying: `dev` passed and `heavy` failed.** The degenerate-sample test
      asserted `point == value` exactly; `fmean` of `n` copies of a value is one ulp off at
      `value=4.413920275115946e-253, count=5`. Fixed the **precondition** (closeness for
      point-vs-value, exact equality retained for `low == high == point`), not the assertion,
      and did not touch the subject. **A `dev`-profile green is ten examples of evidence.**
    - Budget inherited from the root `conftest.py` profile via `HYPOTHESIS_PROFILE`.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 6.13, 7.14_

  - [ ] 15.4 Write property test for the interval-carrying artifact's canonical form
    - `# Feature: decision-quality-proof, Property 61: An interval-carrying artifact round-trips canonically and leaves the aggregate digest unchanged`
    - File: `tests/uplift/test_interval_artifact_roundtrip_property.py`
    - The digest clause is the load-bearing half: it is what proves AD-15's affordability claim
      rather than assuming it.
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 7.17_

  - [ ] 15.5 Make the comparator explicit and scope incompleteness by contrast
    - Files: `uplift/harness.py`, `uplift/cli.py`
    - Add `arm_role: Literal["consensus", "baseline", "oracle", "excluded"]` to arm registration
      and make `_resolve_baseline_arms` **refuse to pool** an `oracle` or `excluded` arm. The
      pooled default then means "every arm declared a baseline", which is what its docstring
      already claims. Record the resolved roles in `UpliftProvenance.arm_roles`.
    - Add `ControlSpec` to `uplift/cli.py` and require one of `--pooled-baseline` or
      `--baseline-arm NAME` for any run whose arm set is not exactly the five `build_arms`
      returns. An unrecognised arm with no explicit comparator is a `ValueError`, not a pooled
      default.
    - Replace `_run_is_incomplete`'s use at the verdict with
      `_contrast_is_incomplete(harness_result, consensus_arm, baseline_arms)`. The whole-run
      predicate is **retained and still reported**; the C60 verdict reads the consensus contrast.
      Without this, one failed oracle replicate drives C60 to `EXIT_UNAVAILABLE` — the oracle
      would break the *consensus* verdict without being its subject.
    - **The multiplicity cost, stated and not paid here.** `MetricContract.classify` is strictly
      two-sample and `decision_rule` is validated by string equality against
      `significant_and_favorable_and_meets_mde`, so two contrasts in one job is a multiplicity
      problem and any correction is a `metric_contract.yaml` version bump. AD-16 declines the
      correction and keeps the oracle contrast in its own job with its own artifact (task 16.7).
      The accepted tradeoff: **the oracle contrast's artifact is not admissible to C60**, which
      is correct, because C60's subject is consensus.
    - _Requirements: 6.14_

  - [ ] 15.6 Write property test for comparator resolution
    - `# Feature: decision-quality-proof, Property 62: A named comparator is never pooled, and an oracle-role arm is never absorbed`
    - File: `tests/uplift/test_named_comparator_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 6.14_

- [ ] 16. E3 — the negative control, the positive control, and the job that runs both
  - **This is the most important task in the spec.** It converts "we measured zero" from an
    ambiguous non-result into a finding, because the instrument is then known to have the power
    to see an effect of that size. Without it, E5's number is unfalsifiable (R6.7).
  - No spec in `.kiro/specs/` specifies a **positive** control — a grep for "positive control"
    across every spec document returns no match. The negative control is specified by
    `purpose-achievement-audit` R2.6 and has never run.
  - The Oracle_Arm needs **zero** model change beyond task 15.5:
    `assemble_uplift_result(..., consensus_arm="oracle", baseline_arm="Par_Level_Reorder")`
    already works, seeds derive from `(scenario.seed, index)`, and `arm_aggregates`,
    `UpliftProvenance.arms` and C60 are all arm-count agnostic.

  - [ ] 16.1 Implement the Oracle_Arm as the analytically optimal policy for the injected structure
    - File: `uplift/oracle_arm.py` (new)
    - Registers with `arm_role="oracle"`, so task 15.5's pooling refusal keeps it out of the
      baseline and a failed oracle replicate cannot mark the consensus contrast incomplete.
    - The "known-exploitable structure" is one of E2c's five (task 12/13), and the analytic
      optimum is stated **for that structure specifically** — an oracle whose optimum is not
      analytically derivable cannot support R6.3's tolerance comparison.
    - _Requirements: 6.2, 6.3_

  - [ ] 16.2 Commit the control policy values and pin them before any run judged against them
    - Files: `infrastructure/quality/uplift-controls.yaml` (new),
      `infrastructure/quality/ratchets.json`, `infrastructure/quality/doc-number-pins.yaml`
    - Values: the R6.3 oracle tolerance (which "does not yet exist and SHALL be committed as a
      pinned value before the run that is judged against it"), and the declared detection
      probability `0.80` — labelled in the file as what it is, a **pre-registered target carried
      from the blueprint, not a measurement**.
    - Each value gets a `ratchets.json` entry whose extractor is verified **by running it** (task
      8.3's registered check).
    - **Path note, surfaced rather than assumed:** the design's "New committed configuration
      files" list names `digital_twin/simulation/policy.yaml`,
      `infrastructure/data/dataset-licences.yaml` and `gate-mutations.yaml::sweep_budget` — it
      names **no** file for the control values. This path is this plan's choice; confirm it
      against AD-13's pin table at implementation time.
    - _Requirements: 6.3, 6.5_

  - [ ] 16.3 Amend ADR-055 to declare the repetition count and the rate tolerance R6.15 reads
    - File: `docs/adr/ADR-055-twin-decision-relevance.md`
    - R6.15 judges the proportion of negative-control repetitions reporting a proven gain against
      "the tolerance the Decision_Relevance_Record declares" for the contract's committed
      `alpha` of `0.05`, and against "the number of independent seed sets" that record declares.
      **Task 8.1's list of ADR-055 contents does not include either**, so R6.15 is unsatisfiable
      until this amendment lands. Recording the gap rather than discovering it inside E3.
    - The reason the repetition is needed at all: a single run classifies only four pairs
      (`primary_kpis: fill_rate` across four scenarios), and four pairs cannot estimate a rate.
    - _Requirements: 6.15_

  - [ ] 16.4 Implement control classification by interval position
    - File: `uplift/controls.py` (new)
    - Negative control: the interval **contains** zero. Positive control: the interval **lies
      entirely above** zero — not "excludes zero", which an interval entirely *below* zero also
      satisfies (R6.2's own wording correction). Out-of-tolerance oracle effect: reported as the
      harness **mis-measuring**, and the Oracle_Arm is **not** reported as under-performing
      (R6.4).
    - Both controls are invoked with exactly one named comparator via task 15.5's `ControlSpec`
      (R6.14).
    - _Requirements: 6.1, 6.2, 6.4, 6.14, 6.15_

  - [ ] 16.5 Write property test for control classification and the repetition rate
    - `# Feature: decision-quality-proof, Property 63: Controls classify by interval position, and the repetition rate matches the committed alpha`
    - File: `tests/uplift/test_control_classification_property.py`
    - `@pytest.mark.slow`. Selected by **`ci.yml::uplift-verify`'s slow step**, whose path list
      already collects `tests/uplift` and whose selector is `-m "slow"` at
      `HYPOTHESIS_PROFILE=heavy`. A slow-marked test outside that step's four paths is selected
      by no job at all.
    - Budget inherited from the profile; no `max_examples` literal.
    - _Requirements: 6.1, 6.2, 6.15_

  - [ ] 16.6 Write property test for the oracle tolerance verdict
    - `# Feature: decision-quality-proof, Property 64: An out-of-tolerance oracle effect is a mis-measurement, never under-performance`
    - File: `tests/uplift/test_oracle_tolerance_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 6.3, 6.4_

  - [ ] 16.7 Add the `uplift-controls` job and its declarations in one commit
    - Files: `.github/workflows/uplift.yml`,
      `infrastructure/quality/blocking-steps.yaml`,
      `infrastructure/quality/required-checks.yaml`
    - Its own job, separate from `uplift-proof` (whose 350-minute budget sits against a
      ~360-minute ceiling for 4 scenarios x 5 arms x 1000 replicates). Runs the negative control,
      the positive control and the power sweep at `MIN_POWERED_REPLICATES` per arm, each with its
      own artifact, so the two contrasts are never classified under one contract instance.
    - **Never on the dev box (R6.12).** `cli.py::build_arms` returns five arms; this is a
      category-4 workload under I-0 and Linux CI is the only locus.
    - **Same-commit declaration coupling.** The steps go into `blocking-steps.yaml` and the job
      name goes into `required-checks.yaml` under `ineligible` with reason `post-merge` — the
      same treatment R7.10 requires of `uplift-proof`, and for the same reason: `uplift.yml`
      carries only `schedule` and `workflow_dispatch`, so the job is **structurally ineligible**
      for `required:` (that file's eligibility rule admits only checks produced by every pull
      request to `main`). The declaration, not branch protection, is what makes the gap visible.
      `required_checks_truth` resolves declared job names against the workflow tree, so either
      half alone is a red gate.
    - _Requirements: 6.1, 6.2, 6.11, 6.12, 6.15_

- [ ] 17. E3 — the Power_Report, the floor's admission shape, and the C60 operator
  - `MIN_POWERED_REPLICATES = 1000` is **assumed** adequate until R6.5 measures otherwise (A-1);
    R6.9 and R6.10 state what happens if it is not.

  - [ ] 17.1 Implement the Power_Report as a generated, version-controlled artifact
    - File: `uplift/power.py` (new)
    - States, for the committed replicate count and the observed variance, the minimum effect
      size the harness detects at the declared detection probability (R6.5), and the detectable
      effect at the current `MIN_POWERED_REPLICATES` (R6.8). Its inputs name the run that
      produced it.
    - `kind` declares it **distinct from an uplift result artifact** (R6.6). This is not
      cosmetic: `artifact_is_version_controlled` refuses a committed result artifact, so without
      the distinction, committing the Power_Report trips that gate.
    - _Requirements: 6.5, 6.6, 6.8_

  - [ ] 17.2 Make the replicate floor a floor, and move its pin in the same change
    - Files: `uplift/uplift_floor.py`, `tests/uplift/test_uplift_floor_data_gate.py`
    - A derived requirement **greater than** `MIN_POWERED_REPLICATES` replaces that constant
      (R6.9). In the same change, convert
      `test_powered_replicate_floor_matches_inv_tw_002` from asserting
      `MIN_POWERED_REPLICATES == MIN_SCENARIOS` to asserting `>=`, so INV-TW-002 stays a floor
      rather than a fixed point (R6.10).
    - A derived requirement **below** `monte_carlo.py::MIN_SCENARIOS` records the INV-TW-002
      floor as **binding** rather than proposing a lower constant (R6.16) — a lower value breaks
      the hard guards at `uplift/harness.py:608-611` and `monte_carlo.py:123-127`.
    - _Requirements: 6.9, 6.10, 6.16_

  - [ ] 17.3 Refuse publication while no Power_Report describes the revision under measurement
    - File: `scripts/audit/uplift_truth.py`
    - An unpowered null is not evidence of absence, and a Power_Report describing a **superseded**
      revision does not license publication (R6.7). This is the constraint that makes E5's
      publication step conditional rather than scheduled.
    - _Requirements: 6.7_

  - [ ] 17.4 Write property test for the Power_Report's contract
    - `# Feature: decision-quality-proof, Property 65: The Power_Report is monotone, distinct in kind, revision-bound and floor-respecting`
    - File: `tests/uplift/test_power_report_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 6.5, 6.6, 6.7, 6.8, 6.9, 6.16_

  - [ ] 17.5 Make the ratchet read the interval's lower bound
    - Files: `uplift/uplift_floor.py`,
      `tests/uplift/test_uplift_floor_monotonic_ratchet_property.py`
    - `PoweredProof.from_payload` reads `headline_uplift`, `incomplete`, a top-level
      `replicates_per_arm` and `fidelity.within_fidelity_bound` today. Extend it to carry the
      interval and make `ratchet_to_measured` admit `interval.low`, **never the point estimate**
      — a floor ratcheted to a point estimate is a floor half the runs at that effect size will
      fail. AD-15 names this as the admission predicate's change of shape, so the ratchet
      property moves in the same commit.
    - `FloorRatchetError` on any lowering is **already enforced** and pinned; nothing here
      relaxes it (R7.13 is a regression pin, not work).
    - _Requirements: 7.12_

  - [ ] 17.6 Write property test for the ratchet's source value
    - `# Feature: decision-quality-proof, Property 66: The floor ratchets to the interval's lower bound, never the point estimate`
    - File: `tests/uplift/test_ratchet_lower_bound_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 7.12_

  - [ ] 17.7 Report a proof older than the code it measured, on the pull request that ages it
    - Files: `scripts/audit/uplift_staleness_truth.py` (new),
      `scripts/audit/verify_claims.py` (`@register`), `.github/workflows/ci.yml`
    - A pull request touching `uplift/`, `scripts/audit/uplift_truth.py` or
      `.github/workflows/uplift.yml` reports whether the most recent recorded powered run
      **predates** the change, so a stale proof cannot silently outlive the code it measured.
    - The step goes in `ci.yml::uplift-verify` deliberately: that job is already declared
      **required** and its `pull_request` trigger carries no path filter, so the report reaches
      every pull request. `ci.yml`'s `on.push` `paths-ignore` does not matter here — the
      obligation is stated on the pull request.
    - _Requirements: 7.16_

  - [ ] 17.8 Write property test for staleness reporting
    - `# Feature: decision-quality-proof, Property 67: A recorded proof older than the code it measured is reported stale`
    - File: `tests/verify/test_uplift_proof_staleness_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 7.16_

  - [ ] 17.9 Declare the `is_proven_uplift` operator and probe it inside the generating job
    - Files: `infrastructure/quality/gate-mutations.yaml`,
      `.github/workflows/uplift.yml`,
      `infrastructure/quality/blocking-steps.yaml`
    - **The first half deliberately deferred this** (task 5.6's closing note). `gate-mutations.yaml::C60`
      declares exactly **one** operator, `untrack-the-evidence-path`; no `is_proven_uplift`
      mutation exists anywhere in the tree, so R7.8 is genuinely unmet.
    - Add the operator, and add a `python -m scripts.audit.gate_fault_injection --gate C60
      --check` step **inside `uplift.yml::uplift-proof`**, because `gate-mutations.yaml` records
      that C60's falsification "moves to the generating job" — the only context in which C60 can
      pass and therefore the only one in which it can be falsified. Declare the step in
      `blocking-steps.yaml` in the same commit.
    - **Read the outcome correctly before E5 lands.** R7.7's precondition is an *admitted,
      passing* artifact, and `False` is the realisable direction — stubbing to `True` cannot
      change an exit code that is already `EXIT_PASS`. Until task 22.1's powered run produces
      that artifact, this probe reports **`indeterminate` naming the non-passing baseline**, which
      is honest and non-passing. It flips to `falsified` in E5, and task 22.1 must not remove the
      step it inherits.
    - _Requirements: 7.8, 7.9_

### Phase 4 — E4: train, benchmark, publish (R8.5-R8.15, R8.18, R9)

E4 runs **in parallel with E3**, gated on E4a (task 7) and completing before E5. Dependency-order
item 4 binds inside it: **R8 precedes R9** — a checkpoint published before it is trained on real
data and scored against an external benchmark has no demonstrable value.

- [ ] 18. E4 — the held-out block, and the recompute that finally has an input
  - Implements **AD-19**. The sharpest finding in R9: **the registered check returns PASS with no
    recompute.** C46 calls `published_checkpoint_truth.evaluate`, not `assess`, and `evaluate`
    ends `if crps.outcome is Outcome.FAIL: return fail` then `return ok` — so
    `Outcome.UNAVAILABLE` **falls through to `ok`**. `evaluate` also never calls `validate_entry`,
    so an entry with no `final_crps` yields `recorded=None` -> `UNAVAILABLE` -> PASS.
  - `UNAVAILABLE` is the outcome for a sidecar carrying no `heldout` block — **which is every
    artifact today's `train.py` produces**. So the hole is not hypothetical; it is the live state.
  - **The fourth state is the whole fix.** `PublishProbe.status` is `"ok" | "fail" | "skip"`; a
    three-valued vocabulary cannot distinguish "nothing was recomputed" from "the subject is
    absent", and `evaluate` resolves that ambiguity in the direction I-7 forbids.

  - [ ] 18.1 Write the held-out block into the published sidecar and declare its shape
    - Files: `agents/demand_prophet/training/train.py`,
      `infrastructure/quality/checkpoint-truth.yaml`
    - `train.py` writes a sidecar of exactly `version`, `smoke`, `arch`, `calibrator` — **no
      `heldout` block** — so *neither* recompute has an input. Add `HeldoutBlock`: per-horizon
      predictions, actuals, and the **conformal-adjusted** `lower_90`/`upper_90` bounds, plus the
      committed minimum row count in `checkpoint-truth.yaml`.
    - The adjustment matters: the declared `quantile_levels: [0.1, 0.5, 0.9]` describe an **80%**
      raw-quantile band, not the conformal-adjusted 90% band INV-DP-002 is about
      (`agents/demand_prophet/spec.yaml:25-27`, `empirical_coverage(...) >= 0.85`, severity
      critical).
    - _Requirements: 9.13_

  - [ ] 18.2 Recompute coverage rather than reading it
    - File: `scripts/audit/published_checkpoint_truth.py`
    - `recompute_coverage_p90(sidecar, floor)` computes empirical coverage from the published
      held-out actuals against the published conformal-adjusted bounds over at least the
      committed minimum row count, returning `UNAVAILABLE` when the block is absent or shorter
      than that minimum. Below `0.85` exits non-zero reporting the measured value and the floor.
    - `compare_coverage`'s existing read of `calibrator.last_coverage_p90` via `_read_dotted` at
      `checkpoint-truth.yaml::floors.coverage_p90.sidecar_path` is **retained as a cross-check**;
      the recompute is the verdict. A recorded number nobody recomputed is not evidence.
    - _Requirements: 8.9, 8.10, 9.8, 9.14_

  - [ ] 18.3 Re-point C46 at `assess`, and move its pinning test in the same commit
    - Files: `scripts/audit/verify_claims.py`,
      `tests/verify/test_published_checkpoint_gate_property.py`
    - `assess` returns a four-valued `Outcome` with findings that name their clause and
      requirement. Status map `{PASS: "pass", FAIL: "fail", SKIP: "skip", UNAVAILABLE:
      "unavailable"}` into `GATE_STATUS`, where `"unavailable"` maps to **SKIP** — non-passing,
      excluded from the published PASS count, never a pass (I-7).
    - **The cost, stated.** `assess` is strictly stricter: it refuses an `indeterminate`
      artifact, folds a smoke *version prefix* into the smoke rule where `evaluate` uses the
      sidecar flag alone, and adds the two policy-pin clauses (`source.zero_cost` true,
      `source.allow_local_substitution` false). The test that pins `evaluate` must be re-pointed
      in the same commit, and C46's row will read differently from its long-pinned form. That is
      intended: the current row is `DP_HF_REPO unset - no published model claimed (operator
      step)` and is a **SKIP**, so re-pointing cannot lose a real PASS.
    - **`evaluate` is retained, not deleted** — it is the legacy triad's surface and static
      reading did not enumerate its callers.
    - _Requirements: 9.14_

  - [ ] 18.4 Write property test for recompute-or-unavailable
    - `# Feature: decision-quality-proof, Property 71: A recorded number is recomputed or reported unavailable, never ok`
    - File: `tests/verify/test_recompute_or_unavailable_property.py`
    - The load-bearing clause is the negative one: **no** observation reaches `ok` through an
      `UNAVAILABLE` outcome.
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 8.9, 8.10, 9.8, 9.13, 9.14_

  - [ ] 18.5 Write property test for the smoke-versus-absent distinction
    - `# Feature: decision-quality-proof, Property 72: A smoke artifact is distinguished from an absent one and never substituted locally`
    - File: `tests/verify/test_smoke_artifact_distinction_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 9.2, 9.5, 9.7, 9.11_

  - [ ] 18.6 Correct the runbook's gate identifier and add the publication step the recompute needs
    - Files: `docs/runbooks/train-and-publish-checkpoint.md`,
      `scripts/audit/published_checkpoint_truth.py` (docstring citations only)
    - The runbook calls this gate **C43** in five places (`:5`, `:58`, `:59`, `:62`, `:75`); it is
      **C46**. C43 is "All 8 agents expose POST /a2a for consensus". `verify_claims.py`'s C46
      docstring records a SKIP branch that previously mis-stamped itself `C43`, so an unavailable
      probe landed on another check's row — the runbook is the surviving copy of that error.
      **Correct the runbook, not the spec.**
    - Runbook step 5 currently reads only "Upload both files to HF Hub (checkpoint + serving
      sidecar)" and says nothing about a held-out block, while `checkpoint-truth.yaml:125-126`
      asserts that publishing the block *is* step 5. Add the step, so R9.13 stops being
      unavailable by construction.
    - Also correct the two docstring citations of `verify_claims.py:1151` (`:54`, `:1472`); the
      `@register("C46", ...)` call is at **`:1251`**.
    - _Requirements: 9.13_

- [ ] 19. E4 — the feed record reconciled, and the external benchmark made honest
  - **Path reconciliation, owed and stated.** Task 7 committed E4a's artifacts at paths derived
    from neighbouring naming convention, with an explicit note to "correct without ceremony if
    they differ". They differ. The design names `infrastructure/data/dataset-licences.yaml` (+
    schema), `data_fabric/licence.py::DatasetLicence`, `data_fabric/ingest/m5.py::M5IngestRecord`
    and `scripts/audit/dataset_licence_truth.py`. Properties 68 and 69 are authored against the
    design's names, so the reconciliation happens here, before them.

  - [ ] 19.1 Reconcile E4a's artifacts onto the design's committed names
    - Files: `data_fabric/licence.py` (new, `DatasetLicence`),
      `infrastructure/data/dataset-licences.yaml` (+ `infrastructure/data/schemas/`),
      `data_fabric/ingest/m5.py` (new, `M5IngestRecord`),
      `scripts/audit/dataset_licence_truth.py` (new),
      `scripts/audit/verify_claims.py` (the `@register` entry moves with the module),
      and the task 7 originals (`infrastructure/quality/feed-licence.yaml`,
      `scripts/audit/feed_licence_truth.py`, `data_fabric/etl/m5_ingest.py`,
      `data_fabric/etl/m5_statistics.py`, `tests/verify/test_feed_licence_admission.py`)
    - One move, not two implementations. The licence artifact keeps every field task 7.1
      committed (dataset identity, licence identifier, licence-text URI, read date, permitted
      use, dataset revision) and stays schema-validated with **every absent field named rather
      than defaulted**, so a missing term cannot read as a permissive one.
    - The ingestion record keeps `M5IngestRecord`'s dataset identity, dataset revision and rows
      consumed (`rows` is already a required registry key), and keeps task 7.3's straddle note:
      the training-row path and the `ExternalFeedSource` world seam are **two unrelated ingestion
      paths**, and only the world seam carries `source_class`.
    - `source_class` reports `EXTERNAL` when the real feed drives the twin (R8.3). **Do not add a
      fourth `SourceProvenance` value** — the three are pinned by
      `orchestrator.audit.models.SOURCE_CLASSES` and a SQL `CHECK` in
      `0007_decision_data_provenance.sql` — and **do not** add a fourth
      `Provenance.feature_source`, which `scripts/audit/runtime_substance.py:172` pins to
      `FEAST`.
    - _Requirements: 8.1, 8.2, 8.3, 8.16, 8.17_

  - [ ] 19.2 Write property test for licence schema totality
    - `# Feature: decision-quality-proof, Property 68: The licence artifact is schema-total and every absent field is named`
    - File: `tests/verify/test_dataset_licence_totality_property.py`
    - Closes the gap task 7.5 recorded deliberately: E4a shipped with unit tests and owed this
      property to E4's numbering block.
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 8.1, 8.2_

  - [ ] 19.3 Write property test for provenanced ingestion
    - `# Feature: decision-quality-proof, Property 69: Real-feed ingestion is provenanced and records what it consumed`
    - File: `tests/verify/test_real_feed_ingestion_provenance_property.py`
    - `@pytest.mark.slow`; selected by `ci.yml::uplift-verify`'s slow step (`-m "slow"`,
      `HYPOTHESIS_PROFILE=heavy`, `tests/verify` in that step's path list).
    - Budget inherited from the profile.
    - The predecessor's Property 29 currently passes **over a stub** —
      `ExternalFeedSource.poll_arrivals` returns `[]` — so this property must be authored against
      a source that actually yields rows, or it inherits the same vacuity.
    - _Requirements: 8.3, 8.17_

  - [ ] 19.4 Record the benchmark score with its metric identity and a non-bare baseline
    - Files: `scripts/audit/benchmark_truth.py` (new, `BenchmarkRecord`),
      `scripts/audit/verify_claims.py` (`@register`)
    - The record carries the score, **the identifier of the metric scored**, and **the identifier
      of the published document that defines that metric** — "the Uncertainty-track metric" names
      no single computable quantity on its own; that track scores quantiles, which maps onto this
      agent's pinball/CRPS objective and its conformal intervals (R8.5).
    - The published baseline is either a **confirmed value with its source and read date** or an
      **explicitly unconfirmed entry**. A bare number satisfies R8.6 while violating R8.8, so the
      schema admits no bare number (R8.6, R8.7).
    - A differing split, aggregation level or metric definition makes the result **not
      leaderboard-comparable** rather than a rank (R8.18).
    - _Requirements: 8.5, 8.6, 8.7, 8.18_

  - [ ] 19.5 Generate the benchmark document rather than transcribing it
    - Files: `scripts/audit/benchmark_gen.py` (new),
      `docs/benchmarks/m5-uncertainty.md` (new, with one generated region)
    - Renders the region from `BenchmarkRecord`, reusing task 4.2's marker helpers
      (`GENERATED_BEGIN`/`GENERATED_END` and `generated_region_bounds`) — one mechanism, not a
      second. `--check` is the default and diffs at exit 1; `--write` never creates the document;
      every byte outside the region survives.
    - An **unconfirmed** baseline is never rendered as fact (R8.8), the domain gap between daily
      retail demand and 10-minute quick-commerce demand accompanies every feed-derived claim
      (R8.12), and the two are described as **distinct domains** in every document reporting a
      feed-derived score (R8.13).
    - _Requirements: 8.8, 8.12, 8.13_

  - [ ] 19.6 Commit the expected-outcome record at an ancestor revision, and check the ancestry
    - Files: `infrastructure/quality/benchmark-expectations.yaml` (new),
      `scripts/audit/benchmark_truth.py`
    - States that a sophisticated model is expected to be **competitive rather than dominant on
      point accuracy**, and the check confirms the record's revision is an **ancestor** of the
      scoring run's revision. Both halves matter: the ancestry stops the result being
      rationalised after the fact, and requiring the record at all stops the criterion being
      satisfied by never recording a prediction.
    - _Requirements: 8.14_

  - [ ] 19.7 Commit the execution-environment run record and pin the zero-cost claim
    - Files: `infrastructure/ml/training_runs.json` (new, beside `published_checkpoints.json`),
      `scripts/audit/benchmark_truth.py`
    - Records where training and scoring executed: either the CI pipeline or external GPU
      capacity requiring **no billable account, no trial linked to a billing account, and no
      purchased or granted credits** — "free" without those exclusions admits a paid tier
      (R8.15). Model training is a category-4 workload under I-0 and never runs on the dev box.
    - The I-1 clause (R8.11) is checked where it is already enforced: no paid API, SDK,
      dependency or host is introduced, and CI already blocks the named packages. This task adds
      no new dependency; it asserts and records that.
    - _Requirements: 8.11, 8.15_

  - [ ] 19.8 Write property test for benchmark-record honesty
    - `# Feature: decision-quality-proof, Property 73: An unconfirmed external value is never rendered as fact, and a differing definition is not comparable`
    - File: `tests/verify/test_benchmark_record_honesty_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 8.5, 8.6, 8.7, 8.8, 8.12, 8.13, 8.15, 8.18_

- [ ] 20. E4 — publication, the confidence contract, and the gates it actually flips
  - **The count correction that prevents a wasted pass.** Finding 2's "five gates" is the number
    the *absent* artifact collapses, not the number publication repairs. C38
    (`checkpoint_truth.ARTIFACTS_DIR = artifacts/training`), C40 (`calibration_truth.ARTIFACTS_DIR`,
    same path) and C45 (`runtime_substance.CHECKPOINT_DIR = artifacts/checkpoints`) all read
    **local** files, and C45's per-agent probe tests `ckpt.is_file()` (`:129`) **before**
    importing or constructing `ModelRegistry` (`:132`, `:154`), so it skips before any download
    could occur. Publishing to the remote source flips only **C46** and **C69**. R9.15 carries
    the difference and task 20.4 discharges it.

  - [ ] 20.1 Make degradation the exact three-term disjunction, and make confidence move
    - Files: `agents/demand_prophet/inference/pipeline.py`,
      `scripts/audit/runtime_substance.py`
    - The live expression is
      `degraded = self._model_degraded or self._feature_source == FeatureSource.FALLBACK or not
      has_intervals` (`pipeline.py:282-285`), pinned by
      `agents/demand_prophet/tests/test_pipeline_contract.py:80-85`. A resolved checkpoint alone
      is **not** sufficient for `degraded` false, and `degraded` must be **true** whenever any of
      the three terms holds (R9.9 is a tightening in the I-7-safe direction).
    - `runtime_substance.py:177` fails only when `all(c == FALLBACK_CONFIDENCE for c in confs)`,
      so three SKUs all returning the same `0.7231` pass it. Strengthen it to require **at least
      two distinct confidence values at the four decimal places served, over at least three SKUs
      carrying distinct feature vectors** — a confidence that does not move across SKUs disables
      the I-5 HITL gate entirely.
    - `confidence_basis` stays a real derivation and **never `constant`**
      (`packages/synapse_common/provenance.py:14-15`). Nothing here relaxes it.
    - _Requirements: 8.4, 9.3, 9.4, 9.9_

  - [ ] 20.2 Write property test for the degradation disjunction and confidence spread
    - `# Feature: decision-quality-proof, Property 70: Degradation is exactly the three-term disjunction, and confidence moves across SKUs`
    - File: `tests/verify/test_degradation_disjunction_property.py`
    - "Exactly" is both directions: no term is dropped, and no fourth condition is smuggled in.
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 8.4, 9.3, 9.4, 9.9_

  - [ ] 20.3 Land the registry entry, and keep both substitution pins where they are
    - Files: `infrastructure/ml/published_checkpoints.json`,
      `infrastructure/quality/checkpoint-truth.yaml`
    - The entry records the sha the resolved version string must contain (R9.2) and the
      `final_crps` the recompute checks (R9.8). A recorded sha that cannot be fetched from the
      declared zero-cost serving source exits non-zero and **does not resolve a locally built
      checkpoint in its place** (R9.7) — `ModelRegistry._resolve_checkpoint_path` prefers the
      local file over the remote (`checkpoint-truth.yaml:38-39`) and the CI smoke job writes one
      into `local_candidate_dir: artifacts/checkpoints` (`:57`), so a gate resolving through
      `ModelRegistry` would certify a **smoke** artifact as the published model.
    - `allow_local_substitution` stays `false` (R9.6) — its own comment says the flag "exists to
      be pinned, not to be flipped". A smoke artifact's detail is distinguished from an absent
      one's (R9.5).
    - _Requirements: 9.1, 9.2, 9.5, 9.6, 9.7, 9.11_

  - [ ] 20.4 Materialise the published artifact for the three local-reading gates
    - Files: `.github/workflows/ci.yml`,
      `infrastructure/quality/blocking-steps.yaml`,
      `infrastructure/quality/required-checks.yaml`
    - A job required to report C38, C40 or C45 against a published checkpoint **first
      materialises** the published checkpoint and its sidecar at the serving checkpoint path
      those checks read. Without this step the three stay SKIPped after publication, and a SKIP
      read as a flip would over-claim.
    - Same-commit declaration coupling: steps into `blocking-steps.yaml`, job name into
      `required-checks.yaml`, in the same commit as the job.
    - _Requirements: 9.15_

  - [ ] 20.5 Make the task-completion check read the registry it is told about
    - File: `scripts/audit/task_claim_truth.py`
    - A task record asserting a landed Published_Checkpoint_Registry entry causes the check to
      read `infrastructure/ml/published_checkpoints.json`; if that file holds no validated
      non-placeholder entry, the check **fails naming the task record**. A task record is a claim,
      and an unchecked claim is how this project acquired the findings this spec exists to fix.
    - _Requirements: 9.10_

  - [ ] 20.6 Write property test for task-record claims against the registry
    - `# Feature: decision-quality-proof, Property 74: A task record asserting a landed registry entry fails when the registry holds none`
    - File: `tests/verify/test_task_claim_registry_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 9.10_

  - [ ] 20.7 Render degradation on every surface that shows the agent's output
    - Files: `frontend/src/surfaces/` (the surfaces displaying Demand_Forecaster output)
    - What the console draws is a different subject from what the agent reports, which is why
      R9.16 is separate from R9.9 and separately testable. Every surface, not the primary one.
    - _Requirements: 9.16_

  - [ ] 20.8 Extend the console degradation property to every surface
    - `# Feature: decision-quality-proof, Property 75: The console renders degradation on every surface displaying the agent's output`
    - File: `frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts` (extended,
      not new — task 1.1 commits this file and task 1.3 strips its per-call `numRuns`)
    - Budget inherited from `fc.configureGlobal` in `frontend/src/test/setup.ts` (task 1.2).
      **No per-call `numRuns` may be reintroduced here** — that would silently override the
      global for the whole file and undo 1.3.
    - Locus: `frontend.yml::quality`.
    - _Requirements: 9.16_

- [ ] 21. Checkpoint — is the confidence contract actually live?
  - discharge: CI, the E4 materialisation job (named at task 20.4)
  - Ensure all tests pass, ask the user if questions arise.
  - **This is a state check with three observable conditions, not a status report.** E4 is
    complete only when all three hold on a CI run, each read from the run's own output:
    1. **A real checkpoint resolves through the production serving path**, and the returned
       version string contains the sha recorded in `infrastructure/ml/published_checkpoints.json`
       (R9.1, R9.2). Resolved through the serving path, not located on disk.
    2. **`degraded` is false** on a forecast produced from Real_Data_Feed features, with the
       feature source not `FALLBACK` and conformal intervals present (R8.4, R9.3). All three
       terms, because that is what the expression says.
    3. **Confidence varies across SKUs** — at least two distinct values at four decimal places
       over at least three SKUs with distinct feature vectors (R9.4). A constant confidence above
       the HITL threshold makes I-5 inoperative, so this is the condition that decides whether
       the confidence contract means anything.
  - Also confirm before proceeding: C46 reports a status **derived from the fetched artifact and
    the committed record**, not the `DP_HF_REPO unset` SKIP (R9.11); the coverage recompute ran
    and did not report `unavailable` (R9.14); C38, C40 and C45 read a materialised artifact
    rather than skipping (R9.15); and the benchmark document carries no unconfirmed value
    rendered as fact (R8.8).
  - **A `SKIP` here is not a pass.** If the recompute is unavailable, or the checkpoint resolves
    but confidence is flat, report that plainly and repair it before E5. E5's headline number is
    only as good as the model behind it.

### Phase 5 — E5: measured uplift, the ratchet, and the external anchor (R7, R10)

- [ ] 22. E5 — run the powered experiment in the evaluating job, then ratchet the floor
  - `uplift_truth.py:494` already derives `EXIT_PASS` from `is_proven_uplift`, `:566` already
    routes a floor raise through `ratchet_to_measured`, `admit()` (`:382`) already rejects an
    inadmissible artifact, and `artifact_is_version_controlled` (`:187`) exists with `artifacts/`
    absent from both the tree and `git ls-files`. **The predicate is reachable and the
    measurement has never been taken.** C60's ledger row reads `SKIP — no uplift run was
    performed in this job`.
  - **Eight of R7's criteria are regression pins, not work,** and are named here so nobody
    implements them twice: R7.3-R7.6 are covered by the `_inadmissible` strategy in
    `tests/uplift/test_uplift_admissibility_property.py`; R7.7 by
    `test_substituting_the_proven_uplift_predicate_changes_the_exit_code`; R7.11 by predecessor
    Property 13; R7.13 by `test_uplift_floor_is_a_monotonic_data_gated_ratchet` and
    `test_declared_floor_holds_under_the_data_gate`; R7.18 by
    `tests/uplift/test_headline_fidelity_colocation_property.py`. Every one must still pass.

  - [ ] 22.1 Regenerate the artifact in the generating job and co-locate the interval
    - File: `.github/workflows/uplift.yml`
    - `uplift-proof` runs the harness to regenerate the artifact in the **same** job that
      evaluates the gate (R7.1). The reason the obligation is scoped to that job and not to every
      pull request: C60 is also evaluated by `verify_claims` with `generating_job=False`, and
      obliging that path to run the harness would make every pull request a category-4 workload,
      contradicting I-0 and AD-9.
    - The reported headline carries its **interval at `1 - alpha`** (R7.14) alongside its
      replicate count per arm and its Fidelity_Report (R7.18) in the same output.
    - A harness that **fails to start, exits non-zero, exceeds the job's wall-clock bound, or
      produces no artifact at the declared path** records a non-passing result **naming which of
      those four states occurred** (R7.2). Four states, four distinct messages — "the run failed"
      is not one of them.
    - Preserve task 17.9's `--gate C60` step. With an admitted passing artifact present, its
      outcome moves from `indeterminate` to `falsified`; that transition is the evidence R7.9
      asks for.
    - _Requirements: 7.1, 7.2, 7.14, 7.18_

  - [ ] 22.2 Declare the job that is the only place C60 can pass
    - Files: `infrastructure/quality/blocking-steps.yaml`,
      `infrastructure/quality/required-checks.yaml`
    - `uplift.yml` appears in **neither** file today, and the omission is **invisible**:
      `required_checks_truth.RULES` has no completeness rule, so nothing fails for an unmentioned
      workflow. The workflow's header promises "No `|| true`, no `|| echo`, no `; exit 0`, no
      `continue-on-error`" as prose no gate reads, and `blocking-steps.yaml`'s own note records
      that the advisory-name rule "is evadable by renaming the step" while a declaration is not
      (R7.15).
    - The `required-checks.yaml` entry goes under `ineligible` with reason **`post-merge`** —
      `uplift-proof` is structurally ineligible for `required:`, not merely undeclared, because
      that file's eligibility rule admits only checks produced by every pull request to `main`
      while `uplift.yml` carries only `schedule` and `workflow_dispatch`. `ineligible[].reason` is
      a closed six-value enum and `post-merge` already fits it (the `deploy-to-vm` precedent), so
      no schema change is needed. **R7.10's stated purpose is unreachable via branch protection;
      the declaration is what makes the gap visible** (R7.10).
    - Same commit as any step name it declares — `required_checks_truth` resolves declared names
      against the workflow tree, and either half alone is a red gate.
    - _Requirements: 7.10, 7.15_

  - [ ] 22.3 Ratchet `UPLIFT_FLOOR` to the measured lower bound, and move its pin with it
    - discharge: uplift.yml::uplift-proof
    - Files: `uplift/uplift_floor.py`,
      `infrastructure/quality/ratchets.json`,
      `infrastructure/quality/doc-number-pins.yaml`
    - `uplift/uplift_floor.py:47` is `UPLIFT_FLOOR: float = 0.0`, and its docstring is honest
      about why: "before the harness has produced and committed a verified positive result, the
      honest floor is 'no proven uplift yet'". `gate-mutations.yaml` records that a complete
      powered in-bound run measuring `0.0` against a floor of `0.0` is **exit 2, not a pass**.
    - The raise is admitted **only** through `ratchet_to_measured` against a `PoweredProof` built
      from an artifact regenerated in the same job (R7.12), and takes `interval.low` per task
      17.5 — never the point estimate. Any proposed value below the committed one is rejected;
      the floor is a monotonic ratchet (R7.13, already enforced).
    - The `ratchets.json` entry and the `doc-number-pins.yaml` pin move **with the value or not
      at all**, and the pin's extractor is verified by running it (task 8.3).
    - **This sub-task runs only if the measurement supports it.** A null or negative headline
      leaves the floor at `0.0` and is reported as such. See task 25.
    - _Requirements: 7.12, 7.13_

- [ ] 23. E5 — ADR-056, the log coordinate, the export, and the same-run publication
  - Implements **AD-20**. C67's ledger row: `SKIP — chain=unverifiable, 0 anchor file(s)`.
    `infrastructure/audit_anchors` does not exist anywhere in the tree, and **it will read SKIP on
    Linux CI too** — this is not another C44 (A-3). Do not spend a debugging pass expecting it to
    flip by changing platform.
  - **R10 carries a deploy precondition no other requirement has.** `anchor_today` returns
    `EXIT_UNAVAILABLE` when the chain holds no row with a non-null `current_hash`, and
    `publish-audit-anchor.yml` skips the anchor step entirely when `SYNAPSE_AUDIT_DSN` is unset
    (`:80-84`). R10 needs a reachable audit database holding at least one hashed consensus row;
    it cannot be validated by landing it in CI the way R1-R4 can.
  - **Three non-goals bind this task.** Do not build or operate a transparency log — a log this
    project runs is a log this project can rewrite. Do not introduce key material; the precedent
    is keyless workflow-identity signing (`cd.yml:86-94`, `id-token: write` plus GitHub OIDC). Do
    not extend the guarantee past the anchored head; `scope_to_anchor` excludes later appends
    deliberately.

  - [ ] 23.1 Write ADR-056 superseding ADR-033, before any anchor is published
    - Files: `docs/adr/ADR-056-external-audit-anchor.md` (new),
      `docs/adr/ADR-033-audit-chain.md` (superseded header only)
    - **OQ-4 is an ADR-level conflict, not a naming slip.** The mechanism is named three times
      and the three disagree: ADR-033 (`:38-42`) decides on a public **GitHub Releases** artifact;
      `publish-audit-anchor.yml` is titled and built for **Rekor** (keyless `cosign sign-blob`
      against public Sigstore); `docs/state/CURRENT.md:167` (C25) records **Rekor and
      OpenTimestamps as unimplemented candidates** with the row **PARTIAL**.
    - **I-1 is not the unresolved point.** Rekor introduces no paid dependency and no new
      dependency class — ADR-033's rejection is of a *notary timestamping service* that "costs
      money", which does not reach a free transparency log, and this repository already depends on
      public Sigstore for image signing (`cd.yml:86-94`, `cd-gcp.yml:200-207`). The unresolved
      point is the **un-superseded ADR**.
    - **The field is narrower than OQ-4's three candidates.** GitHub Releases fails R10.1's
      independent-timestamp clause: a release asset carries no timestamp the log itself asserts,
      and it can be deleted or replaced, so it satisfies neither "appends entries without
      permitting their removal or modification" nor "returns an entry timestamp the log itself
      asserts rather than one the publisher supplies". That leaves **Rekor or OpenTimestamps**.
      ADR-056 records the choice, the R10.6 zero-cost argument at one anchor per UTC day, and the
      supersession — **before the first publication**, which is task 23.10.
    - ADR-054 is the highest committed and ADR-055 is claimed by the Decision_Relevance_Record, so
      056 is the next free identifier.
    - _Requirements: 10.1, 10.6_

  - [ ] 23.2 Record the log coordinate on `AnchorRecord`, nullably
    - File: `orchestrator/audit/anchorer.py`
    - Add `log_entry_id: str | None` and `log_inclusion_proof: str | None`. **Both nullable, and
      the nullability is a requirement rather than a convenience:** `AnchorRecord.from_payload`
      must keep reading anchors published before the fields existed, because refusing to read an
      older anchor would destroy evidence.
    - The anchor commits to the `current_hash` of the last row with a **non-null** `current_hash`
      in canonical walk order, and records the instant (R10.2). That definition is pinned in three
      places that already agree — `anchorer.py:24`, `anchorer.select_head` (`:355`) and
      `packages/tests/strategies_audit.py::head_hash` (`:279-280`) — so a trailing run of legacy
      null-hash rows (E-S9-01) does not move it. **Do not redefine the head as "final position":**
      `scope_to_anchor` would then report `reachable=True` on a truncated presentation, R10.3
      would be voided, and nothing would fail (`chain_walk.py` convention 5).
    - `make_canonical_row` is **untouched** and its literal-digest test
      (`packages/tests/test_audit_chain.py`) is unchanged — the anchor commits to `head_hash` only
      and is a file, not a row, so the anchoring path needs no row change at all (I-4, E-S9-02,
      R10.7). E-S9-03's compact canonical bytes with no trailing newline
      (`anchorer.py:219-220`) are preserved, because that is what makes two anchors of the same
      head byte-identical and a signature cover a deterministic blob.
    - **Unverified, and stated as such:** whether `cosign sign-blob` as invoked
      (`--yes --output-signature --output-certificate`, cosign v2.4.0) already uploads to Rekor,
      and whether a `--bundle` output is required to capture the inclusion proof, are properties
      of an external tool. Confirm against the pinned cosign release; do not assume either way.
    - _Requirements: 10.2, 10.7, 10.8_

  - [ ] 23.3 Add the external-entry freshness rule, preserving the fail-versus-unavailable split
    - File: `scripts/audit/anchor_truth.py`
    - No entry identifier and no inclusion proof after the publisher's declared retry budget is
      exhausted -> **unavailable naming the log and the failure reason**, never a pass (R10.4).
      Retries come from `synapse_common.retry` (jittered), not a hand-rolled loop.
    - Newest external entry older than
      `audit-chain-bounds.yaml::anchor_freshness.max_age_hours` (a committed `48`) ->
      **unavailable naming the entry age and the bound** (R10.5). The bound is **read**, not
      inlined: `load_anchor_settings` raises `SettingsUnavailableError` rather than defaulting.
    - **The rule split is deliberate and "exit non-zero" is too loose:** `no-anchor` and
      `stale-anchor` map to exit 2 (`unavailable`); `unreadable-anchor`, `non-canonical-anchor`
      and `anchor-dir-drift` map to exit 1 (`fail`) — the module's own table (`:25-29`) and
      `_EXIT_CODES` (`:91`) agree, and `:35` gives the reason: "we are not anchored" and "the
      anchor we have is broken" are two different repairs.
    - This scope is the **external** entry only; the local half is `purpose-achievement-audit`
      R6.11. Also drop the stale docstring line at `:6` claiming the daily anchor "had no
      scheduled caller" — that caller landed in `publish-audit-anchor.yml`.
    - **Preserve the reporting vocabulary.** `AnchorTruthReport.chain_status` is
      `Literal["anchored", "unverifiable"]` and **neither value is `verified`** (`:204`); a PASS
      means a fresh commitment exists to walk against, never that the chain is intact.
    - _Requirements: 10.4, 10.5_

  - [ ] 23.4 Write property test for external anchor freshness
    - `# Feature: decision-quality-proof, Property 78: External anchor freshness is unavailable on absence and on staleness, and a back-dated anchor is non-passing`
    - File: `tests/verify/test_external_anchor_freshness_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 10.4, 10.5, 10.10_

  - [ ] 23.5 Add the chain presentation a third party can actually be handed
    - File: `orchestrator/audit/presentation.py` (new)
    - `ChainPresentation` carries the exported snapshot in canonical walk order with the linkage
      hashes **and** the hashed content fields, plus the committed migration boundary
      (`audit-chain-bounds.yaml`, `2026-05-24T11:32:51Z`, `:31`), the walk bounds
      (`max_rows: 5000000`, `max_wall_clock_seconds: 900`, `:70-71`) and the hash-construction
      rule including the canonical-JSON settings and the genesis prev-hash convention.
      `ExternalLogEntry` carries the log's own entry id, timestamp and inclusion proof — **the
      timestamp the log asserts, not the publisher's**, because `AnchorRecord.anchored_at` is
      written by the publisher (`:207`) and a self-asserted timestamp does not support the
      freshness half of the claim.
    - **Why content fields and not just hashes:** a presentation carrying only
      `prev_hash`/`current_hash` lets a verifier check `LINKAGE` and `HEAD_UNREACHABLE` and
      **not** whether a row's content was altered, which is most of what R10 is for.
    - **One disclosure consequence, recorded not resolved:** exporting the canonical rows exports
      operational decision content (`decision_id`, `tier`, `selected_action`, `pareto_weights`,
      `confidence`, `proposals`, `audit_trace`). The export is produced as a workflow artifact
      with a retention period; whether it is attached to a public release is an **operator
      decision**, recorded alongside OQ-4. Whether these rows contain anything a policy would
      classify as restricted **could not be established statically and must not be assumed either
      way.**
    - _Requirements: 10.3_

  - [ ] 23.6 Add `verify-export`, calling the same walker the DSN path calls
    - File: `orchestrator/audit/cli.py`
    - `verify-export --presentation PATH --anchor PATH --log-proof PATH --bounds PATH` constructs
      `ChainRow` values from the export and calls the **same** `chain_walk.walk` — one walker,
      "never reimplemented and never modified", as that module's own docstring insists. Verdict
      vocabulary is the committed three values: `chain-intact`, `chain-rewritten`,
      `chain-unverifiable`.
    - Today `verify` accepts only `--dsn`, `--since`, `--max-rows`, `--timeout` and `--head`
      (`:540-568`), so an external verifier would need **live credentials to this project's
      Postgres** — worse than the trust assumption R10 exists to remove. The offline path takes
      no credential and reads no version-control history.
    - A presentation larger than the committed bound is reported `not_verified` **naming the
      bound**, not silently truncated.
    - _Requirements: 10.3_

  - [ ] 23.7 Write property test for the export round-trip and truncation detection
    - `# Feature: decision-quality-proof, Property 76: The anchor commits to the head, and the export round-trips with truncation detectable`
    - File: `tests/verify/test_chain_presentation_export_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 10.2, 10.8_

  - [ ] 23.8 Write property test for offline verification totality
    - `# Feature: decision-quality-proof, Property 77: Offline verification is a total three-valued function of the public inputs alone`
    - File: `tests/verify/test_offline_verification_totality_property.py`
    - "Of the public inputs alone" is the load-bearing clause: the function must be total over
      anchor bytes, log timestamp and inclusion proof, presentation, boundary and bounds — with no
      database reachable and no repository history read.
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 10.3_

  - [ ] 23.9 Add the `chain-export` job where a database exists
    - Files: `.github/workflows/integration.yml`,
      `infrastructure/quality/blocking-steps.yaml`,
      `infrastructure/quality/required-checks.yaml`
    - `integration.yml` is the workflow that has Postgres (its `audit-chain-tamper` job is the
      precedent). The job reads the ordered snapshot, scopes it to the anchored head with
      `scope_to_anchor`, and writes the canonical presentation as a retained workflow artifact.
    - Same-commit declaration coupling: step names into `blocking-steps.yaml`, job name into
      `required-checks.yaml` with its eligibility reason recorded.
    - _Requirements: 10.3_

  - [ ] 23.10 Make publication reachable, and prove the freshness check can fail
    - Files: `.github/workflows/publish-audit-anchor.yml`,
      `infrastructure/quality/blocking-steps.yaml`
    - **Two independent defects, one fix.** `anchor` runs on `schedule`/`workflow_dispatch`,
      `publish` runs on `push`/`workflow_dispatch`, and there is **no `needs:` anywhere in the
      file** — so on `workflow_dispatch` both run concurrently and `publish`'s
      `git diff --name-only HEAD~1 HEAD` (`:147`) cannot see an anchor `anchor` has not committed
      yet, `files=` is emitted empty (`:150`), and **every signing step is skipped on a job that
      reports green**. The file discloses the other half itself (`:127-134`): the `anchor` job
      pushes with `GITHUB_TOKEN` and GitHub does not trigger workflows from such a push. Only a
      human hand-commit reaches the signing steps today.
    - `publish` gains `needs: anchor` and an `if:` admitting the dispatch and schedule paths;
      `anchor` emits the written anchor's path as a **job output** and `publish` signs exactly
      that. The `push` trigger is retained for hand-landed anchors, and on that event `anchor` is
      skipped and the diff path is used — so the two modes become explicit rather than accidental
      (R10.9).
    - Add the **falsifying** probe: an anchor back-dated beyond the committed freshness bound
      drives the anchor-freshness check to a **non-passing** result (R10.10). This discharges an
      obligation `gate-mutations.yaml` assigns to this workflow and nobody owns — its C67 entry
      classifies the check `reporting_tools` (`:373-374`), excludes it from `declared_gates: 14`,
      and records that the real proof of C67 "is empirical and belongs to the publishing
      workflow". The Falsification_Sweep **structurally cannot probe C67**, which is why R10.10
      exists rather than a `gates:` declaration. A probe that only confirms green proves nothing
      (I-7).
    - Declare the producing-and-publishing job in `blocking-steps.yaml` **in the same commit as
      the steps** (R10.11). The workflow's header asserts that "The freshness step propagates its
      exit status deliberately" (`:26`) — unpoliced prose, the same defect shape R7.15 fixes for
      `uplift.yml`. Adding steps here without the declaration **widens C64's blind spot**.
    - _Requirements: 10.9, 10.10, 10.11_

  - [ ] 23.11 Write property test for same-run publication
    - `# Feature: decision-quality-proof, Property 79: The anchor is published in the run that produced it`
    - File: `tests/verify/test_anchor_same_run_publication_property.py`
    - Budget inherited from the root `conftest.py` profile.
    - Locus: `ci.yml::uplift-verify` fast step.
    - _Requirements: 10.9_

- [ ] 24. Register every new check, then generate the documents that report them
  - **Order is the whole point of this task.** A generated ledger written before the last
    registration lands is a projection of a registry that no longer exists, and the next
    execution diffs against it. Generation is therefore last, after every `@register` in both
    halves.

  - [ ] 24.1 Assign identifiers and complete the registrations
    - Files: `scripts/audit/verify_claims.py`,
      `infrastructure/quality/required-checks.yaml`
    - **C75 is the highest registered identifier, so the next free one is C76.** Verified by
      reading `verify_claims.py`'s `@register` calls: C73 `check_sweep_budget` (5.3), C74
      `check_dataset_licence` (7.2), C75 `check_pin_extractors` (8.3). The first half therefore
      registered **three** new checks, not one — the dataset-licence check and
      `pin_extractor_truth` are **no longer owed**, and attempting to register them again would
      collide. This half registers `benchmark_truth` (19.4) and `uplift_staleness_truth` (17.7).
      This count has now been stale twice (first "C72 is highest", then "C73 is highest"), so
      **re-derive it against the `@register` calls at implementation time** rather than trusting
      this paragraph either.
    - `scripts/audit/spec_ledger_census.py` is deliberately **not** registered. It is local
      session hygiene, and registration precedes generation (this task's own rule); if it should
      become a check, it takes an identifier here, in landing order, with the
      `blocking-steps.yaml` and `required-checks.yaml` entries in the same commit.
    - Do **not** declare falsification mutations for the new checks in this task. The 49
      undeclared operators stay undeclared: forty-nine unverified declarations convert a visible
      gap into false assurance, which is the trade I-7 forbids (R1.9, R1.10, and the spec's own
      non-goal).
    - _Requirements: 9.12_

  - [ ] 24.2 Regenerate the ledger, the gate surface and the README from one execution
    - Files: `docs/state/CURRENT.md`, `docs/state/GATE_SURFACE.md`, `README.md`
    - Run `python -m scripts.audit.ledger_gen --write`, then
      `python -m scripts.audit.gate_surface --write`, then `readme_gen --write` (task 4.2),
      passing the single nested `--counts-json` payload so one registry pass serves every consumer
      and the documents cannot state different numbers for one execution.
    - The commit that publishes a checkpoint **includes** the ledger's generated region as
      projected by one Check_Registry execution at that revision, so every changed check status is
      **generated rather than transcribed** (R9.12). Nothing inside the markers is hand-edited,
      and every byte outside them survives.
    - _Requirements: 9.12_

- [ ] 25. Final checkpoint — state the claim, and state it honestly
  - discharge: uplift.yml::uplift-proof plus publish-audit-anchor.yml
  - Ensure all tests pass, ask the user if questions arise.
  - **The claim this spec exists to support**, and the conditions under which it may be stated:
    a headline uplift with its interval at `1 - alpha`, from a **complete** run at
    `MIN_POWERED_REPLICATES` per arm, **within** the fidelity bound, regenerated in the job that
    evaluated it, on a twin whose KPIs are demonstrably sensitive to the decisions under test
    (E2a/E2c), measured by an instrument shown able to see an effect of that size (E3), over a
    model trained on non-synthetic data and scored against an external benchmark (E4), with the
    audit chain independently verifiable by a party holding no credential from this project (E5).
    Every one of those clauses is a task above. None may be assumed.
  - **Pre-commitment, made here and binding before the number is known.** If the measured uplift
    is null or negative, **it is reported as null or negative.** The floor stays at `0.0`, no
    headline is published as a gain, and the result is written up as a finding rather than
    reframed, re-run at a different replicate count until it moves, or held back pending a
    "better" configuration. A null from a **validated** instrument on a **decision-relevant**
    world is a real finding, and it is worth more than the tautological PASS it replaces: before
    this spec, C60 could only ever report `SKIP`, and `uplift/uplift_floor.py:47`'s `0.0` floor
    meant a measured zero compared against zero was exit 2 — a number that could not fail because
    nothing had ever been measured.
  - **Two guards on reading the number, both already implemented above.** A null while any KPI in
    the R5.33 objective is recorded under R5.34 as not observably sensitive is **inconclusive**,
    not confirmation (task 10.5). And no headline may be published at all while no Power_Report
    describes the harness revision under measurement (task 17.3) — an unpowered null is not
    evidence of absence, and a Power_Report describing a superseded revision does not license
    publication.
  - Also confirm: the `--gate C60` probe reports **`falsified`**, not `indeterminate` (task 17.9
    plus 22.1); `uplift.yml` and `publish-audit-anchor.yml` both appear in
    `blocking-steps.yaml`, and `uplift.yml`'s job appears in `required-checks.yaml` under
    `ineligible`/`post-merge`; every threshold committed in tasks 16.2, 22.3 and the first
    half's 8.2/10.4/12.x/13.x has a `ratchets.json` entry whose extractor was verified **by
    running it**; and the ledger, the gate surface and the README are projections of one
    execution rather than three transcriptions.

### Phase 6 — adopted debt. Registered in session 2q, sequenced BEFORE session 2.

> **Both parents carry work this spec did not author and has now adopted, with the operator's
> explicit decision on each.** Their identifiers are last because renumbering would break
> `task_claim_truth`, this file's own cross-references and other specs' citations. **Their
> execution order is not their id order** — precedent is checkpoints A–D, which fire before the
> work they gate. `SESSION_PROTOCOL.md`'s batch table places **session 2r** before session 2 and
> states why.

- [ ] 26. Regenerate the projected documents — the repair half of the three generators
  - **Adopted by operator decision in session 2q**, from the two options put to them: run the
    generators locally (~30 minutes of full-core CPU, category 3/4 under I-0) or add a CI job that
    runs them on a runner and uploads the result. The second was chosen.
  - **The drift is NOT this spec's authorship.** `README.md`'s generated headline claims
    `PASS 51 / FAIL 3 / SKIP 10 / TOTAL 64` while the suite reported `54 / 2 / 11 / 67` at sha
    `77df3ef`. That gap is session 1's three registrations (C73, C74, C75) never regenerated into
    the README. It is nevertheless **measured as owed rather than predicted**, and the argument is
    not the red tick: C56's red baseline made C56 itself unprobeable, so the falsification sweep
    probed **7** checks instead of 8. **Doc drift removed a gate from the measurement.**
  - **Why CI could not already fix this, verified by reading `truth-gates.yml`.** That workflow
    runs `readme_gen --check`, `ledger_gen --check` and `gate_surface --check`. All three DETECT;
    none REPAIRS. So "let CI answer it" — which was the right call for C63 in session 2p — is
    structurally unavailable here, and the only `--write` path was a developer's machine.
  - **Repair order is fixed and is the one `truth-gates.yml`'s own header states:**
    `gate_surface --write` (landed session 2p, re-run session 2q for the new job) →
    `ledger_gen --write` → `readme_gen --write`. Registration and wiring first, generation last.
  - **CORRECTED SESSION 4 — THAT ORDER IS BACKWARDS FOR EXACTLY THE CASE THIS PARENT EXISTS TO
    REPAIR, and the first real execution proved it.** `ledger_gen` projects a **top-level**
    registry execution, in which C56 **is** evaluated, and C56 reads the README headline that
    `readme_gen` rewrites **afterwards**. The true dependency is
    `readme_gen` → `README.md` → C56 → `ledger_gen`, so the committed order inverts it: run
    `34372152090` generated `CURRENT.md` against the pre-repair README and recorded
    `C56 | FAIL`, which became false the moment step 7 rewrote the README. Measured, not
    predicted: the registry verdict in the artifact reads `C44=FAIL, C56=FAIL, C69=FAIL`, while
    `truth-gates.yml` on the very next commit reads `C44=FAIL, C69=FAIL`.
    - **The README headline is NOT affected**, and the reason is the recursion guard working as
      designed: it projects the **nested** execution, in which C56 self-excludes and counts as a
      SKIP. Only the top-level ledger is exposed.
    - **Consequence: a SECOND regeneration is owed, and it is owed by this job's own step order
      rather than by any external pin.** `CURRENT.md`'s `C56` row and its registry-verdict line
      reach their fixed point only on a dispatch made *after* `2be5a96`. This is a different
      obligation from the one decision 1 weighed — that one was about task 10.4's pin
      invalidating a regeneration; this one is internal to the generator sequence and would
      recur on every future repair of a README-sourced claim.
    - **The durable repair is to swap the two `--write` steps** so `readme_gen` precedes
      `ledger_gen`, which makes the ledger a projection of the tree the README already describes.
      **Not taken here:** the order is stated in `truth-gates.yml`'s header as well as in this
      parent, so changing it edits the declared repair order of the enforcement spine — a
      registered-surface change, and the operator's. Recorded with its mechanism so it is not
      re-derived.
  - **A LOCAL-GENERATION ARTIFACT WAS MASKING THREE REAL FINDINGS, and this was the first
    projection of `CURRENT.md` ever taken on a Linux runner.** The committed ledger recorded
    C44's detail as `check raised FileNotFoundError: [WinError 3] ... The system cannot find the
    path specified: 'C:\Users\Pranesh\Projects\synapse\frontend\node_modules\.pnpm\...'` — a
    Windows dev-box path error standing in for a check's finding. The runner's projection reports
    what C44 actually finds: **three liveness violations** — two dead modules
    (`data_fabric/ingest/__init__.py`, `data_fabric/ingest/m5.py`) against a named baseline of
    `0`, and `synapse_common.contracts.validate_audit_insertion`, which encodes a `[deal.post]`
    invariant and is invoked **only** from `packages/tests/test_contracts.py`. **This is the
    strongest available justification for I-0's never-run-locally rule on the generators and for
    task 26 choosing a CI job over a local `--write`: a document generated on the wrong machine
    does not merely go stale, it can record an environment error as a finding and hide the real
    ones behind it.** C44's repair belongs to its own owner and is not adopted here.
  - **Never repair a count by hand (I-7).** `blocking-steps.yaml` says so in those words. The job
    exists so the number is projected, and the human step is *review*, not transcription.
  - _Requirements: 4.4, 4.5, 4.8, 4.11, 10.1, 10.7, 11.7_

  - [~] 26.1 Author the dispatch-only regeneration job and land its couplings
    - discharge: regenerate-truth-docs.yml::regenerate (first dispatch, 26.2) for the job itself;
      ci.yml::uplift-verify fast step for the closure-parity property
    - **Landed and locally verified in session 2q. `[~]` and not `[x]` because the workflow has
      never executed** — a job that has never run is exactly the shape I-7 names, where reporting
      nothing is indistinguishable from passing.
    - Files: `.github/workflows/regenerate-truth-docs.yml` (new),
      `infrastructure/quality/blocking-steps.yaml`, `docs/state/GATE_SURFACE.md`,
      `tests/verify/test_regeneration_closure_parity.py` (new)
    - `workflow_dispatch` only, `permissions: contents: read`, `timeout-minutes: 45` derived from
      `truth-gates`' own 25 rather than picked. It **commits nothing**: it writes the documents,
      prints the diff to its log and uploads them for a human to commit. An auto-commit variant was
      rejected — it would let a machine write generated counts into the tree with no reviewer, and
      hand-maintained counts drifting is the entire reason these documents are generated.
    - **The install closure is copied verbatim from `truth-gates.yml::truth-gates` and pinned by a
      test rather than extracted into a shared script.** Extracting it would edit the steps of a
      **required** status-check workflow to save a copy. The closure is load-bearing: several
      registered checks report SKIP when an optional import is missing, so a thinner environment
      turns a PASS into a SKIP, moves the counts, and the job would then **write the wrong numbers
      into the documents it exists to correct** — a failure that looks like a success.
    - **`readme_gen --write` runs without `--counts-json`, deliberately.** The flag does not change
      *which* counts are used: without it `readme_gen` calls `doc_truth.nested_suite_counts`
      itself, through the same function the gate calls, so the nested-execution semantics that make
      C56 self-exclude hold either way. It is purely a cost saving, and earning it here would mean
      pairing with `doc_truth --check` — a step **expected** to exit non-zero while C44 and C69 are
      red — so the only way through would be a `continue-on-error` inside a truth-gates-adjacent
      workflow. One extra registry execution is the accepted cost; a discarding construct is not.
    - **`gate_surface --check` is the job's first step and a hard gate**, not a courtesy:
      regenerating on top of a stale gate surface produces an artifact that is stale the moment it
      is written, because C63's status sits inside the counts `doc_truth` and `readme_gen` pin.
    - **Both halves of the fourth same-commit coupling landed together**, and the coupling was
      observed firing rather than assumed: `gate_surface --check` went non-zero on the new job
      (17→18 workflow files, 54→55 jobs, 370→378 steps) and back to 0 after `--write` (536 surface
      rows). `workflow_shape_truth --check` resolves the new declaration and reports 11 blocking
      entries, up from 10.
    - **No `required-checks.yaml` entry is owed, and this was checked rather than assumed.**
      `required_checks_truth` validates that *declared* jobs resolve, not that the file is
      complete; `required-checks.schema.json::ineligibleEntry` constrains `reason` to a closed
      six-value enum with `additionalProperties: false` and none of the six describes
      "dispatch-only". Declaring it would mean amending a schema enum — the third same-commit
      coupling — for a job that produces no status check on any pull request. Eight existing
      workflows carry no entry either.
    - _Requirements: 4.4, 4.5, 4.8, 4.11, 10.1, 10.7, 11.7_

  - [x] 26.2 Dispatch the job and review the regenerated diff
    - discharge: regenerate-truth-docs.yml::regenerate
    - **DISCHARGED session 4. `regenerate-truth-docs.yml::regenerate` run `34372152090`, sha
      `0c0e971`, reached by the `regenerate-truth-docs` label — the workflow's FIRST EXECUTION
      EVER. All nine steps green, including step 5's `gate_surface --check` hard gate, so the
      dispatching commit had not missed the fourth coupling.** The artifact's
      `GATE_SURFACE.md` is byte-identical to the committed copy, which is the independent
      confirmation that C63's PASS was real rather than asserted. The diff reproduces the job's
      own `--stat` exactly: README 1 line, `CURRENT.md` 27, 16 insertions / 13 deletions.
      Committed in `2be5a96`. **Nothing was hand-edited (I-7).**
    - **RUN IT BY LABEL, NOT BY DISPATCH. This sub-task's instruction was wrong and is
      corrected here rather than left for the next reader to discover.** It said
      `gh workflow run regenerate-truth-docs.yml --ref feat/decision-quality-proof`; finding 23
      proves that returns **HTTP 404**, because GitHub requires a workflow file on the DEFAULT
      branch before it can be dispatched and `origin/main` does not carry this one. Session 3
      landed route 1 (`bbe4278`): add the **`regenerate-truth-docs`** label to PR #84, then
      remove it. Then download the `regenerated-truth-docs` artifact and read the diff the run
      printed.
    - **Operator action.** The review is the point: the artifact is a proposal, and a reader must
      confirm the counts moved for the reason expected before any of it is committed.
    - Confirm the job's own first step passed — a red `gate_surface --check` means the dispatching
      commit missed the fourth coupling and the artifact must not be used.
    - **STILL BLOCKED, and no longer by its own mechanism.** Route 1 removed the structural
      blocker; what remains is the account-level CI block (session 3, run `34319298166` at
      `fe8ddeb` started no jobs). A labelled run today would fail before its first step.
    - **UNBLOCKED SESSION 4 — the repository went public and CI runs again. AND DECISION 1's
      ORDERING PREMISE HAS LAPSED, which changes when this should be dispatched.** Decision 1
      chose "route 1 **then 3**" — regenerate *after* the margin lands — on a single argument:
      task 10.4's pin changes `doc_truth`'s claim set and can move C56, so an earlier
      regeneration is stale within the hour and costs a second ~45-minute dispatch. **Conflict M
      removed that argument.** The margin cannot land until the `(s, S)` comparator exists or the
      headroom guard gains an independent bound, both operator decisions with no date. So there
      is no imminent pin to invalidate this regeneration, and dispatching it now costs nothing
      extra while buying what `uplift-verify` — and therefore Properties 38–60 — has been waiting
      on since this branch was cut. **Surfaced rather than silently re-ordered: the trade decision
      1 made was correct on its own facts, and its facts changed.**
    - _Requirements: 4.4, 4.5, 10.1, 11.7_

  - [x] 26.3 Commit the regenerated documents and confirm C56 returns to PASS
    - discharge: truth-gates.yml::truth-gates
    - Files: `docs/state/CURRENT.md`, `README.md`
    - **Two things must be confirmed, not one.** C56 goes PASS on the next `truth-gates` run; and
      the falsification sweep's probeable set returns to **8**, because C56 regains a passing
      baseline. The second is the measurement power the drift cost, and it is the reason this
      parent exists rather than the tick.
    - Read the registry verdict line for the count, not a single step's conclusion — session 2p's
      lesson that a deferred verification aimed at a gated step is not a deferred verification.
    - **DISCHARGED session 4, and BOTH conditions were read from `truth-gates.yml`'s own
      execution — run `34373152377`, sha `2be5a96`.**
      1. **C56 PASSES.** The registry verdict line from step 5's full Check_Registry execution
         reads `[XX] registry-gate: FAIL - 2 check(s) did not pass: **C44=FAIL, C69=FAIL**`.
         C56 is absent from the failure list, where the previous projection had
         `C44=FAIL, C56=FAIL, C69=FAIL`. Read from the verdict line as this sub-task instructs,
         not from a step conclusion. Independently corroborated by `ci.yml::quality-gates`
         **step 17 `success`** on run `34373152347` — the first time that step has passed on
         this branch.
      2. **The probeable set is back to 8.** The sweep reports `7 check(s) falsified by every
         declared mutation, 0 operator(s) unproven`, `16 of 16 declared operator(s) probed`, and
         exactly **one** defect: `C28/zero-a-floor gate-survived-declared-mutation`. 7 falsified
         + 1 survivor = **8 checks with a passing baseline**, and **no check is reported
         `indeterminate`** — which is the condition C56's red baseline used to create. The one
         survivor is task 6's reviewed-and-accepted survivor, whose repair is deferred to its
         owner and is explicitly not this spec's.
    - **`truth-gates.yml::truth-gates` is still RED as a job, and that is not this sub-task's
      subject.** It fails at step 5 on `C44` and `C69`, so steps 6–12 — including
      `ledger_gen --check` — are skipped behind it. Both are pre-existing and neither is this
      spec's: **C69** is `core-purpose-uplift` task 9's placeholder checkpoint registry, the
      same record `task_claim_truth` has reported for four sessions; **C44** is the three
      liveness violations the previous ledger was masking (see below). Ticking on the two stated
      conditions rather than on the job's colour is the same judgement `task_claim_truth`'s red
      already requires: read the subject of a failure before treating it as yours.
    - **AND `ledger_gen --check` IS EXPECTED RED WHEN IT NEXT EXECUTES, for a reason this
      sub-task discovered and could not avoid.** See the repair-order finding under parent 26: a
      second regeneration is owed because the committed order generates the ledger *before* the
      README whose contents C56 reads.
    - _Requirements: 4.4, 4.5, 4.8, 4.11, 10.1, 10.7_

- [x] 27. `mypy --strict orchestrator/` — the debt that gates every property this spec has written
  - **Adopted into scope by explicit operator decision in session 2q**, from three options: file it
    against its author, take it as a named batch, or split it. The batch was chosen.
  - **This is the single largest obstacle in the tree, and the reason is structural.**
    `ci.yml::uplift-verify` declares `needs: quality-gates`; `quality-gates` fails at step 8,
    `mypy --strict orchestrator/`; so **Properties 38–60 have never executed in CI on this branch.**
    Every property this spec has authored is local evidence only until this parent closes.
  - **Measured baseline, session 2q:** 78 errors in 32 files, decomposing as
    `call-arg` 21, `arg-type` 24, `unused-ignore` 7, `type-arg` 5, `no-any-return` 5,
    `no-untyped-def` 4, `import-untyped` 4, `attr-defined` 2, `union-attr` 2,
    `comparison-overlap` 2, `method-assign` 1, `assignment` 1.
  - **CORRECTED session 2r — that baseline is NOT at CI's exact command, and the error costs a
    session if believed.** `ci.yml::quality-gates` step 8 runs
    `mypy --strict orchestrator/ --exclude orchestrator/tests`; the 78/56 figures are the **wide**
    `mypy --strict orchestrator/`, which **no workflow in the repository runs**. Read from CI's own
    step-8 log on run `33582858699`: `Found 3 errors in 3 files (checked 44 source files)` against
    89 source files locally. The 56 decompose by scope as **3** in `orchestrator/` source (the whole
    of step 8's failure, all `import-untyped`), **49** under `orchestrator/tests/` (excluded at step
    8), and **4** under `agents/` (reached by followed imports; step 9 is `continue-on-error: true`).
    The exclusion is effective because nothing imports `orchestrator.tests` — checked, not assumed.
    **So the group 27.3 flagged as probably-unrepairable was the only group that gated anything, and
    the 24 `arg-type` errors 27.2 ranks first gate nothing.**
  - **CORRECTED session 2r — "all 78 originate from `e000258`; none is on `main`" is false.** Nine of
    the twelve files carrying the remaining bucket-B errors, and both bucket-C files, were last
    touched by commits that are ancestors of `origin/main`, so their content is byte-identical to
    `main` and their errors are `main`'s. The single largest file, `test_brownout.py` with 26 of the
    56, is `be3edd1` — on `main`. Ownership had been misfiled in the *opposite* direction this time:
    filed as this branch's, and mostly the default branch's.
  - **Determine ownership mechanically before filing any of the remainder as pre-existing.** Two
    findings have already been misfiled as `main`'s and turned out to be this branch's.
      ```powershell
      git log -1 --format='%h' -- <file>
      git merge-base --is-ancestor <sha> main     # exit 1 => NOT on main => this branch's
      gh run list --branch main --workflow '<name>' --limit 3
      ```
    **`git log -1` reports LAST TOUCH, not authorship, and session 2r was misled by exactly that.**
    `test_cognition_phase.py` resolved to `e000258` and looked like this branch's; the file also
    exists on `main`, and `git diff origin/main -- <file>` showed the failing assertion is
    unchanged from `main`. When a file exists on both, attribute the **line**, and confirm by
    running `git show origin/main:<file>`.
  - **FORBIDDEN REPAIRS, and each names what it would destroy.** No error may be cleared by giving
    an argument a default, by widening a type to `Any`, by adding a `# type: ignore`, or by
    narrowing mypy's scope. The first substitutes an unreviewed value for a committed one; the
    second and third make the checker agree by asking it less; the fourth deletes the gate. If an
    error is genuinely a tooling artifact, the repair must be at the *declaration* that misleads
    the checker — 27.1 is the worked example — never at the call sites that report it.
  - **`warn_unused_ignores = true`, so removing an error can create one.** Expect that and read it
    as progress, not regression. It is why 27.4 is sequenced last.
  - _Requirements: —  (adopted debt; no requirement in this spec declares it)_

  - [x] 27.1 Make the committed `confidence_threshold` default visible to the type checker
    - discharge: ci.yml::quality-gates step 8 (the error count it reports at CI's own scope)
    - **DISCHARGED session 2r.** `ci.yml::quality-gates` step 8 reported **success** on run
      `33588706405`, sha `b7954b6` — the first time that step has passed on this branch. Read from
      the job's own step conclusion, not inferred from a local run.
    - **Landed and locally measured in session 2q: one line, 22 errors cleared, no runtime change.**
      `orchestrator/config.py` declared `Field(0.7, ge=0.0)` — default passed **positionally**.
      This project configures no `pydantic.mypy` plugin, so mypy reads the field through pydantic
      v2's PEP-681 `dataclass_transform`, which recognises a field-specifier default only as
      `default=`. The reviewed default was therefore invisible to the checker and the field was
      synthesised as a **required** keyword argument.
    - Files: `orchestrator/config.py`,
      `orchestrator/tests/test_orchestrator_config_confidence_default.py` (new)
    - **Why the obvious repair was the wrong one, and this is the whole point of the task.**
      Clearing 21 `call-arg` errors by passing a value at each call site would have injected 21
      unreviewed numbers onto the **I-5 confidence gate**, because
      `GuardrailEngine(confidence_threshold=config.confidence_threshold)` consumes it and
      `thresholds.py` records that the boundary is injected a single time at
      `inference/serve.py`. **Three of the 21 sites are production**, not tests
      (`inference/serve.py` ×2, `audit/cli.py`). The reviewed default already existed.
    - **Measured 78 → 56, and the prediction was 57.** Exactly two codes moved and both to zero:
      `call-arg` 21→0 and `assignment` 1→0. Every other code is **identical**, and no new code
      appeared. The unpredicted 22nd is `orchestrator/guardrails/thresholds.py:118`, which assigns
      the **class object** into a `Callable[[], OrchestratorConfig]` slot — not a zero-argument
      callable while `__init__` was believed to require the argument. Same root cause, in the
      module that reads the I-5 boundary, and its own docstring already declared the class callable
      with no arguments. `thresholds.py` now reports zero errors. It is also one of the errors
      `HANDOFF.md` recorded as blocking `pre-commit install`, and it was never a stub-gap error.
    - **What is claimed and what is not.** The claim is the *delta* and the disappearance of the two
      codes, which are inference results independent of installed stubs. The **absolute** CI count
      may differ from 56: the local environment has no `types-PyYAML`, so four `import-untyped`
      errors here may not correspond one-to-one with CI's. Step 8 still **fails** — 56 > 0 — so
      `uplift-verify` remains skipped and nothing this spec wrote has run in CI yet.
    - Five regression tests pin what the field's own comment declares: the default is present with
      no argument passed; it agrees with `DEFAULT_CONFIDENCE_FLOOR` (mechanising a claim
      `rules.py` previously made only in prose); `ge=0.0` refuses `-1.0`; the bound is inclusive
      rather than strict; and no `le` ceiling was introduced, so a boundary above `1.0` remains
      available as an operator kill switch.
    - _Requirements: —_

  - [x] 27.2 Diagnose and repair the 24 `arg-type` errors, per error rather than per pattern
    - **The largest remaining group, and it must not be treated as one pattern.** 27.1's group was
      genuinely uniform — all 21 were one declaration's artifact — and reading that as licence to
      batch-fix these would be exactly the over-generalisation that cost session 2p three real
      Biome findings. Classify each before repairing any.
    - Expect the repair to move the `unused-ignore` count in both directions; 27.4 absorbs that.
    - **Done session 2r. Classified first, then repaired once.** All 24 are **two** distinct
      messages — argument 2 and argument 3 — across **12** call sites, every one in
      `orchestrator/tests/test_brownout.py` supplying a `_FakeBreaker`. Uniformity was *established*
      by grouping the captured messages, not assumed from 27.1.
    - **The declaration was the defect.** `BrownoutController` reads exactly one attribute from a
      breaker — `.state`, compared against `BreakerState` — and calls no method and mutates nothing.
      Typing both parameters as the whole `AsyncBreaker` overstated the requirement, and the
      overstatement was reported 24 times at the call sites rather than once where it lived.
    - Files: `orchestrator/consensus/brownout.py` — a read-only `BreakerStateSource` Protocol.
      `AsyncBreaker` satisfies it **structurally** (its `state` is a read-only property returning
      `BreakerState`), so `inference/serve.py:116` and every other caller is untouched and no
      runtime behaviour moves. Read-only on purpose: a mutable protocol member would reject a
      property. `arg-type` 24 → **0**.
    - `unused-ignore` did **not** move in either direction here; it held at 7. Recorded because the
      prediction that it would move is what sequenced 27.4 last, and the prediction did not fire.
    - _Requirements: —_

  - [x] 27.3 Repair the remaining 26 errors across eight codes
    - `type-arg` 5, `no-any-return` 5, `no-untyped-def` 4, `import-untyped` 4, `attr-defined` 2,
      `union-attr` 2, `comparison-overlap` 2, `method-assign` 1.
    - **`import-untyped` may not be repairable here, and that must be recorded rather than
      suppressed.** `types-PyYAML` is deliberately not installed — `HANDOFF.md` records that
      installing it unmasks real pre-existing errors elsewhere that then block commits to files
      which do not contain them. If these four are that gap, the honest outcome is a recorded
      deferral naming the reason, not a `# type: ignore`.
    - `comparison-overlap` is worth reading closely rather than silencing: a comparison mypy proves
      can never be true is usually a real defect, not a typing nuisance.
    - **Done session 2r. `import-untyped` was the ONLY group that gated anything, and a deferral
      would have been the wrong call.** Three of the four are in `orchestrator/` source and were
      the entire content of step 8's failure; landed separately in `b7954b6` as `yaml.*` and
      `psycopg2.*` `[[tool.mypy.overrides]]` entries — the mechanism `pyproject.toml` already uses
      for 27 other packages, and a declaration about a third-party package's stub availability
      rather than a check weakened on first-party code. Inference is unchanged either way: with the
      stubs absent mypy already models both modules as `Any`.
    - **`comparison-overlap` was right twice, and both were assertions that CANNOT FAIL.** Not
      comparisons that can never be true — comparisons mypy could prove *decided*, which is the same
      defect from the other side. `test_data_provenance_builder.py` asserted R4.4's distinctness
      clause *after* two equality assertions had narrowed both operands to distinct `Literal`s;
      moved above them, it can fail. `test_protocol.py` asserted the FSM reached `COLLECTING` after
      a mutating `transition()`, but the preceding `== IDLE` assertion narrows the member expression
      and mypy does not discard that across the call — so the assertion was provably false. Each
      observation is now bound to a fresh local where it is observed. The same narrowing mechanism
      explains four of 27.4's unused ignores.
    - `union-attr` was a third one: `test_brownout.py` called `.current_level()` straight through
      `get_controller()`, typed `BrownoutController | None`, so a registration failure would raise
      `AttributeError` instead of failing the assertion the test is named for.
    - Every remaining repair is at the point the `Any` **enters**, not where it exits:
      `newsvendor.py` gained a typed `_sqrt` mirroring its own `_ln` (because `x ** 0.5` is typed
      `Any` — a float base with a float exponent may be complex — which leaked into three `-> float`
      returns); `inventory_sentinel/a2a/handler.py` adopted the typed-local convention its **seven**
      sibling handlers already use, being the only one of eight that returned `json.loads(...)`
      directly; `attr-defined` and `method-assign` became `monkeypatch.setattr`, which also restores
      the attribute; `test_twin_verification.py` gained four return annotations (`boom` is
      `NoReturn`, which states that the fake never returns) and lost three now-redundant `ANN202`
      noqas; bare `dict`/`list` parameterised. **No `# type: ignore` was added anywhere.**
    - _Requirements: —_

  - [x] 27.4 Clear the `unused-ignore` errors LAST, once the others have stopped moving
    - **Sequenced last on purpose.** `warn_unused_ignores = true`, so every repair in 27.1–27.3
      can both remove an ignore's justification and create a new unused one. Clearing them first
      would mean clearing them twice, and the second pass would look like a regression.
    - A `# type: ignore` that is genuinely unused is deleted, never re-narrowed to keep it alive.
    - **Done session 2r. Seven deleted, none re-narrowed, `unused-ignore` 7 → 0.** The hazard the
      sequencing guards against did **not** fire: the count held at exactly 7 across 27.2 and 27.3,
      measured, which is what made a single clearing pass sufficient. Six were wholly unused —
      `test_audit.py`, `test_audit_logger.py`, and four in `test_outbox_dispatcher.py` whose
      `attr-defined` ignores are redundant because mypy narrows the member expression to `AsyncMock`
      after the assignment above them.
    - The seventh is the one that needed judgement.
      `test_confidence_gate_universality_property.py:640` carried
      `# type: ignore[method-assign,assignment]` and mypy proved only `assignment` redundant. The
      compound loses that code and keeps `method-assign`, which is still doing work. **That is not
      re-narrowing an unused ignore to keep it alive** — the ignore is used; one of its two codes
      was not. Lines 638 and 639 are byte-identical in form and were *not* reported, so the
      distinction is mypy's, not a preference.
    - _Requirements: —_

  - [x] 27.5 Confirm step 8 passes and that `uplift-verify` actually executes
    - discharge: ci.yml::uplift-verify
    - **This is the payoff, and it is the only thing that discharges it.** Confirm `quality-gates`
      reaches its end, then confirm `uplift-verify` **ran** — not that it was skipped, and not that
      it reported nothing. Then read Properties 38–60's first CI execution.
    - **Read what got skipped behind the failure, not only what failed**, if it still fails:
      `gh api .../jobs` and list every step whose conclusion is `skipped`. One 101-character line
      once gated 18 steps and 3 jobs across two pushes with nothing recording it.
    - Until this leaf is `[x]`, every `HANDOFF.md` must continue to state that this spec's property
      surface is local evidence only.
    - **STEP 8 PASSES. `uplift-verify` STILL DOES NOT RUN, and the reason is not this parent's.**
      Measured on run `33588706405`, sha `b7954b6`: steps 1–16 **success**, including step 8. The
      failure moved to **step 17, the C56 narrative-truth gate**, and steps 18–23 are skipped behind
      it — so `uplift-verify` is skipped for a third distinct reason.
    - **The chain to `uplift-verify` is at least FOUR deep, and parent 27 names only the first.**
      (1) step 8 `mypy --strict orchestrator/ --exclude orchestrator/tests` — **cleared**.
      (2) step 17 **C56**, failing on exactly one claim, `doc-truth/headline-counts`: README claims
      `PASS 51 / FAIL 3 / SKIP 10 / TOTAL 64`, suite reports `54 / 2 / 11 / 67`. That is **task 26's
      drift**, and its repair is `readme_gen --write` via `regenerate-truth-docs.yml` — which is
      not dispatchable, so **task 26.2 now blocks task 27.5.**
      (3) step 19 unit tests, never executed on this branch, will fail on
      `orchestrator/tests/test_cognition_phase.py::test_run_consensus_streams_correlated_phases`
      — found locally in session 2r and **proven pre-existing on `main`** by running
      `git show origin/main:` of that file.
      (4) steps 20–22 (coverage floors, spec coverage, contract tests) have never executed on this
      branch **or on `main`**, so their state is unknown, not green.
    - **C56 and the hidden unit-test failure are both red on `main` itself.** `main`'s last three
      `SYNAPSE CI` runs (`045f44c`, `4114557`, `bd64483`) all fail `quality-gates` at step 17 on the
      same claim, with its unit-test step skipped behind it. `045f44c` is this branch's fork point.
      So obstructions 2–4 are **default-branch debt this spec did not create**, and reading step 8's
      clearance as "27.5 is nearly done" would be the error.
    - **OBSTRUCTION 3 IS NOW REPAIRED ON DISK, session 3 (`bf8693f`), by explicit operator
      decision — and this leaf is still `[ ]`.** The repair is a **precondition correction**, not an
      assertion weakening (R2.10): `all(c.args[0] == PHASE_TOPIC for c in calls)` claimed the
      protocol emits to no other topic, which stopped being true when ADR-038's
      `emit_agent_signals` and ADR-053's `emit_agent_metrics` began sharing the producer at
      `protocol.py:1021` and `:1024`. The calls are now **partitioned** with the partition asserted
      **exhaustive** — a filter alone would have discarded what the original assertion protected —
      and the permitted non-phase topics are **derived** from `firehose_signals.METRICS_TOPIC` and
      `SIGNAL_CHANNELS` rather than transcribed. Ownership was re-confirmed mechanically first:
      the file exists on `origin/main` and `git diff origin/main` shows only session 2r's type
      repairs, so the failing assertion is byte-identical to `main`. **6 passed locally; the file is
      green for the first time on this branch. That is not a discharge** — this leaf's
      `discharge:` line names `ci.yml::uplift-verify`, obstruction 2 still sits ahead of it, and
      CI is account-blocked.
    - **OBSTRUCTION 2's mechanism is unblocked but not cleared.** Route 1 landed in `bbe4278`, so
      task 26.2 can now be reached by label instead of by an impossible dispatch. The regeneration
      itself has still never run.
    - **SESSION 4 — OBSTRUCTION 2 IS CLEARED, AND THE CHAIN GAINED A LAYER NOBODY HAD NAMED.
      `uplift-verify` STILL HAS NOT RUN.** Measured on `ci.yml` run `34373152347`, sha `2be5a96`:
      `quality-gates` steps 1–17 **success** — including **step 17 C56, for the first time on this
      branch** — and the failure moved to **step 18**, with 19–23 skipped behind it.

      | # | Obstruction | State, measured |
      |---|---|---|
      | 0 | the runner itself (billing) | **CLEARED** — repository made public |
      | 1 | step 8 `mypy --strict orchestrator/ --exclude orchestrator/tests` | **CLEARED** (2r), re-confirmed `success` at `2be5a96` |
      | 2 | step 17 **C56** narrative-truth | **CLEARED** (26.2/26.3) |
      | **2.5** | **step 18 `Golden-trace replay metrics (R7.6/R7.7)`** | **RED, NEVER NAMED IN THIS CHAIN BEFORE, AND STRUCTURAL** |
      | 3 | step 19 unit tests → `test_cognition_phase` | **still unknown** — skipped behind 18. The repair is on disk (`bf8693f`) and remains unjudged |
      | 4 | steps 20–22 coverage floors, spec coverage, contract tests | **still unknown** |

    - **OBSTRUCTION 2.5 IS AN HONEST I-7 REFUSAL, NOT A DEFECT, AND THAT IS WHY IT IS HARD.**
      Step 18 measures two floors from `infrastructure/quality/replay-floors.yaml` over 200 golden
      traces at seed `0xCAFEBABE`. It reported:
      - `[OK] tier_routing_accuracy: measured 1.0000 >= floor 0.8000 (200/200 traces classified
        into their expected tier)` — **passes, and it is a real measurement.**
      - `[??] kv_cache_hit_rate: measured UNAVAILABLE, floor 0.7000 -- synapse_ollama_cache_hit_rate
        has no samples -- the replay took no cache observation (Ollama offline); no hit rate was
        measured`
      - `[??] replay-metrics: UNAVAILABLE - at least one floor has no measurement behind it.
        Absence of proof is not a pass (I-7).` → **exit 2.**

      **The gate is behaving exactly as this project demands** — it refuses to call an unmeasured
      floor a pass. But `kv_cache_hit_rate` needs an Ollama-backed cache observation, and a hosted
      runner has no Ollama: standing one up is a category-1 service workload. So this step **cannot
      pass on a GitHub-hosted runner as currently written**, which makes it a structural blocker
      rather than a repairable red.
    - **It is `main`'s, and it has never executed anywhere.** The step exists in `origin/main`'s
      `ci.yml`; it sat behind step 5, then step 8, then step 17 for this branch's whole life, and
      `main`'s own runs fail at step 17 too. Its own comment records the motive: *"The two numbers
      CLAUDE.md has stated since Sprint 9 with NO gate anywhere"*. **So the gate was written to
      close a documentation claim, and the first time anything ran it, it proved the claim is not
      measurable in CI.** That is a genuine finding about the claim, not about the gate.
    - **Three dispositions, all the operator's, none taken here.** (a) Give `uplift-verify` a
      `needs:` that does not transit an unmeasurable step. (b) Split step 18 so
      `tier_routing_accuracy` — which measures cleanly at 1.0000 — gates, while
      `kv_cache_hit_rate` is declared unmeasurable-in-CI with its own recorded reason, which is
      the `DEGRADED`/`SKIP` shape I-7 already blesses. (c) Provide a cache observation in CI.
      **(b) is the one consistent with this repo's own precedent** (C74's honest SKIP behind a
      Kaggle acceptance gate is the same shape) and it is the only one that does not weaken a
      floor. **Do not clear this by lowering `kv_cache_hit_rate` or by making step 18
      `continue-on-error`** — the first is assertion weakening (R2.10), the second re-creates the
      swallowed-exit-status defect session 4 just repaired two steps away.
    - **SESSION 5 — `uplift-verify` HAS NOW RUN, FOR THE FIRST TIME EVER. This leaf is still
      `[ ]`, because its own `discharge:` line asks for a job that reaches its end and this one
      did not.** Disposition **(a)** was taken by explicit operator decision: `needs:
      quality-gates` was removed from `uplift-verify` (`28cecce`), because
      `required-checks.yaml` declares that job `required:` and the edge made it reportable only
      as `skipped` — behind step 5, then 8, then 17, and now behind an unmeasurable step 18.
      **The two consequences of obstruction 2.5 are separable and only one of them is closed.**

      **Measured on run `34384834900`, sha `e9db587`:** `uplift-verify` `steps=9`,
      conclusion `failure`. Step 4 **`Install dependencies` SUCCESS** — the closure proof taken
      before the push was correct. Step 5 `Property + unit tests (fast — full 500-example
      budget)` **failure**: `9 failed, 830 passed, 1 skipped, 25 deselected, 2 xpassed` in
      `849.90s`. Step 6, the slow step, **skipped behind it**.

      **So the claim must be stated precisely, and it is narrower than "Properties 38-60 have
      executed".** The **fast** surface of `tests/uplift` and `tests/verify` ran and is now
      measured. The **slow** step never started, so the six slow properties, the 623-test
      regression floor, the subprocess fault-injection probe and `digital_twin`'s 1000-scenario
      run are all still unexecuted. `sprint6-verify` and `training-smoke` remain `skipped`,
      correctly: they keep their own `needs: quality-gates`.

      **THE NINE FAILURES, ATTRIBUTED MECHANICALLY (`git cat-file -e origin/main:<f>` then
      `git diff origin/main -- <f>`), because ownership decides who repairs them.**

      | Module | Failures | On `origin/main`? | Owner |
      |---|---|---|---|
      | `tests/verify/test_command_path_resolution_property.py` | **5** | **absent** (1177 insertions) | **this spec** |
      | `tests/verify/test_ledger_gen_property.py` | 2 | **absent** (588 insertions) | **this spec** |
      | `tests/verify/test_ratchet_monotonicity_property.py` | 1 | **absent** (861 insertions) | **this spec** |
      | `tests/uplift/test_aggregation_integrity_property.py` | 1 | **byte-identical to main** | `main`'s |

      **SEVEN OF THE NINE REPRODUCE LOCALLY, ON THE FIRST TRY, AT `HYPOTHESIS_PROFILE=dev`.**
      Not environment-dependent and not budget-dependent: `test_command_path_resolution_property`
      fails 5 of 8 at `dev` **and** 5 of 8 at `heavy`, so the falsifying inputs are found at ten
      examples. A hypothesis that the example budget was hiding them was formed and **refuted**
      by measurement rather than carried forward.

      The remaining two, in `test_ledger_gen_property.py`, are **deliberately unexamined
      locally**: `test_the_generated_ledger_round_trips_against_its_registry_execution` names a
      registry execution, and I-0 forbids `ledger_gen` locally in any form. CI is the only
      sanctioned place to read them, and their shapes (`assert 1 == 2`,
      `assert 'unavailable' == 'fail'`) are consistent with the inverted
      `ledger_gen`/`readme_gen` order session 4 measured — the same defect surfacing in a
      property instead of in a gate. Not confirmed.

      **FINDING 42 — THE PER-WAVE SWEEP CANNOT SEE THIS CLASS OF FAILURE, AND THAT IS A HOLE IN
      THE PROCEDURE RATHER THAN IN THE TESTS.** `SESSION_PROTOCOL.md`'s verification block says
      to run "one bounded `pytest` over the loci **that wave touched**", and no wave ever touched
      these four modules. So they were authored, reported as authored-and-diagnostics-clean, and
      executed by **nothing** — not by a sweep, because sweeps are scoped to changes, and not by
      CI, because `uplift-verify` was skipped. Six sessions of `HANDOFF.md` recorded this spec's
      property surface as "local evidence only"; for these modules **there was no local evidence
      either.** The procedure verifies what a session changed and never what it already had.
      Repair options belong to the operator: a periodic full-tree run in CI is what
      `uplift-verify` now is, so the cheapest repair may be to keep this job reachable and read
      it every session.

    - **SESSION 6 — ALL NINE REPAIRED, EIGHT VERIFIED LOCALLY, AND THE NINE WERE ELEVEN.
      THIS LEAF IS STILL `[ ]`: the job has not run since, so nothing has reached its end.**
      Re-measured at HEAD `58fc4e1`, run `34434951478` (job `102737971857`): `quality-gates`
      steps 1–17 success, **18 failure**, 19–23 skipped; `uplift-verify` step 4 success, step 5
      **failure**, step 6 skipped. The same nine.

      **Every falsifying example was read out of the step-5 log rather than guessed**, which is
      what made the diagnoses mechanical. Two of the nine are `ExceptionGroup`s carrying **two
      distinct failures each**, so the tree held **eleven** defects, not nine — a count nobody
      could have got from the summary line.

      | Test | Mechanism, as measured | Repaired at |
      |---|---|---|
      | `test_every_named_command…` (1 of 2) | two `external` extras both claimed root `pytest` | the generator |
      | `test_an_out_of_scope_step…` | same collision | the generator |
      | `test_a_discarded_exit_status…` | same collision | the generator |
      | `test_a_console_script…` | same collision | the generator |
      | `test_every_named_command…` (2 of 2) | `surface='makefile'`, `construct='leading-dash'` → `observed_commands == {}` | **the gate** |
      | `test_a_make_recipe_line…` | the `unresolvable-command` finding was missing on the same shape | **the gate** |
      | `test_aggregation_integrity…` (1 of 2) | `kpi_mean` last-bit mismatch | the test's reference |
      | `test_aggregation_integrity…` (2 of 2) | `kpi_std` last-bit mismatch | the test's reference |
      | `test_the_generated_ledger_round_trips…` | `sum(PASS rows) == status_counts["PASS"]` → `1 == 2` | the test |
      | `test_an_edit_inside_the_generated_region…` | `'unavailable' == 'fail'` | the test's mutation |
      | `test_the_committed_stryker_break_hole…` | `assert True is False` | a stale precondition |

      **FINDING 43 — A GATE DEFECT, AND ITS SHAPE IS THE ONE R6.14 EXISTS TO CATCH.** Hypothesis
      named `scripts/audit/command_path_truth.py:554` as the line run only by failing cases.
      `_MODULE_RE`'s negative lookbehind `(?<![\w./-])` refuses to match `python` behind a `-`,
      and the Makefile branch of `collect_named_commands` handed `named_commands_in` the **raw**
      recipe line while `_makefile_discarding_construct` was already prefix-aware. So on a
      `-`-prefixed recipe the gate reported the discarded exit status and extracted **zero
      commands**: R6.14's two independent clauses collapsed, and **Make's ignore-errors prefix
      concealed the unresolvable command it was ignoring.** That is precisely the pair of defects
      the audit found at `Makefile::deploy-gcp-verify`, where a leading `-` was one of the three
      swallows removed. Repaired with one reading of Make's prefix grammar (`split_make_prefix`)
      shared by both consumers, which also makes `-@`, `+-` and `@+-` read as swallows.
      `_MODULE_RE` is untouched, so no other surface gains a match. **`@` never had the defect** —
      it is not in the lookbehind's class — so the nine `@python -m scripts.audit.*` recipes in
      the committed Makefile read correctly all along; checked rather than assumed, because the
      opposite would have been a much larger finding. Committed report unchanged at **37 commands
      / 0 findings / pass**, predicted before the edit and measured after.

      **FINDING 44 — THE PROPERTY THAT SHOULD HAVE CAUGHT FINDING 43 WAS VACUOUS ON EXACTLY THAT
      INPUT.** `test_a_make_recipe_line_is_read_with_the_same_two_rules` asserted the findings
      **set** and never the command set, so a `-`-prefixed line contributing nothing passed
      whenever every named command happened to resolve. Only its sibling — which does compare
      commands — failed on the resolvable case. The Makefile test now asserts both, and asserts
      `report.commands` non-empty.

      **FINDING 45 — SESSION 1's OWN REPAIR CREATED THE `stryker-break` RED, AND THE COORDINATED
      CHANGE WAS HALF-APPLIED.** `ratchets.json` records `50`/`50` and
      `agrees_with_shipped: true`; the row PASSes with no findings. `verify_claims.py`'s C16
      docstring names the four sites its repair must touch — `CLAUDE.md`, `doc-number-pins.yaml`,
      the ratchet constant, and *this property module* — and still describes the hole as live
      (“**Expected FAIL on landing**”). Two sites moved, two did not, and
      `doc-number-pins.yaml`'s own comment already called the remediation “COMPLETE and verified
      mechanically”. **The prose in `verify_claims.py` is recorded, not edited:** it is another
      spec's, it is read by `doc_truth`, and I-0 forbids running `doc_truth` locally to see what
      the edit would move. Repaired here as a precondition correction — agreement is now
      re-derived from the two committed files rather than from the record, so the flag cannot
      outrun its subject, and detection stays proved by construction in the generated case that
      was always there. The aggregate is SKIP / exit 2 over **22** rows with no measurement
      behind them: 16 `status: unmeasured` **plus 6 that say `status: measured` with
      `measured_at: null`**, derived through one shared predicate because the sibling test's
      docstring said “twelve” and the file had grown past it.

      **FINDING 46 — THE RECORDED HYPOTHESIS ABOUT THE LEDGER-GEN FAILURES IS REFUTED, BY READING
      RATHER THAN BY RUNNING.** The `'unavailable' == 'fail'` failure has nothing to do with the
      `ledger_gen`/`readme_gen` order. `mutations[1]` was
      `clean.replace(f"\n{GENERATED_END}", "", 1)` — it deletes the **end marker**, not the last
      generated line, so `probe_text` correctly reports `unavailable` (its own docstring: “if the
      markers are missing it reports unavailable”) and the test demanded `fail`. Repaired by
      partition: three drift mutations that keep both markers must report `fail`, and marker
      removal is asserted separately as `unavailable` — a clause the file **gained**. The
      `assert 1 == 2` is the same class one level up: the matrix carries one row per **registered**
      id while `status_counts` tallies the whole execution, **foreign ids included**, and the
      falsifying scenario is `registered_ids=('C1',)` with results for C1 and C2. Two subjects,
      one number. Partitioned, partition asserted exhaustive, row set pinned non-empty. **Both
      repairs are authored and diagnostics-clean and were NOT executed** — that module names a
      registry execution and I-0 forbids it in any form. `ci.yml::uplift-verify`'s fast step is
      the only sanctioned reader.

      **FINDING 47 — THE NINTH FAILURE IS `main`'s AND IT GATED EVERYTHING BEHIND IT.** Repairing
      this spec's eight was **necessary but not sufficient**: one red anywhere in the fast step
      keeps step 6 skipped, so the slow surface could never have run while it stood. Adopted by
      explicit operator decision (precedent: session 3's decision 2), ownership re-proved
      mechanically first (`git cat-file -e origin/main:<f>` exit 0, `git diff origin/main` empty).
      `aggregate_arm` sorts completed runs by `(seed, arm)` for R2.5 order-invariance;
      `_reference_mean_std` reduced in **arrival** order and compared with `==`, so numpy's
      pairwise summation differed in the last bits. The falsifying case is three runs at
      **seed 0** with arms `''`, `'0'`, `''` — **the arm component alone reorders them**, which is
      why no amount of seed-uniqueness reasoning would have found it. The reference now mirrors
      the documented sort: exact equality retained, **no tolerance introduced**, no production
      file touched. And because a mirrored sort could **mask** a subject that stopped
      canonicalising, order-invariance is now asserted directly — scoped to key-distinct inputs,
      because `sorted` is stable and the aggregate is invariant **up to ties**, not “entirely” as
      `uplift/harness.py`'s docstring claims. That overclaim is recorded, not edited.

      **CONFLICT O — CF-13 IS ENFORCED OVER A SCOPE THAT EXCLUDES EVERY ONE OF ITS VIOLATIONS.**
      `.kiro/steering/local-compute-budget.md` and `NEXT_SESSION_PROMPT.md` say “**three**
      pre-existing violations still sit in `tests/uplift/` and `tests/verify/`”; `HANDOFF.md`
      names two files. Measured by **AST** over all **354** `test_*.py` in the tree: **41 files,
      56 hardcoded `@settings(max_examples=…)` sites** — 37 files under `tests/uplift/`, 4 under
      `tests/verify/`. And `tests/verify/test_property_inventory_consistency.py` **does** carry a
      mechanical CF-13 check, but it walks `DECLARED_INVENTORY`'s 37 declared paths, and the
      intersection of that inventory with the 41 offenders is **empty**: every violation sits in a
      tree the check never reads. The most severe is
      `tests/uplift/test_reproduction_stability_property.py`, pinned at **4** examples against
      CI's 500 and the ≥100 obligation. **Surfaced, not repaired:** these are
      `decision-integrity-uplift-proof`'s files, and adopting a second owner's debt in the same
      session as finding 47's adoption is the broad change defect 22 rejects. Widening the check's
      scope is the durable repair and is the operator's.

      **A METHOD NOTE, because it is the same defect one level up.** The first draft of this
      count was a regex over raw text and reported 62 sites in 43 files — including four inside
      `tests/verify/test_inventory_budget_rule_property.py`, whose own docstring says
      `max_examples` is never set there and which exists to make exactly this point: a regex over
      raw text cannot tell a subject from its context. It had matched the assignments that file
      **quotes as test data**. The count above is from the parse tree.

      **WHAT SESSION 6 VERIFIED, AND ONLY THIS.** 21 tests green at `HYPOTHESIS_PROFILE=dev` over
      the three locally-runnable repaired modules (8 + 11 + 2), plus 13 over the replay-metrics
      property. `mypy --strict --no-incremental` clean on both changed non-test modules. Lint and
      format debt proven byte-identical at HEAD by materialising the committed blobs — **zero
      added**. Six cheap gates `0/0/0/2/1/0`, census exit 0 **unchanged at 140/63/2/75**,
      `pin_extractor_truth` **14/14/14**, `gate_surface --check` **0** (coupling 4 checked, not
      assumed: a comment-only workflow edit whose step name did not change moved nothing).

      **WHAT IT DID NOT VERIFY.** That the fast step is green — nine reds were repaired and a
      tenth may sit behind them; session 2r's lesson has fired four times. The two
      `test_ledger_gen_property.py` repairs. `mypy --strict` over the four changed **test**
      modules: attempted twice, exceeded the local 120s ceiling both times, abandoned; no CI step
      type-checks `tests/`. The slow step, and therefore the slow half of Properties 38–60.

    - **SESSION 6 — OBSTRUCTION 2.5's OTHER HALF IS LANDED. DISPOSITION (b), BY EXPLICIT OPERATOR
      DECISION. `quality-gates` step 18 is predicted to exit 0; CI has not yet said so.**

      **The floor was not lowered (R2.10) and the step did not gain `continue-on-error`
      (finding 35).** No floor value moves: `read_floor` still returns `0.70`/`0.80`, so
      `ratchets.json`'s two `floors.*.value` extractors and `doc-number-pins.yaml`'s pins are
      untouched and `pin_extractor_truth` still reports 14/14/14 — verified, because a
      declaration that moved a value would move registry counts immediately before an owed
      regeneration.

      **The declaration lives in the configuration, not behind a flag.** A CLI flag would let any
      caller silence any floor from any workflow line with no record of who did it or why.
      `infrastructure/quality/replay-floors.yaml` now carries `unmeasurable_in_ci:` on
      `kv_cache_hit_rate` with `declared: true` plus a **prerequisite**, a **blocked_on** and a
      **procedure** — the shape `infrastructure/data/dataset-licences.yaml` uses for the M5 terms
      behind an acceptance gate an agent must not accept (C74). No JSON Schema governs
      `replay-floors.yaml` (checked: `scripts/validate_schemas.py` does not read it and
      `infrastructure/quality/schemas/` holds only three unrelated schemas), so coupling 3 does
      not fire and well-formedness is enforced by the gate that reads it.

      **The verdict gained a fourth state, and the declaration its own.** `Outcome` gains
      `DECLARED_UNMEASURABLE` — exit 0, printed `[SKIP]`, a distinct value in the JSON, because a
      SKIP is not a PASS **in the record** as well as in the exit code. `Declaration` is a
      *separate* enum (`absent` / `malformed` / `honoured` / `void`), because the floor and its
      declaration are different subjects and folding them into one value would make “the floor is
      satisfied” and “the declaration is still true” indistinguishable — the conflation this gate
      refuses everywhere else.

      **Three clauses stop it being a mute button, and the honesty burden is carried by all
      three.** (1) **Fail-closed**: a block that cannot state its prerequisite, reason and
      procedure — or that carries an unrecognised key — declares nothing, the floor stays
      `UNAVAILABLE`, and the gate still exits 2. It is still *reported* when the floor measured,
      because present-and-unusable is a defect an operator should see. (2) **Falsifiable**: the
      block names the observation whose presence voids it, so it states its own refutation. If a
      measurement is ever obtained the declaration is `VOID` and the gate **FAILS until the block
      is deleted**, whichever side of the floor the number fell on — C74's rule in the other
      direction, since a flag that can disagree with its own subject is a claim rather than
      evidence. A declaration that could not go stale would be permanent. (3) **It silences
      nothing else**: a measured breach on any floor still fails, an undeclared absence on any
      floor still exits 2, and an unreadable floor cannot be declared about at all.

      **The prediction, and how it was taken.** `evaluate()`'s existing `measurers` seam was given
      the two measurements CI itself reported — tier routing `1.0000` over 200/200, kv gauge with
      no samples — while trace resolution ran **for real** against the committed 200-trace corpus
      and the generator's own `0xCAFEBABE`. Result: `[SKIP] kv_cache_hit_rate`,
      `[OK] tier_routing_accuracy 1.0000 >= 0.8000`, aggregate `declared-unmeasurable`, **exit 0**.
      No replay was performed (I-0). **This predicts; it does not prove.** If the real replay
      measures differently the verdict differs, and steps 19–23 have never executed on this branch
      or on `main`, so what they report when they first run is unknown rather than green.

      **FINDING 48 — THE FOURTH OUTCOME REACHED A REGISTRY ROW BEFORE IT REACHED THE TABLE THAT
      TRANSLATES IT, AND THE TRAP WAS DOCUMENTED TWO LINES ABOVE THE TABLE. SELF-INFLICTED, FOUND
      BY CI, REPAIRED IN THE SAME SESSION.**

      The first push of disposition (b) **reddened `quality-gates` one step EARLIER than the step
      it was meant to unblock.** Measured on run `34448902996`, sha `b8eba2f`: step 17 **C56
      failure**, step 18 **skipped behind it** — so the repair was still unjudged and the
      obstruction had moved backwards from 18 to 17, which had been `success` since session 4.

      **Read, not guessed.** `doc_truth`'s own line names the drift:
      `headline-counts … FAIL (README claims 2, suite reports 3); SKIP (README claims 11, suite
      reports 10)` — one check moved SKIP → FAIL. Every pin, **including both `replay-floors.yaml`
      pins (0.70 and 0.80)**, reported `[OK]`, so the declaration had moved no pinned value. The
      `SYNAPSE Truth Gates` run for the same sha then named the check outright:
      `C71 … check raised KeyError: 'declared-unmeasurable'`.

      **`replay_metrics` is registered as C71**, and `verify_claims.GATE_STATUS` is the shared
      table **nineteen** registry rows use to translate a gate's own verdict string into the
      registry's `PASS`/`FAIL`/`SKIP` vocabulary. A new `Outcome` member is a schema change, and
      that table is one of the fixtures carrying it (**coupling 3**). Session 6's wave-2 sweep
      grepped for consumers of the persisted artifact and of `Outcome` **inside** the gate and its
      property test, and did not grep for a *verdict translation* — so `_run_check` coerced the
      `KeyError` to FAIL, the registry counts moved, the README headline drifted, and C56 went red.
      **The comment block immediately above `GATE_STATUS` already describes this exact failure
      mode**, in the words "the three-key mapping those rows used could not express the fourth
      state and would `KeyError` on it — coerced to FAIL by `_run_check`, so never silent, but a
      mapping defect reported as a gate defect". It was read after the fact, not before.

      **Repaired at the declaration that misleads the checker, never at the call site.**
      `"declared-unmeasurable": "SKIP"` joins the table, for the same reason `unavailable` maps
      there: a floor whose measurement is declared unobtainable has established nothing about that
      floor. **That is stricter than the gate's own exit code, deliberately** — the step exits 0 so
      it can gate on the floors it CAN measure, and the registry row says the other one went
      unmeasured, so the published PASS count never absorbs a declared absence. Two vocabularies,
      one fact, and the published counts carry the strict reading. None of the six forbidden
      repairs was used: no default, no `Any`, no `type: ignore`, no narrowed scope, no lowered
      floor, no `continue-on-error`.

      **And the obligation is now mechanical instead of remembered.**
      `test_every_outcome_this_gate_can_report_is_translatable_by_the_registry` asserts that every
      `Outcome` member is a `GATE_STATUS` key **and** that only a genuine pass maps to `PASS` — the
      second clause catching the worse mistake, a non-passing state absorbed into the published
      count. It imports `verify_claims` for a dict and never executes the registry, following the
      two sibling tests that already do. **If a fact is worth discovering twice, it is worth a
      gate**; this one was discovered by a CI run that cost a push.

      **Predicted before the second push, so it can be checked rather than believed:** C71
      `FAIL → SKIP`, the nested suite `FAIL 3 → 2` and `SKIP 10 → 11` matching the committed README
      headline, C56 → PASS, step 17 → success, and **step 18 executing for the first time**. The
      arithmetic cannot be confirmed locally — `doc_truth` and `verify_claims` are on the never-run
      list — so CI is the only reader. **C44 and C69 stay FAIL and are not this spec's**:
      `data_fabric/ingest` module liveness, and `core-purpose-uplift`'s placeholder checkpoint
      registry, which is the pre-existing `task_claim_truth` red the sweep has reported for six
      sessions.

    - **SESSION 6-CI — DISCHARGED. `[x]`. THE WHOLE CHAIN CLEARED IN ONE RUN, AND THE SLOW SURFACE
      EXECUTED FOR THE FIRST TIME IN THIS SPEC'S LIFE.** Measured on `ci.yml` run `34501159046`,
      sha `1f4e876`.

      **`quality-gates`: conclusion `success`, all 26 steps.** First time on this branch, and
      steps 20–22 had never executed on this branch **or on `main`**:

      | Step | Result | Obstruction |
      |---|---|---|
      | 17 C56 narrative-truth | **success** | 2 — the finding-48 regression cleared |
      | 18 Golden-trace replay metrics | **success** | **2.5 CLEARED** — its first execution ever |
      | 19 Unit tests (all gated trees) | **success** | **3 CLEARED** — `test_cognition_phase`'s repair (`bf8693f`) judged at last |
      | 20 Per-package coverage floor | **success** | **4 CLEARED** |
      | 21 Spec coverage | **success** | **4 CLEARED** |
      | 22 Contract tests | **success** | **4 CLEARED** |
      | 23 Upload coverage | **success** | — |

      **Step 18's own output, and it matches the hermetic prediction in substance line for line —
      except that the tier-routing number is now a REAL 200-trace replay rather than a substituted
      one:**

      ```
      replay-metrics: 200 golden traces from tests/eval/golden_traces (seed 0xCAFEBABE)
      [SKIP] kv_cache_hit_rate: measured DECLARED UNMEASURABLE, floor 0.7000 -- ... declared
             unmeasurable in CI -- blocked on A GitHub-hosted runner has no Ollama ...
      [OK]   tier_routing_accuracy: measured 1.0000 >= floor 0.8000 (200/200 traces classified)
      [SKIP] replay-metrics: every MEASURED value is at or above its floor; at least one floor is
             declared unmeasurable in CI with its reason and procedure. A SKIP is not a PASS (I-7)
      ```

      **`uplift-verify` step 5, the fast surface: `850 passed, 1 skipped, 28 deselected, 2 xpassed`
      — ZERO FAILED.** Obstruction 5 **CLEARED**, and the arithmetic confirms the repair exactly:
      `838 + 9 repaired + 3 new = 850`, and `9 failed -> 0`. **That includes the two
      `test_ledger_gen_property.py` repairs, which were authored blind** — I-0 forbids running that
      module locally, so this run is the only thing that could ever have judged them, and it did.

      **`uplift-verify` step 6, the slow surface: it RAN. `1 failed, 59 passed, 936 deselected` in
      421s.** Obstruction 6 is no longer "never executed": the six slow properties, the 623-test
      regression floor, the subprocess fault-injection probe and `digital_twin`'s 1000-scenario run
      have all now run. **The job's conclusion is `failure` on that one test, and it is not this
      spec's — proven on both sides**, which is the "read the subject of a failure before treating
      it as yours" rule:
      - `tests/uplift/test_preserved_baseline_regression.py` exists on `origin/main`; this branch
        modified it (45 insertions / 16 deletions) and **touched no `pinecone` line and no
        `_PAID_CLIENT_TARGETS` line** — the failing assertion is byte-identical to `main`'s;
      - `uplift/consensus_arm.py`, which constructs the client, is on `origin/main` and
        `git diff origin/main` is **empty** — byte-identical.

      **FINDING 49 — THE FULL DEPTH OF THE CHAIN IS NOW KNOWN, AND SESSION 2r's LESSON HELD TO THE
      END.** Six obstructions were cleared across sessions 2r–6 and each one revealed the next; the
      last two (3 and 4) had never executed anywhere, so nothing before this run could have said
      what they would report. **They reported green.** The lesson is not that the predictions were
      right — it is that four of the six could only be read after the one in front of it moved.

      **FINDING 50 — THE BLOCKING I-1 GATE IS FAIL-OPEN TO `pinecone`, AND THE ONLY THING THAT SAW
      IT WAS A PROPERTY THAT HAD NEVER RUN.** `ci.yml::quality-gates` step 13 ("No paid API imports
      (I-1 — BLOCKING)") greps a **deny-list**:
      `openai|anthropic|cohere|replicate` — and `pinecone` is not in it. The slow property asserts
      the stricter and correct I-1 reading — that no paid SDK client is **constructed** on a
      reproduction path — and it reports `paid client used: ['pinecone.Pinecone']`.
      `uplift/consensus_arm.py:618,655` records the intent as an honest degrade ("the semantic cache
      is constructed without a Pinecone key", "no Pinecone key -> the cache reports itself
      unavailable"), so the *degradation* is deliberate; what the property objects to is that the
      paid client is constructed at all. **A deny-list is fail-open by construction** — the prompt
      already carries that lesson about workflow triggers, and here it is again on an invariant
      gate. **Recorded, not repaired:** both sides are `main`'s, I-1 is the highest-precedence
      invariant after I-0, and the choice between widening the grep, moving to an allow-list, and
      changing what `consensus_arm` constructs is the operator's.

      **What this leaf's `discharge:` line asked for, point by point.** `quality-gates` reached its
      end — `success`, 26 of 26. `uplift-verify` **ran**, was not skipped, did not report nothing,
      and **reached its end**: both functional steps executed and neither was skipped behind the
      other. Properties 38–60's first full CI execution has been read. **So this spec's property
      surface is no longer local evidence only, and `HANDOFF.md` no longer has to say it is.**
    - _Requirements: —_

## Notes

- **The census is a command, not a paragraph.**
  `python -m scripts.audit.spec_ledger_census --next 30` derives the leaf total, the three mark
  buckets, the CI-gated set and the next authorable batch from this file. Add `--files` at session
  start: it reports open tasks whose named artifacts already exist, which is the session-1 failure
  mode. Its `absent-artifact` and `prior-art` lines are **informational** — this file legitimately
  names paths in order to reject them (tasks 7.1, 7.3, 8.2 each explain a rejected path), and a
  task that modifies an existing module will always show prior art.
- **`task_claim_truth` already reads this file, and it will bite at task 20.3.** That gate fails
  any record marked `[x]` that asserts a landed `published_checkpoints.json` entry the registry
  does not hold. Task 20.3's title matches its `lands-registry-entry` pattern and its body names
  the registry file, so 20.3 is already a *detected, pending* claim: ticking it requires the
  registry to hold a real validated non-placeholder entry. A `[~]` mark reads as unchecked there
  and is explicitly not a finding, which is why this ledger's third state is safe.
- Sub-tasks marked `*` are optional and can be skipped for a faster path; core implementation
  sub-tasks are never marked optional. Note that task 8.3 (the extractor-resolution mechanism)
  is **not** optional even though its property test at 8.4 is: skipping the mechanism leaves
  every threshold this phase commits pinned by a comparison that may compare nothing.
- Nothing in this plan is executed on the dev box (I-0). Every measurement, sweep, browser and
  container workload names its CI job. Authoring-and-diagnostics-clean is a legitimate reported
  result; "should pass" reported as "passes" is not (I-7). **A task in that state is `[~]` with a
  `discharge:` line, never `[x]`.**
- **Two checkpoints are operator actions, not authoring sessions.** Checkpoint A (tasks 6, 10.4,
  11) runs before task 12 is authored; checkpoint B (task 14) runs after task 13.7 lands and
  before E3 is authored. Both exist because tasks 11 and 14 can end this spec early, and a gate
  that fires after the work it guards is not a gate. `SESSION_PROTOCOL.md` carries the runbook.
- Slow-marked properties are placed only under the four paths `ci.yml::uplift-verify`'s slow
  step collects (`tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`,
  `digital_twin/tests`), because `-m "slow"` is a selector and not a path filter.
- Two conflicts are surfaced rather than resolved: the Property 47/48 extractor-clause
  attribution (task 4.5), and CF-13's disagreement between the I-0 steering file's "three
  pre-existing violations" and the tree's count (task 1.4 makes the gate produce the number
  instead of asserting one).
- Three same-commit couplings are load-bearing and each is stated in its own task: the
  `blocking-steps.yaml` step rename (3.2), the `blocking-steps.yaml` + `required-checks.yaml`
  declaration of the new sweep job (5.6), and the inventory gate's contradictory budget clauses
  (1.3 with 1.4).
- **Every new CI job in phases 3-5 carries the same coupling**, each stated in its own task:
  `uplift.yml::uplift-controls` (16.7), the `--gate C60` step inside `uplift-proof` (17.9), the
  checkpoint materialisation job (20.4), `uplift-proof`'s own overdue declaration (22.2),
  `integration.yml::chain-export` (23.9), and `publish-audit-anchor.yml`'s producing job (23.10).
  Because `uplift.yml` and `publish-audit-anchor.yml` carry only `schedule` and
  `workflow_dispatch`, their jobs are **structurally ineligible** for `required:` and are declared
  under `ineligible` with reason `post-merge` — the declaration, not branch protection, is what
  makes the gap visible.
- **Three schema changes move their pins in the same commit**, and each is a wide-but-shallow
  edit rather than a deep one: `UpliftArtifact`'s `schema_version` + `interval` moves the
  round-trip property's key set and every `tests/uplift/` fixture (15.1); `PoweredProof`'s
  interval moves both floor tests (17.2, 17.5); and C46's re-pointing moves the test that pins
  `evaluate` (18.3).
- **Two more conflicts surfaced rather than resolved**, joining the first half's two: R6.15 reads
  a repetition count and a rate tolerance from the Decision_Relevance_Record that task 8.1's
  content list does not include (16.3 amends ADR-055); and the design's committed-configuration
  list names no file for the R6.3 oracle tolerance or the `0.80` detection probability, so 16.2's
  path is this plan's choice and is flagged as such.
- **E4a's paths are reconciled, not re-implemented** (19.1). Task 7 derived them from neighbouring
  convention and said so; the design names different ones. One move, one implementation.
- Registration precedes generation, always (task 24). A ledger written before the last
  `@register` lands is a projection of a registry that no longer exists.

## Two open questions this plan does not resolve

**This plan assumes OQ-1 Answer A — the full sequence.** Answer A changes nothing in this
document; the ordering above is written for it, and Dependency-order item 4 ("R8 precedes R9")
holds inside E4 as written.

**Under Answer B — R1-R4 plus R9, deferring R5-R8 — four things change, none optional.**

1. **Phase 4 splits and E4's R8 half is deferred, not skipped** (I-7). R8.3, R8.4, R8.5 and R8.6
   become recorded deferrals with the reason stated. Tasks 19.4-19.8 and the M5 half of 19.1 move
   out of the near-term plan; task 18 and task 20 stay, because R9's mechanism defects are real
   independent of the training data.
2. **Task 20.3's registry entry publishes a synthetic-trained checkpoint**, so C46's detail must
   distinguish "a published model" from "a published model scored against a published
   leaderboard". Without that distinction the gate flip **over-claims**, which is the failure mode
   R8.18 exists to prevent in the benchmark's own reporting.
3. **Task 17.3 becomes the binding constraint, and task 25's pre-commitment hardens.** The short
   path must carry an explicit commitment to publish **no** headline uplift number at all —
   without E5's measurement resting on E2c's twin and E3's validated instrument, publishing
   produces exactly the meaningless zero Finding 4 predicts. Task 22.3's ratchet does not run.
4. **Task 10.5 and the first half's task 11 are still owed and still first.** Deferring R5
   wholesale would defer the falsification test for the very finding R5 exists to fix.

**OQ-4 must be answered before task 23.10 — E5's publication step — and task 23.1 is where the
answer lands.** The design narrows the field to Rekor or OpenTimestamps, because GitHub Releases
(ADR-033's decision) fails R10.1's independent-timestamp clause: a release asset carries no
timestamp the log itself asserts and can be deleted or replaced. Whichever is chosen, the
superseding **ADR-056** is committed **before the first anchor is published**, not after. The
disclosure question task 23.5 records — whether the chain presentation is attached to a public
release, given that it carries operational decision content — is the operator's and is
deliberately left open beside it.

**Preconditions this half inherits, and must confirm before task 15 begins:** the first half's
task 11 did not falsify Finding 4 (else R5 **and E3's scope** are re-cut first), and task 14 found
no Pareto-optimal single-objective policy (else the consensus experiment has no room to win and
**E3 must not run at all**).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "3.1", "4.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1", "3.2"] },
    { "id": 2, "tasks": ["1.4", "2.2", "3.3", "4.2"] },
    { "id": 3, "tasks": ["1.5", "1.6", "2.3", "3.4", "3.5", "4.3"] },
    { "id": 4, "tasks": ["4.4", "4.5", "5.1", "5.2"] },
    { "id": 5, "tasks": ["5.3", "5.4"] },
    { "id": 6, "tasks": ["5.5", "5.6"] },
    { "id": 7, "tasks": ["5.7", "5.8", "5.9", "5.10", "7.1", "8.1"] },
    { "id": 8, "tasks": ["7.2", "7.3", "8.2"] },
    { "id": 9, "tasks": ["7.4", "7.5", "8.3", "8.4", "9.1"] },
    { "id": 10, "tasks": ["9.2"] },
    { "id": 11, "tasks": ["9.3"] },
    { "id": 12, "tasks": ["9.4"] },
    { "id": 13, "tasks": ["9.5"] },
    { "id": 14, "tasks": ["9.6", "9.7"] },
    { "id": 15, "tasks": ["9.8", "9.9", "9.10", "9.11", "9.12", "10.1"] },
    { "id": 16, "tasks": ["10.2", "10.3"] },
    { "id": 17, "tasks": ["10.4", "10.5"] },
    { "id": 18, "tasks": ["10.6", "12.1"] },
    { "id": 19, "tasks": ["12.2", "12.3"] },
    { "id": 20, "tasks": ["12.4", "13.1"] },
    { "id": 21, "tasks": ["13.2", "13.3"] },
    { "id": 22, "tasks": ["13.4", "13.5"] },
    { "id": 23, "tasks": ["13.6", "13.7"] },
    { "id": 24, "tasks": ["15.1", "16.2", "16.3", "18.1", "19.1"] },
    { "id": 25, "tasks": ["15.2", "18.2", "19.2", "19.3", "20.1"] },
    { "id": 26, "tasks": ["15.5", "18.3", "20.2", "20.3"] },
    { "id": 27, "tasks": ["15.3", "15.4", "15.6", "16.1", "18.4", "18.5", "18.6", "19.4", "20.5"] },
    { "id": 28, "tasks": ["16.4", "19.5", "20.6", "20.7"] },
    { "id": 29, "tasks": ["16.5", "16.6", "17.1", "19.6", "20.8"] },
    { "id": 30, "tasks": ["16.7", "17.2", "19.7", "19.8"] },
    { "id": 31, "tasks": ["17.3", "17.4", "20.4"] },
    { "id": 32, "tasks": ["17.5", "17.7"] },
    { "id": 33, "tasks": ["17.6", "17.8", "17.9"] },
    { "id": 34, "tasks": ["22.1", "23.1", "23.2", "23.5"] },
    { "id": 35, "tasks": ["22.2", "23.3", "23.6"] },
    { "id": 36, "tasks": ["22.3", "23.4", "23.7", "23.8"] },
    { "id": 37, "tasks": ["23.9"] },
    { "id": 38, "tasks": ["23.10", "23.11"] },
    { "id": 39, "tasks": ["24.1"] },
    { "id": 40, "tasks": ["24.2"] }
  ]
}
```
