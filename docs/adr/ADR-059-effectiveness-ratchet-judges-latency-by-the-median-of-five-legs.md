# ADR-059: The effectiveness ratchet judges latency by the median of five legs

## Status
Accepted (2026-11-01). Operator decision S13.2=a. It replaces the one-run latency comparison of
the effectiveness ratchet (purpose-achievement-audit Req 4.3/4.4, R8.10). No earlier ADR is
superseded. The A/A predictions in "Pre-registered predictions" are stated before any baseline in
this design is committed, and are UNREAD until a run produces one.

## Context

**The gate as it stood.** PR #85's Frontend CI run 41321131601, job 124892919618
(`effectiveness-ratchet`), printed "Tolerance: steps +/-5%, latency +/-10%, errorRate +0.02,
interruptionPrecision -0.02", read "24 spec(s): 16 executed, 8 skipped, 0 reporting a failed test"
from the harness record, and failed on "Baseline: REJECTED": five `[missing-stamp]` findings and
one `[uniform-metrics]`. The committed baseline is still the placeholder, with `steps: 20` and
`latencyMs: 15000` on all five rows and no stamps. Those strings are quoted from the job log as
the dispatch for this ADR recorded them; this ADR did not re-read the log. The measured candidate
that job uploaded (`effectiveness-baseline-candidate`) came from ONE harness run.

**Why one run cannot carry the comparison (measured).** Finding 88
(`.kiro/specs/decision-quality-proof/tasks.md`) read two harness scorecards at seed 30000 on
consecutive commits that differed in latency by up to 94%. The strict A/A that followed re-ran
`e2e-harness` once on one commit (run 38298457463, sha `ecf517b`, attempt 2 job 116358160071):

- steps, errorRate, every row's seed and harness version were identical in both attempts, and
  interruptionPrecision read 0.75 in both (AA1);
- two of five latencies moved by more than the committed `latencyPct` of 0.10:
  identify-degraded-agent 65.0 -> 91.3 ms (+40.5%) and adjust-steering-safely 5.6 -> 4.7 ms
  (-16.1%). The other three moved 2.9% to 4.0% (AA2).

So a baseline committed from attempt 1 would have reported identify-degraded-agent as a regression
with no code change. The latencies are milliseconds of a scripted path on a shared runner, and
runner-to-runner noise exceeds a 10% band on them. Widening `latencyPct` is forbidden, and it
would blunt the gate on every row to absorb noise on two.

## Decision

**D1. Five legs.** `.github/workflows/frontend.yml::e2e-harness` is a `strategy.matrix` of legs
1..5 with `fail-fast: false`. Each leg runs the whole harness suite on its own runner. k = 5 is
`EFFECTIVENESS_LEG_COUNT` in `frontend/src/lib/effectiveness-ratchet.ts`.

**D2. The latency rule.** For each Job_To_Be_Done row, the row REGRESSES iff

    med_f - med_b > max(p * med_b, 3 * 1.4826 * MAD_b)

`med_f` is the median of the five fresh latency samples. `med_b` and `MAD_b` are the median and
the median absolute deviation of the BASELINE's five samples only, never pooled with the fresh
ones. `p` is the committed `latencyPct`, 0.10, unchanged. 1.4826 scales a MAD to a normal
standard deviation; nothing in the rule assumes the latencies are normal. The rule is
`judgeLatency` in `frontend/src/lib/effectiveness-ratchet.ts`, and `compareLegMedians` is the
comparator the CI gate calls. Any rise of a median (`med_f > med_b`) forfeits
`canAdvanceBaseline` (Req 4.5), as any worsening did before.

**D3. The exact metrics.** steps (+5% relative), errorRate (+0.02 absolute) and
interruptionPrecision (-0.02 absolute, compared only when both sides carry a value) keep their
rules exactly: the one-run comparator `compareScorecard` and `compareLegMedians` run one private
core, so Property 5 (`src/lib/__tests__/effectiveness-ratchet.property.test.ts`) still pins the
code the gate uses for them. In addition, all five legs must report IDENTICAL steps, errorRate,
row seed and row harness version on every row, and an identical interruptionPrecision
(`poolLegs`). A disagreement is a failure, named by job and metric with every leg's value,
because the harness claims determinism for these, and a median would hide the claim failing.

