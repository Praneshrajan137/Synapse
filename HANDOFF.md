# HANDOFF — decision-quality-proof

**State at end of session 13 (2026-11-01 to a closing date not recorded (last written 2026-11-15 by file time; committed 2026-11-18)).** PR **#84** merged as
`cd32c9d` and PR **#85** as `d4f985c`, both by merge commit (operator decision S13.1=a), so
`main` holds sessions 1 to 12 and ADR-057. Session 13's own work rides four branches. Two have
open PRs, two PRs were not yet opened when this was written, and none is merged:

| PR | Branch | Newest head read | State when written |
|---|---|---|---|
| #87 | `fix/consensus-reads-request` | `4b659e6` | open; CI green at `4b659e6`; the controls and E5 reported (31.10, 31.11), E5's headline -1.446 `baseline_wins`; the claim pending in 31.12; merging needs the operator |
| #89 | `fix/frontend-gates` | `50deebc` | draft; round 2 red: findings 129 to 131 in repair, and `e2e` red on finding 114 (decision (e)) |
| not yet opened -> #90, opened 2026-11-14 | `fix/owed-gate-defects` | `860c62e` | parent 33's PR |
| not yet opened -> the pull request opened with this commit, 2026-11-18 | `docs/dqp-session-13` | the commit carrying this file | the ledger, this file, the prompt, the progress row |

Code PRs do not edit `tasks.md`; the ledger PR records their discharges.

**This file is DERIVED and short.** Per `.kiro/steering/throughput-with-integrity.md`, every finding
has **one canonical home** — the ADR for design facts, the task body for ledger facts — and this
file carries **state, pointers and the honesty ledger only.** Follow the pointer; no reasoning is
repeated here. A finding number resolves to its body with
`git grep -n "FINDING <n>" -- .kiro/specs/decision-quality-proof/tasks.md`.

**The census is a command, not a number in this file:**

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

It reported `155 / 130 / 0 / 25` and `complete: yes` at session 12's close. Parents 30 to 33,
registered this session under conflict X's resolution, add open leaves, so it no longer reads
complete: `200 / 162 / 0 / 38` (open: 0 authorable, 12 CI-gated, 26 deferred; 0 unharvested), `complete: no`, exit 0, read by truth session 3 on 2026-11-18 at `d4f985c` with these four files; 162 done against 130 at session 12's close. Its `absent-artifact` lines name files of the then-unmerged PRs #87 and #89. **32 leaves discharged.**

---

## The headline

### 1. PRs #84 and #85 are merged, by merge commit (parent 30)

`cd32c9d` (parents `045f44c`, `6ff4973`) and `d4f985c` (parents `cd32c9d`, `b8d6a48`), each on
required checks read green at its head. #85 was synced with `main` by a merge (`05b72e2`), and
its harness repair (`b8d6a48`) turned `e2e-harness` green. Records: parent 30.

### 2. The consensus reads its request; E5 on the repaired arm reads `baseline_wins` (parent 31)

PR #87 repairs finding 112 in all eight handlers, has the Inventory Sentinel plan against the
state its request carries (ADR-058), and closes the consensus arm's two dials (findings 116 and
121). The labelled controls first refused in every leg, because a comment edit had voided the
B-prime record (**finding 122**). `8775a89` restored the file, the re-run held (31.9, 31.10),
and its Power_Report is committed unedited as `4b659e6`. E5 at `4b659e6` (run 41352100304)
dispatched every decision, where session 12's E5 read 24000 of 24000 `untranslatable`, and its
headline is **-1.446, `baseline_wins`**, against E (31.11). **The claim and its cause are owed
in 31.12, and whether the Sentinel bound the pathway probe's decisions is not read yet (31.11).
Task 25's claim stands as stated.**

### 3. PR #89's round 2 is red on three new findings and on finding 114 (parent 32)

