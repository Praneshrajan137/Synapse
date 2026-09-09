# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **3** (2026-09-09).

**This prompt no longer states a HEAD, and that is a repair rather than an omission.** Conflicts J and
K were the same defect in three consecutive sessions: the prompt is written *before* the commit that
carries it, so any sha it names is stale by at least one commit **by construction**, and two sessions
wasted effort reconciling it. Derive it instead — the first three commands of STEP 0 do exactly that.

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`.

**Your session cap is THIRTY leaf tasks, in three waves of about ten. It is a ceiling and it is
expected never to bind.** Do not pad a session to reach it. What will stop you is a barrier or a
phase boundary — and STEP 0 has stopped the last two sessions before either.

### STEP 0 — FIRST, AND IT HAS ENDED THE LAST TWO SESSIONS: can CI run at all?

**At handoff it could not, for the second session running.** Sha `fe8ddeb`, run `34319298166`
(`SYNAPSE CI`): three jobs `failure` in 2–3 seconds with **`steps=0`**, three `skipped`, and the
annotation

```
The job was not started because recent account payments have failed or your spending
limit needs to be increased. Please check the 'Billing & plans' section in your settings
```

**All eight workflows on that sha were identical.** Nothing ran, so none of it is evidence about the
code.

```powershell
git rev-parse --short HEAD                       # derive HEAD; never trust a document for it
git log -1 --format='%s'
git rev-list --count origin/main..HEAD
gh run list --branch feat/decision-quality-proof --limit 12 --json databaseId,headSha,workflowName,conclusion
gh api "repos/:owner/:repo/actions/runs/<id>/jobs"   # steps=0 across the board IS the billing block
gh run view <id>                                     # read the ANNOTATIONS block
```

**Check the run for the sha `git rev-parse` just gave you, not the one a document names.** Session 3's
entire STEP 0 verdict cost four `gh` reads, which are free under I-0.

**Why this ends the session rather than inconveniencing it.** Checkpoint A (tasks 10.4, 11) runs by
labelling PR #84, which needs a runner. Task 11 gates 12; 12.x gates 13.x; 13.7 makes checkpoint B
reachable; B gates all of E3; Phase 3 gates Phase 4; C gates E5. **Session 3 re-derived this from the
census rather than accepting it: zero of the 69 authorable leaves escape checkpoint A.** And
`unavailable` is the state task 11 is in — "**Not a verdict**… I-7 forbids reading absence as either a
pass or a null."

**If CI is still blocked, read this before offering anything: THE BARRIER-INDEPENDENT FALLBACK IS
SPENT.** Session 3 executed all of it on the operator's word — route 1 for C56 (`bbe4278`), the
adopted `test_cognition_phase` repair (`bf8693f`), and the ruff-scope measurement. **What remains is
one costed operator decision and nothing else:**

- **Widening CI's ruff scope.** Measured: **530 lint findings** and **254 files `ruff format` would
  rewrite** across nine trees CI never reads, including `uplift/` and `digital_twin/`. **Recommend
  against it while `uplift-verify` is the goal:** `Ruff lint` is step **5** of `quality-gates`,
  *earlier* than the step 8 session 2r cleared, so widening re-closes the gate at an earlier point
  than the one just opened. `HANDOFF.md` finding 32 has the per-tree table.
- **Nothing else.** Do not invent work. **A session that cannot verify anything should not write
  anything it will have to claim.** Report the block, name the one decision, and stop.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence. Nothing below
   may be used to justify heating the laptop.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the thirty-task ceiling, wave
   discipline, the **barrier stop**, the three marks, the four checkpoints, the batch table, the six
   cheap gates, and the progress ledger. **Read the last two rows (`2r`, `3`) in full** — findings
   24–33 live there. **Its checkpoint-A procedure was corrected in session 3 (conflict L); the
   corrected version is the one to follow.**
3. `HANDOFF.md` (repo root) — the state of the tree, and **what is verified versus what is merely
   authored**. It opens with the CI block. Read that first.
4. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
5. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
6. `.cursorrules` + `docs/cursor/*.md`.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.5 and the amendment log.** Needed the moment
   checkpoint A unblocks.
8. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
   and your worklist**.

**Two invariant numberings disagree between authorities.** `references/14_invariants.md` and
`.cursorrules` differ on I-6, I-8 and I-10. Authority 5 outranks authority 6. The invariants this work
cites — I-1, I-4, I-5, I-7 — agree in both.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict
rather than resolving it silently.** Twelve have been surfaced (A–L). **Four of them are corrections
to instructions a session was itself given, and three of those four landed in session 3.** Expect
more, and expect them in the procedure you are about to follow.

### STEP 2 — derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At handoff: **140 leaf tasks — 61 done, 2 authored-pending-discharge, 77 open** (69 authorable, 8
CI-gated). `--files` reports open tasks whose named artifacts already exist; read its `prior-art`
lines before authoring.

`--next 30` offers `12.1 … 17.7` and prints two barriers, **11** (30 of 30 offered follow) and **14**
(19 of 30 follow). **Session 3's answer, which you should re-derive rather than copy: the batch
DEPENDS ON BOTH.** Task 12's own precondition is "checkpoint A has run and task 11's verdict is not
`material`"; `15.1`–`17.7` are the whole of E3, which checkpoint B can cancel outright. So the offer
truncates to **11** (12.1–13.7), and with task 11 unmeasurable it truncates to **zero**.

**For every barrier line, state in your opening whether the batch depends on it. An unanswered
barrier is a stop, not a warning.** The census is authoritative for counts; `SESSION_PROTOCOL.md`'s
table is authoritative for order. If they disagree, surface it — do not pick.

### STEP 3 — how a thirty-task session is actually run

**Three waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit. Never carry two waves in one commit.
2. **Write findings into `tasks.md` and the ledger as you find them**, not at the end.
3. **Delegate reading, never execution.** I-0 permits **unlimited** parallel sub-agents for reading,
   writing and analysis, and **exactly ONE** that executes code. Keep every command in the main
   agent.
4. **Re-read the authority file for each wave's area before starting that wave.** If you notice
   yourself reasoning about a file you have not opened this session, stop and open it.

**The compute budget does NOT scale with the ceiling.** Four wide `mypy --strict orchestrator/` passes
per session. **One bounded `pytest` per wave, serial, at most three per session** — session 3 spent
exactly three and declared it. `SESSION_PROTOCOL.md` records that this is an *interpretation* of
I-0's "one scoped test run" as a bound on scope rather than a session quota, and names the one-line
amendment if the operator would rather make it explicit. **I-0 outranks the protocol, so treat that as
flagged, not settled.**

### STEP 4 — the work order, and it branches

**If CI is blocked: STEP 0 governs, and the fallback is spent. Stop there.**

**If CI is restored, the order is fixed and checkpoint A comes first — it is the operator's.** The
full corrected procedure is in `SESSION_PROTOCOL.md`'s checkpoint-A section. In brief:

1. **Run 1, by LABEL.** Add `measure-twin-regret` to PR #84, then remove it. Read `regret`,
   `interval_low`/`interval_high`, `comparator_headroom`, `margin_rule`, `margin_rule_derives`,
   `margin_rule_below_headroom` and `interval_excludes_rule_margin` from
   `artifacts/uplift/twin-regret.json`. **Expect `verdict: unavailable`** — finding 16, not a fault.
2. **One ADR-055 D2.5 amendment covering BOTH owed amendments**, one commit, one amendment-log line.
   State the derived value as a literal on **exactly one line** in the `derives` form the parked pin's
   anchor requires, and correct `bracketing.upper` if the measured headroom moved from
   `11.79 - 2.93 = 8.86`. D2.5's own rule puts the amendment **before** the run judged against it.
3. **Commit `materiality_margin.value`** (`5.0 * 0.01 * 8.0` = `0.40`) and **graduate the parked pin**
   from `pending_pins:` into `pins:`. Read finding 20 first; do **not** author a fresh pin. No second
   `ratchets.json` entry is owed. Discharges **10.4**.
   - **PROBE THE DOCUMENT-ANCHOR SIDE BEFORE PUSHING. No cheap gate covers it.**
     `pin_extractor_truth` probes source extractors *"unconditionally, independent of whether the
     document anchor matched"* and will report **15/15 green** on a dead anchor; `doc_truth` is the
     gate that would catch it and I-0 forbids running it locally. `doc_truth.documented_value(pin,
     text)` is a pure function and the contract is **exactly one** matching line. A mismatch takes
     C56 from FAIL to **SKIP** via R1.4/R1.6's non-maskable rule, moving registry counts immediately
     before the regeneration.
4. **Label a second time.** Finding 16, not optional: run 1 cannot exercise
   `must_be_below_measured_headroom`, because `materiality_margin` returns `None` at
   `committed is None` before reaching that guard. Run 2 is a **verdict materialisation, not a
   re-measurement** — seeds are fixed and the interval seed is committed, so there is no
   metric-shopping surface. Discharges **11**.
5. **Read task 11's verdict** against `SESSION_PROTOCOL.md`'s four-value table, then branch:
   `material` → **STOP**, Finding 4 falsified, re-cut R5 (R5.3, R5.4), report it plainly as a success
   of the method. `inconclusive` → **session 2 is authorable: 12.1–12.4, 13.1–13.7, eleven tasks, and
   it must stay eleven** because checkpoint B sits behind 13.7 and can cancel E3 outright.
   `sub-margin` → confirms Finding 4, unreachable today by construction. `unavailable` → the
   measurement did not happen; say so and proceed on nothing.
6. **Then, and only then, task 26.2 — by LABEL, not by dispatch.** Add `regenerate-truth-docs` to
   PR #84, then remove it. Route 1 landed in `bbe4278`; the `gh workflow run` instruction that used to
   sit in task 26.2 returns **HTTP 404** and has been corrected. Sequenced **after** the margin commit
   per the operator's "route 1 then 3", so one regeneration suffices. Then **26.3 confirms TWO
   things**: C56 goes PASS, **and** the falsification sweep's probeable set returns to **8**.

#### FORBIDDEN REPAIRS. Each one names what it would destroy.

No error may be cleared by **giving an argument a default**, by **widening a type to `Any`**, by
**adding a `# type: ignore`**, or by **narrowing a checker's scope**. The first substitutes an
unreviewed value for a committed one; the second and third make the checker agree by asking it less;
the fourth deletes the gate. **If an error is genuinely a tooling artifact, repair the *declaration
that misleads the checker*, never the call sites that report it** — tasks 27.1 and 27.2 are the worked
examples.

#### Determine ownership mechanically, and `git log -1` is NOT enough

```powershell
git cat-file -e origin/main:<file>              # exit 0 => the file exists on main
git diff origin/main -- <file>                  # attribute the LINE, not the file
git log -1 --format='%h' -- <file>              # LAST TOUCH, not authorship
git merge-base --is-ancestor <sha> origin/main  # exit 1 => NOT on main => this branch's
git show origin/main:<file> > scratch           # then EXECUTE main's version if it matters
```

Three findings have been misfiled. Session 3's ownership check on `test_cognition_phase.py` used
`cat-file -e` plus `diff origin/main` and **never called `git log -1`**, precisely because that is
what misled session 2r on the same file.

---

## STOP CONDITIONS

- **Stop at STEP 0 if CI cannot run.** The fallback is spent; one costed decision remains.
- **Stop at any barrier the census names that the batch depends on.** Say which.
- **Stop and report if a task's count does not move as predicted.** State the delta **per code** and
  what you checked. Session 2q's gate predicted `78 → 57` and measured **56**; proceeding was correct
  *because the shape of the deviation was proven*.
- **Do not tick 10.4, 11, 14, 21, 22.3, 25, 26.2, 26.3 or 27.5.** All CI-gated, all blocked.
- **Do not change `main`.**
- **Do not run `ledger_gen` or `readme_gen`** locally, in `--check` or `--write` form, for any reason.
- **Do not pad a session toward thirty.** The ceiling is a limit, never a target.
- Surface every new conflict rather than resolving it silently.

---

## THE THING THAT IS BLOCKING EVERYTHING

**`uplift-verify` has still never run, so Properties 38–60 have never executed in CI.** The chain,
with session 3's movement:

| # | Obstruction | State |
|---|---|---|
| 0 | **the runner itself** — account billing | **BLOCKED; nothing starts** |
| 1 | step 8 `mypy --strict orchestrator/ --exclude orchestrator/tests` | **CLEARED** (2r) |
| 2 | step 17 **C56**, claim `doc-truth/headline-counts` | red, and red on `main`. **Mechanism unblocked** (`bbe4278`); drift not repaired |
| 3 | step 19 `test_cognition_phase::test_run_consensus_streams_correlated_phases` | **REPAIRED ON DISK** (`bf8693f`), 6 passed locally. **Not discharged** |
| 4 | steps 20–22 coverage floors, spec coverage, contract tests | **never executed** here or on `main` |

**The transferable lesson, and session 3 sharpened it:** clearing a gate reveals what it was
shielding, **and unblocking a gate's mechanism is not running it.** Session 3 moved two obstructions
and discharged nothing. **No single clearance licenses a claim about the job at the end of the chain.**

---

## HARD-WON LESSONS. Thirty-three findings and twelve conflicts, each one paid for.

### The six habits that caught the most

1. **Verify at the boundary you are claiming, not at a proxy for it.** Conflict I: three authority
   files said a baseline was measured "at CI's exact command"; no workflow runs that command. One free
   `gh` read of the log of the step being claimed is the cheapest high-yield check in this repo.
2. **Read the procedure against the tree, not against its own table of contents.** Conflict L: the
   batch table said "reachable by labelling", and the procedure three sections below it still
   instructed the HTTP-404 dispatch, told the reader to re-author a landed change, and discharged a
   task already `[x]`. **A table and its procedure can disagree, and the table is the one people
   update.**
3. **Reproducibility is not relevance.** The 56-error figure reproduced to the error, per code, first
   try — and described a command no gate runs.
4. **Prove the SHAPE of a deviation, not just its size.** Session 3 predicted the gate-surface delta
   (`542 → 549`, +7 from one placeholder step row expanding into eight) *before* running `--write`,
   and stated the mechanism. A number that lands where you predicted for the reason you predicted is
   worth far more than one that merely lands.
5. **Never generalise one proof to a population.** One of 40 format errors was proven a line-ending
   artifact and that proof was extended to all 40. **Three were real.** This is why session 3 reported
   its 254 format findings as an **upper bound** and refused to call them defects.
6. **Read what got SKIPPED behind a failure, not only what failed.** `gh api .../jobs` and list every
   step whose conclusion is `skipped`. One 101-character line once gated 18 steps and 3 jobs.

### On assertions and gates that cannot fail

- **An assertion that cannot fail is not an assertion**, and this now has two independent proofs.
  `comparison-overlap` caught two (finding 26). And **session 3 nearly created a third in its own
  repair**: filtering a call list to one topic and asserting the remainder is a subset of a declared
  set is **vacuous** when the remainder is empty (`set() <= anything`). Non-emptiness must be asserted
  too. **Check whether your new assertion has a satisfiable falsifying case.**
- **Repair a stale assertion by PARTITIONING, not by FILTERING.** The filter makes the test pass and
  silently discards what the assertion was protecting. Session 3's `test_cognition_phase` repair
  partitions the calls and asserts the partition **exhaustive**, so a rogue topic is still a failure —
  and derives the permitted set from the emitting module's own declarations, so a legitimate new
  channel does not break it.
- **A test can assert nothing at all.** `test_protocol.py::test_tier1_skips_debate` builds a
  classification, installs it, and contains only comments describing what it would verify.
- **An optional-evidence escape in a decision function is a hole, not a default.** Grep for
  `X is None or`, `if not Y: pass`, `getattr(o, 'f', True)` in anything returning a verdict. Fix it at
  the **production boundary**, not by loosening the classifier.
- **A pin that cannot fail is not a pin.** Finding 20's pin could have stood with `required: false`.
  Rejected. **Parking a correct pin is honest; landing a toothless one is not.**
- **Never weaken a generator or an assertion to make a property pass** (R2.10). Fix the subject — or,
  if the *precondition* was wrong, fix the precondition **and say which**. Both of the last two
  sessions' test repairs were precondition corrections, and both said so.

### On gates reporting the wrong thing

- **The gate that fails is not always the gate that would tell you.** Finding 20: a pin with a dead
  document anchor makes `doc_truth` report a **`skip`** — **C56 SKIP, not FAIL** — while
  `pin_extractor_truth` reports **15/15 green**, because it probes source extractors
  *"unconditionally, independent of whether the document anchor matched."*
- **A verdict is a claim about its own derivation.** A PowerShell splatting bug made
  `workflow_shape_truth` exit 2 when it is 0; a stale mypy incremental cache kept reporting three
  cleared errors (`--no-incremental` after any config change); `$LASTEXITCODE` read `-1` for a census
  run whose own report said `exit 0`.
- **An "unparsable" rendering can be the honest answer.** Finding 30: `gate_surface` cannot parse
  `contains(...labels.*.name, 'x')` and renders `CONDITIONAL | unparsable if:`. It looks like a defect
  the change introduced; the identical rendering already sits in the **C63-green** surface for
  `twin-regret`, and `CONDITIONAL` is the conservative classification. **Check the precedent beside
  your row before treating your row as broken.**
- **A SKIP is not milder than a FAIL for measurement.** The falsification sweep reports
  `indeterminate` for any gate that does not PASS on its unmutated baseline, so **doc drift costs
  measurement power** — C56's drift made the sweep probe **7** checks, not 8.
- **`getDiagnostics` returning nothing is inconclusive, not evidence** (R2.13). **A local red is not
  always a CI red, and a local green is not a CI green.**
- **`heavy` fails what `dev` passes. Twice.** Re-verify anything load-bearing at `heavy` on one scoped
  file — **and say so when `heavy` is a no-op.**

### On scope, ownership and adoption

- **CI's scope is not the tree's scope, and the gap is now measured.** `ruff check`/`format` cover
  `packages/synapse_common/ agents/ orchestrator/` **only**, and `[tool.ruff]` declares no
  include/exclude — so `scripts/`, `tests/`, `packages/tests/`, `api/`, `data_fabric/`,
  `ml_pipelines/`, **`uplift/` and `digital_twin/`** are never linted or format-checked by CI: **530
  lint findings, 254 format findings** (finding 32). `mypy --strict` step 8 excludes
  `orchestrator/tests`, and step 9 (`agents/`) is `continue-on-error: true`. **Know which files a gate
  actually reads before believing a count about them.**
- **A `warn`-level finding co-reported beside a failure did not cause the failure.**
- **Do not adopt another owner's debt unilaterally** — but record the diagnosis so it is not
  re-derived. Parent 27 and `test_cognition_phase` were both adopted by *explicit* operator decision,
  one session apart. Precedent for refusal is task 6's disposition of `C28/zero-a-floor`.

### On install closures and CI mechanics

- **Read the install closure before trusting that a job can run its own subject. Twice.** Defect 14
  (`scipy`) and defect 22 (`pydantic-settings`, absent from `twin-regret`'s closure, which would have
  raised `ModuleNotFoundError` inside the job that exists to run the measurement). Both found by
  reading.
- **Fix a closure narrowly. The broad fix is the dangerous one.** Widening
  `packages/requirements.txt` can turn a SKIP into a PASS and **move the registry counts `doc_truth`
  pins.**
- **`workflow_dispatch` requires the workflow on the default branch; `pull_request` does not.** Finding
  23, and it now applies to two workflows. A PR runs the workflow as defined in its own head.
- **When you add a trigger, the GUARD is the load-bearing half.** A deny-list guard
  (`event_name != 'workflow_dispatch'`) is **fail-OPEN** against a new trigger. Use an allow-list
  naming its events, and **verify it by truth table over every event × input × label combination** —
  reading caught none of the three defects that method found. Session 3's table also proved
  **non-interference**: two label mechanisms in one repo must not fire each other's jobs.
- **A workflow that has never executed is the I-7 shape**, and *reachable* is not *run*. Task 26.1
  is `[~]` for exactly that reason, and route 1 did not change it.

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open — not started. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

- **The `[~]` mark earned its existence.** Tasks 1.2/1.5 were reconciled from `[x]`; then a
  claimed-green repair was **not** green, three times running.
- **A `[~]` graduates on the job's own verdict, never on a local run.**
- **Leave a half-landed task `[ ]`, not `[~]`, when the owed half is authoring blocked on another
  task.** Precedent: task 15.2. Session 3 left **27.5 `[ ]`** and **26.2 `[ ]`** on the same rule,
  despite moving both forward.
- **"Authored and diagnostics-clean, not executed" is a legitimate result.** "Should pass" reported as
  "passes" is an I-7 violation.
- **Disk outranks the ledger.** **`tasks.meta.json` is not authority.**

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what throttle it.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
  `pnpm` anything. **`regenerate-truth-docs.yml` is the sanctioned route for the middle two, and it
  is now reachable by label.**
- **Cheap and encouraged:** file reads, `grep`, `get_diagnostics`; `ruff`/`mypy` on changed files; one
  bounded `pytest` per wave; `spec_ledger_census`; the **six** cheap gates (`workflow_shape_truth`,
  `pin_extractor_truth`, `sweep_budget_truth`, `dataset_licence_truth`, `task_claim_truth`,
  `gate_surface`); the `biome`/`tsc` binaries on changed files; and **`gh` API reads — free, and the
  highest-yield evidence in this repo. Spend them first.**
- **`mypy --strict orchestrator/` is category 2. Four passes per session**, serial, each captured to a
  file. **`--no-incremental` after any config change.**
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
  **unlimited.** Sub-agents that execute code: **exactly ONE at a time.**
- **Preferred flags:** `-x -q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
- **Sweep before finishing**, and **after any cancelled or timed-out command** — a cancelled agent
  does not clean up after itself. Session 3 hit a 120s timeout and checked: `python` count **0**.
  One `node` is Kiro's own ACP server; `chrome` processes predating your first command are the
  operator's browser.

### Verification sweep

**Per wave** — only what that wave touched:

```powershell
python -m ruff check <wave's changed files>
python -m ruff format --check <wave's changed files>
python -m mypy --strict <wave's changed python files>
git ls-files --eol <wave's changed files>          # w/mixed after ANY programmatic edit
$env:HYPOTHESIS_PROFILE='dev'
python -m pytest <wave's touched loci> -q --tb=line -p no:randomly -m "not slow"
```

Then **commit the wave** and write its findings into `tasks.md`.

**Before closing:**

```powershell
python -m scripts.audit.workflow_shape_truth              # C64   expect 0
python -m scripts.audit.pin_extractor_truth --check       # C75   expect 0
python -m scripts.audit.sweep_budget_truth --check        # C73   expect 0
python -m scripts.audit.dataset_licence_truth --check     # C74   expect 2 = honest SKIP
python -m scripts.audit.task_claim_truth --check          # expect 1 = pre-existing, other spec
python -m scripts.audit.gate_surface --check              # C63   expect 0
python -m scripts.audit.spec_ledger_census --files --check # expect 0
```

Expected: **`0 / 0 / 0 / 2 / 1 / 0`** plus census 0. **`pin_extractor_truth` must report 14 declared,
not 15** — 15 means the parked derived-margin pin was moved into `pins:` before checkpoint A, and C56
will go SKIP.

Reproduce CI's exact commands when claiming a CI step will pass:

```powershell
python -m ruff check packages/synapse_common/ agents/ orchestrator/ --output-format=github
python -m ruff format --check packages/synapse_common/ agents/ orchestrator/
python -m mypy --strict packages/synapse_common/
python -m mypy --strict orchestrator/ --exclude orchestrator/tests   # CI's ACTUAL step 8
```

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **A `ruff format --check` diff whose two sides look character-identical is a LINE-ENDING diff.** Hit
  in **six** sessions running. `git ls-files --eol <path>` reports **`w/mixed`**. Repair with Python at
  `newline=''`, normalising to the file's *dominant* ending — **count the WORKTREE bytes first.**
  **NEW (finding 33): the `i/…` index column does NOT describe the worktree.** It read `i/lf` on a
  file whose worktree was 140 CRLF / 51 LF; normalising to LF on that evidence would have rewritten
  the whole file instead of leaving a 46-line diff.
- **NEW: PowerShell's `-f` operator rejects `{1,>6}`** — `>` is not a .NET alignment character. It
  throws per call while the surrounding loop keeps going, so it presents as a hang, not an error.
  Write anything with formatting or per-item aggregation as a temp `.py`.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental`.
- **`git log -1 -- <file>` is last-touch, not authorship.** Prefer `git cat-file -e origin/main:<file>`
  then `git diff origin/main -- <file>`, and execute `main`'s version when it matters.
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** `Get-Content -Raw` decodes
  with the ANSI codepage and `Set-Content -Encoding utf8` adds a **BOM** Python's
  `read_text(encoding='utf-8')` does not strip. `Get-Content` also *displays* em dashes as mojibake
  while the file is clean — **verify bytes, never the console**:
  ```powershell
  $b=[System.IO.File]::ReadAllBytes($f); $t=[System.IO.File]::ReadAllText($f)
  "BOM=$($b[0] -eq 239 -and $b[1] -eq 187 -and $b[2] -eq 191)  U+FFFD=$($t.Contains([char]0xFFFD))"
  ```
- **PowerShell mangles em dashes and box-drawing characters**, so `Select-String` on a CI step name
  containing one finds nothing and looks like a clean run. Match an ASCII substring; read exit codes.
- **`$LASTEXITCODE` is unreliable after a native command is piped through `Select-String`.** Re-run
  with `*> $null` to read it.
- **PowerShell strips double quotes inside single-quoted `--jq`.** Capture `gh api` into a variable and
  use `ConvertFrom-Json`. `>` writes **UTF-16**; there are **no heredocs** — write commit messages to a
  temp file and use `git commit -F`.
- **Complex inline `python -c` breaks on quoting.** Write a temp `.py`, run it, delete it.
- **`git status` over-reports on this tree.** Trust `git diff`, and stage precisely.
- **`git add` refuses an ignored path SILENTLY.** `git check-ignore -v <paths>` first (exit 1 = not
  ignored).
- **Identify a CI run by `head_sha` and `head_commit.message`, NEVER by timestamp.** The documented
  local skew is ~2h45m, and one run's `created_at` was **seven days** off while its sha and message
  matched exactly.
- Suppress twin logging in any engine-driving probe or the output floods:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))`.
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks **seven** pre-existing
  errors under `uplift/` that block commits to files which do not contain them. Note the consequence
  (finding 32): the ruff hook in that config is also the only thing that would lint the trees CI
  never reads, so **the two mitigations are mutually exclusive today.**
- Python 3.14.0, **mypy 1.19.1** locally against CI's unpinned `mypy>=1.10.0,<2.0`, pytest 8.4.2,
  hypothesis 6.151.11, jsonschema 4.26.0. `gymnasium` absent. `frontend/node_modules` installed.
  `gh` 2.82.0, authenticated.

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). A hardcoded value overrides the profile in
  **both** directions. **Do not assert a total** (CF-13).
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`; its fast step
  collects only `tests/uplift tests/verify`. **A slow-marked test outside those four paths is selected
  by no job at all**, and one that must run in `quality-gates` must **not** be slow-marked.
- **Assert a clause unconditionally** rather than wrapping it in a tolerated-exception disjunct. "Or
  it raises" is a weak property. **Prove a refusal path by construction.**
- **Derive numbers; flag the irreducible choice.** A knob with a self-serving sign gets a
  `ratchets.json` direction; one without gets none, and inventing one is fabrication.
- Type hints everywhere (`mypy --strict`); Pydantic v2 `ConfigDict(frozen=True)` for recorded facts;
  `structlog`, never `print()`, in library code; canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`; `encoding='utf-8'` on **every**
  `read_text` (E-S13-07); ASCII-only console output; lines ≤ 100 characters.
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, or any paid SDK.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS.
  Absence of proof is never a pass.

### The five same-commit couplings

1. A rename and its declaration.
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the job
   is genuinely eligible.** `ineligibleEntry.reason` is a closed six-value enum with no
   "dispatch-only" **or "label-conditioned"** member, so a label- or dispatch-conditioned job owes
   **none** (conflict G, extended in session 3).
3. A schema change and every fixture that carries it.
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** **Missed twice** (tasks 5.6 and 10.3): four
   registered gates from one missed `--write`. **Check it rather than assume it** — 2q watched it fire
   (17→18 files, 370→378 steps), 2r-pre-c watched it fire (536→542 rows), session 3 watched it fire
   (**542→549**, shape predicted first), and 2r-pre-b watched it *not* fire on a `run:`-only edit to a
   non-anchor step. **A trigger-only change with no new step still fires it**, because the job's
   per-context row changes and its placeholder step row expands.
5. The session ceiling lives in **one** place, `spec_ledger_census.DEFAULT_BATCH`. When it moves, the
   code and the four documents that name it move in the same commit.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** One commit **per wave**. A
  workflow change and its `gate_surface --write` share a commit; documents describing two work
  streams go **last**, so no message misdescribes its own diff.
- Prefer new commits over `--amend`. No force-push, no `--no-verify`, no interactive flags. Leave git
  config unchanged. **Push to the PR #84 branch, never to `main`.**

---

## What this spec is actually for — hold this while you work

SYNAPSE claims multi-agent AI makes better supply-chain decisions than a simpler system. That claim is
currently untestable — not because the answer is bad, but because nothing in the project can yet
produce an answer that would mean anything. The thesis:

> Make the instruments provably able to fail, make the simulated world one where intelligence can pay,
> prove the measuring device can detect an effect, and only then measure — on non-synthetic data,
> against a published external benchmark.

**Two checkpoints can end this project early, on purpose.** Checkpoint A's task 11 can falsify
Finding 4 and re-cut R5. Checkpoint B's task 14 can prove consensus unnecessary and cancel E3
outright. Both run *before* the work they gate — **and that is why the barrier stop is derived by the
census instead of trusted to a reader.**

**The pre-commitment, binding before the number is known:** if measured uplift is null or negative,
**it is reported as null or negative.** The floor stays at `0.0`, no headline is published as a gain,
and the result is written up as a finding — not reframed, not re-run at a different replicate count
until it moves, not held back pending a "better" configuration. A null from a **validated** instrument
on a **decision-relevant** world is worth more than the tautological PASS it replaces: before this
spec, C60 could only ever report SKIP, and a measured zero against a `0.0` floor exited 2. **A number
that cannot fail is not a number** — and the last two sessions each found an *assertion* in that
condition, one of them in a repair being written at the time.

Three guards on reading the result: a null while any objective KPI is recorded not observably
sensitive is **inconclusive**, not confirmation (task 10.5). No headline may be published while no
Power_Report describes the harness revision under measurement (task 17.3). And **a `material` verdict
on a point estimate with no dispersion is not a falsification either** — the instrument now refuses to
produce one, and finding 16 is what ensures the verdict recorded is the one it produced.

---

## Session 3 handoff — regenerate this section each session

**Two commits plus the documents commit. No task ticked, and none attempted.**

| Commit | Subject |
|---|---|
| `bbe4278` | the regeneration becomes reachable by label, and fails closed (route 1 + coupling 4) |
| `bf8693f` | `test_cognition_phase`'s precondition corrected, not its standard (adopted debt) |
| *(third)* | the documents: this prompt, `HANDOFF.md`, the ledger row, two `tasks.md` bodies, conflict L's repair |

**What was earned.** Nothing was discharged, because nothing could be. Obstruction 2's **mechanism**
is unblocked and obstruction 3 is **repaired on disk**; both are one runner away from mattering and
neither is a pass.

**What was prevented.** Authoring E2c against an unmeasured checkpoint A — which the census proved
would have been authoring behind two barriers the batch depends on. And a vacuous assertion in this
session's own repair.

**What is blocked, and it is the operator's.** Billing. Then checkpoint A, then the regeneration, then
`main`'s never-executed steps 20–22.

**Census at close: 140 leaf, 61 done, 2 authored-pending-discharge, 77 open** (69 authorable, 8
CI-gated) — **unchanged**. The two `[~]` are **10.4** (checkpoint A) and **26.1** (the regeneration
job, still never executed).

**Verified at close:** six cheap gates **0/0/0/2/1/0**; `pin_extractor_truth` **14/14, not 15**;
census **0**; `gate_surface` **542 → 549** with the shape predicted before it was measured;
`workflow_shape_truth` **0**; the guard truth table over three conditioned jobs, proving
non-interference; ruff **0/0** and `mypy --strict` **0** on the one changed Python file; **6 passed**
in `test_cognition_phase.py` and **4 passed** in `test_regeneration_closure_parity.py`; every written
file byte-verified, no BOM, no U+FFFD, no `w/mixed`; process sweep clean (`python` 0).

**NOT verified, and must not be claimed:** `uplift-verify`, and therefore **Properties 38–60**;
`regenerate-truth-docs.yml`, still never executed; `quality-gates` steps 18–23; the
`test_cognition_phase` repair **in CI**; the document-anchor side of the parked pin; whether any of
the 254 `ruff format` findings are real rather than line-ending artifacts;
`ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth`, not run locally in any form.
