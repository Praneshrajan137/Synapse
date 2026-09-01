# HANDOFF — decision-quality-proof

**State at end of session 2q (2026-09-02). Committed; not yet pushed at the time of writing.**
Derive the counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 11
```

At the time of writing that reported **140 leaf tasks: 57 done, 3 authored-pending-discharge, 80
open** — 72 authorable and 8 CI-gated. The total moved from 132 because session 2q **registered two
new parents**, 26 and 27, for work this spec did not author and has now adopted by explicit operator
decision.

> **Session 2q discharged the first third of checkpoint A and adopted two pieces of external debt.**
> It ticked task **6** on the reviewed survivor list, which closes **E1**; it made the two costly
> document generators runnable without local compute; and it cleared 22 of the 78
> `mypy --strict orchestrator/` errors with a one-line change that added no number to the tree.
>
> **Two commits landed before this document:** `e1b274c` the regeneration job with all three of its
> couplings, `d1c4dc7` the `confidence_threshold` declaration fix. The commit carrying this file is
> the third. Branch is **20 commits ahead of `main`** before it.
>
> **Checkpoint A is still open, and still the operator's.** Tasks 10.4 and 11 are untouched. What
> session 2q added to that story is **finding 16**: checkpoint A needs *two* `twin-regret` dispatches,
> not one, and the reason is mechanical rather than stylistic. See below.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree as
it *is*, not as a diff against how it was.

---

## What is owed right now, in order

**Two tracks, and they are NOT freely orderable. Corrected in session 2r-pre; 2q's closing summary
got this wrong.** `uplift.yml`'s jobs `uplift-proof` and `twin-regret` both carry `needs: NONE`, so
checkpoint A does not wait on `quality-gates`, and `ci.yml::uplift-verify` does (`needs:
quality-gates`) — which is why track B exists. **But `needs:` describes CI triggering and says
nothing about the generated documents, which is where the two tracks are coupled.** Any change to
`doc-number-pins.yaml` changes `doc_truth`'s claim set, which can move C56, whose status sits inside
the PASS/FAIL/SKIP counts `ledger_gen` and `readme_gen` project. **So track A's margin commit must
land before track B's regeneration** — reversed, the regenerated `CURRENT.md` and `README.md` are
stale within the hour and the ~45-minute dispatch is spent twice.

### Track A — checkpoint A, operator work, unchanged except for finding 16

1. **Dispatch the regret measurement.**
   ```powershell
   gh workflow run uplift.yml --ref feat/decision-quality-proof --field job=twin-regret
   ```
   Read `regret`, `interval_low`/`interval_high`, `comparator_headroom`, `margin_rule`,
   `margin_rule_derives`, `margin_rule_below_headroom` and `interval_excludes_rule_margin` from
   `artifacts/uplift/twin-regret.json`.
2. **One ADR-055 D2.5 amendment, one commit, one amendment-log line, covering BOTH owed amendments.**
   It must state the derived value as a literal on **exactly one line** — that is what the parked pin
   anchors to (finding 20) — **and** correct `bracketing.upper` if the measured headroom moved from
   `11.79 - 2.93 = 8.86`, which is prose and is **not pinned**, so nothing gates it. D2.5's own rule
   is that an amendment "lands **before** the run judged against the amended text", which puts this
   before dispatch 2. One revision, one log line, not two.
3. **Commit `materiality_margin.value` from the rule** (`service_points * 0.01 *
   weights.unmet_service` = `5.0 * 0.01 * 8.0` = `0.40`) and **graduate the parked pin** —
   `materiality-margin-derived-value` moves from `pending_pins:` into `pins:`, a pure data move once
   the amendment above has landed. **Do not author a fresh pin; read finding 20 first.**
   `policy.py::materiality_margin` will refuse a value the rule does not produce — that is intended.
   **No second `ratchets.json` entry is owed**: the derived value moves only when `service_points`
   moves, and that input already carries `direction: down`. Discharges **10.4**.
4. **Dispatch a second time.** This is finding 16 and it is not optional. Discharges **11**.
5. **Record task 11's verdict** against `SESSION_PROTOCOL.md`'s four-value table, then branch:
   `material` → **STOP**, Finding 4 falsified, re-cut R5 (R5.3, R5.4), report it plainly as a
   success of the method. `inconclusive` → proceed, **but see track B first**. `sub-margin` →
   confirms Finding 4, unreachable today by construction. `unavailable` → the measurement did not
   happen; say so and proceed on nothing.

### Track B — session 2r, the adopted debt, and it should precede session 2

**Its two halves are NOT interchangeable in order.** The orchestrator work touches no generated
document and may start any time. The regeneration must come **after** track A's margin commit.

6. **Clear the remaining 56 `mypy --strict orchestrator/` errors** (tasks 27.2 → 27.3 → 27.4, in that
   order — `unused-ignore` last, because `warn_unused_ignores = true` means the earlier repairs move
   that count in both directions), then confirm `uplift-verify` **executes** — ran, not skipped, not
   silent (27.5). That is what makes Properties 38–60 real rather than local, and it touches no
   generated document, so it is safe to run in parallel with track A.
7. **LAST: dispatch the regeneration job and commit its artifact.**
   ```powershell
   gh workflow run regenerate-truth-docs.yml --ref feat/decision-quality-proof
   ```
   Download `regenerated-truth-docs`, read the diff the run printed, commit `docs/state/CURRENT.md`
   and `README.md`. Discharges **26.2** and **26.3**. Confirm **two** things, not one: C56 goes PASS,
   **and** the falsification sweep's probeable set returns to **8** — that second one is the
   measurement power the drift cost. Read the registry verdict line, not one step's conclusion.

   **It goes last because it projects a snapshot.** Track A's margin commit adds a pin, which moves
   `doc_truth`'s claim set and can move C56 — so a regeneration committed before it is stale
   immediately. Sequenced this way, one dispatch suffices instead of two.

---

## Read these first, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the cap, the three marks, the four
   checkpoints, the batch plan (now carrying rows **2q** and **2r**), the six cheap gates.
3. `CLAUDE.md` — 14 invariants, honesty contract, gate registry, `E-S*` lessons.
4. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
5. `.cursorrules` + `docs/cursor/*.md`.
6. `docs/adr/ADR-055-twin-decision-relevance.md` — the record this phase executes against.
7. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`.

**A conflict between two authority files is surfaced, never silently resolved.** Conflicts A–E are
recorded below; session 2q surfaced two more, F and G, and both are corrections to instructions this
session was given.

### The ledger has three marks and four sources

`[ ]` open · `[~]` **authored, discharge pending** — not a pass, and it carries a `discharge:` line
naming the job that owes the proof · `[x]` done **and** discharged. An *open* leaf with a
`discharge:` line is CI-gated and is not authorable work.

Authoritative: `tasks.md` checkboxes for state, `spec_ledger_census` for every count, this file for
what executed. **`tasks.meta.json` is not authority** — its `executionHistory` bulk-stamped every
task within an eleven-second window.

**And disk outranks all four.** Session 1 opened with eight tasks complete on disk and unchecked.

---

## Session 2q — two corrections to its own instructions, both surfaced rather than absorbed

### Conflict F — the 21 `confidence_threshold` errors were one line, not 21 call sites

The session was instructed to repair them "at the call sites (passing the committed value) rather
than at the signature". **That would have been the wrong repair, and the plan said so itself after
reading the code.** Four facts, all read before anything was changed:

- `orchestrator/config.py` declared `confidence_threshold: float = Field(0.7, ge=0.0)` — **the
  reviewed default already existed**, passed positionally.
- It is the **only** field in `OrchestratorConfig` that uses `Field(...)`; every other field carries
  a bare assignment default. The error named exactly that one field.
- `pyproject.toml`'s `[tool.mypy]` has **no `plugins` entry**, so the `pydantic.mypy` plugin is not
  enabled. There is no `mypy.ini` and no `setup.cfg` mypy section.
- There is exactly one `OrchestratorConfig` in the tree.

Mechanism: without the plugin, mypy synthesises `__init__` from pydantic v2's PEP-681
`dataclass_transform`, which recognises a field-specifier default only as `default=`. The positional
form made the field a **required** keyword argument.

**Why the instructed repair was harmful.** Passing a value at 21 call sites would have put 21
unreviewed numbers onto the **I-5 confidence gate**:
`GuardrailEngine(confidence_threshold=config.confidence_threshold)` consumes it, and `thresholds.py`
records that the boundary is injected a single time at `inference/serve.py`. **Three of the 21 sites
are production, not tests** (`inference/serve.py` ×2, `audit/cli.py`). The default was never missing;
it was invisible to the checker.

**Measured, at CI's exact command, twice — the whole mypy budget this session had:**

| | baseline | after `Field(default=0.7, ge=0.0)` |
|---|---|---|
| total | **78 errors in 32 files** | **56 errors in 17 files** |
| `call-arg` | 21 | **0** |
| `assignment` | 1 | **0** |
| `arg-type` | 24 | 24 |
| `unused-ignore` | 7 | 7 |
| `type-arg` · `no-any-return` | 5 · 5 | 5 · 5 |
| `no-untyped-def` · `import-untyped` | 4 · 4 | 4 · 4 |
| `attr-defined` · `union-attr` · `comparison-overlap` | 2 · 2 · 2 | 2 · 2 · 2 |
| `method-assign` | 1 | 1 |

**Exactly two codes moved, both to zero. Every other count is identical and no new code appeared.**

### The 22nd error, which the prediction missed, and why it is the interesting one

The plan predicted `78 → 57` and set reverting as the gate. The actual is **56**. The session did
**not** revert, and the reasoning is recorded here because the deviation was from a stated gate:

- The gate's question — are the 21 a tooling artifact cleared by the keyword form? — is answered
  **yes**, unambiguously.
- The 22nd is `orchestrator/guardrails/thresholds.py:118`, which assigns the **class object** into a
  `Callable[[], OrchestratorConfig]` slot (`settings_factory if settings_factory is not None else
  OrchestratorConfig`). While mypy believed `__init__` required the argument, `type[OrchestratorConfig]`
  was not a zero-argument callable. **Same root cause**, in the module that *reads* the I-5 boundary,
  and its own docstring already declared the class callable with no arguments. That file now reports
  zero errors.
- Reverting a verified, behaviour-neutral, root-cause-correct one-line repair because it fixed 22
  instead of 21 would be mechanical literalism defeating the gate it was serving.

**Two side-effects worth carrying.** `thresholds.py:118` is one of the errors this file previously
recorded as blocking `pre-commit install`, and it was never a `types-PyYAML` issue at all. And that
list said "nine real pre-existing errors" while naming **eight** paths (`uplift/fidelity.py:43,102`,
`uplift/harness.py:270`, `uplift/consensus_arm.py:384,385,392,637`, `thresholds.py:118`) — corrected
here; with `thresholds.py` cleared, **seven** remain.

**What is claimed and what is not.** The claim is the *delta* and the disappearance of the two codes,
which are inference results independent of installed stubs. **Not** the absolute CI count: the local
environment has no `types-PyYAML`, so the four `import-untyped` errors here may not correspond
one-to-one with CI's. **Step 8 still fails — 56 > 0 — so `uplift-verify` is still skipped and
Properties 38–60 have still never executed in CI.**

### Conflict G — the `required-checks.yaml` half of coupling 2 was not owed

The plan costed the new job as dragging in "**both** its `blocking-steps.yaml` step entry and
`required-checks.yaml` job entry". Read rather than assumed:

- `required-checks.schema.json::ineligibleEntry` constrains `reason` to a **closed six-value enum**
  — `path-filtered`, `path-filtered-and-conditioned`, `branch-push-only`,
  `conditioned-off-pull-request`, `self-labelled-informational`, `post-merge` — with
  `additionalProperties: false`. **None describes "dispatch-only."**
- `required_checks_truth` validates that *declared* jobs resolve. It does **not** require the file to
  be complete.
- Eight existing workflows carry no entry at all: `required-checks-reconcile.yml`,
  `publish-audit-anchor.yml`, `uplift.yml`, `live-truth.yml`, `cd.yml`, `cd-recovery.yml`,
  `eval-llm-judge.yml`, `sprint6-e2e-oracle.yml`.

So declaring it would have meant **amending a schema enum** — dragging in the third same-commit
coupling — for a job that produces no status check on any pull request and blocks no merge.

**Do not read `HANDOFF.md`'s old mention of "`uplift.yml`'s job appears in `required-checks.yaml`
under `ineligible`/`post-merge`" as precedent.** That is **task 25's future success criterion**, not a
present fact. The file does not contain it.

---

## Finding 16 — checkpoint A needs TWO dispatches, and this is unactioned

Derived by reading `policy.py`, `regret.py` and `uplift.yml`; **not** executed.

- **`must_be_below_measured_headroom` never fires on run 1.** `policy.py::materiality_margin`
  returns `None` on `committed is None` **before** reaching the guard. So the guard that makes the
  margin falsifiable-by-construction is unexercised, and `_measure` reports
  `margin_rule_below_headroom` only as an informational bool that refuses nothing.
- **`classify_regret` with `margin=None` returns `verdict: unavailable`.** Recording task 11 as
  `inconclusive` off run 1's artifact means the operator hand-computes a verdict from
  `interval_excludes_rule_margin` + `margin_rule_derives` that **the instrument did not produce** —
  the shape I-7 forbids, and the same shape as session 2p's defect 9.
- **Run 2 is a verdict materialisation, not a re-measurement, so there is no metric-shopping
  surface.** `_measure` iterates `for seed in range(replicates)` — seeds `0..199`, fixed — and the
  interval's seed is committed. Identical arguments give identical numbers; only the verdict field
  changes, and the headroom guard finally executes.

---

## What session 2q changed

### 1. Task 6 is `[x]`, and E1 is closed

Reviewed and accepted by the operator on the list measured at run `33513528766`, sha `77df3ef`:
`REGISTERED=67 DECLARED=14 FALSIFIED=6 PASS_ELIGIBLE=6 EXCLUDED=53`, `PROBED=16 UNPROVEN=0`, one
survivor, `C28/zero-a-floor`, the disclosed one.

The disposition, recorded in the ledger rather than only here: **`C28`'s real repair waits on
`coverage_per_package.py --require-measured-floors` under its own owner and is not this spec's.**
**No mutation was weakened, and none may be.** What the acceptance rests on is `UNPROVEN=0` — the
clause the task's own success criterion names — and *no undisclosed survivor*; had either failed,
acceptance would have been unavailable regardless of the survivor count. The sweep is **still red**
and E1's criterion never asked it to be green. `gate-mutations.yaml`'s misattributed C16 survivor
shape at line 26 stays recorded and unrepaired.

### 2. The regeneration job — `ledger_gen --write` and `readme_gen --write` are now reachable

`.github/workflows/regenerate-truth-docs.yml`, `workflow_dispatch` only, `permissions: contents:
read`, `timeout-minutes: 45` derived from `truth-gates`' own 25 rather than picked.

**The problem it solves is that CI could detect this drift and never repair it.** `truth-gates.yml`
runs all three generators with `--check`; the `--write` form existed only on a developer's machine,
where `ledger_gen` and `readme_gen` each execute the entire Check_Registry in-process at ~900 s and
~15 min of full-core CPU. **That figure is the local Windows cost, and the asymmetry is the point:**
`truth-gates.yml::truth-gates` does comparable work inside `timeout-minutes: 25` on a runner. This is
I-0 escalation step 1, taken literally.

**It commits nothing.** It writes, prints its diff to the log, and uploads the three documents for a
human to review and commit. `contents: read` makes that structural. An auto-commit variant was
rejected: it would let a machine write generated counts into the tree with no reviewer, and
hand-maintained counts drifting is the entire reason these documents are generated.

Three decisions in it that were reasoned rather than defaulted:

- **`gate_surface --check` is the first step and a hard gate.** Regenerating on top of a stale gate
  surface produces an artifact that is stale the moment it is written, because C63's status sits
  inside the counts `doc_truth` and `readme_gen` pin. A red first step means the dispatching commit
  missed the fourth coupling.
- **`readme_gen --write` runs without `--counts-json`.** The flag does not change *which* counts are
  used — without it `readme_gen` calls `doc_truth.nested_suite_counts` itself, through the same
  function the gate calls, so the nested semantics that make C56 self-exclude hold either way. It is
  purely a cost saving, and earning it would mean pairing with `doc_truth --check`, a step **expected**
  to exit non-zero while C44 and C69 are red. The only way through would be a `continue-on-error`
  inside a truth-gates-adjacent workflow. One extra registry execution is the accepted cost.
- **The install closure is copied verbatim and pinned by a test, not hoisted into a shared script.**
  Hoisting it would edit the steps of a **required** status-check workflow to save a copy. The closure
  is load-bearing: several registered checks report SKIP when an optional import is missing (C45
  torch, C46 the published-checkpoint stack, C58 synapse_common), so a thinner environment turns a
  PASS into a SKIP, moves the counts, and the job would then **write the wrong numbers into the
  documents it exists to correct** — a failure that looks like a success.

**The fourth same-commit coupling was observed firing, not assumed.** `gate_surface --check` went
non-zero on the new job — 17→18 workflow files, 54→55 jobs, 370→378 steps, and NOT-EXECUTED +1 under
all three synthetic contexts, which is the dispatch-only job correctly claiming nothing — then back
to **0** after `--write` (533 → **536** surface rows). `blocking-steps.yaml` gained entry **11**
(`all_steps: true`), and `workflow_shape_truth` resolves it.

That `blocking-steps.yaml` entry is **declared by judgement, not obligation**, and the file records
which: the converse there is only R11.3's *name* rule, so omitting it would violate nothing. It is
declared because a `continue-on-error` on `ledger_gen --write` would upload a stale or empty artifact
that a reviewer commits in good faith — repairing a generated count by hand at one remove, which I-7
forbids absolutely. Every other entry in that file protects a *measurement*; this one protects a
*document other gates are judged against*.

### 3. Parents 26 and 27, and why session 2r precedes session 2

Registered under a new `### Phase 6 — adopted debt` heading. **Their ids are last; their execution
order is not.** Precedent is checkpoints A–D, which fire before the work they gate. Renumbering was
rejected: `task_claim_truth`, this file's cross-references and other specs cite these ids.

**Parent 26** (3 leaves) is the regeneration: 26.1 `[~]` the job and its couplings, 26.2 the dispatch
and review, 26.3 the commit and the confirmation that C56 returns to PASS **and** that the sweep's
probeable set returns to 8.

**Parent 27** (5 leaves) is the orchestrator debt: 27.1 `[~]` the declaration fix; 27.2 the 24
`arg-type`, **per error rather than per pattern** — 27.1's group was genuinely uniform and reading
that as licence to batch-fix these would be the over-generalisation that cost session 2p three real
Biome findings; 27.3 the 26 across eight codes, with `import-untyped` flagged as possibly an honest
recorded deferral rather than a repair; 27.4 the `unused-ignore` errors **last**, because
`warn_unused_ignores = true` means 27.1–27.3 move that count in both directions; 27.5 the payoff.

It carries a **FORBIDDEN REPAIRS** block: no error may be cleared by giving an argument a default, by
widening a type to `Any`, by adding a `# type: ignore`, or by narrowing mypy's scope. If an error is
genuinely a tooling artifact, the repair is at the *declaration that misleads the checker* — 27.1 is
the worked example — never at the call sites that report it.

**The sequencing argument, now in `SESSION_PROTOCOL.md`.** Session 2 authors eleven tasks, and **four
of them (12.2, 12.4, 13.2, 13.4) produce `@pytest.mark.slow` properties whose declared discharge is
`ci.yml::uplift-verify`** — the job that has never executed. Running them locally is forbidden
(category 4 under I-0). So authoring session 2 first adds eleven marks, four permanently unverifiable
in the meantime, to a spec whose existing property surface is already unproven. That compounds the
exact defect this spec exists to name.

---

## What is complete, and what it established

**E0 — instrument hygiene (tasks 1–4).** Complete. Fast-check budget resolver mirroring the
`conftest.py` profiles; the inventory gate's TypeScript rule **inverted** to forbid `numRuns` entirely
(R3.8 forbids a minimum coexisting — do not reintroduce one); six per-file console verdicts with
exactly one passing; `workflow_shape_truth`'s `final_list_element` correction; `readme_gen` projecting
the README headline from the **nested** `verify_claims` execution C56 compares against.

**E1 — gate falsifiability (tasks 5, 6). NOW COMPLETE.** `truth-gates.yml::falsification-sweep` is a
gating job with a committed cost budget re-derived by `sweep_budget_truth` (**C73**) on every run:
worst case 3120 s inside the committed 3600 s with 480 s of headroom, over 14 baselines and 16
operators. Task 6's review closed it.

**E4a — feed admission (task 7).** At the *design's* paths: `infrastructure/data/dataset-licences.yaml`
+ schema, `data_fabric/licence.py`, `data_fabric/ingest/m5.py`,
`scripts/audit/dataset_licence_truth.py` → **C74**. `record_ingestion` **refuses** an ingestion whose
licence is unconfirmed, whose dataset is undeclared, or whose revision disagrees with the terms read.

**E2a — decision record and instrumentation (tasks 8, 9).** `ADR-055` committed **before** any R5
engine change (R5.7). `digital_twin/simulation/policy.yaml` is the single committed twin-parameter
file; `policy.py` reads it and **refuses to default a missing key**. `pin_extractor_truth` → **C75**,
verifying all **14** declared pins resolve **by running them** — closing the `None == None` hole where
two absent values agree and a pin reports green having compared nothing.

**The twin is instrumented, and this is the measurement that matters:**

| Config | demand_events | unmet | fill_rate | stockout_rate | avg_on_hand |
|---|---|---|---|---|---|
| restock ON (50.0) | 2784 | 402 | **0.8556** | 0.1444 | 1016.0 |
| restock OFF (0.0) | 2784 | 1784 | **0.3592** | 0.6408 | 202.1 |

`fill_rate` can now fall; before task 9.1 it could not. `demand_events` and the 2855-event demand
trace are **identical** across both arms — the demand path is provably unaffected by any arm's
actions, which is Property 49's separation clause as data.

**E2b — regret and comparator (task 10, except 10.4).** `uplift/regret.py`: five cost terms, every
number read from `policy.yaml`, four-valued verdict. `uplift/foresight.py`: two-pass comparator with
the `demand_identical` soundness invariant recorded, not assumed. Measured: foresight cost 2.93 /
fill 0.9149 vs no-op 11.79 / fill 0.3592.

**Task 10.4 is half landed and half owed, and the split is deliberate** (ADR-055 **D2.5**). The
margin's *derivation rule* is committed and enforced; the *value* is `null` and is owed at
checkpoint A. `policy.py::materiality_margin` **re-derives** a committed value and **refuses one that
disagrees**; it also refuses a margin at or above the measured headroom, which would be unfalsifiable
by construction. Ratchet `down`, because raising the margin is the self-serving move.

**Task 15.2 is half landed and left `[ ]` on purpose.** `uplift/interval.py` exists and is executed;
the `assemble_uplift_result` call site needs task **15.1**'s `ArtifactInterval` first. Left open
rather than `[~]` because the owed half is *authoring blocked on another task*, not a proof owed by a
job — a `discharge:` line would be false and would stop the census offering it. Task **15.3** is
`[x]`.

---

## Defects found and fixed

**Sessions 1, 1r, 2p — 15 defects, unchanged and still worth reading.** `_apply_cold_start` deleting
the catalogue; the licence schema's missing JSON-Schema format checker; a stale `stryker-break` drift
record; task 12.1's rejected path; the two unassigned `kpi_sensitivity` flips; task 24.1's stale gate
ids (**C75 is highest, C76 next free**); task 7.2's never-landed module name; two census bugs;
**`classify_regret` reaching `material` on a point estimate** (the one that could have ended the
spec); `GATE_SURFACE.md` stale on two of this spec's own jobs; three unrecorded Biome findings;
`ledger_gen` missing from the never-run list; design E3.1's wrong order-invariance mechanism; task
15.2's unexecutable `scipy` read; and this file's own commit count being wrong.

**Session 2q.**

16. **Checkpoint A needs two dispatches, not one.** See finding 16 above. The headroom guard is
    unreachable on run 1 and the artifact's verdict field says `unavailable`, so a one-dispatch
    checkpoint A would require the operator to compute a verdict the instrument did not produce.
17. **The instructed `confidence_threshold` repair would have injected 21 unreviewed numbers onto the
    I-5 gate** (conflict F). The reviewed default already existed and was invisible to the type
    checker only.
18. **`orchestrator/guardrails/thresholds.py:118` was the same defect in production**, and had been
    filed as an unrelated `assignment` error blocking `pre-commit install`.
19. **The `required-checks.yaml` coupling was over-costed** (conflict G): the schema's `reason` enum is
    closed and has no "dispatch-only" member, so honouring the instruction would have meant amending a
    schema for a job that is not a check.

**Session 2r-pre.**

20. **Task 10.4's owed pin had nowhere to anchor, and standing it up as instructed would have made
    C56 non-passing — silently, and reported by the wrong gate.** Found by reading, after 2q closed
    and before checkpoint A step 3 was executed. Task 10.4 and `doc-number-pins.yaml`'s own note both
    say to add the derived-margin pin "in the same commit as the value". A pin is a triple — document
    anchor, mechanical source, extractor — and the **document** side does not exist: a repo-wide grep
    puts the derived literal in exactly three places, none pinnable. `SESSION_PROTOCOL.md`, whose own
    rule is "there is no count in this document, and there should never be one again";
    **`HANDOFF.md`, which is overwritten every session** by protocol, so a pin anchored here dies at
    the next close; and the `note` prose inside `ratchets.json`'s
    `materiality-margin-service-points` entry, which is JSON, not a document. **ADR-055 D2.5 — the
    document the sibling pin anchors to — deliberately stops at `service_points * 0.08` and states no
    derived literal.**

    **The mechanism, stated correctly, because the first reading of it was wrong.**
    `doc_truth.documented_value` requires the anchor to match **exactly one line**; zero matches
    raises `_Unresolvable`, whose docstring is *"Always becomes a `skip`, never a pass"* — a **skip,
    not a fail**. Because the pin is `required: true`, that skip is non-maskable: doc_truth's own
    module docstring records R1.4/R1.6 — *"If a required claim cannot be evaluated ... the aggregate
    verdict is `unavailable`, and no number of `ok` siblings can supply a passing verdict."* So **C56
    would go SKIP, and a SKIP is not a PASS (I-7).** That is not milder than a FAIL for this purpose:
    the falsification sweep reports `indeterminate` for any gate that does not PASS on its unmutated
    baseline, so C56 leaves the probeable set either way — the exact measurement loss task 26 exists
    to recover.

    **And C75 would have reported green throughout.** `pin_extractor_truth`'s docstring: it runs
    every declared extractor against its declared source *"unconditionally, independent of whether
    the document anchor matched."* It probes the source side only. 15 of 15 would resolve while C56
    was silent, and a reader would have concluded the regeneration had failed.

    **Resolved with the mechanism this file already has, not with a new anchor invented today.** The
    pin is drafted and parked in `pending_pins:`, which that section's header states is *"NOT
    evaluated by doc_truth"*. Precedent is `mutation-fast-required-job`, parked because standing it up
    *"would convert a documented, attributable gap into an unattributable red gate, which is the
    trade this whole section exists to avoid."* This case is the mirror — source null, anchor absent.
    Its `activates_after` names task 10.4 and **both** conditions: the value non-null, and D2.5
    stating the literal on exactly one line. **`required: false` was available and rejected** — it
    would have let the pin stand today without touching C56, but a pin that cannot fail is not a pin,
    and downgrading a claim to make it safe is the assertion-weakening R2.10 forbids.

---

## Decisions taken — surfaced, then decided. Do not re-litigate.

| # | Decision |
|---|---|
| Conflict A | Twin policy file → `digital_twin/simulation/policy.yaml` (design E2c.2) |
| Conflict B | Licence artifact → `infrastructure/data/dataset-licences.yaml` (design E4a.1) |
| Conflict C | Property 47/48 attribution — follow the property index |
| Conflict D | **C75 is the highest registered gate id; next free is C76.** |
| M5 licence | Fields land **explicitly null** with a `confirmation.procedure` block; the gate reports SKIP. **Never invent a `licence_id`.** |
| Ratchets | Only 2 of 4 new pinned values got `ratchets.json` entries. An objective **weight** has no monotone better-direction. |
| Checkpoint order | Tasks 11 and 14 fire **before** the work they gate, as operator checkpoints A and B. |
| Margin derivation | The *rule* is pre-registered and **enforced by the reader**; the *value* is measured. Ratchet `down`. |
| Census | `spec_ledger_census` is local hygiene, **not** a registered check. |
| Conflict E (2p) | **`material` requires an interval excluding the margin, stricter than R5.3.** Instrument changed, classifier untouched. |
| Interval estimator (2p) | One estimator for regret and headline uplift, `uplift/interval.py`. `alpha` read with `yaml`, not via `load_contract` (`scipy`). |
| `gate_surface` (2p) | The **sixth** cheap gate. `ledger_gen` went the other way, onto the never-run list. |
| Local Biome/tsc (2p) | The installed binaries may be run on changed files or `./src`. **`pnpm` remains banned**, `vitest` banned outright. |
| **Task 6 (2q)** | **Survivor list accepted; C28's repair deferred to its owner.** No mutation weakened. E1 closed. |
| **Conflict F (2q)** | **The `confidence_threshold` repair is at the declaration, never at the call sites.** One line, no number added. |
| **Conflict G (2q)** | **A dispatch-only job owes no `required-checks.yaml` entry.** The schema enum is closed against it. |
| **Regeneration (2q)** | **A CI job that uploads an artifact, not a local `--write` and not an auto-commit.** Review is the point. |
| **Batch order (2q)** | **Session 2r precedes session 2**, because session 2 would author four more properties against a job that has never run. |
| **Conflict H (2r-pre)** | **The derived-margin pin is PARKED in `pending_pins:`, not landed in `pins:`.** Task 10.4 and this pin table both instruct "same commit as the value"; obeyed literally that stands up a pin whose document anchor matches nothing, which makes C56 SKIP while C75 reports 15/15 green. `required: false` was rejected — a pin that cannot fail is not a pin. It graduates when the value is non-null **and** D2.5 states the literal. |
| **Track coupling (2r-pre)** | **Track A and Track B are independent in CI triggering only.** `needs: NONE` says nothing about the generated documents: a `doc-number-pins.yaml` change can move C56, whose status is inside the counts both generators project. **The regeneration goes last.** |

---

## Honesty ledger — verified vs merely authored

### Executed and green, session 2q

| What | Result |
|---|---|
| `ruff check` / `ruff format --check`, CI's exact scope | **0 / 0**, 386 files formatted |
| `ruff` on the three changed Python files | **0 / 0** |
| `mypy --strict` on the two changed non-test files | **Success: no issues found** |
| `mypy --strict orchestrator/` | **78 → 56**, decomposed per code above. Both passes at CI's exact command |
| `test_orchestrator_config_confidence_default.py` | **5 passed** |
| `test_regeneration_closure_parity.py` | **4 passed** |
| The confidence-boundary suites at `HYPOTHESIS_PROFILE=heavy` | **15 passed, 5 deselected** |
| The six cheap gates | `workflow_shape_truth` **0**, `pin_extractor_truth` **0** (14/14 probed, both sides resolved), `sweep_budget_truth` **0** (3120 s of 3600 s), `dataset_licence_truth` **2** (honest SKIP), `task_claim_truth` **1** (pre-existing), `gate_surface --check` **0** (536 rows) |
| `spec_ledger_census --files --check` | pass, exit 0, every record classified |
| Process sweep | no background jobs; **python 0**, chrome 0; one `node` (Kiro's own ACP server) |

### NOT executed. Must not be claimed as passing.

- **`uplift-verify`, and therefore Properties 38–60.** Skipped on every push so far, because
  `quality-gates` has never succeeded. **This spec's entire property surface has never run in CI.**
  Session 2q moved step 8 from 78 errors to 56; it did not clear it.
- **`.github/workflows/regenerate-truth-docs.yml` has never executed.** Its YAML parses, its steps
  are declared and resolve, and it carries no discarding construct — but a workflow that has never
  run is exactly the shape I-7 names. Task 26.1 is `[~]` for that reason.
- **`ledger_gen` and `readme_gen`, in `--check` or `--write` form. Never run locally this session.**
  That is the point of the new job, not an omission.
- **`verify_claims` and `doc_truth`.** I-0 never-run list.
- **The five slow-marked tests in `test_confidence_gate_universality_property.py`.** They drive the
  real `ConsensusProtocol`. They also pass thresholds **explicitly**, so they never exercise the
  default this session changed — that path is covered directly by the five new tests. Their locus is
  CI. Collection of that file alone takes 48 s.
- **`vitest` locally. At all.** I-0 bans it.
- **`uplift/regret.py::_measure`'s wired interval path.** Discharges at the `twin-regret` dispatch.
- **`digital_twin/tests/test_env_response.py`** — module-skipped, `gymnasium` absent.
- **`tests/uplift/test_aggregation_integrity_property.py::test_aggregation_integrity_under_failures`
  FAILS** on pre-existing float fragility. Diagnosed, not repaired.
- **The absolute CI value of the orchestrator error count.** 56 is the local number. The delta and
  the two vanished codes are stub-independent; the total may not be.

### The lesson from this session

**A gate's stated number can be wrong in the safe direction, and mechanical literalism would have
thrown away a correct repair.** The plan set `78 → 57` as a revert condition; the measurement was 56.
What made it safe to proceed was not judgement but *evidence*: exactly two codes moved, both to zero,
every other count identical, no new code, and the 22nd error's mechanism read directly from the
source. **Prove the shape of the deviation before accepting it** — the alternative reading, that
something had been masked, was checkable and was checked.

---

## Environment notes and traps

- **A `ruff format --check` diff whose two sides look identical is a LINE-ENDING diff.** New this
  session, and it cost three detours. `str_replace`-style edits wrote LF into CRLF working-tree files;
  `git ls-files --eol` reported `w/mixed`, and `ruff format --diff` printed blocks that were
  character-identical on both sides. Repair: rewrite with Python at `newline=''`, normalising to the
  file's dominant ending. **Check `git ls-files --eol <path>` after any programmatic edit.**
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** On PS 5.1 `Get-Content -Raw`
  decodes with the ANSI codepage and `Set-Content -Encoding utf8` adds a **BOM** that Python's
  `read_text(encoding='utf-8')` does not strip. Splice with Python or the editor tools.
- **PowerShell splatting bit a gate loop this session.** `$parts[1..($n-1)]` on a one-element array
  yields a reversed range and passes a stray argument; `workflow_shape_truth` reported exit 2 for
  that reason and 0 when run correctly. **A gate's non-zero exit is a claim about the gate — verify
  the invocation before believing it.**
- **PowerShell mangles box-drawing characters.** Read exit codes; do not grep for `━`.
- **PowerShell strips double quotes inside single-quoted `--jq` expressions.** Capture `gh api`
  output into a variable and use `ConvertFrom-Json`. `>` writes UTF-16; there are no heredocs — write
  commit messages to a temp file and use `git commit -F`.
- **`git status` over-reports on this tree.** Trust `git diff`, and stage precisely.
- **The local clock runs ~2h45m ahead** of the commit timestamps git and GitHub agree on. **Identify
  a run by `head_commit.message`, never by timestamp.**
- `types-PyYAML` is not installed, so `mypy --strict` reports `import-untyped` on every
  yaml-importing module. **Do not run `pre-commit install`** — it installs the stubs and unmasks
  **seven** remaining real pre-existing errors (was eight; `thresholds.py:118` is now cleared) that
  block commits to files that do not contain them.
- Python 3.14.0, pytest 8.4.2, hypothesis 6.151.11, jsonschema 4.26.0. `gymnasium` absent.
  `frontend/node_modules` is installed.

---

## I-0 — the rule most likely to burn the machine

**Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
`mutmut`); any `MIN_SCENARIOS`-scale or training workload.

**Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
`pnpm` anything. **The regeneration job is now the sanctioned route for the middle two.**

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, **one** scoped `pytest`
run, `spec_ledger_census`, the **six** cheap gates, the `biome`/`tsc` binaries on changed files, and
`gh` API reads.

**`mypy --strict orchestrator/` is category 2** — bounded but saturates every core. Session 2q spent
exactly two passes on it, deliberately, because it is the boundary the claim was made at and a proxy
would not have been admissible.

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.**

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — if measured `(s, S)` regret on the unmodified twin is at or above the
R5.2 margin **with its interval excluding it**, **Finding 4 is falsified. Stop.** R5's scope shrinks
and the spec is re-cut (R5.3, R5.4). Report it plainly; it is a good outcome.

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and **the experiment must NOT be run.**

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor stays
at `0.0`, no headline is published as a gain, and the result is written up as a finding — not
reframed, not re-run at a different replicate count until it moves, not held back pending a "better"
configuration. A null from a **validated** instrument on a **decision-relevant** world is worth more
than the tautological PASS it replaces: before this spec, C60 could only ever report SKIP, and a
measured zero against a `0.0` floor exited 2. **A number that cannot fail is not a number.**

Three guards on reading it: a null while any objective KPI is recorded not observably sensitive is
**inconclusive**, not confirmation (task 10.5). No headline may be published while no Power_Report
describes the harness revision under measurement (task 17.3). And **a `material` verdict on a point
estimate with no dispersion is not a falsification either** — the instrument now refuses to produce
one, and finding 16 is what makes sure the verdict recorded is the one it produced.
