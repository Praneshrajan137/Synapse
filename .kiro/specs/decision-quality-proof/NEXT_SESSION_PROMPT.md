# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **12** (2026-10-15 to 2026-11-01).

**This prompt states no HEAD, deliberately.** It is written *before* the commit that carries it, so
any sha it named as "the newest" would be stale by construction (conflicts J and K). STEP 0 derives
it. The shas below are evidence for recorded facts, never the state to start from.

**And it carries no count a command can derive.** Where a number appears, the command that derives
it is beside it (conflict P).

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`, on branch `feat/decision-quality-proof`. PR **#84** is open
against `main`. **The spec is complete:** task 25's claim is stated in its body, and every open
leaf is `deferred:`. **PR #85 is a DRAFT** on `fix/open-access-mode`, in the worktree
`.claude/worktrees/open-access`: finding 89's repair, for the operator's review (decision (c)).
**The repository is PUBLIC, but it was found private once without a diff** (ENVIRONMENT TRAPS):
re-check `visibility` with `gh api repos/<owner>/<repo>` before sizing CI work on it.

**Your session cap is FORTY leaf tasks, in waves of about ten. It is a ceiling and it is expected
never to bind.** What stops you is a barrier or a phase boundary. **This session no leaf is left
to discharge** (STEP 2): the work is the claim, the operator's decisions, owed work that is no
leaf, and the two PRs (STEP 3).

### STEP 0 — DERIVE THE STATE, THEN READ THE RUNS AT THE NEWEST HEAD

The newest head is session 12's documents push (**P6**) or anything after it. **P6 changes
documents only**, so its runs should read as P5's (`732ecd9`) did. Before you read a P5 run as
the newest head's verdict, confirm that nothing after P5 changes code.

```powershell
git rev-parse --short HEAD
git rev-list --count origin/main..HEAD
git diff --stat 732ecd9 HEAD
gh run list --branch feat/decision-quality-proof --limit 20 --json databaseId,headSha,workflowName,conclusion
gh run list --branch fix/open-access-mode --limit 10 --json databaseId,headSha,workflowName,conclusion
```

**Two workflows are path-filtered, but on `pull_request` the filter reads the PR's WHOLE diff
against `main`**, so `frontend.yml` and `mutation.yml` run on **every** push to PR #84,
documents-only ones included. Wherever a workflow declares `cancel-in-progress`, a newer push
cancels the older head's in-progress run, **and so does re-running an older run (finding 115).**
`uplift.yml` triggers on `labeled` alone and never cancels in progress, so a push cannot cancel
its runs. **A `cancelled` verdict is no verdict: never push or re-run while a run you need is in
flight.**

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

**Never that way for a labelled run's job** (ENVIRONMENT TRAPS): stream it to disk with
`python .tmp/s12/fetch_log.py <jobid>`, then read the cache with
`python .tmp/s12/job_grep.py <jobid> "<regex>"` (both git-ignored and local; `job_grep.py` alone
buffers an uncached log in memory).

**What to read, in priority order:**

1. **Every `required:` job.** `infrastructure/quality/required-checks.yaml` names them; they live
   in `truth-gates.yml`, `ci.yml` and `integration.yml`. At P5 all read `success`: CI run
   `41289022422`, Truth Gates run `41289022401` and Integration. **Expect each as at P5.** A
   regression in a required check outranks everything below and blocks PR #84's merge path
   (STEP 3 D).
2. **P6's other runs**, expected as at P5: Frontend CI `41289022398`, Mutation `41289022389`,
   Policy `41289022451`, Security and Terraform. **The known reds, read and not repaired:**
   `audit-supply` (finding 105), `effectiveness-ratchet` by design (88), `fe-invariants` on six
   `not_executed` (90) and Stryker's dry run (120). `e2e` passed at P5, but its LCP budget sits
   inside runner variation (114), so an LCP red is not new. **Never commit a measured baseline,
   widen a tolerance or raise a timeout to turn one green.**
3. **PR #85's CI**, the first execution of its vitest and Playwright changes. Q2's review
   (`.tmp/s12/reviews/Q2-login-ci.md`, local) predicted no blocking failure and one informational
   `e2e` flake.
4. **G4:** the census read `unharvested: 0` at P6, with no `[~]` left. Re-derive it, and write
   down that you checked: **checking without writing it down does not satisfy it.**

### STEP 0a — THE METRIC

**Read the four steering files first; they are `inclusion: always`:**
`.kiro/steering/local-compute-budget.md` (I-0), `.kiro/steering/execution-routing.md`,
`.kiro/steering/throughput-with-integrity.md` (**the metric and G1–G7, with G8 beside G7:
authoring agents in alternating batches of at most five, then at most three**) and
`.kiro/steering/standard-of-work.md`.

**Leaves DISCHARGED. A `[~]` counts ZERO. Target: >= 11** (G6). Session 12 discharged **24**.
**Session 13 can discharge none:** the census reported `complete: yes`, and every open leaf is
`deferred:` (STEP 2 re-derives it). Say so in your opening, report 0 with that reason, and never
pad toward the target.

**Reconcile the ledger against disk BEFORE deriving a batch** — `--next 40` offers work that is
already done and the census cannot tell you which (sessions 1 and 9). **Authoring without recording
scores zero and is indistinguishable from not authoring.**

### STEP 0b — WHAT BINDS BEFORE ANY AUTHORING

1. **Checkpoint B-prime PASSED** (ADR-055 **D2.9**, task 14): E3 and E5 are licensed by
   measurement. Do not re-run it, and do not re-open conflict R — R5.45 superseded it.
2. **No claim may be denominated against the incumbent arm.** The honest baseline is the tuned
   control **E**, re-derived per cell by task 13.7's committed search; task 25's re-scope names E
   of the primary cell. **25's claim was stated under this prohibition** (ADR-055 D2.7), and 17.2
   landed under it.
3. **A `deferred:` leaf is terminal** (task 29.1). Never author one; its line is a decision, not a
   TODO.
4. **Decision 1=a binds every claim:** world values are `chosen`, fidelity is `unknown`, and C60 is
   `unavailable` by decision — which is why 17.5, 17.6, 17.9 and 22.3 are deferred (finding 71).
   **Nothing may claim C60 proven.**
5. **Finding 79 is owed before E3 cites arm D as a bound** — open decision (d).
6. **The committed Power_Report describes the tree.** `docs/state/uplift-power-report.json`
   carries harness revision `0dd399e2...`, equal to the tree's `POWER_SOURCE_SET` digest at P5
   (measured). An edit that moves the digest voids it. **The claim is published, so finding 116's
   code repair may land now, and any claim after it needs the controls re-run.**
7. **Task 25's pre-commitment held and still binds:** the claim is negative, stated with finding
   112 beside it, and is never relabelled, reframed or re-run until it moves.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/steering/execution-routing.md` — **where** a workload runs, by table not by judgement.
