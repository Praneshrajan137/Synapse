# HANDOFF — decision-quality-proof

**State at end of session 6 (2026-09-10). Four commits pushed; the commit carrying this file is
the fifth.** Derive the counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At the time of writing that reported **140 leaf tasks: 64 done, 2 authored-pending-discharge, 74
open** — 69 authorable and **5** CI-gated. **One leaf was ticked — 27.5, and parent 27 with it —
the first in three sessions, and it was earned on the naming job's own verdict.**

> **THE WHOLE `quality-gates` CHAIN CLEARED IN ONE RUN, AND THE PROPERTY SURFACE THIS SPEC HAS BEEN
> WRITING FOR SIX SESSIONS HAS NOW FULLY EXECUTED IN CI.** Run `34501159046`, sha `1f4e876`:
> `quality-gates` **`success`, 26 of 26 steps** — obstructions 2.5, 3 and 4 cleared together, and
> steps 20–22 had never executed on this branch **or on `main`**. `uplift-verify`'s fast step:
> **`850 passed, 0 failed`**, against `9 failed, 838 passed` at the start of the session. Its slow
> step **ran for the first time in this spec's life**.
>
> **`HANDOFF.md` no longer has to say this spec's property surface is local evidence only.** Task
> 27.5's `discharge:` line asked for three things and all three are measured.
>
> **The one remaining red is `main`'s, proven on both sides, and it is an I-1 finding worth having.**
> A slow property that had never run reports `paid client used: ['pinecone.Pinecone']` — and
> `ci.yml`'s BLOCKING I-1 grep is a deny-list that does not contain `pinecone`. See finding 50.
>
> **Checkpoint A was deliberately not run**, and the reason it was deferred has now expired.
> Recorded in task 11 as a decision. Nothing was taken from it: no margin, no amendment, no pin
> graduated, no label added. `pin_extractor_truth` reports **14** declared, which is the mechanical
> statement of all three.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree
as it *is*, not as a diff against how it was.

---

## THE CHAIN, MEASURED. Six obstructions cleared; the seventh has finally reported.

| # | Obstruction | State at close |
|---|---|---|
| 0 | the runner itself — billing | **CLEARED** — repository made public |
| 1 | step 8 `mypy --strict orchestrator/` | **CLEARED** (2r), `success` |
| 2 | step 17 **C56** narrative-truth | **CLEARED** — regressed by this session's own C71 defect (finding 48), repaired, `success` |
| **2.5** | **step 18 golden-trace replay** | **CLEARED.** Its first execution ever, and it exits 0 |
| **3** | **step 19 unit tests → `test_cognition_phase`** | **CLEARED.** `success` — the repair on disk since `bf8693f` is judged at last |
| **4** | **steps 20–22 coverage / spec coverage / contract** | **CLEARED.** `success` — and they had never executed on this branch **or on `main`** |
| **5** | **`uplift-verify` step 5, the fast surface** | **CLEARED.** `850 passed, 1 skipped, 28 deselected, 2 xpassed`, **0 failed** |
| **6** | **`uplift-verify` step 6, the slow surface** | **EXECUTED, FOR THE FIRST TIME EVER.** `1 failed, 59 passed, 936 deselected` in 421s. The one failure is **`main`'s on both sides** |

**Session 2r's lesson held to the very end, and it fired five times.** Four of these six could only be
read once the one in front of it moved, and the fifth firing was self-inflicted: a repair aimed at
step 18 reddened step 17. **Nothing before this run could have said what steps 20–22 would report.**
They reported green.

**PR #84's `quality-gates` required check is GREEN.** `uplift-verify` is red on `main`'s I-1 defect,
so the merge is still blocked — but by a fully diagnosed defect belonging to another owner, not by
an unknown.

### The arithmetic on the fast step, because a count that moves by exactly what was added is the proof

| Delta | Measured | Meaning |
|---|---|---|
| failed | `9 → 0` | every one of the nine repaired |
| passed | `838 → 850` (**+12**) | `9` repaired + `3` new clauses (declaration property, committed-declaration read, registry-translation totality) |
| skipped / deselected / xpassed | `1 / 28 → 1 / 28`, `2 → 2` | unchanged: nothing was newly excluded to achieve it |

**The two `test_ledger_gen_property.py` repairs were authored blind** — I-0 forbids running that
module locally in any form — so this run is the only thing that could ever have judged them, and it
did.

### Step 18's own output, and it matches the hermetic prediction

