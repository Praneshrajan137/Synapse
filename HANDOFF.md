# HANDOFF — decision-quality-proof

**State at end of session 6 (2026-09-10). Two commits pushed; the commit carrying this file is
the third.** Derive the counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At the time of writing that reported **140 leaf tasks: 63 done, 2 authored-pending-discharge, 75
open** — 69 authorable and **6** CI-gated, **unchanged from sessions 4 and 5**. **No leaf was
ticked, and that is correct**: the census offers zero authorable work behind checkpoints A and B,
and this session's work was repair.

> **ALL NINE `uplift-verify` FAILURES ARE REPAIRED, AND THE NINE WERE ELEVEN.** Two of the nine
> test functions were `ExceptionGroup`s carrying **two distinct failures each** — a count the
> summary line cannot show and that only the job log reveals.
>
> **One of them was a real gate defect, and its shape is the one R6.14 exists to catch.** On a
> Make recipe line prefixed with `-`, `command_path_truth` reported the discarded exit status and
> extracted **zero commands**: Make's ignore-errors prefix concealed the unresolvable command it
> was ignoring. That is the exact pair of defects the audit found at
> `Makefile::deploy-gcp-verify`, where a leading `-` was one of the three swallows removed.
>
> **Obstruction 2.5's other half is landed.** `kv_cache_hit_rate` is declared unmeasurable in CI
> in `replay-floors.yaml`, with the prerequisite that **voids** the declaration, the reason it is
> blocked, and the procedure to obtain the number.
>
> **And its first push reddened C56 one step EARLIER than the step it was meant to unblock.** The
> fourth outcome reached registry row **C71** before it reached `verify_claims.GATE_STATUS`, the
> table nineteen rows use to translate a verdict; `_run_check` coerted the `KeyError` to FAIL, the
> counts moved, the README headline drifted. **Found by CI, diagnosed from two job logs, repaired
> in the same session, and now asserted mechanically.** See finding 48 — it is the sharpest lesson
> of the session and it was self-inflicted.
>
> **Checkpoint A was deliberately not run.** Recorded in task 11 as a decision. Nothing was taken
> from it: no margin, no amendment, no pin graduated, no label added.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree
as it *is*, not as a diff against how it was.

---

## WHAT WAS MEASURED, AND WHERE THE CHAIN STANDS

**Run `34434951478`, sha `58fc4e1`** (the state session 6 opened on):

| Job | Steps | Result |
|---|---|---|
| `quality-gates` | 26 | 1–17 **success**, **18 failure**, 19–23 **skipped** |
| `uplift-verify` | 9 | 4 install **success**, 5 fast **failure**, 6 slow **skipped** |
| `sprint6-verify`, `training-smoke` | 0 | **skipped** — they keep their own `needs: quality-gates` |

**Step 5's log is where the session's value came from.** It carries every falsifying example, so
eleven defects were diagnosed mechanically rather than guessed. `gh` reads are free under I-0 and
they are still the highest-yield evidence in this repository.

### The eleven defects, and where each was repaired

| Test | Mechanism | Repaired at |
|---|---|---|
| `test_every_named_command…` (1 of 2) | two `external` extras both claimed root `pytest` | generator |
| `test_an_out_of_scope_step…` | same collision | generator |
| `test_a_discarded_exit_status…` | same collision | generator |
| `test_a_console_script…` | same collision | generator |
| `test_every_named_command…` (2 of 2) | `construct='leading-dash'` → `observed_commands == {}` | **the gate** |
| `test_a_make_recipe_line…` | the `unresolvable-command` finding was missing on that shape | **the gate** |
| `test_aggregation_integrity…` (1 of 2) | `kpi_mean` last-bit mismatch | the test's reference |
| `test_aggregation_integrity…` (2 of 2) | `kpi_std` last-bit mismatch | the test's reference |
| `test_the_generated_ledger_round_trips…` | PASS rows tallied against the whole execution | the test |
| `test_an_edit_inside_the_generated_region…` | the mutation deleted the END MARKER | the test's mutation |
| `test_the_committed_stryker_break_hole…` | stale precondition — the hole is closed | the test |

**Four of the eleven were the generator's own disjointness guard firing on the generator's own
defect, exactly as its docstring promises.** `_extra_module` ignored its `index` for the
`external` shape. Roots are indexed now, so naming two external modules stays a *reachable* case
rather than being filtered out, and `max_extras` is guarded against outgrowing the set.

