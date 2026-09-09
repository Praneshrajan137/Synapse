# HANDOFF — decision-quality-proof

**State at end of session 4 (2026-09-09). Three commits pushed; the commit carrying this file is the
fourth.** Derive the counts, never read them:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 30
```

At the time of writing that reported **140 leaf tasks: 63 done, 2 authored-pending-discharge, 75
open** — 69 authorable and **6** CI-gated. Two leaves were discharged by CI this session (**26.2**,
**26.3**), which is the first time this spec has moved on a runner's own verdict since 27.1.

> **CI RUNS AGAIN. The repository was made public, which gives it unlimited standard-runner Actions
> minutes, and the account-level block is gone.** Verified empirically rather than from
> documentation: the push of `8da2c9d` produced runs in which `Security Scan`, `Terraform Validate`
> and `Policy Gate` **succeeded**, which is impossible under the block where all eight workflows
> died in 2–3 seconds with `steps=0`.
>
> **Two obstructions fell, two new ones were found, and `uplift-verify` still has not run.**
> C56 is PASS for the first time on this branch. Checkpoint A produced its first real measurement.
> And the measurement cannot be judged, because the instrument can currently return only one verdict
> and it would be about the wrong comparator (**conflict M**).
>
> The working agreement is `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md`.
> The prompt to paste in a new session is
> `.kiro/specs/decision-quality-proof/NEXT_SESSION_PROMPT.md`.

This file is **overwritten** at the end of each session, never appended to: it describes the tree as
it *is*, not as a diff against how it was.

**Secrets were checked when the repository went public, because public history is permanent.**
**Clean:** no bare credential file was ever added in any commit on any ref; `.env.cloud` is
gitignored at `.gitignore:64` and untracked; every tracked `.env` is an `.example` or `.template`.

---

## THE TWO THINGS THAT NOW BLOCK EVERYTHING

### 1. CONFLICT M — the regret instrument can only return `material`, and it would be wrong

**Checkpoint A's first measurement succeeded.** Run `34366766968`, sha `245d0dc`,
`uplift.yml::twin-regret` via the `measure-twin-regret` label. **200 of 200 replicates usable.**

| field | measured |
|---|---|
| `regret` | `8.937888952967558` |
| `comparator_headroom` | `8.937888952967558` |
| `interval_low` / `interval_high` | `8.916389405913677` / `8.958204644600675` |
| `mean_baseline_cost` / `mean_foresight_cost` | `11.835228527152536` / `2.897339574184977` |
| `margin_rule_derives` | `0.4` |
| `verdict` | `unavailable` — exactly as finding 16 predicted |
| `insensitive_kpis` | `["spoilage_rate", "delivery_latency"]` |

**Now trace run 2.** With the margin committed at the value its own rule derives,
`classify_regret` gets `8.9379 >= 0.40` true and `interval_low 8.9164 > 0.40` true, so it returns
**`material`** — and task 11 says **STOP, Finding 4 is falsified, re-cut R5.**

**Two reasons that verdict would be wrong. The second is structural.**

1. **The baseline arm is a NO-OP, not a base-stock `(s, S)` policy.** `uplift/foresight.py` pass one
   is `NoOpRecordingPolicy` — "Pass one: change nothing" — and the run reports
   `restock_threshold: 0.0`. The artifact says so itself: *"this is NOT yet the (s, S) regret R5.1
   asks for -- Par_Level_Reorder is owned by decision-integrity-uplift-proof and is a
   PRECONDITION."* In service-point equivalents `8.9379` is ≈ **112 points**, against an incumbent
   whose recorded shortfall against its own newsvendor target is ≈ **3.3**. The number describes a
   different subject.
2. **`regret` and `comparator_headroom` are the SAME EXPRESSION.**
   `RegretObjective.regret(policy, reference)` is `aggregate(policy) - aggregate(reference)`, and
   `_measure`'s `headroom` is `mean_baseline - mean_foresight` — identical, and the run confirms it
   to every digit. So `policy.py`'s `must_be_below_measured_headroom` admits exactly the margins
   that are **below the regret they will be compared against**. Every margin inside D2.5's own
   bracket (`0.264`–`0.709` objective units) forces `material` **by construction**.

**The guard was written to stop a margin being unfalsifiable in one direction and is blind to the
other**, because it checks the margin against the very quantity being judged rather than against an
independent bound. **A verdict that cannot be anything else is not a verdict** — the mirror of this
project's own "a number that cannot fail is not a number".

**Two repairs, both the operator's, both costed in task 11. Neither taken.**

- **Land the real comparator.** `Par_Level_Reorder` is the `(s, S)` arm R5.1 names, a declared
  precondition owned by `.kiro/specs/decision-integrity-uplift-proof/`. With it, `regret` and
  `comparator_headroom` stop being the same expression, the guard regains discriminating power, and
  the verdict becomes a claim about the right subject. **This is the repair the design implies.**
- **Or give the guard an independent bound**, so a margin is checked against a contrast other than
  the one it judges. Cheaper, and it changes a committed pre-registered rule — which D2.5 requires
  to land *before* the run judged against it.

**`SESSION_PROTOCOL.md`'s checkpoint-A steps 2, 3 and 4 are marked SUSPENDED in place.** Do not
amend D2.5's derived literal, do not commit `materiality_margin.value`, do not graduate the parked
pin, do not run the second label. **The headroom also moved** — D2.5 records `11.79 - 2.93 = 8.86`,
the measurement is `8.937888952967558` — so `bracketing.upper` is owed a correction whenever the
amendment does land.

### 2. OBSTRUCTION 2.5 — step 18 cannot pass on a hosted runner, and it was never in the chain

`ci.yml::quality-gates` at `2be5a96`: steps 1–17 **success**, failure at **step 18 `Golden-trace
replay metrics (R7.6/R7.7 — KV-cache + tier routing)`**, steps 19–23 skipped.

```
[OK] tier_routing_accuracy: measured 1.0000 >= floor 0.8000 (200/200 traces)
[??] kv_cache_hit_rate: measured UNAVAILABLE, floor 0.7000 -- synapse_ollama_cache_hit_rate
     has no samples -- the replay took no cache observation (Ollama offline)