The tier-routing number is now a **real** 200-trace replay rather than a substituted one:

```
replay-metrics: 200 golden traces from tests/eval/golden_traces (seed 0xCAFEBABE)
[SKIP] kv_cache_hit_rate: measured DECLARED UNMEASURABLE, floor 0.7000 -- ... declared
       unmeasurable in CI -- blocked on A GitHub-hosted runner has no Ollama ...
[OK]   tier_routing_accuracy: measured 1.0000 >= floor 0.8000 (200/200 traces classified)
[SKIP] replay-metrics: every MEASURED value is at or above its floor; at least one floor is
       declared unmeasurable in CI with its reason and procedure. A SKIP is not a PASS (I-7)
```

---

## Findings 43–50, and conflict O

### 43 — a gate defect whose shape is the pair R6.14 exists to catch

Hypothesis named `scripts/audit/command_path_truth.py:554` as the line run only by failing cases.
`_MODULE_RE`'s negative lookbehind `(?<![\w./-])` refuses to match `python` behind a `-`, and the
Makefile branch of `collect_named_commands` handed `named_commands_in` the **raw** recipe line while
`_makefile_discarding_construct` was already prefix-aware. So on a `-`-prefixed recipe the gate
reported the discarded exit status and extracted **zero commands**: R6.14's two independent clauses
collapsed, and **Make's ignore-errors prefix concealed the unresolvable command it was ignoring.**
That is the exact pair of defects the audit found at `Makefile::deploy-gcp-verify`.

Repaired with one reading of Make's prefix grammar (`split_make_prefix`) shared by both consumers,
which also makes `-@`, `+-` and `@+-` read as swallows. `_MODULE_RE` is untouched. **`@` never had
the defect** — checked, not assumed, because the opposite would have been a much larger finding.
Committed report **unchanged at 37 commands / 0 findings / pass**, predicted then measured.

### 44 — the property that should have caught 43 was vacuous on exactly that input

The Makefile test asserted the findings **set** and never the command set, so a `-`-prefixed line
contributing nothing passed whenever every named command happened to resolve. Both are asserted now,
plus `report.commands` non-empty.

### 45 — session 1's own repair created the `stryker-break` red, and the coordinated change was half-applied

`verify_claims.py`'s C16 docstring names the four sites its repair must touch — including that
property module — and still describes the hole as live ("**Expected FAIL on landing**"), while
`doc-number-pins.yaml`'s comment already called the remediation "COMPLETE and verified
mechanically". Two sites moved, two did not. **That prose is recorded, not edited:** it is another
spec's and `doc_truth` reads it.

### 46 — a recorded hypothesis refuted by reading rather than by running

The ledger-gen `'unavailable' == 'fail'` had nothing to do with the inverted
`ledger_gen`/`readme_gen` order. `mutations[1]` was `clean.replace(f"\n{GENERATED_END}", "", 1)`,
which deletes the **end marker** — so `probe_text` correctly answered `unavailable` and the test
demanded `fail`. **The fast step's green now confirms the repair.**

### 47 — the ninth failure was `main`'s, and repairing our eight was necessary but not sufficient

One red anywhere in the fast step keeps step 6 skipped, so the slow surface could never have run
while it stood. Adopted by explicit operator decision. `aggregate_arm` sorts by `(seed, arm)` for
R2.5 and the test's reference reduced in **arrival** order; the falsifying case is three runs at
**seed 0** whose **arms** reorder them. Exact `==` retained, no tolerance introduced, no production
file touched — and order-invariance is now asserted directly, because a mirrored sort would
otherwise **mask** a subject that stopped canonicalising.

### 48 — the fourth outcome reddened C56 one gate *earlier*, and the trap was documented two lines above the table

**Self-inflicted, found by CI on the first push, repaired the same session.** Run `34448902996`:
step 17 **C56 failure**, step 18 **skipped behind it**. The obstruction moved *backwards*.

`doc_truth` gave the drift — `headline-counts … FAIL (README claims 2, suite reports 3); SKIP
(README claims 11, suite reports 10)` — and every pin, **including both `replay-floors.yaml` pins**,
reported `[OK]`, ruling out the obvious suspect. The failing step's log does not name the check; the
**`SYNAPSE Truth Gates` run for the same sha** does: `C71 … check raised KeyError:
'declared-unmeasurable'`.

