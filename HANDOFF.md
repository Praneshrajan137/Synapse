# HANDOFF — decision-quality-proof

**State at end of session 5 (2026-09-09). Three commits pushed; the commit carrying this file is
the fourth.** Derive the counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At the time of writing that reported **140 leaf tasks: 63 done, 2 authored-pending-discharge, 75
open** — 69 authorable and **6** CI-gated, **unchanged from session 4**. **No leaf was ticked, and
that is correct**: the census offers zero authorable work behind checkpoints A and B.

> **`uplift-verify` HAS NOW RUN. For the first time in this branch's life, and it took two minutes
> of editing to make possible after five sessions of being blocked behind it.** The job's own
> verdict is the headline: **`830 passed, 9 failed`** on the fast step, with the slow step skipped
> behind it.
>
> **And its first report falsifies six sessions of "local evidence only".** Seven of those nine
> failures reproduce **locally, at `HYPOTHESIS_PROFILE=dev`, on the first try**, in four modules no
> wave ever touched — so no sweep ever ran them and no gate ever reported them. For those modules
> there was never any local evidence either. That is **finding 42**, and it is a hole in the
> verification *procedure*, not in the tests.
>
> **Conflict M's first reason is repaired** and the comparator now measures the subject R5.1 names.
> **Conflict N is why it was cheaper than costed**: the precondition four documents called
> "unlanded" had landed.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree as
it *is*, not as a diff against how it was.

---

## THE THING THAT IS NOW MEASURED, AND EXACTLY HOW FAR IT GOES

**Run `34384834900`, sha `e9db587`, `ci.yml::uplift-verify`: `steps=9`, conclusion `failure`.**

| # | Step | Result |
|---|---|---|
| 4 | Install dependencies | **success** — the closure proof taken before the push was right |
| 5 | Property + unit tests (fast — 500-example budget) | **failure**: `9 failed, 830 passed, 1 skipped, 25 deselected, 2 xpassed` in `849.90s` |
| 6 | Property + regression tests (slow — 100-example budget) | **skipped** behind step 5 |

**And the run for `4b9d0d4` — wave 3 included — is the arithmetic confirmation that this session
added nothing red.** Run `34389144752`, same job, `972.38s`:
**`9 failed, 838 passed, 1 skipped, 28 deselected, 2 xpassed`.**

| Delta `e9db587` → `4b9d0d4` | Measured | Meaning |
|---|---|---|
| passed | `830 → 838` (**+8**) | **exactly** the eight fast tests in `test_three_arm_comparator_property.py`. All pass in CI. |
| deselected | `25 → 28` (**+3**) | **exactly** the three slow twin-driving properties, correctly routed out of the fast step by `-m "not slow"`. |
| failed | `9 → 9`, **identical list** | the three-arm comparator introduced **zero** regressions. |

That is the cleanest available evidence that the repair is sound *and* that the nine failures are
not its doing: the counts move by exactly what was added and the failure set does not move at all.

**State the claim narrowly.** The **fast** surface of `tests/uplift` and `tests/verify` is now
measured. The **slow** surface is not: the six slow properties, the 623-test regression floor, the
subprocess fault-injection probe and `digital_twin`'s 1000-scenario run have still never executed.
"Properties 38–60 have executed in CI" is **not** yet a true sentence — "their fast subset has" is.

`sprint6-verify` and `training-smoke` are still `skipped`, correctly: they keep their own
`needs: quality-gates`, and only `uplift-verify`'s edge was removed.

### The nine failures, attributed mechanically

`git cat-file -e origin/main:<f>` then `git diff origin/main -- <f>`, because `git log -1` is
last-touch and ownership decides who repairs them.

| Module | Failures | On `origin/main`? | Owner |
|---|---|---|---|
| `tests/verify/test_command_path_resolution_property.py` | **5** | **absent** (1177 insertions) | **this spec** |
| `tests/verify/test_ledger_gen_property.py` | **2** | **absent** (588 insertions) | **this spec** |
| `tests/verify/test_ratchet_monotonicity_property.py` | **1** | **absent** (861 insertions) | **this spec** |
| `tests/uplift/test_aggregation_integrity_property.py` | **1** | **byte-identical** | `main`'s |

