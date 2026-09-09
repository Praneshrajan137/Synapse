# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **4** (2026-09-09).

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

### STEP 0 — CI RUNS AGAIN. Confirm it, then read the chain.

**The repository is public, which gives it unlimited standard-runner Actions minutes, and the
account-level block that ended sessions 2r and 3 is gone.** Do not re-litigate it; confirm it and
move on.

```powershell
git rev-parse --short HEAD                       # derive HEAD; never trust a document for it
git rev-list --count origin/main..HEAD
gh run list --branch feat/decision-quality-proof --limit 10 --json databaseId,headSha,workflowName,conclusion
```

**Then read the chain, because it is where the whole spec is stuck.** Get the `quality-gates` job's
step conclusions for the newest sha — not the run's colour, the step list:

```powershell
$j = gh api "repos/:owner/:repo/actions/runs/<id>/jobs" | ConvertFrom-Json
$qg = $j.jobs | Where-Object { $_.name -match 'Lint \+ Type Check' }
foreach ($s in $qg.steps) { "{0,3}  {1,-10} {2}" -f $s.number, $s.conclusion, $s.name }
```

**At handoff:** steps 1–17 **success** — including step 17 **C56**, cleared in session 4 — and the
failure at **step 18**, with 19–23 skipped. `uplift-verify` skipped. **Use a `foreach`, not a
pipeline: PowerShell 5.1's `ConvertFrom-Json` hands back the array unenumerated and a piped
`Where-Object` silently yields nothing.**

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the ceiling, wave discipline, the
   **barrier stop**, the three marks, the four checkpoints, the batch table, the six cheap gates, the
   progress ledger. **Read the last two rows (`3`, `4`) in full** — findings 30–38 live there. Its
   **checkpoint-A section carries a BLOCKING NOTE and steps 2–4 are SUSPENDED**; that note is the
   most important thing in the document right now.
3. `HANDOFF.md` (repo root) — the state of the tree, and **what is verified versus merely authored**.
   It opens with the two things that block everything. Read those first.
4. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
5. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
6. `.cursorrules` + `docs/cursor/*.md`.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.5 and the amendment log.**
8. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
   and your worklist**.

**Two invariant numberings disagree.** `references/14_invariants.md` and `.cursorrules` differ on
I-6, I-8 and I-10. Authority 5 outranks authority 6. The invariants this work cites — I-1, I-4, I-5,
I-7 — agree in both.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict
rather than resolving it silently.** Thirteen have been surfaced (A–M). **Five are corrections to
instructions a session was itself given.** Expect more, and expect them in the procedure you are
about to follow.

### STEP 2 — derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At handoff: **140 leaf tasks — 63 done, 2 authored-pending-discharge, 75 open** (69 authorable, **6**
CI-gated). `--next 30` offers `12.1 … 17.7` and names barriers **11** (30 of 30 follow) and **14**
(19 of 30 follow).

**The answer, which you should re-derive rather than copy: the batch DEPENDS ON BOTH.** Task 12's own
precondition is "checkpoint A has run and task 11's verdict is not `material`"; `15.1`–`17.7` are all
of E3, which checkpoint B can cancel. So the offer truncates to **11** (12.1–13.7) — and **task 11
still has no admissible verdict, so it truncates to zero.** See conflict M.

**For every barrier line, state in your opening whether the batch depends on it. An unanswered
barrier is a stop, not a warning.**

### STEP 3 — the two things that block everything, and what you may do about them

Both are the operator's. **Bring them up first; do not pick one and start.**

#### A. CONFLICT M — the regret instrument can currently return only `material`

Checkpoint A's first measurement succeeded (run `34366766968`, 200/200 replicates,
`regret = 8.937888952967558`, interval `[8.916389405913677, 8.958204644600675]`,
`verdict: unavailable`). **Committing the margin at the value its own rule derives (`0.40`) makes run
2 return `material`, which task 11 reads as "Finding 4 falsified, STOP, re-cut R5."**

**That verdict would be wrong twice over.** The baseline arm is `NoOpRecordingPolicy` with
`restock_threshold: 0.0`, so the measured quantity is the **no-op's** regret, not the `(s, S)` regret
R5.1 names — `Par_Level_Reorder` is another spec's unlanded precondition. And **`regret` and
`comparator_headroom` are the same expression**, so `must_be_below_measured_headroom` admits exactly
the margins below the regret they will be judged against: **every margin in D2.5's own bracket forces
`material` by construction.**

