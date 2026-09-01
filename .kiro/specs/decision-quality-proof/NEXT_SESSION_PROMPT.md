# NEXT_SESSION_PROMPT.md

**Paste the whole of this file as your first message in a new session.** It names no task batch,
because the agent derives that from the ledger. Regenerate only the `## Session N handoff` section at
the end of each session; everything above it is standing law and grows only when a session learns
something that would have changed its own behaviour.

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`. Work is batched: **at most TEN leaf tasks this session, fewer if you reach a
dependency boundary first. Then stop and tell me to open a new one.**

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**, the local compute budget. Highest
   precedence. Nothing below may be used to justify heating the laptop.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the working agreement: the cap, the
   three marks, the four checkpoints, the batch plan, the verification sweep, the materiality-margin
   rule, and the progress ledger.
3. `HANDOFF.md` (repo root) — the state of the tree as of the last session: defects found, decisions
   taken, and **what is verified versus what is merely authored**.
4. `CLAUDE.md` — the operating manual: the 14 invariants, the honesty contract, the gate registry,
   the `E-S*` hard-won lessons, deploy-truth rules.
5. `.claude/skills/synapse-engineer/SKILL.md` + `references/` (`14_invariants.md`,
   `testing_topology.md`, `spec_schema.md`, `adr_index.md`).
6. `.cursorrules` + `docs/cursor/*.md` — code conventions, agent pattern, domain models.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — the Decision_Relevance_Record this phase is
   executed against. **Read D2.5 and the amendment log.**
8. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
   and your worklist**.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict to
me rather than resolving it silently.** Five have been surfaced so far (Conflicts A–E in
`HANDOFF.md`); expect more.

### STEP 2 — derive the batch. Do not trust any number written in prose.

```powershell
python -m scripts.audit.spec_ledger_census --files --next 11
```

That command **is** the census: leaf total, the three mark buckets, the CI-gated set derived from
`discharge:` lines, and the next authorable batch in ledger order. `--files` reports open tasks whose
named artifacts already exist — read its `prior-art` lines before authoring anything.

Then tell me the tasks you are taking and confirm they match `SESSION_PROTOCOL.md`'s batch table. If
they do not, say so and explain why before proceeding. **If the next thing in the plan is a checkpoint
(A, B, C or D), it is an operator action, not yours to author — tell me and stop.**

### STEP 3 — the work order. Checkpoint A is still open.

**There is no authoring owed before checkpoint A.** In order:

1. **Take the survivor list to me.** It is already measured and recorded under task 6 and in
   `HANDOFF.md`: `DECLARED=14 FALSIFIED=6 PASS_ELIGIBLE=6`, `PROBED=16 UNPROVEN=0`, and **exactly one
   survivor — `C28/zero-a-floor`, the disclosed one.** Task 6 stays `[ ]` until I have reviewed it.
   **Never weaken a mutation to clear a survivor.**
2. **Get a decision from me on the `readme_gen` escalation.** C56 is red on README headline drift
   (README claims `51/3/10/64`; the suite reports `56`-era counts). It is **not** this spec's drift —
   it is session 1's C73/C74/C75 registrations never regenerated — but it is now *measured* as owed,
   not predicted. Repair order is fixed: `gate_surface --write` (**done**), then `ledger_gen --write`,
   then `readme_gen --write`. The last two are **~15 minutes of full-core CPU each** and are
   category-3/4 under I-0, so they need my explicit yes with the duration stated.
3. **Get a decision from me on the 78 `mypy --strict orchestrator/` errors.** They are the single
   largest obstacle in the tree and they are **not this spec's to fix** — see "The thing that is
   blocking everything" below.
4. **Dispatch the regret measurement alone:**
   ```powershell
   gh workflow run uplift.yml --ref feat/decision-quality-proof --field job=twin-regret
   ```
   Then read `regret`, `interval_low`/`interval_high`, `comparator_headroom`, `margin_rule`,
   `margin_rule_derives` and `interval_excludes_rule_margin` from `artifacts/uplift/twin-regret.json`.
5. **Instantiate `materiality_margin.value` FROM THE COMMITTED RULE**
   (`service_points * 0.01 * weights.unmet_service`), record the measured headroom it was checked
   against, and pin the derived value. `policy.py::materiality_margin` will **refuse** a value the
   rule does not produce — that is intended, not a bug. Discharges task **10.4**, the last `[~]`.
6. **Record task 11's verdict** against `SESSION_PROTOCOL.md`'s four-value table, with evidence, then
   branch:
   - `material` → **STOP.** Finding 4 is falsified. Re-cut R5 (R5.3, R5.4) and report it plainly.
     **This is a success of the method.** Do not begin task 12.
   - `inconclusive` → **PROCEED** to session 2: `12.1 12.2 12.3 12.4 13.1 13.2 13.3 13.4 13.5 13.6
     13.7` (eleven; 13.7 is what makes checkpoint B reachable).
   - `sub-margin` → confirms Finding 4. Unreachable today by construction.
   - `unavailable` → **the measurement did not happen.** Say so; do not proceed on it.

**STOP CONDITION:** at most eleven authoring tasks, and stop earlier at a dependency boundary. Then
run the verification sweep, overwrite `HANDOFF.md`, append one progress-ledger row (**never edit a
past row**), regenerate this file's handoff section, and tell me to open a new session.

---

## THE THING THAT IS BLOCKING EVERYTHING

**`uplift-verify` has never run on this branch, so Properties 38–60 have never executed in CI.**

`ci.yml::uplift-verify` declares `needs: quality-gates`, and `quality-gates` has never succeeded. For
two pushes it failed at **step 5** on a single **101-character line** in
`orchestrator/consensus/protocol.py` — which silently skipped **18 steps and 3 jobs**: `mypy --strict`
×3, the **I-1 no-paid-API check**, the **I-2 reward-isolation check**, the **C56 narrative-truth
gate**, the unit tests, the coverage floors, plus `sprint6-verify` and `training-smoke`. Nothing
recorded it. That line is fixed. The failure has moved to **step 8, `mypy --strict orchestrator/`,
which reports 78 errors in 32 files** — all from commit `e000258`, none on `main`.

**21 of the 78 are one pattern:** `Missing named argument "confidence_threshold" for
"OrchestratorConfig"`. **Do NOT clear it by giving that argument a default.**
`GuardrailEngine(confidence_threshold=config.confidence_threshold)` consumes it, so a default
substitutes an unreviewed number for a committed one on the **I-5 confidence gate** — exactly what
`policy.py` refuses to do and what this spec exists to stop. It needs its owner's decision.

Until that is resolved, every property this spec has written is **local evidence only**. Hold that
when you read any claim about them.

---

## HARD-WON LESSONS. Each one cost a session; each names what it protects against.

### On evidence and verification

- **An optional-evidence escape in a decision function is a hole, not a default.** `classify_regret`
  read `regret >= margin and (interval is None or excludes_margin)`. An absent interval was not a
  missing precondition — it was a **satisfied** one, so a bare point estimate could have falsified
  Finding 4 and ended a 132-task spec. **Grep for that shape** (`X is None or`, `if not Y: pass`,
  `getattr(o, 'f', True)`) in anything that returns a verdict. Fix it by supplying the evidence at
  the production boundary, **not** by loosening the classifier — that keeps every pinned property
  intact.
- **Verify at the boundary you are claiming, not at a proxy for it.** "The lint step will pass" was
  claimed from a whole-tree local exit code polluted by CRLF. The claim was wrong. Per-file, on LF
  files, was the admissible unit.
- **Never generalise one proof to a population.** One of 40 local format errors was proven to be a
  line-ending artifact and that proof was extended to all 40. **Three were real.** The correct move
  was the mechanical one: `biome format --write ./src` reports "Fixed 40 files" while `git diff` shows
  exactly **3**, because git normalises line endings. If a claim covers N things, prove it over N or
  find the arithmetic that does.
- **A deferred verification pointed at a gated step is not a deferred verification.** "Let CI answer
  C63" nominated step 9, which was **skipped** behind step 5's failure. The answer arrived only
  because step 5 runs the whole registry. When deferring, name a check that cannot itself be skipped
  — for the registry, that is the `registry-gate: ... N check(s) did not pass` verdict line.
- **When a job fails, read what got SKIPPED behind it, not only what failed.** That is how the
  18-steps-and-3-jobs finding surfaced. `gh api .../jobs` and list every step whose conclusion is
  `skipped`.
- **`heavy` fails what `dev` passes. Twice now.** `HYPOTHESIS_PROFILE=dev` draws **10 examples**. A
  dev-profile green is ten examples of evidence, not a proof. **Re-verify anything load-bearing at
  `heavy` on one scoped file before claiming it.** Last two catches: an absolute-width interval whose
  endpoint landed on the margin, and `fmean` of *n* copies of a value being one ulp off at
  `4.4e-253`.
- **`getDiagnostics` returning nothing is inconclusive, not evidence** (R2.13).
- **A local red is not always a CI red, and a local green is not a CI green.** Prove which you have.

### On ownership — this moved work INTO scope twice

- **Determine ownership mechanically, in three steps, before filing anything as "pre-existing":**
  ```powershell
  git log -1 --format='%h' -- <file>          # or: git blame -L n,n --porcelain <file>
  git merge-base --is-ancestor <sha> main     # exit 1 => NOT on main => this branch's
  gh run list --branch main --workflow '<name>' --limit 3   # is main itself red here?
  ```
  Two findings had been filed as `main`'s and were **this branch's**: four Biome errors (all
  `5db5eb1`) and two Ruff errors plus ten format files (all `e000258`). `main`'s Frontend CI is
  **green**, which settled the first by elimination as well as by blame.
- **A `warn`-level finding co-reported beside a failure did not cause the failure.** The
  `noNonNullAssertion` finding attributed to PR #77 exits **0**. Check the configured severity before
  attributing a red to a finding.

### On design documents and dependencies

- **Consult the design for the area you are touching before authoring — it may already own your
  work.** The interval estimator was fully designed at **E3.1** with a declared path, name, signature
  and property number. Inventing a second one would have forked the concept.
- **A design can be wrong in mechanism, and a property test is what finds it.** E3.1 claimed sorting
  the resample *statistics* gives input-order invariance. It does not — the seeded index stream is
  fixed, so permuting inputs changes which values each resample draws. Order-invariance needs the
  paired *differences* sorted **before** resampling. Both sorts are needed and they do different jobs.
- **Read the install closure before trusting a design's data source.** Task 15.2 said read `alpha`
  through `uplift.contract.load_contract`; `contract.py` imports `scipy`; `scipy` is in **neither**
  `packages/requirements.txt` nor `requirements-dev.txt` and reaches `ci.yml::uplift-verify` only
  transitively via `agents/*/requirements.txt`, which `uplift.yml::twin-regret` does not install. That
  would have crashed the measurement at import, inside the job that exists to run it. **Found by
  reading the closures, before a CI round trip paid for it.**
- **When a workaround creates two readers of one artifact, pin them to each other with a test.** Two
  readers with nothing comparing them is the `None == None` hole C75 exists to close.
- **Doc drift costs measurement power, not just a red tick.** C56's red baseline made its own gate
  *unprobeable*, so the falsification sweep probed **7** checks instead of 8 — the drift **removed a
  gate from the measurement**.

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open — not started. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

- **The `[~]` mark earned its existence, and this is the proof.** Tasks 1.2/1.5 were reconciled from
  `[x]` to `[~]` because nothing had judged them. Then: CI failed on Biome naming one finding → a
  repair claimed green → **it was not green**, there were four findings plus three more behind them →
  a second repair → green on the **third** run. An `[x]` at authoring time would have hidden two
  successive failed repairs.
- **Leave a half-landed task `[ ]`, not `[~]`, when the owed half is authoring blocked on another
  task.** A `discharge:` line naming a job would be false, and `[~]` stops the census offering the
  work. Precedent: task 15.2.
- **"Authored and diagnostics-clean, not executed" is a legitimate result.** "Should pass" reported as
  "passes" is an I-7 violation.
- **Disk outranks the ledger.** Session 1 opened with eight tasks implemented and unticked.

### On the compute budget

- **The three generators are not equally priced, and this is the trap.** `gate_surface --write/--check`
  is pure workflow parsing, ~1s — **cheap, and it is the sixth gate in the sweep.**
  `ledger_gen` and `readme_gen` each execute the **entire Check_Registry in-process** (~900s,
  ~15 min full-core CPU). So a change that moves only the *workflow tree* can be regenerated locally;
  a change that moves a check's *status* cannot. **Know which you are making before you start**, and
  escalate rather than hand-editing a count — I-7 forbids that absolutely.
- **The `biome` and `tsc` binaries in `frontend/node_modules/.bin/` may be run directly on changed
  files or on `./src`** — bounded, single-process, the analogue of `ruff`. **`pnpm` stays banned and
  `vitest` is banned outright.** CI runs vitest; that is what discharges frontend tasks.

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what throttle it.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
  `pnpm` anything.
- **Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, **one** scoped `pytest`
  run on a single file or narrow directory, `spec_ledger_census`, the **six** cheap gates
  (`workflow_shape_truth`, `pin_extractor_truth`, `sweep_budget_truth`, `dataset_licence_truth`,
  `task_claim_truth`, `gate_surface`), the `biome`/`tsc` binaries on changed files, and **`gh` API
  reads** (network, no local compute — use them freely to verify CI).
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
  unlimited. **Sub-agents that execute code: exactly ONE at a time.**
- **Preferred flags:** `-x -q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
- **Sweep before finishing.** List background processes; confirm none of yours survived.

