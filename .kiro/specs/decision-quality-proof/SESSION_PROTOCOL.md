# SESSION PROTOCOL — decision-quality-proof

**Binding working agreement. Read this before starting work in any session.**

This document exists because the `decision-quality-proof` spec is too large for one session's
context window. Work is therefore batched, and **the batch boundary is a hard stop**.

---

## The rule

> **At most THIRTY leaf tasks per session. Stop earlier at a barrier or a phase boundary — which
> is what will actually stop you. Then regenerate the handoff and tell the user to start a new
> session.**

Thirty is a **ceiling, and it is expected never to bind.** That is why it was chosen.

### Why the cap moved from ten, and what the number was really proxying for

The ten-task cap was written at the end of session 1, with a stated rationale: context degrades
before it exhausts, an agent at 85% context makes worse decisions than one at 40%, and the failure
mode is **silent** — it stops reading files it should read and starts inferring from surrounding
code. **That rationale is correct and is unchanged.** What was wrong was using *task count* as its
proxy.

Eight sessions of evidence, read from this document's own progress ledger:

| Session | Leaves ticked | What actually consumed the session |
|---|---|---|
| 1 | ~34 | authoring plus 3 defects — it **overran the ten-cap in the very session that wrote it** |
| 1r | 0 | protocol re-cut, the census tool, the margin rule |
| 2p | 1 | seven defects |
| 2q | 3 | four findings, two of them corrections to its own instructions |
| 2r-pre / -b / -c | 0 / 0 / 0 | findings 20, 22, 23 |
| 2r | 4 | Conflicts I and J, findings 24–29 |

**42 leaves and 29 findings across eight sessions; mean 5.25 leaves.** The ten-cap was the binding
constraint in **zero** of them. What binds is dependency boundaries and defect discovery. A ceiling
never once reached protects nothing — it only splits coherent work, and at ten it was splitting two
natural blocks of 21 and 22 tasks straight through their schema changes.

**Task count is a poor proxy for all three risks it stood in for, and each has a better governor:**

| Risk | What it actually scales with | Governor |
|---|---|---|
| Context degradation | files read and findings held unwritten, **not** tasks ticked | **wave discipline** — write findings into the ledger at each wave, delegate reading to sub-agents |
| Bisect depth when verification goes red | **commits**, not tasks | **one commit per wave**, so a red is bounded to one wave's diff |
| Authoring past a gate that could invalidate the work | **checkpoint crossings**, not tasks | **the barrier stop**, now *derived* by the census rather than asserted |

A two-task batch that crosses checkpoint B is more dangerous than a twenty-eight-task batch that
does not. The count was never the thing that mattered.

### The barrier stop — the one rule that had to become mechanical

**At ten, this rule was satisfied by accident. At thirty it is not.** `--next 30` offers
`12.1 … 13.7` and then jumps straight to `15.1`, stepping over **checkpoint B** — whose own task
says the consensus experiment "**must NOT be run**. Do not proceed to E3." `next_batch` filters
gated leaves out, so the batch could not see what it crossed.

So the census now derives it. `LedgerCensus.barriers_crossed(size)` names every open CI-gated leaf
with at least one offered id after it in ledger order, and `format_report` prints:

```
[!!] barrier    : 14 is CI-gated and 19 of the 30 offered id(s) follow it in ledger order
                  -> uplift.yml, task 13.7's E2c measurement steps (checkpoint B).
                  Ledger order is not execution order: confirm the batch does not DEPEND on it.
```

**It is advisory and never truncates, and that is deliberate.** Ledger order is not execution
order: session 2r's own batch (27.2–27.5) legitimately sat after checkpoint A's task 11 and did not
depend on it. A census that refused work on ledger position alone would have refused a correct
batch. So it names the crossing and leaves the judgement where the judgement belongs.

**Your obligation: for every barrier the census names, state in the session's opening whether the
batch depends on it.** An unanswered barrier line is a stop, not a warning.

### Wave discipline — this is what replaces the count

A thirty-task session is **three waves of about ten**, not one long run. Each wave is
`read → author → verify → commit`.

1. **Author** the wave's leaves.
2. **Verify** the wave: `ruff check` and `ruff format --check` on that wave's changed files,
   `mypy --strict` on its changed Python, and **one** bounded `pytest` invocation over the loci
   that wave touched. Serial, never concurrent.
3. **Write the findings into the ledger as you go** — into the task body in `tasks.md`, not into
   your context. A finding held for the end of a thirty-task session is a finding that will be
   written from memory.
4. **Commit the wave.** Never carry two waves in one commit: the commit is the bisect unit, and
   bounding it is the whole reason waves exist.
5. **Re-read** the authority file for the next wave's area before starting it. This is the specific
   defence against the silent failure mode, because the symptom of degradation is skipping exactly
   this step.

**Delegate reading, never execution.** I-0 permits **unlimited** parallel sub-agents for reading,
writing and analysis, and **exactly ONE** that executes code. At twenty-plus tasks the main context
cannot hold every file it needs, so dispatch `context-gatherer` sub-agents per area in parallel and
keep every command in the main agent. That is how a thirty-task session stays inside I-0 rather than
around it.

### What "one task" means

One **leaf** entry in `tasks.md`: a numbered sub-task like `12.3`, or a checkpoint parent like `11`
that has no sub-tasks. Leaf status is derived from the id tree — `12` is a parent because `12.1`
exists — not from indentation. A parent with sub-tasks is ticked when its last child is.

A session that reaches a barrier at task four stops at four. **Padding a session to reach thirty is
the failure this ceiling is most likely to cause, and it is forbidden.** The number is a limit on
how much may be done, never a target.

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
2. Confirm the last wave is committed. **An uncommitted wave is not a bisect unit.**
3. Run the closing verification sweep (below) and record real numbers.
4. Answer every `[!!] barrier` line the census printed: did the batch depend on it?
5. Regenerate `HANDOFF.md` — overwrite it, do not append. It must describe the tree as it is
   **now**, not as a diff against how it was.
6. Append a row to `## Progress ledger`. **Never edit a past row.** Record the wave structure —
   how many waves, how many leaves in each, and which wave any red came from.
7. Tell the user, explicitly: **"Session complete. Start a new session and paste
   `NEXT_SESSION_PROMPT.md`."**

### The one permitted overrun

If the last task leaves the tree in a state that **cannot be verified** — a half-edited module, a
schema change whose consumers have not moved, a rename applied on one side of a coupling — finish
the coupling and stop at thirty-one or thirty-two. A same-commit coupling left half-applied is a red
gate for the next session and costs more than the extra task saved. **Record the overrun and its
reason in the progress ledger.** Never overrun for convenience or momentum.

At thirty this clause should almost never fire, because the couplings it protects — a schema change
and its fixtures, a rename and its declaration — now sit **inside** one session rather than across a
boundary. That is one of the concrete gains of the larger ceiling: at ten, task 15.1's
`UpliftArtifact` change and the `tests/uplift/` fixtures it moves were in different sessions.

---

## Counts: derive them, never read them

There is no count in this document, and there should never be one again. Three documents used to
carry the same three numbers by hand.

```powershell
python -m scripts.audit.spec_ledger_census --next 30
```

That command **is** the census. It reports the leaf total, the three mark buckets, the CI-gated
set derived from `discharge:` lines, the next authorable batch in ledger order, and **every barrier
that batch steps over**. Add `--files` at session start: it reports open tasks whose named artifacts
already exist, which is exactly the session-1 failure mode. `--json` for a payload, `--check` for an
exit code (`0` pass, `2` unavailable — an unclassifiable mark or a duplicated id is non-passing,
never a guess).

`DEFAULT_BATCH` lives in `scripts/audit/spec_ledger_census.py` and is **30**. It is the single
place the ceiling is written down; when it moves, the code and the four documents that name it move
in the same commit. It is not a registered check and no gate reads it, so changing it moves no
registry count — verified before it was changed.

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