**Do not commit `materiality_margin.value`. Do not graduate the parked pin. Do not run the second
label.** Two repairs, costed in task 11: land `Par_Level_Reorder`, or give the guard an independent
bound. **A verdict that cannot be anything else is not a verdict.**

#### B. OBSTRUCTION 2.5 — step 18 cannot pass on a hosted runner

`tier_routing_accuracy` measures cleanly at `1.0000 >= 0.8000` over 200/200 traces.
`kv_cache_hit_rate` reports `UNAVAILABLE — synapse_ollama_cache_hit_rate has no samples — the replay
took no cache observation (Ollama offline)`, so the gate exits 2 rather than call an unmeasured floor
a pass. **The gate is right; the claim it was built to close is not measurable in CI.** It is
`main`'s and had never executed anywhere.

Three dispositions in task 27.5. **Splitting the step** — measurable floor gates, unmeasurable one
declared SKIP with its reason, the same shape as C74's honest SKIP — is the only one consistent with
precedent. **Do NOT lower `kv_cache_hit_rate`** (R2.10 assertion weakening) **and do NOT add
`continue-on-error`** (it re-creates finding 35 two steps away).

#### Also owed, and smaller

- **A second regeneration**, owed by the generator order itself: `ledger_gen` projects a top-level
  execution in which C56 is evaluated, and C56 reads the README that `readme_gen` rewrites
  *afterwards*. So `CURRENT.md`'s `C56` row is stale and `ledger_gen --check` is expected red. The
  durable repair swaps the two `--write` steps and edits the enforcement spine — the operator's.
- **The `twin-regret` artifact is not canonical JSON.** 215 MB of `structlog` flood with the report
  on the last line; `json.load` fails while `blocking-steps.yaml` declares canonical JSON. Tasks
  17.x, 22.3 and 25 read uplift artifacts with a parser.
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35). Extending it is a
  registered-check change.
- **CI's ruff scope** excludes nine trees including `uplift/` and `digital_twin/`: **530 lint
  findings, 254 format findings (upper bound).** Widening it re-closes `quality-gates` at step 5.

### STEP 4 — how a session is actually run

**Three waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit.
2. **Write findings into `tasks.md` and the ledger as you find them.**
3. **Delegate reading, never execution.** Unlimited parallel sub-agents for reading, writing and
   analysis; **exactly ONE** that executes code. Keep every command in the main agent.
4. **Re-read the authority file for each wave's area before starting it.**