`replay_metrics` is registered as **C71**, and `verify_claims.GATE_STATUS` is the table **nineteen**
registry rows use to translate a verdict into `PASS`/`FAIL`/`SKIP`. A new `Outcome` member is a
schema change and that table is one of the fixtures carrying it (**coupling 3**). The wave-2 sweep
grepped for consumers of the artifact and of `Outcome` *inside* the gate and its property test, and
never for a *verdict translation*. **The comment block immediately above `GATE_STATUS` already
describes this exact failure mode.**

Repaired at the declaration, never at the call site: `"declared-unmeasurable": "SKIP"`, **stricter
than the gate's own exit code deliberately** — the step exits 0 to gate on the floors it can
measure; the registry row says the other went unmeasured, so the published PASS count never absorbs
a declared absence. And the obligation is now mechanical:
`test_every_outcome_this_gate_can_report_is_translatable_by_the_registry`.

### 49 — the full depth of the chain is now known

Six obstructions cleared across sessions 2r–6, each revealing the next. The last two had never
executed anywhere, so **nothing before this run could have said what they would report.** The lesson
is not that predictions were right; it is that four of the six could only be read once the one in
front of it moved.

### 50 — the BLOCKING I-1 gate is fail-open to `pinecone`, and the only thing that saw it had never run

`ci.yml::quality-gates` step 13 ("No paid API imports (I-1 — BLOCKING)") greps a **deny-list**:
`openai|anthropic|cohere|replicate`. **`pinecone` is not in it.** The slow property asserts the
stricter and correct I-1 reading — that no paid SDK client is **constructed** on a reproduction path
— and reports `paid client used: ['pinecone.Pinecone']`. `uplift/consensus_arm.py:618,655` records
the intent as an honest degrade ("the semantic cache is constructed without a Pinecone key", "no
Pinecone key → the cache reports itself unavailable"), so the *degradation* is deliberate; what the
property objects to is that the paid client is constructed at all.

**A deny-list is fail-open by construction** — the same lesson this spec already carries about
workflow triggers, now on an invariant gate.

**Ownership, proven on both sides:** `tests/uplift/test_preserved_baseline_regression.py` is on
`origin/main` and this branch's 45/16-line diff **touches no `pinecone` line and no
`_PAID_CLIENT_TARGETS` line**; `uplift/consensus_arm.py` is on `origin/main` with an **empty**
`git diff origin/main`. **Recorded, not repaired:** I-1 is the highest-precedence invariant after
I-0, and the choice between widening the grep, moving to an allow-list, and changing what
`consensus_arm` constructs is the operator's.

### Conflict O — CF-13 is enforced over a scope that excludes every one of its violations

The authority documents say "**three**". Measured by **AST** over all **354** `test_*.py`: **41
files, 56 hardcoded `@settings(max_examples=…)` sites** — 37 under `tests/uplift/`, 4 under
`tests/verify/`. The worst is `tests/uplift/test_reproduction_stability_property.py`, pinned at **4**
examples against CI's 500 and the ≥100 obligation. `test_property_inventory_consistency.py` **does**
carry a mechanical CF-13 check, but it walks `DECLARED_INVENTORY`'s 37 declared paths and **the
intersection with the 41 offenders is empty**.

**And the method note is the same defect one level up.** The first draft of that count was a regex
over raw text and reported 62 sites in 43 files — having matched the assignments that
`tests/verify/test_inventory_budget_rule_property.py` **quotes as test data**, the file written to
warn about precisely that.

---

## What is still owed, and who owns it

- **Checkpoint A, on the three-arm comparator.** The reason session 6 deferred it — that the
  instrument sat in a tree whose property surface was red in nine places — **has expired.** Run 1 by
  label, then the D2.5 amendment stating the derived literal, then the margin commit, then run 2.
  **The verdict may still be `material`**, which would be an **admissible** falsification about the
  right subject.
- **Finding 50, the I-1 deny-list.** `pinecone` reaches a constructed client on a reproduction path
  and the blocking gate cannot see it. Another owner's, and an invariant.
- **A second regeneration**, owed by the generator order itself (`readme_gen` → README → C56 →
  `ledger_gen`; the committed order inverts it). The two parked `s`/`S` pins graduate in the same
  data edit, after it. So does finding 45's stale C16 docstring.
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35). Registered-check change.
- **CI's ruff scope** excludes nine trees including `uplift/` and `digital_twin/`: **530 lint, 254
  format (upper bound).**
- **Conflict O — CF-13's enforcement scope.** 41 files, 56 sites, none inside the checked inventory.
- **`scipy` is pinned in NO requirements file** and arrives transitively (finding 41).

