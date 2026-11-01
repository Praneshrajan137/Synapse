# HANDOFF — decision-quality-proof

**State at end of session 12 (2026-10-15 to 2026-11-01).** Branch `feat/decision-quality-proof`,
PR **#84** open against `main`. The commit carrying this file, **P6**, also carries
`NEXT_SESSION_PROMPT.md`, `SESSION_PROTOCOL.md`'s session-12 row and the ledger edit that
discharges 22.1 and 25. Earlier commits, oldest first: `e5d43c1` (A/A and LCP pre-registration),
`d8aafe6` (P1), `b3a98a8` (P2), `2b82e03` (steering G8), `af950f3` (P3), `209c6dc` (P4),
`732ecd9` (P5). **E5's re-run, run `41289052859` at `732ecd9`, completed, and task 25's claim is
stated in its body (headline 1).** The repository was observed private around 2026-11-01 05:40Z
and made public again by the operator; the run-timing API reports 0 billable ms for every run
that day.

**This file is DERIVED and short.** Per `.kiro/steering/throughput-with-integrity.md`, every finding
has **one canonical home** — the ADR for design facts, the task body for ledger facts — and this
file carries **state, pointers and the honesty ledger only.** Follow the pointer; no reasoning is
repeated here. A finding number resolves to its body with
`git grep -n "FINDING <n>" -- .kiro/specs/decision-quality-proof/tasks.md`.

**The census is a command, not a number in this file:**

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

It reported `155 / 106 / 0 / 49` at session 11's close (22 authorable, 2 CI-gated, 25 deferred)
and `155 / 130 / 0 / 25` at this session's close (0 authorable, 0 CI-gated, 25 deferred,
`unharvested: 0`, `complete: yes`). **24 leaves discharged.** Every open leaf is `deferred:`, and
a `deferred:` leaf is terminal, so **the spec is complete.**

---

## The headline

### 1. E5 completed; the claim is stated, negative, in task 25's body

The claim is stated once, in **task 25's body** (`tasks.md`, "THE CLAIM (2026-11-01)"); this file
quotes its headline sentence only. On the declared twin's primary cell, unshocked, the consensus
arm's recommendations, if executed, cost 4.40 objective units more per 24-hour replicate than the
tuned control E: headline **-4.4026**, 95% interval **[-4.4218, -4.3843]**, verdict
**`baseline_wins`**. The pre-commitment held: the number is reported as negative, its cause beside
it (**finding 112**), never relabelled. Every E5 prediction, registered before the push, held
(parent 29, "MEASURED at P5").

### 2. 24 leaves discharged against a target of >= 11

Harvested at P2: 15.1, 15.2, 15.4–15.6, 16.4–16.6, 17.1, 17.2, 17.4, 29.4, 29.5. At P3: 16.2,
19.4, 22.2, 24.1, 24.2, 26.5. At P5: 16.7, 17.3 and 29.6, then 22.1 and 25 on P5's own runs,
recorded at P6. Each on its naming job's own run, in its `DISCHARGED:` line.

### 3. The controls ran, the Power_Report is committed, and clause (f) passed

Controls run `41268743674` (`209c6dc`): negative `pass`, positive `detected` (E - O
`[0.1875, 0.2200]`), and arms E, E' and O reproduced B-prime exactly. The Power_Report (MDE
`0.0235` at n = 1000) is committed as `docs/state/uplift-power-report.json`, and its harness
revision equalled the tree's `POWER_SOURCE_SET` digest at P5 (measured). **Agreement reads
`harness_mis_measuring` (finding 117), and the verdict stands as recorded:** clause (f) passed at
P5, so the gap is the seed sets'. Records: `tasks.md`, parent 29, "MEASURED at P4", and finding
117's "MEASURED at P5".

### 4. Finding 89 has a draft PR

**PR #85 (draft)**, `fix/open-access-mode` @ `828742e`, cut from `main` `045f44c`, worktree
`.claude/worktrees/open-access`: open preview access now, sign-in built and dormant (ADR-057 on
that branch). Its CI, the first execution of its vitest and Playwright changes, was not read when
this was written. It overlaps PR #84 in `CLAUDE.md`, both compose files and
`orchestrator/inference/serve.py`; whichever merges second rebases.

---

## Binding decisions — pointers only