**Spend `gh` reads first.** They are free under I-0, and session 4 discharged two leaves on about
twenty of them with **zero** local `pytest` invocations and **zero** wide `mypy` passes. Four wide
`mypy --strict orchestrator/` passes per session remain the ceiling; one bounded `pytest` per wave,
at most three, serial.

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
git show origin/main:<file> > scratch           # then EXECUTE main's version if it matters
```

---

## STOP CONDITIONS

- **Stop and bring conflict M and obstruction 2.5 to the operator before authoring.** Both gate
  everything; neither is a session's to decide.
- **Stop at any barrier the census names that the batch depends on.** Say which.
- **Stop and report if a count does not move as predicted.** State the delta **per code** and what
  you checked.
- **Do not tick 11, 14, 21, 22.3, 25 or 27.5** without the naming job's own verdict.
- **Do not commit `materiality_margin.value`.** Conflict M.
- **Do not change `main`.**
- **Do not run `ledger_gen` or `readme_gen`** locally, in `--check` or `--write` form, for any reason.
- **Do not pad a session toward thirty.**
- Surface every new conflict rather than resolving it silently.

---

## THE THING THAT IS BLOCKING EVERYTHING

**`uplift-verify` has still never run, so Properties 38–60 have never executed in CI.**

| # | Obstruction | State |
|---|---|---|
| 0 | the runner itself — billing | **CLEARED** — repository made public |
| 1 | step 8 mypy strict (orchestrator) | **CLEARED** (2r), re-confirmed `success` |
| 2 | step 17 **C56** narrative-truth | **CLEARED** (26.2 / 26.3) — first PASS on this branch |
| **2.5** | **step 18 golden-trace replay** | **RED, STRUCTURAL, was in no recorded chain** |
| 3 | step 19 unit tests → `test_cognition_phase` | **unknown** — skipped behind 18; repair on disk, unjudged |
| 4 | steps 20–22 coverage / spec coverage / contract | **unknown** |

**Session 2r's lesson has fired three times: clearing a gate reveals what it was shielding, and the
depth is unknown until each layer clears.** Session 4 cleared two and found two more. **No single
clearance licenses a claim about the job at the end.**

---

## HARD-WON LESSONS. Thirty-eight findings and thirteen conflicts, each one paid for.

### The seven habits that caught the most

1. **A gate that has never executed is not evidence, and the cheapest way to learn what a job does is
   to run it once.** Every one of session 4's four material defects was invisible to reading and
   appeared the instant something ran: a closure proof that walked the wrong graph, a step that
   swallowed its subject's exit status, a generator order that produced a document stale on arrival,
   and a committed ledger recording a Windows path error as a check's finding. **Three sessions of
   careful reading had passed over all four.**
2. **Verify at the boundary you are claiming, not at a proxy for it.** Conflict I: three authority
   files said a baseline was measured "at CI's exact command"; no workflow runs that command.
3. **Read the procedure against the tree, not against its own table of contents.** Conflict L: the
   batch table said "reachable by labelling" while the procedure below it still instructed a
   404-returning dispatch. **A table and its procedure can disagree, and the table is the one people
   update.**
4. **Reproducibility is not relevance.** The 56-error figure reproduced per code, first try — and
   described a command no gate runs.
5. **Prove the SHAPE of a deviation, not just its size.** Session 3 predicted the gate-surface delta
   (`542 → 549`, +7 from one placeholder row expanding into eight) *before* running `--write`.
6. **Never generalise one proof to a population.** One of 40 format errors was proven a line-ending
   artifact and that proof was extended to all 40. **Three were real.**
7. **Read what got SKIPPED behind a failure, not only what failed.** One 101-character line once
   gated 18 steps and 3 jobs.

### On verdicts and assertions that cannot move

- **A number that cannot fail is not a number — AND a verdict that cannot be anything else is not a
  verdict.** Conflict M is the second form: `must_be_below_measured_headroom` checks the margin
  against the very quantity being judged, so every admissible margin forces `material`. **When you
  add a guard, ask what it is bounding the subject AGAINST, and whether that thing is independent of
  the subject.**
- **An assertion that cannot fail is not an assertion.** `comparison-overlap` caught two (finding
  26), and session 3 nearly created a third in its own repair: filtering a call list and asserting
  the remainder is a subset of a declared set is **vacuous** when the remainder is empty. Assert
  non-emptiness too.
- **Repair a stale assertion by PARTITIONING, not FILTERING.** A filter makes the test pass and
  silently discards what the assertion protected.
- **A test can assert nothing at all.** `test_protocol.py::test_tier1_skips_debate` contains only
  comments.
- **An optional-evidence escape in a decision function is a hole, not a default.** Grep for
  `X is None or`, `if not Y: pass`, `getattr(o, 'f', True)` in anything returning a verdict.
- **A pin that cannot fail is not a pin.** Finding 20's pin could have stood with `required: false`.
  **Parking a correct pin is honest; landing a toothless one is not.**
- **Never weaken a generator, an assertion or a floor to make something pass** (R2.10). Fix the
  subject — or, if the *precondition* was wrong, fix the precondition **and say which.**

### On gates reporting the wrong thing

- **An unguarded shell pipeline discards its subject's exit status, and `workflow_shape_truth` cannot
  see it** (finding 35). `DISCARDING_CONSTRUCTS` is four literals; a pipeline is none of them. Use
  `set -o pipefail` in any `run:` that pipes a gate or a measurement.
- **A document generated on the wrong machine can record an environment error as a finding and hide
  the real ones behind it** (finding 37). The committed ledger gave C44's detail as a Windows
  `FileNotFoundError`, masking three liveness violations.
- **The gate that fails is not always the gate that would tell you.** A pin with a dead document
  anchor makes `doc_truth` report a **`skip`** — C56 SKIP, not FAIL — while `pin_extractor_truth`
  reports green, because it probes the source side only.
- **A verdict is a claim about its own derivation.** A splatting bug made a gate exit 2 when it is 0;
  a stale mypy cache kept reporting cleared errors (`--no-incremental` after any config change).
- **An "unparsable" rendering can be the honest answer** (finding 30): `gate_surface` cannot parse
  `contains(...labels.*.name, 'x')` and renders `CONDITIONAL | unparsable if:` — already true of
  `twin-regret` in the C63-green surface. **Check the precedent beside your row.**
- **`UNAVAILABLE` from a floor with no measurement is the gate working, not failing** (obstruction
  2.5). The repair is to declare the floor unmeasurable with its reason, never to lower it.
- **A SKIP is not milder than a FAIL for measurement.** The sweep reports `indeterminate` for any
  gate that does not PASS on its unmutated baseline, so **doc drift costs measurement power** — C56's
  drift made the sweep probe 7 checks, and clearing it returned the set to **8**.
- **A local red is not always a CI red, and a local green is not a CI green.**

### On scope, ownership, adoption and closures

- **CI's scope is not the tree's scope, and the gap is measured.** `ruff` covers
  `packages/synapse_common/ agents/ orchestrator/` **only** — 530 lint / 254 format findings sit in
  the nine trees it never reads, including `uplift/` and `digital_twin/`. `mypy` step 8 excludes
  `orchestrator/tests`; step 9 is `continue-on-error: true`.
- **Read the install closure before trusting a job can run its own subject. Three times now.**
  Defect 14 (`scipy`), defect 22 (`pydantic-settings`), and finding 36 — **the closure proof must
  start at the command the job runs**, because `python -m pkg.mod` executes `pkg/__init__.py` first
  and a walk from `pkg.mod` never sees it.
- **Fix a closure narrowly.** Widening `packages/requirements.txt` can turn a SKIP into a PASS and
  **move the registry counts `doc_truth` pins.**
- **`workflow_dispatch` requires the workflow on the default branch; `pull_request` does not.** And
  **a mechanism is not reachable until its trigger exists** — finding 34: both labels were committed
  without ever being created.
- **When you add a trigger, the GUARD is the load-bearing half.** A deny-list is **fail-OPEN** against
  a new trigger. Use an allow-list naming its events and **verify by truth table over every event ×
  input × label combination** — reading caught none of the three defects that method found, and the
  live run then confirmed **non-interference** between two label mechanisms (finding 38).
- **Do not adopt another owner's debt unilaterally**, but record the diagnosis so it is not
  re-derived. Parent 27 and `test_cognition_phase` were each adopted by *explicit* operator decision.
- **A workflow that has never executed is the I-7 shape, and *reachable* is not *run*.**

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

- **A `[~]` graduates on the job's own verdict, never on a local run.** 26.2 and 26.3 became `[x]` in
  session 4 on `regenerate-truth-docs.yml`'s and `truth-gates.yml`'s own output.
- **A `discharge:` line can name TWO subjects.** 26.1 stays `[~]` because its second — the
  closure-parity property at `ci.yml::uplift-verify`'s fast step — still has not run.
- **A job's colour is not always the task's verdict.** 26.3's two stated conditions were both read
  from `truth-gates.yml`'s own run while that job was red on C44/C69 — pre-existing, other subjects.
  **Read the subject of a failure before treating it as yours.**
- **Leave a half-landed task `[ ]`, not `[~]`, when the owed half is blocked on another task.**
- **"Authored and diagnostics-clean, not executed" is a legitimate result.** "Should pass" reported
  as "passes" is an I-7 violation.
- **Disk outranks the ledger.** **`tasks.meta.json` is not authority.**

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what throttle it.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
  `pnpm` anything. **`regenerate-truth-docs.yml` is the sanctioned route for the middle two, it is
  reachable by the `regenerate-truth-docs` label, and it is now proven to work.**
- **Cheap and encouraged:** file reads, `grep`, `get_diagnostics`; `ruff`/`mypy` on changed files; one
  bounded `pytest` per wave; `spec_ledger_census`; the **six** cheap gates; and **`gh` API reads —
  free, and the highest-yield evidence in this repo. Spend them first.**
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
  **unlimited.** Sub-agents that execute code: **exactly ONE at a time.**
- **Preferred flags:** `-x -q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
- **Sweep before finishing, and after any cancelled or timed-out command.** Session 4 hit two and
  checked both: `python` count `0`. One `node` is Kiro's ACP server; `chrome` predating your first
  command is the operator's browser; a `python` running `snow.exe` from
  `AppData\Local\dataforge-automation` is a different tool's, not yours.

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