[??] replay-metrics: UNAVAILABLE - at least one floor has no measurement behind it.
     Absence of proof is not a pass (I-7).
```

**The gate is behaving exactly as this project demands.** It refuses to call an unmeasured floor a
pass. But `kv_cache_hit_rate` needs an Ollama-backed cache observation and a hosted runner has none;
standing one up is a category-1 service workload. **So the step cannot pass in CI as written.**

**It is `main`'s, and it had never executed anywhere** — it sat behind step 5, then step 8, then
step 17 for this branch's entire life, and `main`'s own runs fail at step 17. Its own comment
records the motive: *"The two numbers CLAUDE.md has stated since Sprint 9 with NO gate anywhere."*
**The gate was written to close a documentation claim, and the first execution proved the claim is
not measurable in CI.** That is a finding about the claim, not about the gate.

**Three dispositions, all the operator's.** (a) Re-point `uplift-verify`'s `needs:` so it does not
transit an unmeasurable step. (b) **Split step 18** so `tier_routing_accuracy` — which measures
cleanly at `1.0000` — gates, while `kv_cache_hit_rate` is declared unmeasurable-in-CI with its
recorded reason, which is the `DEGRADED`/`SKIP` shape I-7 already blesses and the same shape as
C74's honest SKIP. (c) Provide a cache observation in CI. **(b) is the only one consistent with
precedent that does not weaken a floor.**

**Do not clear it by lowering `kv_cache_hit_rate` or by making step 18 `continue-on-error`** — the
first is assertion weakening (R2.10); the second re-creates the swallowed-exit-status defect this
very session repaired two steps away.

---

## The chain to `uplift-verify`, measured rather than predicted

| # | Obstruction | State |
|---|---|---|
| 0 | the runner itself — account billing | **CLEARED** — repository made public |
| 1 | step 8 `mypy --strict orchestrator/ --exclude orchestrator/tests` | **CLEARED** (2r); re-confirmed `success` at `2be5a96` |
| 2 | step 17 **C56** narrative-truth | **CLEARED** (26.2 / 26.3) — first PASS on this branch |
| **2.5** | **step 18 golden-trace replay** | **RED, STRUCTURAL, never named before** |
| 3 | step 19 unit tests → `test_cognition_phase` | **still unknown** — skipped behind 18. The repair is on disk (`bf8693f`) and remains unjudged |
| 4 | steps 20–22 coverage floors, spec coverage, contract tests | **still unknown** |

**Properties 38–60 have still never executed in CI**, and every `HANDOFF.md` must keep saying so
until task 27.5 is `[x]`.

**Session 2r's lesson has now fired three times: clearing a gate reveals what it was shielding, and
the depth is unknown until each layer clears.** Session 4 cleared two layers and found two more —
one of them structural and one of them absent from every recorded chain. **No single clearance
licenses a claim about the job at the end.**

---

## What else is owed

### A second regeneration, owed by the generator order itself

**The committed repair order is backwards for exactly the case task 26 exists to repair, and the
first real execution proved it.** `ledger_gen` projects a **top-level** registry execution in which
C56 **is** evaluated, and C56 reads the README headline that `readme_gen` rewrites **afterwards**.
True dependency: `readme_gen` → `README.md` → C56 → `ledger_gen`. The committed order inverts it, so
run `34372152090` generated `CURRENT.md` against the pre-repair README and recorded `C56 | FAIL` —
which was false the moment step 7 finished.

Measured, not inferred: the artifact's verdict line reads `C44=FAIL, C56=FAIL, C69=FAIL`, while
`truth-gates.yml` on the very next commit reads `C44=FAIL, C69=FAIL`.

**The README headline is unaffected** — it projects the *nested* execution where C56 self-excludes
and counts as a SKIP, which is the recursion guard working. Only the top-level ledger is exposed.

**So `CURRENT.md`'s `C56` row and registry-verdict line are stale, and reach their fixed point only
on a dispatch made after `2be5a96`.** `ledger_gen --check` will be red when it next executes. **The
durable repair is to swap the two `--write` steps**; that edits the declared repair order of the
enforcement spine and is the operator's.

### The twin-regret artifact is not canonical JSON

Run `34366766968` uploaded **215,293,577 bytes**. The twin's `structlog` writes to stdout, so `tee`
captured a debug flood with the report on the final line. `json.load` raises
`JSONDecodeError: Extra data: line 1 column 5`, while `blocking-steps.yaml` declares this step
`emits: "artifacts/uplift/twin-regret.json (canonical JSON, --json)"` — **so that declaration is
false as written.** The figures above were recovered from the last line.

**Tasks 17.x, 22.3 and 25 read uplift artifacts with a JSON parser**, and 90-day retention on
215 MB per run is its own cost. Repair is a choice between suppressing twin logging in the
measurement path (`structlog.configure(wrapper_class=make_filtering_bound_logger(logging.ERROR))`,
the documented idiom) and writing the report to the file directly rather than through stdout — the
second loses the log visibility `pipefail` was just made safe for. Not taken.

### `main`'s registry debt, newly visible

`truth-gates.yml::truth-gates` fails at step 5 on **C44** and **C69**, so steps 6–12 including
`ledger_gen --check` are skipped behind it. Neither is this spec's.

- **C69** — `core-purpose-uplift` task 9's placeholder checkpoint registry, the same record
  `task_claim_truth` has reported for four sessions.
- **C44** — three liveness violations that **the committed ledger had been masking**: two dead
  modules (`data_fabric/ingest/__init__.py`, `data_fabric/ingest/m5.py`) against a named baseline of
  `0`, and `synapse_common.contracts.validate_audit_insertion`, which encodes a `[deal.post]`
  invariant and is invoked only from `packages/tests/test_contracts.py`.

---

## Session 4's findings

### Finding 34 — the label mechanism was committed without its labels

`uplift.yml`'s `measure-twin-regret` and `regenerate-truth-docs.yml`'s `regenerate-truth-docs` were
designed, verified by truth table, and committed — and **neither label existed on the repository.**
`gh pr edit --add-label` fails on a label that does not exist, so checkpoint A would still have been
unrunnable after billing cleared. Created with descriptions naming the job each one runs. **A
mechanism is not reachable until the thing that triggers it exists.**

### Finding 35 — a declared-blocking step reported success while measuring nothing

Run `34364879758`. Under `bash -e` a pipeline's status is its **last** command's, so
`python -m uplift.regret ... | tee <file>` returns `tee`'s success even when the Python crashed. The
measurement died at import, `tee` wrote a **zero-byte** artifact, and the step reported **success**
while `blocking-steps.yaml` declares it `role: producer` emitting canonical JSON.

**The step's own comment enumerated three discarding constructs — `continue-on-error`, `|| true`,
`|| echo` — and missed the one it used.**

**The job was red only because the DISCLOSURE step below it, explicitly "not a gate", failed on the
same root cause. Without that step this job would have been GREEN with no measurement in it.**
Repaired with `set -o pipefail` in `245d0dc`; `| tee` kept, because the JSON in the log is what lets
a reader check the artifact against the run, and with `pipefail` that visibility is free.

**`scripts/audit/workflow_shape_truth.py` cannot catch this.** Its `DISCARDING_CONSTRUCTS` is four
literals — `|| true`, `|| echo`, `; exit 0`, bare `exit 0` — and an unguarded pipeline is none of
them, so a declared-blocking step can discard its exit status with **C64 reporting pass**. Its own
docstring is *"A gate whose exit status is discarded is not a gate."* `| tee` occurs **exactly
once** in the workflow tree, so the exposure is closed; **extending the gate is a registered-check
change and is the operator's.**

### Finding 36 — a closure proof that started at the wrong entry point

`scipy` was missing from `twin-regret`'s install closure. The step's comment claimed a static walk
of the 9 first-party modules reachable from `uplift.regret` found `pydantic-settings` as "the ONLY
gap". **The walk followed imports *from* `uplift.regret`, but `python -m` executes the package
initialiser first**, and `uplift/__init__.py` → `uplift.consensus_arm` → `uplift.harness` →
`uplift.contract` → `from scipy import stats` is nowhere in that graph.

**Correct about the module graph, wrong about the entry point's import closure. A closure proof must
start at the command the job actually runs.** This is also HANDOFF defect 14 recurring: that defect
named this exact import, and the repair taken then routed `uplift/interval.py` around
`load_contract` instead of widening the closure, leaving the import on the initialisation path.

Fixed narrowly, this job only, per defect 22's precedent. **`scipy` is pinned in no requirements
file in the repository** (`policy.yml` installs it bare), so `>=1.11,<2.0` is a **choice**, flagged
as one.

### Finding 37 — a local generation was recording an environment error as a finding

The committed `CURRENT.md` gave C44's detail as
`check raised FileNotFoundError: [WinError 3] ... 'C:\Users\Pranesh\Projects\synapse\frontend\node_modules\.pnpm\...'`
— a Windows dev-box path error standing in for a check's finding, **hiding three real liveness
violations behind it.** Session 4's run is the **first projection of that document ever taken on a
Linux runner.**

**This is the strongest available justification for I-0's never-run-locally rule on the generators,
and for task 26 choosing a CI job over a local `--write`: a document generated on the wrong machine
does not merely go stale — it can record an environment error as a finding and hide the real ones.**

### Finding 38 — non-interference, proven in a live run rather than by truth table

Adding `regenerate-truth-docs` also fires `uplift.yml`, which triggers on the same `labeled` event.
Run `34372152145`: **both** its jobs `skipped`, `steps=0`, zero runner minutes — `twin-regret`
because the label does not match, `uplift-proof` because `pull_request` is deliberately absent from
its allow-list. The fail-closed guards hold in both directions, and the ~350-minute job stayed
asleep. Session 3's truth table predicted exactly this; the live run confirms it.

---

## What session 4 changed

| Commit | Subject |
|---|---|
| `245d0dc` | `twin-regret` reported success while measuring nothing — `set -o pipefail` + `scipy` |
| `0c0e971` | conflict M: the instrument can only return `material`, on the wrong comparator |
| `2be5a96` | the regenerated ledger and README headline (task 26.2's artifact, reviewed) |
| *(fourth)* | this file, the ledger row, the prompt, and 26.2 / 26.3 ticked |

**What was earned.** **26.2** and **26.3** are `[x]`, both on CI's own verdict. C56 PASSES for the
first time on this branch. `regenerate-truth-docs.yml` executed for the first time ever, all nine
steps green including its `gate_surface --check` hard gate. Census `140/61/2/77` → **`140/63/2/75`**,
CI-gated `8` → `6`.

**What was prevented.** Committing `0.40` and reading the resulting `material` as the end of this
project. That was the next mechanical step in the standing work order.

**What is blocked, and it is the operator's.** Conflict M's two repairs; obstruction 2.5's three
dispositions; the second regeneration; the artifact's JSON shape.

---

## Honesty ledger — verified vs merely authored

### Executed and green, session 4

| What | Result |
|---|---|
| Repository visibility | `public`, `private=False` — unlimited standard-runner minutes, and runs start |
| Credential audit of full history | **clean** — no bare credential file ever added on any ref |
| `uplift.yml::twin-regret`, run `34366766968` | **success**, 200/200 replicates, first real measurement this spec has produced |
| `regenerate-truth-docs.yml::regenerate`, run `34372152090` | **success**, all 9 steps, **first execution ever** |
| Artifact `GATE_SURFACE.md` vs committed | **byte-identical** — independent confirmation C63's PASS was real |
| Regenerated diff vs the job's own `--stat` | **exact match**, 16 insertions / 13 deletions |
| `ci.yml::quality-gates` step 17 (**C56**) | **success** — first time on this branch |
| Registry verdict line, `truth-gates` step 5 | `FAIL - 2 check(s): C44=FAIL, C69=FAIL` — **C56 absent** |
| Falsification sweep | `16 of 16 operators probed`, `7 falsified`, `0 unproven`, **no `indeterminate`**; 1 defect = `C28/zero-a-floor`, task 6's accepted survivor → **probeable set back to 8** |
| `uplift.yml` on an unrelated label, run `34372152145` | **both jobs skipped**, `steps=0` — fail-closed guards proven live |
| Six cheap gates | **0 / 0 / 0 / 2 / 1 / 0** |
| `spec_ledger_census --check` | exit **0**; `61/2/77` → **`63/2/75`**, CI-gated 8 → 6 |
| Line endings / bytes | every written file uniform, **no `w/mixed`, no BOM, no U+FFFD** |
| Process sweep | see below |

**Budget.** **Zero** local `pytest` invocations and **zero** wide `mypy` passes — this session's
verification was almost entirely free `gh` reads, which is what I-0 recommends and what made a
session this productive affordable. Two cancelled PowerShell commands (a `-f` format error and a
slow recursive walk) were both swept: `python` count **0** after each.

### NOT executed. Must not be claimed as passing.

- **`uplift-verify`, and therefore Properties 38–60.** Still skipped, now behind step 18. **This
  spec's entire property surface remains local evidence only.**
- **`quality-gates` steps 19–23.** Skipped behind step 18. Unknown, not green.
- **The `test_cognition_phase` repair, in CI.** 6 passed locally in session 3; step 19 has not run.
- **`ledger_gen --check` / `readme_gen --check`.** Skipped behind `truth-gates` step 5. Not run
  locally in any form (I-0). `ledger_gen --check` is **expected red** — see the second regeneration.
- **Task 11's verdict.** The measurement ran; what it measured is not what task 11 asks (conflict M).
- **The document-anchor side of the parked derived-margin pin.** No cheap gate covers it.
- **Whether any of the 254 `ruff format` findings in CI's unlinted trees are real** vs line-ending
  artifacts. The 530 lint findings stand.
- **`vitest`. At all.** **The five slow-marked `ConsensusProtocol` properties.** Deselected.

### The lesson from this session

**Every one of the four defects that mattered was invisible to reading and appeared the instant
something actually ran.** A closure proof that walked the wrong graph, a step that swallowed its
subject's exit status, a generator order that produced a document stale on arrival, and a committed
ledger that had recorded a Windows path error as a check's finding. Three sessions of careful reading
had passed over all four.

**The corollary is not "read less" — it is that a gate which has never executed is not evidence, and
the cheapest way to find out what a job does is to run it once.** `gh` reads are free under I-0;
this session spent about twenty of them and moved two leaves that four sessions of authoring could
not.

---

## Decisions taken — surfaced, then decided. Do not re-litigate.

| # | Decision |
|---|---|
| Conflict A | Twin policy file → `digital_twin/simulation/policy.yaml` (design E2c.2) |
| Conflict B | Licence artifact → `infrastructure/data/dataset-licences.yaml` (design E4a.1) |
| Conflict C | Property 47/48 attribution — follow the property index |
| Conflict D | **C75 is the highest registered gate id; next free is C76.** |
| M5 licence | Fields land **explicitly null** with a `confirmation.procedure` block; the gate reports SKIP. **Never invent a `licence_id`.** |
| Ratchets | An objective **weight** has no monotone better-direction, so it gets no ratchet. |
| Checkpoint order | Tasks 11 and 14 fire **before** the work they gate. |
| Margin derivation | The *rule* is pre-registered and **enforced by the reader**; the *value* is measured. Ratchet `down`. |
| Census | `spec_ledger_census` is local hygiene, **not** a registered check. |
| Conflict E (2p) | **`material` requires an interval excluding the margin, stricter than R5.3.** |
| Interval estimator (2p) | One estimator, `uplift/interval.py`. |
| `gate_surface` (2p) | The **sixth** cheap gate. `ledger_gen` went onto the never-run list. |
| Task 6 (2q) | **Survivor list accepted; C28's repair deferred to its owner.** E1 closed. |
| Conflict F (2q) | **The `confidence_threshold` repair is at the declaration, never at the call sites.** |
| Conflict G (2q) | **A dispatch-only — or label-conditioned — job owes no `required-checks.yaml` entry.** |
| Regeneration (2q) | **A CI job that uploads an artifact**, not a local `--write`, not an auto-commit. |
| Conflict H (2r-pre) | **The derived-margin pin is PARKED in `pending_pins:`.** `required: false` rejected. |
| Dispatch mechanism (2r-pre-c) | **Checkpoint A runs by LABEL. `main` is not touched.** Guards are allow-lists. |
| Conflict I (2r) | **CI step 8 excludes `orchestrator/tests`; the wide command is run by no workflow.** |
| Scope (2r) | The full wide 56 mypy errors were cleared, not only the 3 that gated step 8. |
| Decision 1 (3) | **Route 1 then 3.** Landed `bbe4278`. **Its "then 3" premise LAPSED in session 4** — conflict M means no imminent pin, so the regeneration was run immediately. Surfaced, not silently re-ordered. |
| Decision 2 (3) | **`test_cognition_phase` IS adopted**, reversing 2r's refusal. Landed `bf8693f`. |
| Ruff scope (3) | **Measured, not adopted.** 530 lint / 254 format findings across nine unlinted trees. |
| Conflict L (3) | `SESSION_PROTOCOL.md`'s checkpoint-A procedure was stale in four ways; corrected in place with the correction stated. |
| **Conflict M (4)** | **The margin is NOT committed.** Any value in D2.5's bracket forces `material` on a no-op comparator. Checkpoint A steps 2–4 SUSPENDED. Two repairs costed; both the operator's. |
| **Obstruction 2.5 (4)** | **Step 18 is structurally unmeasurable in CI.** Three dispositions costed; splitting the step is the only one consistent with precedent. **Not** cleared by lowering a floor or by `continue-on-error`. |
| **Repair order (4)** | **`ledger_gen` must run AFTER `readme_gen`.** The committed order is inverted; a second regeneration is owed. Swapping the steps edits the enforcement spine and is the operator's. |
| **`scipy` bound (4)** | `>=1.11,<2.0`, added to `twin-regret` only. A **choice**, flagged — `scipy` is pinned nowhere in the repo. |

---

## Environment notes and traps

- **NEW: an unguarded shell pipeline discards its subject's exit status, and `workflow_shape_truth`
  cannot see it.** `cmd | tee f` under `bash -e` reports `tee`'s status. Use `set -o pipefail` in any
  `run:` block that pipes a gate or a measurement.
- **NEW: a closure proof must start at the command the job runs**, not at the module you think it
  imports. `python -m pkg.mod` executes `pkg/__init__.py` first.
- **NEW: `gh label create` prints nothing on success**, and a `gh ... --json x | ConvertFrom-Json |
  Where-Object` filter silently yields nothing on PowerShell 5.1 because `ConvertFrom-Json` hands
  back the array unenumerated. Verify with `gh label list` directly. The same trap makes
  `gh run list --json` need a `foreach`, not a pipeline.
- **NEW: PowerShell's `-f` operator rejects `{1,>6}`** — `>` is not a .NET alignment character. It
  throws per call while the loop continues, so it presents as a hang.
- **NEW: a recursive `Get-ChildItem` over this tree can exceed a 120-second command timeout.** Use
  the search tooling or a temp `.py`, and **sweep for orphaned processes after any cancelled run.**
- **`git ls-files --eol`'s `i/` column does not describe the worktree.** It read `i/lf` on a file
  whose worktree was 140 CRLF / 51 LF. **Count the worktree bytes** before normalising.
- **A `ruff format --check` diff whose two sides look identical is a LINE-ENDING diff.** Six sessions
  running. Normalise to the file's **dominant** ending with Python at `newline=''`.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental`.