Round 1 (`4efa397`, run 41334119693): `audit-supply` green on zod 4.6.7, Stryker green, and
`e2e` red on finding 114's LCP. Read locally over round 1's records, finding 90's repair would
have turned FE-INV-010 into a false pass (**finding 124**), which `50deebc` repairs. Round 2
(`50deebc`, run 41344870270): `build`'s blocking size step green (32.7); `storybook-a11y`'s
first run red on colour contrast (**findings 130 and 131**); all five `e2e-harness` legs red on
Req 10.1 (**finding 129**); and `e2e` red on finding 114 again. `fe-invariants` and the
ratchet were skipped, so neither has run in CI on this PR. The repairs of findings 129 to 131
were in authoring when this was written. **Finding 132**, read in the checker, is registered
beside them.

### 4. CD-GCP has failed to authenticate on every run since at least 2026-08-17 (finding 123)

Every cd-gcp run read fails at Workload Identity Federation (`invalid_target`); the newest
auto-issue is #86. The provider is the operator's to repair. Inferred, not probed: nothing
merged since the failures began is deployed, PR #85's repair of finding 89 included.

---

## Binding decisions — pointers only

- **Session 13's operator decisions S13.1=a, S13.2=a and S13.3=a, and conflicts W and X:**
  `tasks.md`, the opening paragraph of Phase 8. Conflict W's resolution covers the merges of
  #84 and #85 only.
- **The session-11 re-cut** (1=a, 2=a, 3=a/c/d/e, Q1=a, Q2=a, Q3=c): R5.46, ADR-055 **D2.8**,
  task 29. A `deferred:` leaf is terminal.
- **No claim against the incumbent arm:** the baseline is the primary cell's tuned control E
  (ADR-055 D2.7; task 25's re-scope). 31.12's pre-commitment is written under it.
- **Task 25's claim stands as stated.** The repaired arm's claim goes in 31.12, a new task.
- **On PR #87's branch the committed Power_Report describes the tree E5 measured** (`4b659e6`,
  31.10). An edit to any `POWER_SOURCE_SET` file voids it until the controls re-run.
- **The B-prime record binds `BPRIME_PHYSICS_SET`, comments included** (finding 122): an edit
  there voids the record until B-prime is re-measured.
- **ADR-058** (the Sentinel reads its request) is on PR #87's branch and **ADR-059** (the
  ratchet's median of five legs) on PR #89's.
- **Unchanged:** conflict U adopted (task 16.7); steering G8; the M5 terms declined (C74); 23,
  20.3 and 21 deferred to named, uncreated specs.

## Open operator decisions — surfaced, NOT resolved

| | Decision owed | Finding |
|---|---|---|
| (b) | The sweep's PASS-baseline branch credits an abstention or a crash; C69 is the measured case. | 85 |
| (d) | Arm D's "pointwise best" claim: restate it as unmet-pointwise-least, or make D cost-optimal, **before** E3 cites D as a bound. | 79 |
| (e) | Lighthouse LCP at `warn` or `error`, with the 2500 ms budget inside runner variation. New: the zod 4 build read 2728 and 2672 ms in round 1 and 2556 and 2608 ms in round 2, all inside the zod 3 builds' 2100 to 3100 ms; four samples against eleven establish no shift (parent 32's round 2). zod 4 adds 13.8 KiB gzip to the eager set (26.2 against 12.4). | 95, 114 |
| S | The negative control is judged on gains only (task 16.4). | 101 |
| V | The agreement rule under proven per-seed identity, which clause (f) measured at P5. | 117 |
| | The reorders-only lever set for E5 and the controls: the main agent's choice, the operator's to overturn. | none |
| | The chromatic race, ADR-025's owner's call. | 106 |
| new | ADR-058's open items O1 to O5: refusing on absent state, the `SKU001` default, the sensor's `world_inventory`, the review period for other callers, and the lead-time prior. | ADR-058 |
| new | CD-GCP's Workload Identity provider `github-aegis15`: operator-owned, outside the repository. | 123 |
| new | Whether a PR-time check should read the B-prime record against the tree. | 122 |

