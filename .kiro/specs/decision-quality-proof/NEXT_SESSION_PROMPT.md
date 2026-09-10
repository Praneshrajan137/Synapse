# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **6** (2026-09-10).

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

### STEP 0 — TWO REPAIRS ARE ON DISK AND UNJUDGED. READ THE RUN THAT JUDGES THEM.

Session 6 repaired all nine `uplift-verify` fast-step failures and landed obstruction 2.5's
disposition (b). **Neither has been judged by CI.** Reading the run for the newest sha is the whole
of your STEP 0, and it decides what the session is.

```powershell
git rev-parse --short HEAD                       # derive HEAD; never trust a document for it
git rev-list --count origin/main..HEAD
gh run list --branch feat/decision-quality-proof --limit 10 --json databaseId,headSha,workflowName,conclusion
```

Then read **both** jobs' step lists for the newest sha — not the run's colour, the step list:

```powershell
$j = gh api "repos/:owner/:repo/actions/runs/<id>/jobs" --paginate | ConvertFrom-Json
foreach ($job in $j.jobs) { "{0} | {1} | steps={2}" -f $job.name, $job.conclusion, $job.steps.Count }
foreach ($job in $j.jobs) { foreach ($s in $job.steps) { "{0,3} {1,-12} {2}" -f $s.number, $s.conclusion, $s.name } }
```

**Use a `foreach`, not a pipeline: PowerShell 5.1's `ConvertFrom-Json` hands back the array
unenumerated and a piped `Where-Object` silently yields nothing.**

**Then read the LOG, not only the step list.** Session 6's entire payoff was the step-5 log: nine
summary lines turned out to be **eleven** defects, because two of them were `ExceptionGroup`s
carrying two distinct failures each, and every falsifying example was in the log.

```powershell
gh api "repos/:owner/:repo/actions/jobs/<jobid>/logs" 2>$null |
  Select-String -Pattern "FAILED tests|Falsifying example|Failing test case|passed" |
  ForEach-Object { $_.Line }
```

**At session 6's close, on sha `58fc4e1` (run `34434951478`):** `quality-gates` steps 1–17
**success**, **step 18 failure**, 19–23 **skipped**; `uplift-verify` step 4 **success**, step 5
fast **failure** (`9 failed, 838 passed, 1 skipped, 28 deselected, 2 xpassed`), step 6 slow
**skipped**. Both of session 6's commits land after that run. **So the newest run is new evidence
and the four things to read off it are:**

1. **Did step 18 exit 0?** Predicted, not proved. If it did, **steps 19–23 execute for the first
   time on this branch or on `main`** — obstructions 3 and 4, whose state is *unknown*, not green.
   Read what they say before treating anything as clear.
2. **Did the fast step go green?** Nine reds were repaired. A tenth may sit behind them: session
   2r's lesson has fired four times.
3. **If the fast step is green, step 6 — the slow surface — runs for the first time ever.** Six
   slow properties, the 623-test regression floor, the subprocess fault-injection probe and
   `digital_twin`'s 1000-scenario run have never executed. Expect reds, and read them as **newly
   visible, not newly broken**.
4. **Did the two `test_ledger_gen_property.py` repairs pass?** They were authored and never
   executed — I-0 forbids running that module locally, in any form. This run is their only reader.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the ceiling, wave discipline, the
   **barrier stop**, the three marks, the four checkpoints, the batch table, the six cheap gates,
   the progress ledger. **Read the last two rows (`5`, `6`) in full** — findings 34–47 and conflict
   O live there.
3. `HANDOFF.md` (repo root) — the state of the tree, and **what is verified versus merely
   authored**. Read its honesty ledger before believing any colour.
4. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
5. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
6. `.cursorrules` + `docs/cursor/*.md`.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.5, D2.5.1, and the amendment log.**
8. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
   and your worklist**; tasks **11** and **27.5** carry sessions 5 and 6's findings in full.

