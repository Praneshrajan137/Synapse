# SESSION PROTOCOL — decision-quality-proof

**Binding working agreement. Read this before starting work in any session.**

This document exists because the `decision-quality-proof` spec is too large for one session's
context window. Work is therefore batched, and **the batch boundary is a hard stop**.

---

## The rule

> **At most TEN leaf tasks per session. Stop earlier at a dependency boundary. Then regenerate
> the handoff and tell the user to start a new session.**

Ten is a **cap, not a quota**. The cap exists because context degrades before it exhausts: an
agent at 85% context makes worse decisions than one at 40%, and the failure mode is silent — it
stops reading files it should read and starts inferring from surrounding code. Ten is the point at
which quality was observed to still be intact.

A session that reaches a dependency boundary at task four stops at four. Session 7 below is
deliberately four tasks long, because the fifth thing that has to happen is a CI run, not an edit.
Padding it to ten would mean authoring E5 before the E4 checkpoint that gates E5 has looked.

### What "one task" means

One **leaf** entry in `tasks.md`: a numbered sub-task like `12.3`, or a checkpoint parent like
`11` that has no sub-tasks. Leaf status is derived from the id tree — `12` is a parent because
`12.1` exists — not from indentation. A parent with sub-tasks is ticked when its last child is.

### The three marks, because the honesty contract has three states (I-7)

| Mark | Meaning |
|---|---|
| `[ ]` | open — not started |
| `[~]` | **authored, discharge pending.** The work is on disk; the proof is owed by the job named in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

"Authored and diagnostics-clean, not executed" is a legitimate result. Recording it as `[x]` is
the I-7 violation. Every `[~]` carries a `discharge:` sub-bullet naming the job that owes the
proof, and an **open** leaf carrying a `discharge:` line is CI-gated: it is not authorable work
and the census will not offer it.

`[~]` is safe against the one registered gate that already reads `tasks.md`.
`scripts/audit/task_claim_truth.py` defines `_CHECKED_MARKS = {"x", "X"}`, so a `[~]` record is
*unchecked* there and lands in its `pending` bucket, which that gate explicitly does not treat as
a finding.

### What to do at the boundary

1. Stop authoring. Do not start the next task, even partially.
2. Run the verification sweep (below) and record real numbers.
3. Regenerate `HANDOFF.md` — overwrite it, do not append. It must describe the tree as it is
   **now**, not as a diff against how it was.
4. Append a row to `## Progress ledger`. **Never edit a past row.**
5. Tell the user, explicitly: **"Session complete. Start a new session and paste
   `NEXT_SESSION_PROMPT.md`."**

### The one permitted overrun

If the last task leaves the tree in a state that **cannot be verified** — a half-edited module, a
schema change whose consumers have not moved, a rename applied on one side of a coupling — finish
the coupling and stop at eleven or twelve. A same-commit coupling left half-applied is a red gate
for the next session and costs more than the extra task saved. **Record the overrun and its reason
in the progress ledger.** Never overrun for convenience or momentum.

---

## Counts: derive them, never read them

There is no count in this document, and there should never be one again. Three documents used to
carry the same three numbers by hand.

```powershell
python -m scripts.audit.spec_ledger_census --next 10
```

That command **is** the census. It reports the leaf total, the three mark buckets, the CI-gated
set derived from `discharge:` lines, and the next authorable batch in ledger order. Add `--files`
at session start: it reports open tasks whose named artifacts already exist, which is exactly the
session-1 failure mode. `--json` for a payload, `--check` for an exit code (`0` pass, `2`
unavailable — an unclassifiable mark or a duplicated id is non-passing, never a guess).

Two things it deliberately does **not** do. It asserts no total, so no document has to be edited
when the total moves. And its `--files` observations are **informational**: `tasks.md` legitimately
names paths in order to reject them (tasks 7.1, 7.3 and 8.2 each explain a rejected path), and a
task that modifies an existing module will always show prior art. Turning those into failures
would manufacture findings.

