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
  bare `readme_gen --check` (all three spawn the entire Check_Registry as a 900-second
  subprocess), `gate_fault_injection --sweep` (30 gate subprocesses over a tree copy), `pnpm`
  anything.
- **Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, **one** scoped
  `pytest` run on a single file or narrow directory, `spec_ledger_census`, and the five cheap
  gates (`workflow_shape_truth`, `pin_extractor_truth`, `sweep_budget_truth`,
  `dataset_licence_truth`, `task_claim_truth` — each ~1s of pure file reads).
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

**The three same-commit couplings.** A rename and its declaration; a new CI job and both its
`blocking-steps.yaml` step entry and `required-checks.yaml` job entry; a schema change and every
fixture that carries it. Either half alone is a red gate.

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

## Session 1r handoff — regenerate this section each session

**Session 1r was a protocol revision plus one pre-registration. No spec task was completed.**
Derive the state with `spec_ledger_census`; at the time of writing it reported 132 leaf tasks,
53 done, 3 authored-pending-discharge, 76 open — 70 authorable and 6 CI-gated.

**The next thing in the plan is checkpoint A, which is an operator action, not an authoring
session.** Tasks 6, 10.4 and 11 discharge there. Do not author task 12 until task 11's verdict is
recorded and is not `material`. Session 2 is then eleven tasks: 12.1–12.4 and 13.1–13.7.

### What session 1r changed, and why

- **The batch plan was re-cut around the two early-exit gates.** Tasks 11 and 14 were pooled into
  the final session, so each could only fire after the seventy-odd tasks it exists to prevent.
  They are now checkpoints A and B, ahead of the work they gate. Tasks 21, 22.3 and 25 became
  checkpoints C and D — CI-gated but not able to end the spec.
- **The ledger gained a third mark.** `[~]` means authored, discharge pending, with a
  `discharge:` line naming the owed job. Tasks **1.2** and **1.5** moved from `[x]` to `[~]`:
  both are TypeScript, neither has ever been type-checked or executed, and `HANDOFF.md` already
  said so in prose while the ledger said `[x]`. **Task 10.4** is now `[~]` too — see below.
- **Counts became mechanical.** `scripts/audit/spec_ledger_census.py` (+16 tests, all passing)
  replaces the `python -c` one-liner and the hand-copied tables. It derives the CI-gated set from
  `discharge:` lines, so the "six-versus-seven" disagreement between the old `GATED` literal and
  the prose beside it cannot recur.
- **The materiality margin's rule was pre-registered and made enforceable** — ADR-055 **D2.5**,
  `regret_objective.materiality_margin` in the policy file, `policy.py::materiality_margin`, a
  pin (C75 now reports **14/14**), a `direction: down` ratchet, and 13 tests. This is task 10.4's
  first half; its *value* is still `null` and is owed at checkpoint A. The rule matters because
  R5.2's "commit the margin only after measuring it" would otherwise let the margin be chosen to
  suit the number it judges — the reader now **re-derives a committed value and refuses one that
  disagrees**, and refuses any margin at or above the measured headroom as unfalsifiable.
- **`task_claim_truth --check` joined the sweep.** It already parses `tasks.md` and already
  catches ticked-but-not-landed registry claims; nothing had ever invoked it here. **It is red on
  arrival**, at exit 1, on `core-purpose-uplift` tasks 9 and 9.1 — pre-existing and not this
  spec's. Recorded rather than skipped: a gate you skip because it is red is a gate you disabled.

### Defects found in session 1r

1. **Task 12.1 — session 2's first task — still declared
   `infrastructure/quality/twin-decision-relevance.yaml`**, the path Conflict A decided against.
   Authoring it would have forked the twin's parameters across two files. Corrected to
   `digital_twin/simulation/policy.yaml`.
2. **The two sensitivity flips were unassigned.** The protocol asserted tasks 12.3 and 13.3 *earn*
   `spoilage_rate` and `delivery_latency` becoming `sensitive: true`, but no sub-task instructed
   the edit and `policy.py` refuses to default a missing key. Now written into both tasks, each
   coupled to the pin test it breaks.
3. **Task 11's verdict table was missing the state the tree is in.** The verdict is four-valued
   and the protocol resolved three; today's value is `unavailable`, which is not `inconclusive`.
4. **Task 24.1's gate identifiers were stale by two.** C75 is the highest registered
   (`check_pin_extractors`); next free is C76. The two checks 24.1 called "still owed" are
   registered as C74 and C75, so following it would have collided.
5. **Task 7.2 declared `scripts/audit/feed_licence_truth.py`**, which never landed — the module
   is `dataset_licence_truth.py`.
6. Two in the new script itself: its path extractor rejected dotfile-rooted paths (`.github/`,
   `.kiro/`), and its human report echoed em dashes from `tasks.md`, violating the ASCII-only
   console rule.

### Verified vs merely authored — session 1r

**Executed and green:** `test_spec_ledger_census.py` 16 passed; `test_materiality_margin_rule.py`
13 passed; `test_regret_totality_property.py` 16 still passing after the margin reader was wired
into `_measure` (29 together). `ruff` clean on all four touched/new files. `mypy --strict` reports
no error in any line written this session. The five other cheap gates at their claimed exit codes
(0, 0 with 14/14 pins, 0, 2, 0).

**Red, honestly:** `task_claim_truth --check` exits **1** on `core-purpose-uplift` tasks 9 and 9.1
— pre-existing, another spec's ledger, not repaired here.

**NOT executed:** everything session 1 listed as unexecuted is still unexecuted — all TypeScript,
`digital_twin/tests/test_env_response.py` (module-skipped, `gymnasium` absent), and
`tests/uplift/test_aggregation_integrity_property.py::test_aggregation_integrity_under_failures`
which **fails** on pre-existing float fragility. CI has never run this branch; checkpoint A is its
first exposure. See `HANDOFF.md` for the full ledger and the expected-red list.
