# HANDOFF — decision-quality-proof

**State at end of session 1r (2026-09-01). Committed, pushed, and on PR #84.** Derive the counts,
never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 11
```

At the time of writing that reported **132 leaf tasks: 53 done, 3 authored-pending-discharge, 76
open** — 70 authorable and 6 CI-gated. Parent tasks 2, 3, 4, 5, 7, 8, 9 complete; **tasks 1 and 10
are not** — 1.2, 1.5 and 10.4 are `[~]`. E0 is authored, E1/E4a/E2a are closed, E2b is authored
with its margin rule landed and its margin value owed at checkpoint A.

**Three commits, on `feat/decision-quality-proof`, PR #84 open against `main`:**
`1f4f7d1` E4a/E2a/E2b + the margin rule (42 files) · `dd5cd8c` the protocol re-cut (5 files) ·
`e0944cb` the excluding-interval generator fix (1 file).

> **The next thing in the plan is checkpoint A, and it is an operator action, not an authoring
> session.** Tasks 6, 10.4 and 11 discharge there. **Do not author task 12** until task 11's
> verdict is recorded and is not `material`. Session 2 is then eleven tasks: 12.1–12.4, 13.1–13.7.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree
as it *is*, not as a diff against how it was.

---

## Read these first, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the cap, the three marks, the four
   checkpoints, the batch plan.
3. `CLAUDE.md` — 14 invariants, honesty contract, gate registry, `E-S*` lessons.
4. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
5. `.cursorrules` + `docs/cursor/*.md`.
6. `docs/adr/ADR-055-twin-decision-relevance.md` — the record this phase executes against.
7. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`.

When two conflict, the higher-numbered authority wins **and the conflict is surfaced, never
silently resolved.**

### The ledger has three marks and four sources

`[ ]` open · `[~]` **authored, discharge pending** — not a pass, and it carries a `discharge:`
line naming the job that owes the proof · `[x]` done **and** discharged. An *open* leaf with a
`discharge:` line is CI-gated and is not authorable work.

Authoritative: `tasks.md` checkboxes for state, `spec_ledger_census` for every count, this file
for what executed. **`tasks.meta.json` is not authority** — its `executionHistory` bulk-stamped
every task within an eleven-second window, so a record there is not evidence anything ran.

**And disk outranks all four.** Session 1 opened with eight tasks complete on disk and unchecked.
`--files` is the mechanical version of that check; read its `prior-art` lines before authoring.
Treat them as informational — `tasks.md` names some paths in order to reject them (7.1, 7.3, 8.2),
and a task that modifies an existing module always shows prior art.

---

## What is complete, and what it established

**E0 — instrument hygiene (tasks 1–4).** Fast-check budget resolver mirroring the `conftest.py`
profiles; the inventory gate's TypeScript rule **inverted** to forbid `numRuns` entirely (R3.8
forbids a minimum coexisting — do not reintroduce one); six per-file console verdicts with exactly
one passing; `workflow_shape_truth`'s `final_list_element` correction; `readme_gen` projecting the
README headline from the **nested** `verify_claims` execution C56 compares against. **Tasks 1.2
and 1.5 are `[~]`, not `[x]`:** both are TypeScript, neither has been type-checked or executed,
and this file already said so while the ledger claimed otherwise.

**E1 — gate falsifiability (task 5).** `truth-gates.yml::falsification-sweep` is a gating job with
a committed cost budget (`per_subprocess_timeout_s: 90`, `install_budget_s: 420`,
`job_timeout_minutes: 60`). `sweep_budget_truth` re-derives both counts from the declaration's own
pointers and pins `job_timeout_minutes` to the workflow's own `timeout-minutes`. Registered as
**C73**.

**E4a — feed admission (task 7).** At the *design's* paths, not `tasks.md`'s:
`infrastructure/data/dataset-licences.yaml` + schema, `data_fabric/licence.py`,
`data_fabric/ingest/m5.py`, `scripts/audit/dataset_licence_truth.py` → **C74**.
`record_ingestion` **refuses** an ingestion whose licence is unconfirmed, whose dataset is
undeclared, or whose revision disagrees with the terms read (I-6, a hard guardrail).
**Both artifacts were invisible to git until this branch fixed `.gitignore`** — see the latent
blockers in the honesty ledger below.

**E2a — decision record and instrumentation (tasks 8, 9).** `ADR-055` committed **before** any R5
engine change (R5.7). `digital_twin/simulation/policy.yaml` is the single committed
twin-parameter file; `policy.py` reads it and **refuses to default a missing key**.
`pin_extractor_truth` → **C75**, verifying all **14** declared pins resolve **by running them** —
closing the `None == None` hole where two absent values agree and a pin reports green having
compared nothing.

**The twin is instrumented, and this is the measurement that matters:**

| Config | demand_events | unmet | fill_rate | stockout_rate | avg_on_hand |
|---|---|---|---|---|---|
| restock ON (50.0) | 2784 | 402 | **0.8556** | 0.1444 | 1016.0 |
| restock OFF (0.0) | 2784 | 1784 | **0.3592** | 0.6408 | 202.1 |

`fill_rate` can now fall; before task 9.1 it could not. `demand_events` and the 2855-event demand
trace are **identical** across both arms — the demand path is provably unaffected by any arm's
actions, which is Property 49's separation clause and Property 52's substream independence as
data. Six named RNG substreams (`SUBSTREAM_NAMES` order is asserted, because `spawn` derives
children by index). `DemandTrace` recorded at generation time. `inventory_minutes` integrated
lazily at mutations and advance boundaries — never by a sampling process, which would add queue
events and could reorder same-timestamp callbacks.

**E2b — regret and comparator (task 10, except 10.4).** `uplift/regret.py`: five cost terms, every
number read from `policy.yaml`, four-valued verdict (`material` | `sub-margin` | `inconclusive` |
`unavailable`). `uplift/foresight.py`: two-pass comparator with the `demand_identical` soundness
invariant recorded, not assumed. `uplift.yml::twin-regret` + its same-commit declaration.
Measured: foresight cost 2.93 / fill 0.9149 vs no-op 11.79 / fill 0.3592.

**Task 10.4 is half landed and half owed, and the split is deliberate.** Session 1r committed the
margin's *derivation rule*; the *value* is still `null` and is owed at checkpoint A. See below.

**Session 1r — protocol revision plus the margin rule.** `scripts/audit/spec_ledger_census.py` +
16 tests. The batch plan re-cut around checkpoints A–D. The `[~]` mark introduced.
`task_claim_truth --check` added to the sweep. ADR-055 **D2.5** and the enforced margin rule
(13 tests). No spec task authored to completion.

---

## The two checkpoints that come before the work they gate

`tasks.md`'s overview says E2b precedes E2c "specifically to try to kill this spec's central claim
before the project spends its largest single block of work on a premise it declined to test". The
previous batch plan pooled tasks 11 and 14 into the final session, which preserved the authoring
order and destroyed the decision order. **A gate that fires after the work it guards is not a
gate.** They are now operator actions ahead of that work — zero local compute, so I-0 is
unaffected.

**Checkpoint A** (tasks 6, 10.4, 11) — push the branch for its first CI exposure; read the
falsification sweep's survivor list and bring it to the user before fixing anything; dispatch
`uplift.yml::twin-regret`; instantiate the margin **from the committed rule** (the run reports
`margin_rule`, `margin_rule_derives` and `comparator_headroom` for exactly this); record task 11's
verdict.

**Checkpoint B** (task 14) — after 13.7, dispatch the E2c measurements; if **any** single-objective
policy is Pareto-optimal under interval-aware dominance, consensus is provably unnecessary and E3
**must not be run**.

**Task 11's verdict is four-valued and the tree is in the fourth state.** `material` → stop,
Finding 4 falsified. `sub-margin` → confirms it, unreachable today. `inconclusive` → proceed, on
task 11's own words that "the repair is to the instrument" and E2c *is* that repair.
`unavailable` → **not a verdict at all**; it is the absence of a measurement, and I-7 forbids
reading absence as either a pass or a null. That is what checkpoint A exists to move off.

**The margin's derivation rule is landed and enforced; only its value is owed.** R5.2 says commit
the margin only after measuring it, while every other threshold here is pinned before the run
judged against it. Naively combined, those license choosing the margin with the number in hand —
deciding task 11's verdict by the choice of margin. ADR-055 **D2.5** now states the rule:

```
materiality_margin = service_points * 0.01 * weights.unmet_service      # 5.0 -> 0.40
```

Three things make it binding rather than prose. `policy.py::materiality_margin` **re-derives** a
committed value from the rule and **refuses one that disagrees**. It also refuses a margin at or
above the measured comparator headroom (`11.79 - 2.93 = 8.86`), which would be unfalsifiable by
construction. And the ratchet direction is **`down`**, because unlike an objective weight this
threshold has an obvious self-serving sign: raising it makes Finding 4 harder to falsify. The one
chosen input, `service_points: 5.0`, is flagged `chosen` exactly as the `delivery_latency` weight
is, and bracketed on both sides — below ~3.3 points it would call the incumbent's known shortfall
against its own newsvendor target (`0.8556` vs `8/9`) material; above 8.86 it cannot fire.
**A margin that could not have been written down before the number existed is not admissible.**

---

## Defects found and fixed

**Session 1.**

1. **`_apply_cold_start` deleted the catalogue** (`sim._inventory.clear()`). Harmless while a
   stockout cost nothing; once delivery became stock-conditional it meant **no demand event was
   recorded at all**, so both `fill_rate` and `stockout_rate` reported `0.0` for a city where
   every order fails — exactly the insensitive-instrument failure R5.35 exists to catch. Fixed to
   zero the levels and keep the keys: cold start now measures `stockout_rate = 1.0000` over 799
   demand events. An empty *catalogue* remains distinct from empty *stock*.
2. **The licence schema had no JSON-Schema format checker**, so `read_date: "banana"` would have
   validated — `format` is annotation-only in draft-07 by default. Now enforced at two layers,
   because `load_licence_document` deliberately skips schema validation on the runtime path.
3. **A stale `stryker-break` drift record** claimed a live 26-vs-50 hole whose own recorded
   remediation was already complete. **Two tests were failing before session 1 began.** Retired to
   a note per the block's own convention that `drift:` records only live drift.

**Session 1r.**

4. **Task 12.1 — session 2's first task — declared the path Conflict A rejected**
   (`infrastructure/quality/twin-decision-relevance.yaml`). Authoring it would have forked the
   twin's parameters across two artifacts while `pin_extractor_truth` resolves 13 pins against the
   other one. Corrected to `digital_twin/simulation/policy.yaml`.
5. **The two `kpi_sensitivity` flips were unassigned.** The protocol asserted that structures 2
   and 4 *earn* `spoilage_rate` and `delivery_latency` becoming `sensitive: true`, but neither
   task 12.3 nor 13.3 instructed the edit, and `policy.py` refuses to default a missing key. Both
   now carry the obligation explicitly, each coupled to the pin test it breaks.
6. **Task 24.1's gate identifiers were stale by two.** It said C73 was highest and that the
   dataset-licence check and `pin_extractor_truth` were "still owed"; both are registered, as C74
   and C75. **C75 is the highest; next free is C76.** Following the old text would have collided.
7. **Task 7.2 declared `scripts/audit/feed_licence_truth.py`**, which never landed — the module is
   `dataset_licence_truth.py`.
8. Two in the new census script: it rejected dotfile-rooted paths (`.github/`, `.kiro/`,
   `.claude/`) because its pattern required an alphanumeric first character, and its human report
   echoed em dashes from `tasks.md`, violating the ASCII-only console rule. The payload keeps the
   true text; only the console rendering is transliterated.

---

## Three findings that constrain future tasks

1. **The intra-day demand shape is NOT derivable from M5.** Its observation columns are **daily**
   totals; no arithmetic recovers an hour-of-day shape from daily aggregates.
   `extract_statistics` reports it `unavailable` naming the granularity gap, and `ShapeEstimate`
   structurally forbids an unavailable shape from carrying values. **Task 12.1 must source it
   elsewhere and record where — inventing a curve is precisely what R5.11 forbids.** Day-of-week
   and promotion-uplift shapes *are* derived. This is also the sharpest evidence for R8.12's
   domain gap between daily grocery and 10-minute quick-commerce demand.
2. **The benchmark metric does not line up.** M5's Uncertainty track scores **WSPL** over
   50/67/95/99% intervals; `demand_prophet` declares `quantile_levels: [0.1, 0.5, 0.9]` (an
   **80% raw** band); INV-DP-002 asserts a **conformal-adjusted 90%** band. Three interval
   families. R8.18's *not leaderboard-comparable rather than a rank* must carry this (task 19.4).
3. **Task 11 cannot confirm Finding 4 today** — only falsify it or return `inconclusive` — because
   `spoilage_rate` and `delivery_latency` are still `sensitive: false` (`_spoilage` reads neither
   inventory nor order size; `_delivery` draws travel from an independent uniform). Structures 2
   and 4 earn the flips, and tasks 12.3 and 13.3 now carry that obligation by name.

---

## Decisions taken — surfaced, then decided. Do not re-litigate.

| # | Decision |
|---|---|
| Conflict A | Twin policy file → `digital_twin/simulation/policy.yaml` (design E2c.2), not `infrastructure/quality/twin-decision-relevance.yaml`. **Task 12.1's declared path was still wrong and is now corrected.** |
| Conflict B | Licence artifact → `infrastructure/data/dataset-licences.yaml` (design E4a.1), making task 19.1 a **verification** not a migration |
| Conflict C | Property 47/48 attribution — follow the property index; extractor resolution landed in 8.3 |
| Conflict D | **C75 is the highest registered gate id; next free is C76.** Task 24.1 has now been stale twice; re-derive against `@register` at implementation time. |
| M5 licence | Fields land **explicitly null** with a `confirmation.procedure` block; the gate reports SKIP. The terms sit behind a Kaggle acceptance gate an agent must not accept. **Never invent a `licence_id`** — `CC-BY-4.0` would be indistinguishable from fact to every downstream reader. |
| Ratchets | Only 2 of 4 new pinned values got `ratchets.json` entries. A ratchet asserts a monotone better-direction; an objective **weight** has none, so inventing a `direction` would be the fabrication that file's header forbids. Recorded in `$note_on_absent_siblings`. |
| Task 7.3 | Declined the "ingestion-record block inside the licence declaration" — it would make the artifact ingestion is checked against **mutable by ingestion**. The binding runs the other way: the record pins the artifact's digest. |
| Property 49 clause 2 | Stated as the equivalent invariant *the demand path is invariant to fulfilment*, because comparing against the deleted pre-change engine would mean maintaining a second copy of the physics whose fidelity nobody checks. |
| Checkpoint order | Tasks 11 and 14 fire **before** the work they gate, as operator checkpoints A and B. Tasks 21, 22.3, 25 become C and D. |
| Margin derivation | The *rule* is pre-registered and **enforced by the reader**; the *value* is measured. MDE-shaped. Ratchet `down`, because raising a falsification threshold is the self-serving move. |
| Census | `spec_ledger_census` is local hygiene, **not** a registered check — registration precedes generation (task 24's rule). |

---

## Honesty ledger — verified vs merely authored

**Executed and green.** 108 passed / 1 skipped / 22 deselected on the fast suites. All 33
`digital_twin` tests. New property tests: 48 (13), 49 (8), 50 (6), 51 (6), 52 (7), 53 (6), 54
(16). Cheap gates, re-executed 2026-09-01 at the end of session 1r: `workflow_shape_truth` PASS
(exit 0, 370 steps, 0 findings), `pin_extractor_truth` PASS (exit 0, **14/14** resolving on both
sides), `sweep_budget_truth` PASS (exit 0, 3120s ≤ 3600s, 480s headroom), `dataset_licence_truth`
honest SKIP (exit 2), `spec_ledger_census` PASS (exit 0, every record classified).
`task_claim_truth` exits **1** on a pre-existing claim in another spec — see the expected-red list.
Session 1r: `test_spec_ledger_census.py` 16 passed; `test_materiality_margin_rule.py` 13 passed;
`test_regret_totality_property.py` 16 still passing after the margin reader was wired in (29
together); `ruff` clean on all four touched/new files; `mypy --strict` reports **no error in any
line written this session** — `policy.py:28` is the documented repo-wide `yaml` import-untyped and
the other 11 are pre-existing in `uplift/fidelity.py`, `uplift/contract.py`, `uplift/harness.py`,
`uplift/consensus_arm.py` and `orchestrator/`.

**NOT executed. Must not be claimed as passing.**

- **All TypeScript.** The five declared console property files plus `fc-budget-profile` are
  authored, not type-checked, not executed. `getDiagnostics` returns no TS signal here —
  **inconclusive, not evidence** (R2.13). Tasks 1.2 and 1.5 are `[~]` for exactly this reason.
- **`digital_twin/tests/test_env_response.py`** — module-skipped by
  `pytest.importorskip("gymnasium")` at line 17; collects **0 items**. Runs in CI. Carries a real
  new interaction: `test_good_action_beats_bad_over_seeds` asserts `mean(fast) > mean(slow)`, and
  faster dispatch now consumes stock sooner, so dispatch latency alone no longer guarantees the
  reward ordering.
- **`tests/uplift/test_aggregation_integrity_property.py::test_aggregation_integrity_under_failures`
  FAILS.** Falsifying example has `arm=''`, `seed=0`, hypothesis-built `KpiVector`s — never
  executes the twin, compares float dicts with `==`. **Diagnosed as pre-existing float fragility;
  with no before/after run that is a diagnosis, not evidence.**
- **A second flaky property was found and fixed in this session, and the way it was found matters.**
  `test_material_requires_the_interval_to_exclude_the_margin` passed twice and then failed on the
  pre-push re-verify, because `HYPOTHESIS_PROFILE=dev` draws only 10 examples per run. Its
  "excluding" interval was built from an *absolute* width, so at `width >= excess` the lower bound
  landed on or below the margin and the test asserted `material` for an interval that excludes
  nothing. `classify_regret` was right to refuse it: `low > margin` is strict because a closed
  interval whose endpoint sits on the margin **contains** it. **Fixed the precondition, not the
  assertion, and did not touch the subject** (R2.10). Verified at `HYPOTHESIS_PROFILE=heavy`, 17
  passed. **Lesson: a `dev`-profile green is 10 examples of evidence. It is not a proof.**
- **`tests/uplift/test_comparator_restock_disabled_property.py` — 7 tests, all deselected
  locally.** They are slow-marked because they drive the twin, so `-m "not slow"` skips them and
  I-0 forbids running them here. They read `comparator.restock_threshold` and `POLICY_PATH.name`,
  neither of which session 1r changed. The reachable half was checked directly rather than
  assumed: `restock_threshold` reads `0.0` and the filename is `policy.yaml`. The twin-driving
  half remains **unverified** and discharges at checkpoint A.
- **CI has never run this branch. Checkpoint A is its first exposure.** Every gate runs for the
  first time there.
- **Four pre-existing ruff violations in `scripts/audit/verify_claims.py`** (lines 19, 23, 1020,
  1315). Invisible to CI, which scopes ruff to `packages/`, `agents/`, `orchestrator/`.
  **Correction to an earlier claim in this file: the expiry is not session 5.** `verify_claims.py`
  is modified in this branch (the C73/C74/C75 registrations), so it is staged in this PR's first
  commit. The deferral holds only because `pre-commit` is **not installed** — `.git/hooks/` holds
  nothing but `.sample` files. It expires the moment anyone runs `pre-commit install`.

### Two latent blockers found while preparing the commit

1. **`.gitignore`'s bare `data/` silently ignored both E4a artifacts. FIXED in this branch.**
   `data/` matches a directory named `data` at *any* depth, so `infrastructure/data/` was
   excluded, taking `dataset-licences.yaml` and `schemas/dataset-licences.schema.json` with it.
   Because `git add` refuses an ignored path **without printing anything** unless `-f` is passed,
   task 7.1 could tick complete while its deliverable never reached CI — the same defect class as
   task 1.1's untracked console files, but silent.

   **The consequence that matters is C74's degradation becoming indistinguishable.** Locally the
   gate exits 2 as an honest SKIP because the Kaggle terms are unconfirmed. On CI it would have
   exited 2 because *the file was absent*. Same exit code, different cause, nothing to tell them
   apart — exactly the failure I-7 exists to prevent, and this file previously recorded only the
   benign cause.

   Fixed by anchoring the rule to `/data/` rather than adding an exception or using `git add -f`,
   both of which leave the trap armed for the next file. Blast radius verified empirically before
   staging: **exactly two paths become visible**, both intended. The root `data/` tree stays
   ignored (`data/bengaluru/*`), and `data_fabric/feast/data/demand_signals.parquet` stays ignored
   by its own explicit entry at `.gitignore:122`.

2. **`pre-commit install` is a larger latent blocker than the ruff debt, and it is unrecorded.**
   `.pre-commit-config.yaml:14-22` runs `mypy --strict` with
   `additional_dependencies: [pydantic>=2.7.0, types-PyYAML]` and **no `files:` filter**.
   `types-PyYAML` resolves the three `yaml` import-untyped errors this file records as repo-wide
   noise, which unmasks **nine real pre-existing errors**: `uplift/fidelity.py:43,102`,
   `uplift/harness.py:270`, `uplift/consensus_arm.py:384,385,392,637`,
   `orchestrator/guardrails/thresholds.py:118`.

   **These block commits to files that do not contain them**, because mypy follows imports:
   checking `uplift/regret.py` pulls in `fidelity.py`, `harness.py` and `consensus_arm.py`. So the
   first developer to run `pre-commit install` inherits nine failures in code this spec never
   touched, on a commit that only edits `regret.py`. Not repaired here — predecessor code, and
   repairing it under a session-protocol commit would be exactly the misdescribed diff this
   branch's commit split exists to avoid.
- **`_Unresolvable`'s N818** is cleared by a `pyproject.toml` per-file-ignore with a recorded
  reason, matching the `schema_registry.py` / `invariants.py` / `training_contract.py` precedent.
  Proven: `ruff --isolated --select N818` exits 1 naming line 139; with the ignore, exit 0.

### Observed on first CI — PR #84, run 2026-09-01. No longer predictions.

The branch is pushed (`e0944cb`) and PR **#84** is open against `main`. CI has run. **Six jobs
failed, and they decompose into four different kinds — read the kind before touching anything.**

**Predicted, and correct (3).**

- **`TypeScript strict — spec/ + tests/`** (`frontend.yml::spec-typecheck`) — predicted red by
  `tsconfig.spec.json`'s own header. **A prediction is not a dispensation (R2.15):** repair types,
  never `continue-on-error`, never narrow the project's `include`.
- **`Falsification Sweep (declared gate mutations)`** — at most 8 of 14 declared checks are
  probeable, because `falsifies()` reports `indeterminate` when a gate does not pass on the
  unmutated copy. **Read the survivor list before fixing anything, and never weaken a mutation to
  clear a survivor.** This is task 6's subject and discharges it.
- **`Truth Gates (enforcement spine)`** — the `verify_claims` spine, including C67's SKIP.

**Session 1's own discharge, and it failed (1). This is the `[~]` mark earning its place.**

- **`Lint • Typecheck • Unit` fails on Biome**, and one of its two findings is
  `frontend/src/test/setup.ts`'s `organizeImports` — **the import block task 1.2 added**. Tasks 1.2
  and 1.5 were marked `[~]` precisely because no local run or gate had ever judged them; the
  discharge has now arrived and it is red. The third ledger state predicted this exactly, where an
  `[x]` would have hidden it. **Repairing it is what turns 1.2 and 1.5 into `[x]`.**

**Pre-existing on `main`, not this branch's (2).**

- The other Biome finding, `lint/style/noNonNullAssertion` at
  `frontend/src/app/__tests__/primary-surfaces.property.test.ts:33` (`matches[0]!`), arrived in
  PR **#77** and is on `main` today. Note `biome check ./src` never scans `spec/`, so four of the
  five declared console property files are not linted by this job at all.
- **`Audit-chain tamper detection against Postgres`** — `main`'s own `SYNAPSE Integration` run
  concluded **failure** on 2026-09-01, so this is not introduced here.

**Unclassified (1) — do not assume.**

- **`Supply-chain audit (pnpm audit + lockfile HTTPS/host check)`.** `pnpm audit` reads a live
  advisory database, so it can turn red without any code change. `main`'s last Security Scan was
  green on 2026-08-31. **Diagnose before repairing; that is a diagnosis, not evidence.**

**Also still true, and unchanged by this run:** C28's `zero-a-floor` is a disclosed survivor until
`coverage_per_package.py --require-measured-floors` lands; `gate-mutations.yaml`'s recorded
survivor shape for C16 at line 26 is **misattributed**; C67 reads SKIP on Linux too because
`infrastructure/audit_anchors` does not exist — **not another C44**.

### Checkpoint A's cost, discovered while preparing its command

`uplift.yml` declares `workflow_dispatch: {}` with **no inputs**, and holds **two** jobs:
`uplift-proof` (`timeout-minutes: 350`) and `twin-regret`. A bare dispatch therefore runs **both**,
spending up to ~350 minutes of runner time on a job checkpoint A does not need — and `uplift-proof`
cannot produce an admissible artifact yet anyway, so the spend buys nothing.

**Recommended first act of the next session:** add a `workflow_dispatch.inputs.job` selector with
an `if:` guard on each job, so `twin-regret` can be dispatched alone. Small, and it makes checkpoint
A cheap and repeatable rather than a once-per-six-hours event. Declare any new step in
`blocking-steps.yaml` in the same commit.
- **`task_claim_truth` is red, and the red belongs to another spec.** Executed 2026-09-01: 563
  records across 7 specs, exit **1**, naming `core-purpose-uplift` tasks **9** and **9.1** — both
  `[x]` while `infrastructure/ml/published_checkpoints.json` holds only `__placeholder__`. Exactly
  the defect the gate exists to catch, pre-existing, and not this spec's to repair. It is in the
  sweep anyway, because a gate you skip because it is red is a gate you have disabled. **Read the
  subject before treating a failure as yours.**
- **`task_claim_truth` will also bite at task 20.3**, confirmed at `tasks.md:1883`: that task is
  already a detected *pending* claim, because its title matches the `lands-registry-entry` pattern
  and its body names `published_checkpoints.json`. Ticking it requires the registry to hold a real
  validated non-placeholder entry.

---

## Environment notes

- **PowerShell.** `$env:VAR='x'; cmd`, **not** `set VAR=x && cmd` (`&&` is not a valid separator).
  `powershell -NoProfile -Command` is not allowlisted.
- Suppress twin logging in any engine-driving probe or the output floods:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))`.
- `types-PyYAML` is not installed locally, so `mypy --strict` reports import-untyped on every
  yaml-importing module. Pre-existing and repo-wide (70 errors across 36 files) — not introduced
  by this work.
- Python 3.14.0, pytest 8.4.2, hypothesis 6.151.11, jsonschema 4.26.0.
- `gymnasium` is not installed, which is why `test_env_response.py` skips.

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what
throttle it.

**Never run:** dev servers, watchers (`vitest` without `--run` is a watcher — in practice do not
run `vitest` at all), browsers/Playwright, `docker compose up`, anything binding a port; fan-out
execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`, `mutmut`); any `MIN_SCENARIOS`-scale
or training workload.

**Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check` — all three spawn the entire Check_Registry as a **900-second**
subprocess. `gate_fault_injection --sweep` — 30 gate subprocesses over a tree copy (precedent
**E-S13-05**: `mutmut` was validated on CI Linux runners, never the Windows dev box). `pnpm`
anything.

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, **one** scoped
`pytest` run on a single file or narrow directory, `spec_ledger_census`, and the five cheap gates
(`workflow_shape_truth`, `pin_extractor_truth`, `sweep_budget_truth`, `dataset_licence_truth`,
`task_claim_truth`).

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.** If an orchestrator template
permits 3–5, I-0 overrides it — the 2026-08-01 incident was caused by relaxing precisely that cap.

**Preferred flags:** `-x -q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.

---

## Authoring rules that will bite you

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles. A hardcoded
  value overrides the profile in *both* directions — what amplified the original I-0 incident.
  Pre-existing violations are out of scope; do not add one, and **do not assert a total** (CF-13 —
  the gate reports the count, the prose does not).
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests` (line 351);
  its fast step collects only `tests/uplift tests/verify` (line 316). A slow-marked test outside
  the slow step's four paths is selected by **no job at all**; one that must run in
  `quality-gates` must **not** be slow-marked, since that job filters `-m "not slow"`.
- **Never weaken a generator or assertion to make a property pass** (R2.10). Fix the subject — or,
  if the *precondition* was wrong, fix the precondition and say so. The difference is whether the
  subject changed or the standard did. That happened twice in session 1 and twice in 1r; every
  time the subject was correct except the census's own path pattern.
- Type hints everywhere, Pydantic v2 `ConfigDict(frozen=True)` for recorded facts, `structlog`
  never `print()` in library code, canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`, `encoding='utf-8'` on **every**
  `read_text` (E-S13-07), ASCII-only console output, lines ≤ 100 chars.
- **I-1:** never add `openai`, `anthropic`, `cohere`, or any paid SDK.
- **I-4:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7:** a SKIP is not a PASS. Absence of proof is never a pass. **"Authored and
  diagnostics-clean, not executed" is legitimate and its mark is `[~]`; "should pass" reported as
  "passes" is not.**
- **Three same-commit couplings:** a rename and its declaration; a new CI job and *both* its
  `blocking-steps.yaml` and `required-checks.yaml` entries; a schema change and every fixture that
  carries it. Either half alone is a red gate.

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — if measured `(s, S)` regret on the unmodified twin is at or above the
R5.2 margin with its interval excluding it, **Finding 4 is falsified. Stop.** R5's scope shrinks
and the spec is re-cut (R5.3, R5.4). Report it plainly; it is a good outcome.

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and **the experiment must NOT be
run.**

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor
stays at `0.0`, no headline is published as a gain, and the result is written up as a finding —
not reframed, not re-run at a different replicate count until it moves, not held back pending a
"better" configuration. A null from a **validated** instrument on a **decision-relevant** world is
worth more than the tautological PASS it replaces: before this spec, C60 could only ever report
SKIP, and `uplift_floor.py`'s `0.0` meant a measured zero compared against zero exited 2. **A
number that cannot fail is not a number.**

Two guards on reading it: a null while any objective KPI is recorded not observably sensitive is
**inconclusive**, not confirmation (task 10.5, implemented). And no headline may be published while
no Power_Report describes the harness revision under measurement (task 17.3).