**Two invariant numberings disagree.** `references/14_invariants.md` and `.cursorrules` differ on
I-6, I-8 and I-10. Authority 5 outranks authority 6. The invariants this work cites — I-1, I-4,
I-5, I-7 — agree in both.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict
rather than resolving it silently.** Fifteen have been surfaced (A–O). **Six are corrections to
instructions a session was itself given; conflict N corrected the same claim in four documents at
once; conflict O corrects a count in the steering file and in this prompt's predecessor.** Expect
more, and expect them in the procedure you are about to follow.

### STEP 2 — derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At handoff: **140 leaf tasks — 63 done, 2 authored-pending-discharge, 75 open** (69 authorable,
**6** CI-gated), unchanged across sessions 4, 5 and 6. `--next 30` offers `12.1 … 17.7` and names
barriers **11** (30 of 30 follow) and **14** (19 of 30 follow).

**The answer, which you should re-derive rather than copy: the batch DEPENDS ON BOTH.** Task 12's
precondition is checkpoint A's verdict; `15.1`–`17.7` are all of E3, which checkpoint B can cancel.
So the offer truncates to **11** and then to **zero**.

**That does NOT mean there is no work.** Sessions 5 and 6 each landed multiple commits with the
same census. Do not read a zero-leaf census as a zero-work session.

**For every barrier line, state in your opening whether the batch depends on it. An unanswered
barrier is a stop, not a warning.**

**`$LASTEXITCODE` lies if you pipe the census through `Select-Object -First N`** — the report says
`status: pass (exit 0)` while the shell says 1. Re-run with `*> $null`. A gate's non-zero exit is a
claim about the gate; verify the invocation before believing it.

### STEP 3 — what to do, in priority order

#### A. WHATEVER THE NEW RUN SAYS. Start there, and let it choose the session.

The three branches, in the order they become reachable:

- **Fast step green, slow step ran** → read its reds, attribute each one mechanically
  (`git cat-file -e origin/main:<f>`, then `git diff origin/main -- <f>`), and repair only what is
  this spec's. **Task 27.5 discharges only when the job REACHES ITS END** — a job that runs is not
  a job that finished.
- **Fast step still red** → the tenth defect. Read the log for the falsifying example before
  touching anything; session 6's whole method was that the log names the mechanism and the summary
  line does not.
- **Step 18 exited 0 and steps 19–23 ran** → obstructions 3 and 4 report for the first time ever,
  on this branch or on `main`. Obstruction 3's repair is already on disk (`bf8693f`) and unjudged.
  Steps 20–22 have never executed anywhere, so their state is **unknown**, not green.

#### B. IF STEP 18 IS STILL RED, READ WHY BEFORE RE-REPAIRING IT

The declaration mechanism has four states and three of them are non-passing on purpose:

- `malformed` → the block declares nothing; the floor stays `unavailable` and the gate exits 2.
  Check `declared: true` plus non-empty `prerequisite`, `blocked_on`, `procedure`, and **no other
  key** — the reader is fail-closed and `extra="forbid"` is deliberate.
- `void` → a measurement was obtained, so the declaration is false and the gate fails **whichever
  side of the floor the number fell on**. The repair is to DELETE the block, never to keep it.
- an unreadable floor cannot be declared about at all.

**Do NOT lower `kv_cache_hit_rate`** (R2.10) **and do NOT add `continue-on-error`** (finding 35).
If the mechanism itself is wrong, repair it at the reader — `tests/verify/test_replay_metric_
threshold_property.py` asserts all four states plus the converse that an undeclared case is never
milder, so a change that breaks the contract will say so.

#### C. CHECKPOINT A, on the repaired comparator — still owed, still the operator's

Session 6 **deliberately did not run it**, and task 11 records why: the instrument sat in a tree
whose own property surface was red in nine places. That reason expires the moment the fast step is
green.

