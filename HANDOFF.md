# HANDOFF — decision-quality-proof

**State at end of session 10 (2026-09-11).** Branch `feat/decision-quality-proof`, PR **#84** open
against `main`. The session opened at HEAD `27a74a3`, 75 commits ahead of `origin/main`. The commit
carrying this file also carries `NEXT_SESSION_PROMPT.md` and two progress-ledger rows.

**This file is DERIVED and short.** Per `.kiro/steering/throughput-with-integrity.md`, every finding
has **one canonical home** — the ADR for design facts, the task body for ledger facts — and this
file carries **state, pointers and the honesty ledger only.** Follow the pointer; no reasoning is
repeated here.

**The census is a command, not a number in this file.** Re-derive it before believing anything
below:

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

It reported `142 leaf / 67 done / 0 pending / 75 open` at this session's start and
`142 / 87 / 2 / 53` at its close — 48 authorable, 5 CI-gated, `unharvested: 0`, status pass.
**Twenty leaves discharged.**

---

## The headline, and it is two things

### 1. Session 9's work was never recorded, and session 10 is mostly the reconciliation

Session 9 landed six commits — `f468f0f` the `uplift-verify` shard split, `df0f3ff` task 26.4,
`c746463` task 11 option (b), `e0df6a8` task 18, `4715de5` task 19, `4fe1dad` task 20 — and wrote a
ledger entry for **task 11 alone**. Twenty leaves were complete on disk and still marked `[ ]`.
**That is "disk outranks this ledger" at scale, for the second time in this spec's life.**

Session 10 reconciled them: ticked **16.3, 18.1–18.6, 19.1–19.3, 19.5–19.8, 20.1, 20.2, 20.4–20.6,
26.4**; marked **20.7** and **20.8** `[~]`; and **deliberately did not tick 19.4 or 20.3** — 19.4
still owes a `@register` plus a workflow locus, and `task_claim_truth` correctly reports 20.3 as
`pending: claims nothing yet`.

### 2. Finding 61 — task 11's `material` verdict is sound arithmetic on the wrong denominator

Canonical record: **ADR-055 D2.6.** One sentence, and the reasoning is there rather than here: the
measured regret is the incumbent-versus-perfect-information gap, which is EVPI **plus** the
incumbent's own mis-tuning, and because the comparator replenishes instantaneously through
`sim.add_stock` with lead time off in every arm, it cannot contain information value. The repair is
**arm E, a tuned static par-level control**, and the operator has made it a **hard gate**.

---

## Also found and recorded this session — pointers only

- **Finding 62** — the shard split's G5 selection proof compared against a frozen literal
  `EXPECTED_FAST_SELECTED: "874"`. Canonical home: the step comments in `ci.yml` plus the task
  ledger. Repaired: the right-hand side is now measured in-run by a new `universe` step in shard 1.
- **Conflict R** — R5.28 is unsatisfiable a second time, and R5.29 would then cancel E3 on a
  theorem. Canonical home: `requirements.md` and task 14's body.
- **The census cannot distinguish "prior art" from "candidate discharge."** It emitted about 110
  informational `prior-art` lines with the twenty genuine candidate discharges buried inside them.
  Recorded as owed work; a severity split is the repair.

## The three operator decisions, and they are binding

1. **Task 23 (R10, eleven leaves) is DEFERRED** to a named follow-on spec,
   `.kiro/specs/external-audit-anchor/` — **named, not created.** Tamper-evident publication
   infrastructure is orthogonal to whether consensus produces better decisions. **Correction one
   agent surfaced:** OQ-4 is recorded RESOLVED (Rekor) in `requirements.md`, so the open obligation
   is **ADR-056's supersession of ADR-033**, not OQ-4.
2. **The Kaggle M5 terms will NOT be accepted.** C74 is non-passing **by decision rather than
   pending**; the M5 score and the ancestry row are permanently `unavailable`, never a pass. Task
   25's claim is scoped to the twin and must say so, and R8.18 now requires distinguishing "a
   published model" from "a published model scored against a published leaderboard".
3. **Arm E is a HARD GATE.** If the information gap is below the materiality margin, E3's floor and
   task 25's claim may not be denominated against the incumbent arm, and structures 1 and 3 are
   reinstated. **`material` on tuning alone is refused.**

---

## CI state at `27a74a3`, read from the runs

- **`SYNAPSE CI` run `34686422504`.** `quality-gates` (`Lint + Type Check + Unit Tests`) **FAILED at
  step 6 `Ruff format check`**, gating steps 7–23 — one file,
  `agents/demand_prophet/tests/test_pipeline_contract.py`, 385 already formatted. **Repaired this
  session**, ownership proven as this branch's (+144/−3 against `origin/main`, last touched by
  `4fe1dad`, and it is task 20.1's own coupling). **This is the third time one formatting or lint
  finding has gated a whole job on this branch.**
- All four fast shards `success`. Slow selection `1 failed, 65 passed`, the single failure being
  **finding 57** unchanged — `codecarbon/data/hardware/cpu_power.csv`, another owner's guard, still
  unrepaired.
- Aggregator step 5 red on finding 62; step 4 green.
- **`SYNAPSE Frontend CI` run `34686422478`:** `Lint - Typecheck - Unit` failed at step 6 `Biome
  lint`, so **step 8 `Vitest unit + property tests` was SKIPPED** — which is why 20.7 and 20.8 are
  `[~]` and not `[x]`. Three further frontend jobs are red on separate causes: `pnpm audit (high+
  severity)` and `TypeScript strict (spec/ + tests/)`. Not this session's, not adopted, recorded.