Checkpoints are **operator actions, not authoring sessions**: push the branch, run a workflow, read
the output, record the verdict. Zero local compute, so I-0 is unaffected.

> **CORRECTED IN SESSION 3 — CONFLICT L. This section said "`uplift.yml` carries only `schedule`
> and `workflow_dispatch`, so dispatch is the mechanism", and its numbered steps were stale in
> FOUR ways.** The batch table's row A was updated to "reachable by labelling PR #84" when finding
> 23 was resolved; **this procedure, directly below it, was not** — so the binding working
> agreement still instructed a command proven to return HTTP 404. Surfaced rather than quietly
> patched, because a stale instruction in the highest-precedence procedure is the failure mode this
> whole document exists to prevent. The four:
>
> 1. **The mechanism is a LABEL, not a dispatch** (finding 23, repaired in `e8e9528`).
>    `workflow_dispatch` requires the workflow on the default branch; `pull_request` does not.
> 2. **Step 0's `workflow_dispatch.inputs.job` selector already landed**, in session 2p's
>    `85774e1`. Following the instruction would re-author a committed change.
> 3. **Step 1 discharges task 6, which is already `[x]`** — reviewed and accepted in session 2q.
> 4. **It describes ONE run where finding 16 proves TWO are required.** On run 1
>    `policy.py::materiality_margin` returns `None` at `committed is None` *before* reaching the
>    `must_be_below_measured_headroom` guard, so that guard never executes, and `classify_regret`
>    with `margin=None` returns `verdict: unavailable`. Recording task 11 off run 1 means an
>    operator hand-computing a verdict the instrument did not produce (I-7).

### Checkpoint A — before task 12 is authored

Discharges tasks **10.4** and **11**. (Task **6** was discharged in session 2q, on the reviewed
survivor list; it is no longer part of this procedure.)

**The branch is pushed, PR #84 is open, and the job is reachable by label.** What remains is two
labelled runs, one ADR amendment, one margin commit, and one recorded verdict.

0. **Nothing to prepare.** The `workflow_dispatch.inputs.job` selector landed in `85774e1` and the
   label trigger with its fail-closed per-job allow-list landed in `e8e9528`. `twin-regret`'s
   install closure was repaired in `a3b6dff` (finding 22: it could not have imported the twin).
1. **Run 1, by label.** Add **`measure-twin-regret`** to PR #84, then remove it so the next label
   event does not re-measure. Read `regret`, `interval_low`/`interval_high`, `comparator_headroom`,
   `margin_rule`, `margin_rule_derives`, `margin_rule_below_headroom` and
   `interval_excludes_rule_margin` from `artifacts/uplift/twin-regret.json`. **Expect
   `verdict: unavailable`** — that is finding 16, not a fault.
2. **One ADR-055 D2.5 amendment covering BOTH owed amendments, one commit, one amendment-log
   line.** State the derived value as a literal on **exactly one line**, in the `derives` form the
   parked pin's anchor requires, and correct `bracketing.upper` if the measured headroom moved from
   `11.79 - 2.93 = 8.86`. D2.5's own rule puts the amendment **before** the run judged against it,
   so this lands before run 2.
3. **Instantiate the margin per task 10.4** — the rule is committed and enforced; take only the
   value from it (`service_points * 0.01 * weights.unmet_service` = `5.0 * 0.01 * 8.0` = `0.40`),
   record the measured headroom it was checked against, and **graduate the parked pin** from
   `pending_pins:` into `pins:`. Read finding 20 first; do not author a fresh pin. No second
   `ratchets.json` entry is owed. That discharges **10.4**.
   - **The anchor side has no cheap gate, and this is a real gap.** `pin_extractor_truth` probes
     source extractors "unconditionally, independent of whether the document anchor matched", so
     it will report 15/15 green even if the ADR line does not match; `doc_truth` is the gate that
     would catch it and I-0 forbids running it locally. Probe the document side before pushing —
     `doc_truth.documented_value(pin, text)` is a pure function and requires the anchor to match
     **exactly one** line. A mismatch takes C56 from FAIL to **SKIP** via R1.4/R1.6's non-maskable
     rule, which moves registry counts immediately before the regeneration.
4. **Run 2, by label.** Finding 16, not optional: this is a *verdict materialisation, not a
   re-measurement* — `_measure` iterates `for seed in range(replicates)` with seeds fixed and the
   interval seed committed, so there is no metric-shopping surface. That discharges **11**.
5. Read task 11's verdict against the four-value table below and record it in `tasks.md` with
   evidence.

**Task 11's verdict is four-valued, and the fourth value is the state the tree is in today.**

| Verdict | What it means | What it licenses |
|---|---|---|
| `material` | regret at or above the margin, interval excluding it | **STOP.** Finding 4 is falsified. R5 is re-cut (R5.3, R5.4). Report it plainly; it is a good outcome. |
| `sub-margin` | regret below the margin, every objective KPI recorded sensitive | Confirms Finding 4. **Unreachable today** by construction — the two sensitivity flips are earned by tasks 12.3 and 13.3. |
| `inconclusive` | regret below the margin, some objective KPI not observably sensitive | **PROCEED to task 12.** Task 11's own words: "the repair is to the instrument, not to the twin's physics" — and E2c *is* that repair. |
| `unavailable` | **no margin committed, so nothing was compared** | **Not a verdict.** This is the current state, and it is why checkpoint A exists. `unavailable` is not `inconclusive`: one is a measurement that could not decide, the other is the absence of a measurement. I-7 forbids reading absence as either a pass or a null. |

The predecessor protocol resolved three of these four and the tree was sitting in the fourth.

> **BLOCKING NOTE, SESSION 4 — `material` IS CURRENTLY FORCED, AND IT WOULD BE A CLAIM ABOUT THE
> WRONG COMPARATOR. Do not act on the `material` row until this clears (conflict M, task 11).**
>
> Run `34366766968` (sha `245d0dc`) measured `regret = 8.937888952967558`, interval
> `[8.916389405913677, 8.958204644600675]`, over 200 of 200 usable replicates. Run 1 reported
> `verdict: unavailable`, correctly, because no margin is committed. But:
>
> 1. **The baseline arm is `NoOpRecordingPolicy`** — "Pass one: change nothing", `restock_threshold:
>    0.0` — so the measured quantity is the **no-op's** regret, not the `(s, S)` regret R5.1 and
>    Finding 4 are about. The artifact says so in its own `comparator` field. `Par_Level_Reorder`
>    is a declared precondition owned by another spec and has not landed.
> 2. **`regret` and `comparator_headroom` are the same expression**
>    (`aggregate(policy) - aggregate(reference)`), confirmed equal to every digit in the run. So
>    `must_be_below_measured_headroom` admits exactly the margins that are below the regret they
>    will be compared against, and **every margin inside D2.5's own bracket (`0.264`–`0.709`
>    objective units) forces `material` by construction.**
>
> The guard was written to stop a margin being unfalsifiable in one direction and is blind to the
> other, because it checks the margin against the very quantity being judged rather than against
> an independent bound. **A verdict that cannot be anything else is not a verdict** — the mirror
> of this project's own "a number that cannot fail is not a number".
>
> **Consequence for this procedure: steps 2, 3 and 4 above are SUSPENDED.** Do not amend D2.5's
> derived literal, do not commit `materiality_margin.value`, do not graduate the parked pin, and
> do not run the second label. Step 1 is done and its numbers are recorded in task 10.4. The two
> candidate resolutions are costed in task 11 and both are the operator's.

### Checkpoint B — after task 13.7, before E3 is authored

Discharges task **14**.

1. Run `uplift.yml` with task 13.7's E2c measurement steps. **By label, for the same reason as
   checkpoint A** — this file is absent from `main`, so `workflow_dispatch` returns HTTP 404
   (finding 23). Task 13.7 must therefore wire its new steps into a job the label reaches, and
   must not assume a dispatch.
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