Expected: **`0 / 0 / 0 / 2 / 1 / 0`** plus census 0. **`pin_extractor_truth` must report 14 declared,
not 15** — 15 means the parked derived-margin pin was moved into `pins:`, which conflict M forbids.

Reproduce CI's exact commands when claiming a CI step will pass:

```powershell
python -m ruff check packages/synapse_common/ agents/ orchestrator/ --output-format=github
python -m ruff format --check packages/synapse_common/ agents/ orchestrator/
python -m mypy --strict packages/synapse_common/
python -m mypy --strict orchestrator/ --exclude orchestrator/tests   # CI's ACTUAL step 8
```

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **A `ruff format --check` diff whose two sides look character-identical is a LINE-ENDING diff.** Six
  sessions running. `git ls-files --eol` reports `w/mixed`. Normalise to the file's **dominant**
  ending with Python at `newline=''` — and **count the WORKTREE bytes**, because the `i/` index column
  is normalised and reads `lf` on a file whose worktree is 140 CRLF / 51 LF (finding 33).
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated**, so
  `gh ... --json | ConvertFrom-Json | Where-Object {...}` silently yields nothing. Assign to a
  variable and `foreach`. **`gh label create` prints nothing on success** — verify with `gh label list`.
- **PowerShell's `-f` operator rejects `{1,>6}`** — `>` is not a .NET alignment character; it throws
  per call while the loop continues, so it presents as a hang.