What remains, in order: **run 1 by label**, then the **D2.5 amendment stating the derived literal**,
then the **margin commit** with the parked pin graduated, then **run 2**. D2.5's own rule puts the
amendment **before** the run judged against it. Expect `verdict: unavailable` on run 1 — that is
finding 16, not a fault.

**The verdict may still be `material`, and that is now a legitimate outcome.** With the reference
arm in place a `material` verdict is an **admissible** falsification about the right subject, which
this spec's design calls a good outcome. **Do not read `material` as a defect in the repair.**

#### Also owed, and smaller

- **A second regeneration**, owed by the generator order itself: `ledger_gen` projects a top-level
  execution in which C56 is evaluated, and C56 reads the README that `readme_gen` rewrites
  *afterwards*. The durable repair swaps the two `--write` steps and edits the enforcement spine.
  **The two parked `s`/`S` pins graduate in the same data edit, after it.** So does finding 45's
  stale C16 docstring in `verify_claims.py`, which still calls the closed `stryker-break` hole live.
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35). Registered-check change.
- **CI's ruff scope** excludes nine trees including `uplift/` and `digital_twin/`: **530 lint
  findings, 254 format findings (upper bound).** Widening it re-closes `quality-gates` at step 5.
- **Conflict O — CF-13's enforcement scope.** 41 files, 56 hardcoded `max_examples` sites, and the
  intersection with the inventory the check reads is **empty**. Another spec's files; widening the
  check is the durable repair.
- **`scipy` is pinned in NO requirements file in the repository** and arrives transitively via
  `scikit-learn` and `lifelines` (finding 41).

### STEP 4 — how a session is actually run

**Three waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit.
2. **Write findings into `tasks.md` and the ledger as you find them.**
3. **Delegate reading, never execution.** Unlimited parallel sub-agents for reading, writing and
   analysis; **exactly ONE** that executes code. Keep every command in the main agent.
4. **Re-read the authority file for each wave's area before starting it.**

**Spend `gh` reads first.** They are free under I-0 and they are the highest-yield evidence in this
repo: session 5's whole payoff was one `gh` read of a job that had never run, and session 6's was
one `gh` read of that job's **log**.

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

**And for lint or format debt, materialise the blob and re-run the checker** — that is how sessions
5 and 6 each proved they added none:

```powershell
# `>` writes UTF-16 and Set-Content adds a BOM, so do this from Python, not PowerShell.
# git cat-file blob HEAD:<file>  ->  write_bytes  ->  python -m ruff check <scratch>
```

**Wave 1's five files carried 9 pre-existing ruff findings and were already not
`ruff format`-clean at HEAD.** `tests/` and `scripts/` are outside CI's ruff scope, so that debt is
real and is not yours. Prove it rather than assume it.

---

## STOP CONDITIONS

- **Stop at any barrier the census names that the batch depends on.** Say which.
- **Stop and report if a count does not move as predicted.** State the delta **per code** and what
  you checked.
- **Do not tick 11, 14, 21, 22.3, 25 or 27.5** without the naming job's own verdict. **27.5 needs
  `uplift-verify` to reach its END** — running is not finishing.
- **Do not commit `materiality_margin.value`** until the D2.5 amendment stating the derived literal
  has landed and run 1 has been made against the three-arm comparator.
- **`pin_extractor_truth` must report 14 declared.** 15 means the parked derived-margin pin moved
  into `pins:`; 16 means the two parked `s`/`S` pins did, which the owed regeneration forbids until
  it has run.
- **Do not change `main`.**
- **Do not run `ledger_gen` or `readme_gen`** locally, in `--check` or `--write` form, for any
  reason — **and that includes `tests/verify/test_ledger_gen_property.py`.**
- **Do not pad a session toward thirty**, and do not read a zero-leaf census as a zero-work session.
- Surface every new conflict rather than resolving it silently.

---