### Findings 43–47

- **43 — the gate defect.** `_MODULE_RE`'s negative lookbehind `(?<![\w./-])` refuses to match
  `python` behind a `-`, and the Makefile branch of `collect_named_commands` handed
  `named_commands_in` the **raw** recipe line while `_makefile_discarding_construct` was already
  prefix-aware. Repaired with one reading of Make's prefix grammar (`split_make_prefix`) shared by
  both consumers, which also makes `-@`, `+-` and `@+-` read as swallows. `_MODULE_RE` is
  untouched, so no other surface gains a match. **`@` never had the defect** — it is not in the
  lookbehind's class — so the committed Makefile's nine `@python -m scripts.audit.*` recipes were
  always read correctly. Checked rather than asserted, because the opposite would have been a much
  larger finding. Committed report **unchanged at 37 commands / 0 findings / pass**, predicted
  before the edit and measured after.
- **44 — the property that should have caught 43 was vacuous on exactly that input.** The Makefile
  test asserted the findings **set** and never the command set, so a `-`-prefixed line
  contributing nothing passed whenever every named command happened to resolve. Both are asserted
  now, plus `report.commands` non-empty.
- **45 — session 1's own repair created the `stryker-break` red, and the coordinated change was
  half-applied.** `verify_claims.py`'s C16 docstring names the four sites its repair must touch —
  including that property module — and still describes the hole as live ("**Expected FAIL on
  landing**"), while `doc-number-pins.yaml`'s comment already called the remediation "COMPLETE and
  verified mechanically". Two sites moved, two did not. **That prose is recorded, not edited:** it
  is another spec's, `doc_truth` reads it, and I-0 forbids running `doc_truth` locally to see what
  the edit would move.
- **46 — a recorded hypothesis refuted by reading rather than by running.** The ledger-gen
  `'unavailable' == 'fail'` has nothing to do with the inverted `ledger_gen`/`readme_gen` order.
  `mutations[1]` was `clean.replace(f"\n{GENERATED_END}", "", 1)`, which deletes the **end
  marker** — so `probe_text` correctly answered `unavailable` and the test demanded `fail`.
- **47 — the ninth failure is `main`'s, and repairing our eight was necessary but not
  sufficient.** One red anywhere in the fast step keeps step 6 skipped, so the slow surface could
  never have run while it stood. Adopted by explicit operator decision; ownership re-proved
  mechanically. `aggregate_arm` sorts by `(seed, arm)` for R2.5 and the test's reference reduced
  in **arrival** order; the falsifying case is three runs at **seed 0** whose **arms** reorder
  them. Exact `==` retained, no tolerance introduced, no production file touched — and
  order-invariance is now asserted directly, because a mirrored sort would otherwise **mask** a
  subject that stopped canonicalising. Scoped to key-distinct inputs, since `sorted` is stable and
  `uplift/harness.py`'s "removes that dependence entirely" overclaims for a tied key. Recorded,
  not edited.

### Conflict O — CF-13 is enforced over a scope that excludes every one of its violations

The authority documents say "**three** pre-existing violations". Measured by **AST** over all
**354** `test_*.py` in the tree: **41 files, 56 hardcoded `@settings(max_examples=…)` sites** — 37
files under `tests/uplift/`, 4 under `tests/verify/`. The worst is
`tests/uplift/test_reproduction_stability_property.py`, pinned at **4** examples against CI's 500
and the ≥100 obligation.

`tests/verify/test_property_inventory_consistency.py` **does** carry a mechanical CF-13 check, but
it walks `DECLARED_INVENTORY`'s 37 declared paths and **the intersection with the 41 offenders is
empty**. Surfaced, not repaired: these are `decision-integrity-uplift-proof`'s files, and adopting
a second owner's debt in the same session as finding 47's adoption is the broad change defect 22
rejects. Widening the check's scope is the durable repair and is the operator's.

**And the method note is the same defect one level up.** The first draft of that count was a regex
over raw text and reported 62 sites in 43 files — having matched the assignments that
`tests/verify/test_inventory_budget_rule_property.py` **quotes as test data**, the file written to
warn about precisely that. The count above is from the parse tree.

---

## OBSTRUCTION 2.5(b), AS LANDED

**The floor was not lowered (R2.10) and the step did not gain `continue-on-error` (finding 35).**
`read_floor` still returns `0.70`/`0.80`, so `ratchets.json`'s two `floors.*.value` extractors and
`doc-number-pins.yaml`'s pins are untouched and `pin_extractor_truth` still reports **14/14/14**.

**The declaration lives in the configuration, not behind a flag.** A CLI flag would let any caller
silence any floor from any workflow line with no record of who did it or why.
`replay-floors.yaml` carries `unmeasurable_in_ci:` on `kv_cache_hit_rate` with `declared: true`
plus a **prerequisite**, a **blocked_on** and a **procedure** — the shape
`dataset-licences.yaml` uses for the M5 terms behind an acceptance gate an agent must not accept
(C74). No JSON Schema governs `replay-floors.yaml`, so coupling 3 does not fire and
well-formedness is enforced by the gate that reads it.

**The verdict gained a fourth state and the declaration its own.** `Outcome.DECLARED_UNMEASURABLE`
is exit 0, printed `[SKIP]`, and a distinct value in the JSON — a SKIP is not a PASS in the record
as well as in the exit code. `Declaration` is a *separate* enum (`absent`/`malformed`/`honoured`/
`void`) because the floor and its declaration are different subjects.

| State | When | Verdict |
|---|---|---|
| `honoured` | declared, no measurement obtainable | metric `declared-unmeasurable`, gate may exit **0** |
| `void` | declared, and a measurement **was** taken | gate **FAILS** until the block is deleted, whichever side of the floor |
| `malformed` | a block that cannot state prerequisite, reason and procedure | declares nothing: metric `unavailable`, gate exits **2** |
| `absent` | no block | unchanged behaviour |

**Step 18's verdict predicted, and predicted honestly.** `evaluate()`'s existing `measurers` seam
was given the two measurements CI itself reported — tier routing `1.0000` over 200/200, kv gauge
with no samples — while **trace resolution ran for real** against the committed 200-trace corpus
and the generator's own `0xCAFEBABE`. Result: `[SKIP] kv_cache_hit_rate`,
`[OK] tier_routing_accuracy 1.0000 >= 0.8000`, aggregate `declared-unmeasurable`, **exit 0**. No
replay was performed (I-0). **This predicts; it does not prove.**

### Finding 48 — the fourth outcome reddened C56 one gate *earlier*, and the trap was documented two lines above the table

**Self-inflicted, found by CI on the first push, repaired in the same session.** Run
`34448902996`, sha `b8eba2f`: step 17 **C56 failure**, step 18 **skipped behind it**. The
obstruction had moved *backwards* from 18 to 17, which had been `success` since session 4.

`doc_truth` named the drift — `headline-counts … FAIL (README claims 2, suite reports 3); SKIP
(README claims 11, suite reports 10)` — and every pin, **including both `replay-floors.yaml` pins**,
reported `[OK]`, so no pinned value had moved. The `SYNAPSE Truth Gates` run for the same sha named
the check: **`C71 … check raised KeyError: 'declared-unmeasurable'`**.

**`replay_metrics` is registered as C71**, and `verify_claims.GATE_STATUS` is the table **nineteen**
registry rows use to translate a gate's verdict string into `PASS`/`FAIL`/`SKIP`. A new `Outcome`
member is a schema change and that table is one of the fixtures carrying it (**coupling 3**). The
wave-2 sweep grepped for consumers of the artifact and of `Outcome` *inside* the gate and its
property test, and never for a *verdict translation*. `_run_check` coerced the `KeyError` to FAIL,
the counts moved, the headline drifted, C56 went red. **The comment block immediately above
`GATE_STATUS` already describes this exact failure mode.** It was read after the fact.

**Repaired at the declaration, never at the call site:** `"declared-unmeasurable": "SKIP"` joins the
table, for the same reason `unavailable` maps there. **Stricter than the gate's own exit code,
deliberately** — the step exits 0 to gate on the floors it can measure; the registry row says the
other one went unmeasured, so the published PASS count never absorbs a declared absence.

**And the obligation is now mechanical.**
`test_every_outcome_this_gate_can_report_is_translatable_by_the_registry` asserts every `Outcome`
member is a `GATE_STATUS` key **and** that only a genuine pass maps to `PASS`. It imports
`verify_claims` for a dict and never executes the registry.

**Predicted before the second push:** C71 `FAIL → SKIP`, nested suite `FAIL 3 → 2` /
`SKIP 10 → 11` matching the committed headline, C56 → PASS, step 17 → success, **step 18 executing
for the first time**. The arithmetic cannot be confirmed locally — `doc_truth` and `verify_claims`
are on the never-run list. **C44 and C69 stay FAIL and are not this spec's**: `data_fabric/ingest`
module liveness, and `core-purpose-uplift`'s placeholder checkpoint registry.

---

## THE CHAIN, MEASURED RATHER THAN PREDICTED

| # | Obstruction | State |
|---|---|---|
| 0 | the runner itself — billing | **CLEARED** — repository made public |
| 1 | step 8 mypy strict (orchestrator) | **CLEARED** (2r), re-confirmed `success` |
| 2 | step 17 **C56** narrative-truth | **CLEARED** (26.2 / 26.3), then **REGRESSED by this session's own C71 defect** at `b8eba2f`, then repaired (finding 48). **UNJUDGED** |
| **2.5** | **step 18 golden-trace replay** | **REPAIRED ON DISK, STILL UNJUDGED.** Disposition (a) landed session 5; **(b) landed session 6**. Its first run was **skipped behind the C56 regression above**, so the repair has never been reached |
| 3 | step 19 unit tests → `test_cognition_phase` | **still unknown** — has never executed on this branch or on `main` |
| 4 | steps 20–22 coverage / spec coverage / contract | **still unknown** — same |
| **5** | **`uplift-verify` step 5, the fast surface** | **REPAIRED ON DISK, UNJUDGED.** All nine reds repaired; eight verified locally, two authored-only |
| **6** | **`uplift-verify` step 6, the slow surface** | **still skipped behind step 5.** Six slow properties, the 623-test floor, the fault-injection probe and `digital_twin`'s 1000-scenario run have still never executed |

**Session 2r's lesson has fired five times now, and the fifth was this session's own doing:
clearing a gate reveals what it was shielding — and a repair aimed at one gate can redden an
earlier one.** Nine reds were repaired; a tenth may sit behind them. **No single clearance licenses
a claim about the job at the end.**

---

## What is still owed, and who owns it

- **Read the next `uplift-verify` and `quality-gates` runs.** Both commits' discharge is CI's to
  report. Until step 6 **reaches its end**, task 27.5 stays `[ ]` and every handoff must keep
  saying the slow half of Properties 38–60 has never executed.
- **Checkpoint A, on the three-arm comparator.** Run 1 by label, then the D2.5 amendment stating
  the derived literal, then the margin commit, then run 2. **The verdict may still be `material`**
  — which would now be an **admissible** falsification about the right subject.
- **A second regeneration**, owed by the generator order itself (`readme_gen` → README → C56 →
  `ledger_gen`; the committed order inverts it). The two parked `s`/`S` pins graduate in the same
  data edit, after it.
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35). Registered-check
  change.
