# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **2r** (2026-09-09). HEAD **`3b2ec15`**, tree clean, branch **31
commits ahead of `main`**, PR **#84** open.

**This session introduces the thirty-task regime.** The cap moved from ten to thirty, in three waves
of about ten, and the reasoning is in `SESSION_PROTOCOL.md` under "Why the cap moved from ten". The
short version: the ten-cap bound **zero** of eight observed sessions, so it was not protecting
anything — it was splitting coherent phases through their own same-commit couplings. Thirty is a
ceiling expected never to bind; **barriers and phase boundaries are what stop a session now.**

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`. HEAD at handoff is **`3b2ec15`**, tree clean, **31 commits ahead of `main`**.

**Your session cap is THIRTY leaf tasks, in three waves of about ten. It is a ceiling and it is
expected never to bind.** Do not pad a session to reach it. What will stop you is a barrier or a
phase boundary, and STEP 0 may stop you before either.

### STEP 0 — FIRST, AND IT MAY END THE SESSION: can CI run at all?

**At handoff, it could not.** Run `34315612360` started **no jobs**:

```
The job was not started because recent account payments have failed or your spending
limit needs to be increased. Please check the 'Billing & plans' section in your settings
```

Three jobs failed in 3–4 seconds with **zero steps recorded**; three more were skipped. That run is
not evidence about the code — nothing in it ran.

```powershell
gh run list --branch feat/decision-quality-proof --workflow 'SYNAPSE CI' --limit 3 --json databaseId,headSha,status,conclusion
gh run view <id>          # read the ANNOTATIONS block, not just the job list
```

**Why this ends the session rather than inconveniencing it.** Checkpoint A (tasks 10.4, 11) runs by
labelling PR #84, which needs a runner. Task 11 gates task 12; 12.x gates 13.x; 13.7 makes checkpoint
B reachable; B gates all of E3; Phase 3 gates Phase 4; checkpoint C gates E5. **Traced through, zero
of the 69 authorable leaves escape checkpoint A.** And `unavailable` is the state task 11 is in —
`SESSION_PROTOCOL.md`'s verdict table calls it "**Not a verdict**… I-7 forbids reading absence as
either a pass or a null", and its instruction is to "proceed on nothing."

So if CI is still blocked:

1. **Do not author speculatively.** Authoring E2c or E3 against an unmeasured checkpoint A is
   precisely the defect the checkpoints were re-cut to prevent: *a gate that fires after the work it
   guards is not a gate.*
2. **Report it, and offer the one barrier-independent fallback** — the `main`-owned debt recorded in
   `HANDOFF.md`'s decision 2 (`test_cognition_phase`'s failing assertion) and session 2r's finding
   that **`scripts/` and `tests/` are outside CI's ruff scope**, so the audit gates' own source is
   never linted. Both are real, both are diagnosed, neither crosses a barrier. **Both need the
   operator's word first**, because parent 27 was adopted by explicit decision and a further
   adoption is not a session's to make unilaterally (precedent: `C28/zero-a-floor`).
3. **Stop.** A session that cannot verify anything should not write anything it will have to claim.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**, the local compute budget. Highest
   precedence. Nothing below may be used to justify heating the laptop.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the **thirty-task ceiling**, the wave
   discipline, the **barrier stop**, the three marks, the four checkpoints, the re-cut batch table,
   the six cheap gates, the per-wave and closing sweeps, and the progress ledger. **Read the last
   two ledger rows (`2r-pre-c`, `2r`) in full** — findings 20–29 live there.
3. `HANDOFF.md` (repo root) — the state of the tree, and **what is verified versus what is merely
   authored**. It opens with the CI block and two operator decisions. Read those first.
4. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
5. `.claude/skills/synapse-engineer/SKILL.md` + `references/` (`14_invariants.md`,
   `testing_topology.md`, `spec_schema.md`, `adr_index.md`).
6. `.cursorrules` + `docs/cursor/*.md` — code conventions, agent pattern, domain models.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.5 and the amendment log.** Needed the moment
   checkpoint A unblocks.
8. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
   and your worklist**.

**Two invariant numberings disagree between authorities.** `references/14_invariants.md` and
`.cursorrules` differ on I-6, I-8 and I-10. Authority 5 outranks authority 6. The invariants this
work cites — I-1, I-4, I-5, I-7 — agree in both.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict
rather than resolving it silently.** Ten have been surfaced (Conflicts A–J in `HANDOFF.md`), three of
them corrections to instructions a session was itself given. Expect more.

### STEP 2 — derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

That command **is** the census: leaf total, the three mark buckets, the CI-gated set derived from
`discharge:` lines, the next authorable batch in ledger order, and **every barrier that batch steps
over**. At handoff it reported **140 leaf tasks: 61 done, 2 authored-pending-discharge, 77 open** (69
authorable, 8 CI-gated). `--files` reports open tasks whose named artifacts already exist — read its
`prior-art` lines before authoring.

**New in session 2r, and it is the mechanism that makes thirty safe.** `--next 30` prints:

```
[!!] barrier : 11 is CI-gated and 30 of the 30 offered id(s) follow it in ledger order
               -> uplift.yml::twin-regret (checkpoint A). Ledger order is not execution
               order: confirm the batch does not DEPEND on it.
[!!] barrier : 14 is CI-gated and 19 of the 30 offered id(s) follow it in ledger order
               -> uplift.yml, task 13.7's E2c measurement steps (checkpoint B).
```

**For every barrier line, state in your opening whether the batch depends on it. An unanswered
barrier is a stop, not a warning.** It is advisory and never truncates on purpose: ledger order is
not execution order, and session 2r's own batch (27.2–27.5) legitimately sat after task 11 without
depending on it. The judgement is yours; the disclosure is not optional.

**The census is authoritative for counts; `SESSION_PROTOCOL.md`'s table is authoritative for order.**
If they disagree, surface it — do not pick.

### STEP 3 — how a thirty-task session is actually run

**Three waves of about ten, each `read → author → verify → commit`.** The count is not what protects
quality; these four things are.

1. **Commit every wave.** The commit is the bisect unit. A thirty-task session in one commit is a
   thirty-task bisect when verification goes red, and that debugging cost is superlinear. Never carry
   two waves in one commit.
2. **Write findings into `tasks.md` as you find them**, not at the end. Session 2r produced six
   findings from four tasks; a thirty-task session that holds findings in context will write them
   from memory, which is how a finding becomes an approximation.
3. **Delegate reading, never execution.** I-0 permits **unlimited** parallel sub-agents for reading,
   writing and analysis, and **exactly ONE** that executes code. Dispatch `context-gatherer`
   sub-agents per area in parallel; keep every command in the main agent. This is how thirty tasks
   stay inside I-0 rather than around it.
4. **Re-read the authority file for each wave's area before starting that wave.** The silent failure
   mode is skipping exactly this step and inferring from surrounding code instead. If you notice
   yourself reasoning about a file you have not opened this session, stop and open it.

**The compute budget does NOT scale with the ceiling.** Still four wide `mypy --strict orchestrator/`
passes per session. One bounded `pytest` invocation **per wave**, serial, never concurrent — at most
three. `SESSION_PROTOCOL.md` records that this is an *interpretation* of I-0's "one scoped test run"
as a bound on scope rather than a session quota, and names the one-line amendment if the operator
would rather make it explicit. **I-0 outranks the protocol, so treat that as flagged, not settled.**

### STEP 4 — the work order, and it branches

**If CI is blocked: STEP 0 governs. Stop there.**

**If CI is restored, the order is fixed and checkpoint A comes first — it is the operator's.**

1. **Checkpoint A, run by LABEL not by dispatch.** Add `measure-twin-regret` to PR #84, then remove
   it. `workflow_dispatch` cannot reach a workflow absent from `main`; `pull_request` can — finding
   23, already repaired in `e8e9528`. Read `regret`, `interval_low`/`interval_high`,
   `comparator_headroom`, `margin_rule`, `margin_rule_derives`, `margin_rule_below_headroom` and
   `interval_excludes_rule_margin` from `artifacts/uplift/twin-regret.json`.
2. **One ADR-055 D2.5 amendment covering BOTH owed amendments**, one commit, one amendment-log line.
   State the derived value as a literal on **exactly one line** — that is what the parked pin anchors
   to (finding 20) — and correct `bracketing.upper` if the measured headroom moved from
   `11.79 - 2.93 = 8.86`. D2.5's own rule puts the amendment **before** the run judged against it.
3. **Commit `materiality_margin.value`** (`5.0 * 0.01 * 8.0` = `0.40`) and **graduate the parked
   pin** from `pending_pins:` into `pins:`. Read finding 20 first; do **not** author a fresh pin. No
   second `ratchets.json` entry is owed. Discharges **10.4**.
4. **Label a second time.** Finding 16, not optional: run 1 cannot exercise
   `must_be_below_measured_headroom` and reports `verdict: unavailable`. Discharges **11**.
5. **Read task 11's verdict** against `SESSION_PROTOCOL.md`'s four-value table, then branch:
   `material` → **STOP**, Finding 4 falsified, re-cut R5 (R5.3, R5.4), report it plainly as a success
   of the method. `inconclusive` → **session 2 is authorable: 12.1–12.4, 13.1–13.7, eleven tasks,
   and it must stay eleven** because checkpoint B sits behind 13.7 and can cancel E3 outright.
   `sub-margin` → confirms Finding 4, unreachable today by construction. `unavailable` → the
   measurement did not happen; say so and proceed on nothing.
6. **In parallel, and unblocked by A: C56.** `quality-gates` now fails at **step 17**, one claim,
   `doc-truth/headline-counts` — README `PASS 51 / FAIL 3 / SKIP 10 / TOTAL 64` against the suite's
   `54 / 2 / 11 / 67`. That is **task 26's drift**, and **task 26.2 now blocks task 27.5**.
   `HANDOFF.md`'s decision 1 costs three routes. **Never repair those four numbers by hand** —
   `blocking-steps.yaml` forbids it in those words.

#### FORBIDDEN REPAIRS. Each one names what it would destroy.

No error may be cleared by **giving an argument a default**, by **widening a type to `Any`**, by
**adding a `# type: ignore`**, or by **narrowing a checker's scope**. The first substitutes an
unreviewed value for a committed one; the second and third make the checker agree by asking it less;
the fourth deletes the gate. **If an error is genuinely a tooling artifact, repair the *declaration
that misleads the checker*, never the call sites that report it** — tasks 27.1 and 27.2 are the two
worked examples, and `HANDOFF.md`'s conflict F records why the instructed call-site repair would have
put 21 unreviewed numbers onto the I-5 confidence gate.

#### Determine ownership mechanically, and `git log -1` is NOT enough

```powershell
git log -1 --format='%h' -- <file>              # LAST TOUCH, not authorship
git merge-base --is-ancestor <sha> origin/main  # exit 1 => NOT on main => this branch's
git diff origin/main -- <file>                  # if the file exists on BOTH, attribute the LINE
git show origin/main:<file> > scratch           # then EXECUTE main's version if it matters
gh run list --branch main --workflow '<name>' --limit 3
```

Three findings have now been misfiled. Two were filed as `main`'s and were this branch's; session
2r's finding 24 went the other way — filed as this branch's, and mostly `main`'s. `git log -1` on
`test_cognition_phase.py` resolved to this branch's `e000258` and was **wrong**: the file exists on
`main`, the failing assertion is unchanged from `main`, and running `main`'s version fails too.

---

## STOP CONDITIONS

- **Stop at STEP 0 if CI cannot run.** Nothing in this spec is authorable without checkpoint A.
- **Stop at any barrier the census names that the batch depends on.** Say which.
- **Stop and report if a task's count does not move as predicted.** State the delta **per code** and
  what you checked. Session 2q's gate predicted `78 → 57` and measured **56**; proceeding was correct
  *because the shape of the deviation was proven*, not because the number was close.
- **Do not tick 10.4, 11, 14, 21, 22.3, 25, 26.2, 26.3 or 27.5.** All CI-gated, all blocked.
- **Do not change `main`.**
- **Do not run `ledger_gen` or `readme_gen`** locally, in `--check` or `--write` form, for any reason.
- **Do not pad a session toward thirty.** The ceiling is a limit, never a target.
- Surface every new conflict rather than resolving it silently.

---

## THE THING THAT IS BLOCKING EVERYTHING

**`uplift-verify` has still never run, so Properties 38–60 have never executed in CI.** Session 2r
cleared the first obstruction and found three more behind it. The chain, measured:

| # | Obstruction | State |
|---|---|---|
| 0 | **the runner itself** — account billing | **BLOCKED; nothing runs** |
| 1 | step 8 `mypy --strict orchestrator/ --exclude orchestrator/tests` | **CLEARED** (56 → 0; CI step 8 success) |
| 2 | step 17 **C56**, claim `doc-truth/headline-counts` | red — **and red on `main` too** |
| 3 | step 19 unit tests → `test_cognition_phase.py::test_run_consensus_streams_correlated_phases` | fails; **proven pre-existing on `main`** |
| 4 | steps 20–22 coverage floors, spec coverage, contract tests | **never executed on this branch or `main`** |

**`main`'s own last three CI runs fail `quality-gates` at the same step 17 claim**, with its
unit-test step skipped behind it, and `045f44c` — this branch's fork point — is one of them. So
obstructions 2–4 are **default-branch debt this spec did not create.**

**The transferable lesson, and it is the strongest one from session 2r:** clearing a gate reveals what
it was shielding, and **the depth of the chain is unknown until each layer clears.** No single
clearance licenses a claim about the job at the end of it. Step 8 was hiding fifteen steps.

---

## HARD-WON LESSONS. Twenty-nine findings, each one paid for.

### The five habits that caught the most

1. **Verify at the boundary you are claiming, not at a proxy for it.** Session 2r's Conflict I: three
   authority files said a baseline was measured "at CI's exact command"; the command they named had
   no `--exclude` and **no workflow runs it**. CI's own step-8 log said **3 errors**, not 56. One free
   `gh` read of the log of the step being claimed is the cheapest high-yield check in this repo.
2. **Reproducibility is not relevance.** The 56-error figure reproduced to the error, per code, first
   try — and described a command no gate runs. A number can be perfectly reproducible and still wrong
   about what it means.
3. **Prove the SHAPE of a deviation, not just its size.** 2q's stated revert gate was `78 → 57` and
   the measurement was 56. Proceeding was right because exactly two codes moved, both to zero, every
   other count was identical, no new code appeared, and the 22nd error's mechanism was read from
   source. Mechanical literalism would have discarded a correct repair.
4. **Never generalise one proof to a population.** One of 40 local format errors was proven a
   line-ending artifact and that proof was extended to all 40. **Three were real.** If a claim covers
   N things, prove it over N or find the arithmetic that does.
5. **Read what got SKIPPED behind a failure, not only what failed.** `gh api .../jobs` and list every
   step whose conclusion is `skipped`. One 101-character line once gated 18 steps and 3 jobs across
   two pushes with nothing recording it.

### On assertions and gates that cannot fail

- **An assertion that cannot fail is not an assertion**, and `comparison-overlap` finds them.
  Session 2r's finding 26 caught two, plus a `union-attr` third: a distinctness assertion placed
  *after* two equality assertions had narrowed both operands to distinct `Literal`s, and an FSM
  assertion mypy could prove **false** because the preceding assertion narrowed the member expression
  and mypy does not discard that across a mutating call. Repair by binding each observation to a
  fresh local where it is observed. **The same narrowing mechanism explains four unused ignores —
  one mechanism, two opposite symptoms.**
- **A test can assert nothing at all.** `test_protocol.py::test_tier1_skips_debate` builds a
  classification, installs it, and contains only comments describing what it would verify.
- **An optional-evidence escape in a decision function is a hole, not a default.** `classify_regret`
  read `regret >= margin and (interval is None or excludes_margin)` — an absent interval was a
  **satisfied** precondition, so a bare point estimate could have falsified Finding 4. **Grep for
  that shape** (`X is None or`, `if not Y: pass`, `getattr(o, 'f', True)`) in anything returning a
  verdict. Fix it at the **production boundary**, not by loosening the classifier.
- **A pin that cannot fail is not a pin.** Finding 20's pin could have stood with `required: false`
  and would not have touched C56. Rejected: downgrading a claim to make it safe is the
  assertion-weakening R2.10 forbids. **Parking a correct pin is honest; landing a toothless one is
  not.**
- **Never weaken a generator or an assertion to make a property pass** (R2.10). Fix the subject — or,
  if the *precondition* was wrong, fix the precondition **and say which**. `test_cognition_phase`'s
  repair is a precondition correction: the test assumed the protocol's producer served one topic, and
  ADR-038 made that false.

### On gates reporting the wrong thing

- **The gate that fails is not always the gate that would tell you.** Finding 20: a pin with a dead
  document anchor makes `doc_truth` report a **`skip`**, which R1.4/R1.6 turn into an `unavailable`
  aggregate — **C56 SKIP, not FAIL** — while `pin_extractor_truth` reports **15/15 green**, because it
  probes source extractors *"unconditionally, independent of whether the document anchor matched."*
- **A verdict is a claim about its own derivation.** Three instances now: a PowerShell splatting bug
  made `workflow_shape_truth` exit 2 when it is 0; **a stale mypy incremental cache kept reporting
  three cleared errors**, because a cache entry keys to the *importing* module while
  `ignore_missing_imports` belongs to the *imported* one (`--no-incremental` after any config
  change); and `$LASTEXITCODE` read `-1` for a census run whose own report said `exit 0`.
- **A SKIP is not milder than a FAIL for measurement.** The falsification sweep reports
  `indeterminate` for any gate that does not PASS on its unmutated baseline, so **doc drift costs
  measurement power, not just a red tick** — C56's drift made the sweep probe **7** checks, not 8.
- **`getDiagnostics` returning nothing is inconclusive, not evidence** (R2.13). **A local red is not
  always a CI red, and a local green is not a CI green.**
- **`heavy` fails what `dev` passes. Twice.** `HYPOTHESIS_PROFILE=dev` draws **10** examples.
  Re-verify anything load-bearing at `heavy` on one scoped file — **and say so when `heavy` is a
  no-op**, as it is for a test using no Hypothesis.

### On scope, ownership and adoption

- **CI's scope is not the tree's scope.** `ruff check`/`format` cover
  `packages/synapse_common/ agents/ orchestrator/` only, so **`scripts/` and `tests/` are never
  linted or format-checked by CI** — the audit gates' own source included. `mypy --strict` step 8
  excludes `orchestrator/tests`, and step 9 (`agents/`) is `continue-on-error: true`. **Know which
  files a gate actually reads before believing a count about them.**
- **A `warn`-level finding co-reported beside a failure did not cause the failure.** Check configured
  severity before attributing a red.
- **Do not adopt another owner's debt unilaterally.** Parent 27 was adopted by *explicit* operator
  decision. Precedent for the refusal is task 6's disposition of `C28/zero-a-floor`. Diagnose it,
  hand it over, and record the diagnosis so it is not re-derived.

### On install closures and CI mechanics

- **Read the install closure before trusting that a job can run its own subject. Twice.** Defect 14:
  `uplift/contract.py` imports `scipy`, absent from `twin-regret`'s closure. Defect 22: the same job
  could not import the **twin**, because `pydantic-settings` is in every `agents/*/requirements.txt`
  and in neither `packages/requirements.txt` nor `packages/pyproject.toml`. Both found by reading.
- **Fix a closure narrowly. The broad fix is the dangerous one.** Adding a package to
  `packages/requirements.txt` widens the closure `truth-gates`, `quality-gates` and the regeneration
  job run in, and several registered checks report SKIP when an optional import is missing — so it can
  turn a SKIP into a PASS and **move the registry counts `doc_truth` pins**.
- **`workflow_dispatch` requires the workflow on the default branch; `pull_request` does not.**
  Finding 23. A PR runs the workflow as defined in its own head.
- **A workflow that has never executed is the I-7 shape.** `regenerate-truth-docs.yml` is authored,
  parses, resolves its declarations, carries no discarding construct — and proves nothing. Task 26.1
  is `[~]` for exactly that reason.

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open — not started. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

- **The `[~]` mark earned its existence.** Tasks 1.2/1.5 were reconciled from `[x]` because nothing
  had judged them; then a claimed-green repair was **not** green, three times running. An `[x]` at
  authoring time would have hidden two successive failed repairs.
- **A `[~]` graduates on the job's own verdict, never on a local run.** Task 27.1 became `[x]` in
  session 2r because `ci.yml::quality-gates` step 8 reported **success** on run `33588706405`.
- **Leave a half-landed task `[ ]`, not `[~]`, when the owed half is authoring blocked on another
  task.** A `discharge:` line naming a job would be false. Precedent: task 15.2.
- **"Authored and diagnostics-clean, not executed" is a legitimate result.** "Should pass" reported
  as "passes" is an I-7 violation.
- **Disk outranks the ledger.** Session 1 opened with eight tasks implemented and unticked.
- **`tasks.meta.json` is not authority** — its `executionHistory` bulk-stamped every task within an
  eleven-second window.

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what throttle
it — not task count, which is why the thirty-task ceiling does not change this section.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
  `pnpm` anything. **`regenerate-truth-docs.yml` is the sanctioned route for the middle two.**
- **Cheap and encouraged:** file reads, `grep`, `get_diagnostics`; `ruff`/`mypy` on changed files;
  one bounded `pytest` per wave; `spec_ledger_census`; the **six** cheap gates
  (`workflow_shape_truth`, `pin_extractor_truth`, `sweep_budget_truth`, `dataset_licence_truth`,
  `task_claim_truth`, `gate_surface`); the `biome`/`tsc` binaries on changed files; and **`gh` API
  reads — free, and the highest-yield evidence in this repo. Spend them first.**
- **`mypy --strict orchestrator/` is category 2. Four passes per session, and this does NOT scale
  with the ceiling.** Serial, never concurrent, each captured to a file so the per-code decomposition
  needs no re-run. **Use `--no-incremental` after any config change.**
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
  **unlimited — use them, a thirty-task session depends on it.** Sub-agents that execute code:
  **exactly ONE at a time.**
- **Preferred flags:** `-x -q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
- **Sweep before finishing.** List background processes; confirm none survived; check for orphaned
  `python` / `node` / `chrome` explicitly. One `node` is Kiro's own ACP server.

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
python -m scripts.audit.pin_extractor_truth --check       # C75   expect 0 and 14/14
python -m scripts.audit.sweep_budget_truth --check        # C73   expect 0
python -m scripts.audit.dataset_licence_truth --check     # C74   expect 2 = honest SKIP
python -m scripts.audit.task_claim_truth --check          # expect 1 = pre-existing, other spec
python -m scripts.audit.gate_surface --check              # C63   expect 0
python -m scripts.audit.spec_ledger_census --files --check # expect 0
```

Expected: **`0 / 0 / 0 / 2 / 1 / 0`** plus census 0. **`pin_extractor_truth` must report 14 declared,
not 15** — 15 means the parked derived-margin pin was moved into `pins:` and C56 will go SKIP.

Reproduce CI's exact commands when claiming a CI step will pass:

```powershell
python -m ruff check packages/synapse_common/ agents/ orchestrator/ --output-format=github
python -m ruff format --check packages/synapse_common/ agents/ orchestrator/
python -m mypy --strict packages/synapse_common/
python -m mypy --strict orchestrator/ --exclude orchestrator/tests   # CI's ACTUAL step 8
```

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **A `ruff format --check` diff whose two sides look character-identical is a LINE-ENDING diff.**
  Hit in **five** sessions running; in 2r it fired on **all eleven** edited files at once.
  `git ls-files --eol <path>` reports **`w/mixed`**. Repair with Python at `newline=''`, normalising
  to the file's *dominant* ending — **count first**: `pyproject.toml` was 231 CRLF / 25 LF,
  `test_hash_chain.py` 286 / 3, and `test_confidence_gate_universality_property.py` is **pure LF and
  must stay LF**. The editor tool preserves endings **inconsistently**, so the check cannot be
  skipped because the previous file was fine.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental`.
