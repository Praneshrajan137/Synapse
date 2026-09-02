# NEXT SESSION PROMPT — decision-quality-proof

Paste everything from `## PROMPT — copy from here down` to the end of this file into a fresh session.

This document is regenerated at the close of every session. It carries six sessions of accumulated
findings because each one cost a session to learn, and because an agent that re-derives a known fact
spends its context on discovery instead of work.

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`. HEAD at handoff is **`5bcf42c`**, tree clean, branch **24 commits ahead of `main`**.

**Your batch this session is four leaf tasks: `27.2 27.3 27.4 27.5`.** They clear the last
obstruction between this spec and its own evidence. Read STEP 3 before you touch them — there is one
decision you must put to me first, and one thing you must NOT conclude from it.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**, the local compute budget. Highest
   precedence. Nothing below may be used to justify heating the laptop.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the cap, the three marks, the four
   checkpoints, the batch plan, the six cheap gates, the verification sweep, and the progress ledger.
   **Read the last three ledger rows (`2q`, `2r-pre`, `2r-pre-b`) in full**; they are where findings
   16–23 live.
3. `HANDOFF.md` (repo root) — the state of the tree, and **what is verified versus what is merely
   authored**. Its owed list opens with a blocking decision. Read that first.
4. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
5. `.claude/skills/synapse-engineer/SKILL.md` + `references/` (`14_invariants.md`,
   `testing_topology.md`, `spec_schema.md`, `adr_index.md`).
6. `.cursorrules` + `docs/cursor/*.md` — code conventions, agent pattern, domain models.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.5 and the amendment log.** Not needed for
   this batch, but needed the moment checkpoint A unblocks.
8. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
   and your worklist**; parent **27** is your batch.

**Two invariant numberings disagree between authorities.** `references/14_invariants.md` and
`.cursorrules` differ on I-6, I-8 and I-10. Authority 5 outranks authority 6. The invariants this
work cites — I-1, I-4, I-5, I-7 — agree in both.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict to
me rather than resolving it silently.** Eight have been surfaced (Conflicts A–H in `HANDOFF.md`), two
of them corrections to instructions a session was itself given. Expect more.

### STEP 2 — derive the batch. Do not trust any number written in prose.

```powershell
python -m scripts.audit.spec_ledger_census --files --next 10
```

That command **is** the census: leaf total, the three mark buckets, the CI-gated set derived from
`discharge:` lines, and the next authorable batch in ledger order. At handoff it reported **140 leaf
tasks: 57 done, 3 authored-pending-discharge, 80 open** (72 authorable, 8 CI-gated). `--files`
reports open tasks whose named artifacts already exist — read its `prior-art` lines before authoring.

**`--next` will offer you `12.1 12.2 …` and you must NOT take them.** Ledger order is not execution
order. `SESSION_PROTOCOL.md`'s batch table places session **2r** before session 2, and your batch is
2r's authorable half: `27.2 27.3 27.4 27.5`. Confirm that against the table and say so before
starting. If the table and the census disagree, the census is authoritative for *counts* and the
table for *order* — surface it, do not pick.

### STEP 3 — one decision to put to me FIRST, and one inference not to draw from it

**Finding 23: `workflow_dispatch` is unavailable from this branch.**

```
gh workflow run uplift.yml --ref feat/decision-quality-proof
-> HTTP 404: workflow uplift.yml not found on the default branch
```

`--ref` selects which ref's *code* executes; it does not make a workflow dispatchable. GitHub
requires the file on the **default branch** first. **`origin/main` carries 14 workflow files and
`uplift.yml` is not one of them.** `truth-gates.yml` is not either and still runs — because it
triggers on `pull_request`, and a PR runs the workflow as defined in its own head. **`workflow_dispatch`
has no equivalent escape.** `gh workflow list` shows the split exactly: `SYNAPSE Truth Gates` is
registered because it has run, while `uplift.yml` and `regenerate-truth-docs.yml` do not appear at
all, never having run.

**Unreachable until I decide:** checkpoint A (tasks 10.4, 11), checkpoint B (14), task 26.2's
regeneration, and tasks 22.3 and 25. Five CI-gated leaves plus the two `[~]` marks depending on them.
`SESSION_PROTOCOL.md`'s own definition of a checkpoint — "dispatch a workflow, read the output,
record the verdict" — is unexecutable as written.

**Put the five costed options in `HANDOFF.md`'s owed list to me and wait.** Do not change `main`. Do
not add a `push:` trigger to work around it. Do not fabricate a measurement.

**NOW THE INFERENCE YOU MUST NOT DRAW.** Finding 23 does **not** block your batch, and this was
verified rather than assumed: `ci.yml` fires on `pull_request: [main]`, `quality-gates` carries
`needs: NONE` and no `if:`, and `uplift-verify` carries `needs: quality-gates`. **Both are reachable
by pushing to the PR branch.** No dispatch is involved anywhere in tasks 27.2–27.5. Start them while
the decision is outstanding.

### STEP 4 — the work order

**Parent 27 is adopted debt: 56 `mypy --strict orchestrator/` errors, all from commit `e000258`,
none on `main`.** They gate `ci.yml::quality-gates` step 8, which gates `uplift-verify`, which is why
**Properties 38–60 have never executed in CI on this branch.** Every property this spec has written
is local evidence only until 27.5 closes. That is what this batch buys.

**Measured baseline at handoff — `56 errors in 17 files`:**

| code | n | code | n |
|---|---|---|---|
| `arg-type` | 24 | `import-untyped` | 4 |
| `unused-ignore` | 7 | `attr-defined` | 2 |
| `no-any-return` | 5 | `union-attr` | 2 |
| `type-arg` | 5 | `comparison-overlap` | 2 |
| `no-untyped-def` | 4 | `method-assign` | 1 |

**Take them in this order, and the order is load-bearing:**

**27.2 — the 24 `arg-type` errors, diagnosed per error rather than per pattern.** Task 27.1's group
was genuinely uniform: all 21 `call-arg` errors were one declaration's artifact, cleared by one line.
**Reading that as licence to batch-fix these is the exact over-generalisation that cost session 2p
three real Biome findings.** Classify each before repairing any.

**27.3 — the 26 remaining across eight codes.** Two specific notes. `import-untyped` (4) may not be
repairable here: `types-PyYAML` is deliberately not installed, because installing it unmasks seven
real pre-existing errors elsewhere that then block commits to files that do not contain them. If
these four are that gap, **the honest outcome is a recorded deferral naming the reason, not a
`# type: ignore`.** And `comparison-overlap` (2) deserves reading closely rather than silencing: a
comparison mypy proves can never be true is usually a real defect.

**27.4 — the `unused-ignore` errors LAST.** `warn_unused_ignores = true`, so every repair in 27.2 and
27.3 can both remove an ignore's justification and create a new unused one. Clearing them first means
clearing them twice, and the second pass looks like a regression. A genuinely unused ignore is
**deleted**, never re-narrowed to keep it alive.

**27.5 — confirm `uplift-verify` EXECUTED.** Not that it was skipped. Not that it reported nothing.
Push, then read the run. **This is a dependency boundary and your stop point** — it is a CI read, not
an edit, so the session ends whether or not the run is green.

#### FORBIDDEN REPAIRS. Each one names what it would destroy.

No error may be cleared by **giving an argument a default**, by **widening a type to `Any`**, by
**adding a `# type: ignore`**, or by **narrowing mypy's scope**. The first substitutes an unreviewed
value for a committed one; the second and third make the checker agree by asking it less; the fourth
deletes the gate. **If an error is genuinely a tooling artifact, repair the *declaration that misleads
the checker*, never the call sites that report it** — task 27.1 is the worked example, and
`HANDOFF.md`'s conflict F records why the instructed call-site repair would have put 21 unreviewed
numbers onto the I-5 confidence gate.

#### Determine ownership mechanically before filing anything as pre-existing

Two findings have already been misfiled as `main`'s and turned out to be this branch's.

```powershell
git log -1 --format='%h' -- <file>
git merge-base --is-ancestor <sha> main     # exit 1 => NOT on main => this branch's
gh run list --branch main --workflow '<name>' --limit 3
```

#### The mypy budget, and it is tight

`mypy --strict orchestrator/` is **category 2** under I-0 — bounded, but it saturates every core.
**You get four passes: one baseline, one after each of 27.2, 27.3, 27.4.** Run them serially, never
concurrently, and **capture each to a file so the per-code decomposition needs no re-run**:

```powershell
$log = "$env:TEMP\mypy-N.txt"
python -m mypy --strict orchestrator/ 2>&1 | Out-File -FilePath $log -Encoding utf8
```

Then group by the trailing `[code]` from the captured file. **Record the count after every task.** A
delta you cannot attribute per code is not a result.

### STOP CONDITIONS

- **Stop at 27.5.** It is a CI read and a dependency boundary. Do not continue into session 2.
- **Stop and report if a task's count does not move as predicted.** State the delta per code and what
  you checked. Session 2q's gate predicted `78 → 57` and measured **56**; proceeding was correct
  *because the shape of the deviation was proven*, not because the number was close.
- **Do not tick 10.4, 11, 14, 22.3, 25, 26.2 or 26.3.** All are dispatch-gated and blocked by
  finding 23.
- **Do not change `main`.** Finding 23's repair is mine.
- **Do not run `ledger_gen` or `readme_gen`** locally, in `--check` or `--write` form, for any reason.
- **Do not begin session 2's tasks** (12.1–13.7).
- Surface every new conflict rather than resolving it silently.

---

## THE THING THAT IS BLOCKING EVERYTHING

**`uplift-verify` has never run on this branch, so Properties 38–60 have never executed in CI.**

`ci.yml::uplift-verify` declares `needs: quality-gates`. `quality-gates` has never succeeded. The
history is worth holding because it is a study in how a silent gate fails:

- For two pushes it failed at **step 5** on a single **101-character line** in
  `orchestrator/consensus/protocol.py`, silently skipping **18 steps and 3 jobs**: `mypy --strict`
  ×3, the **I-1 no-paid-API check**, the **I-2 reward-isolation check**, the **C56 narrative-truth
  gate**, the unit tests, the coverage floors, plus `sprint6-verify` and `training-smoke`. **Nothing
  recorded it.**
- That line was fixed. The failure moved to **step 8, `mypy --strict orchestrator/`, 78 errors**.
- Session 2q cleared 22 of them with one line. **56 remain, so step 8 still fails.**

**Your batch is what closes this.** Until 27.5 is `[x]`, every `HANDOFF.md` must continue to say that
this spec's property surface is local evidence only.

---

## HARD-WON LESSONS. Twenty-three findings, each one paid for.

### On evidence and verification

- **An optional-evidence escape in a decision function is a hole, not a default.** `classify_regret`
  read `regret >= margin and (interval is None or excludes_margin)`. An absent interval was not a
  missing precondition — it was a **satisfied** one, so a bare point estimate could have falsified
  Finding 4 and ended a 132-task spec. **Grep for that shape** (`X is None or`, `if not Y: pass`,
  `getattr(o, 'f', True)`) in anything returning a verdict. Fix it at the **production boundary**, not
  by loosening the classifier — that keeps every pinned property intact.
- **Verify at the boundary you are claiming, not at a proxy for it.** "The lint step will pass" was
  claimed from a whole-tree local exit code polluted by CRLF. The claim was wrong.
- **Never generalise one proof to a population.** One of 40 local format errors was proven to be a
  line-ending artifact and that proof was extended to all 40. **Three were real.** If a claim covers
  N things, prove it over N or find the arithmetic that does. Session 2r-pre applied this
  deliberately: rather than trust one import path, it walked **all 9** first-party modules reachable
  from `uplift.regret` and proved `pydantic_settings` was the only gap.
- **A deferred verification pointed at a gated step is not a deferred verification.** "Let CI answer
  C63" nominated step 9, which was **skipped** behind step 5's failure. Name a check that cannot
  itself be skipped.
- **When a job fails, read what got SKIPPED behind it, not only what failed.**
  `gh api .../jobs` and list every step whose conclusion is `skipped`.
- **`heavy` fails what `dev` passes. Twice now.** `HYPOTHESIS_PROFILE=dev` draws **10 examples**.
  Re-verify anything load-bearing at `heavy` on one scoped file — **and say so when `heavy` is a
  no-op**, as it is for a test that uses no Hypothesis.
- **A stated gate's number can be wrong in the safe direction, and literalism would discard a correct
  repair.** 2q's revert condition was `78 → 57`; the measurement was **56**. Proceeding was right
  because the *shape* was proven: exactly two codes moved, both to zero, every other count identical,
  no new code, and the 22nd error's mechanism read from source. **Prove the shape of a deviation
  before accepting it.**
- **`getDiagnostics` returning nothing is inconclusive, not evidence** (R2.13). **A local red is not
  always a CI red, and a local green is not a CI green.**

### On gates reporting the wrong thing

- **The gate that fails is not always the gate that would tell you.** Finding 20: a pin with a dead
  document anchor makes `doc_truth` report a **`skip`**, and because the pin is `required: true`
  R1.4/R1.6 turn that into an `unavailable` aggregate — **C56 SKIP, not FAIL** — while
  `pin_extractor_truth` reports **15/15 green**, because it probes source extractors
  *"unconditionally, independent of whether the document anchor matched."* A reader would blame the
  regeneration. **Know which gate reads which side of a claim.**
- **A gate's non-zero exit is a claim about the *invocation* as much as the gate.** A PowerShell
  splatting bug (`$parts[1..0]` on a one-element array) made `workflow_shape_truth` report exit 2; it
  is 0 when invoked correctly. **Verify the command before believing the verdict.**
- **A SKIP is not milder than a FAIL for measurement purposes.** The falsification sweep reports
  `indeterminate` for any gate that does not PASS on its unmutated baseline, so a SKIP removes a gate
  from the measurement exactly as a FAIL does. **Doc drift costs measurement power, not just a red
  tick** — C56's drift made the sweep probe **7** checks instead of 8.
- **Never weaken a claim to make it safe.** Finding 20's pin could have stood today with
  `required: false`, which would not have touched C56. Rejected: **a pin that cannot fail is not a
  pin**, and downgrading a claim is the assertion-weakening R2.10 forbids. Parking a correct pin is
  honest; landing a toothless one is not.

### On install closures and CI mechanics

- **Read the install closure before trusting that a job can run its own subject. Twice now.**
  Defect 14: `uplift/contract.py` imports `scipy`, absent from `twin-regret`'s closure — routing one
  float through the validating reader would have crashed the measurement at import. Defect 22: the
  same job could not import the **twin**, because `pydantic-settings` is in every
  `agents/*/requirements.txt` and in neither `packages/requirements.txt` nor
  `packages/pyproject.toml`. Both found by reading, before a CI round trip paid for it.
- **Fix a closure narrowly. The broad fix is the dangerous one.** Adding a package to
  `packages/requirements.txt` widens the closure `truth-gates`, `quality-gates` and the regeneration
  job run in — and several registered checks report SKIP when an optional import is missing, so it
  can turn a SKIP into a PASS and **move the registry counts `doc_truth` pins**.
- **`workflow_dispatch` requires the workflow on the default branch; `pull_request` does not.**
  Finding 23. A PR runs the workflow as defined in its own head, which is why `truth-gates.yml` works
  from this branch and `uplift.yml` cannot be dispatched from it.
- **A workflow that has never executed is the I-7 shape.** `regenerate-truth-docs.yml` is authored,
  parses, resolves its declarations and carries no discarding construct — and proves nothing. Task
  26.1 is `[~]` for exactly that reason.

### On ownership and scope

- **Determine ownership mechanically, in three steps, before filing anything as "pre-existing."**
  Two findings had been filed as `main`'s and were **this branch's**: four Biome errors (all
  `5db5eb1`) and two Ruff errors plus ten format files (all `e000258`).
- **A `warn`-level finding co-reported beside a failure did not cause the failure.** Check the
  configured severity before attributing a red to a finding.

### On design documents and dependencies

- **Consult the design for the area you are touching before authoring — it may already own your
  work.** The interval estimator was fully designed at **E3.1** with a declared path, name, signature
  and property number.
- **A design can be wrong in mechanism, and a property test is what finds it.** E3.1 claimed sorting
  the resample *statistics* gives input-order invariance. It does not — the seeded index stream is
  fixed. Order-invariance needs the paired *differences* sorted **before** resampling. Both sorts are
  needed and they do different jobs.
- **When a workaround creates two readers of one artifact, pin them to each other with a test.**
- **Two documents that must agree and nothing comparing them is the `None == None` hole.** Session 2q
  landed a closure-parity test for exactly this, and mechanised a claim `rules.py` had made only in
  prose (`OrchestratorConfig().confidence_threshold == DEFAULT_CONFIDENCE_FLOOR`).

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open — not started. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

- **The `[~]` mark earned its existence.** Tasks 1.2/1.5 were reconciled from `[x]` because nothing
  had judged them. Then CI failed on Biome naming one finding → a repair claimed green → **it was not
  green**, there were four findings plus three more behind them → a second repair → green on the
  **third** run. An `[x]` at authoring time would have hidden two successive failed repairs.
- **Leave a half-landed task `[ ]`, not `[~]`, when the owed half is authoring blocked on another
  task.** A `discharge:` line naming a job would be false, and `[~]` stops the census offering the
  work. Precedent: task 15.2.
- **"Authored and diagnostics-clean, not executed" is a legitimate result.** "Should pass" reported as
  "passes" is an I-7 violation.
- **Disk outranks the ledger.** Session 1 opened with eight tasks implemented and unticked.
- **`tasks.meta.json` is not authority** — its `executionHistory` bulk-stamped every task within an
  eleven-second window.

### On the compute budget

- **The three generators are not equally priced, and this is the trap.** `gate_surface
  --write/--check` is pure workflow parsing, ~1s — **cheap, and it is the sixth gate in the sweep.**
  `ledger_gen` and `readme_gen` each execute the **entire Check_Registry in-process** (~900s local).
  A change that moves only the *workflow tree* can be regenerated locally; a change that moves a
  check's *status* cannot.
- **That ~900s figure is the LOCAL WINDOWS cost, and the asymmetry is the point.**
  `truth-gates.yml::truth-gates` does comparable work inside `timeout-minutes: 25` on a runner. That
  is why `regenerate-truth-docs.yml` exists: I-0 escalation step 1, taken literally.
- **The `biome` and `tsc` binaries in `frontend/node_modules/.bin/` may be run directly** on changed
  files or on `./src` — bounded, single-process, the analogue of `ruff`. **`pnpm` stays banned and
  `vitest` is banned outright.**

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what throttle it.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
  `pnpm` anything. **`regenerate-truth-docs.yml` is the sanctioned route for the middle two.**
- **Cheap and encouraged:** file reads, `grep`, `get_diagnostics`; `ruff`/`mypy` on changed files;
  **one** scoped `pytest` run; `spec_ledger_census`; the **six** cheap gates
  (`workflow_shape_truth`, `pin_extractor_truth`, `sweep_budget_truth`, `dataset_licence_truth`,
  `task_claim_truth`, `gate_surface`); the `biome`/`tsc` binaries on changed files; and **`gh` API
  reads** (network, no local compute — use them freely).
- **`mypy --strict orchestrator/` is category 2.** Four passes this session, serial, one at a time.
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
  unlimited. **Sub-agents that execute code: exactly ONE at a time.**
- **Preferred flags:** `-x -q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
- **Sweep before finishing.** List background processes; confirm none of yours survived; check for
  orphaned `python` / `node` / `chrome` explicitly. One `node` is Kiro's own ACP server.