Shapes, for the next reader: three `AssertionError: generated roots collide: ['pytest']`; one
`unresolvable-command` for `orchestrator.audit.cli`; one Makefile-recipe set mismatch; `assert 1 ==
2` and `assert 'unavailable' == 'fail'` in the ledger-gen properties; `assert True is False` on the
committed `stryker-break` hole; and a float **exact-equality** comparison differing in the last
digit (`87381.33333333349` vs `...47`).

**Seven of the nine reproduce locally at `dev` on the first try.** The two exceptions are
`test_ledger_gen_property.py`'s, and they are **deliberately unexamined locally**: that module names
a registry execution and I-0 forbids `ledger_gen` in any form. Their shapes are *consistent with*
the inverted `ledger_gen`/`readme_gen` order session 4 measured — the same defect surfacing in a
property rather than in a gate — but that is **not confirmed**.

### Finding 42 — the sweep cannot see this class of failure

A hypothesis that the example budget was hiding them was formed and **refuted by measurement**:
`test_command_path_resolution_property` fails **5 of 8 at `dev`** and **5 of 8 at `heavy`**, so ten
examples suffice to find the falsifying inputs.

The real cause is `SESSION_PROTOCOL.md`'s own verification block: *"one bounded `pytest` over the
loci **that wave touched**"*. **No wave ever touched these four modules.** So they were authored,
reported authored-and-diagnostics-clean, and executed by nothing — not by a sweep, because sweeps
are scoped to changes, and not by CI, because `uplift-verify` was skipped. **The procedure verifies
what a session changed and never what it already had.**

The cheapest repair may be the one now in place: keep `uplift-verify` reachable and read it every
session. Whether the protocol should also mandate a periodic full-tree read is the operator's.

---

## WHAT SESSION 5 CHANGED

| Commit | Subject |
|---|---|
| `28cecce` | a required check that can only report `skipped` is not a gate — `needs:` removed |
| `e9db587` | a declared canonical-JSON artifact that no parser could read |
| `4b9d0d4` | a verdict that cannot be anything else is not a verdict — the three-arm comparator |
| *(fourth)* | this file, the ledger row, the prompt, and tasks 11 / 27.5 |

### Conflict N — the repair option was costed against a false premise, twice

1. `SESSION_PROTOCOL.md:285` recorded `Par_Level_Reorder` as "a declared precondition owned by
   another spec and **has not landed**"; `NEXT_SESSION_PROMPT.md` called it "another spec's
   **unlanded** precondition". **It had landed.** On disk at
   `uplift/baselines/par_level_reorder.py`; its owning spec marks tasks **2, 2.1 and 2.2 `[x]`**;
   `tests/uplift/test_par_level_reorder_properties.py` already runs Property 1 against it on
   `uplift-verify`'s fast step. Ownership is that spec's and is **not adopted here**. Availability
   was never the blocker — **`run_two_pass` invoked no `DecisionPolicy` at all.** The gap was
   wiring.
2. This file's own repair note said landing the arm would make `regret` and `comparator_headroom`
   "stop being the same expression". **It would not.** `regret` is `aggregate(policy) -
   aggregate(reference)` and the headroom was `mean_baseline - mean_foresight` over the same two
   arms, so whatever pass one became the two coincided. **They separate only if the no-op arm is
   RETAINED as a third pass.** Option (b) alone would have fixed reason 1 of conflict M and left
   reason 2 intact.

### The three-arm comparator, as landed

| Arm | Policy | Role |
|---|---|---|
| A | none (`NoOpRecordingPolicy`) | the **independent** bound: `comparator_headroom = A - C` |
| B | the committed `(s, S)` reference arm | the **subject**: `regret = B - C` |
| C | `ForesightPolicy` from A's recorded trace | the oracle |

One seed, one cadence, all three at `comparator.restock_threshold: 0.0`. The interval is estimated
over the **judged** contrast. `headroom >= regret` was a tautology under two arms — the same
subtraction on both sides — and is now a claim about the world, with `_measure` reporting
`unavailable` and exiting 2 if it fails rather than handing a verdict to a guard it has invalidated.

**Both levels are read, so the comparator introduces no chosen constant.** `s = 50` from
`engine.py::_restock_threshold` ("safety-stock level that triggers restock"); `S = 100` from its
initial-stock literal, the same one `normalisers.on_hand_units` already lifts as `100.0 x 10`.

