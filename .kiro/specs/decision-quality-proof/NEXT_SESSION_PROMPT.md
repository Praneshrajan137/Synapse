# NEXT_SESSION_PROMPT.md

**Paste the whole of this file as your first message in a new session.** It is written to be
reusable: it names no task batch, because the agent derives that from the ledger. Regenerate only
the `## Session N handoff` section at the end of each session.

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`. Work is batched: **at most TEN leaf tasks this session, fewer
if you reach a dependency boundary first. Then stop and tell me to open a new one.**

### Step 1 — read these, in this order. They are binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**, the local compute budget.
   Highest precedence. Nothing below may be used to justify heating the laptop.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — **the working agreement**: the
   ten-task cap, the three marks, the four checkpoints, the batch plan, the verification sweep,
   the materiality-margin rule, and the resolved tasks-11→12 circularity. Read it before touching
   anything.
3. `HANDOFF.md` (repo root) — the state of the tree as of the last session: defects found,
   decisions taken, and what is verified versus merely authored.
4. `CLAUDE.md` — the operating manual: the 14 invariants, the honesty contract, the gate
   registry, the `E-S*` hard-won lessons, deploy-truth rules.
5. `.claude/skills/synapse-engineer/SKILL.md` + its `references/` (`14_invariants.md`,
   `testing_topology.md`, `spec_schema.md`, `adr_index.md`).
6. `.cursorrules` + `docs/cursor/*.md` — code conventions, agent pattern, domain models.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — the Decision_Relevance_Record this phase is
   executed against. Everything in E2/E3 reads from it.
8. The spec itself: `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`.
   `tasks.md` is the **ledger and your worklist**.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict
to me rather than resolving it silently.**

### Step 2 — derive the batch. Do not trust any number written in prose.

```powershell
python -m scripts.audit.spec_ledger_census --files --next 10
```

That command is the census: leaf total, the three mark buckets, the CI-gated set derived from
`discharge:` lines, and the next authorable batch in ledger order. `--files` additionally reports
open tasks whose named artifacts already exist.

Then tell me the tasks you are taking and confirm they match `SESSION_PROTOCOL.md`'s batch table.
If they do not, say so and explain why before proceeding. **If the next thing in the plan is a
checkpoint (A, B, C or D), it is an operator action, not yours to author — tell me and stop.**

### Step 3 — DISK OUTRANKS THE LEDGER. Verify before authoring.

This has already bitten this project once: session 1 opened with **eight tasks fully implemented
on disk and still showing `[ ]`**. The `--files` output above is the mechanical version of this
check; read its `prior-art` lines. Treat them as informational — `tasks.md` names some paths in
order to *reject* them, and a task that modifies an existing module always shows prior art.

And "the file exists" is **not** "the task is done". Read the cited requirement criteria and
confirm the artifact implements them. That exact substitution is the defect this spec's task 2 was
written to kill; do not reintroduce it at the ledger level.

### Step 4 — work the batch

For each task:

1. Read the cited requirement criteria in `requirements.md` and the design section in
   `design.md`. Not the summary in `tasks.md` — the source.
2. Verify current tree state.
3. Implement.
4. Verify within I-0's budget, and record the actual output.
5. Mark it **honestly**: `[x]` only if it is done *and* discharged; `[~]` plus a `discharge:` line
   naming the owed job if it is authored but unproven. Write into `tasks.md` what was measured,
   what was decided, and any defect found. **A tick with no evidence is a claim.**

### Step 5 — close the session

Run the verification sweep in `SESSION_PROTOCOL.md`, including
`spec_ledger_census --files --check` and `task_claim_truth --check`. Then:

1. **Overwrite `HANDOFF.md`** (do not append) with the tree as it now is.
2. Append one row to `SESSION_PROTOCOL.md`'s progress ledger. Never edit a past row.
3. Regenerate the `## Session N handoff` section of this file.
4. Say, explicitly: **"Session complete. Start a new session and paste
   `NEXT_SESSION_PROMPT.md`."**

---

## The rules that will bite you

**I-0, the compute budget.** 16 GB laptop, RTX 3050, thermally throttling. Process *type* and
*count* are what throttle it.

- **Never run:** dev servers, watchers (`vitest` without `--run` is a watcher — in practice do
  not run `vitest` at all), browsers/Playwright, `docker compose up`, anything binding a port;
  fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`, `mutmut`); any
  `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`** (its own docstring: every row
  comes from "one in-process Check_Registry execution"), `gate_fault_injection --sweep` (30 gate
  subprocesses over a tree copy), `pnpm` anything.
- **Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, **one** scoped
  `pytest` run on a single file or narrow directory, `spec_ledger_census`, the six cheap gates
  (`workflow_shape_truth`, `pin_extractor_truth`, `sweep_budget_truth`, `dataset_licence_truth`,
  `task_claim_truth`, `gate_surface` — each ~1s of pure file reads), and the installed
  `frontend/node_modules/.bin/biome` and `tsc` binaries on changed files. **Never via `pnpm`, and
  `vitest` not at all.**
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and
  analysis: unlimited. **Sub-agents that execute code: exactly ONE at a time.** If your
  orchestrator template permits 3–5, I-0 overrides it.
- **Environment is PowerShell.** Use `$env:VAR='x'; cmd`, **not** `set VAR=x && cmd` — `&&` is
  not a valid statement separator. `powershell -NoProfile -Command` is not allowlisted.
- Suppress twin logging in any test or probe that drives the engine, or the output floods:
  `structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))`.

**Authoring rules.**

- **Never hardcode `max_examples` in `@settings`.** Inherit from the root `conftest.py` profiles
  (`dev`=10, `heavy`=100, `ci`/`default`=500, `nightly`=5000). A hardcoded value overrides the
  profile in *both* directions — that is what amplified the original I-0 incident. Pre-existing
  violations are out of scope; do not add one, and **do not assert a total** (CF-13 — the gate
  reports the count, the prose does not).
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  exactly `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`
  (line 351); its fast step collects only `tests/uplift tests/verify` (line 316). A slow-marked
  test outside the slow step's four paths is selected by **no job at all**. A test that must run
  in `ci.yml::quality-gates` must **not** be slow-marked, because that job filters
  `-m "not slow"`.
- **Never weaken a generator or an assertion to make a property pass** (R2.10). Fix the subject.
  If the *precondition* was wrong, fix the precondition and say so — the difference is whether
  the subject changed or the standard did.
- Type hints everywhere (`mypy --strict`), Pydantic v2 with `ConfigDict(frozen=True)` for
  recorded facts, `structlog` never `print()` in library code (CLI entry points may print),
  canonical `json.dumps(obj, sort_keys=True, separators=(',',':'))`, `encoding='utf-8'` on
  **every** `read_text` (E-S13-07), ASCII-only console output, lines ≤ 100 chars.
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, or any paid SDK.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`
  (byte-pinned hash chain).
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS.
  Absence of proof is never a pass. **"Authored and diagnostics-clean, not executed" is a
  legitimate result and its mark is `[~]`; "should pass" reported as "passes" is a violation.**

**The four same-commit couplings.** A rename and its declaration; a new CI job and both its
`blocking-steps.yaml` step entry and `required-checks.yaml` job entry; a schema change and every
fixture that carries it; **and any workflow job/step change, or any `blocking-steps.yaml` entry, and
`python -m scripts.audit.gate_surface --write`.** Either half alone is a red gate. The fourth is the
one session 1 missed twice, on tasks 5.6 and 10.3 — it cost C63 and cascaded into three more gates,
and `gate_surface --check` is now in the sweep so it cannot recur unnoticed.

---

## What this spec is actually for — hold this while you work

SYNAPSE claims multi-agent AI makes better supply-chain decisions than a simpler system. That
claim is currently untestable — not because the answer is bad, but because nothing in the project
can yet produce an answer that would mean anything. The thesis:

> Make the instruments provably able to fail, make the simulated world one where intelligence can
> pay, prove the measuring device can detect an effect, and only then measure — on non-synthetic
> data, against a published external benchmark.

**Two checkpoints can end this project early, on purpose.** Checkpoint A's task 11 can falsify
Finding 4 and re-cut R5. Checkpoint B's task 14 can prove consensus unnecessary and cancel E3
outright. Both now run *before* the work they gate, which is the whole point of them and was not
true of the first batch plan. Most plans cannot reach a conclusion that invalidates themselves.

**The pre-commitment, binding before the number is known:** if measured uplift is null or
negative, **it is reported as null or negative.** The floor stays at `0.0`, no headline is
published as a gain, and the result is written up as a finding — not reframed, not re-run at a
different replicate count until it moves, not held back pending a "better" configuration. A null
from a validated instrument on a decision-relevant world is worth more than the tautological PASS
it replaces: before this spec, C60 could only ever report SKIP, and a measured zero against a
`0.0` floor exited 2. **A number that cannot fail is not a number.**

The honest possible outcome is "no uplift". Hold that clearly. This spec does not promise the AI
wins; it promises the answer will be believable either way.

---

## Session 2p handoff — regenerate this section each session

**Session 2p was pre-batch repair, and it is committed and pushed.** It did three things, in this
order: made checkpoint A's dispatch affordable, made checkpoint A's *verdict admissible*, and
repaired the two discharge failures PR #84 exposed — one of which nothing had recorded. **No
session-2 task was started.** Three commits on `feat/decision-quality-proof`: `85774e1` the interval
+ the dispatch selector + the gate-surface regeneration, `d67f1c7` the Biome repair, and the ledger
commit. Derive the state with `spec_ledger_census`; at the time of writing: 132 leaf tasks, 54 done,
3 authored-pending-discharge, 75 open — 69 authorable and 6 CI-gated, with `--next 11` returning
exactly `12.1 12.2 12.3 12.4 13.1 13.2 13.3 13.4 13.5 13.6 13.7`.

**Your first act is still NOT task 12, and there is no authoring owed before checkpoint A.** The
order is: read the falsification sweep's survivor list and bring it to the user; read whether **C63**
went green on this push (that is the deferred verification of the gate-surface repair — see the
escalation below); dispatch `twin-regret` **alone**
(`gh workflow run uplift.yml --ref feat/decision-quality-proof --field job=twin-regret` — session 2p
is what makes that possible); instantiate the margin from the committed rule; record task 11's
verdict; and only then author E2c. If the verdict is `material`, **stop and re-cut R5.**

### The one finding that most changes what you do next

**Checkpoint A could have ended this spec on a point estimate, and now it cannot.**
`classify_regret`'s material branch is `regret >= margin and (interval is None or excludes_margin)`,
and `uplift/regret.py::_measure` supplied **no interval** — so an absent interval was not a missing
precondition, it was a *satisfied* one. A bare point estimate at or above the margin would have
reported Finding 4 falsified and stopped 132 tasks of work.

Three authorities disagreed about whether that is admissible, and the disagreement is now recorded
in task 11 rather than resolved silently: `RegretVerdict`'s docstring and `SESSION_PROTOCOL.md`'s
checkpoint-A table both require the interval to exclude the margin; **R5.3 does not**; R5.13 does,
but governs the *non-stationary* twin at task 13.7. Resolved toward the stricter reading — **by
changing the instrument, not the classifier.** `uplift/interval.py` (design **E3.1**, task 15.2's
estimator half, landed early) supplies a paired percentile bootstrap at `1 - alpha` from the
committed Metric_Contract; `_measure` passes it; `classify_regret` is untouched and all 17 of task
10.6's pinned properties still pass. A run whose dispersion cannot be estimated reports
`status: unavailable` and exits 2 rather than falling back.

**Adopting a standard the criterion does not demand is only legitimate in the direction that makes
falsification harder to *claim*.** That direction is stated in task 11 so a reader comparing the run
to R5.3 finds the deviation rather than inferring it.

### What else session 2p changed, and why

- **`uplift.yml` gained a job selector.** `workflow_dispatch.inputs.job` (`both` | `uplift-proof` |
  `twin-regret`) with an `if:` guard per job, so checkpoint A stops costing ~350 runner-minutes it
  does not need. `default: both` and the guard's leading `github.event_name != 'workflow_dispatch'`
  keep the nightly proof running — a guard written only against `inputs.job` would have silently
  disabled it, and a job that stops running is indistinguishable from one that passes (I-7). No step
  was added, so no new `blocking-steps.yaml` entry is owed; `workflow_shape_truth` re-verified at
  `verdict=pass`, 370 steps, 10 declared-blocking entries.
- **C63's gate-surface drift is repaired, and it was hiding.** `docs/state/GATE_SURFACE.md` named
  neither `truth-gates.yml::falsification-sweep` (task 5.6) nor `uplift.yml::twin-regret` (task
  10.3), and carried `52 job(s)/357 step(s)/8 anchors` against a tree with `54/370/10` — while
  `docs/state/CURRENT.md:94` records C63 as **PASS**. So C63 was red on PR #84 against a ledger that
  says green, which drifts `ledger_gen`, `doc_truth`'s pinned counts and the README headline: **four
  gates from one missed `--write`**, filed until now as "predicted red". Repaired with
  `gate_surface --write` (+50/-5). **`gate_surface --check` is now the sixth cheap gate in the
  sweep**, and there is now a **fourth** same-commit coupling because of it.
- **`ledger_gen` went onto the never-run list.** Its docstring says every row is projected from "one
  in-process Check_Registry execution". It reads like a document generator and costs what
  `verify_claims` costs.
- **The frontend discharge failure was four findings, not one, and all four were ours.** See below.
- **Task 15.3 is `[x]`; task 15.2 is deliberately still `[ ]`.** 15.2's estimator half is landed and
  executed, but its `uplift/harness.py::assemble_uplift_result` call site needs task 15.1's
  `ArtifactInterval` first. Left open rather than `[~]` because the owed half is *authoring blocked
  on another task*, not a proof owed by a CI job — and because the census must keep offering it to
  session 3. **Read 15.2's note before authoring it; `--files` will flag `uplift/interval.py` as
  prior art, correctly.**

### The frontend repair, and the two corrections it forced

`frontend.yml::quality` failed on Biome. **All four error-level findings were authored by this
branch's own commit `5db5eb1`** — `git merge-base --is-ancestor 5db5eb1 main` exits 1:
`setup.ts` `organizeImports`; `fc-budget.ts:163` `useLiteralKeys`; two `fc-budget.ts` `format`
violations; `SloBurnBoard.tsx:114` `noUselessTernary`. Three of those were unrecorded. And the
finding previously attributed to PR #77 (`noNonNullAssertion`) is configured `warn` and **exits 0** —
it never failed anything.

Verified by executing the installed `biome` binary directly, never `pnpm`: the `HEAD` copy of
`setup.ts` exits **1**, the working-tree copy exits **0**, and `biome check ./src` now reports
**zero error-level lint findings** across 351 files, down from 43 errors. **`tsc --noEmit -p
tsconfig.json` exits 0** — the first time this branch's TypeScript has been compiled.

**Tasks 1.2 and 1.5 are still `[~]`, and the reason is exact.** `frontend.yml::quality` runs Biome,
then `tsc`, then vitest. The first two are now verified locally; **the third cannot be — I-0 bans
`vitest` outright.** 1.5's file is reached by none of the local checks at all: Biome never scans
`frontend/spec/`, and `tsconfig.json`'s `include` omits `frontend/spec/effectiveness/__tests__/**`.
Its discharge is by **execution**.

### Two traps in the local environment, both proven rather than assumed

1. **`biome check ./src` reports 40 `needs to be formatted` errors that do not exist on CI.** They
   are `core.autocrlf` artifacts: the working tree checks out CRLF, `.gitattributes` pins only
   `*.sh` and `*.sql`, and `biome.json` sets `formatter.lineEnding: lf`. Proven —
   `frontend/src/domain/primitives.ts` contains CRLF and is byte-identical to its `HEAD` blob once
   CRLF is normalised. **Do not "fix" them**; a `format --write` sweep would commit line-ending
   churn across 40 untouched files and change nothing about the gate. A local Biome run is
   admissible evidence **per file, on LF files** — not as a whole-tree exit code.
2. **PowerShell's `Get-Content`/`Set-Content` round-trip corrupts UTF-8 in this repo, and it bit
   this session.** On PowerShell 5.1 `Get-Content -Raw` decodes with the ANSI codepage, so splicing
   a file that way mojibakes every em dash and `Set-Content -Encoding utf8` adds a **BOM** —
   which Python's `read_text(encoding='utf-8')` does *not* strip, so the first line of a spliced
   document silently gains a `\ufeff`. Caught by byte-inspecting the result and restored with
   `git checkout`. **Splice documents with Python (`pathlib`, explicit `encoding='utf-8'`) or with
   the editor tools, never with PowerShell text cmdlets.** Related: PowerShell also mangles the
   box-drawing characters Biome and several gates print, so read exit codes or use
   `--reporter=summary` rather than grepping for `━`.

### The escalation was offered, costed, and declined. Read C63 instead.

**Claim, still a prediction:** repairing C63 needed `gate_surface --write` only; `ledger_gen --write`
and `readme_gen --write` should be unnecessary, because `CURRENT.md` already records C63 as PASS, so
restoring PASS restores agreement rather than moving a count.

Verifying it locally costs roughly **900 seconds and ~15 minutes of full-core CPU per command, ~30
minutes serial** — category 3/4 under I-0. It was declined, and not only on heat:
`truth-gates.yml` runs all three generators on this push anyway, so the local run would have bought
the same answer twice, and **if the prediction is wrong, C63, C56 and the README headline go red and
name the drift.** A legible failure in a run that was going to happen beats a private confirmation
that costs the machine.

**The question was not skipped.** Reading C63's status on this push is an owed item, and the
prediction is recorded as unverified in `HANDOFF.md`'s honesty ledger. **Never repair a count by
hand** (I-7).

### Verified vs merely authored — session 2p

**Executed and green:** `test_interval_estimation_property.py` **20 passed at `dev` and re-verified
at `heavy`**; `test_regret_totality_property.py` (17) + `test_materiality_margin_rule.py` (13) =
**30 passed at `heavy`**, so session 1r's properties survive the interval change; **50 passed**
across the three at the sweep profile. `ruff` clean on all three touched Python files.
`mypy --strict` reports no error in any line written this session except the documented repo-wide
`yaml` stub gap. The six cheap gates at `workflow_shape_truth` 0, `pin_extractor_truth` 0,
`sweep_budget_truth` 0, `dataset_licence_truth` **2** (honest SKIP), `task_claim_truth` **1**
(pre-existing, another spec's ledger), `gate_surface --check` **0**. `spec_ledger_census --check`
pass. Process sweep clean.

**NOT executed:** `vitest`, at all. `_measure`'s new interval path — it drives the SimPy twin, so
its arithmetic is covered by Property 60 and its wiring **discharges at the `twin-regret`
dispatch**. `ledger_gen`/`readme_gen --check`. `test_env_response.py` (module-skipped, `gymnasium`
absent). `test_aggregation_integrity_under_failures`, which still **fails** on pre-existing float
fragility.

**A lesson, for the second session running: `heavy` failed what `dev` passed.** Property 60's
degenerate-sample clause asserted `point == value` exactly, and `fmean` of `n` copies is one ulp off
at `value=4.413920275115946e-253, count=5`. Fixed the **precondition** — closeness for
point-vs-value, exact equality retained for `low == high == point`, which *is* exact by construction
— not the assertion, and did not touch the subject (R2.10). **A `dev`-profile green is ten examples
of evidence. Re-verify anything load-bearing at `heavy` on one scoped file.**

**And one design defect that Property 60's own third clause found.** Design E3.1 said sorting the
resample *statistics* makes the interval invariant to input order. It does not — the seeded index
stream is fixed, so permuting the inputs changes which values each resample draws, sorted or not.
Order-invariance needs the paired *differences* sorted before resampling; sorting the statistics is
what makes percentile extraction well defined. **Both are needed and they do different jobs.**
`design.md` E3.1 records the correction, along with the two forced deviations from its declared
signature: the return type is `uplift.interval.Interval` and not `ArtifactInterval` (importing
`harness.py` would drag the twin and numpy into `regret.py`'s deliberately light import path), and
`alpha` is read with `yaml` rather than through `uplift.contract.load_contract`, because
`contract.py` imports `scipy` and **`scipy` is not in `uplift.yml::twin-regret`'s install closure** —
routing one float through the validating reader would have failed the regret measurement at import,
inside the job that exists to run it. Both deviations are pinned by tests, not by intention.
