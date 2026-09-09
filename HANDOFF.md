# HANDOFF — decision-quality-proof

**State at end of session 3 (2026-09-09). Two commits pushed; the commit carrying this file is the
third.** Derive the counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At the time of writing that reported **140 leaf tasks: 61 done, 2 authored-pending-discharge, 77
open** — 69 authorable and 8 CI-gated. **Unchanged by this session, deliberately: no task was
ticked and none was attempted.**

> **Session 3 was ended by STEP 0 before it could author anything. CI is still blocked at the
> account level, and the barriers prove that fact is total rather than inconvenient: ZERO of the 69
> authorable leaves are reachable without checkpoint A.** What ran instead was the
> barrier-independent fallback the standing prompt reserves for exactly this case, on the operator's
> explicit word: **route 1** for C56, and the **adopted `test_cognition_phase` repair**, plus the
> **ruff-scope measurement** that makes the third option costable instead of speculative.
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree as
it *is*, not as a diff against how it was.

---

## STOP — CI STILL CANNOT RUN. Proven at this branch's actual head, not inferred.

**Run `34319298176`… every workflow on sha `fe8ddeb` refused to start. Read `34319298166`
(`SYNAPSE CI`):**

```
The job was not started because recent account payments have failed or your spending
limit needs to be increased. Please check the 'Billing & plans' section in your settings
```

Three jobs `failure` in **2–3 seconds with `steps=0`**; three `skipped`. **All eight workflows on
that sha are identical.** Nothing in any of them ran, so none of it is evidence about the code.

**Resolve billing before anything below is attempted.** Checkpoint A's label, the regeneration
label, and every CI-gated leaf assume a runner will start. None will.

### CONFLICT K — the stated HEAD was stale for the THIRD session running

The standing prompt gave HEAD `3b2ec15`, "31 commits ahead", and named run `34315612360` at
`bfad6a0` as the run to check. Disk and `origin` both held **`fe8ddeb`**, **32** ahead of
`origin/main` — which is still `045f44c` and has not moved. So **two** pushes newer than the one the
prompt described existed, each with its own blocked run set. Reading the run for the *actual* head
is what turned "probably still blocked" into proof.

```powershell
git rev-parse --short HEAD                       # trust this, not the prompt
git rev-list --count origin/main..HEAD
gh run list --branch feat/decision-quality-proof --limit 12 --json databaseId,headSha,workflowName,conclusion
```

**Conflict J said "do not carry the stated ahead-count forward". Conflict K is the same defect a
third time. The standing prompt cannot state HEAD correctly, because it is written before the commit
that carries it.** Treat every HEAD and ahead-count in it as stale by at least one commit, by
construction.

---

## THE THING THAT IS BLOCKING EVERYTHING — the chain, with session 3's movement

**`uplift-verify` has still never run, so Properties 38–60 have never executed in CI.**

| # | Obstruction | State |
|---|---|---|
| 0 | **the runner itself** — account billing | **BLOCKED; nothing starts** |
| 1 | step 8 `mypy --strict orchestrator/ --exclude orchestrator/tests` | **CLEARED** session 2r (56 → 0; CI step 8 success) |
| 2 | step 17 **C56**, claim `doc-truth/headline-counts` | red, and red on `main` too. **Its MECHANISM is now unblocked** (route 1, `bbe4278`) — the drift itself is not repaired |
| 3 | step 19 `test_cognition_phase.py::test_run_consensus_streams_correlated_phases` | **REPAIRED ON DISK** session 3 (`bf8693f`), 6 passed locally. **Not discharged** — local green is not CI green |
| 4 | steps 20–22 coverage floors, spec coverage, contract tests | **never executed on this branch or `main`.** Unknown, which is not green |

**Session 2r's lesson holds and got a second confirmation.** Clearing a layer reveals what it was
shielding, and the depth is unknown until each clears. Session 3 moved obstruction 3 off the critical
path *on disk* and unblocked obstruction 2's *mechanism*, and **neither is a discharge.** No single
clearance licenses a claim about the job at the end of the chain.