## THE CHAIN, MEASURED RATHER THAN PREDICTED

| # | Obstruction | State |
|---|---|---|
| 0 | the runner itself — billing | **CLEARED** — repository made public |
| 1 | step 8 mypy strict (orchestrator) | **CLEARED** (2r), re-confirmed `success` |
| 2 | step 17 **C56** narrative-truth | **CLEARED** (26.2 / 26.3) |
| **2.5** | **step 18 golden-trace replay** | **REPAIRED ON DISK, UNJUDGED.** (a) session 5, (b) session 6. Predicted exit 0 |
| 3 | step 19 unit tests → `test_cognition_phase` | **unknown** — never executed here or on `main`; repair on disk since `bf8693f` |
| 4 | steps 20–22 coverage / spec coverage / contract | **unknown** — never executed anywhere |
| **5** | **`uplift-verify` step 5, the fast surface** | **REPAIRED ON DISK, UNJUDGED.** Nine reds repaired; eight verified locally, two authored-only |
| **6** | **`uplift-verify` step 6, the slow surface** | **still skipped behind step 5** and has never executed |

**Session 2r's lesson has fired four times: clearing a gate reveals what it was shielding, and the
depth is unknown until each layer clears. No single clearance licenses a claim about the job at the
end.**

---

## HARD-WON LESSONS. Forty-seven findings and fifteen conflicts, each one paid for.

### The nine habits that caught the most

1. **Read the LOG, not the summary.** Nine `FAILED` lines were eleven defects: two were
   `ExceptionGroup`s of two. Every mechanism — an `arm`-driven float reorder, a mutation that
   deleted a marker, a lookbehind that refuses `-python` — was invisible from the summary and plain
   from the falsifying example. **`gh` log reads are free under I-0. Spend them first.**
2. **A gate that has never executed is not evidence — and neither is a test that nothing has ever
   run.** Eight own-spec property failures sat undiscovered for six sessions because the sweep is
   scoped to what a wave *changed*. **Verify what you already had, not only what you touched.**
3. **Consensus across documents is not evidence — it is usually one unchecked claim copied
   forward.** Four files agreed `Par_Level_Reorder` was unlanded; it was on disk with tests. The
   steering file says CF-13 has three violations; it has 56.
4. **Check your own instrument before you trust its count.** The first tool written to count CF-13
   violations was a regex over raw text and over-reported by 6 sites, having matched assignments a
   file *quotes as test data* — the very file written to warn about that. AST, not regex.
5. **Check the second half of a recorded repair, not only the first.** Session 1's
   `stryker-break` remediation named four sites and moved two; the two it skipped are what made a
   property red six sessions later.
6. **Verify at the boundary you are claiming, not at a proxy for it.** Conflict I: three authority
   files said a baseline was measured "at CI's exact command"; no workflow runs that command.
7. **Prove the SHAPE of a deviation, not just its size.** Predict the delta, then measure it:
   `gate_surface` 0 on a comment-only edit, `command_path_truth` 37/0/pass before and after a gate
   repair.
8. **Never generalise one proof to a population.** One of 40 format errors was proven a
   line-ending artifact and that proof was extended to all 40. **Three were real.** In the same
   spirit: `-python` is invisible to `_MODULE_RE` and `@python` is not — check, do not assume the
   worse case.
9. **Read what got SKIPPED behind a failure, not only what failed.** One 101-character line once
   gated 18 steps and 3 jobs.

### On verdicts and assertions that cannot move

- **A number that cannot fail is not a number — AND a verdict that cannot be anything else is not a
  verdict.** The repair is to ask what the guard bounds the subject AGAINST, and whether that thing
  is independent of the subject.
- **A tautology dressed as an assertion is the same defect.** **Check whether your new assertion
  can fail before writing it.** A findings-set equality that never compares the command set passes
  vacuously on exactly the input that breaks the gate (finding 44).
