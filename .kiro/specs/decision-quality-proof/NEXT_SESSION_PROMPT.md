# NEXT SESSION PROMPT — decision-quality-proof

Regenerated at the end of session **13** (2026-11-01 to a closing date not recorded (last written 2026-11-15 by file time; committed 2026-11-18)).

**This prompt states no HEAD, deliberately.** It is written *before* the commit that carries it, so
any sha it named as "the newest" would be stale by construction (conflicts J and K). STEP 0 derives
it. The shas below are evidence for recorded facts, never the state to start from.

**And it carries no count a command can derive.** Where a number appears, the command that derives
it is beside it (conflict P).

---

## PROMPT — copy from here down

You are continuing the `decision-quality-proof` spec in the SYNAPSE repo at
`C:\Users\Pranesh\Projects\synapse`. **`main` holds sessions 1 to 12 and ADR-057:** PR #84 and
PR #85 were merged by merge commit in session 13 (operator decision S13.1=a). Session 13's own
work rides four branches, none merged when this was written:

- **#87**, `fix/consensus-reads-request` (open): the consensus reads the request it is sent.
  The controls and E5 have reported on it (31.10, 31.11); the claim is 31.12 (parent 31).
- **#89**, `fix/frontend-gates` (draft), worktree `.claude/worktrees/frontend-gates`: every
  Frontend CI red repaired (parent 32). Round 2 was red on findings 129 to 131 and 114.
- **Parent 33's PR**, not opened when this was written -> #90, opened 2026-11-14,
  `fix/owed-gate-defects`, worktree `.claude/worktrees/gate-defects`: the gate defects owed
  from findings 53 and 119.
- **The ledger PR**, not opened when this was written -> the pull request opened with this commit, 2026-11-18,
  `docs/dqp-session-13`, worktree `.claude/worktrees/ledger`: the ledger and these documents.

**Code PRs do not edit `tasks.md`; record their discharges in a ledger PR.** The repository is
PUBLIC; re-check `visibility` with `gh api repos/<owner>/<repo>` before sizing CI work on it.

**Your session cap is FORTY leaf tasks, in waves of about ten. It is a ceiling and it is expected
never to bind.** What stops you is a barrier or a phase boundary. **The census no longer reads
`complete: yes`:** parents 30 to 33 added leaves, and most open ones are CI-gated on runs that
had not reported when this was written (STEP 2). The session is harvest first, then 31.12 if
session 13 did not state it.

### STEP 0 — DERIVE THE STATE, THEN READ THE RUNS AT EACH NEWEST HEAD

`main` and four PRs are in play. For each, find the newest head, and confirm that nothing after
the head you read changes code before you treat a run as that head's verdict.

```powershell
git fetch origin
git log --oneline -3 origin/main
gh pr list --state open --json number,headRefName,headRefOid,isDraft
gh run list --branch fix/consensus-reads-request --limit 20 --json databaseId,headSha,workflowName,conclusion
gh run list --branch fix/frontend-gates --limit 20 --json databaseId,headSha,workflowName,conclusion
gh run list --branch fix/owed-gate-defects --limit 10 --json databaseId,headSha,workflowName,conclusion
gh run list --branch main --limit 10 --json databaseId,headSha,workflowName,conclusion
```

**Worktrees under `.claude/worktrees/` are git-ignored by the main tree**, so search tools rooted
at the main tree do not see their files. Open them by full path, or use `git -C <worktree> grep`.

**Two workflows are path-filtered, but on `pull_request` the filter reads the PR's WHOLE diff
against `main`**, so `frontend.yml` and `mutation.yml` run on every push to a PR whose diff
touches their paths, documents-only pushes included. Wherever a workflow declares
`cancel-in-progress`, a newer push cancels the older head's in-progress run, **and so does
re-running an older run (finding 115).** `uplift.yml` triggers on `labeled` alone and never
cancels in progress, so a push cannot cancel its runs. **A `cancelled` verdict is no verdict:
never push or re-run while a run you need is in flight.**

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
`python .tmp/s12/job_grep.py <jobid> "<regex>"` (session 12's scripts, git-ignored and local;
`job_grep.py` alone buffers an uncached log in memory). Confirm they still exist before relying
on them.

