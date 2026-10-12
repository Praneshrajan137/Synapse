# HANDOFF — decision-quality-proof

**State at end of session 11 (2026-09-29 to 2026-10-12).** Branch `feat/decision-quality-proof`,
PR **#84** open against `main`. The commit carrying this file — **P2**, the documents push — also
carries `NEXT_SESSION_PROMPT.md` and `SESSION_PROTOCOL.md`'s session-11 row and batch table.
**P1** (`ba02a1b`) was planned as one confirmation push and took three: **P1b** `5c2f2b3` repaired a
Node-engine refusal it shipped (finding 93), and **P1c** `0745290` repaired a latent harness race
its timing exposed (finding 94). **The repository is PUBLIC again** (operator, 2026-10-02):
standard runners are 4-vCPU and Actions minutes are unmetered.

**This file is DERIVED and short.** Per `.kiro/steering/throughput-with-integrity.md`, every finding
has **one canonical home** — the ADR for design facts, the task body for ledger facts — and this
file carries **state, pointers and the honesty ledger only.** Follow the pointer; no reasoning is
repeated here. A finding number resolves to its body with
`git grep -n "FINDING <n>" -- .kiro/specs/decision-quality-proof/tasks.md`.

**The census is a command, not a number in this file:**

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

It reported `147 / 92 / 2 / 53` at session 10's close and `155 / 106 / 0 / 49` at this session's
close (22 authorable, 2 CI-gated, 25 deferred, `unharvested: 0`). **14 leaves discharged.** The
re-cut added task 29's leaves and made every `deferred:` leaf terminal (task 29.1), so neither the
`done` delta nor the total's delta is the discharge count.

---

## The headline

### 1. Checkpoint B-prime PASSED — `room_to_win` in the primary cell

Canonical record **ADR-055 D2.9**; the P1–P5 scorecard is **task 14**. Uplift Proof run
`36860454801`, sha `ec0eb91`. Information ceiling E − D `0.630`, out-of-sample `[0.596, 0.666]`,
in-sample `[0.595, 0.664]` — both wholly above the committed `0.40`, so the rule committed before
the run binds. **E3 and E5 are licensed by measurement.** P5 failed on one clause in three
descriptive cells and is recorded as failed (**finding 79**): its error direction is conservative,
and a restatement is owed before E3 cites arm D as a bound.

### 2. 14 leaves discharged against a target of >= 11

12.1, 12.2, 13.1, 13.2, 13.7, 14, 16.1, 20.7, 20.8, 29.1, 29.2, 29.3, 29.7, 29.8 — each on its
naming job's own run, recorded in its `DISCHARGED:` line.

### 3. The falsification sweep passes for the first time

Truth Gates run `38287788451` (`ba02a1b`, task 29.7): 16/16 operators probed, all 14 checks
falsified, the four SKIP baselines admitted by R1.5a. **One prediction missed:** C69 is counted on
an abstention, not a FAIL (**finding 85**, now measured) — so "14 falsified" overstates by one until
its operator changes.

### 4. E5 is fundable

`25.9 s` per Tier-4 consensus decision and `518.6` core-hours at `MIN_SCENARIOS`, about 26
five-hour jobs at four workers (finding 70, ADR-055 D2.9) — measured on the private 2-vCPU class.
Public runners are unmetered and run jobs in parallel, which is what makes the run affordable.

---

## Binding decisions — pointers only

- **The session-11 re-cut:** operator decisions **1=a, 2=a, 3=a/c/d/e, Q1=a, Q2=a, Q3=c**, listed
  once in `requirements.md` R5.46; design ADR-055 **D2.8**; the re-cut's own leaves are task 29.
  A `deferred:` leaf is terminal and carries its reason in that line.
- **Still binding from session 10:** no claim may be denominated against the incumbent arm. The
  honest baseline is the tuned control **E**, re-derived per cell by task 13.7's committed search;
  task 25's re-scope names E of the primary cell. **17.2 and 25 sit under this prohibition.**
  Reasoning: ADR-055 D2.7.
- **Declined, or deferred to specs that are named and NOT created:** the Kaggle M5 terms (C74
  non-passing by decision); task 23 → `.kiro/specs/external-audit-anchor/`; 20.3 and 21 →
  `.kiro/specs/forecaster-publication/` (3=c).
- **The repository went public again** after a pre-publication secrets audit (finding 80).
- **Taken under the operator's delegation of 2026-10-02:** maplibre-gl 6 (finding 83); the
  frontend toolchain on Node 22.23 LTS (finding 93).

## Open operator decisions — surfaced, NOT resolved

| | Decision owed | Finding |
|---|---|---|
| (a) | The effectiveness ratchet's latency tolerance against its measured noise. Red **by design** until then; a strict A/A (re-run `e2e-harness` once on one sha) is the next measurement. | 88 |
| (b) | The sweep's PASS-baseline branch credits an abstention or a crash. C69 is the measured case; its operator could re-tick a record instead. | 85 |
| (c) | **Live exposure — ask about it first.** The deployed console signs every visitor in as admin (`frontend/src/surfaces/auth/useBootAutoLogin.ts`), and its default credential is compiled into the public bundle. | 89 |
| (d) | Arm D's "pointwise best" claim: restate it as unmet-pointwise-least, or make D cost-optimal — owed **before** E3 cites D as a bound. | 79 |
| (e) | Lighthouse asserts LCP at `warn`. LCP now passes the spec's own budget (2292 ms, one sample), so flipping it to `error` is cheaper than it was. | 86 |