- **CI's ruff scope** excludes nine trees including `uplift/` and `digital_twin/`: **530 lint, 254
  format (upper bound).** Widening it re-closes `quality-gates` at step 5.
- **CF-13's enforcement scope** (conflict O): 41 files, 56 sites, none of them inside the
  inventory the check reads.
- **`verify_claims.py`'s C16 docstring** still describes the closed `stryker-break` hole as live
  (finding 45). Prose, another spec's, `doc_truth` reads it — take it with the regeneration.
- **`scipy` is pinned in NO requirements file** and arrives transitively (finding 41).

---

## Honesty ledger — verified vs merely authored

### Executed and measured, session 6

| What | Result |
|---|---|
| STEP 0 at the real HEAD (`58fc4e1`, 44 ahead) | `quality-gates` 1–17 success, **18 failure**, 19–23 skipped; `uplift-verify` `steps=9`, step 5 failure, step 6 skipped |
| The step-5 log, read for falsifying examples | **eleven** defects across nine test functions; two `ExceptionGroup`s of two |
| Barriers 11 and 14 | both named; batch **depends on both**; offer truncates to **zero** |
| Ownership of the ninth | `git cat-file -e origin/main:<f>` exit 0, `git diff origin/main` **empty** → byte-identical |
| `command_path_truth` over the committed tree | **37 commands / 0 findings / pass**, before **and** after the gate repair — predicted, then measured |
| `ratchet_truth` over the committed file | `stryker-break` **PASS**, no findings; aggregate **SKIP**/exit 2 over **22** rows — 16 `unmeasured` + **6** `measured` with `measured_at: null` |
| Step 18's verdict, through the `measurers` seam | `[SKIP]` + `[OK] 1.0000 >= 0.8000`, aggregate `declared-unmeasurable`, **exit 0**. No replay performed |
| **The first push's CI verdict** | step 17 **C56 failure**, step 18 **skipped** — the repair reddened an earlier gate |
| **The cause, from two job logs** | `headline-counts` drift `FAIL 2→3 / SKIP 11→10`, every pin `[OK]`, then `C71 … KeyError: 'declared-unmeasurable'` |
| `GATE_STATUS` after the repair | every `Outcome` member translatable; `pass→PASS`, `fail→FAIL`, `unavailable→SKIP`, `declared-unmeasurable→SKIP` |
| CF-13, by AST over 354 files | **41 files / 56 sites**; intersection with `DECLARED_INVENTORY` **empty** |
| Bounded `pytest`, six invocations, serial, `dev` | **35 tests green**: 8 command-path, 11 ratchet, 2 aggregation, 14 replay-metrics |
| `mypy --strict --no-incremental` | clean on `scripts.audit.command_path_truth` and `scripts.audit.replay_metrics` |
| Lint/format ownership | materialised the committed blobs and re-ran the checker: **9 findings before, 9 after** on wave 1's five files; **3 before, 3 after** on wave 2's two. **Zero added** |
| Coupling 4 | `gate_surface --check` **0** — a comment-only workflow edit whose step NAME did not change moved nothing. Checked, not assumed |
| Six cheap gates | **0 / 0 / 0 / 2 / 1 / 0** |
| `spec_ledger_census --files --check` | exit **0**, **unchanged** at `140/63/2/75` |
| `pin_extractor_truth` | **14 declared / 14 probed / 14 both-sides** — not 15, not 16 |
| Line endings / bytes | trap fired on **six** files, each normalised by dominant **worktree** byte count; no BOM, no U+FFFD |

