# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **5** (2026-09-09).

**This prompt states no HEAD, deliberately.** Conflicts J and K were the same defect three sessions
running: the prompt is written *before* the commit that carries it, so any sha it names is stale by
construction. STEP 0 derives it instead.

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`.

**Your session cap is THIRTY leaf tasks, in three waves of about ten. It is a ceiling and it is
expected never to bind.** What stops you is a barrier or a phase boundary.

### STEP 0 — `uplift-verify` RUNS NOW. Read what it says, because that is this session's work.

**The `needs: quality-gates` edge was removed in session 5, so `ci.yml::uplift-verify` executes on
every push instead of reporting `skipped`.** Its first run reported **`830 passed, 9 failed`** on the
fast step. **Reading those nine, and repairing the eight that are this spec's, is the top of your
list** — and unlike every leaf in the census, no barrier gates it.

```powershell
git rev-parse --short HEAD                       # derive HEAD; never trust a document for it
git rev-list --count origin/main..HEAD
gh run list --branch feat/decision-quality-proof --limit 10 --json databaseId,headSha,workflowName,conclusion
```

Then read **both** jobs' step lists for the newest sha — not the run's colour, the step list:

```powershell
$j = gh api "repos/:owner/:repo/actions/runs/<id>/jobs" | ConvertFrom-Json
foreach ($job in $j.jobs) { "{0} | {1} | steps={2}" -f $job.name, $job.conclusion, $job.steps.Count }
```

**At handoff:** `quality-gates` steps 1–17 **success**, **step 18 failure**, 19–23 skipped.
`uplift-verify` **ran**: step 4 install **success**, step 5 fast **failure** (`9 failed, 838 passed,
1 skipped, 28 deselected, 2 xpassed` at the head commit), step 6 slow **skipped behind it**.
`sprint6-verify` and `training-smoke` still skipped — they keep their own `needs:`. **Use a
`foreach`, not a pipeline: PowerShell 5.1's `ConvertFrom-Json` hands back the array unenumerated and
a piped `Where-Object` silently yields nothing.**

**Read the two runs as a pair before touching anything**, because their deltas are the proof that the
nine failures are not session 5's doing: across `e9db587 → 4b9d0d4` the passed count moved
`830 → 838` (**+8**, exactly the new fast tests), deselected `25 → 28` (**+3**, exactly the new slow
ones), and **the nine failures are the identical nine**.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the ceiling, wave discipline, the
   **barrier stop**, the three marks, the four checkpoints, the batch table, the six cheap gates,
   the progress ledger. **Read the last two rows (`4`, `5`) in full** — findings 34–42 live there.
   Its checkpoint-A section carries a **BLOCKING NOTE** whose first reason session 5 repaired; read
   it against `tasks.md` task 11, which is current.
3. `HANDOFF.md` (repo root) — the state of the tree, and **what is verified versus merely
   authored**. It opens with the nine failures and what they cost. Read those first.
4. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
5. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
6. `.cursorrules` + `docs/cursor/*.md`.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.5, the new D2.5.1, and the amendment log.**
8. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
   and your worklist**; tasks **11** and **27.5** carry session 5's findings in full.

**Two invariant numberings disagree.** `references/14_invariants.md` and `.cursorrules` differ on
I-6, I-8 and I-10. Authority 5 outranks authority 6. The invariants this work cites — I-1, I-4, I-5,
I-7 — agree in both.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict
rather than resolving it silently.** Fourteen have been surfaced (A–N). **Six are corrections to
instructions a session was itself given, and conflict N corrected the same claim in four documents
at once.** Expect more, and expect them in the procedure you are about to follow.

### STEP 2 — derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At handoff: **140 leaf tasks — 63 done, 2 authored-pending-discharge, 75 open** (69 authorable, **6**
CI-gated). `--next 30` offers `12.1 … 17.7` and names barriers **11** (30 of 30 follow) and **14**
(19 of 30 follow).

**The answer, which you should re-derive rather than copy: the batch DEPENDS ON BOTH.**
`tasks.md:1492` makes task 12's precondition "checkpoint A has run and task 11's verdict is not
`material`"; `15.1`–`17.7` are all of E3, which checkpoint B can cancel. So the offer truncates to
**11** and then to **zero**.

**That does NOT mean there is no work.** Session 5's `uplift-verify` failures are repair, not new
leaves, and no barrier gates them. Do not read a zero-leaf census as a zero-work session — session 5
landed three commits with the same census.

**For every barrier line, state in your opening whether the batch depends on it. An unanswered
barrier is a stop, not a warning.**

### STEP 3 — what to do, in priority order

#### A. THE NINE `uplift-verify` FAILURES. Eight are this spec's. Start here.

Attributed mechanically at handoff (`git cat-file -e origin/main:<f>`, then
`git diff origin/main -- <f>`):

| Module | Failures | Owner |
|---|---|---|
| `tests/verify/test_command_path_resolution_property.py` | **5** | **this spec** (absent from `main`) |
| `tests/verify/test_ledger_gen_property.py` | **2** | **this spec** (absent from `main`) |
| `tests/verify/test_ratchet_monotonicity_property.py` | **1** | **this spec** (absent from `main`) |
| `tests/uplift/test_aggregation_integrity_property.py` | **1** | **`main`'s** (byte-identical) |

**Seven of the nine reproduce locally at `HYPOTHESIS_PROFILE=dev` on the first try.** A hypothesis
that the example budget was hiding them was **refuted by measurement**: 5 of 8 fail at `dev` *and* at
`heavy`. So these are cheap to reproduce and cheap to diagnose — one scoped `pytest` per module.

**Do NOT run `tests/verify/test_ledger_gen_property.py` locally.** It names a registry execution and
I-0 forbids `ledger_gen` in any form. Its two failures (`assert 1 == 2`,
`assert 'unavailable' == 'fail'`) are *consistent with* the inverted `ledger_gen`/`readme_gen` order
session 4 measured — **not confirmed as it.** CI is the only sanctioned reader.

**Repair at the subject, and say which.** A stale assertion whose *precondition* changed is a
precondition correction; an assertion made to pass by filtering is assertion weakening (R2.10).
**Repair by PARTITIONING, not FILTERING**, and assert non-emptiness — `set() <= anything` is
vacuously true, and session 3 nearly created that defect inside its own repair.

#### B. FINDING 42 — the sweep cannot see this class of failure, and that is the procedure's hole

`SESSION_PROTOCOL.md` says to run "one bounded `pytest` over the loci **that wave touched**", and no
wave ever touched those four modules. So they were authored, reported diagnostics-clean, and executed
by **nothing**: not by a sweep, because sweeps are scoped to changes, and not by CI, because
`uplift-verify` was skipped. **Six handoffs called this spec's property surface "local evidence
only"; for these modules there was no local evidence either.**

The cheapest repair is the one now in place — keep `uplift-verify` reachable and read it every
session. Whether the protocol should *also* mandate a periodic full-tree read is the operator's.

#### C. OBSTRUCTION 2.5's OTHER HALF — still owed, still the operator's

`quality-gates` is red at **step 18** and is a `required:` check, so **PR #84 still cannot merge and
`main` is red too.** Disposition (a) is done; **(b) is owed**: split the step so
`tier_routing_accuracy` — which measures cleanly at `1.0000 >= 0.8000` over 200/200 traces — gates,
while `kv_cache_hit_rate` is declared unmeasurable-in-CI with its recorded reason.

**Open sub-decision inside (b):** C74's honest SKIP exits **2**, so making step 18 green requires a
declared-unmeasurable floor to be *non-failing*, which shifts the honesty burden onto the
declaration. My reading is that the declaration belongs in `infrastructure/quality/replay-floors.yaml`
with its prerequisite and procedure (C74's `confirmation.procedure` shape) rather than behind a CLI
flag, because a flag lets any caller silence any floor from a workflow. **Do NOT lower
`kv_cache_hit_rate`** (R2.10) **and do NOT add `continue-on-error`** (finding 35).

#### D. CHECKPOINT A, on the repaired comparator

Session 5 landed the three-arm comparator, so the instrument now measures the subject R5.1 names.
What remains, in order: **run 1 by label**, then the **D2.5 amendment stating the derived literal**,
then the **margin commit** with the parked pin graduated, then **run 2**. D2.5's own rule puts the
amendment **before** the run judged against it.

**The verdict may still be `material`, and that is now a legitimate outcome.** With the reference arm
in place a `material` verdict is an **admissible** falsification about the right subject — which this
spec's design calls a good outcome — as distinct from the inadmissible one conflict M prevented.
**Do not read `material` as a defect in the repair.**

#### Also owed, and smaller

- **A second regeneration**, owed by the generator order itself: `ledger_gen` projects a top-level
  execution in which C56 is evaluated, and C56 reads the README that `readme_gen` rewrites
  *afterwards*. The durable repair swaps the two `--write` steps and edits the enforcement spine —
  the operator's. **The two parked `s`/`S` pins graduate in the same data edit, after it.**
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35). Registered-check change.
- **CI's ruff scope** excludes nine trees including `uplift/` and `digital_twin/`: **530 lint
  findings, 254 format findings (upper bound).** Widening it re-closes `quality-gates` at step 5.
- **`scipy` is pinned in NO requirements file in the repository** and arrives transitively via
  `scikit-learn` and `lifelines`. A declared import on an unpinned transitive dependency (finding
  41). Widening the closure is the broad change defect 22 rejects.
- **CF-13 violations**: hardcoded `max_examples` in
  `tests/uplift/test_par_level_reorder_properties.py` (200) and
  `tests/uplift/test_seeded_demand_identity_property.py` (300, 200).

### STEP 4 — how a session is actually run

**Three waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit.
2. **Write findings into `tasks.md` and the ledger as you find them.**
3. **Delegate reading, never execution.** Unlimited parallel sub-agents for reading, writing and
   analysis; **exactly ONE** that executes code. Keep every command in the main agent.
4. **Re-read the authority file for each wave's area before starting it.**

**Spend `gh` reads first.** They are free under I-0 and they are the highest-yield evidence in this
repo: session 5's whole payoff was one `gh` read of a job that had never run.

#### FORBIDDEN REPAIRS. Each names what it would destroy.

No error may be cleared by **giving an argument a default**, by **widening a type to `Any`**, by
**adding a `# type: ignore`**, by **narrowing a checker's scope**, by **lowering a floor**, or by
**adding `continue-on-error`**. The first substitutes an unreviewed value for a committed one; the
next three make the checker agree by asking it less; the fifth is R2.10 assertion weakening; the
sixth is finding 35. **If an error is genuinely a tooling artifact, repair the *declaration that
misleads the checker*, never the call sites that report it.**

#### Determine ownership mechanically, and `git log -1` is NOT enough

```powershell
git cat-file -e origin/main:<file>              # exit 0 => exists on main
git diff origin/main -- <file>                  # attribute the LINE, not the file
git merge-base --is-ancestor <sha> origin/main  # exit 1 => this branch's
```

**And for lint or format debt, materialise the blob and re-run the checker** — that is how session 5
proved it added none:

```powershell
# `>` writes UTF-16 and Set-Content adds a BOM, so do this from Python, not PowerShell.
# git cat-file blob HEAD:<file>  ->  write_bytes  ->  python -m ruff check <scratch>
```

---

## STOP CONDITIONS

- **Stop at any barrier the census names that the batch depends on.** Say which.
- **Stop and report if a count does not move as predicted.** State the delta **per code** and what
  you checked.
- **Do not tick 11, 14, 21, 22.3, 25 or 27.5** without the naming job's own verdict. **27.5 needs
  `uplift-verify` to reach its END** — it now *runs*, which is not the same thing.
- **Do not commit `materiality_margin.value`** until the D2.5 amendment stating the derived literal
  has landed and run 1 has been made against the three-arm comparator.
- **Do not change `main`.**
- **Do not run `ledger_gen` or `readme_gen`** locally, in `--check` or `--write` form, for any
  reason — **and that now includes `tests/verify/test_ledger_gen_property.py`.**
- **Do not pad a session toward thirty**, and do not read a zero-leaf census as a zero-work session.
- Surface every new conflict rather than resolving it silently.

---

## THE CHAIN, MEASURED RATHER THAN PREDICTED

| # | Obstruction | State |
|---|---|---|
| 0 | the runner itself — billing | **CLEARED** — repository made public |
| 1 | step 8 mypy strict (orchestrator) | **CLEARED** (2r), re-confirmed `success` |
| 2 | step 17 **C56** narrative-truth | **CLEARED** (26.2 / 26.3) |
| **2.5** | **step 18 golden-trace replay** | **RED, STRUCTURAL.** Disposition (a) removed the `needs:` edge so it no longer blocks `uplift-verify`; **it still blocks `quality-gates`, which is a `required:` check** |
| 3 | step 19 unit tests → `test_cognition_phase` | **still unknown** — skipped behind 18 |
| 4 | steps 20–22 coverage / spec coverage / contract | **still unknown** |
| **5** | **`uplift-verify` step 5, the fast property surface** | **RUNS. `830 passed, 9 failed`** — eight of the nine are this spec's |
| **6** | **`uplift-verify` step 6, the slow surface** | **skipped behind step 5.** Six slow properties, the 623-test floor, the fault-injection probe and `digital_twin`'s 1000-scenario run have still never executed |

**Session 2r's lesson has fired four times: clearing a gate reveals what it was shielding, and the
depth is unknown until each layer clears.** Session 5 cleared one and revealed nine failures behind
it. **No single clearance licenses a claim about the job at the end.**

---

## HARD-WON LESSONS. Forty-two findings and fourteen conflicts, each one paid for.

### The eight habits that caught the most

1. **A gate that has never executed is not evidence — and neither is a test that nothing has ever
   run.** Session 5's eight own-spec property failures reproduce locally at the cheapest profile on
   the first try, and sat undiscovered for six sessions because the sweep is scoped to what a wave
   *changed*. **Verify what you already had, not only what you touched.**
2. **Consensus across documents is not evidence — it is usually one unchecked claim copied
   forward.** Four files agreed `Par_Level_Reorder` was unlanded. It was on disk, with tests, and its
   owning spec marked it `[x]`.
3. **Check the second half of a recorded repair, not only the first.** `HANDOFF.md`'s conflict-M fix
   was right that the arm was wrong and wrong that landing it would separate the two quantities.
4. **Verify at the boundary you are claiming, not at a proxy for it.** Conflict I: three authority
   files said a baseline was measured "at CI's exact command"; no workflow runs that command.
5. **Read the procedure against the tree, not against its own table of contents.** Conflict L: the
   batch table said "reachable by labelling" while the procedure below it still instructed a
   404-returning dispatch.
6. **Prove the SHAPE of a deviation, not just its size.** Session 5 predicted `gate_surface`'s
   needs-clause count `6 → 3` with row counts unchanged, *before* running `--write`, and measured
   exactly that.
7. **Never generalise one proof to a population.** One of 40 format errors was proven a line-ending
   artifact and that proof was extended to all 40. **Three were real.**
8. **Read what got SKIPPED behind a failure, not only what failed.** One 101-character line once
   gated 18 steps and 3 jobs.

### On verdicts and assertions that cannot move

- **A number that cannot fail is not a number — AND a verdict that cannot be anything else is not a
  verdict.** Conflict M was the second form. **The repair is not "fix the guard" — it is to ask what
  the guard bounds the subject AGAINST, and whether that thing is independent of the subject.** A
  third arm was needed because two arms make `regret` and `headroom` the same subtraction.
- **A tautology dressed as an assertion is the same defect.** `headroom >= regret` held trivially
  under two arms and proved nothing; it is a real claim only because the two sides are now different
  pairs. **Check whether your new assertion can fail before writing it.**
- **A level floor is a tolerated-exception disjunct.** Suppressing logs below ERROR left an artifact
  canonical only while nothing logged at ERROR. **Assert a clause unconditionally**: route the
  channel, do not just raise the threshold.
- **An assertion that cannot fail is not an assertion.** `comparison-overlap` caught two (finding
  26), and filtering a call list then asserting the remainder is a subset is **vacuous** when the
  remainder is empty. Assert non-emptiness too.
- **Repair a stale assertion by PARTITIONING, not FILTERING.**
- **A test can assert nothing at all.** `test_protocol.py::test_tier1_skips_debate` contains only
  comments.
- **A pin that cannot fail is not a pin.** **Parking a correct pin is honest; landing a toothless one
  is not** — and session 5 parked two more rather than compound an owed regeneration's diff.
- **Never weaken a generator, an assertion or a floor to make something pass** (R2.10). Fix the
  subject — or, if the *precondition* was wrong, fix the precondition **and say which.**

### On gates reporting the wrong thing

- **A required check that can only report `skipped` is not a gate.** `uplift-verify` was declared
  `required:` and skipped for this branch's entire life; removing one `needs:` line produced more
  evidence than four sessions of authoring.
- **An unguarded shell pipeline discards its subject's exit status, and `workflow_shape_truth` cannot
  see it** (finding 35). Use `set -o pipefail` in any `run:` that pipes a gate or a measurement.
- **A document generated on the wrong machine can record an environment error as a finding and hide
  the real ones behind it** (finding 37).
- **The gate that fails is not always the gate that would tell you.** A pin with a dead document
  anchor makes `doc_truth` report a **`skip`** — C56 SKIP, not FAIL — while `pin_extractor_truth`
  reports green, because it probes the source side only. **Probe the anchor as a pure function before
  committing a pin: session 5's first draft of two anchors matched ZERO lines over a misplaced
  backtick.**
- **A verdict is a claim about its own derivation.** A splatting bug made a gate exit 2 when it is 0;
  a stale mypy cache kept reporting cleared errors (`--no-incremental` after any config change).
- **`UNAVAILABLE` from a floor with no measurement is the gate working, not failing.** The repair is
  to declare the floor unmeasurable with its reason, never to lower it.
- **A SKIP is not milder than a FAIL for measurement.** The sweep reports `indeterminate` for any
  gate that does not PASS on its unmutated baseline, so **doc drift costs measurement power.**
- **A local red is not always a CI red, and a local green is not a CI green** — and sometimes, as
  finding 42 shows, there was never a local run at all.

### On scope, ownership, adoption and closures

- **CI's scope is not the tree's scope, and the gap is measured.** `ruff` covers
  `packages/synapse_common/ agents/ orchestrator/` **only** — 530 lint / 254 format findings sit in
  the nine trees it never reads, including `uplift/` and `digital_twin/`.
- **Attribute lint debt by materialising the committed blob and re-running the checker.** Session 5
  proved it added zero of `uplift/harness.py`'s 12 findings that way.
- **Read the install closure before trusting a job can run its own subject. Four times now.**
  Defect 14 (`scipy`), defect 22 (`pydantic-settings`), finding 36 (the entry point), and finding 41
  — where the proof was taken **before** the push and step 4 then succeeded. **The closure proof must
  start at the command the job runs**, because `python -m pkg.mod` executes `pkg/__init__.py` first.
- **Fix a closure narrowly.** Widening `packages/requirements.txt` can turn a SKIP into a PASS and
  **move the registry counts `doc_truth` pins.**
- **`workflow_dispatch` requires the workflow on the default branch; `pull_request` does not.** And
  **a mechanism is not reachable until its trigger exists** (finding 34).
- **When you add a trigger, the GUARD is the load-bearing half.** A deny-list is **fail-OPEN** against
  a new trigger. Use an allow-list and **verify by truth table over every event × input × label
  combination.**
- **Do not adopt another owner's debt unilaterally**, but record the diagnosis so it is not
  re-derived. Parent 27 and `test_cognition_phase` were each adopted by *explicit* operator decision.
- **A workflow that has never executed is the I-7 shape, and *reachable* is not *run*** — and *run*
  is not *finished*: `uplift-verify` now runs and still does not reach its end.

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

- **A `[~]` graduates on the job's own verdict, never on a local run.**
- **A `discharge:` line can name TWO subjects.** 26.1 stays `[~]` because its second — the
  closure-parity property at `ci.yml::uplift-verify`'s fast step — is now **executed but red**, in a
  job whose fast step failed on nine other tests.
- **A job's colour is not always the task's verdict.** Read the subject of a failure before treating
  it as yours.
- **Leave a half-landed task `[ ]`, not `[~]`, when the owed half is blocked on another task.**
- **"Authored and diagnostics-clean, not executed" is a legitimate result.** A **deselected** test is
  not a pass either.
- **Disk outranks the ledger.** **`tasks.meta.json` is not authority.**

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what throttle it.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
  `pnpm` anything — **and `tests/verify/test_ledger_gen_property.py`, which names a registry
  execution.** `regenerate-truth-docs.yml` is the sanctioned route for the generators.
- **Cheap and encouraged:** file reads, `grep`, `get_diagnostics`; `ruff`/`mypy` on changed files;
  bounded scoped `pytest`; `spec_ledger_census`; the **six** cheap gates;
  `doc_truth.documented_value` as a pure function; and **`gh` API reads — free, and the
  highest-yield evidence in this repo. Spend them first.**
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
  **unlimited.** Sub-agents that execute code: **exactly ONE at a time.**
- **Preferred flags:** `-x -q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
- **Count and report your real invocation count.** Session 5 used **nine** bounded `pytest` runs
  against a stated three, and said so rather than reporting the budget. **The bound is on scope and
  serialisation; the honesty obligation is on the count.**
- **Sweep before finishing, and after any cancelled or timed-out command.**

### Verification sweep

**Per wave** — only what that wave touched, plus, from now on, **anything the last `uplift-verify`
run reported red**:

```powershell
python -m ruff check <wave's changed files>
python -m ruff format --check <wave's changed files>
python -m mypy --strict <wave's changed python files> --no-incremental
git ls-files --eol <wave's changed files>          # w/mixed after ANY programmatic edit
$env:HYPOTHESIS_PROFILE='dev'
python -m pytest <wave's touched loci> -q --tb=line -p no:randomly -m "not slow"
```

**Before closing:**

```powershell
python -m scripts.audit.workflow_shape_truth              # C64   expect 0
python -m scripts.audit.pin_extractor_truth --check       # C75   expect 0 and 14 declared
python -m scripts.audit.sweep_budget_truth --check        # C73   expect 0
python -m scripts.audit.dataset_licence_truth --check     # C74   expect 2 = honest SKIP
python -m scripts.audit.task_claim_truth --check          # expect 1 = pre-existing, other spec
python -m scripts.audit.gate_surface --check              # C63   expect 0
python -m scripts.audit.spec_ledger_census --files --check # expect 0
```

Expected: **`0 / 0 / 0 / 2 / 1 / 0`** plus census 0. **`pin_extractor_truth` must report 14
declared** — 15 means the parked derived-margin pin moved into `pins:`, and 16 means the two parked
`s`/`S` pins did, which the owed regeneration forbids until it has run.

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
  Seven sessions running. `git ls-files --eol` reports `w/mixed`. Normalise to the file's
  **dominant** ending with Python at `newline=''` — and **count the WORKTREE bytes**, because the
  `i/` column is normalised (finding 33).
- **`ruff`'s `SIM300` reads an upper-case attribute as a constant.** `assert arm.S == spec.x` is
  flagged a Yoda condition. Compare as a tuple; do not add a `noqa`.
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated.** Assign, then `foreach`.
  **`gh label create` prints nothing on success** — verify with `gh label list`.
- **PowerShell's `-f` operator rejects `{1,>6}`** — it throws per call while the loop continues, so
  it presents as a hang.
- **There are no heredocs.** `python - <<'PY'` is a parse error. Write a temp `.py`, run it, delete
  it. **Complex inline `python -c` breaks on quoting** too — nested quotes inside an f-string will
  fail.
- **A recursive `Get-ChildItem` over this tree can exceed the 120-second command timeout.**
- **`git push` writes progress to stderr**, so PowerShell reports `NativeCommandError` and a non-zero
  `$LASTEXITCODE` on a **successful** push. Read the `old..new ref` line.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental`.
- **`git log -1 -- <file>` is last-touch, not authorship.**
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** `Get-Content -Raw` decodes
  with the ANSI codepage and `Set-Content -Encoding utf8` adds a **BOM**. `>` writes **UTF-16**.
  `Copy-Item` is a byte copy and is safe. **Verify bytes, never the console.**
- **`$LASTEXITCODE` is unreliable after a native command is piped through `Select-String`.** Re-run
  with `*> $null`.
- **`git status` over-reports.** Trust `git diff`, stage precisely, `git check-ignore -v` first.
- **Identify a CI run by `head_sha`, NEVER by timestamp**, and check the run for the sha
  `git rev-parse` gives you.
- **`git commit -F` a temp file** for any message longer than a line.
- Suppress twin logging in any engine-driving probe or the output floods, **and route the factory to
  stderr if the stream matters**:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR), logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))`.
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks pre-existing errors
  under `uplift/`. Its ruff hook is also the only thing that would lint the trees CI never reads, so
  **the two mitigations are mutually exclusive.**
- Python 3.14.0, **mypy 1.19.1** locally against CI's unpinned `mypy>=1.10.0,<2.0`, pytest 8.4.2,
  hypothesis 6.151.11, jsonschema 4.26.0. `gymnasium` absent. `gh` 2.82.0, authenticated.
  **Repository is PUBLIC — Actions minutes are unmetered on standard runners.**

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). **Do not assert a total** (CF-13).
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`; its fast step
  only `tests/uplift tests/verify`. **A slow-marked test outside those four paths is selected by no
  job at all.**
- **Assert a clause unconditionally** rather than wrapping it in a tolerated-exception disjunct.
  **Prove a refusal path by construction**, and **assert non-emptiness** wherever a subset or
  "nothing bad happened" clause could be satisfied by an empty set.
- **Derive numbers; flag the irreducible choice.** A knob with a self-serving sign gets a
  `ratchets.json` direction; one without gets none, and inventing one is fabrication. **A version
  bound with no committed antecedent is a choice and must say so.** Session 5's `s`/`S` are **read**
  from `engine.py` and therefore get **no** ratchet — a policy parameter has no better-direction.
- **`set -o pipefail` in any `run:` block that pipes a gate or a measurement.**
- Type hints everywhere (`mypy --strict`); Pydantic v2 `ConfigDict(frozen=True)` for recorded facts;
  `structlog`, never `print()`, in library code; canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`; `encoding='utf-8'` on **every**
  `read_text` (E-S13-07); ASCII-only console output; lines ≤ 100 characters.
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, or any paid SDK.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS, and
  a **deselected** test is not a pass.

### The five same-commit couplings

1. A rename and its declaration. (Session 5: `run_two_pass` → `run_three_pass` and `__all__`.)
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the job
   is genuinely eligible.** `ineligibleEntry.reason` is a closed six-value enum with no
   "dispatch-only" member, so such a job owes **none** (conflict G).
3. A schema change and every fixture that carries it.
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** **Check it rather than assume it** — it fired
   17→18 files (2q), 536→542 rows (2r-pre-c), 542→549 (session 3), did **not** fire on a `run:`-only
   edit whose step NAME did not change (session 4), and in session 5 fired on a `needs:` removal
   with **3 rows changed and zero rows added** while a comment-only `blocking-steps.yaml` edit
   correctly moved nothing.
5. The session ceiling lives in **one** place, `spec_ledger_census.DEFAULT_BATCH`.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** One commit **per wave**. A
  workflow change and its `gate_surface --write` share a commit; an ADR amendment shares the commit
  of the code it governs; documents describing two work streams go **last**.
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
Finding 4 and re-cut R5. Checkpoint B's task 14 can prove consensus unnecessary and cancel E3.

**Sessions 4 and 5 together are the clearest demonstration yet of why that design matters.**
Checkpoint A produced a number that *would* have ended the project; the checkpoint's own machinery
made it possible to see the number was about the wrong comparator; and the repair then required
noticing that the recorded fix would only have addressed half of it. **An instrument that can end the
project is only safe if you also check what it measured, and check the fix you were handed.**

**The pre-commitment, binding before the number is known:** if measured uplift is null or negative,
**it is reported as null or negative.** The floor stays at `0.0`, no headline is published as a gain,
and the result is written up as a finding — not reframed, not re-run at a different replicate count
until it moves. A null from a **validated** instrument on a **decision-relevant** world is worth more
than the tautological PASS it replaces.

Three guards on reading the result: a null while any objective KPI is recorded not observably
sensitive is **inconclusive**, not confirmation (task 10.5). No headline may be published while no
Power_Report describes the harness revision under measurement (task 17.3). And **a `material` verdict
on a point estimate with no dispersion is not a falsification** — nor is one on a comparator the
requirement does not name (conflict M).

---

## Session 5 handoff — regenerate this section each session

**Three commits plus the documents commit. NO leaf ticked, and the census is unchanged.**

| Commit | Subject |
|---|---|
| `28cecce` | a required check that can only report `skipped` is not a gate — `needs:` removed |
| `e9db587` | a declared canonical-JSON artifact that no parser could read |
| `4b9d0d4` | a verdict that cannot be anything else is not a verdict — the three-arm comparator |
| *(fourth)* | this prompt, `HANDOFF.md`, the ledger row, and tasks 11 / 27.5 |

**What was earned.** **`uplift-verify` executed for the first time ever** — `830 passed, 9 failed` on
the fast step, so this spec's fast property surface is measured at last. Conflict M's first reason is
repaired and the comparator measures the subject R5.1 names. The 215 MB non-JSON artifact is fixed
and now **asserted**. `uplift/foresight.py` has its first tests.

**What was learned, and it is the expensive part.** Eight of those nine failures are **this spec's
own**, seven reproduce locally at `dev` on the first try, and they sat undiscovered for six sessions
because the per-wave sweep only runs what a wave *touched* (**finding 42**). "Local evidence only"
was generous: for four modules there was no local evidence either.

**What is blocked, and it is the operator's.** Obstruction 2.5's step-18 split, and with it PR #84's
mergeability; the second regeneration; `workflow_shape_truth`'s pipeline blindness.

**Verified at close:** six cheap gates **0/0/0/2/1/0**; census exit **0**, unchanged at
`140/63/2/75`; `pin_extractor_truth` **14/14/14**; `gate_surface`'s delta predicted then measured
exactly; every written file uniform-ending, no BOM, no U+FFFD; lint/format debt proven byte-identical
at HEAD so zero was added; `mypy --strict` clean on all three changed modules and `uplift/` down 7→6.

**NOT verified, and must not be claimed:** `uplift-verify`'s **slow** step, and therefore the slow
half of Properties 38–60; the three new slow twin-driving properties (**deselected, not passed**);
what the `(s, S)` regret actually **is** — no twin measurement was taken; that the next
`twin-regret` run uploads a parseable artifact; `quality-gates` steps 19–23; task 11's verdict; the
two `test_ledger_gen_property.py` failures locally, which I-0 forbids.
