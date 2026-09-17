# Requirements Document

> **Decision Quality Proof** — the spec that makes SYNAPSE's central claim measurable.
> Source: `docs/decision-quality-proof-blueprint.md` (Parts I-VI).

## Introduction

`.kiro/specs/purpose-achievement-audit/` diagnosed. This spec proves. Its thesis, in one
sentence:

> Make the instruments provably able to fail, make the simulated world one where
> intelligence can pay, prove the measuring device can detect an effect, and only then
> measure — on non-synthetic data, against a published external benchmark.

Four findings drive it. Three are inherited from the audit. The fourth is new, is the most
consequential, and is **analytical rather than measured** — that limitation is stated here
and carried into the requirement that would falsify it.

### Finding 1 — the effort is inverted

Verification is larger than the thing verified. The blueprint records `scripts/` 17,962 +
`tests/` 15,126 = ~33k lines of proving against `agents/` 19,696 lines of intelligence, with
`frontend/src` at 32,087 lines the single largest mass. *Line counts carried from the
blueprint and NOT re-counted during authoring — treat the ratio as indicative, not
mechanical.* The apparatus for proving things about the system is more developed than the
system. This finding motivates the sequencing in **Dependency order** below; it produces no
requirement of its own, because "write less verification" is not an obligation this project
should take on.

### Finding 2 — one unpublished file gates the intelligence half

`infrastructure/ml/published_checkpoints.json` holds exactly one key, `__placeholder__`,
with `"status": "unpublished"` and an `"entry_shape_do_not_commit_as_truth"` template.
Verified consequences, each read directly from the tree:

| Consequence | Evidence |
| --- | --- |
| Every agent takes the degraded path | `agents/demand_prophet/inference/pipeline.py:332` sets `confidence = FALLBACK_CONFIDENCE` (`:38`, `= 0.5`, "documented I-7 floor when no calibrated model is present") |
| The real conformal machinery has no input | the live branch at `:334-335` computes `mean_rel_width` then `confidence = 1.0 / (1.0 + mean_rel_width)` and stamps `ConfidenceBasis.CONFORMAL_INTERVAL` (`:357`) — reachable only with a resolved checkpoint |
| Four gates SKIP | `docs/state/CURRENT.md` generated region: C38 `no training artifacts (run the smoke job)`, C40 same, C45 `all 8 probe(s) skipped`, C46 `DP_HF_REPO unset - no published model claimed (operator step)` |
| One gate FAILs | C69 `FAIL`, detail names `.kiro/specs/core-purpose-uplift/tasks.md:141` task 9 as marked complete while the registry "holds no validated non-placeholder entry for 'demand_prophet_hgt_tft'" |

A single absent artifact collapses five gates and the entire confidence contract. This is
requirement **R9**.

**Correction to the blueprint's second half of finding 2.** The blueprint also charges the
uplift gate with a live tautology — a committed `artifacts/uplift/result.json` carrying
`incomplete: true`, a gate reading only `headline_uplift`, `is_proven_uplift` unreachable,
and no workflow regenerating the artifact. **Three of those four facts are now stale.**
Verified during authoring:

- `artifacts/` does not exist in the working tree and `git ls-files artifacts` returns
  nothing — the committed artifact was removed.
- `scripts/audit/uplift_truth.py:494` calls `is_proven_uplift(proof, floor)` to derive
  `EXIT_PASS`; `:566` delegates a floor raise to `ratchet_to_measured`. `read_measured_uplift`
  no longer exists. `git grep` shows the predicate imported by `scripts/audit/uplift_truth.py`
  and `uplift/harness.py`, not only by tests.
- `.github/workflows/uplift.yml:116` runs `python -m uplift.cli --full --output
  artifacts/uplift/result.json` and `:123` runs `python -m scripts.audit.uplift_truth --check
  --require-fresh-run` — same job, harness before gate.