### Verification sweep — run before closing any session

```powershell
python -m ruff check <changed files>
python -m mypy --strict <changed python files>
$env:HYPOTHESIS_PROFILE='dev'
python -m pytest <changed test files> -q --tb=line -p no:randomly -m "not slow"
python -m scripts.audit.workflow_shape_truth              # C64   expect 0
python -m scripts.audit.pin_extractor_truth --check       # C75   expect 0
python -m scripts.audit.sweep_budget_truth --check        # C73   expect 0
python -m scripts.audit.dataset_licence_truth --check     # C74   expect 2 = honest SKIP
python -m scripts.audit.task_claim_truth --check          # expect 1 = pre-existing, other spec
python -m scripts.audit.gate_surface --check              # C63   expect 0
python -m scripts.audit.spec_ledger_census --files --check # expect 0
```

**Reproduce CI's exact commands when you are claiming a CI step will pass:**

```powershell
python -m ruff check packages/synapse_common/ agents/ orchestrator/ --output-format=github
python -m ruff format --check packages/synapse_common/ agents/ orchestrator/
python -m mypy --strict packages/synapse_common/
python -m mypy --strict orchestrator/          # 78 pre-existing errors; do not "fix" by defaulting
cd frontend; .\node_modules\.bin\biome.cmd check --max-diagnostics=200 ./src
cd frontend; .\node_modules\.bin\tsc.cmd --noEmit -p tsconfig.json
```