Sessions are sized by **barriers and phase boundaries**, under a ceiling of thirty. Re-derive
membership with `--next 30`; this table says where the boundaries are and why. **The ceiling binds
in none of the remaining sessions — that is the test of whether it was set correctly.**

| Session | Tasks | n | Bound by |
|---|---|---|---|
| **A** | 6 · 10.4 · 11 | — | **Operator.** Task 6 discharged in 2q. 10.4 and 11 outstanding, reachable by labelling PR #84. |
| **2q** | 6 · 26.1 · 27.1 | — | **Landed.** Task 6 ticked; the regeneration job; the `confidence_threshold` declaration fix. |
| **2r** | 27.1 · 27.2 · 27.3 · 27.4 | 4 | **Landed.** `mypy --strict orchestrator/` 56 → 0; CI step 8 passes. **27.5 left `[ ]`** — a CI read, now blocked behind 26.2. |
| **2 (next)** | 12.1–12.4 · 13.1–13.7 | **11** | **Barrier: checkpoint B.** Cannot be padded — 13.7 is what makes B reachable, and B can cancel E3 outright. |
| **B** | 14 | — | **Operator.** Pareto evaluation. Can cancel E3. |
| **3** | 15.1 · 15.2 · 15.4–15.6 · 16.1–16.7 · 17.1–17.9 | **21** | **Phase 3 boundary.** All of E3: interval + schema, both controls and their job, Power_Report, floor admission, C60 operator. |
| **4** | 18.1–18.6 · 19.1–19.8 · 20.1–20.8 | **22** | **Barrier: checkpoint C**, at the E4/E5 boundary. |
| **C** | 21 | — | **Operator.** Is the confidence contract live? Repair before E5. |
| **5** | 22.1 · 22.2 · 23.1–23.11 · 24.1 · 24.2 | **15** | **Barrier: checkpoint D.** Registration precedes generation, so 24.1/24.2 go last inside it. |
| **D** | 22.3 · 25 | — | **Operator.** Ratchet the floor if the measurement supports it; state the claim. |
| **Phase 6** | 26.2 · 26.3 · 27.5 | — | **All CI-gated, all blocked** — 26.2 by finding 23's residue, 27.5 by 26.2, and every one of them by the account-level CI block. |

Authorable total: `11 + 21 + 22 + 15 = 69`. CI-gated: `10.4`'s sibling `11`, `14`, `21`, `22.3`,
`25`, `26.2`, `26.3`, `27.5` = 8. Together 77 open leaves — but **check that against the census, not
against this sum**, because this sum is prose and the census is not.

**What the re-cut bought, stated so it can be checked rather than believed.** Eight authoring
sessions became **four**, and the two blocks the old ceiling was splitting — Phase 3 at 21 and Phase
4 at 22 — now fit whole. That matters beyond convenience: at ten, task **15.1**'s `UpliftArtifact`
`schema_version` + `interval` change and the `tests/uplift/` fixtures it moves fell in *different*
sessions, and the same was true of **17.2/17.5**'s `PoweredProof` interval and both floor tests.
Those are two of the three declared same-commit couplings. **A ceiling that splits a coupling
manufactures the half-applied state the overrun clause exists to prevent.**

**Session 2 is the proof that the ceiling is not a target.** It is eleven tasks and must stay
eleven, because checkpoint B sits behind 13.7 and can end E3. Nineteen further authorable ids exist
in ledger order immediately after it, and the census will name that crossing on every run.

### Why session 2r comes before session 2, and why it is not optional

**`uplift-verify` HAD never executed on this branch, and as of session 5 it HAS.** `ci.yml::uplift-verify`
declared `needs: quality-gates`; `quality-gates` failed at step 8, `mypy --strict orchestrator/`; so
Properties 38–60 — this spec's entire property surface — had never run in CI. Everything sessions
1, 1r, 2p and 2q reported green was **local evidence only**.

> **CORRECTED IN SESSION 5.** The edge was removed (`28cecce`, obstruction 2.5 disposition (a)):
> `required-checks.yaml` declares `uplift-verify` a `required:` check, and the edge made it
> reportable only as `skipped`. Its first execution — run `34384834900` — reports `830 passed,
> 9 failed` on the **fast** step, with the **slow** step skipped behind it. So the sentence above
> is now true only of the slow surface, and **"local evidence only" turned out to be generous**:
> seven of the nine failures reproduce locally at `dev` on the first try, in four modules no wave
> ever touched and therefore no sweep ever ran. See task 27.5 and finding 42.

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

> **AMENDED session 2r — the ordering above is now CONTESTED, and the reason is new evidence rather
> than a change of mind.** Session 2r cleared step 8, and the failure moved to **step 17, the C56
> narrative-truth gate**, failing on one claim: `doc-truth/headline-counts`, README
> `PASS 51 / FAIL 3 / SKIP 10 / TOTAL 64` against the suite's `54 / 2 / 11 / 67`. That is **task
> 26's own drift**, and steps 18–23 are skipped behind it. **So task 26.2 now blocks task 27.5**,
> and with it the first CI execution of Properties 38–60.
>
> The argument for going last is unchanged and still correct *as an argument about cost*: task 10.4's
> margin pin can move C56, so a regeneration committed before it is stale and the repair is a second
> ~45-minute dispatch. What changed is the other side of the trade. When that argument was written,
> nothing waited on the regeneration. **Now the entire property surface does.**
>
> The trade is therefore explicit and is the operator's: **one extra regeneration dispatch against
> continuing to hold every property this spec has written as local-only evidence.** `HANDOFF.md`'s
> decision 1 costs the three routes, including that `regenerate-truth-docs.yml` is still absent from
> `main` and so cannot be dispatched at all — the same finding-23 wall, whose repair is the
> operator's.
>
> Also recorded: **C56 is red on `main` itself**, at `045f44c`, this branch's fork point. The drift
> is not this spec's authorship and the regeneration repairs the default branch as well.

---

## Verification sweep — run per WAVE, and again before closing

Nothing here is expensive. All of it is category-5 under I-0. Serial, never concurrent.

### The I-0 reading this depends on, stated rather than assumed

I-0's category-5 list says "**One** scoped test run: a single file, or one narrow directory." A
three-wave session needs three. **The reading taken here is that the bound is on the SCOPE of an
invocation, not on a per-session quota** — the rule's named enemies are process *type* (services,
watchers, browsers) and process *count in parallel*, and its own precedent section attributes both
incidents to concurrency and leakage, never to serial repetition. Session 2r ran three bounded
`pytest` invocations serially inside the ten-task regime without objection.

**So: at most one `pytest` invocation per wave, each bounded to the loci that wave touched, strictly
serial, never concurrent — three per session maximum.** If the operator wants that written into I-0
rather than inferred here, the amendment is one line in
`.kiro/steering/local-compute-budget.md`: *"One scoped test run per wave, at most three per session;
the bound is on scope and serialisation, not on a session quota."* **I-0 outranks this document, so
until that line exists this is an interpretation and is flagged as one.**

`mypy --strict orchestrator/` is category 2 and its budget does **not** scale with the ceiling:
still four wide passes per session, whatever the task count.

### Per wave

```powershell
# Only what THIS wave touched. Never repo-wide -- pre-existing debt is not yours.
python -m ruff check <this wave's changed files>
python -m ruff format --check <this wave's changed files>
python -m mypy --strict <this wave's changed python files>
git ls-files --eol <this wave's changed files>     # w/mixed after ANY programmatic edit
$env:HYPOTHESIS_PROFILE='dev'
python -m pytest <this wave's touched loci> -q --tb=line -p no:randomly -m "not slow"
```