**What to read, in priority order:**

1. **31.12, the repaired arm's claim (PR #87).** E5 run 41352100304 at `4b659e6` has reported
   (31.11). If 31.12's body still carries its placeholder, read first whether the Inventory
   Sentinel bound the pathway probe's decisions (ADR-058's falsification item 1, in 31.11),
   then state the claim from that run's artifact.
2. **Every `required:` job** on each PR's newest head. `infrastructure/quality/required-checks.yaml`
   names four, in `truth-gates.yml` and `ci.yml`. A regression in a required check outranks
   everything below.
3. **PR #89's round 3**, which carries the repairs of findings 129 to 131 (parent 32). Round 2
   (run 41344870270 at `50deebc`) was the first run of `storybook-a11y` and of the five-leg
   `e2e-harness`; ADR-059's ratchet and `fe-invariants` were skipped behind them, so round 3
   may be the first run of both.
4. **Parent 33's PR**, if its work landed.
5. **`main`'s push runs.** CD-GCP fails at Workload Identity Federation until the operator
   repairs finding 123; that red is not new.
6. **G4:** every `[~]` is re-read against the newest run naming its discharge job, and that
   run's id is written into its `last-checked:` line. None was left when this was written:
   31.8 and 31.9 discharged in session 13. **Checking without writing it down does not
   satisfy it.**

### STEP 0a — THE METRIC

**Read the four steering files first; they are `inclusion: always`:**
`.kiro/steering/local-compute-budget.md` (I-0), `.kiro/steering/execution-routing.md`,
`.kiro/steering/throughput-with-integrity.md` (**the metric and G1–G7, with G8 beside G7:
authoring agents in alternating batches of at most five, then at most three**) and
`.kiro/steering/standard-of-work.md`.

**Leaves DISCHARGED. A `[~]` counts ZERO. Target: >= 11** (G6). Session 13 discharged
**32**. Session 14's dischargeable leaves are the CI-gated ones whose runs report:
31.12 if it is still open, parent 32's leaves on round 3 and later, and parent 33's. Never pad
toward the target.

**Reconcile the ledger against disk BEFORE deriving a batch** — `--next 40` offers work that is
already done and the census cannot tell you which (sessions 1 and 9). **Authoring without recording
scores zero and is indistinguishable from not authoring.**

### STEP 0b — WHAT BINDS BEFORE ANY AUTHORING

1. **Checkpoint B-prime PASSED** (ADR-055 **D2.9**, task 14): E3 and E5 are licensed by
   measurement. Do not re-run it, and do not re-open conflict R — R5.45 superseded it.
2. **No claim may be denominated against the incumbent arm.** The honest baseline is the tuned
   control **E**, re-derived per cell by task 13.7's committed search; task 25's re-scope names E
   of the primary cell. **25's claim was stated under this prohibition** (ADR-055 D2.7), and
   31.12's pre-commitment is written under it.
3. **A `deferred:` leaf is terminal** (task 29.1). Never author one; its line is a decision, not a
   TODO. 33.7 is deferred.
4. **Decision 1=a binds every claim:** world values are `chosen`, fidelity is `unknown`, and C60 is
   `unavailable` by decision — which is why 17.5, 17.6, 17.9 and 22.3 are deferred (finding 71).
   **Nothing may claim C60 proven.**
5. **Finding 79 is owed before E3 cites arm D as a bound** — open decision (d).
6. **On PR #87's branch the committed Power_Report describes the tree E5 measured** (`4b659e6`,
   31.10). An edit to any `POWER_SOURCE_SET` file voids it, and no claim may then cite it until
   the controls re-run on the new tree (task 17.3).
7. **The B-prime record binds `BPRIME_PHYSICS_SET`, comments included** (finding 122).
   `uplift/bprime_record.py` names the set. Edit no file in it without re-measuring B-prime.