**Resolved in session 13 by the operator:** (a) by S13.2=a (a median of five legs, ADR-059);
(c) by S13.1=a (PR #85 merged; it reaches the live console only once finding 123 is repaired);
finding 112's repair by S13.3=a; finding 105's zod 4 migration by S13.2=a.

**Owed work, not decisions:** 31.12, the repaired arm's claim, and the reading of whether the
Sentinel bound the pathway probe's decisions (31.11); parent 32's round 3, carrying the repairs
of findings 129 to 131; finding 132; enforcers for FE-INV-013 and FE-INV-024 (32.6, 32.9);
parent 33; finding 91, on which FE-INV-011's attestation rests (32.5); finding 118 (Stryker's
run time; Stryker passed at `4efa397` and `50deebc`); finding 127 (cause unknown); and finding
119's remainder, F-A3-1's `foresight.py` half, F-F-1, F-F-2 and F-Q1-4 (parent 33's notes).

## CI state, read from the runs

- **`main`:** at `cd32c9d`, CI 41311346965, Truth Gates 41311346956, Mutation 41311346963,
  Policy 41311346973 and SYNAPSE CD 41311347001 `success`; Frontend CI 41311346948 red on
  `audit-supply` (105); CD-GCP 41311346932 red in all 12 build legs (123). At `d4f985c` (#85's merge): CI 41332856943, Truth Gates 41332857284 and SYNAPSE CD
  41332856912 `success`; Frontend CI 41332856903 red on the supply-chain audit and CD-GCP
  41332857094 red, as at `cd32c9d`.
- **PR #87:** at `4b659e6`, CI 41350755590 (every job), Truth Gates 41350755567, Integration
  41350755554 and Policy 41350755600 `success`; CI 41333699137 was green at `1432cda` (the job
  ids are in parent 31's notes). Labelled: the cost probe 41332722823 `success` (31.7); the
  controls 41340385366 refused in every leg (122); the controls re-run 41343879850 at
  `8775a89`, all 22 jobs `success` (31.8 to 31.10); E5 41352100304 at `4b659e6` `success`
  (31.11).
- **PR #89:** round 1, Frontend CI 41334119693 at `4efa397` (parent 32's notes); the lockfile
  run 41334142786 `success`. Round 2, Frontend CI 41344870270 at `50deebc`: red on
  `storybook-a11y` (130, 131), on all five `e2e-harness` legs (129) and on `e2e` (114), with
  `fe-invariants` and `effectiveness-ratchet` skipped (parent 32's notes). Round 3:
  Frontend CI 43575491177 at `9c53859` (2026-11-14): red on `storybook-a11y`, the
  visual-regression gate, all five `e2e-harness` legs and `e2e`; Stryker cancelled; 8 jobs
  green, 2 skipped. After it: 43620027327 (`59610a9`), 43628798777 (`fb6340e`) and
  43631919800 (`9da8ceb`), the last red on `e2e` alone with 17 jobs green and 1 skipped.
- **Parent 33's PR:** not opened when this was written. -> #90, opened 2026-11-14 at `860c62e`: CI 43575474162, Truth Gates 43575474166 and
  Integration 43575474160 `success`; Security Scan 43575474224 `success` (dispatched).
- **Hazards, unchanged:** a newer push cancels an older head's in-progress run where a workflow
  declares `cancel-in-progress`; re-running an older run cancels the newer one's job (115);
  `uplift.yml` is label-only and never cancels in progress.

---

## Honesty ledger

### Executed and measured

- **The merges:** each PR's required checks read green at its head before it merged (parent 30).
- **PR #87's CI** at `1432cda` and at `4b659e6`, and its first run's red, which found finding 121.
- **The cost probe's E5 mode**, run 41332722823: E5's path timed and tallied (31.7).
- **The controls' refusal**, run 41340385366, and its repair measured locally: the physics digest
  back to `dbedae9d...`, and the record accepted (finding 122).
- **The controls re-run** (41343879850) and **E5 on the repaired arm** (41352100304), each read
  from its own artifact (31.8 to 31.11), and the Power_Report's `describes_revision` measured
  locally at `4b659e6` (31.10).
- **PR #89's round 1**, and the repaired FE-INV checker run locally over round 1's own records
  (findings 124 and 125). **Round 2** (run 41344870270), which measured findings 129 to 131.
- **Mutations killed locally:** finding 121's clause with its repair removed, and finding 90's
  checker with its `rootDir` resolution removed.

### The four throughput numbers (steering G6)

- **Leaves DISCHARGED: 32** against a target of **>= 11.** The ledger marks `[x]`
  30.1 to 30.4, 31.1 to 31.11, 32.1 and 32.2, seventeen leaves, and no `[~]` remains
  (the census at this commit: 162 done against 130 at session 12's close, so 32,
  including 31.12 and leaves of parents 32 and 33 marked after this was written; each was
  not re-read against its naming job by truth session 3).
- **Core-seconds: not recorded.**
- **CI critical path: not recorded.**
- **Agents: not recorded.**

### G6, G7 and G8

- G6 met: 32 against >= 11, by the census. G7 and G8 not recorded.
- **Prediction misses, recorded as misses:** CD-GCP on #84's merge (123); Stryker on PR #85
  (120, under a second seed); C2, the Tier-2 cost, whose old figure carried finding 116's
  lookup; K1, the controls (122); round 1's type errors, a miss in the safe direction; K2 as
  worded and K3 by one field, the controls re-run (31.10); E3, two pathway inputs unresponsive
  (31.11); and round 2's `e2e-harness` (129). **One miss of procedure:** E5's label went on
  three minutes before the CI it waited for had completed (31.11).

### NOT verified. Must not be claimed.

- **The repaired arm's claim** (31.12) (since stated: 31.12 is marked done with the claim, -1.4463, interval [-1.4650, -1.4286], `baseline_wins`, read from run 41352100304),
  and **whether the Inventory Sentinel bound the pathway probe's decisions**, so whether
  ADR-058's falsification item 1 fired (31.11).
- **PR #89's round 3**: not run. `fe-invariants` and the five-leg ratchet have never run in
  CI, and the repairs of findings 129 to 131 are unmeasured.
- **Parent 33's work, and the FE-INV-013 and FE-INV-024 enforcers,** had no commit when the
  ledger was written; uncommitted edits were in progress in their worktrees.
- **Truth Gates, Integration and Policy at `1432cda`**, and **CI at `8775a89`**: not recorded.
  The runs at `4b659e6` were read instead (parent 31's runs).
- **That the zod 4 build moves LCP:** four samples against eleven (parent 32's round 2).
- **Inferred:** finding 123's consequence (nothing deployed since the failures began), finding
  126's CSP report (no CI job serves the production CSP), finding 129's Chromium step, finding
  131's cause and finding 132's consequence. **Not known:** finding 127's cause.
- **That FE-INV-011's attestation covers any route but `/login`** (finding 91; 32.5).
- **That the declared world describes a real store** (1=a: fidelity `unknown`, C60
  `unavailable`).

---

## What session 14 does

Read the newest runs on each PR (STEP 0 of `NEXT_SESSION_PROMPT.md`) and harvest every leaf
whose discharge job has reported (G4). If 31.12 still carries its placeholder, read first
whether the Inventory Sentinel bound the pathway probe's decisions (31.11), then state the
repaired arm's claim from run 41352100304's artifact, with its cause beside it and task 25
untouched. Harvest PR #89's round 3 (parent 32) and parent 33's CI, and put the open decisions.
Merging #87, #89 or parent 33's PR changes `main`, and conflict W's resolution covered #84 and
#85 only, so ask first.

## The lesson

**A digest names bytes, not behaviour, and a record no check reads is not protected.** A comment
edit voided the B-prime record while CI stayed green, and the first reader was a labelled run
(finding 122). **A repair that lets a checker see more must re-read every listing it newly
sees:** finding 90's repair would have attested FE-INV-010 from tests that assert no vital
(finding 124). **A test proves only what its environment contains:** the laptop has no
codecarbon, so only CI could see the arm's second dial (finding 121).