---

## ENVIRONMENT TRAPS. Every one of these has already cost time.

- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** On PS 5.1 `Get-Content -Raw`
  decodes with the ANSI codepage and `Set-Content -Encoding utf8` adds a **BOM** — which Python's
  `read_text(encoding='utf-8')` does **not** strip, so a spliced document silently gains a `\ufeff`
  on line 1. This mojibaked 179 lines and was caught only by byte-inspection. **Splice documents with
  Python (`pathlib`, explicit `encoding='utf-8'`, `newline='\n'`) or with the editor tools — never
  with PowerShell text cmdlets.** Then verify:
  ```powershell
  $b=[System.IO.File]::ReadAllBytes($f); $t=[System.IO.File]::ReadAllText($f)
  "BOM=$($b[0] -eq 239 -and $b[1] -eq 187 -and $b[2] -eq 191)  U+FFFD=$($t.Contains([char]0xFFFD))"
  ```
- **PowerShell mangles the box-drawing characters Biome and several gates print.** Grepping for `━`
  finds nothing and looks like a clean run. **Read exit codes, or use `--reporter=summary`.**
- **PowerShell strips double quotes inside single-quoted `--jq` expressions**, so `test("X")` becomes
  `test(X)` and jq fails to parse. Capture `gh api` output into a variable and use
  `ConvertFrom-Json` instead. `>` redirection writes **UTF-16**; `<` is not a valid operator; there
  are **no heredocs** — write commit messages to a temp file and use `git commit -F`.