**NOT claimed:** that `Par_Level_Reorder(s=50, S=100)` *reproduces* the twin's endogenous restock.
An internal engine guard versus an external order-up-to decision on the comparator's cadence. D2.5's
`fill_rate = 0.8556` lower bracket is a **comparable** reference for this arm, not a measurement of
it. Recorded in `policy.yaml`, in ADR-055 D2.5.1, and in the bracket test.

**One asymmetry recorded rather than closed, and it is why arm C is not routed through the shared
loop.** `Observation.inventory` is declared `Mapping[str, int]`, so a driven arm reads truncated
levels; `ForesightPolicy.decide` would then over-order by up to ~240 units per replicate ≈ **0.24
objective units** — the same order as the `0.40` margin — moving the oracle's cost **up** and the
measured regret **down**, which is the **self-serving** direction. Arm C keeps run `34366766968`'s
exact arithmetic. Closing the asymmetry means widening `Observation` for every fixture and every arm
including the consensus arm, and was not this repair's to take.

### Findings 39, 40, 41

- **39 — the instrument at the centre of checkpoint A had no test.** `run_two_pass` had one
  consumer and **no test file in the tree imported `uplift.foresight`**. `NoOpRecordingPolicy` was
  instantiated nowhere; `ForesightPolicy.decide` was never called. Both documented arms were prose.
  Arm A now drives `NoOpRecordingPolicy` through the same loop as arm B, so the claim is structural.
- **40 — the line where the wrong comparator entered.** `comparator.restock_threshold: 0.0`'s
  rationale is about `uplift/harness.py`, where an arm supplies its own `(s, S)` through `decide()`.
  `_measure` reused the key in a path driving **no** policy, so `0.0` deleted the incumbent rather
  than de-stacking an arm. Supplying the arm through `decide()` at `0.0` is exactly what that
  rationale calls correct: **R5.36 unamended, Property 53 untouched.**
- **41 — the closure proof was taken before the push and was correct.** Finding 36's lesson applied
  rather than re-learned: the walk started at the command the job runs. 117 seed modules, 304
  first-party files. Step 4 succeeded. Two flagged, neither a gap: `psycopg2` is outside the closure
  but imported at **function** scope inside `try/except ImportError` with an honest degrade, and
  **`scipy` is pinned in NO requirements file in the repository** yet arrives transitively via
  `scikit-learn` (five `agents/*/requirements.txt`) and `lifelines`. The second is a real fragility,
  recorded rather than repaired — widening the closure is the broad change defect 22 rejects.

### The artifact repair, and the test that improved it

The 215 MB non-JSON artifact is fixed at the producer, never at the declaration (R2.10). **A test
written against the first version exposed that a `structlog` level floor alone left canonicality
true only while nothing logged at ERROR** — a tolerated-exception disjunct the authoring rules
forbid — so the repair gained a **stderr logger factory** and the claim became unconditional. `|
tee` reads stdout only, so every log line and traceback still reaches the job log; nothing was traded
away. New `tests/uplift/test_regret_cli_artifact_shape_property.py` asserts over the **whole** stdout
stream (not its last line, which would have passed against the 215 MB file).

---

## What is still owed, and who owns it

- **The nine `uplift-verify` failures.** Eight are this spec's, one is `main`'s. Seven reproduce
  locally at `dev`. **This is the top of the next session's list** and it is authorable work that
  no barrier gates — it is repair, not new leaves.
- **Obstruction 2.5's other half.** `quality-gates` is still red at step 18 and is a `required:`
  check, so PR #84 still cannot merge and `main` is red too. **Disposition (b) — split the step so
  `tier_routing_accuracy` gates while `kv_cache_hit_rate` is declared unmeasurable-in-CI with its
  reason — is still owed**, and it carries an open sub-decision: C74's honest SKIP exits **2**, so
  making step 18 green requires a declared-unmeasurable floor to be non-failing, which shifts the
  honesty burden onto the declaration. **Do NOT lower the floor (R2.10) or add `continue-on-error`
  (finding 35).**
- **Checkpoint A, on the new comparator.** Run 1 by label, then the D2.5 amendment stating the
  derived literal, then the margin commit, then run 2. **The verdict may still be `material`** —
  which would now be an **admissible** falsification about the right subject, and this spec's own
  design calls that a good outcome.