- **The session-11 re-cut** (1=a, 2=a, 3=a/c/d/e, Q1=a, Q2=a, Q3=c): R5.46, ADR-055 **D2.8**,
  task 29. A `deferred:` leaf is terminal.
- **No claim against the incumbent arm:** the baseline is the primary cell's tuned control E
  (ADR-055 D2.7; task 25's re-scope), and task 25's claim is stated under it.
- **The committed Power_Report binds `POWER_SOURCE_SET`:** moving the digest voids it. The claim
  is published, so finding 116's code repair may land now; a new claim after it needs the controls
  re-run.
- **Conflict U adopted** (task 16.7): the labelled jobs are filed
  `ineligible/conditioned-off-pull-request`, and the operator may object.
- **Steering G8:** authoring agents in alternating batches of at most five, then at most three.
- **Unchanged:** the M5 terms declined (C74); 23, 20.3 and 21 deferred to named, uncreated specs;
  maplibre-gl 6 (83) and Node 22.23 (93) under the 2026-10-02 delegation.

## Open operator decisions — surfaced, NOT resolved

| | Decision owed | Finding |
|---|---|---|
| (a) | The effectiveness ratchet's tolerance against its measured noise; red **by design** until decided. The strict A/A ran and AA1–AA3 held (`tasks.md`, "SESSION 12, 2026-10-15"). | 88 |
| (b) | The sweep's PASS-baseline branch credits an abstention or a crash; C69 is the measured case. | 85 |
| (c) | **Live exposure:** the deployed console signs every visitor in as admin. Its repair is PR #85 (draft), for the operator to review, merge and activate. | 89 |
| (d) | Arm D's "pointwise best" claim: restate it as unmet-pointwise-least, or make D cost-optimal, **before** E3 cites D as a bound. | 79 |
| (e) | Lighthouse LCP at `warn` or `error`. New evidence: `error` turns `mobile-lighthouse` red (95), and the 2500 ms budget sits inside runner variation (114); at P5 it read inside budget. | 95, 114 |
| new | The claim's cause: every agent reads its request one level too shallow. Its repair lies outside decision 3=a, so commissioning it is the operator's. | 112 |
| new | Conflict S: the negative control is judged on gains only (task 16.4). | 101 |
| new | Conflict V: the agreement rule under proven per-seed identity, which clause (f) measured at P5. | 117 |
| new | The reorders-only lever set for E5 and the controls: the main agent's choice, the operator's to overturn. | none |
| new | The zod 4 migration. | 105 |
| new | The chromatic race, ADR-025's owner's call. | 106 |

**Owed work, not decisions:** 116's code repair (allowed now; it voids the Power_Report, so the
controls re-run before any new claim); 118 and 120, both Stryker's (118's next measurement is one
Stryker run on `src/lib/universal-state.ts` alone, in CI); 119's small defects; 90 and 91 (other
owners', from session 11).

## CI state, read from the runs

- **P4 (`209c6dc`):** CI `41268715083` held in full (slow selection 98 of 98) and Truth Gates
  `41268714944` read `success` on both jobs. Frontend CI `41268714970`: `e2e` red on LCP (114),
  `audit-supply` (105) and `effectiveness-ratchet` (88, by design); Stryker timed out (118).