- **`git status` over-reports on this tree.** With `core.autocrlf=true` and `.gitattributes` pinning
  only `*.sh`/`*.sql`, a formatter that writes LF marks ~40 frontend files modified while `git diff`
  shows only the real content changes. **Trust `git diff`, and stage precisely.**
- **The local clock runs ~2h45m ahead of the commit timestamps git and GitHub agree on.** Any
  reasoning that compares "now" against a run's `created_at` will be wrong. **Identify a CI run by
  `head_commit.message`**, never by timestamp:
  ```powershell
  gh api repos/Praneshrajan137/Synapse/actions/runs/<id> --jq '.head_commit.message'
  ```
- Suppress twin logging in any engine-driving probe or the output floods:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))`.
- `types-PyYAML` is not installed, so `mypy --strict` reports import-untyped on every yaml-importing
  module. **Do not run `pre-commit install`** — it installs the stubs and unmasks nine real
  pre-existing errors that then block commits to files that do not contain them.
- Python 3.14.0, pytest 8.4.2, hypothesis 6.151.11. `gymnasium` absent. `frontend/node_modules` is
  installed.

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). A hardcoded value overrides the profile in *both*
  directions. **Do not assert a total** (CF-13 — the gate reports the count, the prose does not).
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`; its fast step
  collects only `tests/uplift tests/verify`. **A slow-marked test outside those four paths is selected
  by no job at all**, and one that must run in `quality-gates` must **not** be slow-marked.
