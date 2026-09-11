# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **7** (2026-09-11).

**This prompt states no HEAD, deliberately.** Conflicts J and K were the same defect three sessions
running: the prompt is written *before* the commit that carries it, so any sha it names is stale by
construction. STEP 0 derives it instead.

**And this prompt carries no transcribed count that a gate can derive.** Conflict P was exactly
that defect — a stop condition asserting `pin_extractor_truth` would report `16` when three parked
rows made it `17`, which would have halted a correct session and looked like a pin defect. Where a
number appears below, the command that derives it appears beside it.

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`.

**Your session cap is FORTY leaf tasks, in waves of about ten. It is a ceiling and it is
expected never to bind.** What stops you is a barrier or a phase boundary. Session 7 stopped at
**four commits** because the measurement it took invalidated the work it had approval to author.

### STEP 0 — THE THROUGHPUT RESET IS INSTALLED AND UNTESTED. YOU ARE THE TEST.

**Session 8 installed three steering documents, made the `[~]` harvest mechanical, and measured
the decomposition that settles task 11. It discharged ZERO leaves and dispatched ZERO parallel
agents — so `throughput-with-integrity.md`'s G6 target is missed by construction, because that
session wrote the rules rather than ran under them.**

**Read these three first; they are `inclusion: always` and they govern how you work:**
`.kiro/steering/local-compute-budget.md` (I-0), `.kiro/steering/execution-routing.md` (where a
workload runs), `.kiro/steering/throughput-with-integrity.md` (**the metric, and six guardrails**).

**The metric you are judged on: leaves DISCHARGED. A `[~]` counts ZERO. Target: >= 11.** If you
miss it, the progress ledger says the reset failed and names the lever — that is G6 and it is not
optional.

**Task 11's disposition is DECIDED: option (b).** ADR-055 **D2.5.3** is the canonical record; do
not re-derive it. The measurement found two defects and the arithmetic shows repairing the
objective alone leaves the regret negative.

### STEP 0b — CHECKPOINT A RAN IN SESSION 7 AND RETURNED A REFUSAL, NOT A VERDICT.

**Derive the state; never trust this document for it.**

**Session 7 committed the materiality margin and discovered that the arm labelled
`perfect_foresight` loses to the incumbent it is supposed to bound.** Runs `34570166681` and
`34574731853`, 200 of 200 replicates usable:

| quantity | measured |
|---|---|
| `comparator_headroom` (A−C) | `8.937888952967558` — unchanged from run `34366766968` to every digit |
| `mean_noop_cost` / `mean_foresight_cost` / `mean_reference_cost` | `11.8352…` / `2.8973…` / `2.0849…` |
| **`regret` (B−C)** | **`-0.8123524459522771`**, interval `[-0.8273…, -0.7978…]`, **excluding zero** |
| `margin_committed` (run 2) | **`0.4`** — the rule re-derived it, the headroom guard passed |

**Task 10.4 is `[x]`. Task 11 is deliberately `[ ]`. E2c was NOT authored.** Read ADR-055
**D2.5.2** and task 11 before doing anything else; the reasoning there is the session.

**Derive the state; never trust this document for it.**

```powershell
git rev-parse --short HEAD
git rev-list --count origin/main..HEAD
gh run list --branch feat/decision-quality-proof --limit 10 --json databaseId,headSha,workflowName,conclusion
```

Then read **both** jobs' step lists for the newest sha — not the run's colour, the step list:

```powershell
$j = gh api "repos/:owner/:repo/actions/runs/<id>/jobs" --paginate | ConvertFrom-Json
foreach ($job in $j.jobs) { "{0} | {1} | steps={2}" -f $job.name, $job.conclusion, $job.steps.Count }
foreach ($job in $j.jobs) { foreach ($s in $job.steps) { "{0,3} {1,-12} {2}" -f $s.number, $s.conclusion, $s.name } }
```

**Use a `foreach`, not a pipeline: PowerShell 5.1's `ConvertFrom-Json` hands back the array
unenumerated and a piped `ForEach-Object` receives it as ONE object.** This fired again in session
7 and printed `System.Object[]` five times.

**Then read the LOG, not only the step list**, and read the OTHER workflows for the same sha.

```powershell
$log = gh api "repos/:owner/:repo/actions/jobs/<jobid>/logs" 2>$null
($log | Select-String -Pattern "FAILED tests|Falsifying example|passed|registry-gate|Summary:").Line
```

**What to read, in priority order:**

1. **Is `quality-gates` still green at 26 of 26?** It is a green `required:` check. A regression
   here is the most important thing that can happen to this branch.
2. **THE CONSTRUCTION GUARD IS CONFIRMED — READ WHAT FAILS NOW INSTEAD.** Run `34578002704`
   (sha `4539b91`): step 5 `success`, **step 6 RAN**, and `guard.paid_client_attempts == []`
   **passes** for the first time since that property first executed. So finding 50/52's defect is
   closed and there was no second construction site. The job is red on the **next** assertion in
   the same test — **finding 57**, a false positive over
   `.../site-packages/codecarbon/data/hardware/cpu_power.csv`, caused by
   `_recording_open`'s `if suffix in _DATA_SUFFIXES or under_data:` flagging any `.csv` anywhere
   and leaving `_REAL_DATA_DIRS` inert. **Another owner's file, and the repair is a judgement:
   `... and under_data` would let a purchased CSV outside `data/` pass. Do not weaken it (R2.10).**
   **Confirm this is still the failure before acting** — assertion N+1 may itself be hiding N+2.
3. **Task 11's disposition.** It is the operator's, it is costed in three options in task 11, and
   **E2c is blocked behind it.** See STEP 3.
4. **`truth-gates.yml` step 5's own log.** Finding 51: steps 6–12 are `skipped` behind a
   pre-existing C44/C69 registry red, so both generator `--check`s and `gate_surface --check` have
   never executed on this branch. Read the `Summary:` and `registry-gate:` lines for the baseline.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the ceiling, wave discipline, the
   **barrier stop**, the three marks, the four checkpoints, the batch table, the six cheap gates,
   the progress ledger. **Read row `7` in full.**
3. `HANDOFF.md` (repo root) — the state of the tree, and **what is verified versus merely
   authored**. Read its honesty ledger before believing any colour.
4. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
   **Its I-1 sentence is load-bearing and was misread for two sessions: the paid-client list is
   CLOSED at four names.**
5. `.claude/skills/synapse-engineer/SKILL.md` + `references/`.
6. `.cursorrules` + `docs/cursor/*.md`.
7. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.5, D2.5.1, D2.5.2 and the amendment log.**
   D2.5.2 is session 7's and it is where finding 54 lives.
8. `docs/adr/ADR-018-pinecone-semantic-cache.md` — **Accepted, and it sanctions Pinecone as a
   free-tier dependency.** This is what makes conflict Q a conflict.
9. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. `tasks.md` is the **ledger
   and your worklist**; tasks **10.4**, **11** and **27.5** carry sessions 5–7's findings in full.

**Two invariant numberings disagree.** `references/14_invariants.md` and `.cursorrules` differ on
I-6, I-8 and I-10. Authority 5 outranks authority 6. The invariants this work cites — I-1, I-4,
I-5, I-7 — agree in both.

When two sources conflict, the higher-numbered authority wins **and you must surface the conflict
rather than resolving it silently.** Seventeen have been surfaced (A–Q). **Seven are corrections to
instructions a session was itself given; conflict Q corrects an instruction this session's own
operator gave, on the strength of an Accepted ADR.** Expect more.

### STEP 2 — derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

At handoff: **142 leaf tasks — 66 done, 0 authored-pending-discharge, 76 open** (70 authorable,
**6** CI-gated). Session 7 ticked **26.1** and **10.4** and registered **26.4** and **26.5**.
`pending: 0` for the first time in this spec's life.

**The answer, which you should re-derive rather than copy: the batch DEPENDS ON BARRIER 11, and 11
is no longer a measurement problem but a DESIGN decision.** Task 12's precondition is task 11's
verdict, and task 11 currently has a refusal rather than a verdict. Barrier 14 (checkpoint B) is
downstream of the same defect: all four of task 13.7's measurements are regret against the
comparator finding 54 invalidated.

**Task 26.4 is authorable and is NOT behind either barrier** — it touches no measurement. That is
the one substantial piece of authoring work available without an operator decision.

**For every barrier line, state in your opening whether the batch depends on it. An unanswered
barrier is a stop, not a warning.**

**`$LASTEXITCODE` lies if you pipe the census through `Select-Object -First N`.** Re-run with
`*> $null`. A gate's non-zero exit is a claim about the gate; verify the invocation before
believing it.

### STEP 3 — what to do, in priority order

#### A. TASK 11'S DISPOSITION. It is an operator decision and E2c is blocked behind it.

**The defect, in one sentence:** `regret = B − C` is negative because arm C, the oracle, costs more
than arm B, the incumbent — so C does not bound B and their difference is not a regret.

**Why the existing guard could not see it, and this is the transferable part.** `_measure` refuses a
run in which `headroom >= regret` fails. Substituting the definitions gives `(A − C) >= (B − C)`,
which reduces to **`A >= B`** — "doing nothing costs at least as much as the incumbent". True, and
entirely silent about C, because **C cancels.** A guard built from two expressions that share a
term cannot constrain that term. **Nothing anywhere asserted `regret >= 0`** until session 7.

**Three mechanisms were EXCLUDED. Do not re-derive them.** Unequal footing (excluded by
construction — `run_three_pass` imports `observe`, `_apply_reorders` and `_derive_unit_costs` from
the harness and drives every arm on one cadence with one `restock_threshold`); lead time (excluded —
`_apply_reorders` applies through `sim.add_stock`, instantaneous, and `_restock`'s own lead time is
off in all three arms); and the `Mapping[str, int]` truncation ADR-055 D2.5.1 records (excluded —
arm C is genuinely not routed through `_drive`, which was **checked** rather than assumed precisely
because the ADR predicted an effect of the right order in the right direction).

**The surviving explanation is a HYPOTHESIS, and its falsifier is the cheapest of the three
options.** `stockout_rate` carries weight **8.0** — equal to `unmet_service`, eight times `on_hand`
— and **ADR-055 D3 already records that its numerator counts SKUs at zero stock and "does not count
unmet demand".** `ForesightPolicy.decide` orders the shortfall "no more, no less", driving on-hand
to zero every window; `Par_Level_Reorder(s=50, S=100)` holds a 50–100 unit buffer. So the objective
charges the efficient arm 8.0 for being efficient. **No per-term decomposition was measured**, so
this is inference from the weights plus D3's own statement.

**The three options, costed in task 11:**

1. **Report the per-term decomposition first** — add each arm's per-term contribution to
   `twin-regret.json`. Cheapest, it is the falsifier the hypothesis needs, and it makes the next
   labelled run decide the question instead of an argument. **Recommended first move.**
2. **Replace `ForesightPolicy`** with an arm that actually minimises the committed objective over
   the known trace, making it an oracle by construction rather than by name.
3. **Repair the objective's `stockout_rate` numerator** so it counts unserved demand. Largest: it
   moves a committed weight's meaning, so D2.3/D3 and every historical value quoting it are
   affected, and ADR-055 D4's rule about a KPI whose meaning moves applies.

**Do NOT read the refusal as a bug to be removed.** It is the guard that stops a negative regret
becoming `sub-margin` once E2c lands — and `sub-margin` is the one verdict that **confirms** Finding
4. `tests/uplift/test_regret_comparator_admissibility_property.py` asserts that mechanically.

#### B. WHY E2c IS BLOCKED, so you do not un-block it by accident

Tasks **12.3** and **13.3** each flip an objective KPI to `sensitive: true`. With both flipped the
insensitive set is empty, and `classify_regret` maps this same negative regret to **`sub-margin`**,
whose `confirms_finding_4` is `True`. **E2c is precisely the work that converts this defect from a
wrong verdict into a false confirmation.** Conflict M's defect forced `material`, which stops the
spec loudly; this one confirms the premise quietly. **A false stop is recoverable.**

#### C. TASK 26.4 — authorable now, and its coupling must be CHECKED not assumed

Swap `regenerate-truth-docs.yml`'s two generator `--write` steps (`readme_gen` before `ledger_gen`)
and move `truth-gates.yml`'s matching `--check` order with them. **A step ORDER change moves rows in
`docs/state/GATE_SURFACE.md`**, so `gate_surface --write` belongs in the same commit — coupling 4.
Precedent cuts both ways: it fired on a `needs:` removal with 3 rows changed and zero added, and did
**not** fire on a `run:`-only edit whose step name did not change. **Predict the row delta, then
measure it.** Never run `ledger_gen` or `readme_gen` locally in any form.

#### Also owed, and smaller

- **THE `uplift-verify` JOB SPLIT — specified in session 8, deliberately NOT landed, and the
  reason is a risk judgement rather than a budget one.** It is the largest free throughput win
  available and it touches a **required** check, so it gets a spec instead of a half-landing.

  **The win:** one serial job runs ~880 fast tests in ~18 min then ~9 min of slow, plus ~3 min
  install — about 30 min. GitHub runs jobs **in parallel at no extra cost**. Sharding the fast
  step by path plus the slow selector as its own job gives roughly `3 + max(shard)` ≈ **8–13 min**,
  a ~2.5–3.5× cut. Install cost is paid per shard, which is what bounds the gain; four shards is
  near the knee.

  **The trap, and it is why this is not a matrix.** `infrastructure/quality/required-checks.yaml`
  declares `uplift-verify` **`required:`**. A matrix parameterises the job NAME, so the declared
  check would stop resolving — `required_checks_truth` fails and the required check vanishes. That
  is the "a required check that can only report `skipped` is not a gate" family, which session 5
  spent a whole disposition removing.

  **The shape that works:** keep `uplift-verify` as a **thin aggregator** with `needs:` on the new
  shard jobs, `if: always()`, and a step that fails unless **every** `needs.*.result == 'success'`.
  `if: always()` is load-bearing — without it a failing shard makes the aggregator `skipped`,
  reintroducing the exact defect. The declared name and its pass/fail semantics are preserved.

  **Couplings, all same-commit and all to be CHECKED not assumed:** `blocking-steps.yaml` entries
  for every new step name; `gate_surface --write` (a job/step change; precedent cuts both ways);
  `required-checks.yaml` only if a shard becomes genuinely eligible (conflict G).

  **G5 applies:** assert the partition is **exhaustive and disjoint** and that total collected
  equals the pre-split count — predicted, then measured. A split can silently drop a path or mask
  a test that only passed because another ran first.

- **Finding 57** — `_recording_open`'s `if suffix in _DATA_SUFFIXES or under_data:` flags any
  `.csv` anywhere, so a dependency's bundled `cpu_power.csv` fails the slow step and
  `_REAL_DATA_DIRS` is inert. Another owner's; the repair is a judgement (`... and under_data`
  would let a purchased CSV outside `data/` pass). **Do not weaken it (R2.10).**
- **Task 26.4 is authorable now** and is not behind either barrier.
- **Thirteen of thirty-five audit gates are UNMEASURED** in `execution-routing.md` and therefore
  routed to CI. Classifying one is a small, real contribution.

- **Task 26.5**, the second regeneration by label, graduating the two `s`/`S` pins. **Its
  verification is weaker than it looks** (finding 51): the two gates that would confirm it are
  skipped behind the C44/C69 registry red, so plan the discharge around `quality-gates` step 17 and
  a local `gate_surface --check`.
- **Finding 45's stale C16 docstring** at `verify_claims.py:2406-2408`. **Its recorded reason for
  not being edited is measurably wrong:** the whole-table probe shows the 18 pins anchor to
  CLAUDE.md (9), ADR-055 (8) and `docs/state/CURRENT.md` (1) — **no pin anchors to
  `verify_claims.py`**, so `doc_truth` does not read it.
- **Finding 53** — `security.yml:98`'s second I-1 deny-list omits `replicate` and its job is
  declared ineligible as path-filtered. Adding `replicate` there is a separate cause.
- **`workflow_shape_truth` cannot see an unguarded pipeline** (finding 35).
- **CI's ruff scope** excludes nine trees: 530 lint, 254 format (upper bound).
- **Conflict O — CF-13's enforcement scope.** 41 files, 56 sites, none inside the checked inventory.
- **`scipy` is pinned in NO requirements file** and arrives transitively (finding 41).

### STEP 4 — how a session is actually run

**Waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit.
2. **Write findings into `tasks.md` and the ledger as you find them.**
3. **Delegate reading, never execution.** Unlimited parallel sub-agents for reading, writing and
   analysis; **exactly ONE** that executes code. Keep every command in the main agent.
   **G7 makes this a DEFAULT rather than an option: any wave with two or more independent units
   dispatches two or more authoring agents, and working serially requires a stated reason in your
   opening.** "Agents dispatched" is one of the four numbers you report, and a zero without a
   reason is a defect in method. **G7 does not touch the one-executor cap, does not move any
   workload's routing, and does not make the metric anything other than DISCHARGE** — an agent
   dispatched to raise a count produces nothing, so report what each one produced.
   **And use the whole tool surface**, not the two tools nearest to hand: code intelligence,
   symbol and reference lookup, and research powers have gone unused while sessions defaulted to
   shell and text search. Finding 48 cost a CI run because a consumer was found by grep instead
   of by asking what *translates* a value.
4. **Re-read the authority file for each wave's area before starting it.**

**Spend `gh` reads first.** Free under I-0 and the highest-yield evidence in this repo. Session 5's
payoff was one `gh` read of a job that had never run; session 6's was one read of that job's log;
session 7's was two labelled runs and one `truth-gates` step list.

**WRITE YOUR PREDICTIONS DOWN BEFORE YOU MEASURE.** Session 7's five pre-registered predictions are
the only reason a negative regret was legible as a defect rather than as a number to interpret. A
prediction recorded after the number arrives is not a prediction.

#### FORBIDDEN REPAIRS. Each names what it would destroy.

No error may be cleared by **giving an argument a default**, by **widening a type to `Any`**, by
**adding a `# type: ignore`**, by **narrowing a checker's scope**, by **lowering a floor**, or by
**adding `continue-on-error`**. **And no refusal path added to make a defect loud may be removed to
make a gate green** — that is session 7's addition to this list. If an error is genuinely a tooling
artifact, repair the *declaration that misleads the checker*, never the call sites that report it.

#### Determine ownership mechanically, and `git log -1` is NOT enough

```powershell
git cat-file -e origin/main:<file>              # exit 0 => exists on main
git diff origin/main -- <file>                  # attribute the LINE, not the file
git merge-base --is-ancestor <sha> origin/main  # exit 1 => this branch's
```

**And for lint or format debt, materialise the blob and re-run the checker** — that is how sessions
5, 6 and 7 each proved they added none. Write the blob from Python with `write_bytes`; PowerShell's
`>` writes UTF-16 and `Set-Content -Encoding utf8` adds a BOM.

---

## STOP CONDITIONS

- **Stop at any barrier the census names that the batch depends on.** Say which.
- **Stop and report if a count does not move as predicted.** State the delta **per code** and what
  you checked.
- **Do not tick 11, 14, 21, 22.3, 25 or 26.5** without the naming job's own verdict.
- **Do not author task 12 or 13** until task 11's disposition has landed. They empty the insensitive
  set and turn finding 54 into a false confirmation.
- **Do not remove or weaken `negative_regret_refusal`** to make `twin-regret` green. Its red is the
  finding.
- **`pin_extractor_truth` reports 15 declared today — DERIVE IT, do not read it:**
  `python -m scripts.audit.pin_extractor_truth --check`. It becomes **17** when task 26.5 graduates
  the two parked `s`/`S` pins. The fourth parked row, `mutation-fast-required-job`, stays parked and
  would FAIL if activated. **Assert `declared == len(pins:)` read from the file, never against a
  transcribed integer** — that is conflict P's durable repair.
- **Do not change `main`.**
- **Do not run `ledger_gen` or `readme_gen`** locally, in `--check` or `--write` form, for any
  reason — **and that includes `tests/verify/test_ledger_gen_property.py`.**
- **Do not pad a session toward thirty**, and do not read a small census delta as a small session.
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
| **7** | **the slow step's Pinecone failure** | **CLEARED.** `paid_client_attempts == []` passes at `4539b91` — the guard is confirmed |
| **8** | **`truth-gates.yml` steps 6–12** | **NEVER EXECUTED HERE** — skipped behind the C44/C69 red (finding 51) |
| **9** | **`uplift-verify` step 5, the fast surface** | **CLEARED.** Went red at `446d5d5` on session 7's own property; repaired, `success` |
| **10** | **the SAME test's next assertion** | **NEW.** `data_file_reads` false-positives on a dependency's bundled `.csv` (finding 57) |

## HARD-WON LESSONS. Fifty-seven findings and seventeen conflicts, each one paid for.

### The habits that caught the most

1. **Write predictions down before measuring, and make them falsifiable.** Session 7's five
   predictions turned an unexpected number into a diagnosed defect in one run. Prediction 1 was
   confirmed to sixteen significant figures, which is what proved adding a third arm perturbed
   neither of the other two.
2. **A guard built from two expressions that share a term cannot constrain that term.**
   `headroom >= regret` reduces to `A >= B`; the oracle cancels. **Ask what a guard reduces to
   algebraically before trusting what it appears to check.**
3. **A citation is not a mechanism.** Finding 50 named a construction site read off a *comment
   describing an intent*. That line constructs nothing; the real site was two modules away behind a
   lazy import. **Walk to the constructor.**
4. **A document edit's blast radius is every pin anchored to that document.** Eight of fifteen pins
   anchor to ADR-055. Probing only the pin you are adding is finding 48 in a new place — session 7's
   own amendment gave a *sibling* pin a second matching line, which is as fatal as none.
5. **Check your own instrument before you trust its verdict.** The anchor probe was run against the
   *unamended* document first, where it correctly reported zero matches.
6. **Read what got SKIPPED behind a failure, not only what failed.** One pre-existing red at
   `truth-gates` step 5 was hiding the execution status of **seven** gates. One 101-character line
   once gated 18 steps and 3 jobs.
7. **Read the LOG, not the summary, and read the OTHER workflows for the same sha.**
8. **Exclude mechanisms explicitly, and say which.** Session 7 excluded three candidate causes
   before accepting a fourth, and recorded each exclusion with its evidence — that is what makes the
   survivor a hypothesis rather than a guess. **And it labelled the survivor a hypothesis with a
   named falsifier, because the decomposition was not measured.**
9. **Verify what you already had, not only what you touched.** Task 26.1's discharge had arrived two
   sessions earlier and nobody had claimed it.
10. **Consensus across documents is not evidence.** Four documents named the wrong construction
    site; four had named `Par_Level_Reorder` unlanded; the steering file says CF-13 has three
    violations and it has 56.

### On verdicts and assertions that cannot move

- **A number that cannot fail is not a number; a verdict that cannot be anything else is not a
  verdict; and a regret measured against a comparator that loses to its own subject is neither.**
- **A false stop is recoverable; a false confirmation is not.** Conflict M's defect forced
  `material`, which stops the spec loudly. Finding 54's would have returned `sub-margin`, which
  confirms the premise quietly. **Rank your failure modes by which one nobody would notice.**
- **A tautology dressed as an assertion is the same defect.** Check whether your new assertion can
  fail before writing it. Session 7's Property 61 asserts the *hole* it closes, not just its own
  condition.
- **Prove a refusal path by construction.** `_measure` drives the twin and cannot run in the fast
  suite, so the refusal decision was extracted into a module-level pure function that a fast
  property can exercise.
- **Repair a stale assertion by PARTITIONING, not FILTERING**, and **assert non-emptiness**.
- **A precondition correction is not an assertion weakening**, and the test of which one you have is
  whether the standard got *stricter*. Session 7's replacement admits exactly one value the rule
  must re-derive, where the old one admitted exactly `None`.
- **Never weaken a generator, an assertion or a floor to make something pass** (R2.10).

### On gates reporting the wrong thing

- **A required check that can only report `skipped` is not a gate.**
- **`set -o pipefail` in any `run:` that pipes a gate** — proven by a REAL failure in session 7:
  without it, run 2's `| tee` would have reported **success** with a refusal inside the artifact.
- **A deny-list is fail-open by construction — BUT check what the invariant actually says before
  widening one.** `CLAUDE.md` states I-1 as a closed list of four names and `ci.yml` greps exactly
  those four, so that gate is a faithful projection, not an incomplete list. **And ADR-018
  (Accepted) sanctions Pinecone for its free tier.** Widening the list would have installed a false
  positive on a required check and blinded 13 steps.
- **A text grep cannot express "is a client constructed on this path?"** Both sites are guarded lazy
  imports and a grep matches the line regardless of the guard. **When a gate's predicate is wrong,
  widening its scope makes it more wrong.**
- **Two independent clauses in one gate can silently become one.**
- **A declaration that cannot go stale is a mute button.**
- **`UNAVAILABLE` from a floor with no measurement is the gate working, not failing.**
- **A verdict is a claim about its own derivation.** `Select-Object -First N` makes a passing gate
  report non-zero; a splatting bug made a gate exit 2 when it is 0.
- **A local red is not always a CI red, and a local green is not a CI green.**

### On scope, ownership, adoption and closures

- **CI's scope is not the tree's scope, and the gap is measured.** `ruff` covers
  `packages/synapse_common/ agents/ orchestrator/` **only**.
- **Attribute lint debt by materialising the committed blob and re-running the checker.**
- **Necessary is not sufficient.** Ask what else gates the thing you are trying to reach.
- **Do not adopt another owner's debt unilaterally**, but record the diagnosis. Three adoptions so
  far, each by explicit operator decision — and session 7 **declined** a fourth on the strength of
  an Accepted ADR, which is the first time an instruction was refused rather than deferred.
- **One diff, one cause.**
- **Read the install closure before trusting a job can run its own subject.**
- **A workflow that has never executed is the I-7 shape, and *reachable* is not *run*** — and *run*
  is not *finished*.

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open. An open leaf carrying a `discharge:` line is **CI-gated** and is not authorable. |
| `[~]` | **authored, discharge pending.** On disk; proof owed by the job in its `discharge:` line. **Not a pass.** |
| `[x]` | done **and** discharged |

- **A `[~]` graduates on the job's own verdict, never on a local run.**
- **A `discharge:` line can name TWO subjects**, and both must report — task 26.1's had been
  satisfied for two sessions before anyone checked.
- **A job's colour is not the task's verdict.** Run 2 is RED and discharged task 10.4.
- **"Authored and diagnostics-clean, not executed" is a legitimate result.** A **deselected** test
  is not a pass either.
- **Disk outranks the ledger.** **`tasks.meta.json` is not authority.**

---

## I-0 — the rule most likely to burn the machine

16 GB laptop, RTX 3050, thermally throttling. **Process type and process count** are what throttle
it.

- **Never run:** dev servers, watchers (`vitest` at all), browsers/Playwright, `docker compose up`,
  anything binding a port; fan-out execution (`-n auto`, `-j`, repo-wide bare `pytest`, `--cov`,
  `mutmut`); any `MIN_SCENARIOS`-scale or training workload.
- **Never run, specific to this spec:** `scripts.audit.verify_claims`, `scripts.audit.doc_truth`,
  bare `readme_gen --check`, **`ledger_gen --check` or `--write`**, `gate_fault_injection --sweep`,
  `pnpm` anything — **and `tests/verify/test_ledger_gen_property.py`.**
- **Cheap and encouraged:** file reads, `grep`, `get_diagnostics`; `ruff`/`mypy` on changed files;
  bounded scoped `pytest`; `spec_ledger_census`; the **six** cheap gates; `command_path_truth` and
  `ratchet_truth` over the committed tree; `replay_metrics` through its `measurers` seam;
  **`doc_truth.documented_value` and `extract_source_values` as pure functions** — session 7's
  whole-table anchor probe is built from exactly those two and it caught a real defect; and **`gh`
  API reads — free, and the highest-yield evidence in this repo. Spend them first.**
- **`mypy --strict` over `tests/verify` or `tests/uplift` modules EXCEEDS a 120s command budget.**
  Type-check changed **non-test** modules by dotted name and say plainly that the test modules were
  not checked. **No CI step type-checks `tests/`.** Mixing `scripts/audit/*.py` and `tests/**` in
  one invocation fails instantly with "Source file found twice".
- **Concurrency is the load-bearing half.** Parallel sub-agents for reading, writing and analysis:
  **unlimited.** Sub-agents that execute code: **exactly ONE at a time.**
- **Preferred flags:** `-q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
- **Count and report your real invocation count.** Session 5 used nine, session 6 five, session 7
  **two**. **The bound is on scope and serialisation; the honesty obligation is on the count.**
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
python -m scripts.audit.dataset_licence_truth --check     # C74   expect 2 = honest SKIP
python -m scripts.audit.task_claim_truth --check          # expect 1 = pre-existing, other spec
python -m scripts.audit.gate_surface --check              # C63   expect 0
python -m scripts.audit.spec_ledger_census --files --check # expect 0
```

Expected: **`0 / 0 / 0 / 2 / 1 / 0`** plus census 0. **Append `*> $null` and read
`$LASTEXITCODE`** — piping any of these through `Select-Object -First N` manufactures a non-zero
exit.

**And probe every pin anchored to any document you edited**, on both sides, before committing.
`doc_truth.documented_value` requires **exactly one** matching line; zero and two are equally fatal,
and `pin_extractor_truth` reports green through a document-side failure.

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **`Select-Object -First N` on a native command makes `$LASTEXITCODE` non-zero.**
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated.** Assign, then `foreach`.
- **Complex inline `python -c` breaks on quoting.** There are no heredocs. Write a temp `.py` under
  `.tmp/` (git-ignored), run it, delete it. Session 7 lost a call to a nested-quote `SyntaxError`.
- **An editor writing LF into a CRLF worktree file leaves `w/mixed`.** Ninth consecutive session.
  Normalise to the file's **dominant WORKTREE** ending from Python at `newline=''` — the `i/` column
  is normalised and cannot tell you what is on disk (finding 33).
- **`ruff`'s `SIM300` reads an upper-case attribute as a constant**, and **`N802` rejects an
  upper-case word in a test name** — fix the name, never add a `noqa`.
- **`git push` writes progress to stderr**, so `$LASTEXITCODE` is non-zero on a **successful** push.
  Read the `old..new ref` line.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental` after any
  config change.
- **`git log -1 -- <file>` is last-touch, not authorship.**
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 in this repo.** `>` writes UTF-16.
  `Copy-Item` is a byte copy and is safe. **Verify bytes, never the console** — a `python -c` print
  of a file containing an em dash shows `?` on this console and the file is fine.
- **`git status` over-reports.** Trust `git diff`, stage precisely, `git check-ignore -v` first.
- **Identify a CI run by `head_sha`, NEVER by timestamp.**
- **`git commit -F` a temp file** for any message longer than a line.
- **`gh run download <id> -n <name> -D <dir>`** beats parsing a `| tee`'d log for an artifact.
- **Adding a label fires every workflow with a `labeled` trigger.** Each job's `if:` decides whether
  anything runs; `regenerate-truth-docs.yml` correctly produced a zero-cost skipped run on the
  `measure-twin-regret` label, twice. **Remove the label after use.**
- **Do not run `pre-commit install`.**
- Python 3.14.0, **mypy 1.19.1**, pytest 8.4.2, hypothesis 6.151.11, jsonschema 4.26.0.
  `gymnasium` absent. `gh` 2.82.0, authenticated. **Repository is PUBLIC — Actions minutes are
  unmetered on standard runners.**

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). **Do not assert a total** (CF-13). Note conflict
  O: the rule is enforced over a scope containing none of its 56 violations.
- **`-m "slow"` is a selector, not a path filter.** `ci.yml::uplift-verify`'s slow step collects
  `tests/uplift`, `tests/verify`, `orchestrator/tests/consensus`, `digital_twin/tests`; its
  fast step only `tests/uplift tests/verify`. **A slow-marked test outside those four paths is selected by no
  job at all.**
- **No `DECLARED_INVENTORY` entry is owed for a new property in this spec**, and this was checked:
  that table covers properties **1–37**, and this spec's own surface (44–54, 60, 61) already sits
  outside it — conflict O's measured scope gap.
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
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS, and
  a **deselected** test is not a pass.

### The five same-commit couplings

1. A rename and its declaration.
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the job
   is genuinely eligible** (conflict G).
3. A schema change and every fixture that carries it — **including whatever TRANSLATES the value**,
   which is what finding 48 cost a CI run to learn.
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** **Check it rather than assume it** — it has
   fired on a `needs:` removal and not fired on a `run:`-only edit whose step name did not change.
5. The session ceiling lives in **one** place, `spec_ledger_census.DEFAULT_BATCH`.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** One commit **per wave**.
- Prefer new commits over `--amend`. No force-push, no `--no-verify`, no interactive flags.
  Leave git config unchanged. **Push to the PR #84 branch, never to `main`.**

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

**Session 7 is the clearest demonstration yet of why that design matters, and it is the second time
the same instrument has been caught pointing at the wrong quantity.** Session 4 found the
comparator measuring a no-op and reporting it as the `(s, S)` regret. Session 5 repaired that with a
third arm. Session 7 measured the repaired instrument and found the *oracle* invalid — a defect the
session-5 guard was structurally incapable of detecting, because it reduces to a claim in which the
oracle cancels. **An instrument that can end the project is only safe if you keep asking what its
guard reduces to.**

**The pre-commitment, binding before the number is known:** if measured uplift is null or negative,
**it is reported as null or negative.** The floor stays at `0.0`, no headline is published as a
gain, and the result is written up as a finding — not reframed, not re-run at a different replicate
count until it moves.

Three guards on reading the result: a null while any objective KPI is recorded not observably
sensitive is **inconclusive**, not confirmation (task 10.5). No headline may be published while no
Power_Report describes the harness revision under measurement (task 17.3). And **a `material`
verdict on a point estimate with no dispersion is not a falsification** — nor is one on a comparator
the requirement does not name (conflict M), **nor is any verdict at all on a comparator that loses
to its own subject (finding 54).**

---

## Session 8 handoff — the throughput reset, installed and untested

**Five commits. ZERO leaves discharged, and that is reported rather than explained away: this
session wrote the rules it will be judged by.** Census unchanged at `142/66/0/76`.

| Commit | Subject |
|---|---|
| `e02c1c2` | task 11(a): the per-term decomposition — finding 54's falsifier |
| `3bcea22` | steering: the throughput reset — measured hardware, an allow-list |
| `5ef7a67` | **finding 59** — the decomposition answers task 11; two defects, not one |
| `b61941b` | census: `[~]` harvest mechanical, ceiling 30 → 40 honestly |
| *(fifth)* | `HANDOFF.md`, this prompt, the progress-ledger row |

**What was measured.** `RegretObjective.contributions()` wired into `_measure` at last (**finding
58** — the capability existed since task 9 and no run called it, which is the only reason finding
54's cause was a hypothesis). The result, canonical in **ADR-055 D2.5.3**: `stockout_rate`
dominates at **0.808** as hypothesised, but `stockout_rate` and `unmet_service` are the **same
number** at weight `8.0` each, and the oracle leaves **8.2%** of demand unmet against the
incumbent's zero. Removing the double-count leaves regret at **−0.1559, still negative**, so
**option (b) is the repair** and option (c) alone is insufficient.

**What was installed.** Three steering documents. The routing **allow-list** over all 35 audit
gates with `cores × wall-seconds` as the metric; the six guardrails with **discharge** as the
throughput unit; and I-0 corrected on hardware (**15.71 GB**, not 14 and not 16) with parallel
authoring moved from *permitted* to **required** — the one-executor cap and both incident records
untouched and verbatim. `spec_ledger_census` now **fails** on a `[~]` lacking a `last-checked:`
run, proven by construction in Property 63 because the tree has `pending: 0` and nothing would
exercise it.

**Two footguns now recorded, both measured.** `HYPOTHESIS_PROFILE` unset loads **500** examples —
a 50× local load one forgotten export away. And `testpaths` omits `digital_twin` while
`uplift-verify` collects it, so a bare `pytest` and CI disagree about what the suite is.

**NOT verified:** `uplift-verify` at any of the five commits — three runs were in flight at close,
and **Properties 62 and 63 are new and run in the fast step at 500 examples**; finding 57's status;
the job split, which is specified above and not landed; and `vitest`, at all.

**The lesson, and it is the same shape twice.** `contributions()` could decompose a cost for eight
sessions and no run called it. I-0 permitted unlimited parallel authoring agents for eight sessions
and sessions used zero. **Capability is not use** — and the reset's largest change is not a new
permission but turning an unused one into an obligation.

**Six commits. Two leaves ticked, two registered. Census `140/64/2/74` -> `142/66/0/76`, and
`pending: 0` for the first time in this spec's life.**

| Commit | Subject |
|---|---|
| `e94a1ac` | an unclaimed discharge, three findings, and checkpoint A pre-registered |
| `2d86899` | the margin lands, and the oracle turns out not to bound its subject |
| `827ffc0` | 10.4 discharged on run 2's own verdict; task 11 deliberately not |
| `446d5d5` | I-1: guard the construction, and do NOT widen the deny-list |
| `daeb972` | the session ledger: findings 51-55, conflicts P and Q, two leaves registered |
| `4539b91` | fix(Property 61): an algebraic identity is not a floating-point identity |

**What was earned.** Checkpoint A ran, twice, by label. The materiality margin is committed,
re-derived from its pre-registered rule and accepted by the headroom guard on the job's own run
(`margin_committed: 0.4`). Task 10.4 is `[x]` after four sessions as `[~]`. Task 26.1 is `[x]` on a
discharge that had been sitting unclaimed for two sessions.

**What was learned, and it is the largest single finding in this spec's life.** The regret is
**negative**: the arm labelled `perfect_foresight` costs more than the incumbent it is supposed to
bound, over 200 of 200 replicates with an interval excluding zero. Three mechanisms were excluded
before a fourth was accepted as a hypothesis with a named falsifier. The session-5 guard could not
have caught it, because `headroom >= regret` reduces to `A >= B` and the oracle cancels. And with
E2c's two sensitivity flips landed, that same number would have returned **`sub-margin`** — the one
verdict that **confirms** Finding 4.

**What was declined, and it is the first time an instruction was refused rather than deferred.**
Widening the I-1 deny-list to `pinecone`: `CLAUDE.md` states I-1 as a closed list of four and
ADR-018 (Accepted) sanctions Pinecone's free tier, so the widened gate would have reported a
violation that does not exist, on a required check, blinding 13 steps. The construction guard was
landed instead and verified behaviourally in both directions.

**What is owed.** Task 11's disposition (three options, the cheapest being the per-term
decomposition that falsifies or confirms the `stockout_rate` hypothesis); E2c, blocked behind it;
tasks 26.4 and 26.5; finding 45's stale docstring; finding 53's second deny-list;
`workflow_shape_truth`'s pipeline blindness; CI's ruff scope; conflict O; `scipy`.

**NOT verified, and must not be claimed:** that `uplift-verify`'s slow step now passes — the guard
is landed and **CI owns that verdict; at `446d5d5` step 6 was skipped behind finding 56's
fast-step failure, so STEP 0 must read BOTH steps of `4539b91`'s run**; task 11's verdict, which
was refused rather than measured; any arm's per-term cost decomposition; that
`Par_Level_Reorder(s=50, S=100)` reproduces the twin's endogenous restock; `mypy --strict` on any
test module; `quality-gates` at `daeb972` or `4539b91` (**measured `success` at 26 of 26 at
`446d5d5`**, the commit carrying the guard); and `vitest`, at all.

**One more lesson, and it is session 7's cheapest.** `heavy` or `ci` failed what `dev` passed for
the third session running — and a scoped pure-arithmetic file at the `ci` profile's 500 examples
costs about **five seconds**. **Verify at the budget that will judge you**, for the files where a
generator can reach a subnormal.