---

## What is owed right now, in order

### 1. BILLING. Everything else is downstream of it.

### 2. Checkpoint A — track A, the operator's, and its procedure is now correct in `SESSION_PROTOCOL.md`

`SESSION_PROTOCOL.md`'s checkpoint-A section was **stale in four ways** and is corrected (conflict
L, below). Read it there rather than reconstructing it here. In brief: **two labelled runs**, one
ADR-055 D2.5 amendment covering **both** owed amendments, one margin commit that graduates the
parked pin, one recorded verdict.

**The one gap worth carrying in your head:** after graduating the pin, **no cheap gate checks the
document-anchor side.** `pin_extractor_truth` probes source extractors *"unconditionally, independent
of whether the document anchor matched"* and will report **15/15 green** even if the ADR line does
not match; `doc_truth` is the gate that would catch it and I-0 forbids running it locally. Probe it
with `doc_truth.documented_value(pin, text)` — a pure function, and the contract is **exactly one**
matching line. A mismatch takes C56 from FAIL to **SKIP** through R1.4/R1.6's non-maskable rule,
moving registry counts immediately before the regeneration.

### 3. Task 26.2 — reachable now, by LABEL

Route 1 landed. Add the **`regenerate-truth-docs`** label to PR #84, then remove it. The
`gh workflow run` instruction that used to sit in task 26.2 was **wrong** (HTTP 404, finding 23) and
has been corrected in `tasks.md`. Sequence it **after** the margin commit, per the operator's
"route 1 then 3": task 10.4's pin changes `doc_truth`'s claim set and can move C56, so an earlier
regeneration is stale within the hour.

### 4. Task 27.5 — still a CI read, still blocked

Obstruction 2 sits ahead of it. Until this leaf is `[x]`, **every `HANDOFF.md` must keep stating that
this spec's property surface is local evidence only.**

### DECISIONS 1 AND 2 ARE CLOSED. Do not re-litigate them.

- **Decision 1 → route 1 then 3**, taken by the operator, landed in `bbe4278`.
- **Decision 2 → adopt `test_cognition_phase`**, taken by the operator, landed in `bf8693f`.
- **The third item was a MEASUREMENT, not an adoption**, and it stays that way until someone decides
  otherwise. See finding 32.

---

## Session 3's findings

### CONFLICT L — this project's own checkpoint-A procedure was unexecutable

`SESSION_PROTOCOL.md`'s batch table row A had been updated to "reachable by labelling PR #84" when
finding 23 was resolved. **The procedure three sections below it was not**, so the binding working
agreement still instructed a command proven to return HTTP 404. Four defects in one section:

1. **The mechanism is a LABEL, not a dispatch** (finding 23, repaired in `e8e9528`).
2. **Step 0's `workflow_dispatch.inputs.job` selector already landed**, in `85774e1`. Following the
   instruction would re-author a committed change.
3. **Step 1 discharges task 6, which is already `[x]`.**
4. **It described ONE run where finding 16 proves TWO are required.**

Checkpoint B carried the same dispatch defect. All corrected in place, **with the correction stated
in the document rather than applied silently.** The general lesson: *a table and the procedure below
it can disagree, and the table is the one people update.*

### Finding 30 — `gate_surface` cannot parse a label guard, and that is honest rather than broken

The new row renders `CONDITIONAL | unparsable if: (unparsable at offset 126: "*.name, 'regenerate-")`.
It reads like a defect this change introduced. It is not: **`uplift.yml::twin-regret` carries the
identical rendering in the committed, C63-green surface.** `gate_surface`'s expression parser does
not understand the `labels.*.name` filter-object syntax, and `CONDITIONAL` is the **conservative**
classification for a guard it cannot decide — the job may or may not run, which is exactly true
(I-7). Now the case for two of two label-conditioned jobs in the tree. **Not repaired: the parser's
degradation is correct, and improving it is not this spec's remit.** Recorded so the next reader does
not chase it.

