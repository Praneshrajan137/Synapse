# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **10** (2026-09-16 to 2026-09-17).

**This prompt states no HEAD, deliberately.** Conflicts J and K were the same defect three sessions
running: the prompt is written *before* the commit that carries it, so any sha it names is stale by
construction. STEP 0b derives it instead.

**And this prompt carries no transcribed count that a gate can derive.** Conflict P was exactly that
defect — a stop condition asserting `pin_extractor_truth` would report `16` when three parked rows
made it `17`, which would have halted a correct session and looked like a pin defect. Where a number
appears below, the command that derives it appears beside it.

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`.

**Your session cap is FORTY leaf tasks, in waves of about ten. It is a ceiling and it is expected
never to bind.** What stops you is a barrier or a phase boundary.

### STEP 0 — THE HARD GATE HAS FIRED. BOTH HALVES BIND, AND THEY COME FIRST

**Everything E3 does is denominated on these two sentences. Read them before anything else.**

> **1. E3's floor and task 25's published claim may NOT be denominated against the incumbent arm.**
> The honest baseline is the **tuned control at `s=20, S=30`**. **Tasks 17.2, 17.5 and 25 may not be
> authored against the incumbent** — a **recorded prohibition, not a preference**.
>
> **2. Structures 1 and 3 are REINSTATED** — tasks **12.1, 12.2, 13.1, 13.2**. Structure 3 is the
> decisive one, because it is the only one that introduces a replenishment **DELAY**, and delay is
> what makes knowing the future worth anything. **Structures 2, 4 and 5 stay deferred**, and
> **12.3 / 13.3 stay forbidden.**

**Why, with the reasoning where it belongs — ADR-055 `D2.7`, finding 63:** the judged regret
decomposes into **85.6% baseline mis-tuning and 14.4% information ceiling**, **neither addend is
material on its own**, and the `material` verdict was produced only by their **SUM**. **Read D2.7;
do not re-derive it, and do not restate it in a third document.** `D2.6` (finding 61) is the
diagnosis that led to it.

**Arm E is AUTHORED AND MEASURED. Do not build it.** Run `35125443185`, `status: measured`, 200/200
usable, `decomposition_residual` exactly `0.0`, all five pre-registered predictions confirmed. Task
11 is decided; option (b) landed in `c746463`; **do not re-open the three options.**

**And the substantive result, which is not what the mechanical test said:** **Finding 4 is
substantively TRUE, and R5.3's mechanical test could not see it.** A gate that reads a sum cannot
report which addend carried it.

### STEP 0a — THE METRIC, AND THE OBLIGATION SESSION 10 ADDED TO IT

**Read these four first; they are `inclusion: always` and they govern how you work:**
`.kiro/steering/local-compute-budget.md` (I-0), `.kiro/steering/execution-routing.md` (where a
workload runs), `.kiro/steering/throughput-with-integrity.md` (**the metric and G1–G7**), and
`.kiro/steering/standard-of-work.md` (**what "done well" means, as tests rather than adjectives**).

**The metric: leaves DISCHARGED. A `[~]` counts ZERO. Target: >= 11** (G6).

**Session 10 discharged 25 — twenty of them by RECONCILIATION rather than authoring.**
Session 9 landed five feature commits and recorded one ledger entry, leaving twenty leaves complete
on disk and marked `[ ]`. **So the standing obligation is now mechanical: reconcile the ledger
against disk BEFORE deriving a batch**, because `--next 40` will offer you work that is already done
and the census cannot tell you which. Session 10's `--files` run emitted about **110** informational
`prior-art` lines with the twenty genuine candidate discharges buried inside them; **the severity
split that would separate them is owed work, not a done thing.**

**Authoring without recording scores zero and is indistinguishable from not authoring.** That is the
lesson of session 9 and it is the one you are most likely to repeat.

### STEP 0b — DERIVE THE STATE. Never trust this document for it.

```powershell
git rev-parse --short HEAD
git rev-list --count origin/main..HEAD
gh run list --branch feat/decision-quality-proof --limit 10 --json databaseId,headSha,workflowName,conclusion
```

Then read **both** workflows' step lists for the newest sha — not the run's colour, the step list:

```powershell
$j = gh api "repos/:owner/:repo/actions/runs/<id>/jobs" --paginate | ConvertFrom-Json
foreach ($job in $j.jobs) { "{0} | {1} | steps={2}" -f $job.name, $job.conclusion, $job.steps.Count }
foreach ($job in $j.jobs) { foreach ($s in $job.steps) { "{0,3} {1,-12} {2}" -f $s.number, $s.conclusion, $s.name } }
```

**Use a `foreach`, not a pipeline: PowerShell 5.1's `ConvertFrom-Json` hands back the array
unenumerated and a piped `ForEach-Object` receives it as ONE object.**

**Then read the LOG, not only the step list**, and read the OTHER workflows for the same sha.

```powershell
$log = gh api "repos/:owner/:repo/actions/jobs/<jobid>/logs" 2>$null
($log | Select-String -Pattern "FAILED tests|Falsifying example|passed|registry-gate|Summary:").Line
```

**What to read, in priority order. Two of these were verdicts session 10 could not have and now has;
three are still open, and item 1 is the one that can regress.**

1. **Is `quality-gates` green at the NEWEST sha?** It reached **`success` at 23 of 23 at
   `fa42263`** — the regression is repaired and **confirmed** — but **at the newest sha it was
   `cancelled`, superseded, so that verdict is not claimed and you must read it.** The cause was one
   file's formatting gating **17** steps, the **third time** one formatting or lint finding has gated
   a whole job on this branch, and `quality-gates` is a `required:` check, so a regression here is
   the most important thing that can happen.
2. **Finding 62 is CLEARED and CONFIRMED.** Aggregator **step 5 green**, reporting
   `shards selected 170/150/349/264 = 933; unsharded selection = 933`. The lesson is what you carry
   forward, not the repair: the proof compared against a frozen literal `874`, went red at 933 with
   **nothing dropped**, and **an equality against a constant still passes when *n* tests are dropped
   and *n* added.** **Any test you add lands in a shard — check that the partition still proves
   itself exhaustive and disjoint IN-RUN** (G5).
3. **Is finding 57 still the ONLY `uplift-verify` failure?** It is now the **sole cause of the
   aggregate red** — `codecarbon/data/hardware/cpu_power.csv`, another owner's guard, unrepaired,
   and the repair is a judgement (see STEP 3D). **Confirm it is still the failure before acting**;
   assertion N+1 may be hiding N+2.
4. **Did `Vitest` run?** `SYNAPSE Frontend CI` failed at step 6 `Biome lint`, so **step 8 `Vitest
   unit + property tests` was SKIPPED — which is the only reason 20.7 and 20.8 are `[~]` rather than
   `[x]`.** They graduate on that step's own verdict and on nothing else.
5. **`Truth Gates`, `Integration` and `Mutation` are all red and were NOT investigated.** Session 10
   says so rather than implying coverage. Reading one of them is a real contribution; adopting it is
   an operator decision.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/steering/execution-routing.md` — **where** a workload runs, by table not by judgement.