**Owed work, not decisions:** **92** (the 14 lazy routes have no failed-chunk state — **before
PR #84 merges**); **91** (the smoke a11y matrix has only ever scanned `/login`); **90**
(`fe-invariants`' unobservable set, and its path-matching defect — the owner's); **93's tail** (two Node 20 pins that install nothing
frontend); forbidding `viz-`/`visx-` in the entry-preload guard now that a CI table shows them
absent.

## CI state, read from the runs

- **Required checks green at `ba02a1b` and `5c2f2b3`:** SYNAPSE CI (`quality-gates`,
  `uplift-verify`) and Truth Gates (`truth-gates`, `falsification-sweep`). Integration, Mutation,
  Security, Policy and Terraform `success` at `5c2f2b3`.
- **Frontend CI run `38291036628` (`5c2f2b3`):** `e2e` 21 passed / 0 failed / 8 skipped (19/1/8 at
  `5eef6ee`); `mobile-reality` "/" LCP **2292 ms** (CLS 0, INP 112 ms) — one sample; the
  entry-preload guard passed with exactly the five predicted eager chunks, 240.8 KiB gzip against
  916.6 KiB before (finding 86); `audit-supply` green and `map-worker.spec.ts` passed (finding 83);
  quality, build, visual, Lighthouse, license, SBOM, spec-typecheck, contract-fidelity green.
  `e2e-harness` failed there (finding 94).
- **At P1c (`0745290`, Frontend CI run `38293903740`):** `e2e-harness` `success` (run `38293903740`), finding 94's
  repair holding; `effectiveness-ratchet` `failure`, on exactly the R8.10 rejection read at `5eef6ee` — red by design (88); `fe-invariants`
  ran for the first time and FAILED: six declared-unobservable invariants plus six top-level e2e
  specs a path-matching defect misreads as never executed (90); Stryker `success` (28.4 min). Every
  other workflow green.
- **Path filters on `pull_request` read the PR's whole diff against `main`**, so every push to
  PR #84 — documents-only included — runs Frontend CI and Mutation Testing, and with
  `cancel-in-progress` a newer push cancels the older head's run. **Never push while a run you
  need is in flight.**

---

## Honesty ledger

### Executed and measured

- **B-prime:** eight cells × 200 replicates, split residual `0.0` in each (D2.9); cost probe run
  `36860581054`.
- **Every CI number above**, each read from its own job, log or artifact.
- **The pre-publication secrets audit:** 132 remote refs, 439 commits, ~528k added lines —
  **0 high-confidence hits**, 56 low-confidence, all dev defaults.
- **Every discharge**, read per test id or per artifact field as its `DISCHARGED:` line states.

### The four throughput numbers (steering G6)

- **Leaves DISCHARGED: 14** against a target of **>= 11.**
- **Core-seconds: ~1,900–2,400, ESTIMATED**, all single-process: ~430 for the last segment from
  command wall times, 1,500–2,000 estimated for the earlier segment, which was not metered per
  command. No repo-wide run, no `--cov`, no `-n auto`, no pnpm/Playwright/tsc locally.
- **CI critical path: 151 min** from push to required-checks-done over seven pushes (30.6,
  27.6, 18.6, 26.4, 16.2, 15.7, 15.8): ~16 min per push on public runners against ~26 on the
  private class. "All done" is set by Stryker: 28.4 min public, 46.2 min private.
- **Parallel agents: ~41 productive / 6–8 failed** on usage limits (the pre-summary dispatches were
  not logged one by one), beside exactly one executor.

### G6 and G7

- **G6 met. G7 met** — waves of 4–5 authoring agents beside exactly one executor.
- **Underperformed, named:** dispatches lost to usage limits; **three CI rounds where one was
  planned, and the confirmation push itself took three** (findings 93 and 94).

### NOT verified. Must not be claimed.

- **That LCP holds** — 2292 ms is one sample with 208 ms of margin.
- **That a drawn map renders tiles** — `map-worker.spec.ts` proves the worker boots; CI serves no
  tiles, so no check sees a decoded tile.
- **That consensus captures any of the ceiling** — E5's question, unmeasured.
- **That the declared world describes a real store** — every value is `chosen` (1=a); fidelity is
  `unknown` and C60 `unavailable` by decision.
- **That the ceiling is the EVPI** — it is a lower bound (D2.9).
- **Finding 89 on the live console** — read from source, not probed.
- **Findings 77 and 82** — read, not executed; other owners'.
- **Finding 94's interleaving** — the mechanism is read in query-core; why P1's timing exposed it
  is inferred.

---

## What session 12 does

Raise finding 89 first. Then the census's authorable list, **re-derived with `--next 40`** (at
close: `15.1`, `15.2`, `15.4`–`15.6`, `16.2`, `16.4`–`16.7`, `17.1`–`17.4`, `19.4`, `22.1`,
`22.2`, `24.1`, `24.2`, `29.4`–`29.6`), and finding 92 before PR #84 merges. Barriers **25**
(`uplift.yml::uplift-proof`) and **26.5** (`regenerate-truth-docs.yml::regenerate`) are CI-gated.
`NEXT_SESSION_PROMPT.md` carries the procedure, a coupling partition and the stop conditions.

## The lesson

**A premise can go false without a diff.** `execution-routing.md`'s "free and unmetered" was false
for as long as the repository was private, and it was found by measuring runner speed, not by
reading the file (finding 80). **A measured baseline is not automatically an honest one:** when the
measurement's own noise exceeds the tolerance, committing it trades a true red for a false one
(finding 88). **And a confirmation push is only as good as the closure it read:** P1 read
maplibre's own `engines` and not its transitive tree (finding 93).