**Budget, honestly counted.** **Five** bounded `pytest` invocations against a plan of five and a
protocol figure of three: three verification, one re-verify after a *derived* expectation proved
wrong, one for the new property. Each scoped to at most three named files, serial, `-m "not
slow"`, at `dev`. **`mypy --strict` over the four changed TEST modules exceeded the 120s ceiling
twice and was abandoned** rather than retried a third time; an orphaned `python` was swept after
each and the count confirmed 0. `ledger_gen`, `readme_gen`, `verify_claims` and `doc_truth` were
not run in any form, and `tests/verify/test_ledger_gen_property.py` was not executed.

### NOT executed. Must not be claimed as passing.

- **That the fast step is green.** Nine reds were repaired; the run that judges them has not
  happened, and a tenth may sit behind them.
- **That C56 goes green on the second push.** Predicted from two job logs: C71 `FAIL → SKIP`, so
  `FAIL 3 → 2` and `SKIP 10 → 11`, matching the committed README headline. **The arithmetic cannot
  be checked locally** — `doc_truth` and `verify_claims` are on the never-run list.
- **That step 18 exits 0.** It has still never executed: its first opportunity was skipped behind
  the C56 regression. The prediction stands and is unproved.
- **The two `test_ledger_gen_property.py` repairs.** Authored, diagnostics-clean, **not
  executed** — that module names a registry execution and I-0 forbids it in any form.