- **A mirrored implementation can MASK the subject it mirrors.** Making a test's reference reduce in
  the subject's canonical order is legitimate only if the order-invariance is *also* asserted
  directly — otherwise the repair makes the test agree by construction (finding 47).
- **Scope a claim to the domain the contract covers.** `sorted` is stable, so an aggregate
  canonicalised by a key is invariant **up to ties**, not "entirely" as its docstring says.
- **Repair a stale assertion by PARTITIONING, not FILTERING**, and **assert non-emptiness**
  wherever a subset or "nothing bad happened" clause could be satisfied by an empty set.
- **A level floor is a tolerated-exception disjunct.** Assert a clause unconditionally.
- **A pin that cannot fail is not a pin.** **Parking a correct pin is honest; landing a toothless
  one is not.**
- **Never weaken a generator, an assertion or a floor to make something pass** (R2.10). Fix the
  subject — or, if the *precondition* was wrong, fix the precondition **and say which.**

### On gates reporting the wrong thing

- **A required check that can only report `skipped` is not a gate.**
- **Two independent clauses in one gate can silently become one.** A leading `-` discarded a Make
  recipe's exit status *and* hid the command on that line, so the swallow concealed the
  unresolvable command it was swallowing. **When one gate asserts two things, ask whether either
  can hide the other.**
- **When two readers need the same parse, write it once.** Make's prefix grammar was read one way
  by the discard classifier and not at all by the extractor. One shared `split_make_prefix` is the
  durable repair; so is one shared "has no recorded measurement" predicate for a SKIP set.
- **An unguarded shell pipeline discards its subject's exit status, and `workflow_shape_truth`
  cannot see it** (finding 35). Use `set -o pipefail` in any `run:` that pipes a gate.
- **A declaration that cannot go stale is a mute button.** An honest SKIP must name the
  prerequisite that VOIDS it, and a measurement that arrives must falsify the declaration and fail
  the build until it is deleted — C74's rule in the other direction.
- **`UNAVAILABLE` from a floor with no measurement is the gate working, not failing.** The repair is
  to declare the floor unmeasurable **with its reason, its falsifier and its procedure**, never to
  lower it.
- **A verdict is a claim about its own derivation.** A splatting bug made a gate exit 2 when it is
  0; `Select-Object -First N` makes a passing gate report non-zero; a stale mypy cache kept
  reporting cleared errors.
- **A SKIP is not milder than a FAIL for measurement.** The sweep reports `indeterminate` for any
  gate that does not PASS on its unmutated baseline, so **doc drift costs measurement power.**
- **A local red is not always a CI red, and a local green is not a CI green.**

### On scope, ownership, adoption and closures

- **CI's scope is not the tree's scope, and the gap is measured.** `ruff` covers
  `packages/synapse_common/ agents/ orchestrator/` **only**. A CF-13 check walks 37 declared paths
  while all 41 violators sit outside them. **A rule enforced over the wrong scope is prose.**
- **Attribute lint debt by materialising the committed blob and re-running the checker.**
- **Necessary is not sufficient.** Repairing this spec's eight failures could not green the fast
  step while `main`'s ninth stood, and one red anywhere keeps the slow step skipped. **Ask what
  else gates the thing you are trying to reach.**
- **Do not adopt another owner's debt unilaterally**, but record the diagnosis so it is not
  re-derived. Two adoptions so far, each by *explicit* operator decision.
- **One diff, one cause.** A CF-13 violation in a file you are repairing for another reason stays;
  changing an example budget in the same commit would confound the measurement of the repair.
- **Read the install closure before trusting a job can run its own subject. Four times now.**
- **`workflow_dispatch` requires the workflow on the default branch; `pull_request` does not.**
- **A workflow that has never executed is the I-7 shape, and *reachable* is not *run*** — and *run*
  is not *finished*.

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