- **A recursive `Get-ChildItem` over this tree can exceed the 120-second command timeout.** Use the
  search tooling or a temp `.py`.
- **`git push` writes progress to stderr**, so PowerShell reports `NativeCommandError` and a non-zero
  `$LASTEXITCODE` on a **successful** push. Read the `old..new ref` line.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental`.
- **`git log -1 -- <file>` is last-touch, not authorship.** Use `git cat-file -e origin/main:<f>` then
  `git diff origin/main -- <f>`, and execute `main`'s version when it matters.
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** `Get-Content -Raw` decodes
  with the ANSI codepage and `Set-Content -Encoding utf8` adds a **BOM** Python's
  `read_text(encoding='utf-8')` does not strip. `Get-Content` also *displays* em dashes as mojibake
  while the file is clean — **verify bytes, never the console**. `Copy-Item` is a byte copy and is safe
  for installing a generated artifact:
  ```powershell
  $b=[System.IO.File]::ReadAllBytes($f); $t=[System.IO.File]::ReadAllText($f)
  "BOM=$($b[0] -eq 239 -and $b[1] -eq 187 -and $b[2] -eq 191)  U+FFFD=$($t.Contains([char]0xFFFD))"
  ```
- **PowerShell mangles em dashes and box-drawing characters**, so `Select-String` on a CI step name
  containing one finds nothing and looks like a clean run. Match an ASCII substring.
- **`$LASTEXITCODE` is unreliable after a native command is piped through `Select-String`.** Re-run
  with `*> $null`.
- **PowerShell strips double quotes inside single-quoted `--jq`.** Capture `gh api` into a variable.
  `>` writes **UTF-16**; there are **no heredocs** — `git commit -F` a temp file.
- **Complex inline `python -c` breaks on quoting.** Write a temp `.py`, run it, delete it.
- **`git status` over-reports.** Trust `git diff`, stage precisely, `git check-ignore -v` first
  (exit 1 = not ignored).
- **Identify a CI run by `head_sha`, NEVER by timestamp**, and check the run for the sha
  `git rev-parse` gives you, not the one a document names.
- Suppress twin logging in any engine-driving probe or the output floods:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))`. **This
  is also the open repair for the 215 MB `twin-regret` artifact.**
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks seven pre-existing
  errors under `uplift/`. Its ruff hook is also the only thing that would lint the trees CI never
  reads, so **the two mitigations are mutually exclusive.**