### Finding 31 — the test repair had a second symptom, and the obvious repair would have created a vacuous assertion

**The recorded diagnosis was verified before it was trusted, and it needed it:** `protocol.py` has
only **one** `produce(` call and it targets the phase topic. The other emitters are
`emit_agent_signals` and `emit_agent_metrics` in `orchestrator/consensus/firehose_signals.py`,
reached at `protocol.py:1021` and `:1024`.

**Second symptom.** Those two pass their payload **positionally** (`producer.produce(topic, item,
key=...)`) while `_emit_phase` passes it as **`value=`** — so `c.kwargs["value"]` over the unfiltered
call list raised `KeyError` as well. One defect, two symptoms, both repaired by the partition.

**And the tempting repair was a trap.** Filtering to the phase topic and asserting the rest is a
subset of the declared telemetry topics looks complete — but `set() <= anything` is **vacuously
true**, so the clause becomes an assertion that cannot fail the moment the telemetry side stops
firing. That is **finding 26's defect class, in a hole the repair itself opened.** Non-emptiness is
now asserted, which closes it and doubles as the mechanical re-proof that the shared-producer premise
holds in this run.

**Why it is a partition and not a filter.** The original assertion was protecting something real —
that nothing emits to an unexpected topic. A filter discards that protection. The partition keeps a
rogue topic a failure, and the permitted set is **derived** from `firehose_signals.METRICS_TOPIC` and
`SIGNAL_CHANNELS` rather than transcribed, so enabling either follow-up channel that module records
as pending does not break the test.

### Finding 32 — the ruff-scope gap is larger than recorded, and it is now a number

Session 2r recorded that `scripts/` and `tests/` are outside CI's ruff scope. Read from `ci.yml`, the
scope is exactly `packages/synapse_common/ agents/ orchestrator/`, and `[tool.ruff]` declares no
`include`/`exclude` — so the unlinted set also contains **`uplift/` and `digital_twin/`, this spec's
own production code**, plus `api/`, `data_fabric/`, `ml_pipelines/`, `packages/tests/` and root
`conftest.py`.

Measured in two ruff passes:

| tree | lint findings | files `ruff format` would rewrite |
|---|---|---|
| `tests/` | 255 | 118 |
| `scripts/` | 103 | 48 |
| `packages/tests/` | 57 | 21 |
| `uplift/` | 53 | 17 |
| `api/` | 24 | 8 |
| `data_fabric/` | 13 | 14 |
| `ml_pipelines/` | 13 | 7 |
| `digital_twin/` | 12 | 20 |
| `conftest.py` | 0 | 1 |
| **TOTAL** | **530** | **254** |

Top rules: `ANN001` 99, `I001` 95, `E501` 69, `F401` 34, `UP037` 28, `TC003` 25.

**The 254 is an UPPER BOUND and must not be reported as 254 real defects.** Session 2p proved 37 of
40 comparable Biome findings were `core.autocrlf` artifacts, and this session re-proved the mechanism
directly (finding 33). Separating real from artifact needs the `--write`-then-`git diff` comparison,
which modifies files and was not taken unasked. **The 530 are not line-ending sensitive and stand.**

**The decisive consequence, and it is why this stayed a measurement rather than a repair.** `Ruff
lint` is step **5** of `quality-gates` — *earlier* than the step 8 session 2r cleared — and both ruff
steps are **declared blocking anchors** in `blocking-steps.yaml`. Widening the scope would re-close
the gate at an earlier point than the one just opened, re-burying `uplift-verify` behind 530
findings, and would owe `gate_surface --write` for editing an anchor step's `run:`.

**And the two mitigations are mutually exclusive today.** CI does not lint these trees, and the
`.pre-commit-config.yaml` ruff hook that would (it carries no `files:` filter) is the one this file
forbids installing — because it also installs the mypy stubs that unmask seven pre-existing errors
under `uplift/`.