3. `.kiro/steering/throughput-with-integrity.md` — **the metric** and guardrails **G1–G7**.
4. `.kiro/steering/standard-of-work.md` — the reviewer bar, the three questions,
   intent-before-implementation, and the methodology at its **measured** level (spec-driven PARTIAL,
   TDD PARTIAL, BDD ABSENT, DDD PARTIAL, outcome verification PRESENT). **Read it before claiming a
   practice or a standard.**
5. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the ceiling, wave discipline, the
   **barrier stop**, the three marks, the four checkpoints, the batch table, the six cheap gates,
   the progress ledger. **Read rows `9` and `10` in full: row 9 is a reconstruction from disk, not a
   session's own report.**
6. `HANDOFF.md` (repo root) — current state, pointers, and **what is verified versus merely
   authored**. Read its honesty ledger before believing any colour.
7. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
   **Its I-1 sentence is load-bearing and was misread for two sessions: the paid-client list is
   CLOSED at four names.**
8. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
9. `.cursorrules` + `docs/cursor/*.md`.
10. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.7 is finding 63 and it is the session's
    starting point**; D2.6 is the diagnosis behind it, D2.5–D2.5.3 its history. **D6** declares both
    R6.15 numbers, which is why 16.3 is done. **Eight of the eighteen pins anchor to this
    document** — probe every one of them, on both sides, if you amend it.
11. `docs/adr/ADR-056` and **ADR-033** — ADR-056's supersession of ADR-033 is the open obligation
    behind the deferred task 23. **OQ-4 is recorded RESOLVED (Rekor) in `requirements.md`**; do not
    cite OQ-4 as the gap.
12. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
    and your worklist**. **`requirements.md` and task 14's body carry conflict R.**

**Two invariant numberings disagree.** `references/14_invariants.md` and `.cursorrules` differ on
I-6, I-8 and I-10. Authority 5 outranks authority 6. The invariants this work cites — I-1, I-4,
I-5, I-7 — agree in both.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict
rather than resolving it silently.** Eighteen have been surfaced (A–R). **Conflict R is the newest:
R5.28 is unsatisfiable a second time, and R5.29 would then cancel E3 on a theorem.** Expect more.

### STEP 2 — reconcile, then derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

**THE BATCH HAS CHANGED, because the reinstatement moves it. The two twin-physics pairs come FIRST,
because everything downstream is denominated on them:**

> **`12.1`, `12.2`** (non-stationary demand), then **`13.1`, `13.2`** (correlated lead times, and the
> **delay** that makes knowing the future worth anything), then **`15.1`, `15.2`, `15.4`, `15.5`,
> `15.6`** — E3's schema half.

Nine leaves, all authorable — **re-derive membership rather than copying it.** Two reconciliation
facts still shrink E3 and both are measured:

- **16.3 is already done.** ADR-055 **D6** declares both R6.15 numbers.
- **16.2 is smaller than its body claims.** `ratchets.json` already carries **both**
  negative-control entries; what is missing is `uplift-controls.yaml`, the oracle tolerance and the
  detection probability.

**12.3 and 13.3 REMAIN FORBIDDEN, and structures 2, 4 and 5 remain deferred.** Those two leaves each
flip an objective KPI to `sensitive: true`. With both flipped the insensitive set is empty and
`classify_regret` maps a negative regret to **`sub-margin`**, whose `confirms_finding_4` is `True` —
**precisely the work that converts a defect into a false confirmation.** A false stop is recoverable;
a false confirmation is not. Under the throughput metric authoring them scores **0**.

**For every barrier line the census prints, state in your opening whether the batch depends on it.
An unanswered barrier is a stop, not a warning.**

