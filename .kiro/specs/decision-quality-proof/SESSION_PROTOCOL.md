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

1. Push the branch. This is its **first CI exposure**; every gate on it runs for the first time.
   Expect the reds `HANDOFF.md` lists as honest, and repair none of them by weakening.
2. Read `truth-gates.yml::falsification-sweep`'s survivor list. **Bring it to the user before
   fixing anything** — a gate proven not to enforce means every number it reported is
   unsupported. Never weaken a mutation to clear a survivor. That discharges task 6.
3. Dispatch `uplift.yml::twin-regret`. Read the reported regret and its interval.
4. Commit the materiality margin per task 10.4 — **the rule is already committed and enforced;
   instantiate only the value from it** (`service_points * 0.01 * weights.unmet_service`), record
   the measured headroom it was checked against, and pin the derived value. The run's own output
   reports `margin_rule`, `margin_rule_derives` and `comparator_headroom` so the number is read
   off the rule rather than chosen. That discharges 10.4.
5. Read task 11's verdict against the table below and record it in `tasks.md` with evidence.

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
| **A** | 6 · 10.4 · 11 | — | **Operator.** First CI exposure, survivor list, regret measurement, margin. Task 11's verdict gates session 2. |
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
sum**, because this sum is prose and the census is not.

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

# 3. The cheap gates. Five of them, all pure file reads, ~1s each.
python -m scripts.audit.workflow_shape_truth              # C64
python -m scripts.audit.pin_extractor_truth --check       # C75
python -m scripts.audit.sweep_budget_truth --check        # C73
python -m scripts.audit.dataset_licence_truth --check     # C74 (expect exit 2 = honest SKIP)
python -m scripts.audit.task_claim_truth --check          # ticked-but-not-landed

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

Expected exit codes for the block above, as executed on 2026-09-01: `workflow_shape_truth` 0,
`pin_extractor_truth` 0, `sweep_budget_truth` 0, `dataset_licence_truth` **2** (honest SKIP —
the M5 terms sit behind a Kaggle acceptance gate an agent must not accept), `task_claim_truth`
**1** (pre-existing, `core-purpose-uplift`), `spec_ledger_census` 0.

**NEVER run**, in any session (I-0): `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, `gate_fault_injection --sweep`, repo-wide `pytest`, `--cov`, `-n auto`,
`pnpm` anything, `docker compose`, or any `MIN_SCENARIOS`-scale run. Each spawns either the whole
Check_Registry as a 900s subprocess or a category-4 workload.

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