**D4. The arrival proof.** After the harness, each leg runs `pnpm effectiveness:ratchet seal`. It
re-checks the emitted `scorecard.json` against the complete-or-failed emission rule and writes
`scorecard.leg.json`: the same record plus `leg: { index, count, commitSha }`, from
`matrix.leg`, `strategy.job-total` and `github.sha`. It refuses an incomplete record, an index
outside 1..5, a matrix of another size and a commit that is not a 40-character sha. The ratchet
then refuses unless EXACTLY five sealed scorecards arrived, their indices are exactly {1..5} with
none repeated, and all five name one commit, one harness version and one master seed
(`checkLegArrival`). A missing leg is a failure, never a median of fewer. The leg index is written
inside the scorecard on the leg's own runner, so a copied artifact carries a duplicate index
rather than passing as a second leg.

**D5. The baseline format, schema version 2.** The document carries `commitSha` and `legCount`.
Each row carries `harnessVersion`, `seed`, `steps`, `errorRate`, `latencyMs` (the median of its
samples) and `latencySamples`, one `{ leg, latencyMs, capturedAt }` per leg 1..5, so `MAD_b` can
be recomputed from the file. The one-run format, schema version 1, is refused BY NAME
(`one-run-format`) before any of its numbers is read. Two rejection kinds are added beside it:
`leg-set` (a row's samples are not exactly legs 1..5, or `legCount` is not 5) and
`median-mismatch` (a row's `latencyMs` is not its samples' median). R8.10's per-row capture stamp
becomes one per sample. `buildBaseline` takes the five legs' scorecards and runs the arrival proof
and the pooling itself, so it cannot build a baseline from a set the gate would refuse. The ratchet
writes the candidate only from a clean measurement: every leg arrived sealed and complete, with a
clean harness record, and the legs agree. A run with any other finding writes no candidate.

**D6. Where the evidence goes.** Every leg uploads `effectiveness-leg-<n>`: the sealed scorecard,
`scorecard.json`, `scorecard.incomplete.json` and its `playwright-harness.json`. The ratchet
downloads the pattern `effectiveness-leg-*` without merging, one directory per leg. Leg 1 alone
uploads `fe-invariant-playwright-harness-report`, which keeps the contract with `fe-invariants`:
that job downloads `fe-invariant-playwright-*-report` with merge-multiple and reads
`playwright-harness.json`, and legs 2..5 upload nothing that pattern matches. The ratchet reads
all five harness records for R8.6 and R8.8, not leg 1's alone. A runtime-conditional skip in one
leg shows only in that leg's record, and the medians are taken over all five legs, so the
evidence that each leg executed what it claims has to come from each leg.

## Pre-registered predictions (A/A at k = 5)

Run A is the first run of this design at a commit S_A. Its candidate artifact is committed
unedited, which makes commit S_B. Run B is the next run, at S_B. The measured candidate and both
ratchet logs are the evidence. Each prediction names what falsifies it, and none may be re-read
under a looser rule after the fact.

**AK1. Arrival.** Run A's ratchet reports "Arrival: PROVEN" for legs 1..5 at one commit and one
harness version, and the candidate it writes carries `legCount: 5`, `commitSha` equal to run A's
`github.sha`, and on each of its five rows exactly five `latencySamples` whose `leg` values are
exactly {1, 2, 3, 4, 5}. Falsified by any `leg-count`, `leg-stamp`, `duplicate-leg`,
`missing-leg`, `mixed-commit` or `mixed-harness` finding in run A, by a candidate row with another
sample count or leg set, or by run B's baseline check rejecting the committed candidate as
`leg-set`.

**AK2. The exact metrics are exact.** In run A and in run B, the five legs report identical
steps, errorRate, row seed and row harness version on every row, and an identical
interruptionPrecision (0.75 at seed 30000, as AA1 read). Falsified by any `[legs-disagree]`
finding in either run. If it is falsified, what failed is the harness's determinism claim
(Req 1.3), not the median rule, and the repair belongs in the harness.

**AK3. Same code, no regression.** Precondition, checked before the verdict is read:
`git diff --stat S_A S_B -- frontend` lists only `frontend/spec/effectiveness/scorecard.baseline.json`.
S_A is the candidate's `commitSha` and S_B is the commit run B's report names for its fresh legs.
If anything else under `frontend/` differs (main moved into the merge commit, or the lockfile
commit landed in between), the pair is not an A/A, and AK3 is UNREAD, neither held nor missed.
With the precondition met, run B reports no regression on any row or metric: on all five rows
`med_f - med_b <= max(0.10 * med_b, 3 * 1.4826 * MAD_b)`, and steps, errorRate and
interruptionPrecision equal the baseline's. Falsified by any row run B names as regressed. One
trial cannot establish a false-positive rate. It can only refute the claim that the band absorbs
same-code noise between two runs.

**AK4. The noise term is live.** In the committed candidate, `MAD_b > 0` on at least one of the
five rows, so the rule is not `p * med_b` everywhere. Predicted because AA2 read fractional
millisecond latencies that moved between attempts. Falsified if `MAD_b = 0` on all five rows. In
that case the rule IS `med_f - med_b > 0.10 * med_b` on every row, the ratchet's report says so
("MAD_b is 0 on every row"), and because AA2 already read same-code moves beyond 10% on two rows,
AK3 would then be expected to fail.

## Rejected alternatives

- **Widening `latencyPct`.** Forbidden. It would loosen every row to absorb noise measured on two,
  and the noise is not a fixed fraction (26.3 ms on one row and 0.9 ms on another in AA2).
- **A one-run baseline.** One sample per row gives no measured spread. Finding 88's A/A shows that
  one run's latency moves by more than the band at one sha.
- **`--repeat-each` inside one leg.** The emitter keeps its rows and ledger in module state
  (`measuredRows` and `scenarioLedger` in `tests/e2e/task-completion.jtbd.spec.ts`), so repeats do
  not aggregate into one scorecard, and repeats on one runner would share that runner's noise
  rather than sample the runner-to-runner spread that AA2 measured.
- **A pooled MAD**, over the baseline's and the fresh samples together. It absorbs the shift the
  gate exists to see: when the fresh samples are the baseline's shifted by `d`, the pooled MAD is
  at least `(d - r) / 2`, with `r` the baseline's range, so for `d` of about `1.82 r` or more the
  pooled band always exceeds `d` and the shift never regresses. Property 33 asserts a case where
  the pooled rule holds a row that this rule regresses.
- **An absolute floor for single-digit-millisecond rows** (finding 88's other option). A floor
  sized for AA2's 0.9 ms move would not absorb its 26.3 ms move (inferred from those two numbers),
  and it is one more tuned constant.
- **Medians for steps, errorRate and interruptionPrecision too.** They are claimed deterministic.
  A disagreement among legs is a defect to surface, not noise to summarise.

## What this design still cannot see

- **A shift shared by every leg of a run.** `MAD_b` is the spread between five legs of ONE run. A
  slowdown common to all legs of a later run (a runner image update, a new Chromium from
  `playwright install`, a slower hardware mix) moves `med_f` without moving `MAD_b`, and only the
  10% relative term absorbs it. If such shifts exceed 10% of a row's median, the gate will fail
  same-code runs. AK3 tests one pair and cannot bound how often that happens.
- **Two slow legs.** The median of five tolerates two arbitrarily slow legs per row by
  construction, and three slow legs regress the row by construction.
- **A small MAD.** A MAD from five samples can understate the spread; the relative term is then
  the only floor.
- **The commit behind the stamp.** The seal stamps `github.sha`, which for a pull request is the
  synthetic merge commit, not the PR head, and is not re-derived from the checked-out tree. The
  arrival proof detects absent, repeated and mixed stamps; it trusts the workflow to give each leg
  its own index.
- **The baseline against the run that made it.** No gate compares the committed baseline's
  `commitSha` and capture instants with the run whose candidate it was; a reader can.
- **Human time.** The latency is a Scripted_Proxy path in a headless browser, not an operator's
  time-to-complete. The proxy ceiling is unchanged.

## Consequences

- `e2e-harness` costs five times the runner minutes per pull request. That is free only while the
  repository is public: check `visibility` before sizing CI on it (`execution-routing.md`).
- `effectiveness-ratchet` stays red on `one-run-format` until a candidate of this design is
  committed. That red is expected and is not a reason to relax anything.
- `compareScorecard` has no CI caller. It is kept because Property 5 pins it and because the
  steps, errorRate and interruptionPrecision code it shares with `compareLegMedians` stays pinned
  through it.
- The committed baseline grows from one value per row to five samples per row, and stays readable
  by every existing loader: `parseScorecard` tolerates the new keys, and
  `spec/effectiveness/real-stack-fidelity.ts` reads only `rows[].job` and `rows[].errorRate`.
