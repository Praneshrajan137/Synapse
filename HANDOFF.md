# HANDOFF — decision-quality-proof

**State at end of session 2p (2026-09-01). Committed and pushed; awaiting CI.** Derive the
counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 11
```

At the time of writing that reported **132 leaf tasks: 54 done, 3 authored-pending-discharge, 75
open** — 69 authorable and 6 CI-gated, with `next 11` returning exactly
`12.1 12.2 12.3 12.4 13.1 13.2 13.3 13.4 13.5 13.6 13.7`, which matches `SESSION_PROTOCOL.md`'s
session-2 row. Parent tasks 2, 3, 4, 5, 7, 8, 9 complete; **tasks 1 and 10 are not** — 1.2, 1.5 and
10.4 are `[~]`. E0 is authored, E1/E4a/E2a are closed, E2b is authored with its margin rule landed
and its margin value owed at checkpoint A.

> **Session 2p was pre-batch repair, not an authoring batch.** It made checkpoint A affordable, made
> checkpoint A's verdict *admissible*, repaired the discharge failures PR #84 exposed, and then
> **verified the CI run rather than trusting its own claims — which falsified two of them.** No
> session-2 task was started. The next thing in the plan is still checkpoint A, an operator action.
>
> **Five commits on `feat/decision-quality-proof`, pushed to PR #84:** `85774e1` the interval + the
> dispatch selector + the gate-surface regeneration, `d67f1c7` the first Biome repair, `77df3ef` the
> ledger, `98b37d9` the lint/format gates this branch had left red, `85ed97a` the verified CI record
> and the survivor list. Branch is **16 commits ahead of `main`.**
>
> **`frontend.yml::quality` is now GREEN, and tasks 1.2 and 1.5 are `[x]` — earned, not asserted.**
> All ten steps pass, including step 8 `Vitest unit + property tests`, which is the only route by
> which 1.5 could ever have been discharged. **Parent task 1 is complete.** Only **task 10.4**
> remains `[~]`, and it discharges at checkpoint A.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree
as it *is*, not as a diff against how it was.

---

## What is owed right now, in order

**All of it is operator work. There is no authoring owed before checkpoint A.**

1. **The survivor list is IN HAND and is recorded below and under task 6 — take it to the user, then
   decide what to fix.** Exactly one survivor, `C28/zero-a-floor`, and it is the disclosed one.
   `UNPROVEN=0`. **Task 6 is deliberately not ticked** until that review happens.
2. **Decide the `readme_gen` escalation. It is no longer speculative.** C56 is red, the counts *did*
   move (PASS 53 -> 54 -> 56), and the drift **removed C56 from the falsification measurement**, so
   it costs measurement power and not just a red tick. Repair order: `gate_surface --write` (done),
   then `ledger_gen --write`, then `readme_gen --write` — the last two ~15 min of full-core CPU each.
   **Never repair a count by hand** (I-7).
3. **Dispatch the regret measurement alone** — what session 2p's `uplift.yml` change bought:
   ```powershell
   gh workflow run uplift.yml --ref feat/decision-quality-proof --field job=twin-regret
   ```
   Then read `regret`, `interval_low`/`interval_high`, `comparator_headroom`, `margin_rule`,
   `margin_rule_derives` and `interval_excludes_rule_margin` from
   `artifacts/uplift/twin-regret.json`.
4. **Instantiate `materiality_margin.value` from the committed rule** (`service_points * 0.01 *
   weights.unmet_service`), record the headroom it was checked against, and pin the derived value.
   `policy.py::materiality_margin` will refuse a value the rule does not produce — that is intended.
   Discharges task 10.4, the last `[~]`.
5. **Record task 11's verdict** against `SESSION_PROTOCOL.md`'s four-value table, with evidence.
   Then branch: `material` -> stop and re-cut R5; `inconclusive` -> session 2's eleven tasks;
   `unavailable` -> the measurement did not happen, say so.

**The single largest obstacle is not on that list, because it is not this spec's to decide.**
`uplift-verify` needs `quality-gates` to *succeed*; `quality-gates` now fails at step 8,
`mypy --strict orchestrator/`, with **78 pre-existing errors**; and therefore **Properties 38-60 have
never executed in CI on this branch.** See failure 4 below, including why the dominant pattern must
not be "fixed" by defaulting an argument.

---

## Read these first, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the cap, the three marks, the four
   checkpoints, the batch plan, and the **six** cheap gates (a sixth joined in session 2p).
3. `CLAUDE.md` — 14 invariants, honesty contract, gate registry, `E-S*` lessons.
4. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
5. `.cursorrules` + `docs/cursor/*.md`.
6. `docs/adr/ADR-055-twin-decision-relevance.md` — the record this phase executes against.
7. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`.

When two conflict, the higher-numbered authority wins **and the conflict is surfaced, never
silently resolved.** Session 2p surfaced three; all three are recorded below.

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
and a task that modifies an existing module always shows prior art. **It now flags `uplift/interval.py`
against open task 15.2, correctly:** session 2p landed that task's estimator half early. Read 15.2's
note before authoring it.

---

## Session 2p — what changed, and why each change had to happen before the dispatch

### 1. The interval, which is the substantive one

**`uplift/regret.py::_measure` supplied no interval, and `classify_regret` reads an absent interval
as a satisfied precondition, not a missing one.** Its material branch is

```python
if regret >= margin and (interval is None or excludes_margin):
```

so on a bare point estimate at or above the margin, checkpoint A could have reported Finding 4
**falsified** and ended a 132-task spec on a number with no dispersion.

Three sources disagreed about whether that is admissible, and the disagreement was surfaced rather
than resolved silently:

| Source | What it says `material` requires |
|---|---|
| `RegretVerdict` docstring, `SESSION_PROTOCOL.md`'s checkpoint-A table | regret at or above the margin **with its interval excluding it** |
| `requirements.md` **R5.3** | at or above the margin. **No interval clause.** |
| `requirements.md` **R5.13** | the interval clause — but for the *non-stationary* twin at task 13.7, not this run |

**Resolved by changing the instrument, not the standard.** `uplift/interval.py` (design **E3.1**,
task 15.2's estimator half, landed early) supplies a paired percentile bootstrap at `1 - alpha`
from the committed Metric_Contract; `_measure` passes it. **`classify_regret`'s logic is
unchanged** — supplying a non-`None` interval is what makes `excludes_margin` load-bearing, so all
17 of task 10.6's pinned properties still hold. A measurement whose dispersion cannot be estimated
reports `status: unavailable` and the CLI exits 2, failing the job; it is never downgraded to a
point-estimate verdict.

**This is stricter than R5.3 requires, deliberately.** Adopting an undemanded standard is only
legitimate in the direction that makes falsification *harder to claim*. The reverse would be
metric-shopping. Recorded in task 11 so a reader comparing the run to R5.3 finds the deviation
stated.

**What the estimator is, and the three things about it that are not free choices.**

- A paired bootstrap over replicate-aligned samples; the statistic is the mean paired difference,
  which is exactly `RegretObjective.regret`'s estimator *and* the headline uplift's — one estimator
  for both call sites rather than two disagreeing about what "95%" means.
- `resamples` is **derived**: `ceil(TAIL_ORDER_STATISTICS / (alpha / 2))`, which is 2000 at the
  committed `alpha = 0.05`. The one flagged choice is `TAIL_ORDER_STATISTICS = 50` — how many
  resample statistics must lie beyond each tail bound. A bare `2000` would be a number with no
  antecedent. It carries no ratchet: unlike the materiality margin, a wider or narrower interval
  has no self-serving sign.
- The seed is committed and **its fixity, not its value, is the point.** The module states the
  honesty clause explicitly: re-seeding after seeing an interval — until a lower bound clears a
  floor, or until an interval excludes a margin — is metric-shopping with extra steps.

### 2. The dispatch selector, which is what makes checkpoint A repeatable

`uplift.yml` had `workflow_dispatch: {}` and two jobs, so a bare dispatch ran both — spending up to
~350 runner-minutes on `uplift-proof`, which cannot produce an admissible artifact until E3/E5. It
now has `workflow_dispatch.inputs.job` (`both` | `uplift-proof` | `twin-regret`) and an `if:` guard
per job.

Two details that were reasoned about rather than defaulted:

- **`default: both`, and the guard's leading disjunct is `github.event_name != 'workflow_dispatch'`.**
  On `schedule` there are no inputs at all, so a guard written only against `inputs.job` would
  silently disable the nightly proof — and a job that stops running is indistinguishable from a job
  that passes, which is the failure I-7 exists to prevent.
- **`concurrency` was left at workflow scope.** Moving it to job scope would let the two jobs run
  side by side, but it would stop being one group across two dispatches of `uplift-proof`, and the
  guarantee that key exists for — never two powered runs writing the same artifact — is worth more
  than saving an operator a wait. The consequence (a dispatch during the 03:00 UTC window queues)
  is recorded in the file rather than removed.

**No step was added, so no new `blocking-steps.yaml` entry is owed.** The existing `twin-regret`
declaration still resolves: `workflow_shape_truth` re-verified at `verdict=pass`, 370 steps, 10
declared-blocking entries.

### 3. The frontend discharge failure — four findings, not one, and none of them `main`'s

`frontend.yml::quality` failed on Biome. **All four error-level findings were authored by this
branch's own commit `5db5eb1`** (task 1.2's commit; `git merge-base --is-ancestor 5db5eb1 main`
exits 1, so it is not on `main`):

| # | Finding | Note |
|---|---|---|
| 1 | `src/test/setup.ts` — `organizeImports` | the one PR #84's log named |
| 2 | `src/test/fc-budget.ts:163` — `lint/complexity/useLiteralKeys` | **task 1.2's own module**, unrecorded |
| 3 | `src/test/fc-budget.ts` — two `format` violations | LF file, so real on CI, unrecorded |
| 4 | `src/surfaces/operations/SloBurnBoard.tsx:114` — `lint/complexity/noUselessTernary` | `git blame` attributes line 114 to `5db5eb1`; unrecorded |

**Two corrections to what this file previously recorded about that CI run.** The other finding it
named — `noNonNullAssertion` at `primary-surfaces.property.test.ts:33` — is configured `warn`, and
`biome check` on that file **exits 0**. It never failed anything; it was co-reported, not causal.
And three real error-level findings went unrecorded, so "one session-1 discharge failure" understated
it by three.

**The Biome rule was derived from the tree, then executed.** Biome 1.9.4 sorts named specifiers by
ASCII code point with the `type` keyword ignored, so SCREAMING_CASE precedes camelCase. Six
Biome-clean files on `main` agree, and one of them only ASCII ordering explains:
`degradation-rendering.property.test.ts` has `SURFACE_DATA_PATHS` before `SURFACE_DATA_PATH_IDS`,
which requires `S` (0x53) < `_` (0x5F).

### 4. C63 — the gate-surface drift nothing had recorded

**Two of this spec's own jobs were missing from `docs/state/GATE_SURFACE.md`:**
`truth-gates.yml::falsification-sweep` (task 5.6) and `uplift.yml::twin-regret` (task 10.3). Both
landed in session 1 without the regeneration `scripts/audit/gate_surface.py` requires. The committed
document carried `52 job(s), 357 step(s)` and `8 declared-blocking entries` against a tree with
**54, 370 and 10**.

`blocking-steps.yaml` predicted this in its own prose, at the point where it declines to add two
other entries: adding one "makes `gate_surface --check` (C63) FAIL until `--write` is re-run — and
C63's status is inside the counts `doc_truth` and `readme_gen` pin, so the drift cascades into C56
and the README headline."

**And `docs/state/CURRENT.md:94` records C63 as `PASS`.** So C63 was red on PR #84 against a
committed ledger that says green — which drifts `ledger_gen --check` too. **Up to four registered
gates from one missed `--write`**, and this file had it hidden inside "Truth Gates (enforcement
spine), predicted red".

Repaired: `python -m scripts.audit.gate_surface --write`, +50/-5 lines, 533 surface rows.
`--check` now exits **0**. The `if:` guards added in change 2 contributed **no** drift of their own —
the `on:` trigger test short-circuits before the `if:` is evaluated, so both jobs still render
`NOT EXECUTED` under all three synthetic contexts.

---

## The escalation that was declined, and why that was the cheaper truth

**Claim, still a prediction:** repairing C63 needed `gate_surface --write` **only**;
`ledger_gen --write` and `readme_gen --write` should be unnecessary.

**Basis:** `docs/state/CURRENT.md` already records `C63 | PASS` and its registry-verdict line names
only `C44`, `C64`, `C69` as failures. Restoring C63 to PASS therefore restores agreement rather than
moving a count, so the documents projected from those counts should not move either.

**Verifying it locally was offered, costed, and declined.** `ledger_gen --check` and
`readme_gen --check` each execute the entire Check_Registry in-process — `ledger_gen`'s own docstring
says every row is projected from "**one** in-process Check_Registry execution" — at roughly **900
seconds and ~15 minutes of full-core CPU each, ~30 minutes serial**, on a thermally throttling
laptop. That is category 3/4 under I-0.

**The decision was to push instead, and the reasoning is not just about cost.** `truth-gates.yml`
runs all three generators on this push anyway, so the local run would have bought the same answer
twice, one of them at 30 minutes of thermal budget. And the failure mode is benign: **if the
prediction is wrong, C63, C56 and the README headline go red and name the drift.** A legible failure
in a run that was going to happen is worth more than a private confirmation that costs the machine.
What would *not* have been acceptable is skipping the question — hence item 2 of the owed list.

**Do not repair a count by hand.** I-7 forbids it absolutely, and `blocking-steps.yaml` says so in
those words.

---

## What is complete, and what it established

**E0 — instrument hygiene (tasks 1–4).** Fast-check budget resolver mirroring the `conftest.py`
profiles; the inventory gate's TypeScript rule **inverted** to forbid `numRuns` entirely (R3.8
forbids a minimum coexisting — do not reintroduce one); six per-file console verdicts with exactly
one passing; `workflow_shape_truth`'s `final_list_element` correction; `readme_gen` projecting the
README headline from the **nested** `verify_claims` execution C56 compares against. **Tasks 1.2 and
1.5 remain `[~]`** — see the honesty ledger for exactly which of `quality`'s three steps are now
verified and which is not.

**E1 — gate falsifiability (task 5).** `truth-gates.yml::falsification-sweep` is a gating job with
a committed cost budget (`per_subprocess_timeout_s: 90`, `install_budget_s: 420`,
`job_timeout_minutes: 60`). `sweep_budget_truth` re-derives both counts from the declaration's own
pointers and pins `job_timeout_minutes` to the workflow's own `timeout-minutes`. Registered as
**C73**. Its job is now also present in `GATE_SURFACE.md`, which it was not.

**E4a — feed admission (task 7).** At the *design's* paths, not `tasks.md`'s:
`infrastructure/data/dataset-licences.yaml` + schema, `data_fabric/licence.py`,
`data_fabric/ingest/m5.py`, `scripts/audit/dataset_licence_truth.py` → **C74**.
`record_ingestion` **refuses** an ingestion whose licence is unconfirmed, whose dataset is
undeclared, or whose revision disagrees with the terms read (I-6, a hard guardrail).

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
number read from `policy.yaml`, four-valued verdict. `uplift/foresight.py`: two-pass comparator with
the `demand_identical` soundness invariant recorded, not assumed. `uplift.yml::twin-regret` + its
same-commit declaration, now with a job selector and an interval. Measured: foresight cost 2.93 /
fill 0.9149 vs no-op 11.79 / fill 0.3592.

**Task 10.4 is half landed and half owed, and the split is deliberate.** The margin's *derivation
rule* is committed and enforced; the *value* is still `null` and is owed at checkpoint A.

**Task 15.2 is now also half landed, and it is left `[ ]` on purpose.** The estimator exists and is
executed; the `uplift/harness.py::assemble_uplift_result` call site needs task **15.1**'s
`ArtifactInterval` and `schema_version` first. Left open rather than `[~]` because the owed half is
*authoring blocked on another task*, not a proof owed by a CI job — a `discharge:` line would be
false, and would also stop the census offering it to session 3, which is precisely what session 3
needs it to do. Task **15.3** is `[x]`: authored *and* executed.

---

## The two checkpoints that come before the work they gate

`tasks.md`'s overview says E2b precedes E2c "specifically to try to kill this spec's central claim
before the project spends its largest single block of work on a premise it declined to test". **A
gate that fires after the work it guards is not a gate.** They are operator actions ahead of that
work — zero local compute, so I-0 is unaffected.

**Checkpoint A** (tasks 6, 10.4, 11) — survivor list, then the `twin-regret` dispatch (now
cheap and alone), then the margin from the committed rule, then task 11's verdict.

**Checkpoint B** (task 14) — after 13.7, dispatch the E2c measurements; if **any** single-objective
policy is Pareto-optimal under interval-aware dominance, consensus is provably unnecessary and E3
**must not be run**.

**Task 11's verdict is four-valued and the tree is in the fourth state.** `material` → stop,
Finding 4 falsified. `sub-margin` → confirms it, unreachable today. `inconclusive` → proceed, on
task 11's own words that "the repair is to the instrument" and E2c *is* that repair.
`unavailable` → **not a verdict at all**; it is the absence of a measurement, and I-7 forbids
reading absence as either a pass or a null.

**The margin's derivation rule is landed and enforced; only its value is owed.** ADR-055 **D2.5**:

```
materiality_margin = service_points * 0.01 * weights.unmet_service      # 5.0 -> 0.40
```

`policy.py::materiality_margin` **re-derives** a committed value from the rule and **refuses one
that disagrees**. It also refuses a margin at or above the measured comparator headroom
(`11.79 - 2.93 = 8.86`), which would be unfalsifiable by construction. The ratchet direction is
**`down`**, because unlike an objective weight this threshold has an obvious self-serving sign:
raising it makes Finding 4 harder to falsify. The one chosen input, `service_points: 5.0`, is
bracketed on both sides — below ~3.3 points it would call the incumbent's known shortfall against
its own newsvendor target (`0.8556` vs `8/9`) material; above 8.86 it cannot fire.
**A margin that could not have been written down before the number existed is not admissible.**

The run now reports `interval_excludes_rule_margin` beside the verdict, so checkpoint A's operator
can see whether *this* interval would have licensed `material` at the value the rule derives —
independently of whether that value is committed yet.

---

## Defects found and fixed

**Session 1.**

1. **`_apply_cold_start` deleted the catalogue** (`sim._inventory.clear()`). Harmless while a
   stockout cost nothing; once delivery became stock-conditional it meant **no demand event was
   recorded at all**, so both `fill_rate` and `stockout_rate` reported `0.0` for a city where
   every order fails. Fixed to zero the levels and keep the keys: cold start now measures
   `stockout_rate = 1.0000` over 799 demand events.
2. **The licence schema had no JSON-Schema format checker**, so `read_date: "banana"` would have
   validated. Now enforced at two layers.
3. **A stale `stryker-break` drift record** claimed a live 26-vs-50 hole whose own recorded
   remediation was already complete. **Two tests were failing before session 1 began.**

**Session 1r.**

4. **Task 12.1 declared the path Conflict A rejected** (`infrastructure/quality/twin-decision-relevance.yaml`).
   Corrected to `digital_twin/simulation/policy.yaml`.
5. **The two `kpi_sensitivity` flips were unassigned.** Both now written into tasks 12.3 and 13.3
   explicitly, each coupled to the pin test it breaks.
6. **Task 24.1's gate identifiers were stale by two.** **C75 is the highest; next free is C76.**
7. **Task 7.2 declared `scripts/audit/feed_licence_truth.py`**, which never landed.
8. Two in the census script: dotfile-rooted paths rejected, and em dashes echoed to an ASCII-only
   console.

**Session 2p.**

9. **`classify_regret` reached `material` on a point estimate, and `_measure` supplied no
   interval.** The single most consequential defect found so far: it could have ended the spec.
   Fixed by supplying the interval, not by changing the classifier. See above.
10. **`docs/state/GATE_SURFACE.md` was stale on two of this spec's own jobs, and C63 was red on
    PR #84 while `CURRENT.md` records it PASS.** Four gates cascade from it. Repaired with
    `--write`; `gate_surface --check` added to the sweep so it cannot recur unnoticed.
11. **Three unrecorded error-level Biome findings, all from this branch's commit `5db5eb1`** —
    `fc-budget.ts:163` `useLiteralKeys`, two `fc-budget.ts` format violations, and
    `SloBurnBoard.tsx:114` `noUselessTernary`. All repaired. And the finding this file attributed
    to PR #77 is a **warning that exits 0** and never failed anything.
12. **`ledger_gen` was missing from the never-run list.** Its docstring says every row comes from
    "one in-process Check_Registry execution" — it costs what `verify_claims` costs and reads like
    a document generator. Added to `SESSION_PROTOCOL.md`'s never-run block.
13. **Design E3.1's order-invariance mechanism was wrong.** It said sorting the resample
    *statistics* makes the interval invariant to input order. It does not: the seeded index stream
    is fixed, so permuting the inputs changes which values each resample draws, sorted or not.
    Order-invariance needs the paired *differences* sorted before resampling; sorting the statistics
    is what makes percentile extraction well defined. **Both are needed and they do different
    jobs.** The subject does both; `design.md` E3.1 records the correction. Property 60's third
    clause is what found it.
14. **`task 15.2`'s "read `alpha` from the contract" is not executable in the job that needs it.**
    `uplift/contract.py` imports `scipy` at module scope; `scipy` is in neither
    `packages/requirements.txt` nor `packages/requirements-dev.txt` and reaches
    `ci.yml::uplift-verify` only transitively through `agents/*/requirements.txt`, which
    `uplift.yml::twin-regret` does not install. Routing one float through the validating reader
    would have failed the regret measurement at import — **discovered by reading the install
    closures, before a CI round trip paid for it.** Resolved with a narrow `yaml` read plus a test
    asserting the two readers agree, which runs where `scipy` is present.
15. **This file said the branch carries three commits. It carries eleven** (`main..HEAD`), and HEAD
    is `24a1a8a`, a fourth spec-doc commit it did not name.

---

## Three findings that constrain future tasks

1. **The intra-day demand shape is NOT derivable from M5.** Its observation columns are **daily**
   totals. `extract_statistics` reports it `unavailable` naming the granularity gap, and
   `ShapeEstimate` structurally forbids an unavailable shape from carrying values. **Task 12.1 must
   source it elsewhere and record where — inventing a curve is precisely what R5.11 forbids.**
2. **The benchmark metric does not line up.** M5's Uncertainty track scores **WSPL** over
   50/67/95/99% intervals; `demand_prophet` declares `quantile_levels: [0.1, 0.5, 0.9]` (an
   **80% raw** band); INV-DP-002 asserts a **conformal-adjusted 90%** band. Three interval
   families. R8.18's *not leaderboard-comparable rather than a rank* must carry this (task 19.4).
3. **Task 11 cannot confirm Finding 4 today** — only falsify it or return `inconclusive` — because
   `spoilage_rate` and `delivery_latency` are still `sensitive: false`. Structures 2 and 4 earn the
   flips, and tasks 12.3 and 13.3 carry that obligation by name.

---

## Decisions taken — surfaced, then decided. Do not re-litigate.

| # | Decision |
|---|---|
| Conflict A | Twin policy file → `digital_twin/simulation/policy.yaml` (design E2c.2) |
| Conflict B | Licence artifact → `infrastructure/data/dataset-licences.yaml` (design E4a.1) |
| Conflict C | Property 47/48 attribution — follow the property index |
| Conflict D | **C75 is the highest registered gate id; next free is C76.** Re-derive against `@register` at implementation time. |
| M5 licence | Fields land **explicitly null** with a `confirmation.procedure` block; the gate reports SKIP. **Never invent a `licence_id`.** |
| Ratchets | Only 2 of 4 new pinned values got `ratchets.json` entries. An objective **weight** has no monotone better-direction, so inventing a `direction` would be fabrication. |
| Task 7.3 | Declined the "ingestion-record block inside the licence declaration" — it would make the artifact ingestion is checked against mutable by ingestion. |
| Property 49 clause 2 | Stated as *the demand path is invariant to fulfilment*, not as a comparison against the deleted pre-change engine. |
| Checkpoint order | Tasks 11 and 14 fire **before** the work they gate, as operator checkpoints A and B. |
| Margin derivation | The *rule* is pre-registered and **enforced by the reader**; the *value* is measured. Ratchet `down`. |
| Census | `spec_ledger_census` is local hygiene, **not** a registered check. |
| **Conflict E (2p)** | **`material` requires an interval excluding the margin, which is stricter than R5.3.** Resolved toward the stricter reading because the deviation only ever makes falsification harder to *claim*. Instrument changed, classifier untouched. |
| **Interval estimator (2p)** | One estimator for regret and headline uplift, in `uplift/interval.py` at its designed path and name. Return type is `Interval` and not `ArtifactInterval` (import weight); `alpha` read with `yaml` and not via `load_contract` (`scipy`). Both deviations recorded in design.md E3.1 and pinned by tests. |
| **`gate_surface` (2p)** | Promoted to the **sixth** cheap gate in the sweep. Pure file reads, and it is the gate every workflow edit trips. `ledger_gen` went the other way, onto the never-run list. |
| **Local Biome/tsc (2p)** | The installed `biome` and `tsc` binaries may be run directly on changed files or on `./src` — bounded, single-process, sub-second-to-seconds, the analogue of `ruff`. **`pnpm` remains banned** and `vitest` remains banned outright. |

---

## Honesty ledger — verified vs merely authored

### Executed and green, session 2p

| What | Result |
|---|---|
| `tests/uplift/test_interval_estimation_property.py` | **20 passed at `dev` and re-verified at `heavy`** |
| `test_regret_totality_property.py` + `test_materiality_margin_rule.py` | **30 passed at `heavy`** — session 1r's properties survive the interval change |
| The three together, sweep profile `dev` | **50 passed** |
| `ruff` on the three touched Python files | exit 0 |
| `mypy --strict` on the same | **no error in any line written this session** except `interval.py:46`, the documented repo-wide `yaml` stub gap (identical to `policy.py:28`) |
| `biome check src/test/setup.ts` | **`HEAD` copy exits 1, working-tree copy exits 0** |
| `biome check --max-diagnostics=200 ./src` | **zero error-level lint findings** across 351 files, down from 43 errors |
| `tsc --noEmit -p tsconfig.json` | **exit 0 — the first time this branch's TypeScript has been compiled** |
| The six cheap gates | `workflow_shape_truth` 0, `pin_extractor_truth` 0, `sweep_budget_truth` 0, `dataset_licence_truth` **2** (honest SKIP), `task_claim_truth` **1** (pre-existing), `gate_surface --check` **0** |
| `spec_ledger_census --files --check` | pass, exit 0, every record classified |

### NOT executed. Must not be claimed as passing.

- **`vitest` locally. At all.** I-0 bans it. **CI ran it instead, and that is what discharged tasks
  1.2 and 1.5** — step 8 of a green `frontend.yml::quality` on the run for `85ed97a`. The lesson is
  not that the ban was costly; it is that the ban made the `[~]` mark load-bearing for three CI runs.
- **`uplift-verify`, and therefore Properties 38-60.** Skipped on every push so far, because
  `quality-gates` has never succeeded. **This spec's entire property surface has never run in CI.**
  The 46 property tests sessions 1/1r reported green, and this session's 20, are local evidence only.
- **Task 1.5's file is reached by none of the local checks, and the reason is precise.**
  `biome check ./src` never scans `frontend/spec/`; `frontend/tsconfig.json`'s `include` names only
  `frontend/spec/effectiveness/harness.ts` and `e2e-entry.ts`, **not** `__tests__/**`; only
  `frontend/vitest.config.ts`'s `include` covers it. So its discharge is by **execution**, and
  `frontend.yml::spec-typecheck` — the only job that type-checks it — is predicted red and out of
  scope (R2.15).
- **`uplift/regret.py::_measure`'s new interval path has never executed.** It drives the SimPy twin
  through `run_two_pass`, a category-4 workload. Its arithmetic is covered by Property 60 and its
  types by `mypy --strict`, but **the wired path discharges at the `twin-regret` dispatch, not
  here.**
- **`digital_twin/tests/test_env_response.py`** — module-skipped by
  `pytest.importorskip("gymnasium")`; collects **0 items**. Runs in CI.
- **`tests/uplift/test_aggregation_integrity_property.py::test_aggregation_integrity_under_failures`
  FAILS** on pre-existing float fragility. Diagnosed, not repaired; with no before/after run that
  is a diagnosis, not evidence.
- **`tests/uplift/test_comparator_restock_disabled_property.py` — 7 tests, slow-marked, deselected
  locally.** They read `comparator.restock_threshold` (`0.0`) and `POLICY_PATH.name`
  (`policy.yaml`), neither of which changed. The twin-driving half discharges at checkpoint A.
- **`ledger_gen --check` and `readme_gen --check`.** Offered, costed at ~30 minutes of full-core CPU
  serial, and declined in favour of letting the push answer it. **The push half-answered it:** C63
  went green, but the counts moved and C56 is red, so `readme_gen --write` is now **measured** as owed
  rather than predicted.
- **Four pre-existing `ruff` violations in `scripts/audit/verify_claims.py`** (19, 23, 1020, 1315),
  invisible to CI, which scopes ruff to `packages/`, `agents/`, `orchestrator/`.

### Two lessons from this session, both worth carrying

**A `dev`-profile green is ten examples of evidence, for the second session running.** Property 60's
degenerate-sample clause **passed at `dev` and failed at `heavy`**: it asserted `point == value`
exactly, and `fmean` of `n` copies of a value is one ulp off at
`value=4.413920275115946e-253, count=5`. Fixed the **precondition** (closeness for point-vs-value,
exact equality retained for `low == high == point`, which *is* exact by construction), not the
assertion, and did not touch the subject (R2.10). **Re-verify anything load-bearing at `heavy` on
one scoped file before claiming it.**

**A local red is not always a CI red, and the difference is worth proving rather than assuming.**
`biome check ./src` reports **40 `needs to be formatted` errors that do not exist on CI.** They are
`core.autocrlf` artifacts: the working tree checks out CRLF, `.gitattributes` pins only `*.sh` and
`*.sql`, and `biome.json` sets `formatter.lineEnding: lf`. **Proven, not assumed** —
`frontend/src/domain/primitives.ts` contains CRLF and is byte-identical to its `HEAD` blob once CRLF
is normalised. **Do not "fix" them:** a `biome format --write` sweep would commit a line-ending
churn diff across 40 untouched files and change nothing about the gate. It also means a local Biome
run is only admissible evidence per-file, on LF files — which is why `setup.ts`, `fc-budget.ts` and
`SloBurnBoard.tsx` (all LF, all verified individually) count and a whole-tree exit code does not.

### Observed on PR #84, run for `77df3ef`. Verified job-by-job, not inferred.

**Eight workflows ran: three green, four red, one cancelled.** Green: `Terraform Validate`,
`SYNAPSE Security Scan`, `SYNAPSE Policy Gate`. Cancelled: `SYNAPSE Mutation Testing` at 45m28s, as
on every push (precedent E-S13-05). **Two of the four failures falsified claims this session had
made.**

**1. `SYNAPSE Truth Gates` — C63 PASSED. The gate-surface repair worked.**

Proven by comparing the two runs' registry verdicts rather than by reading one:

| | previous push `24a1a8a` | this push `77df3ef` |
|---|---|---|
| registry failures | C44, C56, **C63**, C69 | C44, C56, C69 |
| PASS | 53 | **54** |

**But the prediction that justified skipping the escalation was half wrong, and the wrong half
matters.** "Restoring PASS restores agreement rather than moving a count" — the count *did* move,
53 to 54. What saves the conclusion is that **C56 was already failing on the previous push for the
same reason**: `README.md`'s generated headline claims `PASS 51 / FAIL 3 / SKIP 10 / TOTAL 64` while
the suite reports `54 / 2 / 11 / 67`. That drift is exactly session 1's three registrations (C73,
C74, C75) never regenerated into the README. **So C56 is not this session's — but the counts do move,
and `readme_gen --write` is genuinely owed. That is now measured, not predicted.**

**And the step nominated as the verifier never ran.** Step 9, `Gate-surface record matches the parsed
workflow tree`, was **skipped** because step 5 (`Check_Registry gate`) failed first. "Let CI answer
it" worked only by luck: step 5 runs the whole registry, so its verdict line carried C63's status
anyway. **A deferred verification pointed at a step that is itself gated is not a deferred
verification.** Point the next one at the registry verdict line.

**2. `Falsification Sweep` — THE SURVIVOR LIST. This is task 6's deliverable.**

```
Checks:    REGISTERED=67 DECLARED=14 FALSIFIED=6 PASS_ELIGIBLE=6 EXCLUDED=53
Operators: DECLARED=16 PROBED=16 UNPROVEN=0
```

- **Exactly one survivor, and it is the disclosed one.** `C28/zero-a-floor` — "gate exited 0 under
  the declared mutation: it does not gate this property". Recorded in `gate-mutations.yaml`,
  expected, and a defect against C28 rather than against the sweep. **No undisclosed survivor.**
- **Six gates proven to bite:** C16 `lower-stryker-break`, C57 `neutralise-one-actuator`,
  C61 `shrink-the-allowlist-subject`, C65 `rename-a-declared-required-job`,
  C66 `unresolvable-registry-gate-module`, C68 `hollow-out-the-external-feed`.
- **`UNPROVEN=0`** — every declared operator was probed. R1.16's obligation is discharged.
- **Eight indeterminate, every one because the gate does not pass on its unmutated baseline:**
  C44 x2, C56 x2, C60, C69, C70, C71, C72.
- **Task 6 predicted 8 probeable. The actual is 7, and the missing one is C56 — because the README
  drift makes C56's own baseline red.** So the unregenerated README did not merely fail a gate, it
  **removed a gate from the falsification measurement.** That is the sharpest argument available for
  running the generators: doc drift costs measurement power, not just a red tick.

**Task 6 is NOT ticked.** The list goes to the user before anything is fixed, because a gate proven
not to enforce means every number it reported is unsupported.

**3. `SYNAPSE Frontend CI` — `Lint • Typecheck • Unit` IS NOW GREEN, and it took two attempts.**

On the run for `85ed97a` all ten steps pass: **step 6 Biome lint, step 7 TypeScript strict, and step
8 `Vitest unit + property tests`.** That job is tasks 1.2 and 1.5's declared `discharge:`, so both are
now `[x]` and parent task 1 is complete. **Step 8 is the only route by which 1.5 could ever have been
discharged** — `biome check` never scans `frontend/spec/`, and `tsconfig.json`'s `include` omits
`frontend/spec/effectiveness/__tests__/**` — and I-0 bans `vitest`, so nothing local could have
judged it. That is the clearest case in this spec for why the `[~]` mark exists.

**The first attempt failed, and session 2p's claim about it was wrong.** CI reported `Found 3 errors.
Found 80 warnings.` The claim "zero error-level findings" came from an over-generalisation: 40 local
`needs to be formatted` errors, **one** file proven to be a `core.autocrlf` artifact, and that proof
extended to all 40. Three were real and CRLF noise masked them — `DataPathNotice.tsx`,
`surfaces/data-paths.ts`, `lib/interruption-precision.ts`, all from `5db5eb1`. Repaired in `98b37d9`.

**Now proven mechanically rather than argued:** `biome format --write ./src` reports "Fixed 40 files"
while `git diff` shows exactly **3** changed, because git normalises line endings under autocrlf. The
37 are line-ending-only; the 3 are the ones CI named.

**Green in that job unblocked five downstream jobs that had been skipped**, and three of them are now
red for their own reasons: `Playwright E2E + axe` (`blocking-steps.yaml` records this job as
**expected red** until its backendless-preview flakiness is fixed — disclosed, not new),
`Effectiveness harness`, and `Stryker mutation`. **None of those had ever run on this branch.** They
are newly *visible*, not newly broken, and they are the next honest reading.

Still red and out of scope: `TypeScript strict — spec/ + tests/` (predicted; R2.15 — a prediction is
not a dispensation) and `Supply-chain audit` (`pnpm audit` reads a live advisory database; diagnose
before repairing).

**4. `SYNAPSE CI` — the finding that matters most.**

`Lint + Type Check + Unit Tests` failed at **step 5**, `ruff check packages/synapse_common/ agents/
orchestrator/`, on two findings from `e000258` — this branch, not main:
`orchestrator/consensus/protocol.py:154:101 E501 (101 > 100)` and
`orchestrator/tests/consensus/test_dispatch_choke_point.py:23:8 TC003`. Both repaired in `98b37d9`,
with step 6's `ruff format --check`, which had never run and would also have failed, on 10 files —
every one of them `e000258`'s too.

**One 101-character line was gating 18 steps and 3 jobs, across two consecutive pushes, and nothing
recorded it.** Steps 6 through 23 all skipped: `mypy --strict` x3, the **I-1 no-paid-API check**, the
**I-2 reward isolation check**, the **C56 narrative-truth gate**, the unit tests, the coverage
floors. Plus `sprint6-verify`, `training-smoke`, and **`uplift-verify` — where every property test
this spec has written is supposed to run. Properties 38 through 60 have never executed in CI on this
branch.** A gate that reports nothing is indistinguishable from a gate that passes (I-7), and this is
that failure at the scale of a whole workflow.

**The repair advances the chain; it does not clear it — and the run for `85ed97a` confirms that
exactly.** Steps 5, 6 and 7 now pass; the failure moved to **step 8, `mypy --strict orchestrator/`**,
which reports **78 errors in 32 files** — 21 of them the single pattern `Missing named argument
"confidence_threshold" for "OrchestratorConfig"`, plus 24 `arg-type` and 7 `unused-ignore`. Measured
locally at CI's exact scope first, then confirmed by the run; the count is unchanged by this
session's edits and neither edited line adds one.

**That debt must NOT be cleared by giving `confidence_threshold` a default.**
`GuardrailEngine(confidence_threshold=config.confidence_threshold)` consumes it, so a silent default
would substitute an unreviewed number for a committed one on the **I-5 confidence gate** — precisely
what `policy.py` refuses to do, and what this spec exists to stop. It is `e000258`'s owner's call.

**5. `SYNAPSE Integration`** — only `Audit-chain tamper detection against Postgres` fails, and
`main`'s own run fails the same way. Pre-existing, as recorded.

**Two workflow-level facts worth holding.** `main`'s `SYNAPSE Frontend CI` is **green**, so nothing
pre-existing blocks that job — the three format errors were ours by elimination as well as by blame.
`main`'s `SYNAPSE CI` is **red**, so that workflow was already failing before this branch; this branch
adds its own findings on top of whatever main's are.

**Also still true:** C67 reads SKIP because `infrastructure/audit_anchors` does not exist;
`gate-mutations.yaml`'s recorded survivor shape for C16 at line 26 is **misattributed**;
`task_claim_truth` is red on `core-purpose-uplift` tasks 9 and 9.1 — another spec's ledger — and will
bite this spec at task 20.3.

**One environment trap found while reading the runs: the local clock is ~2h45m ahead of the commit
timestamps git and GitHub agree on.** Both put `77df3ef` at `13:27:28Z`; `Get-Date` reported
`16:12Z`. Any reasoning that compares "now" against a run's `created_at` will be wrong. **Identify a
run by `head_commit.message`, never by timestamp** — that is how these runs were confirmed to belong
to this push.

## Environment notes

- **PowerShell.** `$env:VAR='x'; cmd`, **not** `set VAR=x && cmd`. No heredocs — write a commit
  message to a temp file and use `git commit -F`.
- **PowerShell mangles the box-drawing characters Biome and some gates print.** Read exit codes, or
  use `--reporter=summary`, rather than grepping for `━`.
- Suppress twin logging in any engine-driving probe or the output floods:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))`.
- `types-PyYAML` is not installed locally, so `mypy --strict` reports import-untyped on every
  yaml-importing module. Pre-existing and repo-wide — **but `pre-commit install` would install it
  and unmask nine real pre-existing errors** in `uplift/fidelity.py:43,102`,
  `uplift/harness.py:270`, `uplift/consensus_arm.py:384,385,392,637`,
  `orchestrator/guardrails/thresholds.py:118`. Because mypy follows imports, those block commits to
  files that do not contain them. **Do not run `pre-commit install`.**
- Python 3.14.0, pytest 8.4.2, hypothesis 6.151.11, jsonschema 4.26.0. `gymnasium` absent.
- `frontend/node_modules` is installed, so `biome` and `tsc` are runnable directly. **Never via
  `pnpm`.**

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what
throttle it.

**Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
`mutmut`); any `MIN_SCENARIOS`-scale or training workload.

**Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
`pnpm` anything.

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, **one** scoped
`pytest` run on a single file or narrow directory, `spec_ledger_census`, the **six** cheap gates,
and the `biome`/`tsc` binaries on changed files.

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.**

**Preferred flags:** `-x -q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.

**Process sweep at the end of session 2p:** no background jobs; the only `node` process is Kiro
CLI's own ACP server. Nothing of this session's survived.

---

## Authoring rules that will bite you

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles. Do not assert a
  total (CF-13).
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`; its fast
  step collects only `tests/uplift tests/verify`. A slow-marked test outside the slow step's four
  paths is selected by **no job at all**.
- **Never weaken a generator or assertion to make a property pass** (R2.10). Fix the subject — or,
  if the *precondition* was wrong, fix the precondition and say so. That happened once more this
  session, and the record above names which changed.
- Type hints everywhere, Pydantic v2 `ConfigDict(frozen=True)` for recorded facts, `structlog`
  never `print()` in library code, canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`, `encoding='utf-8'` on **every**
  `read_text` (E-S13-07), ASCII-only console output, lines <= 100 chars.
- **I-1:** never add `openai`, `anthropic`, `cohere`, or any paid SDK. `uplift/interval.py` is
  stdlib-only for this reason among others.
- **I-4:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7:** a SKIP is not a PASS. **"Authored and diagnostics-clean, not executed" is legitimate and
  its mark is `[~]`.**
- **Four same-commit couplings, not three.** A rename and its declaration; a new CI job and *both*
  its `blocking-steps.yaml` and `required-checks.yaml` entries; a schema change and every fixture
  that carries it; **and any workflow job/step change or `blocking-steps.yaml` entry and
  `gate_surface --write`.** The fourth is the one session 1 missed twice.

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — if measured `(s, S)` regret on the unmodified twin is at or above the
R5.2 margin **with its interval excluding it**, **Finding 4 is falsified. Stop.** R5's scope shrinks
and the spec is re-cut (R5.3, R5.4). Report it plainly; it is a good outcome. The interval clause in
that sentence is new as of session 2p, and it is the difference between a decision and a coin flip.

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and **the experiment must NOT be run.**

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor
stays at `0.0`, no headline is published as a gain, and the result is written up as a finding —
not reframed, not re-run at a different replicate count until it moves, not held back pending a
"better" configuration. A null from a **validated** instrument on a **decision-relevant** world is
worth more than the tautological PASS it replaces: before this spec, C60 could only ever report
SKIP, and `uplift_floor.py`'s `0.0` meant a measured zero compared against zero exited 2. **A
number that cannot fail is not a number.**

Two guards on reading it: a null while any objective KPI is recorded not observably sensitive is
**inconclusive**, not confirmation (task 10.5). And no headline may be published while no
Power_Report describes the harness revision under measurement (task 17.3).

**And one more, added this session:** a `material` verdict on a point estimate with no dispersion is
not a falsification either. The instrument now refuses to produce one.