- **Never weaken a generator or an assertion to make a property pass** (R2.10). Fix the subject — or,
  if the *precondition* was wrong, fix the precondition **and say which**. The difference is whether
  the subject changed or the standard did.
- **Assert a clause unconditionally rather than wrapping it in a tolerated-exception disjunct.** "Or
  it raises" is a weak property. Prove the refusal path separately, by construction — "no generated
  example triggered it" is not evidence that a guard works.
- **Derive numbers; flag the irreducible choice.** Precedent: `resamples = ceil(50 / (alpha/2))` with
  `TAIL_ORDER_STATISTICS = 50` flagged `chosen`, and `materiality_margin = service_points * 0.01 *
  weights.unmet_service` with `service_points: 5.0` flagged and bracketed on both sides.
- **A knob with a self-serving sign gets a `ratchets.json` direction; one without gets none.** Raising
  a falsification threshold is the self-serving move (margin → `direction: down`); an objective weight
  and an interval width have no better-direction, and inventing one would be fabrication.
- Type hints everywhere (`mypy --strict`), Pydantic v2 `ConfigDict(frozen=True)` for recorded facts,
  `structlog` never `print()` in library code, canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`, `encoding='utf-8'` on **every**
  `read_text` (E-S13-07), ASCII-only console output, lines ≤ 100 chars.
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, or any paid SDK.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS.
  Absence of proof is never a pass.

### The four same-commit couplings

1. A rename and its declaration.
2. A new CI job and **both** its `blocking-steps.yaml` step entry and `required-checks.yaml` job entry.
3. A schema change and every fixture that carries it.
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.**

Either half alone is a red gate. **The fourth was missed twice** (tasks 5.6 and 10.3): it cost C63 and
cascaded into `ledger_gen`, `doc_truth`'s pinned counts and the README headline — four registered
gates from one missed `--write`.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** A workflow change and its
  `gate_surface --write` share a commit; documents that describe *two* work streams go last, so no
  message misdescribes its own diff.
- Verify new files are not gitignored before staging — `git add` refuses an ignored path **silently**:
  `git check-ignore -v <paths>` (exit 1 = not ignored).

---

## What this spec is actually for — hold this while you work

SYNAPSE claims multi-agent AI makes better supply-chain decisions than a simpler system. That claim is
currently untestable — not because the answer is bad, but because nothing in the project can yet
produce an answer that would mean anything. The thesis:

> Make the instruments provably able to fail, make the simulated world one where intelligence can pay,
> prove the measuring device can detect an effect, and only then measure — on non-synthetic data,
> against a published external benchmark.

**Two checkpoints can end this project early, on purpose.** Checkpoint A's task 11 can falsify Finding
4 and re-cut R5. Checkpoint B's task 14 can prove consensus unnecessary and cancel E3 outright. Both
run *before* the work they gate. Most plans cannot reach a conclusion that invalidates themselves.

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
one.

The honest possible outcome is "no uplift". Hold that clearly. This spec does not promise the AI wins;
it promises the answer will be believable either way.

---


## Session 2q handoff — regenerate this section each session

### This section OVERRIDES STEP 3 above. Read it before acting on that list.

**Items 1, 2 and 3 of STEP 3 are discharged.** Do not re-ask them; the operator answered all three in
session 2q and the answers are landed.

| STEP 3 item | Status after session 2q |
|---|---|
| 1 — take the survivor list to the operator | **Done.** Reviewed and accepted. Task 6 is `[x]` and **E1 is closed.** `C28/zero-a-floor`'s repair is deferred to `coverage_per_package.py --require-measured-floors` under its own owner. No mutation was weakened. |
| 2 — decide the `readme_gen` escalation | **Done.** Decided *against* a local run. `.github/workflows/regenerate-truth-docs.yml` now runs both generators on a runner and uploads the result. **Never run `ledger_gen` or `readme_gen` locally.** |
| 3 — decide the 78 `mypy --strict orchestrator/` errors | **Done.** Adopted in scope as spec parent **27**. 22 already cleared; **56 remain.** |
| 4, 5, 6 — the dispatch, the margin, task 11's verdict | **Still owed, unchanged, and still the operator's** — except that item 4 is now **two** dispatches. See finding 16. |

### State of the tree

**Two commits landed in session 2q**, plus the ledger commit carrying the handoff: `e1b274c` the
regeneration job with all three of its couplings, `d1c4dc7` the `confidence_threshold` declaration
fix. Branch was **20 ahead of `main`** before the ledger commit. Derive the rest:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 11
```