**`$LASTEXITCODE` lies if you pipe the census through `Select-Object -First N`.** Re-run with
`*> $null`. A gate's non-zero exit is a claim about the gate; verify the invocation before believing
it.

### STEP 3 — what to do, in priority order

#### A. THE TWIN PHYSICS FIRST — 12.1, 12.2, 13.1, 13.2. Everything downstream is denominated here.

**Arm E is measured and its number lives in D2.7. What is NOT measured is whether a replenishment
DELAY makes information worth anything — that is the next measurement, not a prediction.** Structure
3 (**13.1, 13.2**, correlated lead times) is the decisive pair because it is the only reinstated
structure that introduces a delay; structure 1 (**12.1, 12.2**) is non-stationary demand. Four
obligations, none negotiable:

- **Preserve the refusals.** `negative_regret_refusal` and the comparator-admissibility property
  exist to stop a negative regret becoming a verdict. **No refusal path may be removed to make a
  gate green** — and `tests/uplift/test_regret_comparator_admissibility_property.py` asserts the
  `sub-margin`/`confirms_finding_4` coupling mechanically.
- **Do not build a guard from two expressions that share a term.** `headroom >= regret` reduces to
  `A >= B`; the oracle cancels, so it could never constrain the oracle. Ask what your new guard
  **reduces to** before trusting what it appears to check.
- **Write your predictions down before you measure**, and make them falsifiable. Five pre-registered
  predictions are what made arm E's result legible, including arm independence to sixteen significant
  figures for the fourth consecutive session.
- **Do not let a sum stand in for its addends.** Finding 63's entire content is that a `material`
  verdict was carried by the **sum** of two terms, **neither** of which is material alone. When you
  report the delay's effect, **report the decomposition and its residual, not the total** —
  `contributions()` already does it, and for eight sessions nothing called it.

Measurement is a **labelled CI run**, never local: any `MIN_SCENARIOS`-scale twin run is category 4
under I-0. Add the label, read the artifact, **remove the label.** `twin-regret`'s cost is now
measured — **1.6 min for 800 arm-replicates** — which is what licensed sizing the grid.

#### B. TASK 15.1 — the blast radius is MEASURED and it is smaller than the ledger implies

Session 10 measured this rather than inferring it, and one part of it changes a *different* task:

- `UpliftArtifact` is `frozen=True, extra="forbid"` with ten fields. **`build_uplift_artifact` in
  `uplift/harness.py` is the ONLY production constructor** and `uplift/cli.py` its only caller.
- **No committed JSON fixture carries an artifact payload at all**, so 15.1's declared "every
  committed artifact fixture" is an **EMPTY SET**. Do not go looking for fixtures that do not exist;
  do not manufacture one to satisfy the sentence.
- **The digest-neutrality claim is verified:** `canonical_arm_aggregates` serialises only the sorted
  `ArmAggregate` sequence, so a top-level `interval` leaves `arm_aggregates_digest` byte-identical.
- **The one consumer a name-grep misses is `uplift/uplift_floor.py::PoweredProof.from_payload`**,
  which reads the artifact as a plain dict. It is tolerant of new keys, so **15.1 is safe** — but it
  will **SILENTLY IGNORE the interval**, so **task 17.5 is not obtainable by adding model fields
  alone.** That is coupling 3's lesson in a new place: the consumer that *translates* a value is the
  one a grep does not find.

#### C. The rest of E3, in the order the tasks declare

Interval + schema (15.x), both controls and their job (16.x), Power_Report, floor admission and the
C60 operator (17.x). **E3's floor and task 25's claim may NOT be denominated against the incumbent
arm — the gate has FIRED, the honest baseline is the tuned control at `s=20, S=30`, and tasks 17.2,
17.5 and 25 sit under that prohibition.** It is recorded, not advisory; STEP 0 carries both halves.

#### D. Also owed, and smaller

- **19.4** — a `@register` plus a workflow locus. Deliberately not ticked in session 10.
- **20.3** — `task_claim_truth` reports it `pending: claims nothing yet`. Ticking it requires the
  registry to hold a real validated non-placeholder entry, not a re-worded body.
- **Finding 57** — `_recording_open`'s `if suffix in _DATA_SUFFIXES or under_data:` flags any `.csv`
  anywhere, so a dependency's bundled `cpu_power.csv` fails the slow step and `_REAL_DATA_DIRS` is
  inert. **It is now the SOLE cause of the `uplift-verify` aggregate red.** Another owner's; the
  repair is a judgement (`... and under_data` would let a purchased CSV outside `data/` pass). **Do
  not weaken it (R2.10).**
- **Finding 53** — `security.yml:98`'s second I-1 deny-list omits `replicate`.
- **Finding 45** — the stale C16 docstring at `verify_claims.py:2406-2408`. Its recorded reason for
  not being edited is measurably wrong: **no pin anchors to `verify_claims.py`**, so `doc_truth`
  does not read it.
- **The census severity split** — separate `prior-art` from `candidate-discharge`. Session 10 read
  ~110 informational lines to find 20 real ones.
- **Thirteen of thirty-five audit gates are UNMEASURED** in `execution-routing.md` and therefore
  routed to CI. **Classifying one is a small, real contribution.**
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35); **CI's ruff scope**
  excludes nine trees; **conflict O** — CF-13's enforcement scope covers none of its 56 sites;
  **`scipy` is pinned in NO requirements file** and arrives transitively (finding 41).

### STEP 4 — how a session is actually run

**Waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit.
2. **Write findings into `tasks.md` and the ledger AS YOU FIND THEM.** Session 9 is the proof: work
   on disk that the ledger does not carry scores zero.
3. **Delegate reading and authoring; never delegate execution.** Parallel sub-agents for reading,
   writing and analysis are **required**; **exactly ONE** may execute code. **G7 makes parallel the
   DEFAULT: any wave with two or more independent units dispatches two or more authoring agents, and
   working serially requires a stated reason in your opening.** Partition by **coupling closure**
   (G2), never by file count.
   **Every dispatched agent carries a written contract (G3), and the no-execute clause is its FIRST
   LINE** — session 10 dispatched **thirteen** agents and **five** of them each ran one stray no-op
   shell command before honouring a ban that appeared further down. Four clauses: files it may touch
   and files it must not; the one canonical location for its findings; "authoring only — do not
   execute" unless it is the designated executor; and the couplings it owns, named.
   **And verify an agent's file writes INDEPENDENTLY of its report:** one agent failed with no output
   **after** its write had already landed, which is why ADR-055's amendment log briefly carried a
   session number no progress row supported. **A silent agent is not a no-op agent.**
   **Report what each agent PRODUCED**, not how many there were.
4. **Use the whole tool surface.** Code intelligence, symbol and reference lookup, and research
   powers have gone unused while sessions defaulted to shell and text search. **Finding 48 cost a CI
   run because a consumer was found by grep instead of by asking what *translates* a value** — and
   task 15.1's `PoweredProof.from_payload` consumer is the same shape, found this time.
5. **Re-read the authority file for each wave's area before starting it.**

**Spend `gh` reads first.** Free under I-0 and the highest-yield evidence in this repo. Session 10's
entire CI picture — four shards, a gated `quality-gates`, a skipped `Vitest` step, a confirmed
selection proof — came from runs that were going to happen anyway; its **~4 minutes** of
critical-path wall-clock were **one** labelled `twin-regret` measurement and nothing else.

#### FORBIDDEN REPAIRS. Each names what it would destroy.

No error may be cleared by **giving an argument a default**, by **widening a type to `Any`**, by
**adding a `# type: ignore`**, by **narrowing a checker's scope**, by **lowering a floor**, or by
**adding `continue-on-error`**. **And no refusal path added to make a defect loud may be removed to
make a gate green.** If an error is genuinely a tooling artifact, repair the *declaration that
misleads the checker*, never the call sites that report it.

#### Determine ownership mechanically, and `git log -1` is NOT enough

```powershell
git cat-file -e origin/main:<file>              # exit 0 => exists on main
git diff origin/main -- <file>                  # attribute the LINE, not the file
git merge-base --is-ancestor <sha> origin/main  # exit 1 => this branch's
```

**And for lint or format debt, materialise the blob and re-run the checker.** Session 10 proved the
`test_pipeline_contract.py` format finding was **this branch's** that way (+144/−3 against
`origin/main`, last touched by `4fe1dad`, and task 20.1's own coupling) — which is why it was
repaired rather than recorded. Write the blob from Python with `write_bytes`; PowerShell's `>`
writes UTF-16 and `Set-Content -Encoding utf8` adds a BOM.

---

## STOP CONDITIONS

- **Stop at any barrier the census names that the batch depends on.** Say which.
- **Stop and report if a count does not move as predicted.** State the delta **per code** and what
  you checked.
- **Do not author E3's floor claim, task 17.2, task 17.5 or task 25 against the incumbent arm.** The
  gate has **FIRED**; the honest baseline is the **tuned control at `s=20, S=30`**. This is a
  recorded prohibition, not a preference.
- **Do not author 12.3, 13.3, or structures 2, 4 and 5.** 12.3 and 13.3 empty the insensitive set and
  turn a negative regret into a false confirmation. **12.1, 12.2, 13.1 and 13.2 ARE reinstated.**
- **Do not tick 14, 21, 22.3, 25 or 26.5** without the naming job's own verdict.
- **Do not tick 20.7 or 20.8** until `Vitest unit + property tests` executes. It was **skipped**
  behind a Biome lint failure, and a skipped step is not a pass.
- **Do not tick 19.4 or 20.3** without their own mechanism: 19.4 owes a `@register` plus a workflow
  locus, and `task_claim_truth` will name 20.3 as long as the registry holds a placeholder.
- **Do not remove or weaken `negative_regret_refusal`** to make `twin-regret` green. Its red is the
  finding.
- **Do not accept the Kaggle M5 terms.** C74 is non-passing **by decision**; the M5 score and the
  ancestry row are permanently `unavailable`. **Task 25's claim is scoped to the twin and must say
  so**, and R8.18 requires distinguishing "a published model" from "a published model scored against
  a published leaderboard".
- **Do not create `.kiro/specs/external-audit-anchor/`** unless the operator asks. Task 23 is
  deferred to it **by name**; the spec is not created and its open obligation is **ADR-056's
  supersession of ADR-033**, not OQ-4.
- **`pin_extractor_truth`'s declared count — DERIVE IT, do not read it:**
  `python -m scripts.audit.pin_extractor_truth --check`. **Assert `declared == len(pins:)` read from
  the file, never against a transcribed integer** — that is conflict P's durable repair. The parked
  `mutation-fast-required-job` row **would fail if activated**, and session 10 measured that for the
  first time rather than predicting it.
