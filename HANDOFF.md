# HANDOFF — decision-quality-proof

**State at end of session 2r (2026-09-09). Two commits pushed; the commit carrying this file is the
third.** Derive the counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 10
```

At the time of writing that reported **140 leaf tasks: 61 done, 2 authored-pending-discharge, 77
open** — 69 authorable and 8 CI-gated.

> **Session 2r closed parent 27's four authorable leaves and made `ci.yml::quality-gates` step 8
> pass for the first time on this branch. It did NOT reach `uplift-verify`, and the reason is the
> session's most important finding: the chain to that job is at least four obstructions deep, and
> parent 27 named only the first.**
>
> Tasks **27.1** (discharged by CI), **27.2**, **27.3** and **27.4** are `[x]`. Task **27.5** is
> `[ ]` and is now blocked by **task 26.2**, which is blocked by finding 23's residue.
>
> **`mypy --strict orchestrator/` went 56 → 0.** CI's step 8 went from failure to **success**.
> Properties 38–60 have **still never executed in CI**, and every `HANDOFF.md` must keep saying so
> until 27.5 is `[x]`.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree as
it *is*, not as a diff against how it was.

---

## STOP — CI CANNOT RUN. Account-level block, found after this session's work was pushed.

**Run `34315612360` (sha `bfad6a0`) did not execute. GitHub refused to start any job:**

```
The job was not started because recent account payments have failed or your spending
limit needs to be increased. Please check the 'Billing & plans' section in your settings
```

All three eligible jobs failed in 3–4 seconds with **zero steps recorded**, and the three downstream
jobs were skipped. **That run is not evidence about the code** — nothing in it ran.

**Consequence: every CI-gated leaf in this spec is blocked at the account level, not by its own
precondition.** That is all **8** CI-gated open leaves plus the 2 `[~]` marks:

| Blocked | Needs |
|---|---|
| **27.5** | `ci.yml::uplift-verify` |
| **10.4**, **11** | the `measure-twin-regret` label on PR #84 → `uplift.yml::twin-regret` |
| **14** | checkpoint B's measurement |
| **26.2**, **26.3** | `regenerate-truth-docs.yml`, then `truth-gates.yml` |
| **21**, **22.3**, **25** | the E4 materialisation job, `uplift.yml::uplift-proof` |

**Resolve billing before anything below is attempted.** Decision 1's three routes, checkpoint A's
label, and the regeneration dispatch all assume a runner will start. None will.

**What survives the block, because it was measured before it:** run `33588706405`, head_sha
`b7954b66c7f3b452dfab2158ed4a8ccb3acf9d17`, head_commit *"fix(mypy): declare yaml and psycopg2
stub-free so step 8 stops gating uplift-verify"* — attributed by sha and message, not timestamp, per
this file's own rule. That run executed real steps with real conclusions and is the sole basis for
the step 8 claim below. **It does not cover `743ca6b`.** Step 8's scope is a strict subset of the
wide command, and the wide command exits 0 locally, so step 8 is 0 **by mechanical implication from
local evidence** — not because CI said so at that commit.

**One further anomaly, recorded and unexplained.** `33588706405` reports `created_at`
`2026-09-02T03:52:59Z` for a commit authored in this session on 2026-09-09. The sha and commit
message match this tree exactly, so attribution is sound and the step conclusions stand. But the
recorded clock skew in this file is "~2h45m", and this is seven days. **Do not use `created_at` to
decide which run describes which tree** — the rule was already to use `head_commit.message`, and this
is a second, larger reason.

---

## THE THING THAT IS BLOCKING EVERYTHING — restated, because it changed shape

**`uplift-verify` still has not run, and clearing 56 mypy errors was not enough.** Measured on run
`33588706405`, sha `b7954b6`:

| # | Obstruction | State |
|---|---|---|
| 1 | step 8 `mypy --strict orchestrator/ --exclude orchestrator/tests` | **CLEARED session 2r** |
| 2 | step 17 **C56** narrative-truth, claim `doc-truth/headline-counts` | **RED — and red on `main` too** |
| 3 | step 19 unit tests → `test_cognition_phase.py::test_run_consensus_streams_correlated_phases` | **fails; proven pre-existing on `main`** |
| 4 | steps 20–22 coverage floors, spec coverage, contract tests | **never executed on this branch or `main`** |

Steps 18–23 are skipped behind obstruction 2, so obstructions 3 and 4 are *predicted from local
measurement and from `main`'s history*, not yet observed in CI on this branch. Obstruction 3 was
found by running the test locally; obstruction 4 is unknown, which is not the same as green.

**C56's failure is one claim and four numbers:**

```
[XX] doc-truth/headline-counts [required] README headline drifted from the live verify_claims
     summary: PASS (README claims 51, suite reports 54); FAIL (3 -> 2); SKIP (10 -> 11);
     TOTAL (64 -> 67)