### Finding 33 — the line-ending trap, sixth session running, with a refinement

`git ls-files --eol` reported **`i/lf`** while the worktree was **140 CRLF / 51 LF**. **The index
column is normalised and must not be used to choose the target ending — count the worktree bytes.**
Normalising to the dominant CRLF left `git diff --stat` as pure content (`+46/-8`); forcing LF, which
`i/lf` invites, would have rewritten the whole file and buried the real change.

---

## What session 3 changed

### `bbe4278` — the regeneration becomes reachable by label, and fails closed

`.github/workflows/regenerate-truth-docs.yml` gained `pull_request: types: [labeled], branches:
[main]` and a per-job **allow-list** `if:` guard. `docs/state/GATE_SURFACE.md` regenerated in the
same commit (coupling 4).

**The guard is the load-bearing half, not the trigger.** The job carried no `if:` at all — correct
while `workflow_dispatch` was its only trigger. Adding `pull_request` without one would have run two
full Check_Registry executions on **every** label event on PR #84, including checkpoint A's
`measure-twin-regret` label: ~45 minutes for a label with nothing to do with regeneration. That is the
fail-OPEN shape session 2r-pre-c caught in `uplift.yml`.

**Verified by truth table over every event × input × label combination, for all three conditioned
jobs in the tree**, because reading the expression is what failed to catch three defects last time.
The property that matters is **non-interference**, and it is proven rather than asserted:

| trigger | `uplift-proof` | `twin-regret` | `regenerate` |
|---|---|---|---|
| `schedule` | runs | runs | — (no schedule trigger) |
| `workflow_dispatch` + `job=twin-regret` | no | runs | runs (declares no inputs) |
| label `measure-twin-regret` | no | **runs** | **no** |
| label `regenerate-truth-docs` | no | **no** | **runs** |
| unrelated label, or undeclared `push` | no | no | no |

The parsed `if:` carries **zero literal newlines** (the folded-scalar trap) and **no `!=`** (the
deny-list shape).

**A header claim the change would have falsified was corrected rather than left.** The file used to
say the job "produces no status check on any pull request". On a *labelled* event it does produce
one. What it still does not do is report on **every** pull request — and that, not the absence of a
check run, is why it owes no `required-checks.yaml` entry.

**Coupling 4 observed firing, with its shape predicted first.** `gate_surface --check` exit 1;
`--write` took the surface **542 → 549** rows. The +7 is one `pull_request` placeholder step row
expanding into the job's eight real steps, while the job row changed *status* without changing the
row count. `workflow_shape_truth` stayed **0** — correctly, since no step was added, renamed or
removed.

### `bf8693f` — `test_cognition_phase`'s precondition, corrected rather than weakened

**Ownership re-confirmed mechanically first**, not carried over: the file exists on `origin/main`
(`git cat-file -e` exit 0) and `git diff origin/main` shows only session 2r's type repairs, so the
failing assertion is byte-identical to `main`. **`git log -1` was not used** — it reports last touch,
not authorship, and it is what misled session 2r on this exact file.

The repair is a **precondition correction (R2.10)**: the subject moved when ADR-038 and ADR-053 began
sharing the producer; the standard did not. See finding 31 for the two symptoms and the vacuity trap.
`PHASE_TOPIC` is declared **once** in the test so the two tests asserting on it cannot drift; it was
**not** added to `protocol.py`, which states the literal inline — a production constant is not this
repair's remit.

---

## Honesty ledger — verified vs merely authored

### Executed and green, session 3