### Verification sweep — run before closing any session

```powershell
python -m ruff check <changed files>
python -m ruff format --check <changed files>
python -m mypy --strict <changed python files>
$env:HYPOTHESIS_PROFILE='dev'
python -m pytest <changed test files> -q --tb=line -p no:randomly -m "not slow"
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
python -m mypy --strict orchestrator/
```

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **A `ruff format --check` diff whose two sides look character-identical is a LINE-ENDING diff.**
  Hit in three sessions running. Programmatic edits write LF into CRLF working-tree files;
  `git ls-files --eol <path>` then reports **`w/mixed`**. **Check it after every programmatic edit**
  and repair with Python at `newline=''`, normalising to the file's *dominant* ending — count first,
  because `uplift.yml` was 313 LF to 1 CRLF while `doc-number-pins.yaml` was 337 CRLF to 118 LF.
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** On PS 5.1
  `Get-Content -Raw` decodes with the ANSI codepage and `Set-Content -Encoding utf8` adds a **BOM**
  that Python's `read_text(encoding='utf-8')` does **not** strip. Splice with Python (`pathlib`,
  explicit `encoding='utf-8'`, `newline=''`) or with the editor tools. Then byte-verify:
  ```powershell
  $b=[System.IO.File]::ReadAllBytes($f); $t=[System.IO.File]::ReadAllText($f)
  "BOM=$($b[0] -eq 239 -and $b[1] -eq 187 -and $b[2] -eq 191)  U+FFFD=$($t.Contains([char]0xFFFD))"
  ```