Then **commit the wave** and write its findings into `tasks.md`. A wave that is not committed is not
a bisect unit, and a finding that is not written is a finding that will be reconstructed from memory
at the end of a thirty-task session.

### Before closing the session

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

**And answer every `[!!] barrier` line the census printed.** For each one, state whether the batch
depended on the barrier. An unanswered barrier is a stop.

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


| 2r | 2026-09-09 | **Closed parent 27's four authorable leaves and made `ci.yml::quality-gates` step 8 PASS for the first time on this branch — then found that `uplift-verify` is still three obstructions away.** Ticked **27.1** (discharged by CI), **27.2**, **27.3**, **27.4**. **27.5 left `[ ]`**: it is a CI read and it is now blocked by **task 26.2**. Two commits: `b7954b6` the three errors that were the entire gate, `743ca6b` the wide surface 56 -> 0; the commit carrying the documents is the third. Census 140/57/3/80 -> **140/61/2/77** (69 authorable, 8 CI-gated). | **CONFLICT I, and it inverted the batch's premise.** `ci.yml::quality-gates` step 8 runs `mypy --strict orchestrator/ **--exclude orchestrator/tests**`; `HANDOFF.md`, `tasks.md:2657` and the standing prompt all said the 78/56 baseline was measured "at CI's exact command" using the **wide** `mypy --strict orchestrator/`, which **no workflow in the repository runs**. Read from CI's own step-8 log (run `33582858699`): **`Found 3 errors in 3 files (checked 44 source files)`** against 89 locally. The 56 decompose by scope as **3** in `orchestrator/` source (the whole of step 8's failure, every one `import-untyped`), **49** under `orchestrator/tests/`, **4** under `agents/`. Exclusion proven effective by grepping for imports of `orchestrator.tests` (none). Bucket A **equals CI's 3 exactly**, so the path filter was validated against CI's log rather than trusted. **Consequence: the group 27.3 flagged as "may not be repairable here... the honest outcome is a recorded deferral" was the ONLY group that gated anything, and the 24 `arg-type` errors 27.2 ranks first gate nothing.** A deferral would have been honest and would have left `uplift-verify` dead. **CONFLICT J:** stated HEAD `5bcf42c`/24-ahead was three commits stale; disk held `1508685` and the reflog shows `e8e9528` — finding 23's actual repair — absent from the commit table describing it as done. **(24) Ownership was misfiled in the OPPOSITE direction.** `tasks.md`'s "all 78 originate from `e000258`; none is on `main`" is false: nine of the twelve remaining files and both `agents/` files are byte-identical to `main`; the largest, `test_brownout.py` with 26 of the 56, is `be3edd1` on `main`. **And `git log -1` is LAST TOUCH, not authorship** — `test_cognition_phase.py` resolved to `e000258` and looked like this branch's, but `git diff origin/main` showed the failing assertion unchanged from `main` and a scratch run of `git show origin/main:<file>` **fails there too**. **(25) A cached mypy run hid the repair.** After adding the `yaml.*` override the narrow command still reported the same 3 errors; not a failed repair but a stale cache, because an entry is keyed to the **importing** module while `ignore_missing_imports` belongs to the **imported** one. `--no-incremental` reported `Success: no issues found in 44 source files`. Same shape as 2q's splatting bug: a cached verdict is a claim about the cache. **(26) `comparison-overlap` found two assertions that CANNOT FAIL, and a `union-attr` beside them was a third.** Both were the mirror case — comparisons mypy could prove **decided**: `test_data_provenance_builder.py` asserted R4.4's distinctness clause *after* two equality assertions had narrowed both operands to distinct `Literal`s; `test_protocol.py` asserted the FSM reached `COLLECTING` after a mutating `transition()`, but the preceding `== IDLE` assertion narrows the member expression and mypy does not discard it across the call, making the assertion provably **false**. Repaired by binding each observation to a fresh local where it is observed. The **same** narrowing mechanism explains four of 27.4's seven unused ignores — one mechanism, two opposite symptoms. **(27)** `test_protocol.py::test_tier1_skips_debate` **contains no assertion at all**, only comments describing what it would verify; `main`'s, recorded not rewritten. **(28) Clearing a gate reveals what it was shielding, and here it was three more things.** Step 8 was hiding 15 steps. Clearing it exposed **step 17, C56**, failing on one claim — `doc-truth/headline-counts`, README `PASS 51/FAIL 3/SKIP 10/TOTAL 64` vs suite `54/2/11/67`, which is **task 26's drift**. Behind that, step 19 will fail on `test_cognition_phase` and steps 20-22 have never executed on this branch **or on `main`**. **`main`'s own last three CI runs all fail `quality-gates` at step 17 on the same claim**, with its unit-test step skipped behind it, and `045f44c` is this branch's fork point — so obstructions 2-4 are default-branch debt this spec did not create. **The `>= 4`-deep chain means no single clearance licenses a claim about the job at its end.** **Repairs: 56 -> 0, every code to zero, no new code, and NO `# type: ignore` added anywhere**, no default given, nothing widened to `Any`, scope not narrowed. 27.2's 24 were **two** distinct messages across **12** call sites, uniformity *established* by grouping the captured messages rather than inherited from 27.1; `BrownoutController` reads exactly one attribute (`.state`), so the `AsyncBreaker` declaration overstated the requirement and was reported 24 times at the call sites instead of once where it lived — repaired with a read-only `BreakerStateSource` Protocol that `AsyncBreaker` satisfies structurally, leaving every production call site untouched. `warn_unused_ignores` **did not move in both directions**: the count held at exactly 7 across 27.2 and 27.3, so one clearing pass sufficed — a prediction that did not fire, recorded because it is why 27.4 was sequenced last. 27.4's seventh ignore kept `method-assign` and lost only the `assignment` code mypy proved redundant, which is not re-narrowing an unused ignore: the ignore is used, one of its two codes was not. **Deliberately NOT adopted:** `test_cognition_phase`'s failure is `main`'s, diagnosed for its owner (the test asserts every `kafka.produce` call targets the cognition topic, but ADR-038's `emit_agent_signals` and ADR-053's `emit_agent_metrics` share that producer; the repair is a **precondition correction**, not an assertion weakening) — parent 27 was adopted by explicit operator decision and a fourth adoption is not this session's to make (precedent: C28/zero-a-floor). **Budget, honestly counted:** three wide passes of a four-pass budget (27.2 and 27.3 own **disjoint** codes, so one pass attributes both per code), plus two narrow invocations and one single-file probe that isolated finding 25. Sweep: `mypy --strict orchestrator/` exit **0** over 89 files; CI's exact narrow command exit **0** over 44; ruff + ruff format **0/0** at CI's exact scope (386 files); **191 passed / 18 skipped / 5 deselected / 1 pre-existing failure** across 13 touched loci at `HYPOTHESIS_PROFILE=dev`; six cheap gates **0/0/0/2/1/0** with `pin_extractor_truth` at **14** declared (not 15); census **0**; all 16 written files byte-verified no BOM/no U+FFFD; **line-ending trap fired on all 11 edited source files** and was repaired to each file's dominant ending (`test_confidence_gate_universality_property.py` is pure LF and stayed LF). `ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth` not run in any form. **The lesson: a measurement can be exactly reproducible and still wrong about what it means.** The 56 reproduced to the error, per code, first try — and described a command no gate runs. The check that caught it was one free `gh` read of the log of the step being claimed. |