```

That is **task 26's drift**, unchanged and previously documented. Its repair is `readme_gen --write`,
whose sanctioned route is `regenerate-truth-docs.yml` (I-0 escalation step 1). **Never repair those
four numbers by hand** — `blocking-steps.yaml` forbids it in those words, and the README headline is
a projection of a whole registry execution, not four integers.

**So task 26.2 now blocks task 27.5, and that inverts what session 2r was told.** The standing
prompt said `regenerate-truth-docs.yml`'s absence from `main` "blocks nothing you are doing" because
26.2's precondition (track A's margin commit) was outstanding. It now blocks the payoff of parent 27.

---

## What is owed right now, in order

### DECISION 1 — how to reach C56, and it is a three-way trade

`regenerate-truth-docs.yml` is `workflow_dispatch` only and absent from `main`, so per finding 23 it
**cannot be dispatched from this branch at all.** Three routes, costed:

1. **Give it the same `pull_request: types: [labeled]` trigger `uplift.yml` got in `e8e9528`.**
   Precedented, small, touches no shared branch, and it is the mechanism this branch already proved
   works. It is finding 23's repair applied a second time, and finding 23's repair is **the
   operator's** — so it is offered, not taken. Coupling 4 applies: a new trigger moved
   `gate_surface` from 536 to 542 rows last time, so `--write` is owed in the same commit.
2. **Land `regenerate-truth-docs.yml` on `main`.** Harmless in itself (dispatch-only, no schedule),
   and it was session 2r-pre-c's own recommendation before the label mechanism was found. Costs a
   change to the shared default branch to buy what the branch can grant itself.
3. **Wait for track A.** `SESSION_PROTOCOL.md` sequences the regeneration **last** so one dispatch
   suffices: task 10.4's margin pin changes `doc_truth`'s claim set and can move C56, making an
   earlier regeneration stale within the hour. Correct while nothing waited on it. **Now
   `uplift-verify` waits on it**, so the ~45-minute second dispatch buys the first CI execution of
   Properties 38–60 rather than nothing.

**The trade is explicit: one extra regeneration dispatch against continuing to hold this spec's
entire property surface as local-only evidence.** Route 1 then 3 is the cheapest ordering that does
not touch `main`.

### DECISION 2 — obstruction 3 is `main`'s, and adopting it needs your word

`orchestrator/tests/test_cognition_phase.py::test_run_consensus_streams_correlated_phases` fails,
and it fails **on `main`** — proven by running `git show origin/main:` of that file, not inferred.
It will become the blocker the moment C56 clears.

**Diagnosed, so whoever owns it does not re-derive it.** The test asserts that *every*
`kafka.produce` call targets `synapse.orchestrator.phase`:

```python
assert all(c.args[0] == "synapse.orchestrator.phase" for c in calls)
```

But the protocol's producer is shared: ADR-038's `emit_agent_signals` and ADR-053's
`emit_agent_metrics` both emit through it, on other topics. The assertion therefore claims the
protocol emits to no other topic, which stopped being true when those landed. **The repair is a
precondition correction, not an assertion weakening (R2.10):** filter to the phase-topic calls and
assert the phase narrative and decision-id correlation over those. Roughly six lines.

**Not adopted in session 2r on purpose.** Parent 27 was adopted by *explicit operator decision*;
taking this too would be a fourth adoption made unilaterally. Precedent is task 6's disposition of
`C28/zero-a-floor` — "its real repair waits on its own owner and is not this spec's."

### Track A — checkpoint A, operator work, unchanged

Reachable since `e8e9528`. **Run it by adding the `measure-twin-regret` label to PR #84**, then
removing it. `workflow_dispatch` cannot reach a workflow absent from `main`; `pull_request` can.

1. Label PR #84. Read `regret`, `interval_low`/`interval_high`, `comparator_headroom`,
   `margin_rule`, `margin_rule_derives`, `margin_rule_below_headroom` and
   `interval_excludes_rule_margin` from `artifacts/uplift/twin-regret.json`.
2. **One ADR-055 D2.5 amendment, one commit, one amendment-log line, covering BOTH owed amendments.**
   State the derived value as a literal on **exactly one line** — that is what the parked pin anchors
   to (finding 20) — and correct `bracketing.upper` if the measured headroom moved from
   `11.79 - 2.93 = 8.86`, which is prose and is not pinned. D2.5's own rule puts this **before**
   dispatch 2.
3. **Commit `materiality_margin.value`** (`5.0 * 0.01 * 8.0` = `0.40`) and **graduate the parked
   pin** from `pending_pins:` into `pins:`. Read finding 20 first; do not author a fresh pin. No
   second `ratchets.json` entry is owed. Discharges **10.4**.
4. **Label a second time.** Finding 16, not optional: run 1 cannot exercise
   `must_be_below_measured_headroom` and reports `verdict: unavailable`. Discharges **11**.
5. Record task 11's verdict against `SESSION_PROTOCOL.md`'s four-value table.

### Track B — what remains of session 2r

6. **Tasks 27.1–27.4 are `[x]`.** Nothing further is authorable under parent 27.
7. **Task 27.5 is a CI read**, blocked behind decision 1 and then decision 2.
8. **Tasks 26.2 / 26.3** — the regeneration, now on the critical path. Confirm **two** things when it
   lands, not one: C56 goes PASS, **and** the falsification sweep's probeable set returns to **8**.

---

## Read these first, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the cap, the three marks, the four
   checkpoints, the batch plan, the six cheap gates.
3. `CLAUDE.md` — 14 invariants, honesty contract, gate registry, `E-S*` lessons.
4. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
5. `.cursorrules` + `docs/cursor/*.md`.
6. `docs/adr/ADR-055-twin-decision-relevance.md` — the record this phase executes against.
7. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`.

### The ledger has three marks and four sources

`[ ]` open · `[~]` **authored, discharge pending** — not a pass, and it carries a `discharge:` line
naming the job that owes the proof · `[x]` done **and** discharged. An *open* leaf with a
`discharge:` line is CI-gated and is not authorable work.

Authoritative: `tasks.md` checkboxes for state, `spec_ledger_census` for every count, this file for
what executed. **`tasks.meta.json` is not authority.** **And disk outranks all four.**

---

## Session 2r — five findings, two conflicts, and the batch's premise was inverted

### Conflict I — CI's step 8 is not the command the baseline was measured at

**This is the finding that reshaped the session, and believing the record would have cost it.**

```yaml
- name: MyPy strict type check (orchestrator — blocking)
  run: mypy --strict orchestrator/ --exclude orchestrator/tests
```

`HANDOFF.md`, `tasks.md:2657` and the standing prompt all said the `78 → 56` baseline was measured
"at CI's exact command", using `python -m mypy --strict orchestrator/`. That command has no
`--exclude`, and `[tool.mypy]` declares none either. **No workflow in the repository runs the wide
command.**

Read from CI's own step-8 log, run `33582858699`: **`Found 3 errors in 3 files (checked 44 source
files)`** against 89 files locally. The 56 decompose by scope:

| bucket | n | gates step 8? |
|---|---|---|
| `orchestrator/` source | **3** | **YES — all of it** |
| `orchestrator/tests/` | 49 | no, excluded |
| `agents/` (followed imports) | 4 | no, step 9 is `continue-on-error: true` |

The exclusion is effective because nothing imports `orchestrator.tests` — grepped, not assumed. The
bucket-A count **equals CI's 3 exactly**, so the path filter was validated against CI's own log
rather than trusted.

**The work order was therefore inverted.** It ranked 27.2's 24 `arg-type` first and flagged 27.3's
`import-untyped` as *"may not be repairable here… the honest outcome is a recorded deferral."* All
three gating errors were `import-untyped`. **A deferral would have been honest and would have left
`uplift-verify` dead** — the one outcome the batch existed to prevent. The 24 `arg-type` errors gate
nothing.

Two sub-corrections: the caveat "the absolute CI count may differ because the local environment has
no `types-PyYAML`" is weaker than recorded in that direction — `types-PyYAML` appears in exactly one
place in the repo, `.pre-commit-config.yaml`'s `additional_dependencies`, so CI's `quality-gates`
installs no stubs either. The real divergence risks are the scope above and `mypy>=1.10.0,<2.0` in
`packages/requirements-dev.txt`, an unpinned floor.

### Conflict J — the stated HEAD was three commits stale

The prompt gave HEAD `5bcf42c` and "24 commits ahead". `.git/refs/heads/feat/decision-quality-proof`
held **`1508685`**, and the branch reflog shows `5bcf42c → be666ea → e8e9528 → 1508685` — so
`e8e9528`, finding 23's actual repair, is absent from the commit table that describes it as done.
Benign, but do not carry "24 ahead" forward.

### Finding 24 — ownership was misfiled, in the opposite direction this time

`tasks.md` said *"All 78 originate from commit `e000258`; none is on `main`."* **False.** Nine of the
twelve files carrying the remaining errors, and both `agents/` files, were last touched by ancestors
of `origin/main`, so their content is byte-identical to `main` and their errors are `main`'s. The
largest single file, `test_brownout.py` with **26** of the 56, is `be3edd1` — on `main`.

**And `git log -1` reports LAST TOUCH, not authorship — which misled this session too.**
`test_cognition_phase.py` resolved to `e000258` and looked like this branch's. The file also exists
on `main`; `git diff origin/main` showed the failing assertion **unchanged from `main`**, and
`git show origin/main:<file>` run as a probe **fails there too**. When a file exists on both
branches, attribute the *line*, then confirm by executing `main`'s version.

### Finding 25 — mypy's incremental cache hides a per-module override change

After adding the `yaml.*` override, `mypy --strict orchestrator/ --exclude orchestrator/tests` still
reported the same 3 errors. Not a failed repair: a **stale cache**. A cache entry is keyed to the
*importing* module, while `ignore_missing_imports` belongs to the *imported* one, so mypy reused
`chain_walk`'s entry. `--no-incremental` reported `Success: no issues found in 44 source files`.

**A cached mypy run is a claim about the cache as much as the code** — the same shape as session 2q's
PowerShell splatting bug, where a gate's non-zero exit was a claim about its invocation. Use
`--no-incremental` for any measurement that follows a config change.

### Finding 26 — `comparison-overlap` found two assertions that CANNOT FAIL, and a third was next to them

The work order said a comparison mypy proves can never be true is usually a real defect. Both were
real, and both were the *mirror* case — comparisons mypy could prove **decided**:

- `test_data_provenance_builder.py` asserted R4.4's distinctness clause *after* two equality
  assertions had narrowed both operands to distinct `Literal`s. Moved above them, it can fail.
- `test_protocol.py` asserted the FSM reached `COLLECTING` after a mutating `transition()`, but the
  preceding `== IDLE` assertion narrows the member expression and mypy does not discard that across
  the call — so the assertion was provably **false**. Each observation is now bound to a fresh local
  where it is observed.
- Beside them, `union-attr` in `test_brownout.py`: `.current_level()` called straight through
  `get_controller()`, typed `BrownoutController | None`, so a registration failure raised
  `AttributeError` instead of failing the assertion the test is named for.

**"A number that cannot fail is not a number" applies to assertions too.** The same mypy
member-expression narrowing explains four of 27.4's seven unused ignores — one mechanism, two
opposite symptoms.

### Finding 27 — a test in `main` asserts nothing at all

`test_protocol.py::test_tier1_skips_debate` builds a tier classification, installs it, and then
**contains no assertion** — only three comment lines describing what it would verify. Untouched
beyond the type repair, because it is `main`'s and rewriting it is not this batch's remit. Recorded
because it is the same defect class as finding 26 and nothing else names it.

### Finding 28 — clearing a gate reveals what it was shielding, and here it was three more things

Step 8's failure was hiding **15 steps** in `quality-gates`. Clearing it exposed C56 immediately, and
local measurement plus `main`'s history predicts two more obstructions behind that. Session 2p's
lesson was "read what got SKIPPED behind the failure." The stronger version: **the depth of the
chain is unknown until each layer is cleared, so no single clearance licenses a claim about the
job at the end of it.**

---

## What session 2r changed

### `b7954b6` — the three errors that were the entire gate

`pyproject.toml` gained `[[tool.mypy.overrides]]` for `yaml.*` and `psycopg2.*` with
`ignore_missing_imports = true`, clearing `orchestrator/audit/chain_walk.py:98`,
`orchestrator/consensus/protocol.py:42` and `orchestrator/audit/data_provenance.py:166`.

**Chosen by the operator over installing the stubs, and it is the mechanism this file already uses
for 27 other packages** including `scipy`, `pandas`, `sklearn`, `redis` and `simpy`. It is a
declaration about a third-party package's stub availability, not a check weakened on first-party
code — and **inference is unchanged either way**, because with the stubs absent mypy already models
both modules as `Any`. So the override removes the report and nothing else; no new `no-any-return`
appeared, which was the predicted risk and did not materialise.

`types-PyYAML` stays uninstalled: it unmasks seven pre-existing errors under `uplift/` that the
pre-commit mypy hook reports against commits to files which do not contain them. `psycopg2` is
imported lazily inside a `try/except ImportError` that degrades honestly (I-7) and appears in **no**
requirements file, so its presence is a deploy-time fact, not a type-time one.

Pushed alone and first, deliberately: CI then ran the real verification while local work continued.

### `743ca6b` — 56 → 0 across the wide command

| code | before | after | owner |
|---|---|---|---|
| `arg-type` | 24 | 0 | 27.2 — **one declaration** |
| `import-untyped` | 4 | 0 | `b7954b6` |
| `type-arg` | 5 | 0 | 27.3 |
| `no-any-return` | 5 | 0 | 27.3 |
| `no-untyped-def` | 4 | 0 | 27.3 |
| `attr-defined` · `union-attr` · `comparison-overlap` | 2 · 2 · 2 | 0 · 0 · 0 | 27.3 |
| `method-assign` | 1 | 0 | 27.3 |
| `unused-ignore` | 7 | 0 | 27.4, last |

Every code reached zero; no new code appeared. **No `# type: ignore` was added anywhere**, no
argument gained a default, nothing was widened to `Any`, and mypy's scope was not narrowed.

**27.2 was diagnosed before it was repaired.** All 24 are two distinct messages — argument 2 and
argument 3 — across 12 call sites, every one supplying a `_FakeBreaker`. Uniformity was
*established* by grouping the captured messages, not inherited from 27.1. `BrownoutController` reads
exactly one attribute from a breaker, `.state`; declaring the parameters as the whole `AsyncBreaker`
overstated that, and the overstatement was reported 24 times at the call sites rather than once
where it lived. Repaired with a read-only `BreakerStateSource` Protocol, which `AsyncBreaker`
satisfies structurally because its `state` **is** a read-only property returning `BreakerState`. No
production call site moves.

**`warn_unused_ignores` did not move in both directions.** The count held at exactly 7 across 27.2
and 27.3, measured. The hazard that sequenced 27.4 last did not fire — recorded because a prediction
that does not fire is still worth knowing, and it is why one clearing pass sufficed.

**27.4's seventh ignore needed judgement.**
`test_confidence_gate_universality_property.py:640` carried `[method-assign,assignment]` and mypy
proved only `assignment` redundant. The compound loses that code and keeps the one still working.
That is **not** re-narrowing an unused ignore to keep it alive — the ignore is used; one of its two
codes was not. Lines 638 and 639 are identical in form and were *not* reported, so the distinction
is mypy's.

---

## Honesty ledger — verified vs merely authored

### Executed and green, session 2r

| What | Result |
|---|---|
| **`ci.yml::quality-gates` step 8, on CI** | **success** on run `33588706405` — first time on this branch |
| `mypy --strict orchestrator/ --exclude orchestrator/tests` (CI's exact command) | exit **0**, `no issues found in 44 source files` |
| `mypy --strict orchestrator/` (wide) | **56 → 0**, exit 0, 89 source files, decomposed per code above |
| `ruff check` / `ruff format --check`, CI's exact scope | **0 / 0**, 386 files |
| `pytest` over the 13 touched loci, `HYPOTHESIS_PROFILE=dev` | **191 passed, 18 skipped, 5 deselected, 1 failed** (the pre-existing `main` failure) |
| Six cheap gates | `workflow_shape_truth` **0** (379 steps), `pin_extractor_truth` **0** (**14** declared/probed), `sweep_budget_truth` **0**, `dataset_licence_truth` **2** (honest SKIP), `task_claim_truth` **1** (pre-existing, `core-purpose-uplift`), `gate_surface --check` **0** (542 rows) |
| `spec_ledger_census --files --check` | exit **0**; 57/3/80 → **61/2/77** |
| Line endings | all 16 written files `w/crlf` or `w/lf` per file, **none `w/mixed`** after repair |
| Bytes | all 16 verified: **no BOM, no U+FFFD** |
| Process sweep | see below |

**mypy invocations spent, honestly counted.** The budget was four passes of the wide command; **three**
were spent (baseline, after 27.2+27.3, final). 27.2 and 27.3 own **disjoint** error codes, so one
pass attributes both unambiguously per code — the saving cost no attribution. Three cheaper
invocations were also spent and are not wide passes: two at CI's narrow scope (44 files) and one
single-file probe that isolated finding 25.

### NOT executed. Must not be claimed as passing.

- **`uplift-verify`, and therefore Properties 38–60.** Skipped on every push. **This spec's entire
  property surface has never run in CI.** Session 2r cleared obstruction 1 of at least four.
- **`quality-gates` steps 18–23.** Skipped behind C56 on this branch **and on `main`**. Their state
  is unknown, which is not green.
- **`.github/workflows/regenerate-truth-docs.yml` has never executed.** Task 26.1 stays `[~]`.
- **`ledger_gen`, `readme_gen`, `verify_claims`, `doc_truth`** — not run locally in any form. I-0.
- **The five slow-marked tests in `test_confidence_gate_universality_property.py`.** Deselected by
  `-m "not slow"`. Line 640 was edited; that edit is diagnostics-verified, not executed.
- **`vitest` locally. At all.**
- **`uplift/regret.py::_measure`'s wired interval path.** Discharges at checkpoint A.
- **`digital_twin/tests/test_env_response.py`** — module-skipped, `gymnasium` absent.
- **`tests/uplift/test_aggregation_integrity_property.py::test_aggregation_integrity_under_failures`**
  — pre-existing float fragility, diagnosed, not repaired.
- **The behaviour of `newsvendor.py` on a negative lead time.** `_sqrt` raises
  `ValueError: math domain error` where `** 0.5` raised `TypeError` from `max(0.0, <complex>)`. Both
  fail; the change is on input already invalid and is **not** covered by a test.

### The lesson from this session

**A measurement taken at the wrong boundary can be exactly reproducible and still wrong about what
it means.** The 56-error figure reproduced to the error, per code, on the first attempt — and it
described a command no gate runs. Reproducibility is not relevance. The check that caught it cost
one `gh` API read of the log of the step being claimed, which is free under I-0, and it should have
been the first action of three sessions rather than the first action of this one.

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
| Conflict E (2p) | **`material` requires an interval excluding the margin, stricter than R5.3.** |
| Interval estimator (2p) | One estimator, `uplift/interval.py`. `alpha` read with `yaml`, not `load_contract`. |
| `gate_surface` (2p) | The **sixth** cheap gate. `ledger_gen` went onto the never-run list. |
| Local Biome/tsc (2p) | Installed binaries may run on changed files or `./src`. **`pnpm` banned**, `vitest` banned. |
| Task 6 (2q) | **Survivor list accepted; C28's repair deferred to its owner.** E1 closed. |
| Conflict F (2q) | **The `confidence_threshold` repair is at the declaration, never at the call sites.** |
| Conflict G (2q) | **A dispatch-only job owes no `required-checks.yaml` entry.** |
| Regeneration (2q) | **A CI job that uploads an artifact**, not a local `--write` and not an auto-commit. |
| Batch order (2q) | **Session 2r precedes session 2.** |
| Conflict H (2r-pre) | **The derived-margin pin is PARKED in `pending_pins:`.** `required: false` rejected — a pin that cannot fail is not a pin. |
| Track coupling (2r-pre) | Independent in CI triggering only. **The regeneration goes last** — *now contested by C56 blocking 27.5; see decision 1.* |
| Dispatch mechanism (2r-pre-c) | **Checkpoint A runs by LABEL, not by dispatch, and `main` is not touched.** Both guards are **allow-lists**; `uplift-proof` is excluded from `pull_request` because its provenance gate reads `GITHUB_SHA`, the merge commit there. |
| **Conflict I (2r)** | **CI step 8 excludes `orchestrator/tests`; the wide command is run by no workflow.** The 56-error baseline over-described the gate by a factor of ~19. |
| **`import-untyped` (2r)** | **`ignore_missing_imports` for `yaml.*` and `psycopg2.*`**, chosen over installing stubs. Precedent: 27 sibling entries. Inference unchanged; the module was already `Any`. |
| **Scope (2r)** | **The full wide 56 was cleared**, not only the 3 that gate step 8 — operator's choice, so `mypy --strict orchestrator/` is green locally as well as in CI. |
| **Obstruction 3 (2r)** | **`test_cognition_phase`'s failure is `main`'s and is NOT adopted.** Diagnosed and handed over. Precedent: C28. |

---

## Environment notes and traps

- **NEW: a cached mypy run can hide a `[[tool.mypy.overrides]]` change.** Finding 25. Use
  `--no-incremental` for any measurement taken after a config change.
- **NEW: `git log -1 -- <file>` is last-touch, not authorship.** If the file also exists on `main`,
  `git diff origin/main -- <file>` the line and, when it matters, execute `main`'s version via
  `git show origin/main:<file>` written to a scratch path.
- **A `ruff format --check` diff whose two sides look identical is a LINE-ENDING diff.** Fired for
  the **fifth** session running: all 11 programmatically edited files reported `w/mixed`
  immediately. Repair with Python at `newline=''`, normalising to the file's *dominant* ending —
  count first: `pyproject.toml` was 231 CRLF / 25 LF, `test_hash_chain.py` 286 / 3, and
  `test_confidence_gate_universality_property.py` is **pure LF** and must stay LF. **Check
  `git ls-files --eol` after every programmatic edit**; the editor tool preserves endings
  inconsistently, so the check cannot be skipped on the strength of a previous file.
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** `Get-Content` also
  *displays* em dashes as mojibake while the file is clean — verify bytes, do not trust the console.
- **PowerShell mangles box-drawing characters and em dashes**, so `Select-String` on a CI step name
  containing one finds nothing. Match on an ASCII substring of the name instead.
- **PowerShell strips double quotes inside single-quoted `--jq`.** Capture `gh api` into a variable
  and use `ConvertFrom-Json`. `>` writes UTF-16; no heredocs — `git commit -F` a temp file.
- **`$LASTEXITCODE` is unreliable after a native command is piped through `Select-String`.** It read
  `-1` for a census run whose own report said `exit 0`; re-run with `*> $null` to read it.
- **`git status` over-reports on this tree.** Trust `git diff`, and stage precisely.
- **The local clock runs ~2h45m ahead.** Identify a run by `head_commit.message` or sha, never by
  timestamp.
- `types-PyYAML` is now moot for `orchestrator/` (finding: the override), but **do not run
  `pre-commit install`** — it installs the stubs and unmasks seven pre-existing errors under
  `uplift/` that block commits to files which do not contain them.
- Python 3.14.0, **mypy 1.19.1** locally against CI's unpinned `mypy>=1.10.0,<2.0`, pytest 8.4.2,
  hypothesis 6.151.11, jsonschema 4.26.0. `gymnasium` absent. `frontend/node_modules` installed.
  `gh` 2.82.0, authenticated.

---

## I-0 — the rule most likely to burn the machine

**Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
`mutmut`); any `MIN_SCENARIOS`-scale or training workload.

**Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
`pnpm` anything. **`regenerate-truth-docs.yml` is the sanctioned route for the middle two.**

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, **one** scoped `pytest`
run, `spec_ledger_census`, the **six** cheap gates, the `biome`/`tsc` binaries on changed files, and
**`gh` API reads — which are free and which this session should have spent sooner.**

**`mypy --strict orchestrator/` is category 2.** Session 2r spent three wide passes of a four-pass
budget, plus two narrow and one single-file invocation, each recorded above.

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.**

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — if measured `(s, S)` regret is at or above the R5.2 margin **with its
interval excluding it**, **Finding 4 is falsified. Stop.** R5 is re-cut (R5.3, R5.4). Report it
plainly; it is a good outcome.

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and **the experiment must NOT be run.**

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor stays
at `0.0`, no headline is published as a gain, and the result is written up as a finding — not
reframed, not re-run at a different replicate count until it moves, not held back pending a "better"
configuration. A null from a **validated** instrument on a **decision-relevant** world is worth more
than the tautological PASS it replaces. **A number that cannot fail is not a number** — and session
2r found three assertions in the same condition.