It is **not** a registered check. It is local session hygiene; registration precedes generation
(task 24's rule), so if it should become one it takes an identifier at task 24.1 with its
`blocking-steps.yaml` and `required-checks.yaml` entries in the same commit.

---

## Two checkpoints are operator actions, and they come before the work they gate

**This is the correction that reordered the whole plan.** `tasks.md`'s own overview says E2b is
sequenced before E2c "specifically to try to kill this spec's central claim before the project
spends its largest single block of work on a premise it declined to test." Task 14 says that if
any single-objective policy is Pareto-optimal, "the consensus experiment is reported as having no
room to win and **must NOT be run**. Do not proceed to E3."

The previous batch plan pooled tasks 11 and 14 into the final session. That preserved the
authoring dependency order and destroyed the decision order: task 11 could only falsify Finding 4
after roughly seventy tasks already rested on it, and task 14 could only cancel E3 after E3 was
fully authored. **A gate that fires after the work it guards is not a gate.**

Checkpoints are **operator actions, not authoring sessions**: push the branch, dispatch a
workflow, read the output, record the verdict. Zero local compute, so I-0 is unaffected.
`uplift.yml` carries only `schedule` and `workflow_dispatch`, so dispatch is the mechanism.

### Checkpoint A — before task 12 is authored

Discharges tasks **6**, **10.4**, **11**.

**Steps 1-2 are already done: the branch is pushed and PR #84 is open, and CI has run.** What
remains is reading the sweep, dispatching the measurement, and recording the verdict.

0. **First, make the dispatch affordable.** `uplift.yml` declares `workflow_dispatch: {}` with no
   inputs and holds two jobs — `uplift-proof` (`timeout-minutes: 350`) and `twin-regret`. A bare
   dispatch runs **both**, spending ~350 minutes of runner time on a job checkpoint A does not need
   and which cannot produce an admissible artifact yet. Add a `workflow_dispatch.inputs.job`
   selector with an `if:` guard per job first.
1. Read `truth-gates.yml::falsification-sweep`'s survivor list on PR #84. **Bring it to the user
   before fixing anything** — a gate proven not to enforce means every number it reported is
   unsupported. Never weaken a mutation to clear a survivor. That discharges task 6.
2. Dispatch `twin-regret`:
   `gh workflow run uplift.yml --ref feat/decision-quality-proof`. Read the reported regret, its
   interval, and `comparator_headroom`.
3. Instantiate the margin per task 10.4 — **the rule is already committed and enforced; take only
   the value from it** (`service_points * 0.01 * weights.unmet_service`), record the measured
   headroom it was checked against, and pin the derived value. The run reports `margin_rule`,
   `margin_rule_derives` and `comparator_headroom` for exactly this. That discharges 10.4.
4. Read task 11's verdict against the table below and record it in `tasks.md` with evidence.

**Task 11's verdict is four-valued, and the fourth value is the state the tree is in today.**

| Verdict | What it means | What it licenses |
|---|---|---|
| `material` | regret at or above the margin, interval excluding it | **STOP.** Finding 4 is falsified. R5 is re-cut (R5.3, R5.4). Report it plainly; it is a good outcome. |
| `sub-margin` | regret below the margin, every objective KPI recorded sensitive | Confirms Finding 4. **Unreachable today** by construction — the two sensitivity flips are earned by tasks 12.3 and 13.3. |
| `inconclusive` | regret below the margin, some objective KPI not observably sensitive | **PROCEED to task 12.** Task 11's own words: "the repair is to the instrument, not to the twin's physics" — and E2c *is* that repair. |
| `unavailable` | **no margin committed, so nothing was compared** | **Not a verdict.** This is the current state, and it is why checkpoint A exists. `unavailable` is not `inconclusive`: one is a measurement that could not decide, the other is the absence of a measurement. I-7 forbids reading absence as either a pass or a null. |

The predecessor protocol resolved three of these four and the tree was sitting in the fourth.

### Checkpoint B — after task 13.7, before E3 is authored

Discharges task **14**.

1. Dispatch `uplift.yml` with task 13.7's E2c measurement steps.
2. Evaluate the Pareto frontier of the four single-objective policies **together with ADR-055's
   declared reference set** (13.5's clause: the frontier of a finite non-empty set is non-empty,
   so evaluating only the four makes R5.28 unsatisfiable by construction).
3. If **any** single-objective policy is Pareto-optimal under interval-aware dominance,
   **consensus is provably unnecessary and E3 must not be run.** Report and re-scope.
4. Otherwise proceed to session 3.

This is why session 2 overruns to eleven tasks: 13.7 is what makes checkpoint B reachable, and
stopping at 13.6 would leave E2c's physics changed with no measurement wired to judge it.

### Checkpoints C and D — not early-exit gates, but still CI-gated

**C** discharges task **21** (is the confidence contract live?) and sits between session 7 and
session 8, because task 21 says to repair before E5 and session 8 begins E5. **D** discharges
tasks **22.3** and **25** after session 9. Neither can end the spec; both are recorded here so
the census's seven CI-gated leaves are all accounted for.

---

## The materiality margin — the rule is landed, the value is owed

`requirements.md:857` (R5.2) says the margin "SHALL be committed as a pinned threshold **only
after it has been measured**". Every other threshold in this plan is pinned **before** the run
judged against it. Taken naively, the two rules license choosing the margin with the number
already in hand — which decides task 11's verdict by the choice of margin, the exact pattern task
25's pre-commitment forbids.

**Resolution, landed in session 1r rather than left as an instruction.** The *derivation rule* is
committed; only the *value* is instantiated at checkpoint A.

```
materiality_margin = service_points * 0.01 * weights.unmet_service
```

At the committed weight of `8.0`, one service point costs `0.08` objective units, so
`service_points: 5.0` derives a margin of `0.40`. Expressing it in service points puts the one
irreducible decision-relevance choice into units a supply-chain reader can evaluate, and that
choice is flagged `chosen` exactly as the `delivery_latency` weight is.

Three things make it more than prose:

1. **`policy.py::materiality_margin` re-derives a committed value from the rule and refuses one
   that disagrees.** Without that the pre-registration is decoration and the margin could still
   be chosen to suit the number it judges.
2. **It also refuses a margin at or above the measured comparator headroom** (`11.79 - 2.93 =
   8.86`), which would be unfalsifiable by construction: no policy could exceed it, so `material`
   would be unreachable and task 11 could only ever proceed.
3. **The ratchet direction is `down`.** Unlike an objective weight, this threshold has an obvious
   self-serving sign: raising it makes Finding 4 harder to falsify. It may only ever tighten.

Bracketed on both sides rather than asserted: below about **3.3** service points it would call the
incumbent `(s, S)` policy's known shortfall against its own newsvendor target (`0.8556` measured
against `8/9`) "material"; above `8.86` objective units it cannot fire.

**What checkpoint A still owes:** read the reported regret, instantiate the value from the rule,
record the headroom it was checked against, and pin the derived value.

---

## The batch plan

Sessions are sized by dependency boundaries, capped at ten. Re-derive membership with
`--next N`; this table says where the boundaries are and why.

| Session | Tasks | n | Theme and boundary |
|---|---|---|---|
| **A** | 6 · 10.4 · 11 | — | **Operator.** First CI exposure, survivor list, regret measurement, margin. Task 11's verdict gates session 2. Task 6 discharged in session 2q. |
| **2q** | 6 · 26.1 · 27.1 | — | **Landed.** Task 6 ticked on the reviewed survivor list; the regeneration job and its couplings; the `confidence_threshold` declaration fix. Registered parents 26 and 27. |
| **2r** | 27.2 · 27.3 · 27.4 · 27.5 · 26.2 · 26.3 | 6 | **Adopted debt, and it goes BEFORE session 2 — see below.** Clear `mypy --strict orchestrator/`; confirm `uplift-verify` executes; **then, last, dispatch and commit the regeneration.** The order within 2r is fixed: see "The regeneration goes last". |
| **2 (next)** | 12.1–12.4 · 13.1–13.7 | 11 | E2c's five structures + Pareto. **Overruns by one deliberately:** 13.7 is what makes checkpoint B reachable. |
| **B** | 14 | — | **Operator.** Pareto evaluation. Can cancel E3 outright. |
| 3 | 15.1–15.6 · 16.1–16.4 | 10 | E3 interval + schema; controls begin |
| 4 | 16.5–16.7 · 17.1–17.7 | 10 | Controls job; Power_Report; floor ratchet; staleness |
| 5 | 17.8 · 17.9 · 18.1–18.6 · 19.1 · 19.2 | 10 | C60 operator; held-out block + recompute; benchmark begins |
| 6 | 19.3–19.8 · 20.1–20.4 | 10 | Benchmark honesty; degradation disjunction; registry; materialisation |
| 7 | 20.5–20.8 | 4 | **Stops at the E4/E5 boundary**, not at ten. |
| **C** | 21 | — | **Operator.** Is the confidence contract live? Repair before E5. |
| 8 | 22.1 · 22.2 · 23.1–23.8 | 10 | E5 powered run, declarations, external anchor |
| 9 | 23.9–23.11 · 24.1 · 24.2 | 5 | Chain export, registration, then generation last |
| **D** | 22.3 · 25 | — | **Operator.** Ratchet the floor if the measurement supports it; state the claim. |

Authorable total: `11 + 10 + 10 + 10 + 10 + 4 + 10 + 5 = 70`. CI-gated: `6, 10.4, 11, 14, 21,
22.3, 25` = 7. Together 77 open leaves — but **check that against the census, not against this
sum**, because this sum is prose and the census is not. **It is already stale by session 2q's
eight new leaves, and that is the intended failure mode:** the census moved, this sentence did
not, and the rule is to trust the command.

### Why session 2r comes before session 2, and why it is not optional