- **Do not change `main`.**
- **Do not run `ledger_gen` or `readme_gen`** locally, in `--check` or `--write` form, for any
  reason — **and that includes `tests/verify/test_ledger_gen_property.py`.**
- **Do not pad a session toward forty**, and do not read a small census delta as a small session.
- Surface every new conflict rather than resolving it silently.

## THE CHAIN, MEASURED RATHER THAN PREDICTED

| # | Obstruction | State |
|---|---|---|
| 0 | the runner itself — billing | **CLEARED** — repository made public |
| 1 | step 8 mypy strict (orchestrator) | **CLEARED** (2r) |
| 2 | step 17 **C56** narrative-truth | **CLEARED** |
| 2.5 | step 18 golden-trace replay | **CLEARED** — first execution ever, exit 0 |
| 3 | step 19 unit tests | **CLEARED** |
| 4 | steps 20–22 coverage / spec coverage / contract | **CLEARED** |
| 5 | `uplift-verify` step 5, the fast surface | **CLEARED.** `850 passed`, 0 failed |
| 6 | `uplift-verify` step 6, the slow surface | **EXECUTED.** 1 failed — `main`'s I-1 defect |
| 7 | the slow step's Pinecone failure | **CLEARED.** The construction guard passes; there was no second site |
| 8 | `truth-gates.yml` steps 6–12 | **NEVER EXECUTED HERE** — skipped behind the C44/C69 red (finding 51) |
| 9 | `uplift-verify` step 5, the fast surface | **CLEARED.** Four shards `success` at `27a74a3` |
| **10** | **the slow selection's next assertion** | **UNCHANGED, and now the SOLE cause of the `uplift-verify` aggregate red.** `data_file_reads` false-positives on a dependency's bundled `.csv` (**finding 57**) — another owner's, unrepaired, and the repair is a judgement R2.10 constrains |
| **11** | **`quality-gates` step 6 `Ruff format check`** | **CLEARED and CONFIRMED — `success` at 23 of 23 at `fa42263`.** One file's formatting had gated **17** steps. **NOT claimed at the newest sha, where the job was `cancelled`, superseded — read it** |
| **12** | **the aggregator's step 5 selection proof** | **CLEARED and CONFIRMED.** Finding 62's in-run `universe` measurement reports `shards selected 170/150/349/264 = 933; unsharded selection = 933`. Step 4 (the file-level partition proof) was already green |
| **13** | **`Frontend CI` step 6 `Biome lint`** | **RED, not adopted.** It skips **step 8 `Vitest`**, which is the only route to 20.7/20.8. Two further frontend jobs red on separate causes |
| **14** | **`Truth Gates` / `Integration` / `Mutation`** | **RED, NOT INVESTIGATED.** Said plainly rather than implied |

## HARD-WON LESSONS. Sixty-three findings and eighteen conflicts, each one paid for.

### The habits that caught the most

1. **Write predictions down before measuring, and make them falsifiable.** A prediction recorded
   after the number arrives is not a prediction. Session 10's `gate_surface` prediction was **right
   in content and wrong in magnitude**, which is itself a finding: **the row delta for one step
   change is (trigger contexts × sections), not 1** — six renamed rows and five new rows for one
   rename plus one addition.
2. **A guard built from two expressions that share a term cannot constrain that term.**
   `headroom >= regret` reduces to `A >= B`; the oracle cancels. **Ask what a guard reduces to
   algebraically before trusting what it appears to check.**
3. **An equality against a frozen constant is a TOTAL, not a partition proof.** Finding 62:
   `EXPECTED_FAST_SELECTED: "874"` still passes when *n* tests are dropped and *n* added.
   **Partition, never filter; assert exhaustive-and-disjoint; measure the right-hand side in the
   same run** (G5).
4. **A citation is not a mechanism.** Walk to the constructor; read the code path the assertion
   names, not the docstring of the object that holds it.
5. **A document edit's blast radius is every pin anchored to that document.** Eight of the eighteen
   pins anchor to ADR-055. Session 10 probed **all 18 on both sides after THREE amendments in one
   session** — all 15 live rows `ok`, all 8 ADR-anchored rows matching **exactly one** line, and each
   of the six forbidden anchor patterns occurring **exactly once**. Probing only the pin you are
   adding is finding 48 in a new place.
6. **Check your own instrument before you trust its verdict.**
7. **Read what got SKIPPED behind a failure, not only what failed.** One formatting finding gated 17
   steps at `27a74a3`; one Biome finding skipped the only step that can discharge two leaves. **One
   101-character line once gated 18 steps and 3 jobs.**
8. **Read the LOG, not the summary, and read the OTHER workflows for the same sha.**
9. **Exclude mechanisms explicitly, and say which.** A survivor labelled a hypothesis with a named
   falsifier is worth more than a confident guess.
10. **Verify what you already had, not only what you touched.** Task 26.1's discharge sat unclaimed
    for two sessions; **session 9's twenty leaves sat unticked for one.** G4 exists because this is
    not remembered.
11. **Consensus across documents is not evidence.** It is usually one unchecked claim copied
    forward.
12. **Capability is not use.** `contributions()` could decompose a cost for eight sessions and no
    run called it. I-0 permitted unlimited parallel authoring for eight sessions and sessions used
    zero.

### On verdicts and assertions that cannot move

- **A number that cannot fail is not a number; a verdict that cannot be anything else is not a
  verdict; and a regret measured against a comparator that loses to its own subject is neither.**
- **Sound arithmetic on the wrong denominator is still the wrong answer** (finding 61). Ask what the
  quantity you measured is a difference *between* before you name it.
