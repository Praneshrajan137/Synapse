# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **11** (2026-09-29 to 2026-10-12).

**This prompt states no HEAD, deliberately.** It is written *before* the commit that carries it, so
any sha it named as "the newest" would be stale by construction (conflicts J and K). STEP 0 derives
it. The shas below are evidence for recorded facts, never the state to start from.

**And it carries no count a command can derive.** Where a number appears, the command that derives
it is beside it (conflict P).

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`. **The repository is PUBLIC** (since 2026-10-02): standard runners are 4-vCPU and
Actions minutes are unmetered, so `execution-routing.md`'s premise holds again.

**Your session cap is FORTY leaf tasks, in waves of about ten. It is a ceiling and it is expected
never to bind.** What stops you is a barrier or a phase boundary.

### STEP 0 — DERIVE THE STATE, THEN READ THE RUNS AT THE NEWEST HEAD

The newest head is session 11's documents push (**P2**) or anything after it. **P1** (`ba02a1b`),
planned as ONE confirmation push, became three: it discovered a Node-engine refusal, repaired in
**P1b** `5c2f2b3` (finding 93), and a latent harness race, repaired in **P1c** `0745290` (finding
94). P1c's run (`38293903740`) read as items 3 and 5 below.

```powershell
git rev-parse --short HEAD
git rev-list --count origin/main..HEAD
gh run list --branch feat/decision-quality-proof --limit 20 --json databaseId,headSha,workflowName,conclusion
```

**Two workflows are path-filtered, but on `pull_request` the filter reads the PR's WHOLE diff
against `main`**, so `frontend.yml` (`frontend/**`, `proto/domain/**`, the workflow file) and
`mutation.yml` (its mutation-target paths) run on **every** push to PR #84, documents-only ones
included — Frontend CI ran on the documents-only `5eef6ee`. And wherever a workflow declares
`cancel-in-progress` (P1 extends it to `ci`, `frontend`, `integration` and `mutation`), a newer
pull-request push cancels the older head's in-progress run — P1c's push cancelled `5c2f2b3`'s
Frontend CI after its verdicts had been read. **A `cancelled` verdict is no verdict, so never push
while a run you need is in flight.**

Then read each run's **step list**, not its colour:

```powershell
$j = gh api "repos/:owner/:repo/actions/runs/<id>/jobs" --paginate | ConvertFrom-Json
foreach ($job in $j.jobs) { "{0} | {1} | steps={2}" -f $job.name, $job.conclusion, $job.steps.Count }
foreach ($job in $j.jobs) { foreach ($s in $job.steps) { "{0,3} {1,-12} {2}" -f $s.number, $s.conclusion, $s.name } }
```

**`foreach`, not a pipeline** — PowerShell 5.1's `ConvertFrom-Json` hands back the array
unenumerated. **Then read the LOG, filtered, never dumped:**

```powershell
$log = gh api "repos/:owner/:repo/actions/jobs/<jobid>/logs" 2>$null
($log | Select-String -Pattern "FAILED|Falsifying example|passed|Summary:|falsified|indeterminate").Line
```

**What to read, in priority order:**

1. **Every `required:` job.** `infrastructure/quality/required-checks.yaml` names them; they live
   in `truth-gates.yml`, `ci.yml` and `integration.yml`. CI and Truth Gates read `success` at both
   `ba02a1b` and `5c2f2b3`; Integration, Mutation, Security (at `5c2f2b3`), Policy and Terraform
   `success`. At `5eef6ee`: `quality-gates` `success` (958 s under its 25-minute bound),
   `uplift-verify` aggregate `success`, truth-gates registry `57 PASS / 0 FAIL / 10 SKIP`. **A
   regression in a required check outranks everything below.**
2. **`falsification-sweep`** — required, and at `5eef6ee` it could not exit 0 on any tree (task 6,
   finding 81): 16/16 probed, 12 falsified, 4 indeterminate. P1's R1.5a amendment **PASSED** on
   Truth Gates run `38287788451` (`ba02a1b`, task 29.7): 16/16 operators probed, all 14 checks
   falsified, 0 unproven, with C60, C70, C71 and C72 admitted as SKIP baselines (exit 2) that FAIL
   under mutation. **One pre-registered prediction MISSED:** C69's probe has mutated exit 2, so it
   counts as falsified on an abstention — finding 85, now measured; its repair is C69's declared
   operator, the owner's decision (b). Read the probe table, not the colour.
3. **The frontend, on Frontend CI run `38291036628` (`5c2f2b3`):** `e2e` 21 passed, 0 failed, 8
   skipped (19/1/8 at `5eef6ee`); `audit-supply` `success`, the maplibre critical cleared, and
   `map-worker.spec.ts` — the observable finding 83 said no check had — passed; `mobile-reality`
   "/" LCP 2292 ms, CLS 0, INP 112 ms, passed on **ONE** sample, and the entry-preload guard passed
   with exactly the five predicted eager chunks (finding 86); quality, build, visual, lighthouse,
   license, SBOM, spec-typecheck and contract-fidelity `success`. **`e2e-harness` failed there**
   (finding 94); after P1c's repair it reads **`success` (run `38293903740`)**. Stryker **`success` (28.4 min)**.
4. **Harvest every `[~]` (G4).** For each one the census names, read its discharge job and write a
   `last-checked:` line. The census is non-passing until you do, and **checking without writing it
   down does not satisfy it.**
5. **`effectiveness-ratchet` is red BY DESIGN** (finding 88): at `0745290` it reads **`failure`, on exactly the R8.10 rejection read at `5eef6ee`**.
   **`fe-invariants` ran for the first time and FAILED: the six declared-unobservable invariants, plus six top-level e2e specs that a path-matching defect reads as never executed (finding 90).** Do not
   commit a measured baseline or widen the ratchet's tolerance to turn it green — that is open
   decision (a).

### STEP 0a — THE METRIC

**Read the four steering files first; they are `inclusion: always`:**
`.kiro/steering/local-compute-budget.md` (I-0), `.kiro/steering/execution-routing.md`,
`.kiro/steering/throughput-with-integrity.md` (**the metric and G1–G7**) and
`.kiro/steering/standard-of-work.md`.

**Leaves DISCHARGED. A `[~]` counts ZERO. Target: >= 11** (G6). Session 11 discharged **14**.

**Reconcile the ledger against disk BEFORE deriving a batch** — `--next 40` offers work that is
already done and the census cannot tell you which (sessions 1 and 9). **Authoring without recording
scores zero and is indistinguishable from not authoring.**

### STEP 0b — WHAT BINDS BEFORE ANY AUTHORING

1. **Checkpoint B-prime PASSED** (ADR-055 **D2.9**, task 14): E3 and E5 are licensed by
   measurement. Do not re-run it, and do not re-open conflict R — R5.45 superseded it.
2. **No claim may be denominated against the incumbent arm.** The honest baseline is the tuned
   control **E**, re-derived per cell by task 13.7's committed search; task 25's re-scope names E
   of the primary cell. **17.2 and 25 sit under this prohibition** (ADR-055 D2.7).
3. **A `deferred:` leaf is terminal** (task 29.1). Never author one; its line is a decision, not a
   TODO.
4. **Decision 1=a binds every claim:** world values are `chosen`, fidelity is `unknown`, and C60 is
   `unavailable` by decision — which is why 17.5, 17.6, 17.9 and 22.3 are deferred (finding 71).
   **Nothing may claim C60 proven.**
5. **Finding 79 is owed before E3 cites arm D as a bound** — open decision (d).

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/steering/execution-routing.md` — **where** a workload runs, by table not by judgement.
3. `.kiro/steering/throughput-with-integrity.md` — **the metric** and **G1–G7**.
4. `.kiro/steering/standard-of-work.md` — the reviewer bar and the methodology at its **measured**
   level. Read it before claiming a practice or a standard.
5. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the ceiling, waves, the **barrier
   stop**, the three marks, the batch table, the cheap gates, the progress ledger. **Read rows 10
   and 11 in full.**
6. `HANDOFF.md` (repo root) — state, pointers, the **open operator decisions** and the honesty
   ledger. Read its NOT-verified list before believing any colour.
7. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
   **I-1's paid-client list is CLOSED at four names.**
8. `.claude/skills/synapse-engineer/SKILL.md` + `references/`; then `.cursorrules` +
   `docs/cursor/*.md`.
9. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.8** (the re-cut's design) and **D2.9**
   (B-prime, measured) first; D2.7 and D6 behind them. **Probe every pin anchored to it, on both
   sides, if you amend it** — derive the set with
   `git grep -n "document: docs/adr/ADR-055" -- infrastructure/quality/doc-number-pins.yaml`
   (eight at session 11's close, two of them parked).
10. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. **R5.45/R5.46** carry the
    re-cut; `tasks.md` is the ledger and your worklist.

**Two invariant numberings disagree** (`references/14_invariants.md` vs `.cursorrules` on I-6, I-8,
I-10); authority 5 outranks 6, and I-1, I-4, I-5, I-7 agree in both. **When two sources conflict,
surface it; never resolve it silently.** Eighteen have been surfaced (A–R).

### STEP 2 — reconcile, derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

**The authorable list at session 11's close** — re-derive it, never copy it:

> `15.1`, `15.2`, `15.4`, `15.5`, `15.6`, `16.2`, `16.4`, `16.5`, `16.6`, `16.7`, `17.1`, `17.2`,
> `17.3`, `17.4`, `19.4`, `22.1`, `22.2`, `24.1`, `24.2`, `29.4`, `29.5`, `29.6`.

**Beside it, P1's findings owe work that is no leaf:** **92**, a failed-chunk state for the 14
lazy routes, owed **before PR #84 merges**; **91**, a smoke a11y matrix that has only ever scanned
`/login`; **90**, `fe-invariants`' six unobservable invariants and the path-matching defect that
misreads six top-level e2e specs as never executed (both the owner's); **93's tail**, Node 20 (EOL) still pinned in
`ci.yml::chromatic-color-gates` and `infrastructure/oracle/setup_oracle_vm.sh`, where Node 24 LTS
is the longer-lived line; and forbidding `viz-`/`visx-` in `check-entry-preloads.mjs` now that a CI
table shows them absent, which lets FE-INV-025 name `build` as its enforcer.

**Two CI-gated barriers: `25` (`uplift.yml::uplift-proof`) and `26.5`
(`regenerate-truth-docs.yml::regenerate`)**, and 29.4–29.6 sit after both in ledger order. **The
reading to confirm, not to adopt (inferred from the task bodies):** the batch does not depend on
either — 22.1, 22.2 and 29.4–29.6 are *inputs* to 25's run, and 24.2's regeneration is itself a
labelled `regenerate-truth-docs` run, so one dispatch after 24.1 lands may serve 24.2 and 26.5
together. **State your answer to every barrier line in your opening; an unanswered barrier is a
stop.**

**`$LASTEXITCODE` lies if you pipe the census through `Select-Object -First N`.** Re-run with
`*> $null`.

### STEP 3 — what to do, in priority order

#### A. E3's schema half and the objective headline — one coupling closure

15.1, 15.2, 15.4, 15.5, 15.6, 29.4 and 29.5 all touch or test `uplift/harness.py` (with
`uplift/interval.py`, `uplift/cli.py`, `uplift/contract.py` and `uplift/metric_contract.yaml`).
**One agent owns the closure** (G2).

- **15.1's blast radius was measured in session 10** (its task body): no committed fixture carries
  an artifact payload, so its "every committed artifact fixture" is an **empty set** — do not
  manufacture one. The translator `PoweredProof.from_payload` **silently ignores** new keys.
- **29.4 makes the committed objective the sole primary KPI** (decision 2=a, finding 64); 29.5 is
  Property 94. **15.5 makes the comparator explicit; under STEP 0b's prohibition, the one a claim
  names is E, never the incumbent.**

#### B. The information pathway — 29.6

Decisions 3=a and Q2=a, finding 68: `uplift/consensus_arm.py` + `uplift/harness.py`, with a
`@pytest.mark.slow` probe (Property 95) that is **CI-only**. It shares `harness.py` with A, so
**give it to A's agent or sequence it after A.**

#### C. The controls — 16.2, 16.4, 16.5, 16.6, then 16.7

16.2's committed values, `uplift/controls.py` and its two properties, then 16.7's `uplift-controls`
job with its declarations **in one commit** (couplings 2 and 4). **16.2 is smaller than its body
claims:** `ratchets.json` already carries both negative-control entries.

#### D. The Power_Report — 17.1, 17.2, 17.3, 17.4

`uplift/power.py`, `uplift/uplift_floor.py`, `scripts/audit/uplift_truth.py` and their tests.
**17.2 may not be authored against the incumbent arm.**

#### E. The job and the registrations — 22.1, 22.2, 19.4, 24.1, then 24.2

22.1 builds `uplift-proof` as a labelled, attributable, sharded matrix (findings 70, 74); 22.2
declares it; 24.1 registers C76 `benchmark_truth` — **which is 19.4's owed `@register`, one
obligation seen from two leaves** (19.4's body) — and 19.4 also owes a workflow locus that invokes
it. **Registration and regeneration land in the SAME session** (finding 73), and **24.2's
`--write` is CI-only** — `ledger_gen` and `readme_gen` are never local. 16.7 and 22.1 both edit
`uplift.yml`; 16.7, 19.4, 22.2 and 24.1 all edit `required-checks.yaml` or `blocking-steps.yaml` —
**one closure, one agent**, with `gate_surface --write` in the same commit.

#### F. Then E5 — task 25 — is a labelled CI run, never a local one

`518.6` core-hours projected (D2.9): fundable now, **not runnable until A–E land.** Size it from
the cost probe and escalate to the GCP window (ADR-036) rather than cut replicates below
`INV-TW-002`.

### THE OPEN OPERATOR DECISIONS — name them in your opening; do not resolve them

`HANDOFF.md` carries one line each. **(a)** the effectiveness ratchet's tolerance against its
measured noise (finding 88) — the next measurement is a strict A/A, re-running `e2e-harness` once
on one sha; **(b)** the sweep's PASS-baseline branch credits an abstention or a crash — C69 is the
measured case, and its operator could re-tick a record instead (finding 85); **(c)** the deployed
console signs every visitor in as admin and its default credential ships in the public bundle
(finding 89) — **live exposure, so raise it first**; **(d)** arm D's "pointwise best" claim, owed
before E3 cites D (finding 79); **(e)** the Lighthouse LCP assertion is `warn`, and with
`mobile-reality`'s LCP passing at 2292 ms on one sample, flipping it to `error` is cheaper
(finding 86).

### STEP 4 — how a session is actually run

**Waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit.
2. **Write findings into `tasks.md` AS YOU FIND THEM**, in the task body that owns them.
3. **Parallel authoring is the DEFAULT (G7); exactly ONE agent executes (G1).** This batch
   partitions by coupling closure (G2) into four disjoint file sets: **A + B** (`harness.py`),
   **C** (controls, minus 16.7's job), **D** (Power_Report), **E + 16.7** (workflows and
   declarations). Working serially requires a stated reason.
   **Every contract's FIRST line is the no-execute clause** (G3), then: files it may and may not
   touch, the one canonical location for its findings, and the couplings it owns. **Verify every
   agent's writes independently of its report** — a silent agent is not a no-op agent. **Session
   11 lost six to eight dispatches to usage limits:** size each contract so a lost agent costs one
   closure, not a wave. **Report what each agent PRODUCED**, not how many there were.
4. **Use the whole tool surface** — code intelligence and reference lookup before grep. The
   consumer that *translates* a value is the one a name-grep misses (finding 48;
   `PoweredProof.from_payload`).
5. **Re-read the authority file for each wave's area before starting it.**
6. **Pre-register what each CI round must show, and plan one round per wave.** Session 11 planned
   one and spent three, and the third, meant to confirm, became three pushes (findings 93, 94). A
   round takes about 16 min to required checks done on the public 4-vCPU runners and about 46 to
   all done, which Stryker sets. **Spend `gh` reads first** — free under I-0, and the
   highest-yield evidence in this repo.

#### FORBIDDEN REPAIRS. Each names what it would destroy.

No error may be cleared by **giving an argument a default**, by **widening a type to `Any`**, by
**adding a `# type: ignore`**, by **narrowing a checker's scope**, by **lowering a floor, a
tolerance or a replicate count**, or by **adding `continue-on-error`**. **No refusal path added to
make a defect loud may be removed to make a gate green.** If an error is genuinely a tooling
artifact, repair the *declaration that misleads the checker*, never the call sites that report it.

#### Determine ownership mechanically — `git log -1` is NOT enough

```powershell
git cat-file -e origin/main:<file>              # exit 0 => exists on main
git diff origin/main -- <file>                  # attribute the LINE, not the file
git merge-base --is-ancestor <sha> origin/main  # exit 1 => this branch's
```

For lint or format debt, materialise the blob and re-run the checker. Write it from Python with
`write_bytes`: PowerShell's `>` writes UTF-16 and `Set-Content -Encoding utf8` adds a BOM.

---

## STOP CONDITIONS

- **Stop at any barrier the census names that the batch depends on.** Say which.
- **Stop and report if a count does not move as predicted** — the delta per code, and what you
  checked.
- **Do not author any claim, task 17.2 or task 25 against the incumbent arm.**
- **Do not author a `deferred:` leaf** — 12.3, 12.4, 13.3–13.6, 17.5–17.9, 20.3, 21, 22.3, 23.x.
- **Do not tick 25 or 26.5** without the naming job's own verdict, and never tick a `[~]` on a
  local run.
- **Do not claim C60 proven, fidelity known, or the declared world real** (decision 1=a).
- **Do not resolve open decisions (a)–(e).** Surface them.
- **Do not commit a measured effectiveness baseline or widen its tolerance** (finding 88).
- **Do not remove or weaken `negative_regret_refusal`, the split's refusals or the
  comparator-admissibility property** to make a gate green.
- **Do not accept the Kaggle M5 terms.** C74 is non-passing by decision.
- **Do not create `.kiro/specs/external-audit-anchor/` or `.kiro/specs/forecaster-publication/`**
  unless the operator asks.
- **`pin_extractor_truth`'s declared count — DERIVE it:**
  `python -m scripts.audit.pin_extractor_truth --check`, and assert `declared == len(pins:)` read
  from the file, never against a transcribed integer (conflict P).
- **Do not change `main`, and do not change the repository's visibility.**
- **Do not run `ledger_gen` or `readme_gen` locally**, in any form — including
  `tests/verify/test_ledger_gen_property.py`.
- **Do not pad a session toward forty.**
- Surface every new conflict rather than resolving it silently.

## HARD-WON LESSONS — each one paid for

### The habits that caught the most

1. **Write predictions down before measuring, and make them falsifiable.** B-prime's P1–P5 were
   committed before the label; P5 failed and is recorded as failed. That is the habit working.
2. **A guard built from two expressions that share a term cannot constrain that term.**
   `headroom >= regret` reduces to `A >= B`. Ask what a guard reduces to before trusting it.
3. **An equality against a frozen constant is a TOTAL, not a partition proof** (finding 62).
   Partition, never filter; measure the right-hand side in the same run (G5).
4. **A citation is not a mechanism.** Walk to the constructor.
5. **A document edit's blast radius is every pin anchored to that document.** Probe all of them, on
   both sides.
6. **Read what got SKIPPED behind a failure, and read the LOG, not the summary.**
7. **Verify what you already had.** G4 exists because harvests are not remembered.
8. **Consensus across documents is not evidence.** It is usually one unchecked claim copied
   forward.
9. **Capability is not use.**
10. **A premise can go false without a diff** (finding 80): "free and unmetered" was false while
    the repository was private, and it was found by measuring runner speed.
11. **A measured baseline is not automatically an honest one** (finding 88): when the
    measurement's noise exceeds the tolerance, committing it trades a true red for a false one.
12. **A confirmation push is only as good as the dependency closure it read** (finding 93): P1 read
    maplibre's own `engines`, not its transitive tree, so the push meant to confirm discovered a
    Node-engine refusal — and its timing change surfaced a latent race in test infrastructure
    (finding 94).

### On verdicts

- **A number that cannot fail is not a number; a verdict that cannot be anything else is not a
  verdict.**
- **Sound arithmetic on the wrong denominator is still the wrong answer** (D2.6), and **a SUM can be
  material when neither addend is** (D2.7). Decompose before you publish, and report the residual.
- **A false stop is recoverable; a false confirmation is not.** D2.8 states each arm's error
  direction, and where one is unsafe (E's winner's curse) it requires BOTH ceiling intervals to
  clear rather than trusting either.
- **A precondition correction is not an assertion weakening** — the test is whether the standard
  got stricter (R2.10).
- **A SKIP is not a PASS, a deselected test is not a pass, `unavailable` is not `inconclusive`, and
  a green `audit-supply` is not a rendered map.**

### On scope and ownership

- **CI's scope is not the tree's scope.** `ruff` covers `packages/synapse_common/ agents/
  orchestrator/` only.
- **Do not adopt another owner's debt unilaterally** — record the diagnosis (findings 77, 82).
- **Necessary is not sufficient. One diff, one cause. Reachable is not run, and run is not
  finished.**

### On the ledger and the three marks

| Mark | Meaning |
|---|---|
| `[ ]` | open. An open leaf carrying `discharge:` is **CI-gated**; one carrying `deferred:` is **terminal**. Neither is authorable. |
| `[~]` | **authored, discharge pending.** Worth ZERO. Graduates on the job's own verdict and owes a `last-checked:` line (G4). |
| `[x]` | done **and** discharged |

- **A job's colour is not the task's verdict. A `discharge:` line can name TWO subjects, and both
  must report.**
- **DISK OUTRANKS THE LEDGER.** `tasks.meta.json` is not authority.

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
- **Cheap and encouraged — and only what `execution-routing.md` lists as LOCAL:** file reads,
  `grep`, diagnostics; `ruff`/`mypy` on changed files; bounded scoped `pytest`;
  `spec_ledger_census`; the **six** cheap gates; `command_path_truth` and `ratchet_truth`;
  `replay_metrics` through its `measurers` seam; `doc_truth.documented_value`,
  `extract_source_values` and `resolve_pin_texts` **as pure functions**; and **`gh` API reads**.
  **Biome, actionlint and secrets scans are not on that list** — session 11 ran all three;
  classifying them is a table edit owed to the operator.
- **Verify at the budget that will judge you.** A scoped **pure-arithmetic** file at
  `HYPOTHESIS_PROFILE=ci` costs seconds and catches what `dev` cannot.
- **`mypy --strict` over `tests/verify` or `tests/uplift` EXCEEDS a 120 s budget.** Type-check
  changed **non-test** modules by dotted name and **say plainly that the test modules were not
  checked.** Mixing `scripts/audit/*.py` and `tests/**` in one invocation fails with "Source file
  found twice".
- **Concurrency is the load-bearing half.** Parallel authoring agents: **required**. Agents that
  execute code: **exactly ONE**.
- **Preferred flags:** `-q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
  **`HYPOTHESIS_PROFILE` unset loads 500 — a 50× load. Set it explicitly, in the same command.**
- **Report core-seconds, not just invocation counts.** Session 11 spent **about 1,900–2,400,
  ESTIMATED** — the last ~430 from command wall times, the earlier 1,500–2,000 never metered per
  command — all single-process, one executor, no repo-wide run.
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
python -m scripts.audit.workflow_shape_truth              # C64
python -m scripts.audit.pin_extractor_truth --check       # C75   DERIVE the count
python -m scripts.audit.sweep_budget_truth --check        # C73
python -m scripts.audit.dataset_licence_truth --check     # C74   2 = SKIP, BY DECISION
python -m scripts.audit.task_claim_truth --check          # 1 = another spec's, when last read
python -m scripts.audit.gate_surface --check              # C63
python -m scripts.audit.spec_ledger_census --files --check
```

Last measured at session 11's close as **`0 / 0 / 0 / 2 / 0 / 0`** plus census 0
(`task_claim_truth`'s 1 cleared when core-purpose-uplift's tasks 9/9.1 were retracted) —
**re-measure, never assume.** **Append `*> $null` and read `$LASTEXITCODE`**; piping through
`Select-Object -First N` manufactures a non-zero exit. **Probe every pin anchored to any document
you edited**, on both sides: `doc_truth.documented_value` requires **exactly one** matching line,
and `pin_extractor_truth` reports green through a document-side failure.

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **The line-ending trap fires on programmatic edits.** Normalise to the file's dominant
  **worktree** ending, measured from Python at `newline=''` — `ci.yml` and `blocking-steps.yaml`
  were CRLF when last measured; these three documents were LF. **The `i/lf` column misleads**
  (finding 33). Check `git ls-files --eol` after **any** programmatic edit.
- **`Select-Object -First N` on a native command makes `$LASTEXITCODE` non-zero.**
- **PowerShell 5.1's `ConvertFrom-Json` returns an array unenumerated.** Assign, then `foreach`.
- **Complex inline `python -c` breaks on quoting.** Write a temp `.py` under `.tmp/` (git-ignored),
  run it, delete it.
- **`ruff`'s `SIM300` reads an upper-case attribute as a constant**, and **`N802` rejects an
  upper-case word in a test name** — fix the name, never add a `noqa`.
- **`git push` writes progress to stderr**, so `$LASTEXITCODE` is non-zero on a **successful**
  push. Read the `old..new ref` line.
- **A cached mypy run can hide a `[[tool.mypy.overrides]]` change.** `--no-incremental` after any
  config change.
- **`git log -1 -- <file>` is last-touch, not authorship.**
- **PowerShell's `Get-Content`/`Set-Content` corrupt UTF-8 here.** `Copy-Item` is a byte copy and
  is safe. **Verify bytes, never the console.**
- **`git status` over-reports.** Trust `git diff`, stage precisely, `git check-ignore -v` first.
- **Identify a CI run by `headSha`, NEVER by timestamp.** The local clock has run ~2h45m ahead.
- **`addopts` carries `-v`** — filter reads, never dump them.
- **`testpaths` omits `digital_twin`** while `uplift-verify` collects it, so a bare `pytest` and CI
  disagree about what the suite is.
- **`git commit -F` a temp file** for any message longer than a line.
- **`gh run download <id> -n <name> -D <dir>`** beats parsing a `| tee`'d log for an artifact.
- **Adding a label fires every workflow with a `labeled` trigger. Remove the label after use.**
- **Do not run `pre-commit install`.**
- Python 3.14.0, mypy 1.19.1, pytest 8.4.2, hypothesis 6.151.11, jsonschema 4.26.0 when last
  read; `gymnasium` absent; `gh` authenticated.

---

## AUTHORING RULES

- **Never hardcode `max_examples`.** Inherit from the root `conftest.py` profiles (`dev`=10,
  `heavy`=100, `ci`/`default`=500, `nightly`=5000). **Do not assert a total** (CF-13).
- **`-m "slow"` is a selector, not a path filter.** A slow test outside the paths the slow
  selection collects is selected by **no job at all**. The fast surface is **sharded**: check which
  shard's glob your new file lands in, and that the partition still proves itself exhaustive and
  disjoint **in-run** (finding 62). Task 13.7's discharge line was corrected for exactly this.
- **No `DECLARED_INVENTORY` entry is owed for a new property in this spec** — that table covers
  properties 1–37 (conflict O).
- **Assert a clause unconditionally; prove a refusal path by construction; assert non-emptiness.**
- **Derive numbers; flag the irreducible choice `chosen`.**
- **`set -o pipefail` in any `run:` block that pipes a gate or a measurement.**
- Type hints everywhere (`mypy --strict`); Pydantic v2 `ConfigDict(frozen=True)` for recorded
  facts; `structlog`, never `print()`, in library code; canonical
  `json.dumps(obj, sort_keys=True, separators=(',',':'))`; `encoding='utf-8'` on **every**
  `read_text` (E-S13-07); ASCII-only console output; lines <= 100 characters.
- **I-1 zero cost:** never add `openai`, `anthropic`, `cohere`, `replicate`, or any paid SDK. It is
  a closed list of four, and ADR-018 sanctions Pinecone's free tier.
- **I-4 append-only audit:** never UPDATE/DELETE audit rows; never mutate `make_canonical_row`.
- **I-7 honest degradation:** `DEGRADED`/`unknown`/`SKIP` are first-class. A SKIP is not a PASS.

### The five same-commit couplings

1. A rename and its declaration.
2. A new CI job and its `blocking-steps.yaml` entry — **and `required-checks.yaml` only when the job
   is genuinely eligible** (conflict G).
3. A schema change and every fixture that carries it — **including whatever TRANSLATES the value**
   (15.1: no fixture; the translator `PoweredProof.from_payload` ignores new keys).
4. **Any workflow job/step change, or any `blocking-steps.yaml` entry, and
   `python -m scripts.audit.gate_surface --write`.** Predict the row delta, then measure it — it is
   (trigger contexts × sections), not 1.
5. The session ceiling lives in **one** place, `spec_ledger_census.DEFAULT_BATCH`.

### Commit hygiene

- **Split commits by what must land together, never by narrative.** One commit **per wave**.
- Prefer new commits over `--amend`. No force-push, no `--no-verify`, no interactive flags. Leave
  git config unchanged. **Push to the PR #84 branch, never to `main`.**

---

## What this spec is actually for — hold this while you work

SYNAPSE claims that multi-agent AI makes better supply-chain decisions than a simpler system. The
thesis:

> Make the instruments provably able to fail, make the simulated world one where intelligence can
> pay, prove the measuring device can detect an effect, and only then measure.

**Both early-exit checkpoints have now run.** Checkpoint A's `material` verdict turned out to
measure tuning, not information (D2.6, D2.7); checkpoint B-prime then found room to win at the
declared structure (D2.9). **What can still end this honestly:** E3's controls showing the
instrument cannot see an effect of the ceiling's size, or E5 measuring a null. The world is
declared, not observed (1=a), so **every claim is a claim about the twin and must say so.**

**The pre-commitment, binding before the number is known:** if measured uplift is null or
negative, **it is reported as null or negative.** The floor stays at `0.0`, no headline is
published as a gain, and the result is written up as a finding — not reframed, not re-run at a
different replicate count until it moves.

Five guards on reading the result: no headline while no Power_Report describes the revision under
measurement (17.3); a null while any objective KPI is recorded not observably sensitive is
**inconclusive**, not confirmation (10.5); no `material` on a point estimate with no dispersion;
no verdict on a comparator that loses to its own subject (finding 54); and **no claim against the
incumbent arm — the baseline is the primary cell's tuned control E** (D2.7, task 25).

---

## Session 11 in one paragraph — the rest is in `HANDOFF.md`

**Fourteen leaves discharged, and checkpoint B-prime passed.** The session ran the operator-approved
re-cut first (decisions in R5.46, design in D2.8, leaves in task 29), declared the world from
research rather than from a feed (1=a, Q3=c; the research record is progress row 11), landed
structures 1 and 3 — the replenishment delay on the order path every arm uses — and wired B-prime
as an eight-cell matrix with its predictions committed before the label. **The primary cell's
ceiling, `0.630`, lies wholly above the `0.40` margin on both intervals**; P5 failed on one clause
in three descriptive cells and is recorded as failed (finding 79). CI then took **three**
remediation rounds where one was planned, clearing the truth-gate, integration and mutation reds
at their causes, and the operator made the repository public again after a secrets audit, because
private runners were metered and had half the cores (finding 80). **The third round, meant to
confirm, became three pushes, because it discovered a Node-engine refusal (finding 93) and a latent
harness race (finding 94)**; the sweep then passed with one prediction missed (finding 85), and
`e2e`, `audit-supply` and one mobile LCP sample passed. **Four numbers:** 14 discharged, about
1,900–2,400 core-seconds (estimated), 151 min of CI critical path (push to required checks done)
over seven pushes, about 41 productive / 6–8 failed agents beside one executor. **Not
verified:** LCP beyond one sample, E5's question, and anything about a real store.