**`uplift-verify` has never executed on this branch.** `ci.yml::uplift-verify` declares
`needs: quality-gates`; `quality-gates` fails at step 8, `mypy --strict orchestrator/`; so
Properties 38–60 — this spec's entire property surface — have never run in CI. Everything sessions
1, 1r, 2p and 2q reported green is **local evidence only**.

Session 2 authors eleven more tasks, and **four of them (12.2, 12.4, 13.2, 13.4) produce
`@pytest.mark.slow` properties whose declared discharge is that same unexecuted job.** Running them
locally is forbidden: they drive the real SimPy twin, which is category 4 under I-0. So authoring
session 2 first means adding eleven marks — four of them permanently unverifiable in the meantime —
to a spec whose existing property surface is already unproven. That compounds the exact defect this
spec exists to name: a gate that reports nothing is indistinguishable from a gate that passes.

Session 2r is what opens that path. It is sequenced first for the same reason checkpoints A–D fire
before the work they gate.

**It does not block checkpoint A.** Checkpoint A's `twin-regret` dispatch is a `workflow_dispatch`
job in `uplift.yml` with no `needs:`, so it runs regardless of `quality-gates`. A and 2r are
independent **in CI triggering**, and either may start first.

### The regeneration goes last, and that is a correction

**Session 2q's closing summary said the two tracks were freely orderable, on the strength of
`needs: NONE`. That was wrong, and the correction is recorded here rather than quietly applied.**
`needs:` describes CI triggering. It says nothing about the *generated documents*, which is where the
coupling lives.

`ledger_gen` and `readme_gen` project the PASS/FAIL/SKIP counts of one Check_Registry execution.
**C56's status is inside those counts.** Task 10.4 adds a pin to `doc-number-pins.yaml`, which
changes `doc_truth`'s claim set, which can move C56. So a regeneration committed *before* the margin
lands is stale the moment it does — and the repair is a second ~45-minute dispatch, for nothing.

**Therefore, within 2r: the orchestrator work (27.2–27.5) first — it touches no generated document
and is safe beside checkpoint A — and tasks 26.2/26.3 last, after track A's margin commit.** One
dispatch instead of two.

This is also why the derived-margin pin is **parked** rather than landed (finding 20, conflict H).
Standing it up before ADR-055 D2.5 states the literal would make its anchor match nothing, which
makes the claim a `skip`; and because the pin is `required: true`, R1.4/R1.6's non-maskable rule
turns that into an `unavailable` aggregate — **C56 SKIP, not FAIL** — while `pin_extractor_truth`
reports green because it probes source extractors unconditionally. The regeneration would then look
broken for a reason that had nothing to do with it.

---

## Verification sweep — run before closing any session

Nothing here is expensive. All of it is category-5 under I-0. Serial, never concurrent.

```powershell
# 1. Lint and type-check only what the session touched.
#    Never repo-wide -- pre-existing debt is not yours.
python -m ruff check <changed files>
python -m mypy --strict <changed python files>

# 2. The fast suites for the loci the session's properties name.
$env:HYPOTHESIS_PROFILE='dev'
python -m pytest <changed test files> -q --tb=line -p no:randomly -m "not slow"

# 3. The cheap gates. SIX of them, all pure file reads, ~1s each.
python -m scripts.audit.workflow_shape_truth              # C64
python -m scripts.audit.pin_extractor_truth --check       # C75
python -m scripts.audit.sweep_budget_truth --check        # C73
python -m scripts.audit.dataset_licence_truth --check     # C74 (expect exit 2 = honest SKIP)
python -m scripts.audit.task_claim_truth --check          # ticked-but-not-landed
python -m scripts.audit.gate_surface --check              # C63 (added session 2p -- see below)

# 4. Re-derive the ledger and confirm it moved by exactly what was ticked.
python -m scripts.audit.spec_ledger_census --files --check
```

`task_claim_truth` is in this list because it mechanically catches the failure the ledger warning
describes in prose. **It is red today, and the red is not this spec's.** Executed 2026-09-01: 563
records across 7 specs, exit **1**, naming `core-purpose-uplift` tasks **9** and **9.1** — both
marked `[x]` while `infrastructure/ml/published_checkpoints.json` still holds only
`__placeholder__`. That is the precise defect the gate was written for, in a neighbouring spec, and
it predates this work. **Read the subject of the failure before treating it as yours**, and do not
repair it by weakening the gate or by editing another spec's ledger without its owner.

It will also bite **this** spec at task 20.3. Confirmed empirically at `tasks.md:1883`: 20.3 is
already a *detected pending* claim, because its title matches the `lands-registry-entry` pattern
and its body names `published_checkpoints.json`. Ticking it requires the registry to hold a real
validated non-placeholder entry, or the gate fails naming the record.

**`gate_surface --check` joined the list in session 2p, and it is the most likely of the six to
bite.** It is the gate every workflow edit trips: `scripts/audit/gate_surface.py` projects **every
job and every step of every workflow** plus the whole of `blocking-steps.yaml` into
`docs/state/GATE_SURFACE.md`, so adding a job, renaming a step or adding a blocking declaration
makes that committed document stale and flips **C63** to FAIL. It belongs here on cost as well as
on relevance: it is pure workflow parsing and file reads, ~1s, no subprocess and no registry
execution.

Session 2p added it because it had already fired unnoticed. Both `truth-gates.yml::falsification-sweep`
(task 5.6) and `uplift.yml::twin-regret` (task 10.3) landed in session 1 **without** the
regeneration, so the committed record carried `52 job(s), 357 step(s)` and `8 declared-blocking
entries` against a tree with 54, 370 and 10 — while `docs/state/CURRENT.md:94` records C63 as
**PASS**. C63 was therefore red on PR #84, hidden inside "Truth Gates (enforcement spine),
predicted red", and its FAIL also drifts `ledger_gen --check`, `doc_truth`'s pinned counts and the
README headline. **Four registered gates from one missed `--write`.**

**The asymmetry that makes this affordable, and the trap in it.** `gate_surface --write` is cheap
and is the repair. `ledger_gen --write` and `readme_gen --write` — the other two thirds of the
repair order `truth-gates.yml` fixes — each execute the entire Check_Registry in-process and are
**category 3/4 under I-0**. So a change that moves a check's *status* cannot be fully regenerated
locally; a change that only moves the *workflow tree* can, because the committed ledger's recorded
status for C63 does not move. Know which kind of change you are making before you start, and if it
is the first kind, escalate to CI rather than hand-editing a count (I-7 forbids the latter
absolutely).

Expected exit codes for the block above, as executed on 2026-09-01: `workflow_shape_truth` 0,
`pin_extractor_truth` 0, `sweep_budget_truth` 0, `dataset_licence_truth` **2** (honest SKIP —
the M5 terms sit behind a Kaggle acceptance gate an agent must not accept), `task_claim_truth`
**1** (pre-existing, `core-purpose-uplift`), `gate_surface --check` 0 (**after** session 2p's
regeneration; it was non-zero before), `spec_ledger_census` 0.