- **A second regeneration**, owed by the generator order itself (`readme_gen` → README → C56 →
  `ledger_gen`; the committed order inverts it). The two parked `s`/`S` pins graduate in the same
  data edit, after it.
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35). Registered-check change.
- **CI's ruff scope** excludes nine trees including `uplift/` and `digital_twin/`: **530 lint, 254
  format (upper bound).** Widening it re-closes `quality-gates` at step 5.
- **CF-13 violations**: hardcoded `max_examples` in `tests/uplift/test_par_level_reorder_properties.py`
  (200) and `tests/uplift/test_seeded_demand_identity_property.py` (300, 200).

---

## Honesty ledger — verified vs merely authored

### Executed and measured, session 5

| What | Result |
|---|---|
| STEP 0 at the real HEAD (`e8c7c5a`, 39 ahead) | `quality-gates` 1–17 success, **18 failure**, 19–23 skipped, `uplift-verify` skipped `steps=0` |
| Barriers 11 and 14 | both named; batch **depends on both**; offer truncates to **zero** |
| `uplift-verify` install closure, at the command the job runs | **no gap** — confirmed by step 4 succeeding |
| **`ci.yml::uplift-verify`, run `34384834900`** | **`steps=9`; fast step `830 passed / 9 failed`; slow step skipped** |
| The nine failures' ownership | measured against `origin/main`, not assumed: **8 this spec's, 1 `main`'s** |
| The budget hypothesis for finding 42 | **refuted**: 5 of 8 fail at `dev` **and** at `heavy` |
| Coupling 4, shape predicted **then** measured | `--check` 1 → `--write` → 0; **3/3**; needs-clause **6 → 3**; lines 972, rows 920, uplift-verify rows 20 **all unchanged**; `workflow_shape_truth` **0** |
| `blocking-steps.yaml` comment-only edit | `gate_surface --check` **0** — moved nothing, checked rather than assumed |
| Both new pin anchors, probed as a pure function | first draft **0 matches**; corrected to **exactly one** each, capturing `50` and `100` |
| Six cheap gates | **0 / 0 / 0 / 2 / 1 / 0** |
| `spec_ledger_census --files --check` | exit **0**, **unchanged** at `140/63/2/75` |
| `pin_extractor_truth` | **14 declared / 14 probed / 14 both-sides** — not 15, not 16 |
| Lint/format ownership | the 12 in `uplift/harness.py` and the 1 in `test_materiality_margin_rule.py` proven **byte-identical at HEAD** by materialising the blob and re-running the checker — **zero added** |
| `mypy --strict` | clean on `policy.py`, `foresight.py`, `regret.py`; `uplift/` total **7 → 6** |
| Line endings / bytes | every written file uniform; trap fired on `ci.yml` (629/47), `blocking-steps.yaml` (576/38), `doc-number-pins.yaml` (518/7), each normalised by **worktree** byte count |

**Budget, honestly counted.** **Nine** bounded `pytest` invocations — above the three-per-session
figure `SESSION_PROTOCOL.md` states. Three were an author-fix-verify loop on one new file, three
were per-wave verification, three were the diagnostics that produced finding 42. Every one was
scoped to at most four files, serial, `-m "not slow"`, at `dev` except one deliberate `heavy` on a
single file to test the budget hypothesis. **Zero** wide `mypy` passes.
`ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth` not run in any form.

### NOT executed. Must not be claimed as passing.

- **The slow step, and therefore the slow half of Properties 38–60.** Skipped behind step 5.
- **The three new slow twin-driving properties** in `test_three_arm_comparator_property.py`.
  Authored, diagnostics-clean, **deselected locally and deselected in CI's fast step** — category 4
  under I-0, and a deselection is not a pass. Their eight *fast* siblings **are** CI-verified: the
  fast step's passed count moved `830 → 838` by exactly eight and its deselected count `25 → 28` by
  exactly three.
- **That the three-arm comparator produces a correct regret.** No twin measurement was taken. Its
  code paths are CI-green and its arithmetic is unexercised: what the `(s, S)` regret *is* remains
  unmeasured, and checkpoint A run 1 is its only source.
- **That the next `twin-regret` run uploads a parseable artifact.** The mechanism is asserted
  locally; the run is CI's to report.
- **`quality-gates` steps 19–23.** Still skipped behind step 18.
- **Task 11's verdict.** No margin is committed and no run has been made against the new comparator.
- **The two `test_ledger_gen_property.py` failures**, locally. I-0 forbids it.
- **`vitest`. At all.**

