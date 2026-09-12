# HANDOFF — decision-quality-proof

**State at end of session 8 (2026-09-11). Five commits pushed; the commit carrying this file is
the fifth.**

**This file is now DERIVED and short, and that is the change.** Session 7's handoff ran to 395
lines and restated finding 54 for the third of five times. Per
`.kiro/steering/throughput-with-integrity.md`, every finding has **one canonical home** — the ADR
for design facts, the task body for ledger facts — and this file carries **state, pointers and the
honesty ledger only.** If you want a finding's reasoning, follow the pointer; it is not repeated
here.

```powershell
python -m scripts.audit.spec_ledger_census --files --next 40
```

At close: **142 leaf tasks — 66 done, 0 pending, 76 open** (70 authorable, 6 CI-gated).
**No leaf ticked this session**, deliberately: the work was the throughput reset and the
measurement that unblocks E2c's disposition.

---

## What changed, with pointers

| Commit | Subject | Canonical record |
|---|---|---|
| `e02c1c2` | per-term cost decomposition — finding 54's falsifier | ADR-055 **D2.5.3**, task 11 |
| `3bcea22` | the throughput reset: three steering documents | `.kiro/steering/*` |
| `5ef7a67` | **finding 59** — the decomposition answers task 11 | **ADR-055 D2.5.3** |
| `b61941b` | `[~]` harvest made mechanical; ceiling 30 → 40 | `spec_ledger_census`, Property 63 |
| *(fifth)* | this file, the prompt, the progress-ledger row | — |

**The reset, in one line each.** `.kiro/steering/execution-routing.md` — an **allow-list** routing
all 35 audit gates, every test path and every lint/type/build command to LOCAL, CI or
NEVER, with `cores × wall-seconds` as the cost metric. `.kiro/steering/throughput-with-integrity.md`
— six values and six guardrails, and **the metric: throughput is leaves DISCHARGED; a `[~]` counts
zero.** `local-compute-budget.md` (I-0) — four narrow edits; **every incident record and the
one-executor cap intact and verbatim**, verified by diff.

---

## The single most important thing to read next

**Task 11's disposition is decided, by arithmetic rather than preference: option (b).** ADR-055
**D2.5.3** carries the measurement and **finding 60**. In short — the per-term decomposition shows
**two** defects, not one:

- `stockout_rate` and `unmet_service` are **one quantity, by construction**, each weighted `8.0`,
  so **one KPI is priced at 16.0**. `SimulationMetrics.fill_rate` is the exact complement of
  `stockout_rate` over one shared denominator, and its own docstring says so. **`fill_rate` has two
  inequivalent definitions in this tree** (`KpiExtractor`'s is not the complement), so a
  measurement inherits whichever its read path used — Property 64 asserts the divergence.
- The arm labelled `perfect_foresight` leaves **8.2% of demand unmet**; the incumbent leaves
  **exactly zero**. It orders "no more, no less" and carries no buffer.

**Removing the double-count alone leaves regret at `-0.1559` — still negative.** So repairing the
objective is necessary but **not sufficient**, and replacing `ForesightPolicy` with an arm that
minimises the committed objective over the known trace is the repair the measurement demands.

**E2c stays blocked**, and **checkpoint B is now gated too**: task 13.5 defines dominance over the
same objective, so a Pareto verdict over four effective dimensions answers about a different
objective than R5.28 names.

## The schedule: FOUR sessions, and three was never honest

Session 8's close said three sessions "if checkpoint B cancels E3". **That is withdrawn.** A
schedule contingent on a measurement outcome is not a schedule, and the contingency had a direction:
checkpoint B firing deletes 21 leaves **and** means consensus is provably unnecessary — SYNAPSE's
central claim false. **Those are the same event, so hoping for the saving is hoping the project
fails.** Task 14 now names that temptation in its own body so it cannot operate silently.

**Four sessions, and the levers that compress them are process, not scope:** the `uplift-verify`
job split (specified, unlanded) and G7's parallel authoring (mandated, never yet used).

---

## Honesty ledger

### Executed and measured

| What | Result |
|---|---|
| The machine, `Get-CimInstance` | **15.71 GB** RAM (6.86 free), i5-12450HX **8/12** cores, RTX 3050 6 GB — correcting *both* prior figures |
| `HYPOTHESIS_PROFILE` unset, via `conftest` itself | **500** examples — a **50×** load. `dev` 10, `heavy` 100, `ci` 500 |
| Run `34590696403` — the decomposition | per-term sums to `-0.8125` = `regret`; `dominant_regret_term` `stockout_rate` at **0.808** |
| Property 62 (decomposition identity) | **4 green at `ci` (500)** |
| Property 63 (harvest refusal) | **5 green at `ci` (500)**, both directions proven by construction |
| `test_spec_ledger_census` after the ceiling move | **26 green** |
| All 18 pins re-probed after the ADR edit | **0** document-side failures; `pin_extractor_truth` 15/15/15 |
| Six cheap gates | **0 / 0 / 0 / 2 / 1 / 0**, unchanged across all five commits |
| Census | **0**, unchanged at `142/66/0/76` |
| `mypy --strict` | clean on `scripts.audit.spec_ledger_census`; `uplift.regret` clean, its 6 errors all in two files with **empty** `origin/main` diffs |
| `ruff check` | **0** on all five changed Python files |
| `ruff format` ownership | deviations on `spec_ledger_census.py` and `test_spec_ledger_census.py` proven **PRE-EXISTING** at HEAD by materialising the blobs; **zero added**, and left alone |
| `quality-gates` at `e02c1c2` | **`success`** |
| Line endings | the `w/mixed` trap fired on I-0 and was normalised to its dominant **worktree** ending (CRLF 99 vs LF 49) |

**Throughput numbers, as G6 requires.** Leaves **discharged: 0**. Core-seconds: **~700**
(6 `pytest` invocations, 2 `mypy`, ~20 cheap gates, 5 probes — all serial, one executor).
CI critical-path wall-clock: ~5 min for the labelled measurement. **Parallel agents dispatched: 0.**

**So G6's target is missed, and the honest reading is that this session installed the levers and
did not yet pull them.** Zero discharged against a target of ≥ 11 — but the target is for the
first session *under* these rules, and this is the session that wrote them. **Session 9 is the
test.** The reset is falsifiable and has not yet been tested.

### NOT executed. Must not be claimed.

- **`uplift-verify` at `e02c1c2`, `3bcea22`, `5ef7a67` or `b61941b`.** Three runs were in flight at
  close. **Read the fast step first: Properties 62 and 63 are new and run there at 500 examples.**
  Both passed locally at `ci`, which is not a CI green.
- **Finding 57's status** — the `codecarbon` `.csv` false positive on the slow step. Unrepaired,
  another owner's, mechanism recorded in task 27.5.
- **The `uplift-verify` job split (Task 5 of the reset), deferred with a written spec** in
  `NEXT_SESSION_PROMPT.md`. It touches a **required** check; the analysis and its risk are recorded
  rather than half-landed.
- **That the 8.2% unmet figure is caused by within-window arrival order** — the most plausible
  reading of a no-buffer policy, mechanism not isolated.
- **That defect 1 was unintentional.** D2.3 committed both weights; read the record before
  assuming an error rather than a choice.
- **`mypy --strict` on any test module**; no CI step type-checks `tests/`.
- **`vitest`. At all.**

### The lesson

**Capability is not use.** `RegretObjective.contributions()` has been able to decompose a cost
into its five weighted terms since task 9, with a docstring saying a regret whose composition
cannot be inspected "is a number nobody can argue with" — and `_measure` called `cost()` and never
`contributions()`. That single missing call is the **only** reason finding 54's cause had to be
recorded as a hypothesis for a session. **Ask what the tree can already do before building
anything.**

And the same shape one level up: **I-0 permitted unlimited parallel authoring agents for eight
sessions and sessions used zero.** The reset's largest change is not a new permission — it is
turning an unused one into an obligation.