8. **Task 25's claim stands as stated, and is never edited or relabelled.** The repaired arm's
   claim goes in 31.12, under the pre-commitment written there before E5 reported.

### STEP 1 — read these, in this order. Binding, not advisory.

1. `.kiro/steering/local-compute-budget.md` — invariant **I-0**. Highest precedence.
2. `.kiro/steering/execution-routing.md` — **where** a workload runs, by table not by judgement.
3. `.kiro/steering/throughput-with-integrity.md` — **the metric** and **G1–G8**.
4. `.kiro/steering/standard-of-work.md` — the reviewer bar and the methodology at its **measured**
   level. Read it before claiming a practice or a standard.
5. `.kiro/specs/decision-quality-proof/SESSION_PROTOCOL.md` — the ceiling, waves, the **barrier
   stop**, the three marks, the batch table, the cheap gates, the progress ledger. **Read rows 12
   and 13 in full.**
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
10. `docs/adr/ADR-058-inventory-sentinel-reads-the-request.md` (PR #87's branch) and
    `docs/adr/ADR-059-effectiveness-ratchet-judges-latency-by-the-median-of-five-legs.md`
    (PR #89's branch): the Sentinel's reading, with its falsification items and open decisions,
    and the ratchet's rule, with its A/A's predictions AK1 to AK4.
11. `.kiro/specs/decision-quality-proof/{requirements,design,tasks}.md`. **R5.45/R5.46** carry the
    re-cut; `tasks.md` is the ledger. **Task 25's body states session 12's claim once**, Phase 8's
    opening paragraph states session 13's operator decisions once, and parents 30 to 33 record
    every run this prompt cites.
12. `.kiro/steering/engineering-learnings.md` — session 12's lessons, each with its evidence
    (loaded on demand, `inclusion: auto`). Read it before planning; the four steering files above
    still govern any conflict.

**Two invariant numberings disagree** (`references/14_invariants.md` vs `.cursorrules` on I-6, I-8,
I-10); authority 5 outranks 6, and I-1, I-4, I-5, I-7 agree in both. **When two sources conflict,
surface it; never resolve it silently.** Twenty-four are surfaced (A–X); W and X are session 13's,
and the operator resolved both (Phase 8).

### STEP 2 — reconcile, derive the batch, then ANSWER THE BARRIERS

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

**At session 13's close the census no longer read `complete: yes`.** It reads `200 / 162 / 0 / 38` (open: 0 authorable, 12 CI-gated, 26 deferred; 0 unharvested), `complete: no`, exit 0, read by truth session 3 on 2026-11-18 at `d4f985c` with these four files; 162 done against 130 at session 12's close. Its `absent-artifact` lines name files of the then-unmerged PRs #87 and #89. Re-derive it, never copy it. If it names a barrier, state your answer to it
in your opening; an unanswered barrier is a stop. Its `absent-artifact` lines for parents 31 and
32 are expected while PR #87 and PR #89 are unmerged: those leaves name files `main` does not
hold yet.

**The chains that order the CI-gated leaves** (each body is in `tasks.md`):

- **31.12 is the last of parent 31's chain:** 31.10 and 31.11 are discharged. Register each
  labelled run's predictions before its label, and add a label only once the CI it waits for
  has completed (31.11's sequence deviation).
- **Parent 32's `fe-invariants` leaves** wait on one run in which `quality`, `e2e`, `e2e-visual`,
  `e2e-harness` and `storybook-a11y` all pass. `e2e`'s LCP budget sits inside runner variation
  (finding 114, decision (e)): never re-run `e2e` to draw a passing sample. In round 2,
  `storybook-a11y` and `e2e-harness` failed too (findings 129 to 131).
- **32.14 waits on 32.13:** run A's candidate is committed unedited, then run B reads it.
- **32.6, 32.9 and parent 33's leaves** had no commit when they were registered, though edits
  were in progress, and their bodies say so. Read the body and the census before treating any
  of them as CI-gated.

**`$LASTEXITCODE` lies if you pipe the census through `Select-Object -First N`.** Re-run with
`*> $null`.

### STEP 3 — what to do, in priority order

#### A. The repaired arm's claim (31.12)

The controls re-ran and their Power_Report is committed unedited (31.10); E5 has reported
(31.11). If 31.12 still carries its placeholder, read whether the Inventory Sentinel bound the
pathway probe's decisions, then state the claim in 31.12's body from run 41352100304's
artifact, against E, worded "recommendations, if executed", with its cause beside it. **Task
25 is never edited.**

#### B. PR #89's round 3 (parent 32)

Read it against its predictions (PR #89's comment 6874467160 of 2026-11-14, written before the push of `9c53859`; its
outcome is comment 6881277614), harvest what
reported, and record every miss as a miss. An axe violation in `storybook-a11y` is repaired
where its cause is (finding 130's is the story's background, finding 131's the glyph's ink),
never by disabling a rule.

#### C. Parent 33

Read its CI and harvest what reported. 33.7 stays deferred.

#### D. Put the open operator decisions

Name each in your opening, with its finding (the section below), and resolve none.

#### E. Merges are the operator's

Merging #87, #89, parent 33's PR or a ledger PR changes `main`. Conflict W's resolution covered
#84 and #85 only (S13.1=a). Lay out each PR's required checks and its non-required reds with
their findings, and ask.

### THE OPEN OPERATOR DECISIONS — name them in your opening; do not resolve them

`HANDOFF.md` carries one line each. **(b)** the sweep's PASS-baseline branch credits an abstention
(finding 85, C69). **(d)** arm D's "pointwise best" restatement, owed before E3 cites D (finding
79). **(e)** Lighthouse LCP at `warn` or `error`, with the 2500 ms budget inside runner variation
(findings 95 and 114); the zod 4 build's four samples (2728 and 2672 ms in round 1, 2556 and
2608 ms in round 2) sit inside the zod 3 builds' spread, and four against eleven establish no
shift. **Conflict S** (the negative control judged on gains only, finding 101) and
**conflict V** (finding 117's agreement rule under proven per-seed identity). **The reorders-only
lever set** for E5 and the controls (the main agent's choice; the operator may overturn it).
**Finding 106** (the chromatic race, ADR-025's owner's call). **New in session 13:** ADR-058's
open items O1 to O5; CD-GCP's Workload Identity provider (finding 123, operator-owned); and
whether a PR-time check should read the B-prime record against the tree (finding 122).

**Resolved in session 13 by the operator:** (a) by S13.2=a (a median of five legs, ADR-059); (c)
by S13.1=a (PR #85 merged; it reaches the live console only once finding 123 is repaired);
finding 112's repair by S13.3=a; the zod 4 migration of finding 105 by S13.2=a. **Conflict U**
stays adopted (task 16.7), surfaced so the operator may object.

### STEP 4 — how a session is actually run

**Waves of about ten, each `read → author → verify → commit`.**

1. **Commit every wave.** The commit is the bisect unit.
2. **Write findings into `tasks.md` AS YOU FIND THEM**, in the task body that owns them, on the
   ledger PR's branch.
3. **Parallel authoring is the DEFAULT (G7); exactly ONE agent executes (G1); batches alternate at
   most five, then at most three, each released only when the previous one has fully returned
   (G8).** Partition by coupling closure (G2). Working serially requires a stated reason.
   **Every contract's FIRST line is the no-execute clause** (G3), then: files it may and may not
   touch, the one canonical location for its findings, and the couplings it owns. **Verify every
   agent's writes independently of its report** — a silent agent is not a no-op agent. A failed
   agent is RESUMED from a measured RESUME NOTE, never restarted. **Report what each agent
   PRODUCED.**
4. **Use the whole tool surface** — code intelligence and reference lookup before grep. The
   consumer that *translates* a value is the one a name-grep misses (finding 48;
   `PoweredProof.from_payload`).
5. **Re-read the authority file for each wave's area before starting it.**
6. **Pre-register what each CI round and each labelled run must show, before the push or the
   label,** in a PR comment or the commit message, and record every miss as a miss. **Spend `gh`
   reads first** — free under I-0, and the highest-yield evidence in this repo.

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
- **Do not author a `deferred:` leaf** — 12.3, 12.4, 13.3–13.6, 17.5–17.9, 20.3, 21, 22.3, 23.x,
  33.7.
- **Do not re-open a discharged leaf**, 22.1 and 25 among them: task 25's claim stands as it
  states it. Never tick a `[~]` on a local run.
- **State the repaired arm's claim only in 31.12**, from run 41352100304's artifact, whose
  Power_Report (`4b659e6`) describes the revision E5 measured.
- **Edit no `BPRIME_PHYSICS_SET` file, comments included, without re-measuring B-prime**
  (finding 122).
- **Do not resolve conflicts S and V or the open decisions.** Surface them.
- **Do not claim C60 proven, fidelity known, or the declared world real** (decision 1=a).
- **Commit no effectiveness baseline but run A's candidate, unedited (32.14), and never widen
  `latencyPct`** (finding 88, ADR-059).
- **Do not raise the LCP budget, and do not re-run `e2e` to draw a passing sample** (finding 114).
- **Do not remove or weaken `negative_regret_refusal`, the split's refusals or the
  comparator-admissibility property** to make a gate green.
- **Do not accept the Kaggle M5 terms.** C74 is non-passing by decision.
- **Do not create `.kiro/specs/external-audit-anchor/` or `.kiro/specs/forecaster-publication/`**
  unless the operator asks.
- **`pin_extractor_truth`'s declared count — DERIVE it:**
  `python -m scripts.audit.pin_extractor_truth --check`, and assert `declared == len(pins:)` read
  from the file, never against a transcribed integer (conflict P).
- **Do not change `main` without the operator's decision, and do not change the repository's
  visibility.**
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
17. **A digest pins bytes, comments included, and a record no check reads is not protected**
    (finding 122): a comment edit voided the B-prime record while CI stayed green, and the first
    reader was a labelled run.
18. **A repair that lets a checker see more must re-read every listing it newly sees** (finding
    124): finding 90's repair would have attested FE-INV-010 from tests that assert no vital.
19. **A guarantee covers only the components and environments it names** (finding 121): the
    laptop has no codecarbon, so only CI could see the consensus arm's second dial.

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
  orchestrator/` only (33.7 records why widening it is deferred).
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
  **Biome lint, actionlint and the stdlib secrets scan are LOCAL rows** (measured 2026-10-12),
  at the scope the table states.
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
- **Report core-seconds, not just invocation counts.** Session 13 spent an amount not recorded, neither measured nor
  estimated.
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

Last read on 2026-11-18 by truth session 3, at `d4f985c` with this commit's ledger files: C64 0, C75 0
(18 pins), C73 0, C74 2 (skip, by decision), task-claim 0, C63 0; the census `--check` 0 — **re-measure, never
assume.** **Append `*> $null` and read `$LASTEXITCODE`**; piping through `Select-Object -First N`
manufactures a non-zero exit. **Probe every pin anchored to any document you edited**, on both
sides: `doc_truth.documented_value` requires **exactly one** matching line, and
`pin_extractor_truth` reports green through a document-side failure.

---

## ENVIRONMENT TRAPS. Every one has already cost time.

- **Kiro autonomous mode forces the OS command sandbox on, with outbound network blocked**
  (https://kiro.dev/docs/sandbox/). Here it broke every shell command: `grant_rw` fails on any
  `fs_write` path in `~/.kiro/settings/permissions.yaml` that does not exist (undocumented), and
  sandboxed commands cannot read `~/.gitconfig` or the GitHub CLI config, so `gh` cannot start.
  The operator turned it off (`.kiro/settings/sandbox.json`, `enabled: false`, untracked and
  local; **never commit it**). Re-enabling needs fs_read grants for those paths and
  `sandbox_network` rules for github.com and api.github.com (https://kiro.dev/docs/permissions/).
- **Worktrees are invisible to tools rooted at the main tree.** `.claude/worktrees/` is
  git-ignored there, so a search from the main tree returns nothing for a worktree file. Open it
  by full path, or use `git -C <worktree> grep`.
- **`audit-supply` installs with `--frozen-lockfile=false`** (`frontend.yml`), so its verdict
  judges `package.json`'s resolve, not the committed lockfile. The lockfile is proven by the
  `regen-lockfile` run whose artifact is committed unedited.
- **Labelled-run logs are huge:** E5's job log was 556 MB (4.4 M lines), and a controls leg's did
  not finish downloading in 10 minutes. Stream them to disk (STEP 0), never into memory.
- **Visibility can change without a diff:** private around 2026-11-01 05:40Z (an unauthenticated
  404 on the API and the PR page), public again by the operator, 0 billable ms that day.
- **A per-test regex over a job log must allow spaces in parametrised test ids.**
- **The line-ending trap fires on programmatic edits.** Normalise to the file's dominant
  **worktree** ending, measured from Python at `newline=''` — `.github/workflows/*.yml`,
  `blocking-steps.yaml`, `required-checks.yaml` and `ratchets.json` were CRLF when last read, and
  in the ledger worktree `tasks.md`, `SESSION_PROTOCOL.md`, this file and `HANDOFF.md` read
  `i/lf w/crlf` before session 13's edits. **The `i/lf` column misleads** (finding 33). Check
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
  git config unchanged. **Push to the PR's own branch, never to `main`.** A worktree branch with
  no upstream is pushed with an explicit refspec.
- **A code PR never edits `tasks.md`:** its discharges and findings go in a ledger PR. Two PRs
  that edit one file (`uplift.yml` is edited by #87 and by parent 33's 33.5) merge `main` before
  the second merges.

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
traced to the seed sets. **E5 ended session 12 honestly:** task 25's claim is negative,
`baseline_wins` against E, because no agent read its request (finding 112). **Session 13 repaired
that cause** (parent 31): E5 on the repaired arm dispatched every decision and still read
`baseline_wins`, headline -1.446 against E (31.11). The claim and its cause are 31.12's. The
world is declared, not observed (1=a), so **every claim is a claim about the twin and must say
so.**

**The pre-commitment, made before the number was known, held and still binds, and 31.12 repeats
it for the repaired arm:** if measured uplift is null or negative, **it is reported as null or
negative.** The floor stays at `0.0`, no headline is published as a gain, and the result is
written up as a finding — not reframed, not re-run at a different replicate count until it moves.

Five guards on reading the result: no headline while no Power_Report describes the revision under
measurement (17.3); a null while any objective KPI is recorded not observably sensitive is
**inconclusive**, not confirmation (10.5); no `material` on a point estimate with no dispersion;
no verdict on a comparator that loses to its own subject (finding 54); and **no claim against the
incumbent arm — the baseline is the primary cell's tuned control E** (D2.7, task 25).

---

## Session 13 in one paragraph — the rest is in `HANDOFF.md`

**PRs #84 and #85 merged by merge commit; the consensus now reads its request; E5 on the repaired
arm reads `baseline_wins`.** The operator commissioned three things (S13.1=a to S13.3=a),
registered as parents 30 to 32, with parent 33 for owed gate defects. PR #87 repairs finding 112
and the consensus arm's two dials (findings 116 and 121). A comment edit had voided the B-prime
record (finding 122), so the controls measured nothing until `8775a89` restored it; the re-run
held, its Power_Report is committed unedited (`4b659e6`), and E5 on the repaired arm dispatched
every decision and read headline -1.446 against E (31.11). The claim is 31.12's. PR #89 repairs
the Frontend CI reds: round 1 read `audit-supply` and Stryker green, and round 2 was red on
three new findings (129 to 131) and on finding 114's LCP. CD-GCP has not authenticated since at
least 2026-08-17 (finding 123). **Four numbers:** leaves discharged 32; core-seconds,
CI critical path and agents not recorded. **Not verified:** the repaired arm's claim, whether the Sentinel
bound the pathway probe's decisions, PR #89's round 3, parent 33's CI.