- Python 3.14.0, **mypy 1.19.1** locally against CI's unpinned `mypy>=1.10.0,<2.0`, pytest 8.4.2,
  hypothesis 6.151.11, jsonschema 4.26.0. `gymnasium` absent. `frontend/node_modules` installed.
  `gh` 2.82.0, authenticated. **Repository is PUBLIC — Actions minutes are unmetered on standard
  runners.**

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). **Do not assert a total** (CF-13).
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`; its fast step
  only `tests/uplift tests/verify`. **A slow-marked test outside those four paths is selected by no
  job at all.**
- **Assert a clause unconditionally** rather than wrapping it in a tolerated-exception disjunct.
  **Prove a refusal path by construction.**
- **Derive numbers; flag the irreducible choice.** A knob with a self-serving sign gets a
  `ratchets.json` direction; one without gets none, and inventing one is fabrication. **A version
  bound with no committed antecedent is a choice and must say so** — `scipy>=1.11,<2.0` is the
  worked example.
- **`set -o pipefail` in any `run:` block that pipes a gate or a measurement.**
- Type hints everywhere (`mypy --strict`); Pydantic v2 `ConfigDict(frozen=True)` for recorded facts;
  `structlog`, never `print()`, in library code; canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`; `encoding='utf-8'` on **every**
  `read_text` (E-S13-07); ASCII-only console output; lines ≤ 100 characters.
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, or any paid SDK.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS.

### The five same-commit couplings

1. A rename and its declaration.
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the job
   is genuinely eligible.** `ineligibleEntry.reason` is a closed six-value enum with no
   "dispatch-only" or "label-conditioned" member, so such a job owes **none** (conflict G).
3. A schema change and every fixture that carries it.
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** **Check it rather than assume it** — it fired
   17→18 files (2q), 536→542 rows (2r-pre-c), **542→549 (session 3, shape predicted first)**, and did
   **not** fire on a `run:`-only edit to an anchor step whose NAME did not change (session 4,
   measured). **A trigger-only change with no new step still fires it**, because the job's
   per-context row changes and its placeholder step row expands.
5. The session ceiling lives in **one** place, `spec_ledger_census.DEFAULT_BATCH`.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** One commit **per wave**. A
  workflow change and its `gate_surface --write` share a commit; documents describing two work
  streams go **last**.
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

**Session 4 is the clearest demonstration yet of why that design matters.** Checkpoint A produced a
number that *would* have ended the project, and the checkpoint's own machinery — the interval, the
headroom guard, the comparator field in the artifact — is what made it possible to see that the
number was about the wrong comparator. **An instrument that can end the project is only safe if you
also check what it measured.**

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

## Session 4 handoff — regenerate this section each session

**Three commits plus the documents commit. Two leaves discharged on CI's own verdict.**

| Commit | Subject |
|---|---|
| `245d0dc` | `twin-regret` reported success while measuring nothing — `set -o pipefail` + `scipy` |
| `0c0e971` | conflict M: the instrument can only return `material`, on the wrong comparator |
| `2be5a96` | the regenerated ledger and README headline (26.2's reviewed artifact) |
| *(fourth)* | this prompt, `HANDOFF.md`, the ledger row, and 26.2 / 26.3 ticked |

**What was earned.** **26.2** and **26.3** are `[x]`. **C56 PASSES for the first time on this
branch.** `regenerate-truth-docs.yml` executed for the first time ever, nine steps green. Checkpoint
A produced its first real measurement. Census `140/61/2/77` → **`140/63/2/75`**, CI-gated `8` → `6`.

**What was prevented.** Committing `0.40` and reading the resulting `material` as the end of this
project. That was the next mechanical step in the standing work order.

**What is blocked, and it is the operator's.** Conflict M's two repairs; obstruction 2.5's three
dispositions; the second regeneration; the artifact's JSON shape.

**Verified at close:** six cheap gates **0/0/0/2/1/0**; census exit **0** at `140/63/2/75`;
`pin_extractor_truth` **14/14**; C63 and C64 **0**; the registry verdict line with **C56 absent**;
the sweep's probeable set back to **8** with `0 indeterminate`; every written file uniform-ending,
no BOM, no U+FFFD; process sweep clean.

**NOT verified, and must not be claimed:** `uplift-verify`, and therefore **Properties 38–60**;
`quality-gates` steps 19–23; the `test_cognition_phase` repair **in CI**; task 11's verdict;
`ledger_gen`/`readme_gen`/`verify_claims`/`doc_truth`, not run locally in any form; the
document-anchor side of the parked pin; whether any of the 254 `ruff format` findings are real.