- **A SUM can be material when NEITHER of its addends is, and the verdict cannot say which** (finding
  63, ADR-055 D2.7). **Decompose before you publish**, and report the residual: a gate that reads a
  total is blind to which term carried it.
- **A false stop is recoverable; a false confirmation is not.** Rank your failure modes by which one
  nobody would notice.
- **A tautology dressed as an assertion is the same defect as no assertion.** Check whether your new
  assertion can fail before writing it.
- **Prove a refusal path by construction**, and **assert non-emptiness**.
- **Repair a stale assertion by PARTITIONING, not FILTERING.**
- **A precondition correction is not an assertion weakening**, and the test of which one you have is
  whether the standard got *stricter*.
- **Never weaken a generator, an assertion or a floor to make something pass** (R2.10).

### On gates reporting the wrong thing

- **A required check that can only report `skipped` is not a gate.** That is why the shard split
  kept `uplift-verify` as a thin aggregator with `needs:` and `if: always()` rather than a matrix.
- **`set -o pipefail` in any `run:` that pipes a gate** — without it a `| tee` reports success with
  a refusal inside the artifact.
- **A deny-list is fail-open by construction — BUT check what the invariant actually says before
  widening one.** I-1 is a closed list of four names and ADR-018 (Accepted) sanctions Pinecone's
  free tier. **When a gate's predicate is wrong, widening its scope makes it more wrong.**
- **A SKIP is not a PASS, a deselected test is not a pass, and `unavailable` is not
  `inconclusive`.**
- **`UNAVAILABLE` from a floor with no measurement is the gate working, not failing.** C74's
  non-passing state is now that by **decision**: the M5 terms will not be accepted, so the score and
  the ancestry row are permanently `unavailable`.
- **A verdict is a claim about its own derivation.** `Select-Object -First N` makes a passing gate
  report non-zero; a splatting bug made a gate exit 2 when it is 0.
- **A local red is not always a CI red, and a local green is not a CI green.**

### On scope, ownership, adoption and closures

- **CI's scope is not the tree's scope, and the gap is measured.** `ruff` covers
  `packages/synapse_common/ agents/ orchestrator/` **only**.
- **Attribute lint debt by materialising the committed blob and re-running the checker.** Three
  sessions proved they added none this way; session 10 proved it had added **one**, and repaired it.
- **Necessary is not sufficient.** Ask what else gates the thing you are trying to reach.
- **Do not adopt another owner's debt unilaterally**, but record the diagnosis.
- **One diff, one cause.**
- **A workflow that has never executed is the I-7 shape, and *reachable* is not *run*** — and *run*
  is not *finished*.

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass, and worth ZERO on the metric.** |
| `[x]` | done **and** discharged |

- **A `[~]` graduates on the job's own verdict, never on a local run**, and owes a `last-checked:`
  sub-bullet naming the run it was read at. The census is **non-passing** without it (G4).
- **A `discharge:` line can name TWO subjects**, and both must report.
- **A job's colour is not the task's verdict.** A red run has discharged a leaf before.
- **"Authored and diagnostics-clean, not executed" is a legitimate result.**
- **DISK OUTRANKS THE LEDGER, and it has now happened twice at scale** — eight tasks in session 1,
  twenty in session 9. **`tasks.meta.json` is not authority.**

---

## I-0 — the rule most likely to burn the machine

**15.71 GB** RAM (6.86 free at measurement), i5-12450HX **8 physical / 12 logical**, RTX 3050 6 GB,
thermally throttling. **No workload in this repo needs the GPU.** **Process type and process count**
are what throttle it, and the cost metric is **cores × wall-seconds**.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`'s
  CLI, bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection
  --sweep`, `pnpm` anything — **and `tests/verify/test_ledger_gen_property.py`.**
- **Cheap and encouraged:** file reads, `grep`, diagnostics; `ruff`/`mypy` on changed files; bounded
  scoped `pytest`; `spec_ledger_census`; the **six** cheap gates; `command_path_truth` and
  `ratchet_truth` over the committed tree; `replay_metrics` through its `measurers` seam;
  **`doc_truth.documented_value`, `extract_source_values` and `resolve_pin_texts` as pure
  functions** — session 10's whole-table 18-pin probe is built from exactly those and it is how the
  parked row's would-fail state was measured; and **`gh` API reads — free, and the highest-yield
  evidence in this repo. Spend them first.**
- **Verify at the budget that will judge you.** A scoped **pure-arithmetic** file at
  `HYPOTHESIS_PROFILE=ci` costs seconds and catches what `dev` cannot.
- **`mypy --strict` over `tests/verify` or `tests/uplift` EXCEEDS a 120s budget.** Type-check
  changed **non-test** modules by dotted name and **say plainly that the test modules were not
  checked.**
  Mixing `scripts/audit/*.py` and `tests/**` in one invocation fails instantly with "Source file
  found twice".
- **Concurrency is the load-bearing half.** Parallel authoring agents: **required**. Agents that
  execute code: **exactly ONE**.