**NEVER run**, in any session (I-0): `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
repo-wide `pytest`, `--cov`, `-n auto`, `pnpm` anything, `docker compose`, or any
`MIN_SCENARIOS`-scale run. Each spawns either the whole Check_Registry as a 900s subprocess or a
category-4 workload.

**`ledger_gen` was added to that list in session 2p, and it had been missing.** Its own module
docstring is the evidence: "every row and every count is projected from **one**
`RegistryVerdict` — one in-process Check_Registry execution". It reads as a document generator and
costs what `verify_claims` costs. `gate_surface` is the one generator in that trio that is genuinely
cheap, which is exactly why it is in the sweep and these two are not.

**Sweep for processes before finishing.** List background processes; confirm none of yours
survived. After a cancelled run, check for orphaned `python`, `node` and `chrome` explicitly — a
cancelled agent does not clean up after itself.

---

## Four ledgers exist. Only one is authoritative.

| Source | Status |
|---|---|
| `tasks.md` checkboxes | **Authoritative** for task state, once reconciled against disk. |
| `scripts/audit/spec_ledger_census.py` | Authoritative for every *count*, because it derives them from the above. |
| `HANDOFF.md` honesty ledger | Authoritative for what executed versus what was merely authored. |
| `tasks.meta.json` | **Not authority.** Kiro machine state. Its `executionHistory` bulk-stamped every task in the spec within an eleven-second window, so a record there is *not* evidence that anything ran. `pbtResults` is empty. Do not cite it. |

And **disk outranks all four.** Session 1 opened with eight tasks implemented and unticked.

---

## Session 2's three known traps

1. **The two sensitivity flips were unassigned until now.** The protocol asserted that structures
   2 and 4 *earn* `spoilage_rate` and `delivery_latency` becoming `sensitive: true`, but no
   sub-task instructed the edit and `policy.py` refuses to default a missing key. The obligation
   is now written into tasks 12.3 and 13.3 explicitly.
2. **Session 2 ends with a deliberate red, and it must be closed in the same commit.**
   `tests/uplift/test_regret_totality_property.py::test_today_a_sub_margin_regret_cannot_confirm_finding_4`
   pins the current insensitivity and fails the moment a flip lands. That is by design — it forces
   whoever earns the flip to notice that what task 11 may conclude has changed. Update it with the
   flip, in the same commit, and state the new expectation. This is a **precondition correction,
   not an assertion weakening**: R2.10 forbids the latter, and the difference is that the subject
   changed, not the standard.
3. **Four of session 2's eleven tasks cannot be executed locally at all.** Tasks 12.2, 12.4, 13.2
   and 13.4 produce `@pytest.mark.slow` properties that drive the real SimPy twin. The sweep
   filters `-m "not slow"`, so they will report as deselected, which is **not** a pass. They are
   `[~]` with `discharge: ci.yml::uplift-verify` slow step until CI runs them, and `HANDOFF.md`
   must say so.

---

## Progress ledger — append one row per session, never edit a past row

| Session | Date | Tasks completed | Notes |
|---|---|---|---|
| 1 | 2026-09-01 | Front-load (3 blockers, HANDOFF.md); reconciled 5.3–5.10; tasks 7.1–7.5, 8.1–8.4, 9.1–9.12, 10.1–10.3, 10.5, 10.6 | Overran ten deliberately: the session began with a ledger reconciliation (8 tasks already on disk, unticked) that was discovery rather than authoring. Found and fixed 3 real defects: `_apply_cold_start` deleting the catalogue, a missing JSON-Schema format checker, and a stale `stryker-break` drift record. Established this protocol at the end. |
| 1r | 2026-09-01 | **Protocol revision + the margin rule. No spec task completed.** Added `scripts/audit/spec_ledger_census.py` + 16 tests. Re-cut the batch plan around checkpoints A–D. Introduced the `[~]` mark; reconciled 1.2 and 1.5 from `[x]`. Landed ADR-055 **D2.5** and task 10.4's *first half* — the enforced materiality-margin rule, pin (C75 now 14/14), `direction: down` ratchet, + 13 tests. | Reconciliation and pre-registration, not authoring — session 1's row is left as written. Found: tasks 11 and 14 fired after the work they gate; task 11's `unavailable` state was absent from the verdict table; the two sensitivity flips were unassigned; task 12.1 still declared the path Conflict A rejected; task 24.1's gate ids were stale by two (C75 is highest, C76 next free); task 7.2's declared module name never landed. Fixed the census's rejection of dotfile-rooted paths and an ASCII-only violation in its own output. Sweep executed: census 0, `workflow_shape_truth` 0, `pin_extractor_truth` 0 (14/14), `sweep_budget_truth` 0, `dataset_licence_truth` 2 (honest SKIP), `task_claim_truth` **1** on pre-existing `core-purpose-uplift` claims — recorded, not repaired. |
| 1r-close | 2026-09-01 | **Committed, pushed, PR #84 opened.** Three commits: `1f4f7d1` E4a/E2a/E2b + margin rule (42 files), `dd5cd8c` the protocol re-cut (5 files), `e0944cb` a flaky-generator fix (1 file). | Two blockers surfaced at the commit gate. **(1)** `.gitignore`'s bare `data/` matched a directory named `data` at any depth, silently ignoring `infrastructure/data/dataset-licences.yaml` and its schema — so task 7.1 was ticked while its deliverable could not reach CI, and C74's honest SKIP would have been indistinguishable from a file-missing SKIP on CI. Anchored to `/data/`, blast radius verified as exactly those two paths before staging. **(2)** Session 1 was entirely uncommitted and interleaved with 1r across eight shared files, so the planned three-commit split would have produced commit messages that misdescribed their own diffs; re-split by what must land together instead. A flaky property surfaced on the pre-push re-verify and was fixed at the precondition. **First CI run then reclassified the expected-red list: 3 predicted, 1 session-1 discharge failure (task 1.2's Biome `organizeImports` — the `[~]` mark working), 2 pre-existing on `main`, 1 unclassified.** |
| 2p | 2026-09-01 | **Pre-batch repair. No session-2 task started, and that was the point.** Ticked **15.3** only (Property 60, `tests/uplift/test_interval_estimation_property.py`, 20 tests passing at `dev` and `heavy`); landed **15.2**'s estimator half early as `uplift/interval.py` and left 15.2 `[ ]` on purpose. Repaired PR #84's two discharge failures. Added `gate_surface --check` as the sixth cheap gate and `ledger_gen` to the never-run list. Census moved 53/76 -> 54/75. | **Found seven defects, and one of them could have ended the spec.** **(9)** `classify_regret`'s `material` branch reads `regret >= margin and (interval is None or excludes_margin)`, and `_measure` supplied **no interval** — so checkpoint A could have reported Finding 4 falsified on a point estimate with no dispersion. Three sources disagreed on what `material` requires (`RegretVerdict`'s docstring and this protocol say "interval excluding it"; R5.3 does not; R5.13 does but governs task 13.7's twin). Resolved toward the stricter reading by changing the **instrument**, not the classifier — all 17 of task 10.6's pinned properties still pass. **(10)** `GATE_SURFACE.md` was stale on **two** of this spec's own jobs (5.6's `falsification-sweep`, 10.3's `twin-regret`), carrying `52 job(s)/357 step(s)/8 anchors` against `54/370/10`, so **C63 was red on PR #84 while `CURRENT.md:94` records it PASS** — four gates cascade from one missed `--write`, and it had been hidden inside "predicted red". **(11)** Three unrecorded error-level Biome findings beyond the one the log named, **all four from this branch's own commit `5db5eb1`**; and the finding previously attributed to PR #77 is a `warn` that exits 0 and never failed anything. **(12)** `ledger_gen` executes the whole Check_Registry in-process and was missing from the never-run list. **(13)** Design E3.1's order-invariance mechanism was wrong — sorting the resample statistics does not give it; the paired differences must be sorted before resampling. Property 60's third clause found it. **(14)** Task 15.2's "read `alpha` through `load_contract`" is unexecutable in `twin-regret`, whose install closure has no `scipy`; caught by reading the closures, not by a failed CI run. **(15)** This project's `HANDOFF.md` said three commits; the branch carries eleven. Sweep: six cheap gates at 0/0/0/2/1/0, census pass, 50 tests green, `biome check ./src` down from 43 error-level findings to 0, `tsc --noEmit` exit 0 for the first time on this branch. **`heavy` failed what `dev` passed for the second session running** — fixed at the precondition (R2.10). **Not committed, and one escalation (`ledger_gen`/`readme_gen --check`, ~15 min full-core CPU each) is stated and unrun.** |

| 2p-close | 2026-09-01 | **Committed and pushed to PR #84.** Three commits: `85774e1` the interval + the dispatch selector + the gate-surface regeneration (6 files), `d67f1c7` the Biome repair (3 files), and the ledger commit that carries this row. Branch now 14 commits ahead of `main`. | **The I-0 escalation was offered, costed and declined, and that was a judgement about evidence rather than only about heat.** Verifying that C63's repair moves no count needs `ledger_gen --check` + `readme_gen --check`, each ~900s and ~15 min of full-core CPU, ~30 min serial. `truth-gates.yml` runs all three generators on this push anyway, so the local run would have bought the same answer twice — and if the prediction is wrong, C63/C56/the README headline go red and **name** the drift. A legible failure in a run that was going to happen beats a private confirmation that costs the machine. The question was **not** skipped: reading C63's status is item 2 of `HANDOFF.md`'s owed list, and the prediction is recorded as unverified. **One incident, caught by byte-inspection rather than by a gate.** Splicing `NEXT_SESSION_PROMPT.md` with PowerShell's `Get-Content`/`Set-Content` mojibaked every em dash in its 179-line head and added a UTF-8 **BOM** — which Python's `read_text(encoding='utf-8')` does *not* strip, so the first line would silently have gained a `\ufeff`. On PS 5.1 `Get-Content -Raw` decodes with the ANSI codepage. Restored with `git checkout`, redone with a `pathlib` one-liner at explicit `encoding='utf-8', newline='\n'`, then the two small edits re-applied with the editor tool. **All nine written files then byte-verified: no BOM, no U+FFFD.** Recorded as a trap in the new handoff section, because the next agent to splice a document this way will not notice. Commit split by what must land together, not by narrative: the workflow change and `gate_surface --write` share a commit (the fourth same-commit coupling), the frontend repair stands alone, and the spec docs — which describe *both* streams — go last so no message misdescribes its own diff. That is the 1r-close lesson applied rather than re-learned. |

| 2p-ci | 2026-09-01 | **Verified PR #84's run for `77df3ef` job-by-job, and it falsified two of session 2p's own claims.** Commit `98b37d9` repairs both. **No task ticked** — the survivor list is now recorded under task 6 but the review is the operator's. | **C63 went FAIL -> PASS**, proven by diffing the two runs' registry verdicts (`C44,C56,C63,C69` at `24a1a8a` -> `C44,C56,C69` at `77df3ef`; PASS 53 -> 54), so `gate_surface --write` was the right and sufficient repair. **But the prediction that justified skipping the escalation was half wrong: the counts DID move**, and C56 is red on the README headline drift (claims 51/3/10/64, suite reports 54/2/11/67) — that drift is session 1's C73/C74/C75 registrations, pre-existing, and it was already red on the previous push. **`readme_gen --write` is now measured as owed, not predicted.** Worse: the drift makes C56's own baseline red, so the falsification sweep probed **7** checks rather than the 8 task 6 predicted — **doc drift removed a gate from the measurement**, which is a stronger argument than the red tick. **And the step nominated as C63's verifier (step 9) was itself skipped** behind step 5; the answer arrived only because step 5 runs the whole registry. A deferred verification aimed at a gated step is not a deferred verification. **Two claims falsified.** (a) "biome check ./src reports zero error-level findings" — CI reported **3 errors**, in `DataPathNotice.tsx`, `surfaces/data-paths.ts`, `lib/interruption-precision.ts`, all from `5db5eb1`. Root cause: 40 local `needs to be formatted` errors, **one** proven a `core.autocrlf` artifact, and that proof over-generalised to all 40. Now proven mechanically instead — `biome format --write ./src` reports "Fixed 40 files" while `git diff` shows exactly **3**, because git normalises line endings. (b) `SYNAPSE CI` fails at step 5 `ruff check` on two findings from `e000258` — a **101-character line** and one `TC003` — and **that one line was gating 18 steps and 3 jobs across two pushes**: mypy strict x3, the I-1 no-paid-API check, the I-2 reward-isolation check, C56, unit tests, coverage floors, `sprint6-verify`, `training-smoke`, and **`uplift-verify`, so Properties 38-60 have NEVER executed in CI on this branch.** Repaired, with step 6's `ruff format --check` (10 files, all `e000258`'s). **The chain is advanced, not cleared:** step 8 `mypy --strict orchestrator/` reports **78 errors in 32 files**, 21 of them one `confidence_threshold` pattern, and it **must not** be cleared by defaulting that argument — `GuardrailEngine` consumes it, so a default substitutes an unreviewed number on the I-5 confidence gate. Owner's decision. Sweep: `ruff check`/`ruff format --check` 0 at CI's exact scope, `mypy --strict packages/` 0, `mypy --strict orchestrator/` 78 **unchanged** with nothing new at either edited line, `pytest --collect-only` 7 collected, `biome check ./src` **0**. **Environment trap found: the local clock is ~2h45m ahead of the commit timestamps git and GitHub agree on** — identify a run by `head_commit.message`, never by timestamp. |

| 2p-green | 2026-09-01 | **`frontend.yml::quality` went GREEN on the run for `85ed97a`, and tasks 1.2, 1.5 and parent 1 are `[x]` — earned.** Census 54/3 -> **56 done / 1 pending**; only task **10.4** remains `[~]`, discharging at checkpoint A. | All ten steps of that job pass, including step 7 `TypeScript strict` and **step 8 `Vitest unit + property tests`** — the job named in both tasks' `discharge:` lines. **Step 8 is the only route by which 1.5 could ever have been discharged:** `biome check` never scans `frontend/spec/`, `tsconfig.json`'s `include` omits `frontend/spec/effectiveness/__tests__/**`, and I-0 bans `vitest`, so nothing local could judge it. It sat behind two other steps' failures for **three** CI runs before its own step first executed. That is the clearest case in this spec for why `[~]` exists: an `[x]` at authoring time would have claimed a pass nothing had produced, and the mark is what kept it honest across two failed repair attempts. **Both predictions from `98b37d9` confirmed at step level:** the Biome/format repair turned the frontend job green, and the Ruff repair advanced `SYNAPSE CI` from step 5 to **step 8 `mypy --strict orchestrator/`** (steps 5, 6, 7 now pass) — so `uplift-verify` is still skipped and **Properties 38-60 have still never executed in CI.** Green in the frontend job also unblocked **five** previously-skipped downstream jobs; three are now red (`Playwright E2E + axe` — which `blocking-steps.yaml` already records as **expected red** until its backendless-preview flakiness is fixed — plus `Effectiveness harness` and `Stryker mutation`). **None had ever run on this branch: they are newly visible, not newly broken**, and reading them is the next honest step rather than a regression to chase. Nothing ticked on the strength of a local run; every mark in this row rests on a CI job's own verdict. |


| 2q | 2026-09-02 | **Closed the first third of checkpoint A and adopted two pieces of external debt, by explicit operator decision on three questions.** Ticked **6** on the reviewed survivor list, which **closes E1**. Registered new parents **26** (regenerate the projected documents) and **27** (`mypy --strict orchestrator/`), with **2r** placed before session 2 in the batch table. Landed 26.1 and 27.1 as `[~]`. Census 132/57/1/74 -> **140 leaf / 57 done / 3 pending / 80 open** (72 authorable, 8 CI-gated). Two commits: `e1b274c` the regeneration job + all three couplings, `d1c4dc7` the declaration fix; branch 20 ahead of `main` before the ledger commit. | **Four findings, and two of them are corrections to this session's own instructions.** **(16)** **Checkpoint A needs TWO `twin-regret` dispatches, not one.** `policy.py::materiality_margin` returns `None` on `committed is None` **before** reaching the `must_be_below_measured_headroom` guard, so on run 1 the guard that makes the margin falsifiable-by-construction never executes; and `classify_regret` with `margin=None` returns `verdict: unavailable`, so recording task 11 off run 1 means the operator hand-computes a verdict the instrument did not produce (I-7, the same shape as defect 9). Run 2 is a *verdict materialisation, not a re-measurement* — `_measure` iterates `for seed in range(replicates)`, seeds `0..199` fixed, interval seed committed — so there is no metric-shopping surface. Unactioned; handed to the operator. **(17) CONFLICT F: the instructed `confidence_threshold` repair would have injected 21 unreviewed numbers onto the I-5 gate.** The plan said "fix the 21 at the call sites rather than at the signature". Read first: `Field(0.7, ge=0.0)` **already carried** the reviewed default, positionally; it is the **only** `Field(...)` in the class while every other field uses a bare default; `[tool.mypy]` has **no `plugins` entry** so there is no pydantic plugin and mypy synthesises `__init__` from PEP-681 `dataclass_transform`, which recognises a default only as `default=`. **Three of the 21 sites are production** (`inference/serve.py` x2, `audit/cli.py`). Repair was one line at the declaration. **(18)** The 22nd error `thresholds.py:118` was the **same defect in production** — it assigns the class OBJECT into a `Callable[[], OrchestratorConfig]` slot, which is not a zero-arg callable while `__init__` is believed to require the argument — and had been filed as an unrelated `assignment` error blocking `pre-commit install`. That list also said "nine" while naming eight paths; **seven** remain. **(19) CONFLICT G: the `required-checks.yaml` half of coupling 2 was over-costed.** `ineligibleEntry.reason` is a **closed six-value enum** with `additionalProperties: false` and no "dispatch-only" member; `required_checks_truth` validates declared->resolves, not completeness; eight existing workflows carry no entry. Honouring it would have meant amending a schema for a job that is not a check. **The stated gate was deviated from, deliberately and with proof.** The plan set `78 -> 57` as a revert condition; measured **78 -> 56**. Not reverted, because the deviation's *shape* was checked rather than assumed: exactly two codes moved and both to zero (`call-arg` 21->0, `assignment` 1->0), **every** other code identical, no new code, and the 22nd error's mechanism read directly from source. Mechanical literalism would have discarded a correct behaviour-neutral repair for fixing 22 instead of 21. **The fourth same-commit coupling was observed firing rather than assumed:** `gate_surface --check` went non-zero on the new job (17->18 files, 54->55 jobs, 370->378 steps, NOT-EXECUTED +1 under all three contexts) and back to 0 after `--write` (533 -> **536** rows); `blocking-steps.yaml` 10 -> 11 entries, resolved by `workflow_shape_truth`. **New trap, three detours:** a `ruff format --check` diff whose two sides look *character-identical* is a **line-ending** diff — programmatic edits wrote LF into CRLF files, `git ls-files --eol` reported `w/mixed`; repaired with Python at `newline=''`. **Also:** a PowerShell splatting bug made `workflow_shape_truth` report exit 2; it is 0 when invoked correctly — a gate's non-zero exit is a claim about the gate, so verify the invocation before believing it. Sweep: ruff + ruff format **0** at CI's exact scope (386 files), `mypy --strict` clean on both changed non-test files, **24 tests passing** (5 + 4 new, plus 15 at `heavy` across the confidence-boundary suites), six cheap gates **0/0/0/2/1/0**, census 0, process sweep clean (python 0, chrome 0, one `node` = Kiro's own server). **`ledger_gen`, `readme_gen`, `verify_claims` and `doc_truth` were not run locally in any form** — that is what the new job exists for. **Step 8 still fails at 56 > 0, so `uplift-verify` is still skipped and Properties 38-60 have still never executed in CI.** |


| 2r-pre | 2026-09-02 | **A repair session that discharges nothing, opened because a defect was found by reading AFTER 2q closed and had to land before checkpoint A step 3 executed. NO TASK TICKED** -- 10.4 and 11 remain the operator's, and this session deliberately makes 10.4's remaining work smaller rather than doing it. One commit. Census unchanged at **140 leaf / 57 done / 3 pending / 80 open**. | **(20) Task 10.4's owed pin had nowhere to anchor, and standing it up as instructed would have made C56 non-passing while the gate a reader would check reported green.** A pin is a triple -- document anchor, mechanical source, extractor -- and the document side did not exist. A repo-wide grep put the derived literal in exactly three places, none pinnable: `SESSION_PROTOCOL.md`, whose own rule is "there is no count in this document, and there should never be one again"; **`HANDOFF.md`, which this protocol overwrites every session**, so a pin anchored there dies at the next close; and the `note` prose inside `ratchets.json`. **ADR-055 D2.5 -- the document the sibling pin anchors to -- deliberately stops at `service_points * 0.08` and states no derived literal.** **The mechanism, and the first reading of it was WRONG in a way worth recording:** `doc_truth.documented_value` requires the anchor to match exactly one line; zero matches raises `_Unresolvable`, whose docstring is "Always becomes a `skip`, never a pass" -- **a skip, not a fail.** Because the pin is `required: true` that skip is non-maskable (doc_truth's own module docstring, R1.4/R1.6: "the aggregate verdict is `unavailable`, and no number of `ok` siblings can supply a passing verdict"), so **C56 would go SKIP.** Not milder than FAIL for this purpose: the falsification sweep reports `indeterminate` for any gate that does not PASS on its unmutated baseline, so C56 leaves the probeable set either way -- the exact measurement loss task 26 exists to recover. **And C75 would have reported 15/15 GREEN**, because `pin_extractor_truth` runs every declared extractor against its declared source "unconditionally, independent of whether the document anchor matched" -- it probes the source side only. A reader would have seen C56 non-passing after a regeneration and concluded the regeneration failed. **Resolved with the mechanism the pin table already has, not a new anchor invented today:** drafted and parked in `pending_pins:`, which that section states is "NOT evaluated by doc_truth", with `activates_after` naming task 10.4 and **both** graduation conditions (value non-null AND D2.5 stating the literal on exactly one line). Precedent is `mutation-fast-required-job`, parked because landing it "would convert a documented, attributable gap into an unattributable red gate". **`required: false` was available and rejected** -- it would have let the pin stand today without touching C56, but a pin that cannot fail is not a pin, and downgrading a claim to make it safe is the assertion-weakening R2.10 forbids. **A trap inside the trap:** D2.5 already contains the rule's own code-block line `materiality_margin = service_points * 0.01 * weight(1 - fill_rate)`, so a naive anchor `materiality_margin = (?P<value>[\d.]+)` is safe only because `service_points` does not match `[\d.]+` -- luck, not design, and the exactly-one-line contract makes a second match as fatal as none. The parked anchor uses a `derives` verb to be unambiguous. **(21) CORRECTION TO 2q'S OWN CLOSING SUMMARY, surfaced rather than quietly applied.** 2q told the operator Track A and Track B were freely orderable because both `uplift.yml` jobs carry `needs: NONE`. **True of CI triggering, false of the generated documents.** `ledger_gen` and `readme_gen` project the PASS/FAIL/SKIP counts of one registry execution and **C56's status is inside those counts**, so task 10.4's pin can move it. A regeneration committed before the margin lands is stale the moment it lands, costing a second ~45-minute dispatch. **2r's internal order is now fixed: 27.2-27.5 first (they touch no generated document and are safe beside checkpoint A), 26.2/26.3 last.** Recorded as conflict H and a `Track coupling` decision row. Sweep, all measured: **`pin_extractor_truth` 0 with declared=14 probed=14 both_sides_resolved=14 -- the load-bearing check, because 15 would have meant the draft landed in `pins:` and is the precise defect this session exists to prevent**; `workflow_shape_truth` 0; `sweep_budget_truth` 0; `dataset_licence_truth` 2 (honest SKIP); `task_claim_truth` 1 (pre-existing, `core-purpose-uplift`); `gate_surface --check` 0; census 0. **No `ruff`/`mypy`/`pytest` owed and none run** -- Phase 1 changed no Python source, and running them for appearance would be theatre. **`ledger_gen`, `readme_gen`, `verify_claims`, `doc_truth` not run in any form.** Line-ending trap hit for the fourth session running: the pin-table edit produced `w/mixed` (337 CRLF / 118 LF); normalised to the dominant CRLF with Python at `newline=''`, after which `git diff --stat` showed +86/-0, pure content. |


| 2r-pre-b | 2026-09-02 | **Attempted checkpoint A's dispatch and found TWO blockers ahead of it, one of them structural. Neither track can start.** Commit `a3b6dff` fixes the first. The second is an operator decision and is costed, not taken. **No task ticked.** | **(22) `uplift.yml::twin-regret` could not have imported the twin.** Pre-flighted the install closure before spending the dispatch -- the lesson from defect 14 (`scipy`) applied rather than re-learned. Its closure was `packages/requirements.txt` + `-e packages/` + `simpy numpy pyyaml`, and **`pydantic-settings` is in none of them**: not the six packages in `packages/requirements.txt`, not the seven in `packages/pyproject.toml`'s `dependencies`, not its `dev` extra. It lives in every `agents/*/requirements.txt`, which this job does not read. So the unavoidable chain `uplift.regret` -> `_measure` -> `uplift.foresight` -> `digital_twin.simulation.engine` -> `digital_twin.config` -> `pydantic_settings` would have raised `ModuleNotFoundError` **at import, inside the job that exists to run the measurement, on the first dispatch checkpoint A ever made.** The job has never executed, so nothing had reported it. **Proven over the whole graph rather than the one path first followed:** a static AST walk of all **9** first-party modules reachable from `uplift.regret` reports `pydantic_settings` as the **only** third-party import outside the closure. Fixed narrowly, in that job only, with the version bound copied verbatim from `agents/*/requirements.txt` per CLAUDE.md's pinning rule. **The broad fix is the dangerous one and was rejected:** adding it to `packages/requirements.txt` widens the closure `truth-gates`, `quality-gates` and the new regeneration job run in, and several registered checks report SKIP when an optional import is missing -- so it could turn a SKIP into a PASS and **move the registry counts `doc_truth` pins**, immediately before task 26's regeneration. Coupling 4 checked rather than assumed: `gate_surface --check` exits **0** after the change, because the install step is not a declared-blocking anchor (twin-regret's entry is `all_steps: false`, naming only the measure and disclose steps) and GATE_SURFACE renders commands only in the anchors section -- so **no `--write` was owed**. `workflow_shape_truth --check` 0. **(23) `workflow_dispatch` IS NOT AVAILABLE FROM THIS BRANCH, and the whole checkpoint design rests on it.** `gh workflow run uplift.yml --ref feat/decision-quality-proof` returns **`HTTP 404: workflow uplift.yml not found on the default branch`**. `--ref` selects which ref's *code* executes; it does not make a workflow dispatchable. GitHub requires the file to exist on the **default branch** first. **`origin/main` carries 14 workflow files and `uplift.yml` is not one of them.** Neither is `truth-gates.yml` -- which still runs, because it triggers on `pull_request`, and a PR runs the workflow as defined in its own head. **`workflow_dispatch` has no equivalent escape.** `gh workflow list` shows the split precisely: `SYNAPSE Truth Gates` is registered because it has run, while `uplift.yml` and `regenerate-truth-docs.yml` do not appear at all, never having run. **This document's own checkpoint definition -- "push the branch, dispatch a workflow, read the output, record the verdict", and "`uplift.yml` carries only `schedule` and `workflow_dispatch`, so dispatch is the mechanism" -- is therefore unexecutable as written.** Unreachable until resolved: checkpoint A (10.4, 11), checkpoint B (14), task 26.2's regeneration, and tasks 22.3 and 25 whose `discharge:` lines name `uplift.yml::uplift-proof` -- **five CI-gated leaves plus the two `[~]` marks that depend on them.** **NOT resolved here, because the cheapest repair changes `main` and has a cost:** `uplift.yml` also carries `schedule: "0 3 * * *"` and its `if:` guards lead with `github.event_name != 'workflow_dispatch'`, so on `schedule` **both** jobs run -- landing it on `main` starts a nightly **~350-minute** `uplift-proof` that cannot produce an admissible artifact until E3/E5. Five options are costed in `HANDOFF.md`'s owed list; the recommendation is to land the dispatch-only `regenerate-truth-docs.yml` on `main` first (harmless, unblocks 2r's last step) and decide `uplift.yml` separately. **An operator decision, surfaced rather than taken.** Sweep after both commits: six cheap gates **0/0/0/2/1/0**, census **0** and unchanged at 140/57/3/80, `gate_surface --check` 0, `workflow_shape_truth --check` 0. No `ruff`/`mypy`/`pytest` owed -- no Python source changed in either commit. `ledger_gen`, `readme_gen`, `verify_claims`, `doc_truth` not run in any form. Process sweep clean. |


| 2r-pre-c | 2026-09-02 | **Finding 23 RESOLVED, and without touching `main`.** Commit `e8e9528`. Checkpoint A is now reachable; running it is still the operator's. **No task ticked.** Census unchanged at 140/57/3/80. | **The framing was the defect, not the constraint.** Both options offered to the operator traded off *within* an assumption -- that `uplift.yml`'s trigger set was fixed -- and the operator's own recommendation was among the rejected. `truth-gates.yml` is **also** absent from `main` and runs on every PR, which is empirical proof that `pull_request` reaches a branch-only workflow while `workflow_dispatch` cannot. **The mechanism:** `pull_request: types: [labeled], branches: [main]`, run by adding the `measure-twin-regret` label to PR #84. Specifying `types` replaces the default `[opened, synchronize, reopened]`, so it does not fire on pushes, and an unrelated label produces a run in which every job skips at zero cost. **THE LOAD-BEARING HALF WAS THE GUARDS, NOT THE TRIGGER.** Both led with `github.event_name != 'workflow_dispatch'` -- correct while the only other trigger was `schedule`, and **fail-OPEN against a new one**: under that form `pull_request` would have made the disjunct true and fired `uplift-proof`, ~350 minutes on a run that cannot be admissible until E3/E5. Inverted to **allow-lists** naming `schedule` explicitly, so session 2p's intent (never silently stop the nightly -- "a job that stops running is indistinguishable from a job that passes") is preserved by declaration rather than by a double negative, and a future trigger cannot enable the most expensive workload in the repository by accident. **`uplift-proof` is excluded from `pull_request` for a second reason beyond cost:** on that event `GITHUB_SHA` is the synthetic MERGE commit, and that job's gate compares the artifact's `revision` against it to reject stale or foreign evidence -- so a labelled powered proof would be provenance-inadmissible **by construction**. `twin-regret` carries no such gate, which is exactly why the label is safe there and would not be safe there. **A revision-disclosure step was added FIRST in `twin-regret`** so a failed run still records which revision failed: `github.sha` on a `pull_request` event is a merge commit that appears in no branch's history, so a reader asking "which code produced this number?" would get a commit they cannot find. `github.event.pull_request.head.sha || github.sha` yields the real head on a labelled run and the right answer everywhere else. Checkpoint A can END this spec; its verdict must be attributable to a commit that exists -- the concern task 17.7 gates mechanically for the powered proof. Deliberately **not** declared in `blocking-steps.yaml`: that entry is `all_steps: false` naming the two substantive steps, and the declaration set should mean "a swallowed failure here would corrupt evidence" -- an `echo` of context variables does not qualify, and over-declaring dilutes what a declaration means. **VERIFIED BY TRUTH TABLE, and it earned its keep three times.** Both guards were evaluated over every event x input x label combination: `schedule` -> both run; `workflow_dispatch` -> correct per-job selection; `pull_request` unlabelled or wrongly labelled -> **neither**; `pull_request` + label -> regret only; `push` (undeclared) -> **neither**. That check caught (a) an orphaned `|| inputs.job == 'twin-regret'` disjunct left by the first edit, which would have defeated the allow-list's fail-closed property; (b) a **duplicated** label clause left by the second; and (c) a YAML subtlety -- in a `>-` folded scalar a MORE-INDENTED continuation line is preserved verbatim rather than folded, so the parsed expression carried literal newlines. **Reading would not have caught any of the three reliably.** Four alternatives rejected and recorded in the workflow header: landing the file on `main` as-is (its own header says an incomplete run exits 2 and turns the job RED, so the nightly would manufacture a **permanent red on `main` that means nothing** -- a gate with a foreordained verdict is the failure this spec exists to remove, and installing a second one while repairing the first would be incoherent); landing it with the schedule stripped (works, but diverges `main` from the branch and spends a change to the shared default branch to buy what the branch can grant itself); landing only `regenerate-truth-docs.yml` (unblocks task 26.2, whose own precondition is blocked, so it buys nothing yet); and a `push:` trigger on a magic branch prefix (better provenance, but litters the remote and hides intent in a ref name). **Still outstanding:** `regenerate-truth-docs.yml` is also absent from `main`, so task 26.2 remains undispatchable -- it is 2r's last step and its precondition is outstanding anyway, so nothing waits on it. Coupling 4 honoured and **observed firing**: `gate_surface --check` exited 1 on the new trigger and step, 0 after `--write` (536 -> **542** surface rows). `workflow_shape_truth` **379** steps (was 378), 11 blocking entries, verdict pass. Six cheap gates **0/0/0/2/1/0**, census **0**. No `ruff`/`mypy`/`pytest` owed and none run -- no Python source changed. The single over-100-character line is **pre-existing and byte-identical at HEAD**, confirmed rather than assumed. `ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth` not run in any form. |