### The lesson from this session

**Two of the three repairs were made cheaper or safer by checking a premise that four documents
agreed on.** `Par_Level_Reorder` was recorded as unlanded and was not; the recorded fix for
conflict M's second reason would not have fixed it; and a `structlog` level floor looked sufficient
until a test asked what happens at ERROR. **Consensus across documents is not evidence — it is
usually just one unchecked claim copied forward.**

And the corollary to session 4's lesson is now measured rather than argued: **a gate that has never
executed is not evidence, and neither is a test that nothing has ever run.** Eight property
failures sat in this spec's own tree, reproducible on the first try at the cheapest profile, while
six handoffs called the surface "local evidence only".

---

## Decisions taken — surfaced, then decided. Do not re-litigate.

| # | Decision |
|---|---|
| Conflict A | Twin policy file → `digital_twin/simulation/policy.yaml` (design E2c.2) |
| Conflict B | Licence artifact → `infrastructure/data/dataset-licences.yaml` (design E4a.1) |
| Conflict C | Property 47/48 attribution — follow the property index |
| Conflict D | **C75 is the highest registered gate id; next free is C76.** |
| M5 licence | Fields land **explicitly null** with a `confirmation.procedure` block; gate reports SKIP. **Never invent a `licence_id`.** |
| Ratchets | An objective **weight** has no monotone better-direction, so it gets no ratchet. |
| Checkpoint order | Tasks 11 and 14 fire **before** the work they gate. |
| Margin derivation | The *rule* is pre-registered and **enforced by the reader**; the *value* is measured. Ratchet `down`. |
| Census | `spec_ledger_census` is local hygiene, **not** a registered check. |
| Conflict E (2p) | **`material` requires an interval excluding the margin, stricter than R5.3.** |
| Interval estimator (2p) | One estimator, `uplift/interval.py`. |
| `gate_surface` (2p) | The **sixth** cheap gate. `ledger_gen` went onto the never-run list. |
| Task 6 (2q) | **Survivor list accepted; C28's repair deferred to its owner.** E1 closed. |
| Conflict F (2q) | **The `confidence_threshold` repair is at the declaration, never at the call sites.** |
| Conflict G (2q) | **A dispatch-only — or label-conditioned — job owes no `required-checks.yaml` entry.** |
| Regeneration (2q) | **A CI job that uploads an artifact**, not a local `--write`, not an auto-commit. |
| Conflict H (2r-pre) | **The derived-margin pin is PARKED in `pending_pins:`.** `required: false` rejected. |
| Dispatch mechanism (2r-pre-c) | **Checkpoint A runs by LABEL. `main` is not touched.** Guards are allow-lists. |
| Conflict I (2r) | **CI step 8 excludes `orchestrator/tests`; the wide command is run by no workflow.** |
| Scope (2r) | The full wide 56 mypy errors were cleared, not only the 3 that gated step 8. |
| Decision 1 (3) | **Route 1 then 3.** Landed `bbe4278`. Its "then 3" premise lapsed in session 4. |
| Decision 2 (3) | **`test_cognition_phase` IS adopted**, reversing 2r's refusal. Landed `bf8693f`. |
| Ruff scope (3) | **Measured, not adopted.** 530 lint / 254 format across nine unlinted trees. |
| Conflict L (3) | `SESSION_PROTOCOL.md`'s checkpoint-A procedure was stale in four ways; corrected in place. |
| Conflict M (4) | **The margin is NOT committed.** Any value in D2.5's bracket forced `material` on a no-op comparator. |
| Obstruction 2.5 (4) | **Step 18 is structurally unmeasurable in CI.** Three dispositions costed. |
| Repair order (4) | **`ledger_gen` must run AFTER `readme_gen`.** A second regeneration is owed. |
| `scipy` bound (4) | `>=1.11,<2.0`, `twin-regret` only. A **choice**, flagged. |
| **Conflict M repair (5)** | **Option (b): `Par_Level_Reorder` as the reference arm, wired through `DecisionPolicy`** — plus the no-op arm RETAINED as a third pass, without which reason 2 survives. Both levels **read**, not chosen. |
| **Obstruction 2.5 (5)** | **(a) then (b).** `needs:` removed now because a `required:` check that can only report `skipped` is not a gate; the step-18 split lands separately and is still owed. |
| **Conflict N (5)** | **`Par_Level_Reorder` HAD landed.** Four documents said otherwise. Ownership stays with `decision-integrity-uplift-proof`; it is **not** adopted. |
| **Arm C precision (5)** | **NOT routed through the shared observe loop.** Truncation would move the regret in the self-serving direction by ~0.24 objective units. Asymmetry recorded, not closed. |
| **`s`/`S` pins (5)** | **PARKED**, not landed. One regeneration diff should not carry two causes. **No ratchet** — policy parameters have no monotone better-direction. |