- **`git log -1 -- <file>` is last-touch, not authorship.** If the file exists on `main` too, diff the
  line and, when it matters, execute `main`'s version from a scratch path.
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
- **PowerShell strips double quotes inside single-quoted `--jq`.** Capture `gh api` into a variable
  and use `ConvertFrom-Json`. `>` writes **UTF-16**; there are **no heredocs** — write commit messages
  to a temp file and use `git commit -F`.
- **Complex inline `python -c` breaks on quoting.** Write a temp `.py`, run it, delete it.
- **`git status` over-reports on this tree.** Trust `git diff`, and stage precisely.
- **`git add` refuses an ignored path SILENTLY.** `git check-ignore -v <paths>` first (exit 1 = not
  ignored).
- **Identify a CI run by `head_sha` and `head_commit.message`, NEVER by timestamp.** The documented
  local skew is ~2h45m, and session 2r saw a run whose `created_at` was **seven days** off while its
  sha and message matched this tree exactly.
- Suppress twin logging in any engine-driving probe or the output floods:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))`.
- `types-PyYAML` is now moot for `orchestrator/` (session 2r declared `yaml.*` and `psycopg2.*`
  stub-free in `pyproject.toml`), but **do not run `pre-commit install`** — it installs the stubs and
  unmasks **seven** pre-existing errors under `uplift/` that block commits to files which do not
  contain them.
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
  collects only `tests/uplift tests/verify`. **A slow-marked test outside those four paths is
  selected by no job at all**, and one that must run in `quality-gates` must **not** be slow-marked.
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

### The four same-commit couplings

1. A rename and its declaration.
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the job
   is genuinely eligible.** `ineligibleEntry.reason` is a closed six-value enum with no
   "dispatch-only" member, so a `workflow_dispatch`-only job owes **none** (conflict G).
3. A schema change and every fixture that carries it.
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** **Missed twice** (tasks 5.6 and 10.3): it cost
   C63 and cascaded into `ledger_gen`, `doc_truth`'s pinned counts and the README headline — four
   registered gates from one missed `--write`. **Check it rather than assume it**: 2q watched it fire
   (17→18 files, 370→378 steps), 2r-pre-c watched it fire again (536→542 rows), and 2r-pre-b watched
   it *not* fire on a `run:`-only edit to a non-anchor step.

**A fifth, new in session 2r:** the session ceiling lives in **one** place,
`spec_ledger_census.DEFAULT_BATCH`. When it moves, the code and the four documents that name it move
in the same commit. It is not a registered check, so no registry count moves — verified before it was
changed.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** One commit **per wave**. A
  workflow change and its `gate_surface --write` share a commit; documents describing two work
  streams go **last**, so no message misdescribes its own diff.
- Prefer new commits over `--amend`. No force-push, no `--no-verify`, no interactive flags. Leave git
  config unchanged. **Push to the PR #84 branch, never to `main`.**

---

## What this spec is actually for — hold this while you work

SYNAPSE claims multi-agent AI makes better supply-chain decisions than a simpler system. That claim
is currently untestable — not because the answer is bad, but because nothing in the project can yet
produce an answer that would mean anything. The thesis:

> Make the instruments provably able to fail, make the simulated world one where intelligence can
> pay, prove the measuring device can detect an effect, and only then measure — on non-synthetic
> data, against a published external benchmark.

**Two checkpoints can end this project early, on purpose.** Checkpoint A's task 11 can falsify
Finding 4 and re-cut R5. Checkpoint B's task 14 can prove consensus unnecessary and cancel E3
outright. Both run *before* the work they gate. Most plans cannot reach a conclusion that invalidates
themselves — **and that is exactly why the barrier stop is now derived by the census instead of
trusted to a reader.**

**The pre-commitment, binding before the number is known:** if measured uplift is null or negative,
**it is reported as null or negative.** The floor stays at `0.0`, no headline is published as a gain,
and the result is written up as a finding — not reframed, not re-run at a different replicate count
until it moves, not held back pending a "better" configuration. A null from a **validated**
instrument on a **decision-relevant** world is worth more than the tautological PASS it replaces:
before this spec, C60 could only ever report SKIP, and a measured zero against a `0.0` floor exited 2.
**A number that cannot fail is not a number** — and session 2r found three *assertions* in exactly
that condition.

Three guards on reading the result: a null while any objective KPI is recorded not observably
sensitive is **inconclusive**, not confirmation (task 10.5). No headline may be published while no
Power_Report describes the harness revision under measurement (task 17.3). And **a `material` verdict
on a point estimate with no dispersion is not a falsification either** — the instrument now refuses
to produce one, and finding 16 is what ensures the verdict recorded is the one it produced.

---

## Session 2r handoff — regenerate this section each session

**Four commits, branch 31 ahead of `main`, HEAD `3b2ec15`, tree clean.**

| Commit | Subject |
|---|---|
| `b7954b6` | `yaml.*`/`psycopg2.*` declared stub-free — the 3 errors that were the entire gate |
| `743ca6b` | the wide mypy surface 56 → 0, per error, no ignore added |
| `bfad6a0` | 27.1–27.4 ticked; conflicts I and J; findings 24–28 |
| `3b2ec15` | the account-level CI block |

**What was earned.** Tasks **27.1** (discharged by CI's own step-8 success), **27.2**, **27.3**,
**27.4** are `[x]`. `mypy --strict orchestrator/` **56 → 0**; CI step 8 **passes for the first time
on this branch**. Census `140/57/3/80 → 140/61/2/77`.

**What was prevented.** A deferral of the `import-untyped` group — which the work order explicitly
invited — would have been honest and would have left `uplift-verify` dead, because those three errors
*were* the whole gate.

**What is blocked, and it is the operator's.** Billing. Then C56 (task 26.2, which now blocks 27.5),
then `main`'s hidden unit-test failure, then three never-executed steps.

**Census at close: 140 leaf, 61 done, 2 authored-pending-discharge, 77 open** (69 authorable, 8
CI-gated). The two `[~]` are **10.4** (checkpoint A) and **26.1** (the regeneration job, never
executed).

**Verified at close:** `mypy --strict orchestrator/` exit 0 over 89 files; CI's exact narrow command
exit 0 over 44; ruff `0/0` at CI's exact scope (386 files); 191 passed / 18 skipped / 5 deselected /
1 pre-existing failure across 13 loci; **21 passed** in the census suite including 6 new barrier
tests; six cheap gates **0/0/0/2/1/0**; `pin_extractor_truth` **14/14**; census 0; every written file
byte-verified, no BOM, no U+FFFD; process sweep clean.

**NOT verified, and must not be claimed:** `uplift-verify`, and therefore **Properties 38–60**;
`quality-gates` steps 18–23; `regenerate-truth-docs.yml`, never executed;
`ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth`, not run locally in any form; the five
slow-marked `ConsensusProtocol` properties; `vitest`; `_measure`'s wired interval path; **step 8 at
commit `743ca6b`** (its scope is a strict subset of the wide command, which exits 0 locally, so step
8 is 0 **by mechanical implication from local evidence** — not because CI said so at that commit).