3. `.kiro/steering/throughput-with-integrity.md` — **the metric** and **G1–G8**.
4. `.kiro/steering/standard-of-work.md` — the reviewer bar and the methodology at its **measured**
   level. Read it before claiming a practice or a standard.
5. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the ceiling, waves, the **barrier
   stop**, the three marks, the batch table, the cheap gates, the progress ledger. **Read rows 11
   and 12 in full.**
6. `HANDOFF.md` (repo root) — state, pointers, the **open operator decisions** and the honesty
   ledger. Read its NOT-verified list before believing any colour.
7. `CLAUDE.md` — the 14 invariants, the honesty contract, the gate registry, the `E-S*` lessons.
   **I-1's paid-client list is CLOSED at four names.**
8. `.claude/skills/synapse-engineer/SKILL.md` + `references/`; then `.cursorrules` +
   `docs/cursor/*.md`.
9. `docs/adr/ADR-055-twin-decision-relevance.md` — **D2.8** (the re-cut's design) and **D2.9**
   (B-prime, measured) first; D2.7 and D6 behind them. **Probe every pin anchored to it, on both
   sides, if you amend it** — derive the set with
   `git grep -n "document: docs/adr/ADR-055" -- infrastructure/quality/doc-number-pins.yaml`;
   never transcribe its count.
10. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. **R5.45/R5.46** carry the
    re-cut; `tasks.md` is the ledger, **task 25's body states the claim once**, and parent 29's
    P1–P5 blocks record every run this prompt cites.
11. `.kiro/steering/engineering-learnings.md` — session 12's lessons, each with its evidence
    (loaded on demand, `inclusion: auto`). Read it before planning; the four steering files above
    still govern any conflict.

**Two invariant numberings disagree** (`references/14_invariants.md` vs `.cursorrules` on I-6, I-8,
I-10); authority 5 outranks 6, and I-1, I-4, I-5, I-7 agree in both. **When two sources conflict,
surface it; never resolve it silently.** Twenty-two are surfaced (A–V); S to V are session 12's.

### STEP 2 — reconcile, derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

**At session 12's close the census reported `complete: yes`** — 0 authorable, 0 CI-gated, 0
pending, every open leaf `deferred:`. Re-derive it, never copy it. **There is no batch of leaves
to derive.** If the census names a barrier, state your answer to it in your opening; an
unanswered barrier is a stop.

**The work is owed work that is no leaf** (each body is in `tasks.md`, parent 29):

- **Finding 116's code repair**, an offline reasoner in the consensus arm's assembly. **Allowed
  now that the claim is published**, but it moves `POWER_SOURCE_SET` and so voids the committed
  Power_Report (STEP 0b item 6): **re-run the controls before any new claim.**
- **Findings 118 and 120, Stryker's.** 120 (a frontend property fails on the key `__proto__`)
  failed Stryker's dry run at P5, not on time. 118's next measurement is one Stryker run on
  `src/lib/universal-state.ts` alone, in CI. Raising the timeout is not a repair, and 120's
  repair is the frontend owner's decision (its body).
- **Finding 119's small defects**, listed once in its body.
- **Findings 105** (the zod 4 migration) **and 106** (the chromatic race): open decisions as well,
  so ask before starting either.
- **Findings 90 and 91**, other owners', carried from session 11; `fe-invariants` read 90's six
  `not_executed` again at P5.

**`$LASTEXITCODE` lies if you pipe the census through `Select-Object -First N`.** Re-run with
`*> $null`.

### STEP 3 — what to do, in priority order

#### A. Surface task 25's claim to the operator, with its cause

The claim is stated once, in task 25's body ("THE CLAIM (2026-11-01)"). Quote its headline
sentence, whose numbers are the only ones a derived document carries (headline -4.4026, 95%
interval [-4.4218, -4.3843], verdict `baseline_wins` against the tuned control E of the primary
cell), and point to the body for the rest. Put the cause beside the number, never in place of it:
finding 112, whose repair lies outside decision 3=a. **Whether to commission that repair is the
operator's decision; do not start it.**

#### B. Put the open operator decisions

Name each in your opening, with its finding (the section below), and resolve none. Conflict V
stays the operator's although clause (f) passed.

#### C. Owed work that is no leaf, in G8 batches

STEP 2's list, partitioned by coupling closure (G2); ask before starting 105 or 106. **If finding
116's code repair lands, the Power_Report no longer describes the tree:** the controls' re-run is
a labelled run, so register its predictions first, and state no new claim before it reports.

#### D. PR #84's merge path, and PR #85's review

PR #84's required checks were green at P5; confirm them at P6 (STEP 0). Lay out the path for the
operator: the required checks, the non-required reds with their findings, and the overlap with
PR #85 in four files (`HANDOFF.md`, headline 4), where whichever merges second rebases. For
PR #85, report what its CI ran against Q2's prediction; its review, merge and activation are the
operator's (decision (c)). **Neither merge is yours: do not change `main`.**

### THE OPEN OPERATOR DECISIONS — name them in your opening; do not resolve them

`HANDOFF.md` carries one line each. **(a)** the effectiveness ratchet's tolerance against its
measured noise (finding 88; the strict A/A ran, and AA1–AA3 held). **(b)** the sweep's
PASS-baseline branch credits an abstention (finding 85, C69). **(c)** finding 89, live exposure:
its repair is PR #85, a draft, for the operator to review, merge and activate. **(d)** arm D's
"pointwise best" restatement, owed before E3 cites D (finding 79). **(e)** Lighthouse LCP at
`warn` or `error` (findings 95 and 114: the 2500 ms budget sits inside runner variation).

**New in session 12:** finding 112, the claim's cause (every agent reads its request one level
too shallow; the repair lies outside decision 3=a, so commissioning it is the operator's);
conflict S (the negative control is judged on gains only, finding 101); conflict V (finding 117's
agreement rule under proven per-seed identity, which clause (f) measured at P5); the
reorders-only lever set for E5 and the controls (the main agent's choice; the operator may
overturn it); finding 105 (the zod 4 migration); finding 106 (the chromatic race). **Conflict U
was adopted** (task 16.7), surfaced so the operator may object.

### STEP 4 — how a session is actually run

**Waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit.
2. **Write findings into `tasks.md` AS YOU FIND THEM**, in the task body that owns them.
3. **Parallel authoring is the DEFAULT (G7); exactly ONE agent executes (G1); batches alternate at
   most five, then at most three, each released only when the previous one has fully returned
   (G8).** Partition by coupling closure (G2). Working serially requires a stated reason.
   **Every contract's FIRST line is the no-execute clause** (G3), then: files it may and may not
   touch, the one canonical location for its findings, and the couplings it owns. **Verify every
   agent's writes independently of its report** — a silent agent is not a no-op agent. Session 12
   lost 18 of 32 agents before G8, and none of the G8 dispatches `HANDOFF.md` itemises to the
   limit. A failed agent is RESUMED from a measured RESUME NOTE, never restarted. **Report what
   each agent PRODUCED.**
4. **Use the whole tool surface** — code intelligence and reference lookup before grep. The
   consumer that *translates* a value is the one a name-grep misses (finding 48;
   `PoweredProof.from_payload`).
5. **Re-read the authority file for each wave's area before starting it.**
6. **Pre-register what each CI round must show, and plan one round per wave.** Session 12 ran five
   rounds (P1–P5), about 20–25 minutes each to required checks, and recorded every miss as a miss.
   **Spend `gh` reads first** — free under I-0, and the highest-yield evidence in this repo.

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
- **Do not author any claim against the incumbent arm.**
- **Do not author a `deferred:` leaf** — 12.3, 12.4, 13.3–13.6, 17.5–17.9, 20.3, 21, 22.3, 23.x.
- **Do not re-open a discharged leaf**, 22.1 and 25 among them: the claim stands as task 25 states
  it. Never tick a `[~]` on a local run.
- **Repairing finding 116 in code voids the Power_Report: re-run the controls before any new
  claim.**
- **Do not resolve conflict V**, open decisions (a)–(e) or session 12's new ones, finding 112's
  repair among them. Surface them.
- **Do not claim C60 proven, fidelity known, or the declared world real** (decision 1=a).
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
13. **Profile a timed-out run's log before hypothesising** (finding 116): the leading hypothesis
    was wrong.
14. **A guard that compares two instruments on disjoint seeds tests only sampling once per-seed
    identity holds** (finding 117).
15. **Never re-run an older run of a PR-keyed workflow while a newer one is in flight** (finding
    115): the re-run cancels the newer run's job.
16. **Autonomous mode sandboxes every shell command** (no finding number; ENVIRONMENT TRAPS).

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
  `spec_ledger_census`; the LOCAL audit gates the table lists, the six cheap gates among them;
  `replay_metrics` through its `measurers` seam; `doc_truth.documented_value`,
  `extract_source_values` and `resolve_pin_texts` **as pure functions**; and **`gh` API reads**.
  **Biome lint, actionlint and the stdlib secrets scan are now LOCAL rows** (measured
  2026-10-12), at the scope the table states.
- **Verify at the budget that will judge you.** A scoped **pure-arithmetic** file at
  `HYPOTHESIS_PROFILE=ci` costs seconds and catches what `dev` cannot.
- **`mypy --strict` over `tests/verify` or `tests/uplift` EXCEEDS a 120 s budget.** Type-check
  changed **non-test** modules by dotted name and **say plainly that the test modules were not
  checked.** Mixing `scripts/audit/*.py` and `tests/**` in one invocation fails with "Source file
  found twice".
- **Concurrency is the load-bearing half.** Parallel authoring agents: **required**, in G8's
  batches. Agents that execute code: **exactly ONE**.
- **Preferred flags:** `-q --tb=line -p no:randomly -m "not slow"`, `HYPOTHESIS_PROFILE=dev`.
  **`HYPOTHESIS_PROFILE` unset loads 500 — a 50× load. Set it explicitly, in the same command.**
- **Report core-seconds, not just invocation counts.** Session 12 spent **about 4,600,
  ESTIMATED**: about 3,700 by P4 and about 900 on 2026-11-01 (three login-branch verifications,
  the E5 log profiling over 556 MB, scoped tests and gates). All single-process, one executor, no
  repo-wide run, no simulation locally.
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
python -m scripts.audit.task_claim_truth --check          # 0 when last read
python -m scripts.audit.gate_surface --check              # C63
python -m scripts.audit.spec_ledger_census --files --check
```

Last read on 2026-11-01 as **`0 / 0 / 0 / 2 / 0 / 0`** plus census 0 (session 12's local gate log,
`.tmp/s12/local_gates.log`, which records no sha) — **re-measure, never assume.** **Append
`*> $null` and read `$LASTEXITCODE`**; piping through `Select-Object -First N` manufactures a
non-zero exit. **Probe every pin anchored to any document you edited**, on both sides:
`doc_truth.documented_value` requires **exactly one** matching line, and `pin_extractor_truth`
reports green through a document-side failure.

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **Kiro autonomous mode forces the OS command sandbox on, with outbound network blocked**
  (https://kiro.dev/docs/sandbox/). Here it broke every shell command: `grant_rw` fails on any
  `fs_write` path in `~/.kiro/settings/permissions.yaml` that does not exist (undocumented), and
  sandboxed commands cannot read `~/.gitconfig` or the GitHub CLI config, so `gh` cannot start.
  The operator turned it off (`.kiro/settings/sandbox.json`, `enabled: false`, untracked and
  local; **never commit it**). Re-enabling needs fs_read grants for those paths and
  `sandbox_network` rules for github.com and api.github.com (https://kiro.dev/docs/permissions/).
- **Labelled-run logs are huge:** E5's job log was 556 MB (4.4 M lines), and a controls leg's did
  not finish downloading in 10 minutes. Stream them to disk (STEP 0), never into memory.
- **Visibility can change without a diff:** private around 2026-11-01 05:40Z (an unauthenticated
  404 on the API and the PR page), public again by the operator, 0 billable ms that day.
- **A per-test regex over a job log must allow spaces in parametrised test ids.**
- **The line-ending trap fires on programmatic edits.** Normalise to the file's dominant
  **worktree** ending, measured from Python at `newline=''` — `.github/workflows/*.yml`,
  `blocking-steps.yaml`, `required-checks.yaml` and `ratchets.json` were CRLF when last read;
  these three documents were LF. **The `i/lf` column misleads** (finding 33). Check
  `git ls-files --eol` after **any** programmatic edit.
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
  git config unchanged. **Push to the PR #84 branch, never to `main`.** PR #85's worktree has no
  upstream: push it with an explicit refspec.

---

## What this spec is actually for — hold this while you work

SYNAPSE claims that multi-agent AI makes better supply-chain decisions than a simpler system. The
thesis:

> Make the instruments provably able to fail, make the simulated world one where intelligence can
> pay, prove the measuring device can detect an effect, and only then measure.

**Both early-exit checkpoints have run, and so have E3's controls and E5.** Checkpoint A's
`material` verdict turned out to measure tuning, not information (D2.6, D2.7); checkpoint B-prime
then found room to win at the declared structure (D2.9); the controls detected the positive effect
(MDE `0.0235` at 1000 per arm) while their agreement rule fired (finding 117), which clause (f)
traced to the seed sets. **E5 ended it honestly:** task 25's claim is negative, `baseline_wins`
against E, with finding 112 beside it, as its registered prediction said. The world is declared,
not observed (1=a), so **every claim is a claim about the twin and must say so.**

**The pre-commitment, made before the number was known, held and still binds:** if measured
uplift is null or negative, **it is reported as null or negative.** The floor stays at `0.0`, no
headline is published as a gain, and the result is written up as a finding — not reframed, not
re-run at a different replicate count until it moves.

Five guards on reading the result: no headline while no Power_Report describes the revision under
measurement (17.3); a null while any objective KPI is recorded not observably sensitive is
**inconclusive**, not confirmation (10.5); no `material` on a point estimate with no dispersion;
no verdict on a comparator that loses to its own subject (finding 54); and **no claim against the
incumbent arm — the baseline is the primary cell's tuned control E** (D2.7, task 25).

---

## Session 12 in one paragraph — the rest is in `HANDOFF.md`

**Twenty-four leaves discharged, E3's controls ran, and E5 completed: the claim is stated,
negative.** The session landed E3 (15–17), the objective headline and information pathway
(29.4–29.6), and the job that makes E5 judgeable. The controls committed a Power_Report; their
agreement rule fired, and clause (f) traced it to the seed sets (finding 117). E5's first run
spent its bound on an Ollama lookup (finding 116); the re-run at P5 completed, and task 25 states
its result with finding 112 beside it. **Four numbers:** 24 discharged; about 4,600 core-seconds
(estimated); five CI rounds of about 20–25 min each; 63 agents dispatched (36 finished) beside one
executor. **Not
verified:** P6's CI, PR #85's CI, a real store.