---

## Environment notes and traps

- **NEW: a level floor alone is a tolerated-exception disjunct.** Suppressing `structlog` below
  ERROR keeps stdout clean only while nothing logs at ERROR. Route the **logger factory to
  stderr** as well; `| tee` reads stdout only, so nothing is lost.
- **NEW: `ruff`'s `SIM300` reads an upper-case attribute as a constant.** `assert arm.S == spec.x`
  is flagged as a Yoda condition. Compare as a tuple; do not add a `noqa`.
- **NEW: attribute pre-existing lint debt by MATERIALISING THE BLOB.** `python` writes
  `git cat-file blob HEAD:<f>` to disk as bytes and the checker runs over it. PowerShell's `>`
  writes UTF-16 and `Set-Content -Encoding utf8` adds a BOM, so neither can do this.
- **NEW: probe a pin anchor before committing it.** `doc_truth.documented_value` requires **exactly
  one** matching line, and a backtick one token out of place matches **zero** — which is a
  non-maskable skip for a `required: true` pin, so C56 goes SKIP while `pin_extractor_truth`
  reports green.
- **`git ls-files --eol`'s `i/` column does not describe the worktree.** Count the worktree bytes.
- **A `ruff format --check` diff whose two sides look identical is a LINE-ENDING diff.** Seventh
  session running. Normalise to each file's **dominant** ending with Python at `newline=''`.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental`.
- **`git log -1 -- <file>` is last-touch, not authorship.** Use `git cat-file -e origin/main:<f>`
  then `git diff origin/main -- <f>`.
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** Verify bytes, never the
  console.
- **There are no heredocs.** `python - <<'PY'` is a parse error; write a temp `.py`.
- **`git push` writes progress to stderr**, so PowerShell reports `NativeCommandError` and a
  non-zero `$LASTEXITCODE` on a **successful** push. Read the `old..new ref` line.
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated.** Assign, then `foreach`.
- **`git status` over-reports.** Trust `git diff`, stage precisely, `git check-ignore -v` first.
- **Identify a CI run by `head_sha`, NEVER by timestamp**, and check the run for the sha
  `git rev-parse` gives you.
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks pre-existing errors
  under `uplift/`.
- Python 3.14.0, mypy 1.19.1 locally, pytest 8.4.2, hypothesis 6.151.11. `gh` 2.82.0.
  **Repository is PUBLIC — Actions minutes are unmetered on standard runners.**

---

## I-0 — the rule most likely to burn the machine

**Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
`mutmut`); any `MIN_SCENARIOS`-scale or training workload.

**Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
`pnpm` anything — **and note that `tests/verify/test_ledger_gen_property.py` names a registry
execution, so that module is CI-only too.** `regenerate-truth-docs.yml` is the sanctioned route for
the generators, reachable by the `regenerate-truth-docs` label, and proven to work.

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, bounded scoped
`pytest`, `spec_ledger_census`, the six cheap gates, `doc_truth.documented_value` as a pure
function, and **`gh` API reads — free, and the highest-yield evidence in this repo.**

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.**

**Process sweep at close:** recorded in the progress ledger row.

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — if measured `(s, S)` regret is at or above the R5.2 margin **with its
interval excluding it**, Finding 4 is falsified. **Session 5 repaired the instrument so that this
verdict, if it comes, is about the arm R5.1 names.** It may well still be `material`, and that would
now be an admissible falsification rather than an artefact of the wrong comparator.

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and the experiment must NOT be run.

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor stays
at `0.0`, no headline is published as a gain, and the result is written up as a finding — not
reframed, not re-run at a different replicate count until it moves. **A number that cannot fail is
not a number, and a verdict that cannot be anything else is not a verdict** — session 4 found the
second of those in the instrument that decides this spec's central question, and session 5 removed
it.