- **PowerShell mangles the box-drawing characters Biome and several gates print.** Grepping for `━`
  finds nothing and looks like a clean run. **Read exit codes**, or use `--reporter=summary`.
- **PowerShell strips double quotes inside single-quoted `--jq` expressions.** Capture `gh api` output
  into a variable and use `ConvertFrom-Json`. `>` writes **UTF-16**; there are **no heredocs** — write
  commit messages to a temp file and use `git commit -F`.
- **Complex inline `python -c` in PowerShell breaks on quoting.** Write the script to a temp `.py`
  file, run it, delete it.
- **`git status` over-reports on this tree.** With `core.autocrlf=true` and `.gitattributes` pinning
  only `*.sh`/`*.sql`, a formatter that writes LF marks ~40 frontend files modified while `git diff`
  shows only real content changes. **Trust `git diff`, and stage precisely.**
- **`git add` refuses an ignored path SILENTLY.** `git check-ignore -v <paths>` first (exit 1 = not
  ignored). `.gitignore`'s bare `data/` once made a ticked task's deliverable unreachable by CI.
- **The local clock runs ~2h45m ahead** of the commit timestamps git and GitHub agree on. **Identify a
  CI run by `head_commit.message`, never by timestamp.**
- Suppress twin logging in any engine-driving probe or the output floods:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))`.
- `types-PyYAML` is not installed, so `mypy --strict` reports `import-untyped` on every yaml-importing
  module. **Do not run `pre-commit install`** — it installs the stubs and unmasks **seven** real
  pre-existing errors (was eight; `thresholds.py:118` was cleared in 2q) that block commits to files
  that do not contain them.
- Python 3.14.0, pytest 8.4.2, hypothesis 6.151.11, jsonschema 4.26.0. `gymnasium` absent.
  `frontend/node_modules` is installed. `gh` 2.82.0, authenticated.

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). A hardcoded value overrides the profile in **both**
  directions. **Do not assert a total** (CF-13 — the gate reports the count, the prose does not).
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`; its fast step
  collects only `tests/uplift tests/verify`. **A slow-marked test outside those four paths is selected
  by no job at all**, and one that must run in `quality-gates` must **not** be slow-marked.