- **Preferred flags:** `-q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
  **`HYPOTHESIS_PROFILE` unset loads 500 — a 50× load. Set it explicitly, in the same command.**
- **Report core-seconds, not just invocation counts.** Session 10 spent **~1,100** across ~30 cheap
  gates, three `ruff` passes, two `mypy --strict` runs and **two** bounded `pytest` invocations (`ci`
  = 63 s, `dev` = 4 s) — all serial, one executor, no repo-wide run.
- **Sweep before finishing, and after any cancelled or timed-out command.**

### Verification sweep

**Per wave** — only what that wave touched, plus **anything the last CI run reported red**:

```powershell
python -m ruff check <wave's changed files>
python -m ruff format --check <wave's changed files>
python -m mypy --strict -m <dotted name of each changed non-test module>
git ls-files --eol <wave's changed files>          # w/mixed after ANY programmatic edit
$env:HYPOTHESIS_PROFILE='dev'
python -m pytest <wave's touched loci> -q --tb=line -p no:randomly -m "not slow"
```

**Before closing:**

```powershell
python -m scripts.audit.workflow_shape_truth              # C64   expect 0
python -m scripts.audit.pin_extractor_truth --check       # C75   expect 0; DERIVE the count
python -m scripts.audit.sweep_budget_truth --check        # C73   expect 0
python -m scripts.audit.dataset_licence_truth --check      # C74   expect 2 = SKIP, BY DECISION
python -m scripts.audit.task_claim_truth --check          # expect 1 = pre-existing, other spec
python -m scripts.audit.gate_surface --check              # C63   expect 0
python -m scripts.audit.spec_ledger_census --files --check # expect 0
```

Expected: **`0 / 0 / 0 / 2 / 1 / 0`** plus census 0, measured again in session 10. **Append
`*> $null` and read `$LASTEXITCODE`** — piping any of these through `Select-Object -First N`
manufactures a non-zero exit. `task_claim_truth`'s **1** is `core-purpose-uplift` tasks **9** and
**9.1**, another spec's, and it was re-read **after** twenty-four leaves were ticked rather than
assumed unchanged.

**The census's `unharvested-pending` rule is the mechanical form of G4.** It exits **2** for any
`[~]` leaf recording no `last-checked:` run for its discharge job. **There are two `[~]` leaves now
(20.7, 20.8), so this rule is live rather than theoretical** — and **checking without writing it
down does not satisfy it.**

**And probe every pin anchored to any document you edited**, on both sides, before committing.
`doc_truth.documented_value` requires **exactly one** matching line; zero and two are equally fatal,
and `pin_extractor_truth` reports green through a document-side failure.

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **The line-ending trap has now fired TEN CONSECUTIVE SESSIONS**, most recently on `ci.yml` and
  `blocking-steps.yaml` from `str_replace` edits. Normalise to the file's **dominant WORKTREE**
  ending, measured from Python at `newline=''` — session 10 measured **CRLF** (1356 vs 93, and 802
  vs 15). **The `i/lf` column would have led a reader to guess LF and make it worse** (finding 33).
  Check `git ls-files --eol` after **any** programmatic edit, including edits to these three
  documents.
- **`Select-Object -First N` on a native command makes `$LASTEXITCODE` non-zero.**
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated.** Assign, then `foreach`.
- **Complex inline `python -c` breaks on quoting.** There are no heredocs. Write a temp `.py` under
  `.tmp/` (git-ignored), run it, delete it.
- **`ruff`'s `SIM300` reads an upper-case attribute as a constant**, and **`N802` rejects an
  upper-case word in a test name** — fix the name, never add a `noqa`.
- **`git push` writes progress to stderr**, so `$LASTEXITCODE` is non-zero on a **successful** push.
  Read the `old..new ref` line.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental` after any
  config change.
- **`git log -1 -- <file>` is last-touch, not authorship.**
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** `>` writes UTF-16;
  `Set-Content -Encoding utf8` adds a BOM that `read_text(encoding='utf-8')` does **not** strip.
  `Copy-Item` is a byte copy and is safe. **Verify bytes, never the console.**
- **`git status` over-reports.** Trust `git diff`, stage precisely, `git check-ignore -v` first.
- **Identify a CI run by `head_sha`, NEVER by timestamp.** The local clock is ~2h45m ahead.
- **`addopts` carries `-v`**, so every local run is verbose — **filter reads, never dump them.** One
  job-log read once cost 112 KB of truncated output.
- **`testpaths` omits `digital_twin`** while `uplift-verify` collects it, so a bare `pytest` and CI
  disagree about what the suite is.
- **`git commit -F` a temp file** for any message longer than a line.
- **`gh run download <id> -n <name> -D <dir>`** beats parsing a `| tee`'d log for an artifact.
- **Adding a label fires every workflow with a `labeled` trigger. Remove the label after use.**
- **Do not run `pre-commit install`.**
- Python 3.14.0, **mypy 1.19.1**, pytest 8.4.2, hypothesis 6.151.11, jsonschema 4.26.0.
  `gymnasium` absent. `gh` 2.82.0, authenticated. **Repository is PUBLIC — Actions minutes are
  unmetered on standard runners, and jobs run in parallel at no extra cost.**

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). **Do not assert a total** (CF-13). Note conflict
  O: the rule is enforced over a scope containing none of its 56 violations.
- **`-m "slow"` is a selector, not a path filter.** A slow-marked test outside the paths the slow
  selection collects is selected by **no job at all**. **The fast surface is now SHARDED**, so check
  which shard's partition your new test lands in — and that the partition still proves itself
  exhaustive and disjoint **in-run** (finding 62).
- **No `DECLARED_INVENTORY` entry is owed for a new property in this spec** — that table covers
  properties 1–37 and this spec's surface sits outside it (conflict O's measured scope gap).