- **A `[~]` graduates on the job's own verdict, never on a local run.**
- **A `discharge:` line can name TWO subjects.**
- **A job's colour is not always the task's verdict.** Read the subject of a failure first.
- **"Authored and diagnostics-clean, not executed" is a legitimate result.** A **deselected** test
  is not a pass either.
- **Disk outranks the ledger.** **`tasks.meta.json` is not authority.**

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what throttle
it.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
  `pnpm` anything — **and `tests/verify/test_ledger_gen_property.py`, which names a registry
  execution.** `regenerate-truth-docs.yml` is the sanctioned route for the generators.
- **Cheap and encouraged:** file reads, `grep`, `get_diagnostics`; `ruff`/`mypy` on changed files;
  bounded scoped `pytest`; `spec_ledger_census`; the **six** cheap gates; `command_path_truth` and
  `ratchet_truth` over the committed tree (pure static readers); `replay_metrics` through its
  `measurers` seam with trace resolution real and the replay substituted;
  `doc_truth.documented_value` as a pure function; and **`gh` API reads — free, and the
  highest-yield evidence in this repo. Spend them first.**
- **`mypy --strict` over `tests/verify` or `tests/uplift` modules EXCEEDS a 120s command budget** —
  the closure drags `uplift/__init__` → `scipy`, numpy and hypothesis. Type-check changed
  **non-test** modules by dotted name (`-m scripts.audit.<mod>`, ~13s) and say plainly that the
  test modules were not checked. **No CI step type-checks `tests/`.** Mixing `scripts/audit/*.py`
  and `tests/**` in one invocation fails instantly with "Source file found twice".
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
  **unlimited.** Sub-agents that execute code: **exactly ONE at a time.**
- **Preferred flags:** `-q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`. Add
  `-x` when you want the first failure; omit it when you want the whole picture in one invocation,
  which is cheaper than two runs.
- **Count and report your real invocation count.** Session 5 used **nine** against a stated three;
  session 6 used **five**. **The bound is on scope and serialisation; the honesty obligation is on
  the count.**
- **Sweep before finishing, and after any cancelled or timed-out command.** Session 6 timed out
  twice and swept an orphaned `python` each time.

### Verification sweep

**Per wave** — only what that wave touched, plus **anything the last `uplift-verify` run reported
red**:

```powershell
python -m ruff check <wave's changed files>
python -m ruff format --check <wave's changed files>
python -m mypy --strict -m <dotted name of each changed non-test module> --no-incremental
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

Expected: **`0 / 0 / 0 / 2 / 1 / 0`** plus census 0. **Append `*> $null` and read
`$LASTEXITCODE`** — piping any of these through `Select-Object -First N` manufactures a non-zero
exit.

Reproduce CI's exact commands when claiming a CI step will pass:

```powershell
python -m ruff check packages/synapse_common/ agents/ orchestrator/ --output-format=github
python -m ruff format --check packages/synapse_common/ agents/ orchestrator/
python -m mypy --strict packages/synapse_common/
python -m mypy --strict orchestrator/ --exclude orchestrator/tests   # CI's ACTUAL step 8
```

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **`Select-Object -First N` on a native command makes `$LASTEXITCODE` non-zero.** The census
  printed `status: pass (exit 0)` while the shell reported 1. Re-run with `*> $null`.
- **A `ruff format --check` diff whose two sides look character-identical is a LINE-ENDING diff.**
  Eighth session running. `git ls-files --eol` reports `w/mixed`. Normalise to the file's
  **dominant** ending with Python at `newline=''` — and **count the WORKTREE bytes**, because the
  `i/` column is normalised (finding 33). It fired on **six** files in session 6.
- **`ruff`'s `SIM300` reads an upper-case attribute as a constant.** `assert arm.S == spec.x` is
  flagged a Yoda condition. Compare as a tuple; do not add a `noqa`.
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated.** Assign, then `foreach`.
- **PowerShell's `-f` operator rejects `{1,>6}`** — it throws per call while the loop continues, so
  it presents as a hang.
- **There are no heredocs.** `python - <<'PY'` is a parse error. Write a temp `.py` under `.tmp/`
  (git-ignored), run it, delete it. **Complex inline `python -c` breaks on quoting** too.
- **A recursive `Get-ChildItem` over this tree can exceed the 120-second command timeout.**
- **`git push` writes progress to stderr**, so PowerShell reports `NativeCommandError` and a
  non-zero `$LASTEXITCODE` on a **successful** push. Read the `old..new ref` line.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental` after any
  config change; incremental is legitimate when no config moved, and much faster.