- **P5 (`732ecd9`):** CI `41289022422` `success`: G5's partition exact, the slow selection 99 of
  99, clause (f) among them. Truth Gates `41289022401` as at P4; Mutation `41289022389`, Policy
  `41289022451`, Integration, Security and Terraform `success`. Frontend CI `41289022398`: `e2e`
  passed (21 passed, 8 skipped; 114's LCP inside budget); `audit-supply` (105),
  `effectiveness-ratchet` (88) and `fe-invariants` (90: the same six `not_executed`,
  `ATTESTED=60`) red; Stryker red in its dry run on the key `__proto__` (120), not on time.
- **P6 (this commit):** documents only; its CI had not run when this was written. Expect it as at
  P5.
- **Labelled:** controls `41268743674` (22 jobs `success`); E5 `41268752414` (`failure`, at its
  bound); E5 `41289052859`, job `124796295692` (`success`; the supervisor `completed` after
  3646.5 s).
- **Hazards:** a push to PR #84 runs Frontend CI and Mutation Testing, and `cancel-in-progress`
  cancels the older head's run; re-running an older run cancels the newer one's job (115).
  `uplift.yml` is label-only and never cancels in progress: a push cannot cancel its runs (read).

---

## Honesty ledger

### Executed and measured

- **The controls, and E5 at P4 and at P5**, from their artifacts and logs; E5's 556 MB log at P4
  was profiled gap by gap (116). E5 at P5 yielded task 25's numbers, and every E5 prediction held.
- **Clause (f)**, in P5's slow selection: passed at the positive range's first three seeds, so
  finding 117's gap is the seed sets'.
- **The strict A/A** for (a), and the LCP samples behind (e) (95, 114).
- **The Power_Report's harness revision against the tree's digest**, at P5.
- **Five pre-registered CI rounds, P1–P5**, misses recorded as misses (parent 29); every CI number
  and every discharge read from its own job, log or artifact.

### The four throughput numbers (steering G6)

- **Leaves DISCHARGED: 24** against a target of **>= 11.**
- **Core-seconds: about 4,600, ESTIMATED**, single process, one executor: about 3,700 by P4 and
  about 900 on 2026-11-01 (three login-branch verifications, the E5 log profiling over 556 MB,
  scoped tests and gates). No repo-wide run, no simulation locally. The estimate predates E5's
  result; the reads after it are not added.
- **CI critical path:** five rounds (P1–P5) of about 20–25 min each to required checks; the
  controls about 25 min; E5 at P4 229 min, failing at its bound, and at P5 3646.5 s to
  `completed`.
- **Agents: 63 dispatched**, beside one executor, and **36 finished**. Dispatched (finished):
  the opening research, 18 read-only agents in two turns, r1 7 (2) and r2 11 (9); wider than
  five, d1 7 (0) and d2 11 (4); at most five, b1 5 (5), b2 5 (1) and b3 4 (4); under G8, B4 1 (1),
  R1+R2 2 (2), X1–X3 3 (3), two introspect queries 1 and 1 (both cancelled), Q1+Q2+introspect
  3 (3), and the documents agent D1 1 (1) with its amendment 1 (1).

### G6, G7 and G8

- **G6 met:** 24 against >= 11. **G7 met:** 63 dispatches beside one executor; wave 3 ran one
  agent (B4) because its work was one coupling closure, the probe into the E5 CLI (G7's stated
  exception).
- **G8 came from these losses:** dispatches wider than five finished 4 of 18, batches of at most
  five 10 of 14. Under G8, 13 were dispatched and 11 finished; the 2 cancelled were documentation
  queries, and none was lost to the usage limit.
- **Underperformed, named:** E5's first run produced no headline (116); P3 missed three
  predictions, P4 four (one the executor's own cancellation of Stryker, 115) and P5 two in the
  frontend: `e2e` passed, a miss in the safe direction, and Stryker failed its dry run (120).

### NOT verified. Must not be claimed.

- **P6's CI** had not run when this was written.
- **PR #85's vitest and Playwright changes never ran locally**; its CI is their first execution,
  and it was not read when this was written.
- **The core-seconds are estimated**, not metered per command.
- **Inferred:** finding 112's consequence (no consensus decision depends on the world), and the
  causes of findings 118 and 120. **Not known:** why the resolver slowed at 04:01Z (116).
- **That a drawn map renders tiles; that the declared world describes a real store** (1=a:
  fidelity `unknown`, C60 `unavailable`); **that the ceiling is the EVPI** (D2.9: a lower bound);
  **finding 89 on the live console** (read from source, never probed).

---

## What session 13 does

No leaf is left to discharge. Read P6's CI (documents only: expect it as at P5) and PR #85's CI.
Then surface task 25's claim to the operator with its cause (finding 112, whose repair lies
outside decision 3=a); put the open operator decisions; take the owed work in G8 batches; and lay
out PR #84's merge path (its required checks were green at P5) and PR #85's review, both the
operator's to decide. `NEXT_SESSION_PROMPT.md` carries the procedure, the plan and the stop
conditions.

## The lesson

**Read the log before naming a cause.** E5's first run spent its bound on a DNS lookup; logging,
the cause inferred before the log was read, was not the term (finding 116). **A comparison across
disjoint seeds can see only sampling once both paths agree per seed**, and clause (f) measured
that they do (finding 117), so a well-formed guard can be blind to the bias it is named for
(conflict V). **And dispatch width has a price:** batches wider than five finished 4 of 18
agents, which is why G8 exists.