| What | Result |
|---|---|
| `gh` reads of every run on sha `fe8ddeb` | **8 workflows, all refused to start, `steps=0`** — the STEP 0 finding |
| `spec_ledger_census --files --next 30` | exit **0**; 140/61/2/77 **unchanged**; both barriers named and answered |
| Guard truth table, 3 conditioned jobs × events × inputs × labels | **non-interference proven**; 0 literal newlines; no deny-list `!=` |
| `gate_surface --check` → `--write` → `--check` | **1 → 0**, surface **542 → 549** rows, shape as predicted |
| `workflow_shape_truth --check` | **0** (379 steps, 11 blocking entries) — unmoved, correctly |
| `ruff check` / `ruff format --check` on the one changed Python file | **0 / 0** |
| `mypy --strict orchestrator/tests/test_cognition_phase.py` | **0**, 1 source file |
| `pytest orchestrator/tests/test_cognition_phase.py` | **6 passed** — green for the first time on this branch |
| `pytest tests/verify/test_regeneration_closure_parity.py` | **4 passed** |
| Six cheap gates | **0 / 0 / 0 / 2 / 1 / 0** |
| `pin_extractor_truth --check` | **0**, and **14 declared / 14 probed / 14 both-sides — not 15** |
| Line endings | `w/crlf` or `w/lf` per file, **none `w/mixed`** after repair |
| Bytes | every written file verified: **no BOM, no U+FFFD** |
| Process sweep | `python` **0**, `node` 1 (Kiro's own ACP server), `chrome` 11 (the operator's browser, started before this session's first command; no browser was launched here) |

**Budget, honestly counted.** **Three** bounded `pytest` invocations — the protocol's stated
per-session maximum — declared rather than left to be counted: one for wave 1, and two for wave 2
because the repair had to be verified after the non-vacuity assertion was added. **Zero** wide
`mypy --strict orchestrator/` passes of the four-pass budget; one single-file probe, which is not a
wide pass. **One cancelled run, swept explicitly:** a PowerShell `-f` format-string error
(`{1,>6}` is not a valid .NET alignment) ran into the 120s timeout; the `python` process count after
it was **0**, so nothing leaked.

### NOT executed. Must not be claimed as passing.

- **`uplift-verify`, and therefore Properties 38–60.** This spec's entire property surface has never
  run in CI. Session 3 did not change this.
- **`regenerate-truth-docs.yml` has never executed.** Task 26.1 stays `[~]`. Route 1 made it
  *reachable*, which is not the same as *run* — a workflow that has never executed is the I-7 shape.
- **`quality-gates` steps 18–23.** Skipped behind C56 on this branch and on `main`. Unknown, not
  green.
- **The `test_cognition_phase` repair, in CI.** 6 passed locally. Local green is not CI green, and
  obstruction 2 sits ahead of it.
- **`ledger_gen`, `readme_gen`, `verify_claims`, `doc_truth`** — not run locally in any form. I-0.
- **The document-anchor side of the parked derived-margin pin.** No cheap gate covers it.
- **The five slow-marked tests in `test_confidence_gate_universality_property.py`.** Deselected.
- **`vitest`. At all.**
- **`uplift/regret.py::_measure`'s wired interval path.** Discharges at checkpoint A.
- **Whether any of the 254 `ruff format` findings are real** versus line-ending artifacts.
- **`digital_twin/tests/test_env_response.py`** — module-skipped, `gymnasium` absent.
- **`tests/uplift/test_aggregation_integrity_property.py::test_aggregation_integrity_under_failures`**
  — pre-existing float fragility, diagnosed, not repaired.

### The lesson from this session

**A gate whose mechanism you unblock is not a gate you have run, and a repair that is locally green
is not a repair that has been judged.** Session 3 moved two obstructions and discharged nothing,
which is the honest outcome and is why no mark changed. The corollary is sharper: **the instruction
set itself decays.** Three of this session's findings are corrections to committed instructions —
task 26.2's dispatch command, `SESSION_PROTOCOL.md`'s entire checkpoint-A procedure, and a workflow
header claim that this session's own change falsified. **Read the procedure you are about to follow
against the tree, not against its own table of contents.**

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
| Dispatch mechanism (2r-pre-c) | **Checkpoint A runs by LABEL, not by dispatch, and `main` is not touched.** Both guards are **allow-lists**. |
| Conflict I (2r) | **CI step 8 excludes `orchestrator/tests`; the wide command is run by no workflow.** |
| `import-untyped` (2r) | **`ignore_missing_imports` for `yaml.*` and `psycopg2.*`**, chosen over installing stubs. |
| Scope (2r) | **The full wide 56 was cleared**, not only the 3 that gate step 8. |
| **Decision 1 (3)** | **ROUTE 1 THEN 3.** `regenerate-truth-docs.yml` gets the label trigger; the dispatch happens **after** the margin lands, so one regeneration suffices. Landed `bbe4278`. |
| **Decision 2 (3)** | **`test_cognition_phase` IS ADOPTED** — reversing 2r's refusal, on the operator's explicit word. Landed `bf8693f`. |
| **Ruff scope (3)** | **MEASURED, NOT ADOPTED.** 530 lint findings / 254 format findings across nine unlinted trees. Widening CI's scope is the operator's call and would re-red `quality-gates` at step 5. |
| **Conflict L (3)** | **`SESSION_PROTOCOL.md`'s checkpoint-A procedure was stale in four ways and is corrected in place**, with the correction stated in the document. |

---

## Environment notes and traps

- **NEW: `git ls-files --eol`'s index column does not describe the worktree.** It read `i/lf` on a
  file whose worktree was 140 CRLF / 51 LF. **Count the worktree bytes** before normalising; the
  index side is normalised by `.gitattributes` and will send you to the wrong ending, which turns a
  46-line change into a whole-file diff.
- **NEW: PowerShell's `-f` operator rejects `{1,>6}`.** `>` is not a .NET alignment character; the
  operator throws per-call and the surrounding loop keeps going, so the failure looks like a hang.
  Write anything with formatting or per-item aggregation as a temp `.py` and run that.
- **NEW: `gate_surface` renders a label guard as `CONDITIONAL | unparsable if:`.** Expected, honest,
  and already true of `uplift.yml::twin-regret` in the green surface. Not a defect (finding 30).
- **A `ruff format --check` diff whose two sides look identical is a LINE-ENDING diff.** Fired for
  the **sixth** session running. Normalise to the file's **dominant** ending with Python at
  `newline=''`.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental` after any
  config change.
- **`git log -1 -- <file>` is last-touch, not authorship.** If the file exists on `main` too, diff
  the line and, when it matters, execute `main`'s version from a scratch path.
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo**, and `Get-Content`
  *displays* em dashes as mojibake while the file is clean. **Verify bytes, never the console.**
- **PowerShell strips double quotes inside single-quoted `--jq`.** Capture `gh api` into a variable
  and use `ConvertFrom-Json`. `>` writes **UTF-16**; there are **no heredocs** — write commit
  messages to a temp file and use `git commit -F`.
- **`$LASTEXITCODE` is unreliable after a native command is piped through `Select-String`.** Re-run
  with `*> $null` to read it.
- **`git status` over-reports on this tree.** Trust `git diff`, and stage precisely.
- **`git add` refuses an ignored path SILENTLY.** `git check-ignore -v <paths>` first (exit 1 = not
  ignored).
- **Identify a CI run by `head_sha` and `head_commit.message`, NEVER by timestamp.**
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks seven pre-existing
  errors under `uplift/` that block commits to files which do not contain them.
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
`pnpm` anything. **`regenerate-truth-docs.yml` is the sanctioned route for the middle two, and as of
`bbe4278` it is reachable by label.**

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, **one bounded `pytest`
per wave**, `spec_ledger_census`, the **six** cheap gates, the `biome`/`tsc` binaries on changed
files, and **`gh` API reads — free, and the highest-yield evidence in this repo. Spend them first:
this session's entire STEP 0 verdict cost four of them.**

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
than the tautological PASS it replaces. **A number that cannot fail is not a number** — and session 3
found an *assertion* it was about to create in exactly that condition, in its own repair.