- **`git log -1 -- <file>` is last-touch, not authorship.**
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** `Get-Content -Raw`
  decodes with the ANSI codepage and `Set-Content -Encoding utf8` adds a **BOM**. `>` writes
  **UTF-16**. `Copy-Item` is a byte copy and is safe. **Verify bytes, never the console.**
- **`git status` over-reports.** Trust `git diff`, stage precisely, `git check-ignore -v` first.
- **Identify a CI run by `head_sha`, NEVER by timestamp.**
- **`git commit -F` a temp file** for any message longer than a line.
- Suppress twin logging in any engine-driving probe or the output floods, **and route the factory to
  stderr if the stream matters.**
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks pre-existing errors
  under `uplift/`. Its ruff hook is also the only thing that would lint the trees CI never reads, so
  **the two mitigations are mutually exclusive.**
- Python 3.14.0, **mypy 1.19.1** locally against CI's unpinned `mypy>=1.10.0,<2.0`, pytest 8.4.2,
  hypothesis 6.151.11, jsonschema 4.26.0. `gymnasium` absent. `gh` 2.82.0, authenticated.
  **Repository is PUBLIC — Actions minutes are unmetered on standard runners.**

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). **Do not assert a total** (CF-13). And note
  conflict O: the rule is enforced over a scope that contains none of its 56 violations.
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`; its fast
  step only `tests/uplift tests/verify`. **A slow-marked test outside those four paths is selected
  by no job at all.**
- **Assert a clause unconditionally** rather than wrapping it in a tolerated-exception disjunct.
  **Prove a refusal path by construction**, and **assert non-emptiness** wherever a subset or
  "nothing bad happened" clause could be satisfied by an empty set.
- **Derive numbers; flag the irreducible choice.** A knob with a self-serving sign gets a
  `ratchets.json` direction; one without gets none, and inventing one is fabrication.
- **`set -o pipefail` in any `run:` block that pipes a gate or a measurement.**
- Type hints everywhere (`mypy --strict`); Pydantic v2 `ConfigDict(frozen=True)` for recorded facts;
  `structlog`, never `print()`, in library code; canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`; `encoding='utf-8'` on **every**
  `read_text` (E-S13-07); ASCII-only console output; lines <= 100 characters.
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, or any paid SDK.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS, and
  a **deselected** test is not a pass.

### The five same-commit couplings

1. A rename and its declaration.
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the
   job is genuinely eligible** (conflict G).
3. A schema change and every fixture that carries it. **Session 6: a new `Outcome` member and a new
   `Declaration` enum moved `_MARKER`, `exit_code_for`, `aggregate`, `_format`, the property's
   severity map and its expected-outcome mirror — all in one commit.**
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** **Check it rather than assume it** — it fired
   17→18 files (2q), 536→542 rows (2r-pre-c), 542→549 (session 3), did **not** fire on a `run:`-only
   edit whose step NAME did not change (session 4), fired on a `needs:` removal with 3 rows changed
   and zero added (session 5), and did **not** fire on a comment-only step edit (session 6).
5. The session ceiling lives in **one** place, `spec_ledger_census.DEFAULT_BATCH`.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** One commit **per wave**. A
  workflow change and its `gate_surface --write` share a commit; an ADR amendment shares the commit
  of the code it governs; documents describing two work streams go **last**.