- **`quality-gates` steps 19–23.** Have never executed on this branch **or on `main`**.
- **The slow step, and therefore the slow half of Properties 38–60**, the six slow properties, the
  623-test floor, the fault-injection probe, `digital_twin`'s 1000-scenario run.
- **`mypy --strict` on the four changed test modules.** Attempted twice, exceeded the local
  ceiling, abandoned. No CI step type-checks `tests/`.
- **Task 11's verdict.** No margin committed, no run made against the three-arm comparator.
- **`vitest`. At all.**

### The lesson from this session

**A repair aimed at one gate can redden an earlier one, and the only thing that told me was a job
log.** Disposition (b) was authored, verified locally against every clause a property could carry,
predicted through the gate's own seam, and it still broke `quality-gates` at step 17 — because a new
enum member reached a registry row before it reached the table that translates verdicts, and the
comment two lines above that table already described the failure mode. **Enumerating a schema
change's consumers by grepping the module and its test is not enumerating them.** Ask what
*translates* the value, not only what reads it.

**A gate that has never executed is not evidence, and the log of the run that finally executes it
is worth more than any amount of reasoning about it.** Nine summary lines became eleven diagnosed
defects because the falsifying examples were read; the `arm`-driven reorder behind the float
mismatch and the marker deletion behind `'unavailable' == 'fail'` were both invisible from the
summary and obvious from the log. The same is true of C71: the step-17 log gave the drift, and only
the *Truth Gates* run for the same sha named the check.