- **`git log -1 -- <file>` is last-touch, not authorship.** Prefer `git cat-file -e origin/main:<f>`
  then `git diff origin/main -- <f>`, and execute `main`'s version when it matters.
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo**, and `Get-Content`
  *displays* em dashes as mojibake while the file is clean. **Verify bytes, never the console.**
  `Copy-Item` is a byte copy and is safe for installing a generated artifact.
- **`git push` writes progress to stderr**, so PowerShell reports `NativeCommandError` and a
  non-zero `$LASTEXITCODE` on a **successful** push. Read the `old..new ref` line.
- **`>` writes UTF-16; there are no heredocs** — `git commit -F` a temp file.
- **`$LASTEXITCODE` is unreliable after a pipe through `Select-String`.** Re-run with `*> $null`.
- **`git status` over-reports.** Trust `git diff`, stage precisely, `git check-ignore -v` first.
- **Identify a CI run by `head_sha`, NEVER by timestamp.** And **check the run for the sha
  `git rev-parse` gives you**, not the one a document names.
- **Do not run `pre-commit install`** — it installs `types-PyYAML` and unmasks seven pre-existing
  errors under `uplift/`. Note the consequence: its ruff hook is also the only thing that would lint
  the trees CI never reads, so **the two mitigations are mutually exclusive.**