- **`Truth Gates`, `Integration` and `Mutation` are all red and were not investigated this
  session.** Saying so is the point.

---

## Honesty ledger

### Executed and measured

| What | Result |
|---|---|
| Census, before and after | `142/67/0/75` → `142/87/2/53`, `unharvested: 0`, status pass |
| Six cheap gates | `workflow_shape_truth` 0 · `pin_extractor_truth` 0 · `sweep_budget_truth` 0 · `dataset_licence_truth` **2** (honest SKIP) · `task_claim_truth` **1** · `gate_surface --check` 0 after `--write`; census 0 |
| `task_claim_truth`'s 1 | **still `core-purpose-uplift` tasks 9 and 9.1** — verified by reading its output *after* ticking twenty leaves, and it correctly lists our **20.3** as `pending: claims nothing yet`, which is why 20.3 was not ticked |
| **All 18 documentation pins, BOTH sides**, through `doc_truth.resolve_pin_texts` as a pure function, after the ADR-055 amendment | all 15 live rows `ok`; all 8 ADR-055-anchored rows still match **exactly one** line each. The single non-ok row is the **parked** `mutation-fast-required-job`, which the pin table itself records as one that would fail if activated — **now measured for the first time rather than predicted** |
| `ruff format --check` at CI's exact scope | `386 files already formatted`, exit 0 |
| `ruff check` at CI's exact scope | all passed |
| `gate_surface` row delta, predicted then measured | 413 → 414 steps. **A refinement worth recording: the row delta for one step change is (trigger contexts × sections), not 1** — six renamed rows and five new rows for one rename plus one addition. The prediction was right in content and **wrong in magnitude** |
| Line endings | **the trap fired for the TENTH consecutive session**, on `ci.yml` and `blocking-steps.yaml`, from `str_replace` edits. Both normalised to their measured dominant **worktree** ending, which was **CRLF** (1356 vs 93, and 802 vs 15) — the `i/lf` column would have led a reader to guess LF and make it worse. Finding 33 confirmed again |

### The four throughput numbers (steering G6)

- **Leaves DISCHARGED: 20**, against G6's target of **>= 11**. **These were earned by
  RECONCILIATION rather than by authoring.** That is a real result and also a warning: the previous
  session created them and did not claim them.
- **Core-seconds: ~400** — about 20 cheap gate invocations, two `ruff` passes at CI scope, one pin
  probe, one YAML parse, one census pair. **No `pytest` ran at all.** All serial, one executor.
- **CI wall-clock on the critical path: 0 minutes** — no run was dispatched; every CI fact came
  from reading completed runs.
- **Parallel agents dispatched: 6** — four read-only reconciliation and blast-radius agents, then
  three authoring agents partitioned by coupling closure (ADR / requirements / tasks), then one for
  these documents. **Reported honestly: three of the authoring agents each ran one stray no-op shell
  command** (`echo` / `Write-Output`) before honouring the no-execute clause, disclosed it
  unprompted, and touched no project code. **That is a contract-compliance defect in the dispatch**,
  and the repair is to put the ban in the contract's first line.

### NOT verified. Must not be claimed.

- **That `quality-gates` now passes steps 7–23.** The format repair is landed and **CI owns that
  verdict**; steps 7–23 have not executed at this sha.
- **That the finding-62 repair makes aggregator step 5 green.** The new `universe` step has never
  run.
- **Finding 57's repair** — not attempted. It is another owner's and the fix is a judgement
  (R2.10 forbids weakening the guard).
- **`mypy --strict` on anything this session.** No Python source changed except one test file's
  formatting.
- **`vitest`, at all**, and any frontend job's repair.
- **Arm E's measurement.** It is not authored yet.

---

## What session 11 does

**Arm E first, because it is a hard gate on E3's floor.** Then E3: the batch is
`15.1, 15.2, 15.4, 15.5, 15.6, 16.1, 16.2, 16.4, 16.5, 16.6, 16.7, 17.1–17.9` — 20 leaves, all
authorable, none behind a barrier. Two reconciliation facts shrink it: **16.3 is already done**
(ADR-055 D6 declares both R6.15 numbers) and **16.2 is smaller than its body claims**
(`ratchets.json` already carries `negative-control-seed-sets` 20 and
`negative-control-rate-tolerance`; what is missing is `uplift-controls.yaml`, the oracle tolerance
and the detection probability). `NEXT_SESSION_PROMPT.md` carries the measured blast radius for
task 15.1 and the rest of the procedure.

Still owed beyond the batch: **19.4**'s `@register` plus a workflow locus; **finding 57**;
**finding 53** (`replicate` in `security.yml:98`'s second deny-list); **finding 45**'s stale C16
docstring; the census severity split; and the **thirteen unmeasured audit gates** in
`execution-routing.md`.

## The lesson

**Authoring without recording scores zero, and it is indistinguishable from not authoring.** Twenty
leaves sat complete on disk for a session while the ledger said the spec had not moved, which under
the throughput metric is worth exactly nothing. The metric is not an accounting preference: a mark
whose discharge has silently arrived, or whose work has silently landed, is indistinguishable from
one still waiting. **Reconcile against disk before deriving a batch** — otherwise `--next 40` offers
work that is already done, and the census cannot tell you so.