**And the corollary: check the premise, then check your own instrument.** Four documents said
CF-13 had three violations; there are 56. The first tool written to count them repeated, on its
first draft, the exact regex-over-raw-text defect that one of the files it mis-flagged exists to
warn about.

---

## Environment notes and traps

- **NEW: `Select-Object -First N` on a native command makes `$LASTEXITCODE` non-zero.** The census
  printed `status: pass (exit 0)` in its own output while the shell reported 1. Re-run with
  `*> $null` before believing a gate's exit code — a non-zero exit is a claim about the gate, and
  the pipeline can manufacture one.
- **NEW: `mypy --strict` over `tests/verify` + `tests/uplift` modules exceeds a 120s command
  budget.** The closure drags `uplift/__init__` → `scipy`, numpy and hypothesis. Type-check the
  changed **non-test** modules by module name (`-m scripts.audit.<mod>`), which is ~13s, and say
  plainly that the test modules were not checked.
- **NEW: mixing `scripts/audit/*.py` and `tests/**` in one mypy invocation fails instantly** with
  "Source file found twice under different module names". Use `-m <dotted>`.
- **A `ruff format --check` diff whose two sides look identical is a LINE-ENDING diff.** Eighth
  session running. Normalise to each file's **dominant** ending with Python at `newline=''`, and
  count the **worktree** bytes — `git ls-files --eol`'s `i/` column is normalised.
- **`ruff format --check` was already non-clean on all five of wave 1's files at HEAD**, and
  `ruff check` reported 9 findings there. `tests/` and `scripts/` are outside CI's ruff scope.
  **Attribute by materialising the committed blob** with Python `write_bytes` and re-running the
  checker; PowerShell's `>` writes UTF-16 and `Set-Content -Encoding utf8` adds a BOM.
- **`git log -1 -- <file>` is last-touch, not authorship.** Use `git cat-file -e origin/main:<f>`
  then `git diff origin/main -- <f>`.
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated.** Assign, then `foreach`.
- **There are no heredocs.** Write a temp `.py` under `.tmp/` (git-ignored), run it, delete it.
- **`git push` writes progress to stderr**, so PowerShell reports `NativeCommandError` and a
  non-zero `$LASTEXITCODE` on a **successful** push. Read the `old..new ref` line.
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
`pnpm` anything — **and `tests/verify/test_ledger_gen_property.py`, which names a registry
execution.** `regenerate-truth-docs.yml` is the sanctioned route for the generators.

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, bounded scoped
`pytest`, `spec_ledger_census`, the six cheap gates, `command_path_truth` and `ratchet_truth` over
the committed tree (both are pure static readers), `replay_metrics` through its `measurers` seam,
`doc_truth.documented_value` as a pure function, and **`gh` API reads — free, and the
highest-yield evidence in this repo.**

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.**

**Process sweep at close:** recorded in the progress ledger row.

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — if measured `(s, S)` regret is at or above the R5.2 margin **with its
interval excluding it**, Finding 4 is falsified. Session 5 repaired the instrument so that this
verdict, if it comes, is about the arm R5.1 names. Session 6 deliberately did not run it, and
recorded why.

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and the experiment must NOT be run.

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor stays
at `0.0`, no headline is published as a gain, and the result is written up as a finding — not
reframed, not re-run at a different replicate count until it moves. **A number that cannot fail is
not a number, and a verdict that cannot be anything else is not a verdict.**