- Python 3.14.0, mypy 1.19.1 locally, pytest 8.4.2, hypothesis 6.151.11. `gymnasium` absent.
  `gh` 2.82.0, authenticated.

---

## I-0 — the rule most likely to burn the machine

**Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
`mutmut`); any `MIN_SCENARIOS`-scale or training workload.

**Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
`pnpm` anything. **`regenerate-truth-docs.yml` is the sanctioned route for the middle two, it is
reachable by the `regenerate-truth-docs` label, and it has now been proven to work.**

**Cheap and encouraged:** file reads, `grep`, `ruff`/`mypy` on changed files, one bounded `pytest`
per wave, `spec_ledger_census`, the six cheap gates, and **`gh` API reads — free, and the
highest-yield evidence in this repo. Session 4 spent about twenty and discharged two leaves.**

**Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
unlimited. **Sub-agents that execute code: exactly ONE at a time.**

**Process sweep at close:** `python` **0**, `node` **1** (Kiro's own ACP server), `chrome` the
operator's own browser started before this session's first command. Two `python` processes seen
mid-session belonged to `dataforge-automation`'s Snowflake CLI, from a different virtualenv — not
this session's, and not killed.

---

## Two decision points can end this spec early, on purpose

**Checkpoint A, task 11** — if measured `(s, S)` regret is at or above the R5.2 margin **with its
interval excluding it**, Finding 4 is falsified. **Session 4 measured a regret that would trigger
this and proved the trigger would be about the wrong comparator. That is conflict M, and it is why
the checkpoint is suspended rather than concluded.**

**Checkpoint B, task 14** — if **any** single-objective policy is Pareto-optimal under
interval-aware dominance, consensus is provably unnecessary and the experiment must NOT be run.

### The pre-commitment, binding before the number is known

If the measured uplift is null or negative, **it is reported as null or negative.** The floor stays
at `0.0`, no headline is published as a gain, and the result is written up as a finding — not
reframed, not re-run at a different replicate count until it moves. **A number that cannot fail is
not a number, and a verdict that cannot be anything else is not a verdict** — session 4 found the
second of those in the instrument that decides this spec's central question.