| 3 | 2026-09-09 | **STEP 0 ended the authoring session before it started: CI is still account-blocked, so ZERO of the 69 authorable leaves were reachable and none was attempted.** Ran the operator-authorised barrier-independent fallback instead — three items, two commits, **no task ticked**. Census unchanged at **140/61/2/77**. Two waves: wave 1 = route 1 + its coupling (`bbe4278`), wave 2 = the adopted `main`-owned test repair (`bf8693f`); the documents commit is the third. | **STEP 0, measured not assumed.** Run `34319298166`, `SYNAPSE CI`, sha **`fe8ddeb`** — three jobs `failure` in 2–3s with **`steps=0`**, three `skipped`, annotation verbatim *"The job was not started because recent account payments have failed or your spending limit needs to be increased."* All **8** workflows on that sha identical. **CONFLICT K — the stated HEAD was stale for the THIRD session running.** The prompt gave HEAD `3b2ec15`, 31 ahead, and named run `34315612360` at `bfad6a0` as the newest. Disk and `origin` both held **`fe8ddeb`**, **32** ahead of `origin/main` (which is still `045f44c`, unmoved), so **two** pushes newer than the run the prompt described existed, each with its own blocked run set. Checking the run for the actual head rather than the named one is what turned "probably still blocked" into proof. **BARRIERS ANSWERED, and the answer is the opposite of session 2r's.** `--next 30` offered `12.1 … 17.7` and named barriers **11** (30 of 30 follow) and **14** (19 of 30 follow). The batch **DEPENDS ON BOTH**: task 12's own precondition is "checkpoint A has run and task 11's verdict is not `material`", and `15.1`–`17.7` are the whole of E3, which checkpoint B can cancel outright. So the 30-offer truncates to 11 and then to **zero** — the prompt's claim that no authorable leaf escapes checkpoint A was re-derived rather than accepted. **Deliberately did NOT add the `measure-twin-regret` label**: it would have produced another zero-step failure and left a run in the history that a later reader could mistake for a measurement attempt. **(30) `gate_surface`'s `if:` parser cannot parse `contains(github.event.pull_request.labels.*.name, 'x')`** and renders the row `CONDITIONAL \| unparsable if:`. **Pre-existing and HONEST, not introduced here** — `uplift.yml::twin-regret` carries the identical rendering in the committed, **C63-green** surface, and `CONDITIONAL` is the conservative classification for a guard the parser cannot decide (I-7). Checked rather than assumed, because "my new row says unparsable" reads like a defect until you look at the green precedent beside it. Not repaired; not this session's remit. **(31) The `test_cognition_phase` repair had a SECOND symptom, and a pure filter would have created a vacuous assertion.** The telemetry emitters pass their payload **positionally** (`producer.produce(topic, item, key=...)`) while `_emit_phase` passes it as **`value=`**, so `c.kwargs["value"]` over the unfiltered call list raised `KeyError` as well — one defect, two symptoms, both repaired by the partition. And `set() <= anything` is **vacuously true**, so filtering to the phase topic and asserting the rest is a subset would have become an assertion that cannot fail the moment the telemetry side stopped firing — finding 26's defect class, in a hole the repair itself opened. Non-emptiness is now asserted, which both closes it and is the mechanical re-proof that the shared-producer premise holds in this run. **The recorded diagnosis was verified before it was trusted:** `protocol.py` has only **ONE** `produce(` call and it targets the phase topic; the other emitters are `emit_agent_signals`/`emit_agent_metrics` in `orchestrator/consensus/firehose_signals.py`, reached at `protocol.py:1021` and `:1024`. **(32) THE RUFF-SCOPE GAP IS LARGER THAN RECORDED, AND IT IS NOW QUANTIFIED.** Session 2r recorded that `scripts/` and `tests/` are outside CI's ruff scope. Read from `ci.yml`: the scope is exactly `packages/synapse_common/ agents/ orchestrator/`, `[tool.ruff]` declares no `include`/`exclude`, so the unlinted set also contains **`uplift/` and `digital_twin/` — this spec's own production code** — plus `api/`, `data_fabric/`, `ml_pipelines/`, `packages/tests/` and root `conftest.py`. Measured in two ruff passes: **530 lint findings** and **254 files `ruff format` would rewrite** (`tests/` 255/118, `scripts/` 103/48, `packages/tests` 57/21, `uplift/` 53/17, `api/` 24/8, `data_fabric/` 13/14, `ml_pipelines/` 13/7, `digital_twin/` 12/20, `conftest.py` 0/1). Top rules `ANN001` 99, `I001` 95, `E501` 69, `F401` 34. **The 254 is an UPPER BOUND and must not be reported as 254 real defects** — session 2p proved 37 of 40 comparable Biome findings were `core.autocrlf` artifacts, and this session re-proved the mechanism on `test_cognition_phase.py` (`i/lf` index against a 140-CRLF/51-LF worktree); separating real from artifact needs the `--write`-then-`git diff` comparison, which modifies files and was not taken unasked. **The 530 are not line-ending sensitive and stand.** **The decisive consequence, and it is why this stayed a measurement:** `Ruff lint` is step **5** of `quality-gates`, *earlier* than the step 8 session 2r cleared, and both ruff steps are **declared blocking anchors** in `blocking-steps.yaml`. Widening the scope would re-close the gate at an earlier point than the one just opened, re-burying `uplift-verify` behind 530 findings — and would owe `gate_surface --write` for editing an anchor step's `run:`. **And the two mitigations are mutually exclusive today:** CI does not lint these trees, and the `.pre-commit-config.yaml` ruff hook that would (no `files:` filter) is the one `HANDOFF.md` forbids installing, because it also installs the mypy stubs that unmask seven pre-existing errors under `uplift/`. **(33) Refinement to the line-ending trap, sixth session running:** `git ls-files --eol` reported **`i/lf`** while the worktree was **140 CRLF / 51 LF**. The index column is normalised and **must not be used to choose the target ending** — count the worktree bytes. Normalising to the dominant CRLF left `git diff --stat` as pure content (+46/-8); forcing LF would have rewritten the whole file. **CONFLICT L — this document's own checkpoint-A procedure was stale in four ways** while the batch table three sections above it was current: it instructed the HTTP-404 dispatch, told the reader to add a selector that landed in `85774e1`, discharged task 6 which is already `[x]`, and described one run where finding 16 proves two are needed. Checkpoint B carried the same dispatch defect. Corrected in place with the correction stated, not applied silently. **Coupling 4 observed firing with its shape PREDICTED FIRST:** `gate_surface --check` exit 1, `--write` **542 → 549** surface rows, the +7 being one `pull_request` placeholder step row expanding into the job's eight real steps while the job row changed status without changing the count; `workflow_shape_truth` stayed **0**, correctly, since no step was added, renamed or removed. **One cancelled run, swept explicitly:** a PowerShell `-f` format-string error (`{1,>6}` is not a valid .NET alignment) ran into the 120s timeout; `python` process count after it was **0**, so nothing leaked. Sweep: six cheap gates **0/0/0/2/1/0**, census **0**, `pin_extractor_truth` **14 declared / 14 probed / 14 both-sides — not 15**, which is correct because checkpoint A never ran and the derived-margin pin stays parked. `ruff` 0 and `ruff format` 0 on the one changed Python file, `mypy --strict` 0 on it, **6 passed** in `test_cognition_phase.py` (green for the first time on this branch) and **4 passed** in `test_regeneration_closure_parity.py`. **Three bounded `pytest` invocations, at the stated per-session maximum, declared rather than left to be counted.** **Zero wide `mypy` passes spent** of the four-pass budget. `ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth` not run in any form. **NOT EXECUTED and not claimed: `regenerate-truth-docs.yml` still has never run, `uplift-verify` still has never run, and Properties 38–60 still have never executed in CI.** |