- **Never weaken a generator or an assertion to make a property pass** (R2.10). Fix the subject — or,
  if the *precondition* was wrong, fix the precondition **and say which**.
- **Assert a clause unconditionally** rather than wrapping it in a tolerated-exception disjunct. "Or
  it raises" is a weak property. **Prove a refusal path by construction** — "no generated example
  triggered it" is not evidence a guard works.
- **Derive numbers; flag the irreducible choice.** A knob with a self-serving sign gets a
  `ratchets.json` direction; one without gets none, and inventing one is fabrication.
- Type hints everywhere (`mypy --strict`); Pydantic v2 `ConfigDict(frozen=True)` for recorded facts;
  `structlog`, never `print()`, in library code; canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`; `encoding='utf-8'` on **every**
  `read_text` (E-S13-07); ASCII-only console output; lines ≤ 100 characters (a single 101-character
  line gated 18 steps and 3 jobs across two pushes).
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, or any paid SDK.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS.
  Absence of proof is never a pass.

### The four same-commit couplings, with 2q's correction

1. A rename and its declaration.
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the job
   is genuinely eligible to be a required check.** `ineligibleEntry.reason` is a closed six-value enum
   with no "dispatch-only" member, so a `workflow_dispatch`-only job owes **none** (conflict G).
3. A schema change and every fixture that carries it.
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** **The fourth was missed twice** (tasks 5.6 and
   10.3): it cost C63 and cascaded into `ledger_gen`, `doc_truth`'s pinned counts and the README
   headline — four registered gates from one missed `--write`. **Check it rather than assume it**: 2q
   watched it fire (17→18 files, 370→378 steps) and 2r-pre watched it *not* fire on a `run:`-only edit
   to a non-anchor step, where `--check` stayed 0 and nothing was owed.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** A workflow change and its
  `gate_surface --write` share a commit; documents describing *two* work streams go **last**, so no
  message misdescribes its own diff.
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
outright. Both run *before* the work they gate. Most plans cannot reach a conclusion that
invalidates themselves.

**The pre-commitment, binding before the number is known:** if measured uplift is null or negative,
**it is reported as null or negative.** The floor stays at `0.0`, no headline is published as a gain,
and the result is written up as a finding — not reframed, not re-run at a different replicate count
until it moves, not held back pending a "better" configuration. A null from a **validated** instrument
on a **decision-relevant** world is worth more than the tautological PASS it replaces: before this
spec, C60 could only ever report SKIP, and a measured zero against a `0.0` floor exited 2. **A number
that cannot fail is not a number.**

Three guards on reading it: a null while any objective KPI is recorded not observably sensitive is
**inconclusive**, not confirmation (task 10.5). No headline may be published while no Power_Report
describes the harness revision under measurement (task 17.3). And **a `material` verdict on a point
estimate with no dispersion is not a falsification either** — the instrument now refuses to produce
one, and finding 16 is what ensures the verdict recorded is the one it produced.

**Your batch serves that directly.** Properties 38–60 are this spec's instruments, and not one has
ever executed in CI. Clearing 56 type errors is unglamorous work that converts the entire apparatus
from *asserted* to *observed*.

---

## Session 2r-pre handoff — regenerate this section each session

**Two sessions ran back to back: 2q authored, 2r-pre repaired what 2q's own close revealed.** Six
commits, branch **24 ahead of `main`**, HEAD **`5bcf42c`**, tree clean.

| Commit | Subject |
|---|---|
| `e1b274c` | the regeneration job + all three couplings |
| `d1c4dc7` | `Field(default=0.7, ge=0.0)` — 22 mypy errors, one line |
| `3715adc` | task 6 ticked, parents 26/27 registered, batch re-cut |
| `6d6360d` | the derived-margin pin **parked**, not landed (finding 20) |
| `a3b6dff` | `twin-regret` could not import the twin (finding 22) |
| `5bcf42c` | findings 22 and 23 recorded |

**What was earned.** Task **6** is `[x]` and **E1 is closed** — the survivor list was reviewed and
accepted, `C28/zero-a-floor` deferred to its owner, no mutation weakened. Parents **26** and **27**
are registered. `mypy --strict orchestrator/` went **78 → 56**, and the 22 cleared errors added no
number to the tree.

**What was prevented.** Three defects that would have fired later and looked like something else: a
pin that would have made C56 SKIP while C75 reported green (20); a job that could not import its own
subject (22); and a dispatch mechanism that does not exist from this branch (23).

**What is blocked, and it is mine.** Finding 23. Five costed options in `HANDOFF.md`'s owed list.
Until I choose, checkpoint A, checkpoint B and task 26.2 are unreachable — **but your batch is not.**

**Census at close: 140 leaf tasks, 57 done, 3 authored-pending-discharge, 80 open** (72 authorable,
8 CI-gated). The three `[~]` are **10.4** (checkpoint A), **26.1** (the regeneration job, never
executed) and **27.1** (the declaration fix, CI has not confirmed the count at its own scope).

**Verified at close:** six cheap gates **0/0/0/2/1/0**; census 0; `gate_surface --check` 0;
`workflow_shape_truth --check` 0; `pin_extractor_truth` 0 at **14/14**; all written files
byte-verified with no BOM and no U+FFFD; process sweep clean.

**NOT verified, and must not be claimed:** `uplift-verify`, and therefore **Properties 38–60**;
`regenerate-truth-docs.yml`, which has **never executed**; `ledger_gen`/`readme_gen`/`verify_claims`/
`doc_truth`, none run locally in any form; the five slow-marked `ConsensusProtocol` properties;
`vitest`; `_measure`'s wired interval path; and **the absolute CI value of the orchestrator error
count** — 56 is the local number, the local environment has no `types-PyYAML`, and only the delta and
the two vanished codes are stub-independent.