At close that reported **140 leaf tasks: 57 done, 3 authored-pending-discharge, 80 open** (72
authorable, 8 CI-gated). The total moved from 132 because session 2q registered two new parents. The
three `[~]` are **10.4** (checkpoint A), **26.1** (the regeneration job, never executed) and **27.1**
(the declaration fix, CI has not confirmed the count at its own scope).

### FINDING 16 — checkpoint A needs TWO dispatches, not one. Unactioned.

Derived by reading `policy.py`, `regret.py` and `uplift.yml`; **not executed**.

- **`must_be_below_measured_headroom` never fires on run 1.** `policy.py::materiality_margin` returns
  `None` on `committed is None` **before** reaching the guard, so the guard that makes the margin
  falsifiable-by-construction is unexercised. `_measure` reports `margin_rule_below_headroom` only as
  an informational bool that refuses nothing.
- **`classify_regret` with `margin=None` returns `verdict: unavailable`.** Recording task 11 as
  `inconclusive` off run 1's artifact means hand-computing a verdict from
  `interval_excludes_rule_margin` + `margin_rule_derives` that **the instrument did not produce** —
  the shape I-7 forbids, and the same shape as session 2p's defect 9.
- **Run 2 is a verdict materialisation, not a re-measurement.** `_measure` iterates
  `for seed in range(replicates)` — seeds `0..199`, fixed — and the interval's seed is committed, so
  identical arguments give identical numbers. No metric-shopping surface.