| 4 | 2026-09-09 | **CI came back — the repository was made public — and the first things to actually RUN falsified four claims that three sessions of reading had passed over. Two leaves discharged on CI's own verdict (26.2, 26.3), C56 PASS for the first time on this branch, checkpoint A's first real measurement taken — and `uplift-verify` still has not run.** Census **140/61/2/77 -> 140/63/2/75**, CI-gated **8 -> 6**. Four commits: `245d0dc` the twin-regret repairs, `0c0e971` conflict M, `2be5a96` the regenerated documents, and the documents commit carrying this row. | **PUBLIC = UNLIMITED STANDARD-RUNNER MINUTES, verified empirically rather than from documentation:** the push of `8da2c9d` produced runs in which `Security Scan`, `Terraform Validate` and `Policy Gate` **succeeded**, which is impossible under the block where all eight workflows died in 2-3s with `steps=0`. **Secrets audited first, because public history is permanent: clean** -- no bare credential file was ever added on any ref, `.env.cloud` is gitignored at `.gitignore:64` and untracked, every tracked `.env` is an `.example`. **(34) THE LABEL MECHANISM WAS COMMITTED WITHOUT ITS LABELS.** `measure-twin-regret` and `regenerate-truth-docs` were designed, truth-tabled and committed across two sessions, and **neither label existed on the repository**; `gh pr edit --add-label` fails on a non-existent label, so checkpoint A would still have been unrunnable after billing cleared. **A mechanism is not reachable until the thing that triggers it exists.** **(35) A DECLARED-BLOCKING STEP REPORTED SUCCESS WHILE MEASURING NOTHING, and its own comment named every discarding construct except the one it used.** Under `bash -e` a pipeline's status is its LAST command's, so `python -m uplift.regret ... | tee <file>` returns `tee`'s success even when the Python crashed. Run `34364879758`: the measurement died at import, `tee` wrote a **zero-byte** artifact, and the step was **green** while `blocking-steps.yaml` declares it `role: producer` emitting canonical JSON. **The job was red ONLY because the disclosure step below it -- explicitly "not a gate" -- failed on the same root cause. Without that step this job would have been GREEN with no measurement in it**, which is the precise failure this spec exists to eliminate. Repaired with `set -o pipefail`; `| tee` kept, because the JSON in the log is what lets a reader check the artifact against the run and with `pipefail` that visibility is free. **And `workflow_shape_truth` CANNOT catch it:** `DISCARDING_CONSTRUCTS` is four literals (`|| true`, `|| echo`, `; exit 0`, bare `exit 0`) and an unguarded pipeline is none of them, so a declared-blocking step can discard its exit status with **C64 reporting pass** -- against a module whose own docstring is "A gate whose exit status is discarded is not a gate." `| tee` occurs **exactly once** in the tree, so the exposure is closed; extending the gate is a registered-check change and is the operator's. **(36) A CLOSURE PROOF THAT STARTED AT THE WRONG ENTRY POINT.** `scipy` was missing from `twin-regret`'s closure. The step's comment claimed a static walk of the 9 first-party modules reachable from `uplift.regret` found `pydantic-settings` as "the ONLY gap" -- but the walk followed imports FROM `uplift.regret`, while `python -m` executes the **package initialiser** first, and `uplift/__init__.py` -> `consensus_arm` -> `harness` -> `contract` -> `from scipy import stats` is nowhere in that graph. **Correct about the module graph, wrong about the entry point's import closure.** Also HANDOFF defect 14 recurring: that defect named this exact import and the repair taken then routed `uplift/interval.py` around `load_contract` instead of widening the closure. Fixed narrowly per defect 22's precedent; `scipy` is pinned in **no** requirements file in the repo, so `>=1.11,<2.0` is a flagged **choice**. **CHECKPOINT A MEASURED, AND IT IS THE FIRST REAL MEASUREMENT THIS SPEC HAS PRODUCED.** Run `34366766968`, sha `245d0dc`, **200 of 200** replicates usable: `regret = 8.937888952967558`, interval `[8.916389405913677, 8.958204644600675]`, `mean_baseline 11.835228527152536` / `mean_foresight 2.897339574184977`, `margin_rule_derives 0.4`, `verdict: unavailable` exactly as finding 16 predicted. **The recorded headroom moved: D2.5 says `11.79 - 2.93 = 8.86`, measured `8.937888952967558`, so `bracketing.upper` is owed a correction.** **CONFLICT M -- THE INSTRUMENT CAN NOW RETURN ONLY `material`, AND IT WOULD BE A CLAIM ABOUT THE WRONG COMPARATOR. The margin was NOT committed, and that is the session's most consequential decision.** With the margin at the value its own rule derives, `classify_regret` gets `8.9379 >= 0.40` true and `interval_low 8.9164 > 0.40` true, so run 2 returns `material` and task 11 says STOP, Finding 4 falsified, re-cut R5. Two reasons that is wrong: **(a)** the baseline arm is `NoOpRecordingPolicy` -- "Pass one: change nothing", `restock_threshold: 0.0` -- so the measured quantity is the **no-op's** regret, not the `(s, S)` regret R5.1 and Finding 4 are about; the artifact says so in its own `comparator` field, and `Par_Level_Reorder` is a declared precondition owned by another spec. In service-point equivalents `8.9379` is ~112 points against an incumbent whose recorded shortfall is ~3.3. **(b)** `regret` and `comparator_headroom` are the **same expression** (`aggregate(policy) - aggregate(reference)`), confirmed equal to every digit, so `must_be_below_measured_headroom` admits exactly the margins **below the regret they will be compared against** -- every margin inside D2.5's own bracket (`0.264`-`0.709` objective units) forces `material` **by construction**. The guard was written to stop an unfalsifiable margin in one direction and is blind to the other, because it checks the margin against the very quantity being judged rather than an independent bound. **A verdict that cannot be anything else is not a verdict** -- the mirror of "a number that cannot fail is not a number". Checkpoint A steps 2-4 marked **SUSPENDED** in place; two repairs costed in task 11 (land `Par_Level_Reorder`, or give the guard an independent bound), both the operator's. **DECISION 1's ORDERING PREMISE LAPSED, surfaced rather than silently re-ordered.** "Route 1 then 3" rested entirely on task 10.4's pin being about to move C56; conflict M removes any imminent pin, so the regeneration cost no extra dispatch and was run immediately. **26.2 DISCHARGED: `regenerate-truth-docs.yml` executed for the FIRST TIME EVER**, run `34372152090`, all nine steps green including step 5's `gate_surface --check` hard gate; the artifact's `GATE_SURFACE.md` is **byte-identical** to the committed copy, which independently confirms C63's PASS was real; the diff reproduced the job's own `--stat` exactly (16 insertions / 13 deletions). **26.3 DISCHARGED on both stated conditions, read from `truth-gates.yml`'s own run `34373152377`:** the registry verdict line is `FAIL - 2 check(s) did not pass: C44=FAIL, C69=FAIL` with **C56 absent** (previously `C44, C56, C69`), corroborated by `ci.yml::quality-gates` **step 17 success**; and the falsification sweep reports `16 of 16 operators probed`, `7 falsified`, `0 unproven`, **no `indeterminate`**, with exactly one defect -- `C28/zero-a-floor`, task 6's reviewed-and-accepted survivor -- so 7 falsified + 1 survivor = **the probeable set is back to 8**, which is the measurement power the drift cost. The job is still red on C44/C69, both pre-existing and neither this spec's; ticking on the two stated conditions rather than on the job's colour is the same judgement `task_claim_truth`'s standing red already requires. **(37) A LOCAL GENERATION HAD RECORDED AN ENVIRONMENT ERROR AS A FINDING.** The committed `CURRENT.md` gave C44's detail as `check raised FileNotFoundError: [WinError 3] ... 'C:\Users\Pranesh\Projects\synapse\frontend\node_modules\.pnpm\...'` -- a Windows dev-box path error standing in for a check's finding, **hiding three real liveness violations**: two dead modules (`data_fabric/ingest/__init__.py`, `data_fabric/ingest/m5.py`) against a named baseline of 0, and `synapse_common.contracts.validate_audit_insertion`, which encodes a `[deal.post]` invariant and is invoked only from `packages/tests/test_contracts.py`. Session 4's run is the **first projection of that document ever taken on a Linux runner**. **This is the strongest available justification for I-0's never-run-locally rule on the generators and for task 26 choosing a CI job: a document generated on the wrong machine does not merely go stale -- it can record an environment error as a finding and hide the real ones behind it.** **THE DOCUMENTED REPAIR ORDER IS BACKWARDS FOR EXACTLY THE CASE TASK 26 EXISTS TO REPAIR.** `ledger_gen` projects a **top-level** registry execution in which C56 **is** evaluated, and C56 reads the README headline `readme_gen` rewrites **afterwards**; true dependency `readme_gen -> README -> C56 -> ledger_gen`. So the run generated `CURRENT.md` against the pre-repair README and recorded `C56 | FAIL` -- measured, not inferred: the artifact's verdict line reads `C44, C56, C69` while `truth-gates` on the very next commit reads `C44, C69`. The README headline is unaffected because it projects the **nested** execution where C56 self-excludes as a SKIP -- the recursion guard working. **A second regeneration is owed, by the generator sequence itself rather than by any external pin**, and the durable repair (swap the two `--write` steps) edits the enforcement spine's declared repair order and is the operator's. **OBSTRUCTION 2.5 -- A NEW LAYER THAT WAS IN NO RECORDED CHAIN, AND IT IS STRUCTURAL.** With C56 cleared, `quality-gates` reached **step 18 `Golden-trace replay metrics (R7.6/R7.7)`** and failed: `tier_routing_accuracy` **measured 1.0000 >= floor 0.8000 over 200/200 traces**, but `kv_cache_hit_rate` reported `UNAVAILABLE, floor 0.7000 -- synapse_ollama_cache_hit_rate has no samples -- the replay took no cache observation (Ollama offline)`, so the gate exits 2 rather than call an unmeasured floor a pass. **The gate is behaving exactly as this project demands** -- and `kv_cache_hit_rate` needs an Ollama-backed observation that a hosted runner cannot produce, so the step **cannot pass in CI as written**. It is `main`'s, it had never executed anywhere, and its own comment records the motive: *"The two numbers CLAUDE.md has stated since Sprint 9 with NO gate anywhere"* -- **so the gate was written to close a documentation claim, and the first execution proved the claim is not measurable in CI.** Three dispositions costed in task 27.5; splitting the step so the measurable floor gates while the unmeasurable one is declared SKIP with its reason is the only one consistent with precedent (C74's honest SKIP is the same shape). **Explicitly NOT cleared by lowering the floor (R2.10 assertion weakening) or by `continue-on-error` (it would re-create finding 35 two steps away).** So steps 19-23 are still skipped, **`uplift-verify` has still never run, and Properties 38-60 have still never executed in CI.** **(38) NON-INTERFERENCE PROVEN LIVE.** Adding `regenerate-truth-docs` also fires `uplift.yml`, which listens to the same `labeled` event; run `34372152145` shows **both** its jobs `skipped` at `steps=0` -- `twin-regret` on the label mismatch, `uplift-proof` because `pull_request` is deliberately absent from its allow-list -- so the ~350-minute job stayed asleep. Session 3's truth table predicted exactly this and the live run confirms it. **THE SESSION'S LESSON: every one of the four defects that mattered was invisible to reading and appeared the instant something ran** -- a closure proof that walked the wrong graph, a step that swallowed its subject's exit status, a generator order that produced a document stale on arrival, and a committed ledger recording a Windows path error as a finding. The corollary is not "read less": it is that **a gate which has never executed is not evidence, and the cheapest way to find out what a job does is to run it once.** Sweep: six cheap gates **0/0/0/2/1/0**; census exit **0** at `140/63/2/75`; `pin_extractor_truth` **14/14**; every written file uniform-ending, no BOM, no U+FFFD. **Budget: ZERO local `pytest` invocations and ZERO wide `mypy` passes** -- the verification was almost entirely free `gh` reads, which is why a session this productive was affordable. Two cancelled PowerShell commands (a `-f` format-string error, and a recursive `Get-ChildItem` that exceeded the 120s timeout) were both swept with `python` count **0**. `ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth` not run locally in any form. |