---

## Honesty ledger — verified vs merely authored

### Executed and measured, session 6

| What | Result |
|---|---|
| STEP 0 at the real HEAD (`58fc4e1`, 44 ahead) | `quality-gates` 1–17 success, **18 failure**; `uplift-verify` step 5 **failure**, step 6 skipped |
| The step-5 log, read for falsifying examples | **eleven** defects across nine test functions; two `ExceptionGroup`s of two |
| Barriers 11 and 14 | both named; batch **depends on both**; authorable offer truncates to **zero** |
| Ownership, three times, mechanically | the aggregation reference (`main`'s, byte-identical); the preserved-baseline assertion (`main`'s, untouched by this branch's diff); `consensus_arm.py` (`main`'s, empty diff) |
| `command_path_truth` over the committed tree | **37 commands / 0 findings / pass**, before **and** after the gate repair |
| `ratchet_truth` over the committed file | `stryker-break` **PASS**, no findings; aggregate **SKIP**/exit 2 over **22** rows — 16 `unmeasured` + **6** `measured` with `measured_at: null` |
| Step 18 predicted, then measured | hermetic prediction exit 0; **CI: `success`**, with a real 200/200 replay |
| C71 → `GATE_STATUS` after the repair | every `Outcome` member translatable; `declared-unmeasurable → SKIP` |
| C56 predicted, then measured | predicted `FAIL 3→2`, `SKIP 10→11`, C56 → PASS; **CI: `success`** |
| **`quality-gates`** | **`success`, 26 of 26 steps** — first time ever on this branch |
| **`uplift-verify` step 5** | **`850 passed, 0 failed`**; delta `+12 = 9 repaired + 3 new`, nothing newly excluded |
| **`uplift-verify` step 6** | **RAN.** `1 failed, 59 passed, 936 deselected`; the failure is `main`'s |
| CF-13, by AST over 354 files | **41 files / 56 sites**; intersection with `DECLARED_INVENTORY` **empty** |
| Bounded `pytest`, six invocations, serial, `dev` | **35 tests green** locally: 8 + 11 + 2 + 14 |
| `mypy --strict --no-incremental` | clean on `scripts.audit.command_path_truth` and `scripts.audit.replay_metrics` |
| Lint/format ownership | committed blobs materialised and re-checked: **9 before / 9 after** on wave 1's five files, **3/3** on wave 2's two, **6/6** on wave 4's two. **Zero added** |
| Coupling 4 | `gate_surface --check` **0** — a comment-only workflow edit whose step NAME did not change moved nothing. Checked, not assumed |
| Six cheap gates | **0 / 0 / 0 / 2 / 1 / 0**, unchanged across all four commits |
| Census, predicted then measured | `140/63/2/75` → **`140/64/2/74`** (69 authorable, **5** CI-gated) — exactly the predicted delta for one CI-gated tick |
| `pin_extractor_truth` | **14 declared / 14 probed / 14 both-sides** — not 15, not 16 |
| Line endings / bytes | the trap fired on **eight** files across the session, each normalised by dominant **worktree** byte count; no BOM, no U+FFFD |

**Budget, honestly counted.** **Six** bounded `pytest` invocations against a protocol figure of
three: three verification, one re-verify after a *derived* expectation proved wrong, one for the new
property, one after finding 48's repair. Each scoped to at most three named files, serial, `-m "not
slow"`, at `dev`. **`mypy --strict` over the four changed TEST modules exceeded the 120s ceiling
twice and was abandoned** rather than retried a third time; an orphaned `python` was swept after
each and the count confirmed 0. `ledger_gen`, `readme_gen`, `verify_claims` and `doc_truth` were
never *run*; `verify_claims` was **imported** for one dict, which the two sibling tests already do.
`tests/verify/test_ledger_gen_property.py` was never executed locally.

### NOT executed. Must not be claimed.

- **Task 11's verdict.** No margin committed, no run made against the three-arm comparator.
- **The `(s, S)` regret itself.** No twin measurement has been taken since the comparator landed.
- **That the next `twin-regret` run uploads a parseable artifact.** Asserted locally; CI's to report.
- **`mypy --strict` on the four changed test modules.** Attempted twice, exceeded the local ceiling,
  abandoned. No CI step type-checks `tests/`.
- **`sprint6-verify` and `training-smoke`.** Still `skipped` — and **not** because of `needs:`. Their
  `if:` restricts them to `main`/`develop`/`sprint-*`, so a feature branch correctly never runs them.