**The order:** dispatch 1 measures → **ONE ADR-055 D2.5 amendment, one amendment-log line, covering
both owed amendments together** → commit the margin value and **graduate the parked pin** (discharges
10.4) → dispatch 2 (discharges 11).

### FINDING 20 — the pin task 10.4 owes is already drafted, and it is PARKED. Do not just add it.

Task 10.4 and `doc-number-pins.yaml` both say to add the derived-margin pin "in the same commit as
the value". **Obeyed literally, that lands a pin whose document anchor matches nothing.** The derived
literal exists in only three places and none is pinnable: `SESSION_PROTOCOL.md` (whose own rule is
that it carries no counts), **`HANDOFF.md` (overwritten every session)**, and a `note` field inside
`ratchets.json`. **ADR-055 D2.5 states no derived literal** — it stops at `service_points * 0.08`.

**What would happen, and which gate would say so.** `doc_truth.documented_value` needs the anchor to
match **exactly one line**; zero matches raises `_Unresolvable`, which is *"always a `skip`, never a
pass"* — a **skip, not a fail**. The pin is `required: true`, and that skip is non-maskable (R1.4,
R1.6): *"the aggregate verdict is `unavailable`, and no number of `ok` siblings can supply a passing
verdict."* **C56 goes SKIP, and a SKIP is not a PASS.** Meanwhile `pin_extractor_truth` reports
**15/15 green**, because it probes source extractors *"unconditionally, independent of whether the
document anchor matched."* The failure would look like the regeneration hadn't worked.

**So the pin is drafted and parked** as `materiality-margin-derived-value` under `pending_pins:`,
which that section does not evaluate. Its `activates_after` names **both** graduation conditions:
the value non-null, **and** D2.5 stating the literal on exactly one line matching the anchor
`` derives `materiality_margin = (?P<value>[\d.]+)` ``. Graduating it is then a pure data move.

**Two things the amendment must get right.** It is **one** amendment covering the derived literal
*and* `bracketing.upper` if the headroom moved from `11.79 - 2.93 = 8.86` — one revision, one log
line, not two. And it must land **before dispatch 2**, per D2.5's own rule that an amendment "lands
before the run judged against the amended text". **No second `ratchets.json` entry is owed:** the
derived value moves only when `service_points` moves, and that input already carries
`direction: down`; inventing one would be fabrication.

### Two tracks, and their order is FIXED. Corrected in 2r-pre — 2q's summary got this wrong.

`uplift.yml`'s jobs both carry `needs: NONE`, so **checkpoint A does not wait on `quality-gates`.**
`ci.yml::uplift-verify` does. **That is CI triggering, and it is the whole of what `needs:` tells
you.** The tracks are coupled through the *generated documents*: any change to
`doc-number-pins.yaml` changes `doc_truth`'s claim set, which can move C56, whose status sits inside
the PASS/FAIL/SKIP counts `ledger_gen` and `readme_gen` project.

**So track A's margin commit lands BEFORE track B's regeneration.** Reversed, the regenerated
`CURRENT.md` and `README.md` go stale the moment the margin lands, and the ~45-minute dispatch is
spent twice. **Do not read `needs: NONE` as licence to run these in any order.**

**Track A — checkpoint A.** Items 4, 5, 6 of STEP 3, with finding 16 applied.

**Track B — session 2r, and it should precede session 2.** Six tasks:
`26.2 26.3 27.2 27.3 27.4 27.5`. **Its two halves are not interchangeable in order.**

1. **First, and safe in parallel with track A:** clear the remaining 56 orchestrator errors —
   **27.2 (24 `arg-type`) → 27.3 (26 across eight codes) → 27.4 (`unused-ignore` last, because
   `warn_unused_ignores` means the earlier repairs move that count in both directions)** — then
   confirm `uplift-verify` **executed**, not skipped (27.5). This touches no generated document.