What remains true, and is what **R7** claims: `uplift/uplift_floor.py:47` still reads
`UPLIFT_FLOOR: float = 0.0`; C60's ledger row reads `SKIP — no uplift run was performed in
this job`; no powered run has ever been recorded; `uplift.yml` fires on a nightly cron and
`workflow_dispatch` only, and `infrastructure/quality/required-checks.yaml` declares no
entry for `.github/workflows/uplift.yml`. The plumbing landed. The measurement never ran,
and nothing requires it to.

### Finding 3 — zero of 64 gates have been proven able to fail

`infrastructure/quality/gate-mutations.yaml` declares falsifying mutations for 14 checks
(`completeness.declared_gates: 14`, `registry_size_at_authoring: 64`), records C67 as a
reviewed `reporting_tools` entry, and states of the remaining 49: "UNDECLARED:
`gate_fault_injection` names them and excludes them from PASS-eligibility, which is the
honest label and never a pass (I-7)."

C72's ledger row: `SKIP — 14 of 64 registered check(s) declare a falsification, 49
undeclared and excluded from PASS-eligibility; declaration is valid for 14 check(s) but no
falsification was probed; absence of proof is not a pass (I-7) - run with --sweep in CI`.
The file admits C72's row "can never report PASS outside `--sweep`", and a search of
`.github/workflows/*.yml` and `Makefile` for `gate_fault_injection` or `--sweep` returns
**no match**. The accountability apparatus is itself unaccountable. This is **R1**.

### Finding 4 — the twin does not reward intelligence (analytical, not measured)

Read `digital_twin/simulation/engine.py` as an operations researcher would. Every row below
was verified by reading the file:

| Property | Code | Consequence |
| --- | --- | --- |
| Demand | `_order_arrival`: `self._rng.exponential(1.0 / (self._config.order_arrival_rate * self._demand_mult))` | stationary Poisson |
| SKUs | `start()`: `{f"sku_{i}": 100.0 for i in range(10)}` | 10 independent, identical items |
| Lead time | `_restock`: `self._rng.uniform(30.0, 120.0) * self._lead_time_mult` | i.i.d., uncorrelated with demand |
| Delivery | `_delivery`: `self._rng.uniform(10.0, 45.0)` + `self._rng.normal(0.0, 3.0)` | no rider pool, no queue, no capacity coupling |
| Spoilage | `_spoilage`: `decay_rate = 0.01 * self._spoilage_rate_multiplier`, threshold `0.3`, reset to `1.0` | decoupled from order quantity |

`git grep "simpy.Resource\|simpy.Container\|simpy.Store\|PriorityResource"` across `*.py`
returns **no match**: there is no contended resource anywhere in the twin.

**The argument.** For stationary Poisson demand, independent identical items, i.i.d. lead
times uncorrelated with demand, and no capacity coupling between items, a base-stock
`(s, S)` policy is provably near-optimal — standard inventory theory. The Baseline_Arm's
`Par_Level_Reorder` (`.kiro/specs/decision-integrity-uplift-proof/` R1.2) **is** that
policy. So the baseline arm is the optimal policy for this world, and the consensus arm
cannot beat it except by chance.

**The consequence.** Run the uplift experiment on today's twin and it returns approximately
zero. That number would be read as *"the agents are not better."* It would in fact mean
*"the world is too easy to be better in."* Publishing it would be a true measurement of a
meaningless quantity — the most expensive mistake available to this project.

**The limitation, stated plainly.** This finding rests on reading `engine.py` plus inventory
theory. It is **analytical, not measured**, and it is therefore recorded as *plausible but
unverified*. **R5.1-R5.4 are the criteria that falsify it**: a measured `(s, S)`-regret test
on the **unmodified** twin, sequenced before any twin change. If regret is already materially
positive on today's twin, R5's remaining scope shrinks substantially and this spec should be
re-cut rather than executed as written.

**A sixth row, found during refinement and recorded in full under R5.** No KPI in the measured
vector is sensitive to stock availability at all: `_delivery` increments `orders_delivered`
**unconditionally** before clamping inventory at zero, so a stockout costs nothing measurable.
That strengthens this finding and changes what R5.1 must do first — see R5's verified reality,
R5.34 and R5.38.

### Corroborating external evidence, and its limits

The Makridakis M-Competitions' central replicated result across four decades is that
statistically sophisticated methods do not necessarily beat simpler ones on point accuracy,
while combination methods do outperform their components. M5 used roughly 42,000
hierarchical daily Walmart series (3,049 products x 10 stores x 3 states) and ran two
separate tracks — Accuracy and Uncertainty — with separate winners. *Source: the blueprint's
research, corroborated at authoring time against the public summary of the Makridakis
Competitions. The competition structure and the existence of the two tracks were confirmed;
the **numeric leaderboard scores were NOT verified** and MUST be confirmed at implementation
time (R8.5).*

Two consequences this spec carries:

1. **Do not expect consensus to dominate on point accuracy.** The plausible edge for a
   coordinating multi-agent system is decision quality under shocks, binding constraints,
   and multi-objective tradeoffs — precisely what `inject_shock` (`engine.py:156`) and
   `orchestrator/guardrails/rules.py::GuardrailEngine` exist for, and precisely what the
   current twin does not exercise. The uplift hypothesis must be framed that way or it is
   tested against the wrong prediction.
2. `git grep -i "m5\|walmart"` across `*.md`, `*.py`, `*.yaml` returns no dataset reference
   anywhere in the tree. M5 is a **new** dependency, and its licence terms must be confirmed
   before ingestion (R8.1).

### Relationship to prior specs — what this spec does NOT restate

- **`.kiro/specs/decision-integrity-uplift-proof/`** owns the Uplift_Harness, the arm
  interface, the Baseline_Policy suite (`Par_Level_Reorder`, `Static_Pricing`,
  `Greedy_Routing`, `No_Op_Disruption`), the Metric_Contract, the Adversarial_Scenario_Suite,
  the fidelity-disclosure rule, and `make prove-uplift`. All of that is a **precondition** of
  this spec, not a deliverable of it. `uplift/` exists (`harness.py`, `consensus_arm.py`,
  `contract.py`, `metric_contract.yaml`, `scenarios.py`, `kpi.py`, `fidelity.py`,
  `persistence.py`, `cli.py`).
- **`.kiro/specs/purpose-achievement-audit/`** owns the negative control. Its **R2.6** reads:
  "WHEN the Consensus_Arm is replaced in a scratch branch by a copy of the Baseline_Arm so
  the two arms are identical, THE Uplift_Harness at `MIN_POWERED_REPLICATES` replicates per
  arm SHALL report a headline uplift whose 95% interval contains zero." *Correction to the
  spec brief: the negative control is specified in `purpose-achievement-audit`, not in
  `decision-integrity-uplift-proof`, which contains no negative-control criterion.* Its R2.1,
  R2.2, R2.4, R2.5, R2.7, R2.8 and R2.10 also already specify the gate obligations this
  spec's R7 depends on. **R6.2 — the POSITIVE control — is a NEW obligation and closes a gap
  in that audit spec: nobody specified one.** Without it a zero result is uninterpretable.
- **`.kiro/specs/core-purpose-uplift/`** is the spec whose tasks 9 and 9.1 are marked `[x]`
  against the unchanged placeholder; that is the live C69 FAIL, and R9.7 is how it closes.
- The audit spec's `design.md` numbers correctness properties to 37. This spec's design phase
  continues from **38**.

### Scope, method, limits

- **Method.** Static reading, `grep`, and `git` metadata only. **No code was executed** while
  authoring — invariant **I-0** (`.kiro/steering/local-compute-budget.md`) forbids the
  category-2/3/4 workloads every claim here would need. Authoring-only is the honest result.
- **This spec states no measured number that does not already exist.** Every threshold it
  references is one a task **produces** and a gate **records**. Where a requirement depends
  on a measurement that does not yet exist, the criterion says so.
- **Working-tree caveat.** `git status --porcelain` reports 100 modified and 112 untracked
  paths — the predecessor spec's work is uncommitted. Five of the files R2 concerns are
  untracked-but-not-ignored (`git check-ignore` returns nothing for any of them), so
  committing them is a precondition for CI to see them at all.
- **Ledger caveat.** The gate statuses quoted from `docs/state/CURRENT.md`'s generated region
  come from a **Windows** execution. C44's `FAIL` there is the known Windows-only
  `FileNotFoundError` on a deep `frontend/node_modules/.pnpm` path and may PASS on Linux CI;
  that is a non-goal (see below), not a defect to chase.
- **What this spec cannot establish locally.** Whether any test passes; the live frontend
  type-check result; whether any gate's declared mutation is actually killed; whether GitHub
  branch protection marks any job required.

### Verdict vocabulary

*demonstrably achieved · bounded scope · substantially achieved · partially achieved ·
superficially achieved · implemented but not integrated · integrated but not validated ·
validated only under limited conditions · plausible but unverified · contradicted by
evidence · not achieved · not verifiable locally.*

## Glossary

- **Anchor_Publisher**: the external-log publication path for
  `orchestrator/audit/anchorer.py`'s `AnchorRecord`; `ANCHOR_DIR` (`:130`) resolves to
  `infrastructure/audit_anchors`, which does not exist in the tree.
- **Atlas_Console**: the React operator frontend under `frontend/src/`.
- **Baseline_Arm** / **Consensus_Arm** / **Baseline_Policy** / **Uplift_Harness** /
  **Metric_Contract** / **Fidelity_Report**: as defined in
  `.kiro/specs/decision-integrity-uplift-proof/requirements.md`. Not redefined here.
- **Check_Registry**: the 64 checks registered via `@register` in
  `scripts/audit/verify_claims.py`.
- **CI_Pipeline**: the GitHub Actions workflows under `.github/workflows/`.
- **Console_Property_Suite**: the five fast-check property files declared for Properties
  31-36 in `tests/verify/test_property_inventory_consistency.py:177-185`.
- **Decision_Relevance_Record**: `docs/adr/ADR-055-twin-decision-relevance.md`, to be
  authored. ADR-054 is the highest committed ADR, so 055 is the next free identifier.
- **Demand_Forecaster**: the `demand_prophet` agent, its `inference/pipeline.py` and
  `training/train.py`.
- **Example_Budget_Profile**: the Hypothesis profile set in the root `conftest.py`
  (`dev`=10, `heavy`=100, `default`=500, `ci`=500, `nightly`=5000, selected by
  `HYPOTHESIS_PROFILE`) and the fast-check analogue this spec introduces.
- **Falsification_Sweep**: `python -m scripts.audit.gate_fault_injection --sweep`. The module
  exists at `scripts/audit/gate_fault_injection.py`; no workflow invokes it. Its unit of work
  is a declared mutation **operator**, not a check: 14 checks declare 16 operators.
- **Headline_Generator**: the `--write` projection path — `scripts/audit/ledger_gen.py`
  extended to `README.md`. The marker literals it obeys are owned by
  `scripts/audit/gate_surface.py:116-117` (`GENERATED_BEGIN` / `GENERATED_END`).
- **Model_Registry**: `packages/synapse_common/model_registry.py::ModelRegistry`, the
  production serving-path resolver R9.1 and R9.2 are stated against.
- **Oracle_Arm**: a new arm that plays the analytically optimal policy for a deliberately
  injected, known-exploitable structure. Does not exist.
- **Power_Report**: the effect-size-versus-detection-probability curve for the
  Uplift_Harness at a given replicate count. Does not exist.
- **Property_Inventory_Gate**: `tests/verify/test_property_inventory_consistency.py`.
- **Published_Checkpoint_Registry**: `infrastructure/ml/published_checkpoints.json`.
- **Real_Data_Feed**: the M5 (Walmart) hierarchical daily-sales dataset, once ingested.
  *Note the straddle:* this definition names a **training-row** source, while the tree's only
  provenance-bearing external seam, `ExternalFeedSource`, reads **Kafka topics** into
  `WorldState`. R8.3 and R8.4 touch two unrelated ingestion paths, and only the world seam
  carries a provenance field today.
- **Truth_Ledger**: `docs/state/CURRENT.md`, and specifically the region between
  `<!-- generated:begin -->` (`:15`) and `<!-- generated:end -->` (`:120`).
- **Uplift_Gate**: check C60, `scripts/audit/uplift_truth.py`.
- **Workflow_Shape_Gate**: check C64, `scripts/audit/workflow_shape_truth.py`, whose advisory
  markers are `("ADVISORY", "informational")` (`:88`).
- **World_Twin**: `digital_twin/simulation/engine.py::SupplyChainSimulation` plus
  `digital_twin/world/runtime.py::WorldRuntime`.

---

## Requirements

### Requirement 1: No gate has been proven able to fail

**User Story:** As the operator who trusts a green registry, I want each gate proven to fail
when its subject breaks, so that a PASS count describes enforcement rather than execution.

**The verified reality.** Finding 3 above. Additionally, `gate-mutations.yaml`'s own notes
disclose that a sweep run today cannot probe all fourteen: `falsifies()` reports
`indeterminate` when the gate does not pass on the unmutated copy, "because a check that is
already red proves nothing by staying red." Cross-referencing the declared set against the
ledger's current statuses:

| Baseline status | Checks | Probeable today |
| --- | --- | --- |
| `PASS` | C16, C28, C56, C57, C61, C65, C66, C68 | yes — 8 |
| `FAIL` | C44, C69 | no — indeterminate |
| `SKIP` | C60, C70, C71, C72 | no — indeterminate (C72 structurally, by design) |

So the honest expectation, stated before the run: **at most 8 of 14 can be probed on this
tree**. A survivor is a gate that does not enforce; it is a defect against that gate, not
against the sweep.

**The unit of work is an operator, not a check.** The 14 declared checks carry **16** declared
mutation operators, counted from the committed file — C44 and C56 declare two each. Per-check
reporting cannot identify **which of C44's two mutations survived**, so every count and every
failure message in the criteria below is per-operator.

**The outcome vocabulary is four values, not three.**
`Outcome = Literal["falsified", "survived", "indeterminate", "not-applied"]`
(`scripts/audit/gate_fault_injection.py:364`), pinned as `OUTCOMES` in
`tests/verify/test_declared_falsification_property.py:112-118`, whose comment records why the
set is closed: "A fifth would fall through the classifier's precedence chain into `survived`,
so the closed set is pinned here." The report field is `falsified_ids`. `killed` is **mutmut's**
word and does not appear in this harness.
`not-applied` is the fourth state, reported when a mutation cannot be applied or would change
nothing, so that "the harness must not be able to convert its own defect into a verdict about
the gate" (`gate_fault_injection.py:992-994`).

**What already runs, stated precisely.**
`tests/verify/test_declared_falsification_property.py:1298`
(`@pytest.mark.slow test_a_real_subprocess_probe_agrees_with_the_declared_decision_table`)
copies the real tree, runs the gate unmutated, applies `COMMITTED_OPERATORS[0]`, and runs the
gate again in a real subprocess. That module's own header records where it executes:
`ci.yml::uplift-verify`'s slow step, `pytest tests/uplift tests/verify -m "slow"` at
`HYPOTHESIS_PROFILE=heavy`. So **one** committed operator is already probed against a real gate
process in CI. It asserts that the classifier agrees with the declared decision table —
**not** that any gate is falsified. The correct statement of the gap is therefore: the declared
set is never swept, and no exit status derived from a sweep gates any job.

**The known survivor, correctly attributed.** `gate-mutations.yaml` records a survivor shape
for C16 at `26`, but **nobody declared that mutation**: C16's declared operator sets
`$.thresholds.break` to `10`, which must fire. The declared operator disclosed as a survivor
today is C28's `zero-a-floor` — "Falsifies C28 only once `coverage_per_package.py
--require-measured-floors` lands (task 4.1). Before that, C28 asserts floors >= 0 and a 0.0
floor satisfies it." C28's baseline is `PASS`, so it **is** probeable, and the honest
expectation is therefore that of the 8 probeable checks **C28 reports `survived`, making the
first gating run expected-red** — a defect against C28, not against the sweep.

**Cost, derived from the committed declaration rather than measured.** A complete sweep spawns
14 baseline + 16 operator = **30 gate subprocesses**. The committed per-subprocess bound is
`DEFAULT_TIMEOUT_S: Final[float] = 900.0` (`gate_fault_injection.py:118`), and the candidate
host `ci.yml::uplift-verify` carries `timeout-minutes: 60` while already running two property
suites. No duration is stated here because none was measured; what the committed bounds admit
in the worst case exceeds the committed job bound, and that is a scheduling decision the design
phase owes an answer to.

**Why it matters.** This is the earliest correctable cause in the repository. Every number
produced by every later requirement is only as trustworthy as the gate that reports it.

#### Acceptance Criteria

1. WHEN a commit is pushed to `main`, THE CI_Pipeline SHALL execute the Falsification_Sweep
   in a step whose exit status gates the job.
2. THE Falsification_Sweep step SHALL carry no `continue-on-error` setting and no construct
   that discards its exit status.
3. WHEN the Falsification_Sweep runs, THE Falsification_Sweep SHALL report, for each declared
   mutation operator it probed, the check identifier, the operator identifier, and exactly one
   outcome from `falsified`, `survived`, `indeterminate`, `not-applied`.
4. IF a probed mutation operator reports `survived` or `not-applied`, THEN THE
   Falsification_Sweep SHALL exit non-zero naming that check identifier and that operator
   identifier.
5. IF a probed mutation operator reports `indeterminate`, THEN THE Falsification_Sweep SHALL
   report which condition made it indeterminate: a non-passing unmutated baseline, naming that
   baseline's exit status; a timeout; or a gate subprocess that could not be started.
6. IF any probed mutation operator declared for a check reports an outcome other than
   `falsified`, THEN THE Falsification_Sweep SHALL exclude that check from the falsified-check
   count.
7. THE Falsification_Sweep SHALL report the number of declared mutation operators it probed and
   the number declared, counted in the same unit.
8. WHERE a declared falsification was not probed, THE Falsification_Sweep SHALL report that
   check as unproven, because absence of proof is never a pass (I-7).
9. WHERE a registered check declares no falsification, THE Falsification_Sweep SHALL report
   that check as undeclared.
10. WHERE a registered check declares no falsification, THE Falsification_Sweep SHALL exclude
    that check from PASS-eligibility.
11. IF the Falsification_Sweep cannot start, exceeds the committed per-gate subprocess
    wall-clock bound (`scripts/audit/gate_fault_injection.py::DEFAULT_TIMEOUT_S`), is terminated
    by a signal, or emits an unparseable report, THEN THE gating step SHALL record a non-passing
    result.
12. WHEN the Falsification_Sweep completes in a job, THE C72 row reported by that same job SHALL
    state the probed count, the falsified-check count, and the unproven count observed in that
    run rather than the fixed `no falsification was probed` detail.
13. THE Falsification_Sweep SHALL execute on Linux CI runners only, because it copies the
    tree and runs gates as subprocesses, which is a category-2/3 workload under I-0
    (precedent: E-S13-05, `mutmut` validated on CI and never on the Windows box).
14. THE job that executes the Falsification_Sweep SHALL be named in
    `infrastructure/quality/required-checks.yaml`, in the `required` set if it reports on every
    pull request targeting `main` and in the `ineligible` set with its recorded reason otherwise,
    so whether a surviving falsification blocks a merge is a declared fact rather than an absent
    one.
15. WHEN the CI_Pipeline executes the Falsification_Sweep in the gating step, THE
    Falsification_Sweep SHALL probe every mutation operator declared in
    `infrastructure/quality/gate-mutations.yaml`.
16. IF the Falsification_Sweep is invoked with the unmutated baseline run suppressed, THEN THE
    Falsification_Sweep SHALL record a non-passing result naming baseline suppression as the
    reason, because without a baseline an already-red gate reads as falsified.

**Verdict: implemented but not integrated.** The harness and the declaration file are real
and carefully built; the declared set is never swept, and no exit status derived from a sweep
gates any job.

**Falsification.** *What would prove this finding false:* a workflow step invoking
`gate_fault_injection --sweep` whose exit code gates a job. *Attempted:* searched every file
under `.github/workflows/` and `Makefile` for `gate_fault_injection` and `--sweep`; no match.
The closest thing in the tree is the single-operator subprocess probe at
`test_declared_falsification_property.py:1298`, which runs inside `ci.yml::uplift-verify` and
asserts classifier agreement rather than gate falsification — so it does not falsify the
finding. **[falsification attempted]**

---

### Requirement 2: The console's newest verification has never been compiled or executed

**User Story:** As a reviewer, I want the five authored console property files actually
type-checked and run, so that "authored" stops being read as "verified".

**The verified reality.** `tests/verify/test_property_inventory_consistency.py:177-185`
declares five fast-check property files for Properties 31-36:

- `frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts` (31)
- `frontend/spec/effectiveness/__tests__/scorecard-completeness.property.test.ts` (32)
- `frontend/spec/effectiveness/__tests__/ratchet-sensitivity.property.test.ts` (33)
- `frontend/spec/effectiveness/__tests__/interruption-precision-responsiveness.property.test.ts` (34)
- `frontend/spec/effectiveness/__tests__/baseline-measurement.property.test.ts` (36)

*The declaration span is not five TypeScript lines:* `:184` inside it is Property 35's
**Python** entry. "Five fast-check property files for Properties 31-36" is accurate; "lines
177-185 are the five files" would not be.

All five exist on disk and all five are **untracked**: `git ls-files` lists none of them,
`git status --porcelain` reports each as `??`, and `git check-ignore` returns nothing, so they
are uncommitted rather than ignored. *The per-file line counts carried in earlier drafts
(469 / 780 / 575 / 752 / 661, ~3,237 total) were **not** re-verified and are recorded as
indicative only.*

`frontend/vitest.config.ts:36-40` declares **three** include patterns, not two —
`src/**/*.{test,spec}.{ts,tsx}`, `spec/effectiveness/__tests__/**/*.{test,spec}.{ts,tsx}`, and
`spec/contract-fidelity/__tests__/**/*.{test,spec}.{ts,tsx}` (`:39`). The first two cover all
five declared files **only if `**` matches zero path segments** — true under picomatch, but
unconfirmed without executing vitest. Collection coverage is therefore **probable, not
proven**, which is exactly why R2.7 and R2.8 are stated against a run record rather than
against the config.

*The run record R2.7, R2.8, R2.14 and R2.16 are stated against already exists as a
configuration.* `vitest.config.ts` declares `reporters: ["default", "json"]` and
`outputFile: { json: "artifacts/test-reports/vitest.json" }`, and its own comment records why:
`frontend/spec/check_fe_invariants.py` "gates the registry on EXECUTED, non-skipped assertions,
so it needs the machine-readable run record — file existence proves nothing." That path is
gitignored and deliberately outside Playwright's `outputDir`, so the record is a CI product and
never a committed one — which is what makes R2.12's "no CI run record exists" the live state
rather than a hypothetical.

`frontend/tsconfig.json`'s `include` covers `src`, the four config files, and exactly two files
under `spec/effectiveness/` (`harness.ts` and `e2e-entry.ts`) — the wording
`frontend.yml:75-88` already uses. `frontend/tsconfig.spec.json`
(`include: ["spec/**/*.ts", "tests/**/*.ts"]`) exists precisely to cover the rest;
`frontend.yml` runs `pnpm typecheck` in `quality` (`:48`) and `pnpm typecheck:spec` in a
deliberately standalone `spec-typecheck` job (`:114`).

The coupling that makes this urgent: Property 31 sits under `src/`, so it is inside
`pnpm build`'s `tsc --noEmit`. **Confirmed** in `frontend.yml`: `build` needs `quality`
(`:120`), `fe-invariants` needs `[quality, e2e, e2e-visual, e2e-harness]` (`:182`), and `e2e`
needs `build` (`:221`). **Not confirmed** during authoring: the arrows from `build` to
`e2e-visual`, `e2e-harness` and `mobile-lighthouse`, and from `effectiveness-ratchet` to
`e2e-harness`. So "one type error in that one file skips the entire console-effectiveness
spine" is **partially verified** — the `fe-invariants` half is proven, the remainder is carried
from `tsconfig.spec.json`'s own header, which states the expectation honestly: "EXPECTED RED ON
THE FIRST CI RUN, and that is honest (I-7)."

#### Acceptance Criteria

1. THE five files named in the Property_Inventory_Gate's declaration SHALL be committed to
   version control, because an untracked file is invisible to the CI_Pipeline.
2. WHEN the CI_Pipeline runs the frontend quality job, THE CI_Pipeline SHALL execute
   `pnpm typecheck`.
3. THE step that executes `pnpm typecheck` SHALL carry no `continue-on-error` setting and no
   construct that discards its exit status.
4. WHEN the CI_Pipeline runs the spec type-check job, THE CI_Pipeline SHALL execute
   `pnpm typecheck:spec`.
5. THE step that executes `pnpm typecheck:spec` SHALL carry no `continue-on-error` setting and
   no construct that discards its exit status.
6. WHEN the CI_Pipeline runs the console test suite, THE CI_Pipeline SHALL execute all five
   declared property files.
7. WHEN the console test suite completes, THE CI_Pipeline SHALL record an executed, non-skipped
   assertion count for each of the five declared property files in the machine-readable run
   record the FE-INV attestation gate reads.
8. IF the console test run record holds no entry for a declared property file, or holds an entry
   reporting zero executed assertions for it, THEN THE job SHALL record a non-passing result,
   because a file that matches no include pattern produces no entry at all rather than a zero
   count.
9. IF a property reports a shrunk counterexample, THEN THE job SHALL record a non-passing result
   naming the property file, the property title, and the minimal failing input.
10. IF a property reports a shrunk counterexample, THEN THE property's generators and assertions
    SHALL remain unweakened.
11. IF `pnpm typecheck` fails, THEN THE gate surface report SHALL render every job that did not
    execute as a consequence as NOT EXECUTED rather than as a pass.
12. IF no CI run record exists for a declared property file, THEN every document referring to
    that file SHALL describe it as authored but not executed, because absence of proof is never
    a pass (I-7).
13. WHERE a local diagnostics probe reported no error for a declared property file, THAT probe
    SHALL be reported as inconclusive rather than as evidence that the file passes, because
    `getDiagnostics` returns no TypeScript signal in this workspace.
14. IF the console test run record reports any test in a declared property file as skipped or
    todo, THEN THE job SHALL record a non-passing result, because a skipped assertion is never a
    pass (I-7).
15. WHILE the spec type-check job reports one or more TypeScript errors, THE declared property
    files under `frontend/spec/` SHALL be reported as not type-checked, because
    `tsconfig.spec.json`'s documented expectation of red on the first run is a prediction, not a
    dispensation.
16. IF the console test run record is absent or unparseable, THEN THE job SHALL record a
    non-passing result for all five declared property files, because absence of proof is never a
    pass (I-7).

**Verdict: not verifiable locally.** I-0 forbids the `pnpm install` + full-project `tsc` +
vitest run this requires; the first CI run is the first signal.

**Falsification.** *What would prove this finding false:* a CI run record showing executed
assertion counts for these five files. *Attempted:* checked git tracking, the vitest include
patterns, and both tsconfig projects. **[falsification attempted]**

---

### Requirement 3: The TypeScript example budget is hardcoded, and a gate mandates it

**User Story:** As the developer running tests on a thermally throttling laptop, I want the
fast-check budget inherited from a profile, so that a local run is cheap and a CI run is
thorough — the contract Hypothesis already honours.

**The verified reality.** The root `conftest.py:43-58` registers `dev`=10, `heavy`=100,
`default`=500, `ci`=500 and `nightly`=5000 and selects with
`settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))`. That inheritance is
the entire I-0 mechanism, and the Property_Inventory_Gate enforces it for Python: line 599,
`test_no_python_property_test_in_this_feature_hardcodes_max_examples`, fails on any
`max_examples =` assignment because "a hardcoded value overrides the root `conftest.py`
profile in both directions".

For TypeScript the same file takes the opposite position. Lines 92-95: "fast-check's
equivalent of `max_examples` is `numRuns`, and fast-check has no profile mechanism to inherit
it from, so all five files state `{ numRuns: 100 }` in place". **The enforcing clause is
`test_every_typescript_property_test_states_a_run_budget_of_at_least_100` at `:624`** — not
`test_every_fast_check_property_declares_numRuns` at `:625`, which does not exist. Its
mechanics, read line by line: `_NUM_RUNS_RE` (`:236`) collects every `numRuns: <digits>`;
`:637` fails a file with **no** match; `:639` fails any value **below** `MIN_NUM_RUNS`
(`:237`, `= 100`).

**The `configureGlobal` evidence is weaker than earlier stated and is downgraded here.**
`git grep "configureGlobal" -- frontend` returns no match, but `git grep` reads **tracked**
files only and all five declared files are untracked, so they were never in scope of that
search. A direct read confirms absence in **one** of the five; the other four are
**unverified**. The corrected premise still holds — `fc.configureGlobal` is the mechanism and a
per-call `numRuns` overrides it, so adding a global alone changes nothing — but it now rests on
one confirmed file and four unverified ones. The `numRuns` occurrence counts are downgraded the
same way: only `degradation-rendering.property.test.ts` was re-verified, at exactly 10
occurrences, all `{ numRuns: 100 }`.

**Where R3.1 lands, verified.** `frontend/src/test/setup.ts` exists and is wired as
`setupFiles: ["./src/test/setup.ts"]` in `frontend/vitest.config.ts:26`, so every collected
console test already loads it. It contains **no fast-check configuration at all** today — no
`fast-check` import and no `configureGlobal` — so R3.1 is a net addition to that file rather
than a change to an existing knob.

**Two decisions recorded as decisions, not as clarifications.** *(a)* Reusing
`HYPOTHESIS_PROFILE` as the single budget knob for **both** language halves is a choice this
spec makes; the tree contains no cross-language profile variable today, and an alternative
(a separate `FC_PROFILE`) would let the two halves drift. *(b)* R3.2 defaults the fast-check
count to `dev`=10 where the Python side defaults to `default`=500. That asymmetry is
deliberate and is in service of I-0: an unset variable is the local case, and the local case
must be the cheap one. The CI case is explicit and is bounded from below by R3.5.

**A conflict this spec surfaces rather than resolves.** The I-0 steering file records "three
pre-existing violations still sit in `tests/uplift/` and `tests/verify/`". The tree contradicts
that count. Under `tests/verify/` there are **four** assignment sites
(`test_headline_count_pin_property.py:104`, `test_headline_pin_skip_property.py:141`,
`test_published_checkpoint_gate_property.py:137`,
`test_verify_claims_status_partition_property.py:96`). Under `tests/uplift/` there are **at
least 20** sites across **at least 12** files with values from 50 to 300 (confirmed:
`test_uplift_floor_monotonic_ratchet_property.py:140` `max_examples=300`,
`test_effect_size_property.py:69` `max_examples=300`). The gate's own docstring names six files
plus "roughly fifty more values across `tests/uplift`". **No total is stated here.** R3.6 makes
the gate produce it, which is the only count that will not go stale — and the discrepancy
between the steering file and the tree is recorded as a conflict, not silently resolved in
either direction.

**Why it matters.** A gate that mandates a hardcoded 100-example budget on a 16 GB throttling
laptop is a gate that mandates an I-0 violation. The asymmetry between the two halves of the
same file is the defect.

#### Acceptance Criteria

1. THE Example_Budget_Profile SHALL set the fast-check example count once, globally, in the
   vitest setup file, resolving it from the same `HYPOTHESIS_PROFILE` profile names the root
   `conftest.py` registers (`dev`=10, `heavy`=100, `ci`/`default`=500, `nightly`=5000).
2. IF the profile environment variable is unset or names no registered profile, THEN THE
   Example_Budget_Profile SHALL resolve the fast-check example count to the `dev` profile count
   of 10.
3. THE five declared property files SHALL carry no per-call `numRuns` option, because a
   per-call value overrides the global.
4. WHEN the Property_Inventory_Gate runs, THE Property_Inventory_Gate SHALL fail on any
   `numRuns` option appearing in a declared TypeScript property file, whether literal or
   computed, mirroring its `max_examples` rule for Python.
5. WHEN the CI_Pipeline runs the console test suite, THE effective fast-check example count
   SHALL be at least 100, the value `MIN_NUM_RUNS` holds in the Property_Inventory_Gate today.
6. WHEN the Property_Inventory_Gate runs, THE Property_Inventory_Gate SHALL report a count of
   `max_examples` assignments under `tests/uplift/` and `tests/verify/` derived from that scan,
   counting only assignments in executable code and excluding occurrences inside docstrings and
   comments. *(The gate's regex `_HARDCODED_MAX_EXAMPLES_RE` — `max_examples[ \t]*=(?!=)` at
   `:233` — currently matches a docstring line at
   `tests/uplift/test_baseline_determinism_conformance.py:22`, so without a counting rule two
   testers get two totals.)*
7. IF a `max_examples` assignment remains under `tests/uplift/` or `tests/verify/`, THEN THE
   Property_Inventory_Gate SHALL name each offending file and the line of each assignment. *No
   count is asserted here: the steering file's "three" and the tree disagree, and that conflict
   is recorded in the verified reality above.*
8. WHEN the Property_Inventory_Gate's TypeScript budget clause is replaced by the no-`numRuns`
   rule, THE clause requiring a declared `numRuns` of at least `MIN_NUM_RUNS` and the clause
   failing a file that declares no `numRuns` SHALL be removed in the same commit, because the two
   rules are contradictory and a half-move leaves the gate failing on the files R3.3 has just
   corrected.
9. WHEN the CI_Pipeline runs the console test suite, THE run record SHALL report the effective
   fast-check example count that was applied, because a global that failed to load is otherwise
   indistinguishable from one that applied. *fast-check's own fallback `numRuns` is reportedly
   100 — **not** confirmed against the installed library — so a silently failed global would
   still produce the CI-legal count while costing a local laptop ten times the intended budget,
   with no signal.*

**Known residual, recorded rather than legislated.** Four pre-existing effectiveness property
tests (`fixture-factory`, `harness-determinism`, `schema-less`, `unhandled-path`) carry their own
`numRuns` and sit **outside** R3's declared scope. After R3.1 lands they still override the
global locally. Widening the gate to cover them would contradict its own recorded reasoning: "A
check born red for another feature's debt gets disabled, and a disabled check is worse than no
check."

**Verdict: contradicted by evidence.** The gate enforces what the steering invariant forbids.

---

### Requirement 4: Ten non-propagating steps carry no advisory label, and a published headline is transcribed by hand

**User Story:** As a maintainer, I want every non-propagating step either fixed or honestly
labelled, and every published count generated, so that red means red and no document is bent
to make a gate green.

**The verified reality — two distinct defects.**

*(a) C64.* Ledger row: `C64 | Declared-blocking workflow steps propagate their exit status |
FAIL | unlabelled-advisory=10`.

**C64's verdict is the disjunction of four rules**, not one: `blocking-discards`,
`blocking-unresolved`, `chain-verifier-discards` and `unlabelled-advisory`
(`workflow_shape_truth.py::_RULES`), plus the AD-12 bundle assertion. Three consequences follow
directly: R4.1 as previously written could pass while C64 stayed FAIL, because it covered only
`unlabelled-advisory`; **R4.3's fix path creates `blocking-unresolved` findings**; and R4.1's
widening to every rule **subsumes the anti-evasion case**, because a declared-blocking step that
discards is reported as `blocking-discards` whatever its name carries, so renaming a declared
step to add a marker word buys nothing.

`workflow_shape_truth.py:88` reads exactly
`ADVISORY_MARKERS: Final[tuple[str, ...]] = ("ADVISORY", "informational")`, mirrored in
`tests/verify/strategies.py:433` so a drift in either is visible. Three properties of the real
rule the requirement must state: matching is **case-insensitive substring**; a **job-scoped**
`continue-on-error` is excused by the **job's** display name rather than the step's — precedent
`ci.yml`'s `v4-compliance`, whose steps carry no marker at all while its display name is
`v4.0 Definitive Edition Compliance (informational)` (`:378`) and its `continue-on-error: true`
sits at `:381`; and such a job is reported once as `(all steps)`.

`infrastructure/quality/blocking-steps.yaml` declares **8 declaration entries** — not 8 steps —
covering 21 named steps plus three whole jobs via `all_steps: true`; the gate prints
"declarations : 8 blocking entries". It records four entries under
`unlabelled_discarding_steps` and states its own limitation: those entries are "documentation of
known obligations" — nothing reads that section as a pass. It also records why no rename
happened: "`steps:` above declares step names by string, and a rename makes those declarations
resolve to no step — which this same gate fails on. The fix is an operator decision, not a
drive-by edit." The rename and the declaration must therefore move in one commit.

**The ledger row reads `unlabelled-advisory=10`; static re-derivation at authoring time yields
9, across 6 files.** Named, so the fix is actionable rather than a hunt:

*Recorded in `blocking-steps.yaml` and still findings (3):* `ci.yml:210`
`quality-gates`::"Contract tests" (`|| echo` at `:212`); `ci.yml` `training-smoke`::"Measure
per-package coverage under full ML stack (binds the 0.0 floors)" (`continue-on-error: true` at
`:553` plus `|| true` at `:562`); `frontend.yml:135` `build`::"Size budget" (`|| true` at
`:136`).

*Recorded nowhere (6) — these are the six R4.1, R4.2 and R4.3 need named:* `security.yml:67`
`security`::"Secret detection via gitleaks" (`continue-on-error: true` at `:71`);
`terraform-validate.yml:78` `validate`::"tflint (optional, won't block)"
(`continue-on-error: true` at `:80` — honest prose carrying neither marker word);
`sprint6-e2e-oracle.yml:56` `sprint6-e2e`::"Preflight — VM resources" (terminal `|| echo` at
`:67`); `sprint6-e2e-oracle.yml:151`::"Capture evidence artifacts" (terminal `|| true` at `:164`);
`sprint6-e2e-oracle.yml:175`::"Teardown (preserve volumes)" (terminal `|| true` at `:179`);
`cd-gcp.yml:404` `deploy-to-vm`::"Pull + restart stack" (`|| true` at `:428-431` inside one
continuation-joined logical line).

*Recorded but not currently a finding (1):* `frontend.yml:317` `e2e-visual`::"Generate + commit
Linux baselines if none are committed yet" — its `|| true` at `:330` is intermediate and the
script's last effective line is `fi`, a block terminator, so the step classifies as
propagating. That recorded entry over-states.

The residual tenth is **not reproducible by reading**. That gap is surfaced here, not resolved.

**`cd-gcp.yml:404` is probably a gate defect rather than a workflow defect.**
`effective_command_lines` joins continuations into one logical line and
`terminal_discarding_construct` then runs an unanchored `re.search` over it, so a step whose
final command *does* decide its exit status is misclassified. Same class as the
`strip_js_comments` fix already recorded in that module, and the mirror image of the stale
`e2e-visual` entry above: one reading over-states a finding, the other over-states a
declaration. R4.12 states the honest disposition, and it leaves one option open that the design
phase may prefer — correcting `terminal_discarding_construct`'s reading rather than rewriting
the workflow, which removes the finding without touching `cd-gcp.yml`. Either route is honest;
attaching an advisory marker to a step whose final command decides its exit status is not.

*(b) The README headline.* `README.md:24` states **51 PASS / 3 FAIL / 0 PARTIAL / 10 SKIP /
64 TOTAL**. `docs/state/CURRENT.md:119` states **52 PASS / 3 FAIL / 0 PARTIAL / 9 SKIP / 64
TOTAL**. **These are two different executions, and that is the load-bearing correction.**

`doc_truth::_claim_readme_headline_counts` compares `README.md`'s line against a **nested**
`verify_claims` run (child env flag `SYNAPSE_DOC_TRUTH_NESTED=1`, `doc_truth.py:659`) in which
C56 self-excludes as SKIP — 51/3/0/10/64. `ledger_gen` renders from the **top-level** verdict,
where C56 is PASS — 52/3/0/9/64 (`ledger_gen.py:324` -> `CURRENT.md:119`). **A generator that
projects the top-level counts into `README.md` therefore makes C56 FAIL by exactly the guard
delta.** R4.4 must name which execution it projects, or automating the transcription breaks the
gate it exists to serve.

`README.md:26` discloses the asymmetry explicitly — "a top-level `make verify-claims` therefore
reports C56 as a pass, i.e. one more PASS and one fewer SKIP. That asymmetry is the recursion
guard, not a discrepancy." Credit that: it is disclosed, not hidden. The defect that remains is
structural, and it is smaller and more specific than "generate the README": **no code path
writes `README.md`.** `ledger_gen`'s document constant is `docs/state/CURRENT.md`, and `:324`
renders the README headline *into CURRENT.md's own generated region*. The transcription step is
literally "copy `CURRENT.md:119` into `README.md:24`".

**The marker mechanism, since R4.4, R4.5 and R4.11 are stated against it.** The literals are
owned by `gate_surface.py:116-117` (`GENERATED_BEGIN` / `GENERATED_END`) and imported by
`ledger_gen`. A marker delimits only when it **owns its line** (`_standalone_marker_offsets` ->
`generated_region_bounds`); there must be exactly one of each with begin before end, or
`LedgerMarkersError` -> `unavailable` -> exit 2. `render()` preserves every byte outside the
region — including prose that quotes the markers — and is idempotent. `--check` is the default
(diffs, exits 1); only `--write` rewrites, and it never creates the document.
`_readme_headline_line` selects the line matching `verify[-_]claims`
(`_VERIFY_CLAIMS_MENTION`, `:665`) carrying the most extractable counts, so a generated headline
that drops that phrase makes C56 **skip**.

**R4.9's obligation is genuinely unmet.** A grep over `tests/**/*.py` for
`SYNAPSE_DOC_TRUTH_NESTED`, "recursion" and "nested" returns no reference to the guard.

**R4.6 and R4.7 are already discharged, and are retained below only as regression pins.**
Every `doc_truth` claim carries `required`, and a required claim that cannot be evaluated forces
the aggregate to `unavailable` with exit 2 regardless of how many siblings report `ok`. The
module docstring names the exact causes — "the README headline claim's 900s suite timeout, an
unparseable summary, a missing pin table, the recursion guard firing" — and records that this
replaced an `evaluate()` which returned `ok` when *any* claim was ok, "so a skipped headline
claim was absorbed by the unrelated spec-threshold pin passing". The owning obligation is
`purpose-achievement-audit` **R1.4 / R1.6**, which that docstring cites by number. This is
stated here because under this spec's own "what this spec does NOT restate" rule the two
criteria would otherwise read as new work and be implemented twice.

#### Acceptance Criteria

1. WHEN the Workflow_Shape_Gate runs over `.github/workflows/`, THE Workflow_Shape_Gate SHALL
   report zero findings under every rule it applies, because C64's verdict is the disjunction of
   all four and a fix under one rule may create a finding under another.
2. WHERE a step carries a discarding construct and is not named in `blocking-steps.yaml`'s
   `steps:` set, THE Workflow_Shape_Gate SHALL treat that step as honestly labelled only when the
   name owning the construct's scope — the step name for a step-scoped construct, the job's
   display name for a job-scoped one — contains `ADVISORY` or `informational`, matched
   case-insensitively.
3. WHEN a step named in `blocking-steps.yaml`'s `steps:` set is renamed, THE Workflow_Shape_Gate
   SHALL report zero `blocking-unresolved` findings on the resulting tree, because a declaration
   is matched by step-name string and an `exact`-match entry breaks on punctuation alone.
4. WHEN the Headline_Generator runs in write mode, THE Headline_Generator SHALL render the
   `README.md` headline counts inside a region delimited by one standalone
   `<!-- generated:begin -->` line and one standalone `<!-- generated:end -->` line, projecting
   the counts of the same Check_Registry execution that check C56's headline-counts claim compares
   against, so the generated number and the enforced number cannot differ.
5. WHEN the Headline_Generator runs in write mode, THE Headline_Generator SHALL replace every
   byte between its two markers and leave every byte outside them unchanged, including prose that
   quotes those markers.
6. IF the headline-counts claim cannot be evaluated, THEN THE evaluating step SHALL record a
   non-passing result.
7. IF the headline-counts claim cannot be evaluated, THEN no other claim evaluated in that
   same step SHALL supply a passing result for the step.
8. IF the recursion guard causes the comparing execution to self-exclude, THEN THE
   Headline_Generator SHALL state inside the generated region both the counts that execution
   reported and the one-check compensation a top-level run applies, so the number a reader
   reproduces and the number the gate enforces are each derivable from the published text rather
   than from a hand-written note.
9. WHEN the recursion-guard environment flag is set, THE headline-counts claim SHALL report a
   non-passing, `required` status naming the guard as the cause, and an automated test SHALL
   assert that status without executing the Check_Registry suite.
10. IF the Workflow_Shape_Gate detects a non-propagating step that is neither named in
    `blocking-steps.yaml`'s `steps:` set nor recorded under its `unlabelled_discarding_steps`
    section with a remediation, THEN THE Workflow_Shape_Gate SHALL exit non-zero naming that
    workflow, job and step, and THE step that invokes it SHALL propagate that exit status to the
    job result, because an unattributable red is the condition that section exists to remove and
    nothing reads that section as a pass.
11. IF `README.md` holds no generated region, more than one, or its two markers out of order,
    THEN THE Headline_Generator SHALL report a non-passing result naming the cause and SHALL leave
    the document byte-identical.
12. WHERE a step's only discarding constructs are non-terminal within a single
    continuation-joined command, THE Workflow_Shape_Gate SHALL report that step as a shape defect
    to be made readable rather than one to be labelled, because a step whose final command decides
    its exit status is blocking and an advisory marker on it would be a false label (I-7).
13. WHILE the Workflow_Shape_Gate reports any unremediated non-propagating step, THE job that
    invokes it SHALL record a non-passing result, so the finding blocks rather than accumulates.

**R4.6 and R4.7 are regression pins, not new work** — see the verified reality above for the
mechanism that already discharges them and the spec that owns the obligation.

**Verdict: partially achieved.** C64 is a live, disclosed FAIL. The headline asymmetry is
disclosed in prose but not yet mechanical.

---

### Requirement 5: The simulated world does not reward intelligence

**User Story:** As a stakeholder asking whether multi-agent consensus is worth its
complexity, I want the twin to contain structure a coordinating system can exploit, so that a
measured uplift of zero is informative rather than inevitable.

**The verified reality.** Finding 4 above. **Every structure below must name the agent
decision it unlocks; nothing is added for realism's sake.** The design rule and the five
structures are recorded first in the Decision_Relevance_Record so the phase is falsifiable
rather than aesthetic.

**Four things R5.1 needs do not exist, and two live paths disagree.** This is why A-4 has been
replaced by a finding rather than retained as an assumption.

1. **No scalar objective for "regret."** `uplift/metric_contract.yaml` declares per-KPI
   hypothesis tests (`primary_kpis: {fill_rate: higher}`, `mde: {fill_rate: 0.2}`,
   `alpha: 0.05`, `mann_whitney_u`, `decision_rule: significant_and_favorable_and_meets_mde`),
   and `MetricContract.classify` returns a one-of-three `Outcome`, **not a cost**. Regret has no
   units, no sign convention, and no aggregation rule over the 6-field `KpiVector`.
2. **No perfect-foresight seam.** `DecisionPolicy.decide(obs)` sees only present state.
   `_order_arrival` draws from `self._rng` and exposes no arrival trace. `_delivery` picks the
   depleting SKU by `self._rng.choice(list(self._inventory.keys()))`, so there is no per-SKU
   demand path to foresee. The only exogenous-demand seam,
   `start(external_demand=True)` + `inject_orders(n)`, is a bare count and **replaces** the
   demand process — using it is not the unmodified twin.
3. **No holding-cost or on-hand-inventory signal.** `SimulationMetrics` carries only
   `orders_created`, `orders_delivered`, `orders_spoiled`, `restocks_triggered`,
   `total_delivery_time_min` and `total_pick_pack_time_min`. There is no inventory-time
   integral, so the classic `(s, S)` cost objective is not derivable.
4. **No stock-sensitive KPI at all — a NEW finding that strengthens Finding 4.** `_delivery`
   executes `self._metrics.orders_delivered += 1` **unconditionally**, then clamps
   `self._inventory[sku] = max(0.0, ... - 1.0)`. `kpi.py` derives
   `fill_rate = orders_delivered / max(1, orders_created)`. **A stockout costs nothing
   measurable.** `co2_estimate` shares that numerator. `spoilage_rate` is a fixed clock
   (`_freshness` keys frozen at `start()`, decay `0.01 x mult` per tick against threshold `0.3`)
   that never reads inventory or order size. **None of the six KPIs sees stock availability.**

**Two configuration disagreements between live paths.** `uplift/harness.py::_build_twin` calls
`sim.start()` and leaves the engine's endogenous `(s, S)` restock live at
`_restock_threshold = 50.0`; `digital_twin/world/runtime.py:128` sets
`set_policy(restock_threshold=0.0)` precisely to disable it. R5.1 did not say which
configuration the comparator runs in — and through the harness, "the `(s, S)` policy" would be
measured **stacked on top of the twin's own `(s, S)`**, biasing regret toward zero independently
of whether the world is easy. R5.36 settles it.

**A documented-versus-implemented contradiction.** `uplift/kpi.py:85-86` documents
`unmet_demand_events` as "incremented whenever a delivery draws a SKU already at zero
inventory". `uplift/harness.py` actually increments
`sum(1 for level in sim.inventory.values() if level <= 0.0)` **once per step** — a per-step count
of SKUs at zero, whose numerator scales with `n_steps` x SKU count and is clamped by
`_clamp_fraction`. Those are different quantities.

**And a docstring its own engine contradicts.** `digital_twin/world/runtime.py:18-21` claims
that disabling auto-restock means "If the agents do nothing, stock genuinely runs out and
`fill_rate` falls". Given `_delivery`'s unconditional increment, **stock running out does not
lower `fill_rate`**. Either that docstring or `_delivery` is wrong; R5.38 decides it in favour
of the docstring.

**The consequence, stated plainly.** R5.1 as previously written would return approximately zero
for **instrumentation** reasons and be read as confirming Finding 4 — the exact failure mode the
criterion exists to prevent. R5.33-R5.38 are what make R5.1 a measurement rather than an
artefact.

**Sequencing note that overrides convenience.** R5.1 measures `(s, S)` regret on the
**unmodified** twin and is the falsification test for this spec's central finding. It runs
before any twin change.

#### Acceptance Criteria

**The falsification test, first (R5.1-R5.4).**

1. WHEN a perfect-foresight policy and a base-stock `(s, S)` policy are each run against the
   **unmodified** World_Twin on the same replicate seeds, THE Uplift_Harness SHALL measure and
   record the `(s, S)` policy's regret against the scalar objective declared under R5.33.
2. THE materiality margin for `(s, S)` regret SHALL be committed as a pinned threshold only
   after it has been measured, because no such measurement exists today.
3. IF the measured regret on the unmodified World_Twin is at or above that margin, THEN THE
   Finding-4 claim SHALL be reported as falsified.
   *[R5.43-discharge annotation — R5.3 is NOT weakened, NOT rewritten and NOT softened. It did
   exactly what it said: it fired `material` correctly, and it fired about the **wrong quantity**.
   Run `35125443185`, sha `34d861b`, splits that verdict into `tuning_gap`
   `0.38812253172657085` and `information_ceiling` `0.06524434327342887`, so **Finding 4 is
   substantively TRUE** — the simulated world does not reward intelligence — while R5.3's
   mechanical test could not see it. **Satisfying R5.3 is therefore necessary but not sufficient**
   for the claim R5 exists to support; the sufficient test is R5.45.]*
4. IF the Finding-4 claim is reported as falsified, THEN THE remaining scope of this
   requirement SHALL be re-cut before implementation continues.

**THE R5.4 RE-CUT — performed here, not promised.** *R5.4's condition is met, so this block is
its discharge. Nothing below is deleted: scope that leaves this spec leaves it marked (I-7).*

**R5.3 is DISCHARGED.** Task 11's checkpoint A has run: run `34685048665`, sha `c746463`,
`verdict: material`. The measured `(s, S)` regret on the **unmodified** World_Twin is at or above
the R5.2 margin, so the Finding-4 claim is **reported as falsified**. R5.1 and R5.3 close by
measurement, and R5.4 is therefore binding rather than hypothetical.

**R5.6's claim is measured, not owed.** Its falsifiable claim — that a base-stock `(s, S)` policy
is measurably sub-optimal on this twin — now holds **on the UNMODIFIED twin**, so it no longer
requires the five structures to become true. *What that licenses:* stating the sub-optimality
claim as measured, and treating the twin as already containing structure a policy can be wrong
about. *What it does NOT license:* attributing that sub-optimality to **information value**,
reading it as uplift, or reading it as evidence that consensus beats a **tuned** baseline. R5.41
forbids that last inference by name.

**Structures 2, 4 and 5 become recorded DEFERRALS — R5.15-R5.20 and R5.25-R5.27.** The reason is
the same shape for each: each unlocks a **different** agent, and **none of them creates the
quantity the central claim is about.** This is a deferral, **not a deletion** — every criterion
keeps its text, its number and its traceability row, and each carries a `DEFERRED` marker in
place. R5.28 and R5.29 are **not** deferred; they are the subject of CONFLICT R below.

**Structures 1 and 3 become CONDITIONAL — R5.8-R5.14 and R5.21-R5.23.** The condition is written
down **before the number that decides it is known**, which is the only ordering under which it is
a condition rather than a rationalisation: they are reinstated **if and only if** the
information-gap term measured by the new tuned-static comparator arm is **below** the R5.2
materiality margin. At or above that margin the twin already rewards information and neither
structure buys anything the central claim needs. **Why these two and not the other three is a
design fact. It is recorded once, in `docs/adr/ADR-055-twin-decision-relevance.md` D2.6, and is
not restated here.** R5.42 and R5.43 make the condition mechanical rather than remembered.

**R5.43'S CONDITION IS TESTED AND MET — STRUCTURES 1 AND 3 ARE REINSTATED.** Run `35125443185`,
sha `34d861b`, `uplift.yml::twin-regret`, `status: measured`, 200 of 200 replicates usable.
`tuning_gap` = `0.38812253172657085`, interval `[0.3870638568995475, 0.38909283394762645]`;
`information_ceiling` = `0.06524434327342887`; committed materiality margin `0.40`;
`decomposition_residual` exactly `0.0`; `decomposition_admissible` `True`. Selected tuned levels
`s=20, S=30` — a unique minimum over 18 pre-registered candidates, with the incumbent ranked 15th
of 18. So **85.6% of the judged regret is baseline mis-tuning and 14.4% is a ceiling on
information value**, a ratio of **5.95 to 1**; the ceiling is about **0.82 service-point
equivalents** against a pre-registered margin of five. The information-gap term is **below** the
R5.2 margin, so R5.43's first branch fires: **R5.8-R5.14 and R5.21-R5.23 return to scope and are
no longer conditional.**

**And the part that was NOT predicted: neither addend is material on its own.** The tuning gap's
interval sits **below** `0.40` and **excludes** it; the ceiling is far below. Run `34685048665`'s
`material` verdict was produced **only by their SUM** — which is what R5.45 exists to stop a
reader from mistaking for the claim.

**The mechanism, once.** Under instantaneous replenishment an arm can order **after** observing
demand, so foresight buys no timing advantage — and structure 3 is decisive because it is the only
reinstated structure that introduces a **replenishment delay**. The reasoning is recorded once, in
`docs/adr/ADR-055-twin-decision-relevance.md` **D2.7**, and is not restated here.

**Structures 2, 4 and 5 remain DEFERRED and this discharge touches no criterion of theirs:** each
unlocks a different agent, and **none of them introduces a replenishment delay.**

**What this does NOT claim.** Not that the twin's physics are wrong, and not that adding a
replenishment delay would necessarily produce material information value. That is the **next
measurement**, not a prediction to act on.

**Record the decision before writing code (R5.5-R5.7).**

5. THE Decision_Relevance_Record SHALL state the inventory-theory argument, the five
   structures, and the agent decision each structure unlocks.
6. THE Decision_Relevance_Record SHALL state the falsifiable claim that after this phase a
   base-stock `(s, S)` policy is measurably sub-optimal on this twin. *[R5.4 re-cut: this claim is
   already **measured**, on the unmodified twin — run `34685048665`, sha `c746463`,
   `verdict: material`. "After this phase" no longer conditions it, and the record states it as
   measured together with what it does not license.]*
7. THE Decision_Relevance_Record SHALL be committed before any change to
   `digital_twin/simulation/engine.py` made under this requirement.

**Structure 1 — non-stationary demand (R5.8-R5.14).** *Unlocks the Demand_Forecaster:
forecasting has zero value under stationary demand.* ~~**CONDITIONAL under the R5.4 re-cut:
R5.8-R5.14 are reinstated if and only if R5.42's information-gap term is below the R5.2 margin
(R5.43). Text retained in full; no criterion is deleted.**~~ **REINSTATED — the condition above
was tested and MET by run `35125443185`, sha `34d861b`: `information_ceiling`
`0.06524434327342887` is below the `0.40` margin. R5.8-R5.14 are in scope and unconditional. The
struck sentence was accurate when written and is retained so the change of state is visible.**

8. WHEN the World_Twin generates demand, THE demand intensity SHALL vary within a simulated
   day.
9. WHEN the World_Twin generates demand, THE demand intensity SHALL vary across days of the
   simulated week.
10. WHERE a promotion is configured as active, THE demand intensity SHALL rise for the
    promotion's duration.
11. THE demand-intensity shape SHALL be calibrated from statistics derived from the
    Real_Data_Feed rather than from invented literals.
12. THE calibrated demand-intensity parameters SHALL be committed to a version-controlled
    policy file rather than embedded as literals in `engine.py`.
13. WHEN a perfect-foresight policy and a base-stock `(s, S)` policy are each run against the
    non-stationary World_Twin, THE measured `(s, S)` regret SHALL exceed the R5.2 materiality
    margin with its reported interval excluding that margin.
14. IF the measured `(s, S)` regret on the non-stationary World_Twin is not strictly positive,
    THEN THE non-stationarity SHALL be reported as too weak to make forecasting pay.

**Structure 2 — capacity and queueing (R5.15-R5.20).** *Unlocks `routing_navigator` and
dispatch prioritisation: with infinite capacity, dispatch policy is a no-op.* **DEFERRED under the
R5.4 re-cut. Reason: it unlocks a different agent (`routing_navigator`) and creates no part of the
quantity the central claim is about — the information value of coordination in the reorder
decision. Deferred, not deleted (I-7): the text below stands and every criterion is marked.**

15. THE World_Twin SHALL model a finite rider pool as a contended resource.
    *[DEFERRED — R5.4 re-cut.]*
16. THE World_Twin SHALL model finite pick stations as a contended resource.
    *[DEFERRED — R5.4 re-cut.]*
17. WHEN an order is delivered, THE delivery wait SHALL be a function of the contended-resource
    queue state rather than an independent draw. *[DEFERRED — R5.4 re-cut.]*
18. WHEN the World_Twin is measured at each level of the ascending utilisation ladder declared in
    the R5.12 policy file, THE mean wait time over the committed replicate count SHALL be
    non-decreasing in utilisation to within its reported interval. *[DEFERRED — R5.4 re-cut.]*
19. WHEN the mean wait times at the declared utilisation ladder are compared, THE successive
    wait-time increments across the near-saturation band declared in the R5.12 policy file SHALL
    be strictly increasing. *(Band boundaries are committed to that policy file before the run
    judged against them; no value is stated here — the same deferral as R5.2.)*
    *[DEFERRED — R5.4 re-cut.]*
20. THE claim of an OSRM travel-time estimate in **both** the `SupplyChainSimulation` class
    docstring and the `_delivery` docstring SHALL be replaced by a description of the travel time
    the code actually produces, because `_delivery` draws `self._rng.uniform(10.0, 45.0)` and
    makes no OSRM call, and binding the twin to the repository's OSRM container
    (`docker/docker-compose.mumbai.yml::osrm-mumbai`) would make every twin run a category-1
    workload under I-0. *[DEFERRED — R5.4 re-cut, by the stated R5.15-R5.20 range.* **A cost this
    block surfaces rather than resolves:** *R5.20 is a documentation-truth repair — two docstrings
    assert an OSRM call the code does not make — and it is independent of whether the queueing
    structure is ever built. Its cost is two docstring edits and no twin change, so deferring it
    leaves a false claim standing at no saving. Recorded for the design phase to retain or
    re-defer explicitly; not resolved here, because the range was given by operator decision.]*

**Structure 3 — correlated lead times and supplier state (R5.21-R5.24).** *Unlocks
`supplier_trust` and `inventory_sentinel` safety-stock decisions: under i.i.d. lead times a
static safety stock is optimal.* ~~**CONDITIONAL under the R5.4 re-cut: R5.21-R5.23 are reinstated
if and only if R5.42's information-gap term is below the R5.2 margin (R5.43). Text retained in
full; no criterion is deleted.**~~ **REINSTATED — the condition above was tested and MET by run
`35125443185`, sha `34d861b`: `information_ceiling` `0.06524434327342887` is below the `0.40`
margin. R5.21-R5.23 are in scope and unconditional, and this structure is the **decisive** one
because it is the only reinstated structure that introduces a replenishment delay (D2.7). The
struck sentence was accurate when written and is retained so the change of state is visible.**

21. THE World_Twin SHALL correlate supplier lead time with concurrent demand.
    *[REINSTATED — R5.43 condition met, run `35125443185`, sha `34d861b`.]*
22. THE World_Twin SHALL auto-correlate supplier lead time across consecutive simulated days.
    *[REINSTATED — R5.43 condition met, run `35125443185`, sha `34d861b`.]*
23. THE World_Twin SHALL attribute each restock to a named supplier and SHALL expose that
    supplier's realised lead-time history in the `Observation` presented to every arm, so
    `supplier_trust`'s reliability scoring has an observable subject. *[REINSTATED — R5.43 condition met, run `35125443185`, sha `34d861b`.]*
24. WHEN a supplier-aware reorder policy and a supplier-blind reorder policy are compared on the
    same replicate seeds, THE supplier-aware policy's aggregate on every KPI named in the R5.33
    objective SHALL be better with the two policies' reported intervals disjoint on at least one
    of them. *[The operator's re-cut named R5.21-R5.23. R5.24 is recorded here as **consequentially
    conditional**, not as a separate decision: its subject — a supplier-aware policy — has nothing
    to be aware of unless R5.23 lands, so it cannot be judged while R5.21-R5.23 are held. Stated as
    a consequence for the design phase to confirm, not as an operator decision.]*
    *[R5.43-discharge annotation: R5.21-R5.23 are no longer held, so R5.24 is **consequentially
    reinstated** on the same reasoning that made it consequentially conditional — its subject now
    lands. Still a consequence for the design phase to confirm, not an operator decision.]*

**Structures 4 and 5 — perishability coupling and substitution (R5.25-R5.29).** *Unlocks
`freshness_guardian` and `pricing_oracle`, and creates the multi-objective tension.*
**R5.25-R5.27 are DEFERRED under the R5.4 re-cut. Reason: they unlock different agents
(`freshness_guardian`, `pricing_oracle`) and create no part of the quantity the central claim is
about. Deferred, not deleted (I-7). R5.28 and R5.29 are NOT deferred — see CONFLICT R below.**

25. THE World_Twin SHALL make spoilage a function of age-at-arrival. *[DEFERRED — R5.4 re-cut.]*
26. THE World_Twin SHALL make spoilage a function of order size, so bulk ordering raises
    spoilage. *[DEFERRED — R5.4 re-cut.]*
27. WHEN a demand event names a SKU whose stock is zero, THE World_Twin SHALL divert the
    substitution fraction declared in the R5.12 policy file to that SKU's declared substitutes, so
    `pricing_oracle`'s cross-SKU pricing and `freshness_guardian`'s markdown decisions have a
    substitution channel to act on. *[DEFERRED — R5.4 re-cut.]*
28. WHEN the four single-objective policies — minimise `stockout_rate`, minimise `spoilage_rate`,
    minimise the R5.40 on-hand-inventory measure, minimise `avg_delivery_time_min` — are evaluated
    on the modified World_Twin together with the reference policy set declared in the
    Decision_Relevance_Record, THE Pareto-optimal subset of that combined set SHALL exclude all
    four, where one policy dominates another only if it is no worse on every KPI named in the R5.33
    objective and strictly better on at least one with their reported intervals disjoint.
    *R5.28 as previously written was **unsatisfiable**: the Pareto frontier of a finite non-empty
    set is non-empty, so if the evaluated set is exactly those four, at least one is non-dominated
    by construction. It also named "minimise holding cost", a quantity that exists nowhere in the
    tree, and "maximise SLA", which is not a `KpiVector` field.* *[See CONFLICT R: still
    unsatisfiable.]*
29. IF any single-objective policy is Pareto-optimal on the modified World_Twin, THEN THE
    consensus experiment SHALL be reported as having no room to win and SHALL NOT be run,
    because a Pareto-optimal single-objective policy is a proof that consensus is unnecessary.
    *[See CONFLICT R: fires on a theorem, not a measurement.]*

**CONFLICT R — R5.28 is unsatisfiable a second time, and R5.29 then fires on a theorem.**
*Surfaced, not resolved. The argument below is pure logic: no run is needed and none was made.*

**The argument.** R5.28 requires the Pareto-optimal subset of the combined set to **exclude all
four** single-objective policies. Domination requires being **no worse on every KPI** named in the
R5.33 objective and strictly better on at least one. So a **unique minimiser of one coordinate can
never be dominated** — nothing can be no-worse on that coordinate than the thing that uniquely
minimises it. One of the four, "minimise the R5.40 on-hand measure", has a **trivially attainable
unique minimum: hold no inventory.** Nothing ties that without also holding none. That policy is
therefore non-dominated **by construction**. R5.28 is unsatisfiable, R5.29 then fires, and the
consensus experiment is reported as having no room to win — **cancelling E3 and declaring
SYNAPSE's central claim false on a theorem rather than on a measurement.**

**Two aggravations.** **(i)** The interval clause makes this strictly **worse**, not better:
requiring the two policies' reported intervals to be disjoint makes domination **harder**, and
therefore non-dominance **easier**, widening the set R5.28 must exclude. **(ii)** R5.28's own text
already records that it was found unsatisfiable **once** and repaired by adding the reference set.
**Adding points cannot dominate a unique argmin**, so that repair addressed the symptom — the set
being too small — and not the cause.

**The costed repair, recorded and NOT applied.** *No criterion above is amended by this block.
Applying it is a design-phase decision and is not treated here as already agreed.* Replace
Pareto-optimality with **scalar-objective optimality against the committed R5.33 weights**:
consensus has no room to win **if and only if** some single-objective policy attains the committed
objective's optimum within intervals. Why that is well-posed where R5.28 is not:

- **It can fail in both directions.** A single-objective policy can attain the weighted optimum
  and can fail to; neither outcome is a theorem.
- **It uses weights the project has already committed** under R5.33, so it invents no number.
- **It does not fire today.** On run `34685048665`'s own numbers the minimiser of on-hand
  inventory is the no-op arm, whose objective cost is far above the incumbent's. *(Read from the
  recorded run, not re-measured in this document.)*

**A gate that can fail and does not fire today is what a gate should look like.**

**Compatibility and cost (R5.30-R5.32).**

30. WHILE the World_Twin runs under its neutral default policy levers, THE following SHALL
    reproduce their committed expectations:
    `digital_twin/tests/test_simulation.py::TestSimPyEngine::{test_run_deterministic_with_seed, test_run_produces_valid_metrics, test_longer_run_more_orders, test_metrics_to_dict}`,
    `digital_twin/tests/test_simulation.py::TestMonteCarlo::test_shock_params_affect_output`,
    `digital_twin/tests/test_env_response.py::{test_state_persists_across_steps, test_good_action_beats_bad_over_seeds, test_different_actions_yield_different_returns}`,
    `digital_twin/tests/test_world_runtime.py::{test_perceive_after_start_is_full_stock, test_demand_depletes_inventory_and_auto_restock_is_disabled}`,
    `tests/uplift/test_seed_reproducibility_property.py::test_identical_seeds_reproduce_within_noise_tolerance`,
    `tests/uplift/test_seeded_demand_identity_property.py::test_arms_receive_identical_seeded_demand`,
    and `tests/verify/test_nonsynthetic_ingestion_replay_property.py`.
    *Two expected casualties, which is exactly what R5.31 is for:*
    `test_good_action_beats_bad_over_seeds` asserts that fast dispatch out-earns slow dispatch in
    mean return, which R5.15-R5.19's queue coupling changes directly; and
    `test_perceive_after_start_is_full_stock` depends on the
    `{f"sku_{i}": 100.0 for i in range(10)}` literal, which PRESERVE forbids reintroducing on the
    non-seeded path. *[R5.4 re-cut: with R5.15-R5.20 deferred, the **first** casualty is no longer
    expected — `test_good_action_beats_bad_over_seeds` is only threatened by the queue coupling that
    is now held, and it returns to expected-casualty status if and only if R5.43 reinstates that
    work. The second casualty is untouched by any deferral: it arises from the PRESERVE constraint
    on opening stock, which no criterion in this re-cut moves.]*
    *[R5.43-discharge correction, and it makes the reading **stricter** rather than looser: R5.43's
    met condition reinstates structures 1 and 3 **only**. The queue coupling (structure 2) stays
    held, so the first casualty remains **not expected** — R5.43 is now discharged and cannot
    reinstate it. Reinstating structure 2 would need a decision this discharge does not make.]*
31. IF a determinism test's committed expectation changes as a consequence of these structures,
    THEN THAT test SHALL be updated in the same change with its new expectation stated.
32. WHERE a run of the modified World_Twin is executed for measurement, THE run SHALL execute
    in the CI_Pipeline, because a scenario sweep at `MIN_SCENARIOS` scale
    (`digital_twin/simulation/monte_carlo.py:22`, `MIN_SCENARIOS = 1000`) is a category-4
    workload under I-0.

**The instrument R5.1 needs, which does not exist yet (R5.33-R5.40).** These are not scope
creep: without R5.33-R5.37 there is nothing to measure regret against and no foresight seam to
measure it with, and without R5.38 no inventory decision is observable in any KPI, so every
regret number in this requirement would be taken on an instrument that cannot see its subject.

33. THE Decision_Relevance_Record SHALL declare the scalar objective against which regret is
    measured, naming its KPI terms, each term's sign, and the aggregation over replicates, before
    the R5.1 run. *(Weights are committed at declaration time; no value is stated here.)*
34. WHEN the R5.33 objective is declared, THE Decision_Relevance_Record SHALL record, for each
    KPI it names, whether that KPI is observably sensitive to the inventory policy on the
    unmodified World_Twin.
35. IF the R5.1 regret falls below the R5.2 margin while any KPI named in the R5.33 objective is
    recorded under R5.34 as not observably sensitive, THEN THE result SHALL be reported as
    inconclusive and SHALL NOT be reported as confirming the Finding-4 claim, because a null
    produced by an insensitive instrument is not evidence of absence (I-7).
36. WHEN the R5.1 comparator runs, THE World_Twin's endogenous restock loop SHALL be disabled and
    its configured threshold recorded in the result, so measured regret is attributable to the
    compared reorder policy rather than to the twin's own `(s, S)` rule.
37. WHEN a scenario is run for the R5.1 comparator, THE World_Twin SHALL expose the realised
    demand path for that seed as a replayable record, because a perfect-foresight policy cannot
    exist without one.
38. IF a delivery draws a SKU whose stock is zero, THEN THE World_Twin SHALL record the event as
    unmet demand and SHALL NOT count it as a delivered order, so `inventory_sentinel`'s reorder
    timing and quantity are observable in a KPI at all.
39. WHEN the World_Twin generates a demand event, THE event SHALL name the SKU it demands, so
    `demand_prophet`'s per-SKU forecast and `pricing_oracle`'s per-SKU price have a demand stream
    to act on.
40. THE World_Twin SHALL record a time-weighted on-hand inventory measure per scenario, so
    `inventory_sentinel`'s safety-stock-versus-holding tradeoff has a cost term and R5.28's third
    single-objective policy has a KPI to minimise.

**Added by the R5.4 re-cut (R5.41-R5.43).** *These continue R5's sequence; nothing above is
renumbered. R5.41 is the operator's binding decision. R5.42 and R5.43 exist so the conditional
above is judged mechanically rather than remembered.*

**Why R5.41 is needed and R5.35 does not already cover it.** R5.35 guards one direction only: a
regret **below** the margin measured on an instrument recorded as insensitive is reported
inconclusive. It says nothing about an **at-or-above** margin verdict whose cause is a badly tuned
baseline — and that is the direction now measured. The existing guard and the actual result point
opposite ways, so this needs a criterion of its own rather than a re-reading of R5.35.

41. IF a `material` verdict is attributable to baseline mis-tuning rather than to information
    value, THEN THAT verdict SHALL NOT be used to denominate E3's floor and SHALL NOT be used to
    denominate the R7 or R9 published claim, and the attribution SHALL be recorded with the
    verdict.
    *[R5.41 now **BINDS** rather than merely standing. Run `35125443185`, sha `34d861b`, attributes
    **85.6%** of run `34685048665`'s `material` verdict to baseline mis-tuning, so this is the live
    case, not a hypothetical: the honest baseline is the **tuned static control at `s=20, S=30`**,
    not the incumbent, which ranked 15th of 18 candidates. The incumbent-denominated verdict is
    therefore unusable for E3's floor and for the R7/R9 published claim. R5.44 states the positive
    obligation this leaves behind.]*
42. WHEN the R5.1 comparator is next run, THE Uplift_Harness SHALL include a tuned-static
    comparator arm and SHALL record the information-gap term measured against it, because the
    R5.8-R5.14 and R5.21-R5.23 condition is not decidable without that quantity.
    *[DISCHARGED — run `35125443185`, sha `34d861b`, `status: measured`, 200/200 replicates usable;
    `tuning_gap` `0.38812253172657085`, `information_ceiling` `0.06524434327342887`,
    `decomposition_residual` exactly `0.0`, `decomposition_admissible` `True`.]*
43. IF the R5.42 information-gap term is below the R5.2 materiality margin, THEN R5.8-R5.14 and
    R5.21-R5.23 SHALL be reinstated as in-scope; and IF it is at or above that margin, THEN they
    SHALL remain deferred with that measured term recorded as the reason.
    *[TESTED AND MET — first branch fires. `information_ceiling` `0.06524434327342887` is below the
    committed `0.40` margin (run `35125443185`, sha `34d861b`), so R5.8-R5.14 and R5.21-R5.23 are
    **REINSTATED**. Second branch not taken. Structures 2, 4 and 5 are untouched by this criterion
    and remain deferred.]*

**Added by the R5.43 discharge (R5.44-R5.45).** *These continue R5's sequence; nothing above is
renumbered and no criterion text is deleted. R5.44 is the positive obligation R5.41's prohibition
leaves open. R5.45 is the sufficiency test R5.3 alone cannot supply.*

44. WHERE E3's regret floor or the R7 or R9 published claim is reported, THE reported figure SHALL
    be denominated against the tuned static control declared under R5.42 — the honest baseline,
    measured at `s=20, S=30` — rather than against the incumbent baseline arm, and THE report
    SHALL name the arm it is denominated against, so a reader never has to infer it.
45. IF an at-or-above-margin R5.3 verdict is cited as establishing the claim R5 exists to support,
    THEN THAT citation SHALL be reported as insufficient, because satisfying R5.3 is necessary but
    not sufficient; THE sufficient test SHALL be the R5.42 information-gap term **alone** clearing
    the R5.2 materiality margin, and a sum of decomposed terms of which no addend clears that
    margin on its own SHALL NOT be reported as satisfying it.

**Two notes the design phase owes an answer to, recorded here rather than legislated as
criteria.** `orders_spoiled` increments **per SKU per tick**, so `spoilage_rate` is a tick-count
ratio and not a spoiled-units fraction; R5.25 and R5.26 will change what it measures, and that
change must be stated rather than absorbed. And `digital_twin/simulation/monte_carlo.py` also
drives a `ProcessPoolExecutor`, which the I-0 taxonomy names explicitly as a category-4
workload — that strengthens R5.32 rather than qualifying it.

**Verdict: partially achieved.** *R5.1, R5.3, R5.4 and now R5.42 and R5.43 are discharged — the
falsification test ran (run `34685048665`, sha `c746463`, `verdict: material`) and the re-cut it
mandated is the marked block above. R5.15-R5.20 and R5.25-R5.27 are deferred; ~~R5.8-R5.14 and
R5.21-R5.23 are conditional on R5.43~~ **R5.8-R5.14 and R5.21-R5.23 are REINSTATED — R5.43's
condition was tested and met by run `35125443185`, sha `34d861b`**; R5.28 is unsatisfiable per
CONFLICT R. Everything else is not achieved.*

**Falsification.** *What would prove this finding false:* a measured, materially positive
`(s, S)` regret on the unmodified twin (R5.1). ~~*Not attempted — requires compute that I-0
places in CI.*~~ **[CHALLENGED, and the finding is FALSIFIED.]** *Attempted and measured in CI:
run `34685048665`, sha `c746463`, `verdict: material`. The struck sentence above was accurate when
written and is retained rather than deleted so the change of state is visible. **What this does not
settle:** whether the measured regret is attributable to information value or to baseline
mis-tuning — R5.41 forbids the second reading from denominating any published floor, and R5.42
measures which it is.*

**[NOW SETTLED, and the mechanical falsification does not survive it.]** *Run `35125443185`, sha
`34d861b`, attributes 85.6% of that verdict to baseline mis-tuning and 14.4% to an information
ceiling that is far below the margin — see the R5.43 discharge block above for the numbers, and
D2.7 for the reasoning. So **Finding 4 is substantively TRUE**: R5.3 fired `material` correctly,
about the wrong quantity. The falsification stands as a **mechanical** result and is withdrawn as a
**substantive** one; R5.45 records that R5.3 alone was never sufficient.*

---

### Requirement 6: The measuring instrument has never been shown able to detect an effect

**User Story:** As a reader of an uplift result, I want the harness proven able to detect a
known effect of known size, so that a null result means "no effect" rather than "blind
instrument".

**The verified reality.** `.kiro/specs/purpose-achievement-audit/` R2.6 specifies the
negative control — identical arms must yield a 95% interval containing zero. No spec in
`.kiro/specs/` specifies a **positive** control: `grep` for "positive control" across every
spec document returns no match. `uplift/harness.py` enforces the power floor
(`if n < MIN_SCENARIOS: raise ValueError("INV-TW-002 violated...")`, `:608-611` — re-verified)
and models incompleteness carefully (`_run_is_incomplete`, `_pair_is_incomplete`), but nothing in
the tree establishes what effect size the harness can *see*. Audit R2.5 and R2.6 were both
re-read and are restated accurately below.

**No 95% interval exists anywhere in the tree.** `UpliftResult` and `UpliftArtifact` carry only
`headline_uplift: float`; a grep for `bootstrap|confidence_interval|ci_low|ci_high|percentile(`
across `uplift/**/*.py` returns no match, and `tests/uplift/test_uplift_null_arm_property.py:67`
states outright that "no interval is estimated here at all". **R6.1, R6.2 and R7.14 are therefore
all judged on a quantity nothing produces**, which is why R6.13 exists. Carrying one is a schema
change: `UpliftArtifact` is `extra="forbid"` with a byte-pinned canonical serialisation and an
aggregate digest. The figure `95%` is `1 - alpha` from the committed contract, not an invented
number.

**The third arm is cheaper than it looks, and the blocker is one line.** The policy layer is
already N-arm: `DecisionPolicy` is a Protocol of `name` + `decide`, seeds derive from
`(scenario.seed, index)`, and `arm_aggregates`, `UpliftProvenance.arms` and the C60 gate are
arm-count agnostic. The single blocking line is **`uplift/harness.py:749`** —
`_resolve_baseline_arms` pools **every** non-`consensus` arm into the baseline, so an Oracle_Arm
is silently absorbed, and one failed oracle replicate would mark the consensus contrast
incomplete and drive C60 to `EXIT_UNAVAILABLE`. The oracle contrast itself needs zero model
change: `assemble_uplift_result(..., consensus_arm="oracle", baseline_arm="Par_Level_Reorder")`
already works. Not free, though: `MetricContract.classify` is strictly two-sample and
`decision_rule` is validated by string equality, so any multiplicity correction needs a contract
version bump.

**The negative control's premise fails today.** With the pooled default, replacing the consensus
arm with a `Par_Level_Reorder` copy still compares one policy against a pool of four, and
`cli.py::main` never passes `baseline_arm=`. Both R6.1 and R6.2 therefore name the sole
comparator, and R6.14 makes the obligation explicit.

**Why this is the most important requirement in the spec.** It converts "we measured zero"
from an ambiguous non-result into a real finding, because the instrument is then known to
have the power to see an effect of that size. Without it, R7's number is unfalsifiable. The one
number this requirement introduces is a detection probability of `0.80`, and it is labelled what
it is: a **pre-registered target** carried from the blueprint, not a measurement.

#### Acceptance Criteria

1. WHEN the Consensus_Arm is replaced by a copy of the Baseline_Arm so the two arms are
   identical and the Uplift_Harness runs at `MIN_POWERED_REPLICATES` per arm against that copy as
   the sole named comparator, THE Uplift_Harness SHALL report a headline uplift whose 95%
   interval contains zero. *(Restates `purpose-achievement-audit` R2.6 as a dependency of R6.2;
   the comparator is named here because the harness pools baselines by default.)*
2. WHEN a known-exploitable structure is present in the World_Twin and an Oracle_Arm plays
   the analytically optimal policy for that structure against a single named baseline comparator,
   THE Uplift_Harness at `MIN_POWERED_REPLICATES` per arm SHALL report a headline uplift whose
   95% interval lies entirely above zero. *(NEW — closes the gap in `purpose-achievement-audit`
   R2. "Lies entirely above zero" replaces "excludes zero", which an interval entirely below zero
   also satisfies.)*
3. WHEN the Oracle_Arm result is reported, THE measured effect SHALL fall within a declared
   tolerance of the analytic optimum for the injected structure. *The tolerance does not yet
   exist and SHALL be committed as a pinned value before the run that is judged against it.*
4. IF the measured Oracle_Arm effect falls outside that tolerance, THEN THE Uplift_Harness
   SHALL be reported as mis-measuring, and THE Oracle_Arm SHALL NOT be reported as
   under-performing.
5. THE Power_Report SHALL state, for the committed replicate count and the observed variance,
   the minimum effect size the Uplift_Harness detects at a declared detection probability.
6. THE Power_Report SHALL be committed to version control as a generated artifact declared
   distinct from the uplift result artifact that `artifact_is_version_controlled` refuses, whose
   inputs name the run that produced it, because without that distinction committing the
   Power_Report trips the gate's version-control refusal.
7. WHILE no Power_Report exists that describes the Uplift_Harness revision under measurement,
   THE project SHALL NOT publish any headline uplift result, because an unpowered null is not
   evidence of absence and a Power_Report describing a superseded revision does not license
   publication.
8. WHERE `MIN_POWERED_REPLICATES` is retained at its current value, THE Power_Report SHALL
   state the detectable effect at that value.
9. WHERE the Power_Report derives a replicate requirement **greater than**
   `uplift/uplift_floor.py::MIN_POWERED_REPLICATES`, THE derived value SHALL replace that
   constant.
10. WHEN `MIN_POWERED_REPLICATES` is raised, THE pin
    `tests/uplift/test_uplift_floor_data_gate.py::test_powered_replicate_floor_matches_inv_tw_002`
    SHALL be converted in the same change from asserting `MIN_POWERED_REPLICATES == MIN_SCENARIOS`
    to asserting `MIN_POWERED_REPLICATES >= MIN_SCENARIOS`, so INV-TW-002 remains a floor rather
    than a fixed point.
11. WHEN the same seed set is replayed through the Uplift_Harness in two separate
    operating-system processes, THE Uplift_Harness SHALL produce byte-identical arm KPI
    aggregates. *(Restates `purpose-achievement-audit` R2.5; recorded here because an interval
    that is not reproducible cannot support a ratchet.)*
12. WHERE a control run or a power sweep is executed, THE run SHALL execute in the
    CI_Pipeline, because `uplift/cli.py::build_arms` returns **five** arms and
    `.github/workflows/uplift.yml` states "4 adversarial scenarios x 5 arms x 1000 replicates per
    arm" at `timeout-minutes: 350` against a ~360-minute ceiling — a category-4 workload under
    I-0.
13. WHEN the Uplift_Harness completes a powered run, THE Uplift_Harness SHALL estimate and record
    a two-sided interval for the headline uplift at `1 - alpha`, using the `alpha` the
    Metric_Contract commits (`0.05`), because no interval is estimated anywhere in the tree today
    and R6.1, R6.2 and R7.14 are each judged on one.
14. WHEN either the negative control or the positive control is run, THE Uplift_Harness SHALL be
    invoked with exactly one named baseline comparator rather than the pooled default, so the
    contrast is between two policies rather than between one policy and a pool of four.
15. WHEN the negative control is repeated over the number of independent seed sets the
    Decision_Relevance_Record declares, THE proportion of repetitions reporting a proven gain SHALL
    fall within the tolerance that record declares for the Metric_Contract's committed `alpha` of
    `0.05`, because a single run classifies only four pairs (`primary_kpis: fill_rate` across four
    scenarios) and four pairs cannot estimate a rate.
16. IF the Power_Report derives a replicate requirement below
    `digital_twin/simulation/monte_carlo.py::MIN_SCENARIOS`, THEN THE Power_Report SHALL record the
    INV-TW-002 floor as binding rather than proposing a lower constant, because a value below that
    floor breaks the hard guard at `uplift/harness.py:608-611` and `monte_carlo.py:123-127`.

**Verdict: not achieved.** The negative control is specified and unrun; the positive control
is unspecified until this requirement.

---

### Requirement 7: The uplift verdict is plumbed but has never measured anything

**User Story:** As a stakeholder asking "are the decisions better?", I want the verdict to
come from a completed, powered, fidelity-bounded experiment that CI is obliged to run, so
that the answer is evidence rather than an unexercised code path.

**The verified reality — with the blueprint's stale half corrected.**

*What is already closed* (credit `purpose-achievement-audit` tasks 10.3 and 10.5):
`uplift_truth.py:494` derives `EXIT_PASS` from `is_proven_uplift`; `:566` routes a floor raise
through `ratchet_to_measured`; `admit()` (`:382`) rejects an inadmissible artifact;
`artifact_is_version_controlled` (`:187`) exists and `artifacts/` is absent from the tree and
from `git ls-files`; `uplift.yml` runs the harness (`:116`) and the gate with
`--require-fresh-run` (`:123`) in one job, and its header states "No `|| true`, no
`|| echo`, no `; exit 0`, no `continue-on-error`."

*What remains:*

- `uplift/uplift_floor.py:47` — `UPLIFT_FLOOR: float = 0.0`. The docstring is honest about
  why ("before the harness has produced and committed a verified positive result, the honest
  floor is 'no proven uplift yet'"), and `gate-mutations.yaml` records that a complete
  powered in-bound run measuring `0.0` against a floor of `0.0` is exit 2, not a pass.
- C60's ledger row: `SKIP — no uplift run was performed in this job`. **No powered run has
  ever been recorded.**
- `uplift.yml` triggers on `schedule: cron "0 3 * * *"` and `workflow_dispatch` only, and
  `infrastructure/quality/required-checks.yaml` contains **no entry for
  `.github/workflows/uplift.yml`** — its declared uplift row is `job: uplift-verify` in
  `ci.yml`, the fast property suites, not the powered harness. So the one job in which C60
  can ever pass is not required by anything.
- `gate-mutations.yaml` records that C60's falsification obligation "moves to the generating
  job", which is the only context in which it can be falsified — and that context has never
  run a sweep (R1).

**All three staleness claims above were re-verified during refinement, and all five preamble
line citations verify byte-for-byte.** But R7 over-claims new work, and it misses one gap
entirely.

**Eight of the fourteen criteria below describe behaviour that already exists and is already
tested. They are demoted to regression pins, with the covering test named, so nobody implements
them twice:**

- **R7.3-R7.6** are covered comprehensively by the `_inadmissible` strategy in
  `tests/uplift/test_uplift_admissibility_property.py` — `incomplete` incomplete/absent/
  non-boolean, under-powered with both integer forms, fidelity absent-or-out-of-bound across gain,
  zero and regression headlines, all five provenance flaws, and version-controlled with a
  proof-grade payload. That suite runs inside `ci.yml::uplift-verify`, which **is** in the required
  set.
- **R7.7** is already covered by
  `test_substituting_the_proven_uplift_predicate_changes_the_exit_code`.
- **R7.13** is already enforced: `ratchet()` raises `FloorRatchetError` on any lowering before a
  proof is consulted, pinned by `test_uplift_floor_is_a_monotonic_data_gated_ratchet` and
  `test_declared_floor_holds_under_the_data_gate`.

**Genuinely new work in R7 is narrower than it looks:** R7.8 (`gate-mutations.yaml::C60` declares
exactly **one** operator, `untrack-the-evidence-path`; no `is_proven_uplift` mutation exists
anywhere in the tree) and the interval half of R7.14.

**R7.10 is verified and sharper than the earlier draft.** `required-checks.yaml`'s only uplift
row is `job: uplift-verify` / `workflow: .github/workflows/ci.yml`, and
`.github/workflows/uplift.yml` appears in **none** of the file's four sections. Three additions:
(a) the omission is **invisible** — `required_checks_truth.RULES` has no completeness rule, so
nothing fails for an unmentioned workflow; (b) `uplift-proof` is structurally **ineligible**, not
merely undeclared — the file's eligibility rule requires a check produced by **every** pull
request to `main`, and `uplift.yml` carries only `schedule` and `workflow_dispatch`, so **R7.10's
stated purpose is unreachable via branch protection**; (c) `ineligible[].reason` is a closed
six-value enum and `post-merge` fits it (the `deploy-to-vm` precedent), so no schema change is
needed.

#### Acceptance Criteria

1. WHEN the CI_Pipeline runs the job that **generates** the uplift evidence, THE Uplift_Harness
   SHALL be executed in that same job to regenerate the artifact, because C60 is also evaluated by
   `verify_claims` with `generating_job=False` and obliging that path to run the harness would make
   every pull request a category-4 workload, contradicting I-0 and AD-9.
2. IF the Uplift_Harness cannot run in the generating job — it fails to start, exits non-zero,
   exceeds that job's wall-clock bound, or produces no artifact at the declared path — THEN that
   job SHALL record a non-passing result naming which of those four states occurred.
3. IF the evaluated artifact carries `incomplete` as `true`, omits it, or carries a
   non-boolean value, THEN THE Uplift_Gate SHALL exit `EXIT_UNAVAILABLE` printing the reason.
4. IF the evaluated artifact records fewer replicates per arm than `MIN_POWERED_REPLICATES`,
   THEN THE Uplift_Gate SHALL exit `EXIT_UNAVAILABLE` printing the recorded and required
   counts.
5. IF `within_fidelity_bound` is absent or false, THEN THE Uplift_Gate SHALL exit
   `EXIT_UNAVAILABLE` irrespective of the headline magnitude, because "exit non-zero" would permit
   collapsing an out-of-bound gain into `EXIT_REGRESSION` and the code returns
   `EXIT_UNAVAILABLE`.
6. IF the evaluated artifact was read from version control, or carries provenance whose
   revision, seed set, arm identifiers, or run identifier differ from the run performed in the
   generating job, THEN THE Uplift_Gate SHALL exit `EXIT_UNAVAILABLE`.
7. WHERE the evaluated artifact is admitted and its verdict is `EXIT_PASS`, WHEN
   `is_proven_uplift` is replaced by a stub returning `False`, THE exit code the Uplift_Gate
   produces SHALL change. *(The precondition is not decoration: without an admitted, passing
   artifact the criterion is vacuously satisfiable, and `False` is the realisable direction —
   stubbing to `True` cannot change an exit code that is already `EXIT_PASS`.)*
8. THE mutation that replaces `is_proven_uplift` SHALL be declared in
   `infrastructure/quality/gate-mutations.yaml`.
9. WHEN the Falsification_Sweep runs inside the job that generates the uplift evidence, THE
   sweep SHALL probe the declared `is_proven_uplift` mutation, because
   `gate-mutations.yaml` records that generating job as the only context in which C60 can be
   falsified.
10. THE job that runs the Uplift_Harness and evaluates the Uplift_Gate SHALL be declared in
    `infrastructure/quality/required-checks.yaml` under `ineligible` with the recorded reason
    `post-merge`, because that file's eligibility rule admits only checks produced by every pull
    request to `main` while `uplift.yml` carries only `schedule` and `workflow_dispatch` — so the
    declaration, not branch protection, is what makes the omission visible.
11. WHERE the Uplift_Gate exits with any code other than `EXIT_PASS`, THE published PASS count
    for the Check_Registry SHALL exclude the Uplift_Gate's check.
12. WHEN `UPLIFT_FLOOR` is raised above `0.0`, THE raise SHALL be admitted only through
    `ratchet_to_measured` against a `PoweredProof` built from an artifact regenerated in the
    same job.
13. IF a proposed `UPLIFT_FLOOR` value is below the previously committed value, THEN THE raise
    SHALL be rejected, because the floor is a monotonic ratchet.
14. WHEN the powered run completes, THE reported headline uplift SHALL be accompanied by its
    interval at `1 - alpha` in the same output. *The interval does not exist today (R6.13), and
    carrying it in `UpliftArtifact` is a schema change against an `extra="forbid"` model with a
    byte-pinned canonical serialisation and an aggregate digest.*
15. THE job in `.github/workflows/uplift.yml` that runs the Uplift_Harness and evaluates the
    Uplift_Gate SHALL be declared in `infrastructure/quality/blocking-steps.yaml`, because that
    workflow's header promises "No `|| true`, no `|| echo`, no `; exit 0`, no `continue-on-error`"
    as prose no gate reads, and that file's own note records that the advisory-name rule "is
    evadable by renaming the step to carry `informational`" while a declaration is not — so C64
    does not currently police the one job in which C60 can pass.
16. WHEN a pull request changes `uplift/`, `scripts/audit/uplift_truth.py`, or
    `.github/workflows/uplift.yml`, THE CI_Pipeline SHALL report on that pull request whether the
    most recent recorded powered run predates the change, so a stale proof cannot silently outlive
    the code it measured.
17. WHEN an `UpliftArtifact` carrying an interval is serialised and read back, THE read-back
    artifact SHALL equal the original and its canonical serialisation SHALL be byte-identical,
    because the interval is a schema change to a byte-pinned model.
18. WHEN the powered run completes, THE reported headline uplift SHALL be accompanied by its
    replicate count per arm and its Fidelity_Report in the same output. *(Split out of R7.14
    because the interval half is new work and this half is not: already co-located and pinned by
    `tests/uplift/test_headline_fidelity_colocation_property.py`, retained as a regression pin.)*

**Verdict: implemented but not integrated.** The predicate is reachable, the artifact is no
longer committed, and the workflow exists; the measurement has never been taken and nothing
requires it.

**Falsification.** *What would prove this finding false:* a recorded artifact with
`incomplete: false` at `MIN_POWERED_REPLICATES`, or a required-check entry for `uplift.yml`.
*Attempted:* read the gate, the floor, the workflow, `required-checks.yaml`, and searched for
the artifact in the tree and the index. **[falsification attempted]**

---

### Requirement 8: No model has trained on non-synthetic data, and no claim is externally benchmarked

**User Story:** As a sceptic, I want the flagship model scored against a published
leaderboard, so that "intelligent" is externally auditable rather than self-certified.

**The verified reality.** `artifacts/` does not exist, so there is no checkpoint directory.
Real training exists and is gated — C37 `Models actually train (real gradient steps, ratchet)`
is `PASS`, and `scripts/audit/training_truth.py` AST-flags a `pipeline_validated` sentinel
return and an optimizer that is constructed but never stepped — but it has produced no
published artifact. `docs/runbooks/train-and-publish-checkpoint.md` exists and declares
"**Cost:** $0 (I-1) — free Colab/Kaggle GPU + the free Hugging Face Hub tier".
`agents/demand_prophet/spec.yaml:25-27` declares INV-DP-002: "90% conformal interval achieves
>=85% empirical coverage", asserted as `empirical_coverage(...) >= 0.85`, severity critical.

No claim in this repository is compared with any external benchmark, and
`git grep -i "m5\|walmart"` finds no dataset reference anywhere. The predecessor spec's
Property 29 ("Non-synthetic input is ingested faithfully and replays deterministically") is
authored against a `WorldSource` seam whose `ExternalFeedSource.poll_arrivals` returns `[]`,
so it currently passes over a stub. There is **no dataset-licence gate anywhere in the tree**,
which is why R8.1 and R8.2 now name an artifact, a schema and a registered check rather than an
intention.

**Three corrections found during refinement.**

*(a) R8.3 named the wrong field.* `Provenance.feature_source` **cannot** express "real feed
versus seeded generator": it is a closed `StrEnum` of exactly three values (`FEAST`, `FALLBACK`,
`DIRECT`) about where **features** were fetched, and a fourth value would break
`scripts/audit/runtime_substance.py:172`, which fails the demand_prophet probe unless
`feature_source == FeatureSource.FEAST`. The field carrying the distinction is
**`WorldState.source_class`**, typed `SourceProvenance` and declared by
`WorldSource.provenance()`: `SimWorldSource` -> `SEEDED`, `ExternalFeedSource` -> `EXTERNAL`, and
`feed_provenance.py` overrides to `STUB` when `poll_arrivals` is unconditionally empty.
`WorldState.is_synthetic` derives from it (AD-11). **Do not add a fourth class** — the three
values are pinned by `orchestrator.audit.models.SOURCE_CLASSES` and by a `CHECK` constraint in
`0007_decision_data_provenance.sql`. And note the straddle recorded in the Glossary: the world
seam and the training rows are two unrelated ingestion paths, and only the first carries a
provenance field today.

*(b) R8.4 and R9.3 described a path that does not exist as stated.* The live expression is
`degraded = self._model_degraded or self._feature_source == FeatureSource.FALLBACK or not has_intervals`.
A resolved checkpoint alone is **not** sufficient — all three conditions matter, and
`agents/demand_prophet/tests/test_pipeline_contract.py:82-85` pins exactly that. As previously
written, R9.3 would fail whenever Feast is unreachable, and R8.4 could be read as demanding
`degraded = false` with no published checkpoint, which is the opposite of I-7. Both now carry the
guard conditions.

*(c) R8.9's recompute does not exist and could not run against today's sidecar.*
`compare_coverage` **reads** `calibrator.last_coverage_p90` via `_read_dotted` and compares it to
`0.85`; the only recompute in the module is `recompute_final_crps`.
`agents/demand_prophet/training/train.py` writes a sidecar of exactly `version`, `smoke`, `arch`
and `calibrator` — **no `heldout` block** — so neither recompute has an input. And the declared
`quantile_levels: [0.1, 0.5, 0.9]` describe an **80%** raw-quantile band, not the
conformal-adjusted `lower_90` / `upper_90` that INV-DP-002 is about.

#### Acceptance Criteria

1. THE licence terms of the Real_Data_Feed SHALL be recorded in a version-controlled artifact
   carrying the dataset identity, the licence identifier, the licence-text URI, the read date, the
   permitted use, and the dataset revision, validated against a committed schema. *[Permanently
   unmet — see THE R8 LICENCE DECISION below. `licence_id` and `read_date` stay `null`.]*
2. THE Check_Registry SHALL include a registered check that reads the licence artifact and
   reports a non-passing result IF any declared field is absent or fails schema validation, because
   no dataset-licence gate exists anywhere in the tree today. *[C74 is non-passing **by decision**,
   not pending — see THE R8 LICENCE DECISION below. The criterion is met by the check existing and
   reporting honestly; the licence fields it reads will never be populated.]*
3. WHEN the Real_Data_Feed drives the World_Twin, THE World_Twin SHALL report `source_class` as
   `EXTERNAL` on every perceived state.
4. WHERE a checkpoint is resolved, WHILE the feature source is not `FALLBACK` and conformal
   intervals are present, WHEN a forecast is produced from Real_Data_Feed features, THE provenance
   of that forecast SHALL report `degraded` as false.
5. WHEN the Demand_Forecaster is trained on the Real_Data_Feed, THE training run SHALL record its
   score together with the identifier of the metric scored and the identifier of the published
   document that defines that metric, because "the Uncertainty-track metric" names no single
   computable quantity on its own, and that track scores quantiles and so maps onto this agent's
   pinball/CRPS objective and its conformal intervals.
6. WHEN the training run records its Uncertainty-track score, THE record SHALL carry the published
   baseline score for the same metric either as a confirmed value with its source and read date or
   as an explicitly unconfirmed entry, and SHALL carry no bare number, because a bare number
   satisfies R8.6 while violating R8.8.
7. IF the exact published leaderboard values cannot be confirmed at implementation time, THEN
   THE recorded comparison SHALL state that limitation.
8. IF a published leaderboard value is unconfirmed, THEN THAT value SHALL NOT be asserted as
   fact in any generated document.
9. WHEN held-out coverage is evaluated, THE gate SHALL recompute `coverage_p90` from the
   published sidecar's held-out **actuals** against the published **conformal-adjusted 90%**
   bounds over at least the committed minimum row count, rather than reading a recorded value.
10. IF the recomputed `coverage_p90` is below `0.85`, THEN THE gate SHALL exit non-zero
    reporting the measured value and the floor (INV-DP-002).
11. THE training SHALL introduce no paid API, SDK, dependency, or host (I-1).
12. WHERE a claim is derived from the Real_Data_Feed, THE claim SHALL be accompanied by the
    documented domain gap between daily retail demand and 10-minute quick-commerce demand.
13. THE Real_Data_Feed and quick-commerce demand SHALL be described as distinct domains in every
    document that reports a score derived from the feed.
14. THE expected-outcome record SHALL state that a sophisticated model is expected to be
    competitive rather than dominant on point accuracy, and SHALL be committed at a revision that
    is an ancestor of the scoring run's revision, so the result cannot be rationalised after the
    fact and the criterion can no longer be satisfied by never recording a prediction at all.
15. WHERE training or benchmarking is executed, THE execution SHALL occur either in the
    CI_Pipeline or on external GPU capacity that requires no billable account, no trial linked to a
    billing account, and no purchased or granted credits, and THE run record naming that execution
    environment SHALL be committed, because model training is a category-4 workload under I-0 and
    "free" without those exclusions admits a paid tier.
16. WHEN a change ingests the Real_Data_Feed for the first time, THE CI_Pipeline SHALL report the
    licence check on that same change, because "before the first ingestion" is enforceable only on
    the change that performs it.
17. WHEN the Real_Data_Feed is ingested, THE ingestion SHALL record the dataset identity, the
    dataset revision, and the number of rows consumed, because `rows` is already a required registry
    key.
18. IF the split, the aggregation level, or the metric definition used differs from the published
    competition's, THEN THE record SHALL report the result as not leaderboard-comparable rather
    than reporting a rank. *[**R8 licence decision extension, binding.** The published record SHALL
    distinguish "a published model" from "a published model scored against a published
    leaderboard", and SHALL NOT let the first be read as the second. With no accepted licence there
    is no leaderboard-comparable result at all, so this is the only distinction that keeps R8.18's
    prohibition enforceable rather than vacuous.]*

**THE R8 LICENCE DECISION — permanent, and it makes criteria unsatisfiable rather than pending.**
*Operator decision: the Kaggle M5 competition terms are **NOT** accepted. This is a permanent
state, not a queue item, and nothing below is weakened to make it satisfiable (I-7).*

`infrastructure/data/dataset-licences.yaml` therefore keeps `licence_id: null` and
`read_date: null` **permanently**. The consequences, stated once:

- **C74 is non-passing BY DECISION, not pending.** The distinction is the whole point: "pending"
  invites a future green, and there is no future in which this one arrives. The registry entry
  reports non-passing because a required field is absent, which is exactly what R8.2 asks of it,
  and that is the correct and final result.
- **The M5 score and the ancestry row are permanently `unavailable` / SKIP, and never a pass.**
  Per PRESERVE's `unavailable -> SKIP, never PASS` mapping
  (`scripts/audit/verify_claims.py::GATE_STATUS`), absence of the score is reported as absence.
  It is not a pass, it is not a failure of the training machinery, and it is not to be re-labelled.
- **The criteria that cannot now be satisfied are named rather than removed:** R8.1 and R8.2 (the
  licence fields), R8.5-R8.8 (the Uncertainty-track score and its baseline comparison), R8.14 (the
  expected-outcome record and its ancestor revision), R8.16 and R8.17 (first-ingestion licence
  check, ingestion record). **Their text stands unchanged.** None is relaxed, none is deleted, and
  none is restated as a lower bar — the honest record is that they are unmet and will stay unmet.
- **What survives the decision.** The training machinery is real and gated (C37 `PASS`), and
  R8.3, R8.4, R8.9-R8.13, R8.15 and R8.18 are unaffected by the licence state. The claim this
  requirement gives up is **external benchmark comparability**, and only that.

**Verdict: not achieved** for the benchmark, **permanently, by the licence decision above**;
**demonstrably achieved** for the training machinery that would produce it.

---

### Requirement 9: One unpublished artifact collapses five gates and the confidence contract

**User Story:** As an operator reading a confidence value, I want it derived from a live
conformal interval, so that `confidence` measures something instead of reporting a floor.

**The verified reality.** Finding 2 above, plus the guard that must not be weakened:
`scripts/audit/published_checkpoint_truth.py` fails when `source.allow_local_substitution` is
true, and records the honest behaviour when it is false. `packages/synapse_common/provenance.py:14-15`
states the contract that `confidence_basis` must name a real derivation "(conformal interval
width, ensemble variance, posterior spread, ...) — NEVER `constant`. A constant confidence above
the HITL threshold makes I-5" inoperative.

**The sharpest finding: the registered check returns PASS with no recompute.** C46 calls
`published_checkpoint_truth.evaluate` (`:1469`), **not** `assess` (`:1160`).
`evaluate` calls `recompute_final_crps` but acts on one outcome only —
`if crps.outcome is Outcome.FAIL: return fail`, then `return ok`. So **`UNAVAILABLE` falls
through to `ok`**, and `UNAVAILABLE` is the outcome for a sidecar carrying no `heldout` block —
which is every artifact today's `train.py` produces. The module docstring defers the fix rather
than hiding it: "Re-pointing C46 at `assess` is task 12.1's call." `evaluate` also never calls
`validate_entry`, so an entry with no `final_crps` yields `recorded=None` -> `UNAVAILABLE` ->
PASS. **Every recompute clause in this requirement is therefore stated against a surface C46
does not call**, which is what R9.14 fixes.

Also recorded, each read directly:

- **`compare_coverage` reads rather than recomputes.** It fetches
  `calibrator.last_coverage_p90` through `_read_dotted` (the path
  `checkpoint-truth.yaml::floors.coverage_p90.sidecar_path` commits) and compares it to the
  committed `0.85`. The only recompute in the module is `recompute_final_crps`.
- **Neither recompute has an input.** `agents/demand_prophet/training/train.py:266-271` writes a
  sidecar of exactly `version`, `smoke`, `arch`, `calibrator`. `checkpoint-truth.yaml:125-126`
  asserts that "publishing the block is a runbook step
  (`docs/runbooks/train-and-publish-checkpoint.md` step 5)", but **step 5 reads only "Upload both
  files to HF Hub (checkpoint + serving sidecar)"** — it says nothing about a held-out block.
  R9.13 assumes that step is added; until it is, both recomputes are unavailable by construction.
- **What publication actually flips, and what it does not.** C38
  (`checkpoint_truth.ARTIFACTS_DIR = artifacts/training`), C40
  (`calibration_truth.ARTIFACTS_DIR`, same path) and C45
  (`runtime_substance.CHECKPOINT_DIR = artifacts/checkpoints`) all read **local** files, and
  C45's per-agent probe tests `ckpt.is_file()` (`:129`) **before** importing or constructing
  `ModelRegistry` (`:132`, `:154`), so it skips before any download could occur. Publishing to
  the remote source flips only **C46** and **C69**. Finding 2's "five gates" is the count of
  gates the absent artifact collapses, not the count publication alone repairs — R9.15 carries
  the difference.
- **R9.4's nearest local enforcer catches only total collapse.** `runtime_substance.py:177`
  fails when `all(c == FALLBACK_CONFIDENCE for c in confs)` — three SKUs all returning the same
  `0.7231` pass it. That probe does assert `degraded` false, `feature_source == FEAST` (`:172`)
  and `confidence_basis == CONFORMAL_INTERVAL` (`:174`) over distinct per-SKU features (its
  `StubFeatureStore` returns "DISTINCT per-entity features", `:77`), so R9.1-R9.3 have a real
  local analogue. **R9.4 does not**, which is why it is restated below with a measurable floor.
- **R9.7's guard, verified.** `checkpoint-truth.yaml::source` records that the CI smoke job
  writes a locally built checkpoint into `local_candidate_dir: artifacts/checkpoints` (`:57`) and
  that `ModelRegistry._resolve_checkpoint_path` **prefers that local file over the remote**
  (`:38-39`), so a gate that resolved through `ModelRegistry` would certify a *smoke* artifact as
  the published model. The comment on `allow_local_substitution: false` (`:55-56`) says the flag
  "exists to be pinned, not to be flipped".
- **R9.9 was widened from checkpoint-only to the full three-term disjunction.** As previously
  written it fired on `WHILE no checkpoint is published` alone, which is narrower than
  `pipeline.py:282-285` and narrower than its own siblings: R9.3 and R8.4 already carry all three
  guard terms, and R9.9 was the asymmetric one. It now reads on the same disjunction — no resolved
  checkpoint, **or** a fallback feature source, **or** a restored calibrator returning no
  intervals. This is a **tightening**: `degraded` is now obliged to be true in strictly more
  cases, which is the I-7-safe direction. The rendering half moved to R9.16, because what the
  Atlas_Console draws is a different subject from what the Demand_Forecaster reports and the two
  are separately testable.

**Citation corrections.**

- `docs/runbooks/train-and-publish-checkpoint.md` calls the gate **C43** in five places (`:5`,
  `:58`, `:59`, `:62`, `:75`); it is **C46**. C43 is "All 8 agents expose POST /a2a for consensus"
  (`verify_claims.py:1335`). `verify_claims.py`'s C46 docstring records a SKIP branch that
  previously mis-stamped itself `C43` — "so an unavailable published-checkpoint probe landed on
  another check's row and left C46 with no result (R10.5, design AD-14)". The runbook is the
  surviving copy of that error. **Correct the runbook, not this spec.**
- `published_checkpoint_truth.py`'s docstring cites `verify_claims.py:1151` for the C46
  registration in two places (`:54`, `:1472`); the `@register("C46", ...)` call is at **`:1251`**.
- The `:1239-1246` and `:1349` line spans this section previously carried are **not
  line-verified** and the spans have been dropped rather than restated. The clause itself is
  confirmed: the `policy` row requires `zero_cost` true and `allow_local_substitution` false, and
  "Either pin flipped is a FAIL". Both land inside `assess`, which begins at `:1160`.

#### Acceptance Criteria

1. WHEN a checkpoint is published and recorded in the Published_Checkpoint_Registry, THE
   Model_Registry SHALL resolve it through the production serving path and return an object
   whose `degraded` attribute is false.
2. WHEN a checkpoint is resolved through the production serving path, THE returned version
   string SHALL contain the sha recorded in the Published_Checkpoint_Registry.
3. WHILE a real checkpoint is resolved, its restored calibrator returns intervals, and features
   are served from the online feature path, THE Demand_Forecaster SHALL report a
   `confidence_basis` of `CONFORMAL_INTERVAL`. *(Live expression, `pipeline.py:282-285`:
   `degraded = self._model_degraded or self._feature_source == FeatureSource.FALLBACK or not
   has_intervals`. Degradation is a three-term disjunction, so a resolved checkpoint alone is not
   sufficient; `agents/demand_prophet/tests/test_pipeline_contract.py:80-85` pins the mirror case
   — Feast resolved, model absent, still degraded — which is what establishes the terms as
   independent contributors. As previously written this criterion would fail whenever Feast is
   unreachable, for a reason that has nothing to do with the checkpoint.)*
4. WHILE a real checkpoint is resolved, WHEN a batch of at least three SKUs carrying distinct
   feature vectors is served, THE Demand_Forecaster SHALL report at least two distinct confidence
   values at the four decimal places it serves, because a confidence that does not move across
   SKUs disables the I-5 HITL gate.
5. IF the artifact resolved from the Published_Checkpoint_Registry was produced by a smoke
   run, THEN THE published-checkpoint check SHALL exit non-zero, and THE reported detail
   SHALL distinguish a smoke artifact from an absent artifact.
6. THE `allow_local_substitution` flag SHALL remain false.
7. IF a recorded sha cannot be fetched from the declared zero-cost serving source, THEN THE
   published-checkpoint check SHALL exit non-zero and SHALL NOT resolve a locally built
   checkpoint in its place.
8. WHEN the Published_Checkpoint_Registry entry records `final_crps`, THE published-checkpoint
   check registered in the Check_Registry SHALL recompute that value from the published held-out
   predictions by the committed method and SHALL exit non-zero when the absolute difference
   exceeds the allowance the committed policy declares (currently `max(0.05, 0.10 x |recorded|)`).
9. WHILE no checkpoint is resolved, OR the feature source is the fallback path, OR the restored
   calibrator returns no intervals, THE Demand_Forecaster SHALL report `degraded` as true on every
   response, because degradation is the three-term disjunction at `pipeline.py:282-285` and a
   checkpoint alone does not establish health.
10. WHEN a task record asserts a landed Published_Checkpoint_Registry entry, THE
    task-completion check SHALL read the registry, and IF that file holds no validated
    non-placeholder entry, THEN THE check SHALL fail naming the task record.
11. WHEN a real checkpoint is published to the declared zero-cost source and its record is
    committed, THE published-checkpoint check `C46` SHALL report a status derived from the fetched
    artifact and the committed record, replacing its current
    `DP_HF_REPO unset - no published model claimed (operator step)` SKIP.
12. WHEN the commit that publishes a checkpoint lands, THAT commit SHALL include the
    Truth_Ledger's generated region as projected by one Check_Registry execution at that revision,
    so every changed check status is generated rather than transcribed. *(The original "SHALL name
    each check" is a hand-transcription obligation — the defect R4 removes.)*
13. WHEN a checkpoint is published, THE published sidecar SHALL carry the held-out block in the
    shape the committed policy declares, including per-horizon predictions, actuals, and the
    conformal-adjusted 90% bounds the coverage recompute reads.
14. IF the recorded `final_crps` or `coverage_p90` cannot be recomputed from the published
    sidecar, THEN THE published-checkpoint check registered in the Check_Registry SHALL report
    unavailable, because a recorded number nobody recomputed is not evidence and a SKIP is not a
    PASS (I-7). *(Closes the live hole recorded above: `evaluate` returns `ok` on `UNAVAILABLE`.
    It also forces the registered surface to be the one carrying the recompute clauses, since a
    criterion stated against `assess` while C46 calls `evaluate` binds nothing.)*
15. WHERE a job is required to report `C38`, `C40` or `C45` against a published checkpoint, THAT
    job SHALL first materialise the published checkpoint and its sidecar at the serving checkpoint
    path those checks read, because all three read local training artifacts and publication to the
    remote source alone leaves them SKIPped.
16. WHILE the Demand_Forecaster reports `degraded` as true, THE Atlas_Console SHALL render that
    degradation on every surface that displays the agent's output.

**Verdict: not achieved** for the published model; **demonstrably achieved** for the serving
path and for honest degradation in its absence.

---

### Requirement 10: The audit chain is not externally verifiable

**User Story:** As an auditor who does not trust this repository, I want to verify the audit
chain independently, so that tamper-evidence is a claim I can check rather than one I must
accept.

**The verified reality.** C67's ledger row: `SKIP — chain=unverifiable, 0 anchor file(s); no
anchor exists; the chain is unverifiable (R6.11)`. `orchestrator/audit/anchorer.py:130` sets
`ANCHOR_DIR = REPO_ROOT / "infrastructure" / "audit_anchors"`, mirroring
`infrastructure/quality/audit-chain-bounds.yaml::anchor_freshness.anchor_dir` (`:56`); that
directory **does not exist**. `.github/workflows/publish-audit-anchor.yml` writes and signs
anchors under that path and triggers on pushes touching it. `gate-mutations.yaml` records C67 as
a `reporting_tools` entry (`:373-374`) with a reviewed reason: the passing state depends on a
fresh anchor that no committed fixture can be, so "the real proof of C67 is empirical and belongs
to the publishing workflow."

An internal tamper-evidence chain nobody outside can check is a strong internal control and a
weak external claim.

**The mechanism is named three times, inconsistently — and that is an ADR-level conflict, not a
naming slip.** `docs/adr/ADR-033-audit-chain.md:38-42` decides on a public **GitHub Releases**
artifact — "a free pseudo-blockchain root any auditor can cross-check".
`.github/workflows/publish-audit-anchor.yml` is titled **"Publish daily audit anchor to Rekor"**
and uses `sigstore/cosign-installer@v3` (`:159`) with keyless `cosign sign-blob --yes` (`:173`)
and `id-token: write` (`:47`). `docs/state/CURRENT.md:167` (C25) records **Rekor and
OpenTimestamps as unimplemented candidates** and the row as **PARTIAL**. ADR-033's rejection list
declines a notary timestamping service because it "costs money + adds a third-party dependency.
Violates I-1" (`:62-63`) — a rejection that does not reach a *free* transparency log, and the
repository already depends on public Sigstore for image signing (`cd.yml:86-94`,
`cd-gcp.yml:200-207`). So Rekor adds **no paid dependency and no new dependency class**. **The
unresolved point is therefore not I-1 compliance; it is that adopting Rekor amends a binding ADR
that was never superseded.** Hence R10.1 is stated mechanism-agnostically and the choice is
carried as **OQ-4**.

**The publication path is unreachable by any automated trigger.** The workflow discloses half of
this itself (`:127-134`): the `anchor` job pushes with `GITHUB_TOKEN`, "and GitHub does not
trigger workflows from such a push", so a scheduled anchor is signed only "on the next push to
main that touches infrastructure/audit_anchors/". The undisclosed half: `anchor` (`:50`) runs on
`schedule`/`workflow_dispatch`, `publish` (`:122`) runs on `push`/`workflow_dispatch`, and there
is **no `needs:` between them anywhere in the file** — so on `workflow_dispatch` both jobs run
concurrently and `publish`'s `git diff --name-only HEAD~1 HEAD` (`:147`) cannot see the anchor
that `anchor` is about to commit; `files=` is emitted empty (`:150`) and every signing step is
skipped on a job that reports green. **Only a human hand-commit reaches the signing steps.**
R10.9 closes it.

**What a third party must actually be given.** Read off `detect_rewrite` -> `chain_walk.walk` ->
`hash_payload_for_row`:

- the anchor bytes — the commitment is `head_hash` alone; `anchorer.py:173-175` records that
  `row_id` "is **provenance only**" and that `detect_rewrite` "uses `head_hash` alone, because
  that is all a third party holds";
- an **independent timestamp** from the log. `AnchorRecord.anchored_at` is written by the
  publisher (`:207`), so without an external timestamp the freshness half of the claim is
  self-asserted;
- an exported chain presentation in canonical walk order carrying the linkage hashes and the
  hashed content fields. **This artifact does not exist and no criterion required it.**
  `orchestrator/audit/cli.py`'s `verify` subcommand accepts `--dsn`, `--since`, `--max-rows`,
  `--timeout` and `--head` (`:540-568`) and nothing else — there is no way to hand it an exported
  row set, so today an external verifier would need live credentials to this project's Postgres.
  That is **worse** than the trust assumption R10 exists to remove;
- the committed migration boundary (`audit-chain-bounds.yaml`, `2026-05-24T11:32:51Z`, `:31`) and
  the walk bounds (`max_rows: 5000000`, `max_wall_clock_seconds: 900`, `:70-71`);
- the hash-construction rule, including the canonical-JSON settings and the genesis prev-hash
  convention.

**The head definition.** `anchorer.py:24` pins it: the head is the `current_hash` of the last row
with a **non-null** `current_hash` in canonical walk order, so a trailing run of legacy null-hash
rows (E-S9-01) does not move it. `anchorer.select_head` (`:355`) and
`packages/tests/strategies_audit.py::head_hash` (`:279-280`, "The newest non-null `current_hash`,
i.e. the head an anchor commits to") share that one definition.

**`anchor_truth.py`'s rule split is deliberate, so "exit non-zero" is too loose.**
`no-anchor` and `stale-anchor` map to exit 2 (`unavailable`); `unreadable-anchor`,
`non-canonical-anchor` and `anchor-dir-drift` map to exit 1 (`fail`) — its own table (`:25-29`)
and `_EXIT_CODES` (`:91`) agree, and `:35` gives the reason: telling "we are not anchored" apart
from "the anchor we have is broken" separates two different repairs. That module reads local
`*.json` only and has **no notion of the external log**, so it cannot detect what R10.4
previously asked of it.

**The workflow is undeclared.** `publish-audit-anchor.yml` appears in neither
`infrastructure/quality/blocking-steps.yaml` nor `infrastructure/quality/required-checks.yaml`,
while its own header asserts that "The freshness step propagates its exit status deliberately"
(`:26`). That is unpoliced prose — the same defect shape R7.15 fixes for `uplift.yml`. R10.11
closes it.

**Stale docstring worth flagging.** `anchor_truth.py:6` still says the daily anchor "had no
scheduled caller". That caller landed in `publish-audit-anchor.yml`.

**R10 cites ADR-033** (`docs/adr/ADR-033-audit-chain.md`) as the binding decision for the area it
touches; the previous version of this requirement cited no ADR at all.

#### Acceptance Criteria

1. WHEN the Anchor_Publisher publishes an anchor, THE Anchor_Publisher SHALL publish it to an
   external log that is readable by a party holding no credential issued by this project, appends
   entries without permitting their removal or modification, and returns an entry timestamp the log
   itself asserts rather than one the publisher supplies.
2. THE published anchor SHALL commit to the current hash of the last chain row carrying a
   non-null current hash in the chain's canonical walk order at the instant the anchor was
   captured, and SHALL record that instant.
3. WHEN a third-party verification is performed using only the published anchor bytes, the
   external log's timestamp and inclusion proof for those bytes, an exported chain presentation in
   the chain's canonical walk order, and the committed migration boundary and walk bounds, THE
   verification SHALL report exactly one of chain-intact, chain-rewritten, or chain-unverifiable,
   with no credential to this project's audit database and no read of this repository's
   version-control history.
4. IF the external log does not return an entry identifier and an inclusion proof for an anchor
   after the publisher's declared retry budget is exhausted, THEN THE anchor-freshness check SHALL
   report unavailable naming the log and the failure reason, and SHALL NOT report a pass.
5. IF the newest external log entry for an anchor is older than the freshness bound read from
   `infrastructure/quality/audit-chain-bounds.yaml::anchor_freshness.max_age_hours` (a committed
   `48` at authoring time), THEN THE anchor-freshness check SHALL report unavailable naming the
   entry age and the bound. *(Scoped to the **external** entry; the local half is
   `purpose-achievement-audit` R6.11 and is not restated. `unavailable` rather than "exit non-zero"
   preserves `anchor_truth.py`'s deliberate fail-vs-unavailable split. The bound is **read**, not
   inlined, per AD-13: `load_anchor_settings` raises `SettingsUnavailableError` rather than
   defaulting.)*
6. THE external publication SHALL require no billable account, no payment credential, and no
   dependency outside the project's zero-cost set, and SHALL complete within the log's no-charge
   allowance at the project's publication rate of one anchor per UTC day (I-1).
7. THE Anchor_Publisher and the third-party verification SHALL NOT alter
   `packages/synapse_common/audit_chain.py::make_canonical_row`, and the literal-digest test that
   byte-pins it SHALL remain unchanged, because a field change requires a chain-rewrite migration,
   not a silent bump (I-4, E-S9-02). *(Verified: `make_canonical_row` at `audit_chain.py:62`;
   E-S9-02 named in that module's docstring (`:13`); `anchorer.py:67` states "`make_canonical_row`
   is untouched"; `orchestrator/audit/cli.py:20-21` states it is "never reimplemented and never
   modified: the chain is byte-pinned by a literal-digest test
   (`packages/tests/test_audit_chain.py`)". The anchoring path needs no row change at all — the
   anchor commits to `head_hash` only and is a file, not a row.)*
8. WHEN the external log accepts an anchor, THE Anchor_Publisher SHALL record the log's entry
   identifier and inclusion proof alongside the published anchor, and SHALL remain able to read
   anchors published before that record was introduced. *(Without a pointer into the log a verifier
   cannot obtain the independent timestamp R10.3 depends on; the current path commits only a
   signature and a certificate back into the same repository whose integrity is in question. The
   second clause preserves `AnchorRecord.from_payload`'s existing discipline — refusing to read a
   published anchor would destroy evidence — and the new coordinate lands in the anchor record, not
   in the canonical row.)*
9. WHEN the Anchor_Publisher produces an anchor, THE Anchor_Publisher SHALL publish that anchor
   to the external log within the same workflow run that produced it.
10. WHEN the publishing workflow has published an anchor, THE workflow SHALL verify that an
    anchor back-dated beyond the committed freshness bound drives the anchor-freshness check to a
    non-passing result. *(This discharges an obligation `gate-mutations.yaml` assigns to this
    workflow and nobody owns: its C67 entry classifies the check `reporting_tools`, excludes it
    from `declared_gates: 14`, and records that the real proof of C67 "is empirical and belongs to
    the publishing workflow", an anchor published and read back there being "the only context in
    which this gate can pass and therefore the only one in which it can be falsified". This
    criterion is deliberately the **falsifying** half — R10.5 governs the passing half, and a probe
    that only confirms green proves nothing (I-7).)*
11. THE job in `.github/workflows/publish-audit-anchor.yml` that produces and publishes an anchor
    SHALL be declared in `infrastructure/quality/blocking-steps.yaml`.

**R10 IS DEFERRED IN ITS ENTIRETY to a named follow-on spec.** *Operator decision. Deferred, not
deleted: R10.1-R10.11 keep their text, their numbers and their traceability row, and no criterion
above is weakened, relaxed or removed (I-7).*

**The follow-on spec is `.kiro/specs/external-audit-anchor/`.** It is named here and **not
created** by this change; creating it is the follow-on's own first act.

**The reason, in three parts.**

- **It is tamper-evident-publication infrastructure**, not a decision-quality measurement. Every
  criterion in R10 is about how an anchor reaches a third party and what that party can check.
- **It is orthogonal to whether consensus produces better decisions.** Nothing in R5-R7 or R9
  reads an external anchor, and no uplift number changes if one exists.
- **It is blocked on OQ-4's undischarged obligation, which this spec does not resolve.** *A
  conflict surfaced rather than resolved:* the deferral was handed down with the reason "blocked on
  open question OQ-4", but OQ-4's own entry below records **RESOLVED (2026-08-12, operator) —
  Rekor**. Both can be true only in this precise reading, which is the one recorded here: the
  **mechanism choice** is closed, and OQ-4's obligation **(i)** is not — **ADR-056 must supersede
  `docs/adr/ADR-033-audit-chain.md` before the first publication**, and this spec neither writes
  that ADR nor authorises publishing without it. R10.1 is stated mechanism-agnostically for that
  reason. **The wording "OQ-4 is open" is therefore wrong and "OQ-4's supersession obligation is
  open" is right**; the deferral stands on the second, and the first is not adopted here.

**The decision-quality claim stands without R10.** This spec's thesis is that measured decisions
are better; R10 would make the *audit trail* externally checkable, which is a different claim to a
different reader. Deferring it removes no evidence from the decision-quality argument. What is
honestly given up is the **external** half of the tamper-evidence claim: C67 remains
`SKIP — chain=unverifiable`, the internal chain remains a strong internal control, and neither is
reported as more than that.

**Two things the deferral does not touch.** The byte-pinned canonical audit row and the single head
definition remain in PRESERVE and remain binding — they are protected by I-4 and E-S9-02, not by
R10.7, and R10.7 only restated them. And the two live defects R10 documented remain **recorded**
findings for the follow-on: the `workflow_dispatch` race in `publish-audit-anchor.yml` (no `needs:`
between `anchor` and `publish`, so signing steps skip on a green job) and that workflow's absence
from `blocking-steps.yaml` and `required-checks.yaml`. Deferring the requirement does not retract
the findings.

**Verdict: not achieved** externally, **and deferred to `.kiro/specs/external-audit-anchor/`**;
**demonstrably achieved** internally.

---

## Traceability — blueprint task to requirement

Every task in blueprint Part III maps to at least one requirement.

| Blueprint task | Requirement |
| --- | --- |
| 1 — prove one gate can fail, then all fourteen | R1 |
| 2 — execute the unverified frontend property files | R2 |
| 3 — replace hardcoded `numRuns` with an inherited profile | R3 |
| 4 — fix C64 properly, and un-bend the README | R4 |
| 5 — write `ADR-055-twin-decision-relevance.md` first | R5.5-R5.7 |
| 6 — non-stationary demand (and the early `(s,S)`-regret test) | R5.1-R5.4 done; R5.8-R5.14 [C] |
| 7 — capacity and queueing | R5.15-R5.20 [D] |
| 8 — correlated lead times and supplier state | R5.21-R5.24 [C] |
| 9 — perishability coupled to order quantity, SKU substitution | R5.25-R5.27 [D]; R5.28-29 [X] |
| 10 — negative control | R6.1 |
| 11 — positive control (NEW) | R6.2-R6.4 |
| 12 — make the honest predicate the production path | R7.7-R7.10 |
| 13 — ingest M5 as the non-synthetic source | R8.1-R8.4, R8.16-R8.17 [L] |
| 14 — train and benchmark on the Uncertainty track | R8.5-R8.15, R8.18 [L] |
| 15 — publish the checkpoint, let five gates flip | R9 |
| 16 — run the powered experiment in the evaluating job | R7.1-R7.6, R7.14, R7.18 |
| 17 — ratchet the floor to the measured lower bound | R7.12, R7.13 [see R5.41] |
| 18 — anchor the chain externally | R10 [D — follow-on spec] |

**Status markers, added by the R5.4 re-cut and the R8 and R10 decisions.** `[C]` conditional on
R5.43. `[D]` deferred, text retained rather than deleted (I-7). `[X]` unsatisfiable — see
CONFLICT R under R5.29. `[L]` permanently unmet by the R8 licence decision. **A marked row is
still a mapped row:** the mapping is unchanged, only its status is recorded.

**Criteria belonging to no blueprint task.** Refinement created these; they are recorded here so
the table above is not read as complete coverage in the other direction: **R6.13-R6.16**,
**R7.15-R7.17**, **R9.13-R9.15**, **R10.8-R10.11**.

Blueprint Part V's evidence table maps to R1.3 and R1.4 (a declared mutation operator reporting
`falsified`), R5.13 and R5.28 (the world rewards intelligence), R6.5 **and R6.13** (the
instrument can see), R8.5 and R8.9 (the model is real and externally scored), R7.14 **and R7.18**
(decisions are better), and R10.3 (accountability is external).

---

## PRESERVE — what must not be broken

A plan that damages any of these is a net loss. Each is credited with its citation.

- **The generated Truth Ledger.** `docs/state/CURRENT.md`'s region between
  `<!-- generated:begin -->` (`:15`) and `<!-- generated:end -->` (`:120`) is projected from
  one Check_Registry execution; `:206` states the counts are deliberately not restated
  elsewhere because "a second statement of the same numbers is a second thing to keep in
  sync". R4.4 extends this pattern to the README; it must not replace it with a second
  hand-maintained surface.
- **The `confidence_basis` contract.** `packages/synapse_common/provenance.py:14-15` — a real
  derivation, "NEVER `constant`". R9.3 and R9.4 depend on it; nothing in this spec may relax
  it.
- **The byte-pinned canonical audit row.** `packages/synapse_common/audit_chain.py:62::make_canonical_row`.
  Append-only discipline under I-4; adding or removing a field requires a chain-rewrite
  migration (E-S9-02). R10.7 states this as a criterion because anchoring work touches the
  chain's neighbourhood.
- **The twin's refusal to invent opening stock.** `digital_twin/world/runtime.py:146::_start_from_non_seeded_source`
  starts the world genuinely empty and reports `INVENTORY_ABSENT` when a non-seeded source
  supplies nothing, "because a fabricated 100 units per SKU would be indistinguishable,
  downstream, from a real store's reported stock" (`:151-152`). R5's twin changes must not
  reintroduce a literal default on that path.
- **`unavailable -> SKIP`, never PASS.** The status mapping is
  `scripts/audit/verify_claims.py::GATE_STATUS` (`:60-66`), with `"unavailable": "SKIP"` at
  `:65`, and the aggregate rule at `:1718-1720` reports `unavailable` whenever a *required* claim
  could not be evaluated, so "an `ok` sibling no longer supplies a passing verdict for it". Every
  criterion in this spec that says "SHALL NOT report a pass" inherits from it.
- **The honest zero floor and its pin.** `uplift/uplift_floor.py:47`'s `0.0` is disclosed, not
  disguised, and pinned by `tests/uplift/test_uplift_floor_data_gate.py`. R7.12 raises it only
  through `ratchet_to_measured`; the pin moves with the value or not at all.
- **`gate-mutations.yaml`'s `reporting_tools` and `indeterminate` vocabulary.** Both are
  honest labels that never contribute a PASS. R1.5, R1.6, R1.9 and R1.10 preserve them rather
  than converting them into declarations.
- **`chain_walk.py` convention 5 — `HEAD_UNREACHABLE` is reachability, not final position**
  (`:66-69`), together with the single head definition shared by `anchorer.select_head` and
  `packages/tests/strategies_audit.py::head_hash` (the newest non-null `current_hash`). Redefine
  the recorded head as "final position" and truncation becomes undetectable: `scope_to_anchor`
  would return `reachable=True` on a truncated presentation, R10.3 would be voided, and **nothing
  would fail**. R10.2 and R10.3 both rest on this.
- **The three-valued detection vocabulary, and the two-valued reporting vocabulary above it.**
  `AnchorDetection.status` is `Literal["intact", "rewritten", "unverifiable"]`
  (`anchorer.py:331`); `AnchorTruthReport.chain_status` is `Literal["anchored", "unverifiable"]`
  (`anchor_truth.py:221`) — **and neither of the latter two is `verified`**, which that module
  states outright (`:204`). C67's docstring says the same thing from the gate side: walking the
  chain against the anchored head "is a separate job", and a PASS there means a fresh commitment
  exists to walk against, never that the chain is intact. This is the same honest-label discipline
  the `reporting_tools` and `indeterminate` entry above protects; the anchor half was unprotected,
  and R10.3, R10.4 and R10.5 all inherit from it.
- **E-S9-03 — compact canonical anchor bytes.** `AnchorRecord.to_json` emits "Compact canonical
  JSON, no trailing newline (E-S9-03)" (`anchorer.py:219-220`), and `anchor_truth.py`'s
  `non-canonical-anchor` rule fails published bytes that are not (`:28`, `:339`). This is what
  makes two anchors of the same head byte-identical and what makes a signature cover a
  deterministic blob. Every external-publication criterion in R10 depends on it.

**Numbering disambiguation, because a reader inside this document will mis-resolve it.**
`docs/state/CURRENT.md:206`'s "the drift between them is audit finding R10" and `:119`'s
"`README.md` headline counts, from this same execution (R10.9)" both refer to
**`purpose-achievement-audit`'s R10** (README drift), **not to this spec's R10** (external
anchoring). This spec's R10.9 is the same-run publication obligation.

## Non-goals

Blueprint Part VI, carried unchanged.

- **No new frontend features.** 32,087 lines already correctly report "nothing to trust yet".
  Marginal value is approximately zero until the measurement exists.
- **Do NOT declare the 49 undeclared falsification operators.** Forty-nine unverified
  declarations convert a visible gap into false assurance — the exact trade I-7 forbids, and
  the reason `gate-mutations.yaml` records C67 as a reviewed reporting tool rather than
  inventing a decorative operator for it. R1.9 and R1.10 keep the gap visible.
- **No Kubernetes or Helm breadth.** C12 (`Helm chart templates all 11 services`) and C13
  (`Linkerd/KEDA/Flagger inside Helm`) both read `PASS` in the ledger; the non-goal is
  *widening* that surface. A single GCP VM matches the I-1 zero-cost constraint, so
  orchestration breadth buys nothing this spec needs. *The blueprint described these as
  "honest skeletons"; the current ledger says PASS, so the framing is corrected here.*
- **Do not chase C44.** Its `FAIL` in the local ledger is a Windows-only `FileNotFoundError`
  on a deep `frontend/node_modules/.pnpm` path; Linux CI is unaffected. Guard the directory
  walk; do not restructure for it.
- **Deleting `.gl_scratch/uplift-wt/`** (a committed second copy of the tree) is hygiene, not
  leverage. Batch it in only if it costs minutes.

**Three added for R10**, which is otherwise unbounded and is the one requirement in this spec that
touches third-party cryptography:

- **Do not build or operate a transparency log.** R10 publishes to an **existing** one. Standing
  one up reintroduces exactly the trust assumption R10 removes: a log this project runs is a log
  this project can rewrite.
- **Do not introduce key material.** The precedent in this tree is keyless workflow-identity
  signing (`cd.yml:86-94`, `id-token: write` plus GitHub OIDC). A managed keypair adds rotation,
  custody and revocation obligations that I-1 does not fund.
- **Do not extend the guarantee past the anchored head.** `anchorer.scope_to_anchor` deliberately
  excludes rows appended after publication, "because including them would let a later, honest
  append be reported against an anchor that never covered it". R10.3 does not verify the live
  chain, and the anchor is not the walk — C67's docstring states that "walking the chain against
  the anchored head is a separate job" and then restates it: a PASS there means "a fresh commitment
  exists to walk against", never "the chain is intact".

## Dependency order

1. **R1-R4 gate trust in any later measurement.** A number reported by a gate never shown able
   to fail, on a console whose verification never ran, under a budget rule that violates I-0,
   in a workflow whose steps discard their exit status, is not evidence.
2. **R5 precedes R6.** An instrument validated on a world with no exploitable structure proves
   nothing about a world that has one. **R5.1 precedes all of R5** — it is the test that could
   falsify the finding R5 exists to fix.
3. **R6 precedes any published result from R7.** Publishing an uplift number before the
   Power_Report exists is exactly the mistake this spec was written to prevent (R6.7).
4. **R8 precedes R9.** A checkpoint published before it is trained on real data and scored
   against an external benchmark has no demonstrable value; the same artifact published after
   is measurable.
5. **R7 and R9 together precede any headline claim about decision quality.**

**R10 is independent of the measurement chain (R5-R9) and may land in parallel, with three
qualifications.**

- **First, R10 is outside R1's mechanism but not outside R1's obligation.**
  `gate-mutations.yaml` classifies C67 as `reporting_tools`, excludes it from
  `declared_gates: 14`, and routes its proof to the publishing workflow, so the Falsification_Sweep
  **structurally cannot probe it**. That is why R10.10 exists rather than a `gates:` declaration.
  R10 may land before R1; it may **not** land without its own falsification.
- **Second, R10 carries a deploy precondition no other requirement has.**
  `anchorer.anchor_today` returns `EXIT_UNAVAILABLE` when the chain holds no row with a non-null
  `current_hash`, and `publish-audit-anchor.yml` skips the anchor step entirely when
  `SYNAPSE_AUDIT_DSN` is unset (`:80-84`). So R10 cannot be validated by landing it in CI the way
  R1-R4 can: it needs a reachable audit database holding at least one hashed consensus row.
- **Third, R10 touches R4's subject.** `publish-audit-anchor.yml` is declared in neither
  `blocking-steps.yaml` nor `required-checks.yaml`, so adding steps under R10 **widens C64's blind
  spot** unless the declaration moves in the same commit — R4.3's rule, and R10.11's obligation.

## Open questions and assumptions

Blueprint Part IV asked for three decisions. They are recorded here as open, not silently
resolved. **OQ-4 and OQ-5** are not among them — both were found during this spec's own authoring.

- **OQ-1 — the sequence.** *Two corrections before the question itself.* **(i)** There is **no
  ten-week ordering in this document**: **Dependency order** above states a sequence, not
  durations, and the ten-week estimate is the blueprint's — the dangling reference is corrected
  here. **(ii)** The short path as previously written **contradicts this spec's own Dependency-order
  item 4**, which reads "R8 precedes R9". Restated as two answers:

  **Answer A — the full sequence.** Changes nothing in this document. This spec is written for it.

  **Answer B — R1-R4 plus R9, deferring R5-R8.** Flips gates in roughly two weeks and needs four
  explicit changes, none of which is optional:
  1. Amend Dependency-order item 4, and record **R8.3, R8.4, R8.5, R8.6** as **deferred, not
     skipped** (I-7).
  2. The gates still flip, but over a **synthetic-trained** checkpoint, so C46's detail must
     distinguish "a published model" from "a published model scored against a published
     leaderboard" — otherwise the flip over-claims.
  3. **R6.7 becomes the binding constraint.** The short path must carry an explicit commitment to
     publish **no** headline uplift number, or the two-week win produces exactly the meaningless
     zero Finding 4 predicts.
  4. **R5.1 is still owed and still first.** Deferring R5 wholesale would defer the falsification
     test for the very finding R5 exists to fix.

  **Decision rule.** If the operator's constraint is *a demonstrable artifact in about two weeks*,
  B delivers it at the cost of items 1-3, with item 4 non-negotiable either way. If the constraint
  is *a defensible decision-quality claim*, only A delivers it. *The blueprint's recommendation is
  the full sequence. **Unresolved.***

  **What the answer does and does not block (verified 2026-08-12).** Answer B is "R1-R4 plus R9",
  and **E0** (R2, R3, R4) plus **E1** (R1) is exactly the R1-R4 block — tasks 1-6 of the
  implementation plan. Those six tasks are therefore **identical under both answers**, and the
  first task where the answer changes anything is task 7 (E4a). So the cost of deciding late is
  bounded at six tasks rather than the whole plan, and E0/E1 may proceed while OQ-1 is open.
  This does not weaken item 4: R5.1 is still owed and still first *within R5*, whichever answer
  is taken.

  **One correction to Answer B's item 2, found while verifying R9's C46 finding.** Item 2 asks
  C46's detail to distinguish "a published model" from "a published model scored against a
  published leaderboard". That is true but is not the binding exposure. C46's live row is a
  **SKIP** (`DP_HF_REPO unset`), so the `evaluate`/`UNAVAILABLE`-falls-through-to-`ok` hole
  documented below is **latent, not currently reporting a false PASS**. It goes live at the first
  publication — which under B *is* the deliverable. So under B, task 18.3 (re-point C46 at
  `assess`) must land **before** the publish step, not after it. Under A it lands in its stated
  position regardless.
- **OQ-2 — is M5 acceptable as "real data"?** It is retail demand, not quick-commerce; daily,
  not 10-minute. Taking it buys an external published leaderboard, which no synthetic
  alternative can offer. *The blueprint's recommendation is to take the benchmark and document
  the domain gap explicitly (R8.9). Unresolved: the operator has not confirmed the domain gap
  is acceptable.*
- **OQ-3 — AD-12 and `window.__atlasHarness`.** The JTBD suite requires the harness global,
  which by AD-12 exists only in the e2e bundle. AD-12 is not a `docs/adr/ADR-*.md` file; it is
  recorded inline at `.github/workflows/frontend.yml:396`, `.github/workflows/integration.yml:247-263`
  and `frontend/.gitignore:4`, and `integration.yml:262-263` already notes that the alternative
  "needs a compose/Dockerfile change and an amendment to AD-12's wording about which bundles may
  carry the harness". *The blueprint's recommendation is to inject the global via Playwright
  `addInitScript` rather than bundle it, dissolving the tension instead of amending AD-12.
  Unresolved and carried over from the predecessor spec; R2 does not depend on it, but the
  console-effectiveness spine does.*
- **OQ-4 — which external log, and what happens to ADR-033?** The mechanism is named three times
  in the tree, inconsistently, and the three do not agree: **ADR-033** (`:38-42`) decides on a
  public **GitHub Releases** artifact; `publish-audit-anchor.yml` is titled and built for
  **Rekor** (keyless `cosign sign-blob` against public Sigstore); `docs/state/CURRENT.md:167` (C25)
  records **Rekor and OpenTimestamps as unimplemented candidates** with the row **PARTIAL**.
  Rekor introduces **no new paid dependency and no new dependency class** — ADR-033's own rejection
  is of a *notary timestamping service* that "costs money", which does not reach a free
  transparency log, and this repository already depends on public Sigstore for image signing
  (`cd.yml:86-94`, `cd-gcp.yml:200-207`). **So the unresolved point is not I-1 compliance; it is
  the un-superseded ADR.** Whichever log is chosen must be recorded in a **superseding ADR —
  ADR-056**, since ADR-054 is the highest committed and ADR-055 is already claimed by the
  Decision_Relevance_Record — **before the first publication**. R10.1 stays mechanism-agnostic so
  all candidates are judged against the same criterion; the requirement does not name an instance
  even now that one is chosen.

  **RESOLVED (2026-08-12, operator) — Rekor.** The field had already narrowed to two before the
  choice: GitHub Releases fails R10.1's independent-timestamp clause, because a release asset
  carries no timestamp the log itself asserts and it can be deleted or replaced. Between Rekor and
  OpenTimestamps, Rekor is taken on lowest delta against the tree as it stands:
  `publish-audit-anchor.yml` is already titled and built for it (keyless `cosign sign-blob`), and
  this repository already depends on public Sigstore for image signing (`cd.yml:86-94`,
  `cd-gcp.yml:200-207`), so it adds **no new dependency and no new dependency class** under I-1.
  The property that argued for OpenTimestamps — durability independent of any single operated
  log — is recorded here as the accepted cost, not as an unexamined one.

  **Two obligations follow, and neither is discharged by this entry.** (i) **ADR-056 must supersede
  ADR-033 before the first publication.** ADR-033 (`:38-42`) decided on GitHub Releases, and its
  rejection reasoning is aimed at a *paid notary timestamping service* — which does not reach a
  free transparency log, so the supersession is a correction of scope, not a reversal of judgement.
  ADR-055 is claimed by the Decision_Relevance_Record, so 056 is the next free identifier.
  (ii) `docs/state/CURRENT.md:167` (C25) records Rekor and OpenTimestamps as **unimplemented
  candidates** with the row PARTIAL. That row stays PARTIAL until the anchor actually publishes; a
  chosen mechanism is not an implemented one (I-7).

  **[R10 deferral: both obligations travel to `.kiro/specs/external-audit-anchor/`.** The mechanism
  choice above stays resolved and is not reopened. C25 stays PARTIAL, which is the honest state for
  a chosen-but-unpublished mechanism, and it is not to be read as pending completion inside this
  spec.**]**
- **OQ-5 — where the Falsification_Sweep is hosted.** R1.1's trigger and R1.14's requiredness
  cannot both be satisfied at their strongest reading, and this spec records the trade rather than
  making the choice. The sweep's own documentation names its intended host: both
  `gate_fault_injection.py`'s module docstring (`:49-53`) and its C72 note (`:1421-1424`) say the
  sweep "belongs to `ci.yml::uplift-verify`" (task 12.2), and
  `infrastructure/quality/required-checks.yaml` already declares `uplift-verify` **required**.
  But `ci.yml`'s `on.push` carries `paths-ignore` for `**.md`, `docs/**`, `plans/**` and
  `notebooks/**`, so a Markdown-only push to `main` never runs any job in that workflow — which
  makes R1.1's literal "WHEN a commit is pushed to `main`" unsatisfiable by any job in `ci.yml`.
  That is precisely the recorded reason `truth-gates` was split into its own workflow: "a job has
  no `paths:` key and cannot opt out of its workflow's filter". Hosting the sweep in a new
  push-triggered workflow would satisfy R1.1 literally, but that file's ELIGIBILITY RULE then
  excludes it from `required:` altogether, because a required check must be produced by *every*
  pull request to `main` (precedent: `sprint6-verify` and `training-smoke`, both recorded
  `reason: branch-push-only`). Conversely `ci.yml`'s `pull_request` trigger carries no path
  filter, so hosting the sweep in `uplift-verify` satisfies R1.14 on the PR event and leaves
  Markdown-only pushes to `main` uncovered. The `mutation-fast` entry is the tree's own precedent
  for accepting exactly that trade with the reason recorded rather than resolving it. *Unresolved:
  the trigger choice is the operator's, and it carries the cost recorded in R1's verified reality
  — a complete sweep's committed worst case exceeds the candidate host's committed job bound.*
- **A-1 — assumption.** `MIN_POWERED_REPLICATES = 1000` is assumed adequate until R6.5 measures
  otherwise. R6.9 and R6.10 state what happens if it is not.
- **A-2 — assumption, and the `max_examples` half is now MEASURED and was wrong by 18x.** The
  line-count ratio in Finding 1 is still carried from the blueprint and is still unverified. The
  "three pre-existing hardcoded `max_examples`" count referenced by R3.6 and R3.7 is **not**:
  task 1.4's census clause now derives it mechanically, and the answer is **56 executable
  assignments across 41 files** under `tests/uplift/` and `tests/verify/` — not three.

  The raw pattern scan finds 58; the difference of two lies in comments or string literals, and
  both are lines that *quote* an assignment rather than make one (`tests/uplift/
  test_baseline_determinism_conformance.py:22` reads "pinned with `@settings(max_examples=200)`",
  and the gate's own explanatory comment quotes that line in turn). That gap is exactly why R3.7
  asks for an executable-only counting rule: two readers counting by hand get two totals and
  neither is obviously wrong, which is how "three" survived as long as it did.

  **The gate reports this count and asserts no total** (CF-13), so the number above is a
  measurement recorded in a spec document, not a pinned threshold. The obligation it creates is
  R3.6's reporting one, not a repair: nothing in E0 rewrites 56 files. `.kiro/steering/
  local-compute-budget.md` still says "three pre-existing violations still sit in `tests/uplift/`
  and `tests/verify/`" and **that sentence is now known to be false**; correcting it is a
  steering-file edit outside this feature's scope and is raised rather than performed.
- **A-3 — assumption.** Gate statuses quoted from the Truth Ledger are from a Windows execution.
  Linux CI may differ, most likely for **C44** — a Windows-only `FileNotFoundError` on a deep
  `frontend/node_modules/.pnpm` path. **C67 is the opposite case and is named here so the two are
  not conflated.** C67 reads SKIP off the dev box for the reason its own docstring gives —
  "Locally the anchor directory is normally empty, so this row reads SKIP off the dev box" — and it
  will read SKIP on Linux CI too, because `infrastructure/audit_anchors` does not exist **anywhere**
  in the tree. Nobody should expect C67 to flip by moving to Linux; treating it as another C44
  would waste a debugging pass.
- **A-4 — superseded, not open.** The assumption that a perfect-foresight policy is implementable
  against the twin's KPI vector was replaced by R5's verified reality during authoring, which
  established that it is **not** implementable today: no scalar objective, no perfect-foresight
  seam, no holding-cost signal. **R5.33-R5.37** state what must be built and what must be recorded
  — the declared objective and its aggregation (R5.33), the per-KPI sensitivity record (R5.34), the
  inconclusive rule when an insensitive KPI carries the null (R5.35), the restock configuration
  (R5.36), and the replayable demand path a perfect-foresight policy cannot exist without (R5.37).
  This entry is retained only so the identifier does not read as silently dropped.