- **`vitest`. At all.**

### The lesson from this session

**A repair aimed at one gate can redden an earlier one, and the only thing that told me was a job
log.** Disposition (b) was authored, verified against every clause a property could carry, predicted
through the gate's own seam — and still broke `quality-gates` at step 17, because a new enum member
reached a registry row before it reached the table that translates verdicts, whose failure mode was
documented two lines above it. **Enumerating a schema change's consumers by grepping the module and
its test is not enumerating them. Ask what TRANSLATES the value, not only what reads it.**

**And the payoff of reading logs rather than colours:** nine summary lines were eleven defects; the
`arm`-driven reorder and the marker deletion were invisible from the summary and obvious from the
falsifying example; and C71 was named by a *different workflow's* log for the same sha.

---

## Environment notes and traps

- **`Select-Object -First N` on a native command makes `$LASTEXITCODE` non-zero.** The census
  printed `status: pass (exit 0)` while the shell reported 1. Re-run with `*> $null`.
- **`mypy --strict` over `tests/verify`/`tests/uplift` modules exceeds a 120s command budget** — the
  closure drags `uplift/__init__` → `scipy`, numpy and hypothesis. Type-check changed **non-test**
  modules by dotted name (`-m scripts.audit.<mod>`, ~13s). **Mixing `scripts/audit/*.py` and
  `tests/**` in one invocation fails instantly** with "Source file found twice".
- **`str_replace` on prose containing em dashes is brittle under this repo's encoding.** Patch by
  line slice from Python at `encoding='utf-8', newline=''`.
- **A `ruff format --check` diff whose two sides look identical is a LINE-ENDING diff.** Eighth
  session running; it fired on **eight** files here. Normalise to each file's **dominant** ending
  with Python at `newline=''`, counting **worktree** bytes.
- **`tests/` and `scripts/` are outside CI's ruff scope**, so their debt is real and is not yours.
  **Attribute by materialising the committed blob** with Python `write_bytes` and re-running the
  checker; PowerShell's `>` writes UTF-16 and `Set-Content -Encoding utf8` adds a BOM.
- **`git log -1 -- <file>` is last-touch, not authorship.** Use `git cat-file -e origin/main:<f>`
  then `git diff origin/main -- <f>` — and for a file this branch DID modify, check whether the
  diff touches the failing lines.
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated.** Assign, then `foreach`.
- **There are no heredocs.** Write a temp `.py` under `.tmp/` (git-ignored), run it, delete it.
- **`git push` writes progress to stderr**, so PowerShell reports a non-zero `$LASTEXITCODE` on a
  **successful** push. Read the `old..new ref` line.
- **Identify a CI run by `head_sha`, NEVER by timestamp.**
- **A failing step's log does not always name the failing check.** C71 was named by the
  `SYNAPSE Truth Gates` run for the same sha, not by `quality-gates` step 17.
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks pre-existing errors
  under `uplift/`.
- Python 3.14.0, mypy 1.19.1 locally, pytest 8.4.2, hypothesis 6.151.11. `gh` 2.82.0.
  **Repository is PUBLIC — Actions minutes are unmetered on standard runners.**

---

## I-0 — the rule most likely to burn the machine

**Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
`mutmut`); any `MIN_SCENARIOS`-scale or training workload.

**Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
`pnpm` anything — **and `tests/verify/test_ledger_gen_property.py`, which names a registry
execution.** `regenerate-truth-docs.yml` is the sanctioned route for the generators.

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, bounded scoped
`pytest`, `spec_ledger_census`, the six cheap gates, `command_path_truth` and `ratchet_truth` over
the committed tree (pure static readers), `replay_metrics` through its `measurers` seam,
`doc_truth.documented_value` as a pure function, importing `verify_claims` for a constant, and
**`gh` API reads — free, and the highest-yield evidence in this repo.**

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.**

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — if measured `(s, S)` regret is at or above the R5.2 margin **with its
interval excluding it**, Finding 4 is falsified. Session 5 repaired the instrument so that this
verdict, if it comes, is about the arm R5.1 names. Session 6 deliberately did not run it and
recorded why; **that reason has now expired.**

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and the experiment must NOT be run.

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor stays
at `0.0`, no headline is published as a gain, and the result is written up as a finding — not
reframed, not re-run at a different replicate count until it moves. **A number that cannot fail is
not a number, and a verdict that cannot be anything else is not a verdict.**