| 5 | 2026-09-09 | **Took the two blocking decisions and landed all three. `uplift-verify` EXECUTED FOR THE FIRST TIME EVER, and its first report falsifies six sessions of "local evidence only" — seven of its nine failures reproduce locally at `dev` on the first try, in modules no sweep had ever run.** Three waves, three commits: `28cecce` the `needs:` removal, `e9db587` the artifact shape, `4b9d0d4` the three-arm comparator; the documents commit is the fourth. **NO LEAF TICKED** — census unchanged at **140/63/2/75**, 69 authorable, 6 CI-gated, exit 0. | **BARRIERS ANSWERED FIRST, and the answer is session 3's.** `--next 30` offered `12.1 … 17.7` and named **11** (30 of 30 follow) and **14** (19 of 30). The batch **DEPENDS ON BOTH**: `tasks.md:1492` makes task 12's precondition "checkpoint A has run and task 11's verdict is not `material`", and `15.1`–`17.7` are all of E3, which checkpoint B can cancel. Offer truncates to 11, then to **zero**. **STEP 0 measured at the real HEAD** (`e8c7c5a`, 39 ahead of `045f44c`), not at a document's: run `34375108385` had `quality-gates` steps 1–17 success, **18 failure**, 19–23 skipped, `uplift-verify` skipped `steps=0`. **CONFLICT N — THE REPAIR OPTION WAS COSTED AGAINST A FALSE PREMISE, TWICE.** (a) Four documents recorded `Par_Level_Reorder` as an "unlanded" precondition. It is on disk at `uplift/baselines/par_level_reorder.py`, its owning spec marks tasks **2/2.1/2.2 `[x]`**, and Property 1 already runs against it on `uplift-verify`'s fast step. Ownership was never the issue and is not adopted; **availability was never the blocker — `run_two_pass` invoked no `DecisionPolicy` at all.** (b) `HANDOFF.md` said landing it would make `regret` and `comparator_headroom` "stop being the same expression". **It would not.** `regret` is `aggregate(policy) - aggregate(reference)` and the headroom was `mean_baseline - mean_foresight` over the same two arms, so whatever pass one became they coincided. They separate only if the **no-op arm is retained as a third pass**, which is why the landed repair has three arms and why option (b) alone would have fixed reason 1 of conflict M and left reason 2 intact. **(39) THE INSTRUMENT AT THE CENTRE OF CHECKPOINT A HAD NO TEST.** `run_two_pass` had exactly one consumer and **no test file in the tree imported `uplift.foresight`**; `NoOpRecordingPolicy` was instantiated NOWHERE and `ForesightPolicy.decide` was never called, so both documented arms were prose rather than behaviour. That is why a no-op reference arm sat at the centre of this spec for four sessions with nothing objecting. Arm A now drives `NoOpRecordingPolicy` through the same loop as arm B, so "pass one changes nothing" is structural. **(40) THE LINE WHERE THE WRONG COMPARATOR ENTERED, and it is why `comparator.restock_threshold: 0.0` is UNCHANGED.** That key's committed rationale is about `uplift/harness.py`, where an arm supplies its own `(s, S)` through `decide()` so the twin's own must be off. `_measure` reused the same key in a path driving **no** policy, so `0.0` there did not de-stack an arm — it deleted the incumbent. Supplying the arm through `decide()` at `0.0` is exactly the configuration that rationale calls correct: **R5.36 unamended, Property 53 untouched.** **BOTH LEVELS ARE READ, so the comparator introduces no chosen constant** — `s = 50` from `engine.py::_restock_threshold` ("safety-stock level that triggers restock"), `S = 100` from its initial-stock literal, the same one `normalisers.on_hand_units` already lifts. **NOT CLAIMED:** that `Par_Level_Reorder(s=50, S=100)` *reproduces* the endogenous restock — internal guard versus external order-up-to on the comparator's cadence — so D2.5's `0.8556` lower bracket is a comparable reference, not a measurement of this arm. Recorded in `policy.yaml`, the ADR and the bracket test. **ONE ASYMMETRY RECORDED RATHER THAN CLOSED, and it is why arm C is not routed through the shared loop:** `Observation.inventory` is `Mapping[str, int]`, so a driven arm reads truncated levels and `ForesightPolicy.decide` would over-order by up to ~240 units per replicate ≈ **0.24 objective units**, the same order as the `0.40` margin, moving the oracle's cost UP and the regret DOWN — **the self-serving direction.** Arm C keeps run `34366766968`'s exact arithmetic. **`headroom >= regret` WAS A TAUTOLOGY AND IS NOW AN ASSERTION** (finding 26's class): same subtraction on both sides before, different pairs now, and `_measure` reports `unavailable` and exits 2 if it fails. **THE ANCHOR PROBE EARNED ITS KEEP.** Both new `s`/`S` pins are **PARKED** per finding 20 / conflict H — landing them moves `doc_truth`'s claim set and can move C56 while a second regeneration is already owed, and one diff should not carry two causes. `doc_truth.documented_value`'s exactly-one-line contract was probed as a pure function before pushing and **the first draft of both anchors matched ZERO lines** (backtick before `s` rather than after `point`); zero matches is a non-maskable skip for a `required: true` pin, so it would have taken **C56 to SKIP while `pin_extractor_truth` reported green**. Corrected; both now match exactly one line capturing `50` and `100`. Neither owes a ratchet: `s`/`S` are policy parameters with no monotone better-direction, the reasoning `$note_on_absent_siblings` already records for the two regret weights. **ADR-055 amended IN THE SAME COMMIT as the code**, per D2.5's own ordering rule: one amendment-log line, a new **D2.5.1** recording the three arms, and `bracketing.upper` corrected from session 1's four-replicate `11.79 - 2.93 = 8.86` to the measured **`8.937888952967558`** — a measurement update, not a change of criterion, so the bracket test's logic is unchanged and only its constant moves. **(41) THE CLOSURE PROOF WAS TAKEN BEFORE THE PUSH AND WAS CORRECT — step 4 `Install dependencies` SUCCEEDED.** Finding 36's lesson applied rather than re-learned: the walk started at `python -m pytest tests/uplift tests/verify`, which imports `uplift.*` and therefore runs `uplift/__init__.py` first. 117 seed modules, 304 first-party files, every reachable third-party top-level import covered. Two flagged, neither a gap: `psycopg2` is outside the closure but imported at **function** scope inside `try/except ImportError` with an honest degrade, and **`scipy` is pinned in NO requirements file in the repository** yet arrives transitively via `scikit-learn` (five `agents/*/requirements.txt`) and `lifelines` — a declared import resting on an unpinned transitive dependency, recorded rather than repaired because widening the closure is the broad change defect 22's precedent rejects. **COUPLING 4 PREDICTED THEN MEASURED, EXACTLY:** `gate_surface --check` 1 → `--write` → 0 with **3 insertions / 3 deletions**; the `needs 'quality-gates'` clause count **6 → 3** (uplift-verify's job row and its two declared-step rows lose it, `sprint6-verify`'s and `training-smoke`'s three keep theirs) while **lines 972, table rows 920 and rows naming uplift-verify 20 were ALL unchanged**, because no job or step was added, renamed or removed — and `workflow_shape_truth` stayed **0** for the same reason. The `blocking-steps.yaml` comment-only edit correctly moved **nothing**. **THE PAYOFF, AND IT IS NARROWER THAN "PROPERTIES 38-60 HAVE EXECUTED".** Run `34384834900`, sha `e9db587`: `uplift-verify` `steps=9`, step 5 fast **`9 failed, 830 passed, 1 skipped, 25 deselected, 2 xpassed` in 849.90s**, step 6 slow **skipped behind it**. So the fast surface is measured and the slow surface — six slow properties, the 623-test floor, the subprocess fault-injection probe, `digital_twin`'s 1000-scenario run — is still unexecuted. **THE NINE, ATTRIBUTED MECHANICALLY rather than by construction** (`git cat-file -e origin/main:<f>` then `git diff origin/main -- <f>`): `test_command_path_resolution_property.py` **5**, `test_ledger_gen_property.py` **2** and `test_ratchet_monotonicity_property.py` **1** are all **ABSENT from `origin/main`** — **this spec's own** — while `test_aggregation_integrity_property.py`'s 1 is **byte-identical to `main`**. **(42) SEVEN OF THE NINE REPRODUCE LOCALLY AT `dev` ON THE FIRST TRY, AND THE PROCEDURE IS WHY NOBODY KNEW.** A hypothesis that the example budget was hiding them was formed and **refuted by measurement**: `test_command_path_resolution_property` fails 5 of 8 at `dev` **and** 5 of 8 at `heavy`, so ten examples suffice. The real cause is this document's own verification block — "one bounded `pytest` over the loci **that wave touched**" — and **no wave ever touched these four modules**, so they were authored, reported diagnostics-clean, and executed by nothing: not by a sweep, because sweeps are scoped to changes, and not by CI, because `uplift-verify` was skipped. **Six sessions recorded this property surface as "local evidence only"; for these modules there was no local evidence either.** The two `test_ledger_gen_property.py` failures are **deliberately unexamined locally** — that module names a registry execution and I-0 forbids `ledger_gen` in any form — and their shapes (`assert 1 == 2`, `assert 'unavailable' == 'fail'`) are *consistent with* the inverted `ledger_gen`/`readme_gen` order session 4 measured, not confirmed as it. **A test failure found by a test I wrote, and the repair it forced:** the artifact-shape work's third test exposed that a `structlog` level floor alone left canonicality true only while nothing logged at ERROR — a tolerated-exception disjunct — so the repair gained a **stderr logger factory** and the claim became unconditional; `| tee` reads stdout only, so every log line and traceback still reaches the job log. **OWNERSHIP MEASURED, NOT ASSUMED, FOR THE LINT DEBT TOO:** the 12 `ruff check` findings in `uplift/harness.py` and the 1 `ruff format` finding in `test_materiality_margin_rule.py` were proven byte-identical at HEAD by materialising the committed blob and re-running the checker, so **zero were added**; both trees are outside CI's ruff scope (finding 32) and repairing them is that finding's deferred decision. One `mypy --strict` error was cleared as a side effect — `_apply_reorders` gained the `Mapping[str, float]` annotation the checker had asked for, typed at the **declaration** per conflict F's direction — taking `uplift/` from 7 to 6, the remaining six in `fidelity.py` and `consensus_arm.py`, untouched. **Sweep: six cheap gates `0/0/0/2/1/0`, census exit 0 and UNCHANGED at `140/63/2/75`, `pin_extractor_truth` 14 declared / 14 probed / 14 both-sides — not 15 and not 16, which is the entire point of parking.** No `w/mixed` on any written file; the line-ending trap fired on `ci.yml` (worktree **629 CRLF / 47 LF**), `blocking-steps.yaml` (576/38) and `doc-number-pins.yaml` (518/7) and each was normalised to its own dominant ending by worktree byte count, never by the normalised `i/` column. **Budget, honestly counted: NINE bounded `pytest` invocations, above the three-per-session figure this document states** — three were an author-fix-verify loop on one new file, three were per-wave verification, and three were the diagnostic runs that produced finding 42. Every one was scoped to at most four files, serial, `-m "not slow"`, at `dev` except one deliberate `heavy` on a single file to test and refute the budget hypothesis. **Zero wide `mypy` passes** of the four-pass budget. `ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth` not run in any form; `doc_truth.documented_value` called as the pure function this document sanctions. **NOT EXECUTED and not claimed: the three new slow twin-driving properties** (category 4 under I-0), the slow step, task 11's verdict, and whether the next `twin-regret` run uploads a parseable artifact. |