2. **LAST:** `gh workflow run regenerate-truth-docs.yml --ref feat/decision-quality-proof`, download
   `regenerated-truth-docs`, read the diff, commit `docs/state/CURRENT.md` and `README.md`.
   **Confirm two things, not one:** C56 goes PASS, **and** the falsification sweep's probeable set
   returns to **8**. The second is the measurement power the drift cost. It goes last because it
   projects a snapshot that track A's margin commit would invalidate.

**Why 2r precedes session 2.** Session 2 authors eleven tasks, and **four of them (12.2, 12.4, 13.2,
13.4) produce `@pytest.mark.slow` properties whose declared discharge is `ci.yml::uplift-verify`** —
the job that has never run. They cannot be run locally (category 4 under I-0). Authoring them first
adds eleven marks, four permanently unverifiable in the meantime, to a spec whose property surface is
already unproven.

### What session 2q proved, and what it did not

**Executed and green:** `ruff` + `ruff format` **0** at CI's exact scope (386 files);
`mypy --strict` clean on both changed non-test files; **`mypy --strict orchestrator/` 78 → 56** at
CI's exact command, twice; **24 tests passing** (5 new config-default, 4 new closure-parity, 15 at
`heavy` across the confidence-boundary suites); six cheap gates **0/0/0/2/1/0**; census 0; process
sweep clean.

**NOT executed, and must not be claimed:** **`uplift-verify`, so Properties 38–60 have still never
run in CI** — step 8 still fails at 56 > 0; **`regenerate-truth-docs.yml` has never executed**, which
is why 26.1 is `[~]`; `ledger_gen`, `readme_gen`, `verify_claims`, `doc_truth` — none run locally, in
any form; the five slow-marked `ConsensusProtocol` properties; `vitest`; `_measure`'s wired interval
path. **And the absolute CI value of the orchestrator error count** — 56 is the local number, the
local environment has no `types-PyYAML`, and only the delta and the two vanished codes are
stub-independent.

### Three things session 2q learned that are not in the lists above

- **A stated gate's number can be wrong in the safe direction, and mechanical literalism would have
  thrown away a correct repair.** The plan set `78 → 57` as a revert condition; the measurement was
  **56**. What made proceeding safe was evidence, not judgement: exactly two codes moved and both to
  zero, **every** other count identical, no new code, and the 22nd error's mechanism read from source
  (`thresholds.py:118` assigns the class *object* into a `Callable[[], OrchestratorConfig]` slot).
  **Prove the shape of a deviation before accepting it** — "something was masked" was checkable, and
  was checked.
- **A `ruff format --check` diff whose two sides look character-identical is a LINE-ENDING diff.**
  Programmatic edits wrote LF into CRLF working-tree files; `git ls-files --eol` reported `w/mixed`.
  Repair with Python at `newline=''`. **Run `git ls-files --eol <path>` after any programmatic edit.**
- **A gate's non-zero exit is a claim about the *invocation* as much as the gate.** A PowerShell
  splatting bug (`$parts[1..0]` on a one-element array) made `workflow_shape_truth` report exit 2; it
  is 0 when invoked correctly. Verify the command before believing the verdict.

### The two corrections session 2q made to its own instructions

Both are recorded in `HANDOFF.md` as conflicts F and G. **Do not re-derive them.**

- **F — the `confidence_threshold` repair belongs at the declaration, never at the call sites.** The
  reviewed default already existed as `Field(0.7, ge=0.0)`, passed *positionally*; there is no
  `pydantic.mypy` plugin, so mypy reads defaults through PEP-681 `dataclass_transform`, which
  recognises only `default=`. Three of the 21 reporting sites are **production**. Passing a value at
  each would have put 21 unreviewed numbers on the I-5 gate.
- **G — a `workflow_dispatch`-only job owes no `required-checks.yaml` entry.**
  `ineligibleEntry.reason` is a closed six-value enum with no "dispatch-only" member;
  `required_checks_truth` validates declared→resolves, not completeness; eight existing workflows
  carry no entry. `HANDOFF.md`'s old mention of `uplift.yml` appearing there is **task 25's future
  criterion**, not a present fact.