- Prefer new commits over `--amend`. No force-push, no `--no-verify`, no interactive flags. Leave
  git config unchanged. **Push to the PR #84 branch, never to `main`.**

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

**Sessions 4, 5 and 6 together are the clearest demonstration yet of why that design matters.**
Checkpoint A produced a number that *would* have ended the project; the checkpoint's own machinery
made it possible to see the number was about the wrong comparator; the repair then required noticing
that the recorded fix would only have addressed half of it; and the first execution of the property
surface underneath it found eleven defects in tests nothing had ever run. **An instrument that can
end the project is only safe if you also check what it measured, check the fix you were handed, and
check that the suite around it has ever executed.**

**The pre-commitment, binding before the number is known:** if measured uplift is null or negative,
**it is reported as null or negative.** The floor stays at `0.0`, no headline is published as a
gain, and the result is written up as a finding — not reframed, not re-run at a different replicate
count until it moves. A null from a **validated** instrument on a **decision-relevant** world is
worth more than the tautological PASS it replaces.

Three guards on reading the result: a null while any objective KPI is recorded not observably
sensitive is **inconclusive**, not confirmation (task 10.5). No headline may be published while no
Power_Report describes the harness revision under measurement (task 17.3). And **a `material`
verdict on a point estimate with no dispersion is not a falsification** — nor is one on a comparator
the requirement does not name (conflict M).

---

## Session 6 handoff — regenerate this section each session

**Two commits plus the documents commit. NO leaf ticked, and the census is unchanged at
`140/63/2/75`.**

| Commit | Subject |
|---|---|
| `2b35c5a` | the swallow was hiding the command it swallowed — all nine fast-step failures |
| `d6443eb` | declare the unmeasurable floor, and give the declaration a falsifier |
| *(third)* | this prompt, `HANDOFF.md`, the ledger row, and tasks 11 / 27.5 |

**What was earned.** All nine `uplift-verify` failures repaired — **and the nine were eleven**, two
being `ExceptionGroup`s of two. One was a real gate defect whose shape is the pair R6.14 exists to
catch: on a `-`-prefixed Make recipe the gate reported the swallow and extracted **zero commands**.
Obstruction 2.5's owed disposition (b) landed, with the declaration in the configuration and a
prerequisite that **voids** it. Step 18 predicted exit 0 through the gate's own `measurers` seam.

**What was learned.** The job log is worth more than the job's colour: every mechanism was in the
falsifying example and none was in the summary line. Session 1's own `stryker-break` repair created
a red six sessions later because a four-site coordinated change moved two sites. And CF-13 is
enforced over a scope containing **none** of its 56 violations — a count four documents got wrong,
and which the first tool written to measure it also got wrong, by repeating the exact regex defect
one of the files it mis-flagged exists to warn about.

**What is blocked, and it is CI's.** Both commits' discharge. The fast step's colour, the slow
step's first execution, step 18's real verdict, and steps 19–23 — which have never executed on this
branch **or on `main`**.

**Verified at close:** six cheap gates **0/0/0/2/1/0**; census exit **0**, unchanged at
`140/63/2/75`; `pin_extractor_truth` **14/14/14**; `gate_surface --check` **0** with coupling 4
checked rather than assumed; 34 tests green at `dev` across five bounded serial `pytest`
invocations; `mypy --strict --no-incremental` clean on both changed non-test modules; lint/format
debt proven byte-identical at HEAD by materialising the blobs, **zero added**; every written file
uniform-ending, no BOM, no U+FFFD; process sweep clean.

**NOT verified, and must not be claimed:** that the fast step is green; the two
`test_ledger_gen_property.py` repairs; that step 18 exits 0; `quality-gates` steps 19–23; the slow
step and therefore the slow half of Properties 38–60; `mypy --strict` on the four changed test
modules; task 11's verdict.