- **Assert a clause unconditionally** rather than wrapping it in a tolerated-exception disjunct.
  **Prove a refusal path by construction**, and **assert non-emptiness**.
- **Derive numbers; flag the irreducible choice.**
- **`set -o pipefail` in any `run:` block that pipes a gate or a measurement.**
- Type hints everywhere (`mypy --strict`); Pydantic v2 `ConfigDict(frozen=True)` for recorded facts;
  `structlog`, never `print()`, in library code; canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`; `encoding='utf-8'` on **every**
  `read_text` (E-S13-07); ASCII-only console output; lines <= 100 characters.
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, `replicate`, or any paid SDK. **Note
  what I-1 does NOT say:** it is a closed list of four, and ADR-018 sanctions Pinecone's free tier.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS.

### The five same-commit couplings

1. A rename and its declaration.
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the job
   is genuinely eligible** (conflict G).
3. A schema change and every fixture that carries it — **including whatever TRANSLATES the value.**
   **Measured for 15.1:** the fixture set is **empty**, and the translator is
   `PoweredProof.from_payload`, which ignores the interval rather than rejecting it.
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** **Predict the row delta, then measure it — and
   the delta is (trigger contexts × sections), not 1.**
5. The session ceiling lives in **one** place, `spec_ledger_census.DEFAULT_BATCH`.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** One commit **per wave**.
- Prefer new commits over `--amend`. No force-push, no `--no-verify`, no interactive flags. Leave
  git config unchanged. **Push to the PR #84 branch, never to `main`.**

---

## What this spec is actually for — hold this while you work

SYNAPSE claims multi-agent AI makes better supply-chain decisions than a simpler system. That claim
is currently untestable — not because the answer is bad, but because nothing in the project can yet
produce an answer that would mean anything. The thesis:

> Make the instruments provably able to fail, make the simulated world one where intelligence can
> pay, prove the measuring device can detect an effect, and only then measure — on non-synthetic
> data, against a published external benchmark.

**Two checkpoints can end this project early, on purpose.** Checkpoint A's task 11 can falsify
Finding 4 and re-cut R5. Checkpoint B's task 14 can prove consensus unnecessary and cancel E3 —
**and conflict R records that R5.28 is unsatisfiable a second time, with R5.29 then cancelling E3 on
a theorem rather than on a measurement.** Read task 14's body before planning any session that
reaches it.

**Three times now the same instrument has been caught pointing at the wrong quantity.** Session 4
found the comparator measuring a no-op and reporting it as the `(s, S)` regret. Session 7 measured
the repaired instrument and found the *oracle* invalid. Session 10 found that the surviving
quantity is a **different difference than the one the requirement names** — EVPI plus the
incumbent's own mis-tuning (finding 61). **An instrument that can end the project is only safe if
you keep asking what its guard reduces to, and what its number is a difference between.**

**The pre-commitment, binding before the number is known:** if measured uplift is null or negative,
**it is reported as null or negative.** The floor stays at `0.0`, no headline is published as a
gain, and the result is written up as a finding — not reframed, not re-run at a different replicate
count until it moves.

Four guards on reading the result: a null while any objective KPI is recorded not observably
sensitive is **inconclusive**, not confirmation (task 10.5). No headline may be published while no
Power_Report describes the harness revision under measurement (task 17.3). A `material` verdict on a
point estimate with no dispersion is not a falsification, nor is one on a comparator the requirement
does not name (conflict M), nor is any verdict at all on a comparator that loses to its own subject
(finding 54). **And no claim may be denominated against the incumbent arm: the gate has FIRED, the honest baseline
is the tuned control at `s=20, S=30`, and `material` on tuning alone is refused** (finding 63,
ADR-055 D2.7).

---

## Session 10 in one paragraph — the rest is in `HANDOFF.md`

**Twenty-four leaves discharged — twenty by RECONCILIATION and four from arm E.** Session 9 landed
five feature commits and recorded one ledger entry, so twenty leaves were complete on disk and marked
`[ ]`; session 10 ticked them, kept 20.7/20.8 `[~]` behind a skipped `Vitest` step, and deliberately
left 19.4 and 20.3 open. **Finding 63** (ADR-055 **D2.7**) is the session's design result and the
reason the batch moved: the judged regret is **85.6% baseline mis-tuning and 14.4% information
ceiling**, **neither addend material alone**, so the `material` verdict came only from their **SUM** —
**Finding 4 is substantively TRUE and R5.3's mechanical test could not see it.** **The hard gate
fired: no claim may be denominated against the incumbent arm, and structures 1 and 3 are
reinstated.** **Finding 62** is cleared and confirmed — the frozen-literal selection total is now an
in-run measurement, `933 == 933` — and `quality-gates` is `success` at 23 of 23 at `fa42263`. **Four
numbers:** 25 discharged, **~1,100** core-seconds, **~4 minutes** of CI critical path, and **13**
agents dispatched, of which **five ran one stray no-op shell command each** and **one failed with no
output after its write had landed** — which is why the no-execute ban is a contract's first line and
why an agent's writes are verified independently of its report. **Not verified, and must not be
claimed:** that `quality-gates` is green at the newest sha (it was `cancelled` there), finding 57 —
now the **sole** cause of the `uplift-verify` aggregate red — `vitest` at all, the frontend jobs,
`Truth Gates`/`Integration`/`Mutation`, and **that a replenishment delay would produce material
information value. That is the next measurement, not a prediction.**
