# FREEZE W - the release world, its incumbent and their numbers, fixed before any challenger

**Frozen by truth session 5 (prepared 2026-11-19 to 24), under PREREG-1 section 5.** Nothing of
SYNAPSE (no challenger, composition or component) ran on the release world before this freeze was
pushed. Check it anywhere with the standard library: `python docs/truth/sealed/check_freeze_w.py`.
CI runs that check, the seal check of PREREG-1 and an add-only rule for `docs/truth/sealed/` on
every pull request and every push to `main` (`.github/workflows/seals.yml`).

`SHA256SUMS-W` lists every frozen file with the sha256 of its bytes as git stores them (a Windows
checkout's CRLF read as LF, so the digest equals `git show <rev>:<path> | sha256sum`).
`freeze-w.json` states each item below as data, and the checker ticks it against the frozen files.
`freeze-w.json`'s `base_commit` is the commit the frozen files were hashed on. The time witnesses
are the server-side merge time of this freeze's pull request and an OpenTimestamps proof of
`SHA256SUMS-W` (`SHA256SUMS-W.ots`), added beside it when the freeze is pushed and upgraded once
Bitcoin confirms it.

A fresh-context attack on the first candidate found one blocker and five fixes (truth log S5-M-39);
all were repaired before this freeze (S5-D-07), and the numbers below come from the repaired code.

## What is frozen, item by item (PREREG-1 section 5)

| Item | Where | What it holds |
|---|---|---|
| The kernel | every file under `synapse_kernel/` at the freeze, counted in `freeze-w.json` | the legacy mode (session 3), SYNAPSE's Sentinel port (session 5, stage A) if it merged before the freeze, and the release world (session 5): counter-based draws (Threefry-2x32-20), exact samplers, an hourly engine with ageing batches issued first in first out, the observation, the objective, the cells, the scenario, the incumbent, the tuner, the guard, the headroom oracle and the run-time check |
| The world, every declared parameter | `synapse_kernel/worlds/release_world.json` | 300 items, 3,823 units a day, 14 profiles of 168 hours, day-level variance tables; each parameter group with a provenance (fitted, cited or chosen, with its source or reason) and the CC BY 4.0 attribution of FreshRetailNet-50K. It is the fit script's output with its shelf lives recalibrated by the stage D driver (below), so re-running the fit alone gives the world before calibration |
| The item set | the world's `items` | rates at evenly spaced quantiles of each category group's within-store distribution, 4.7 to 237 a day, the top fifth 47% of units |
| Suppliers and their items, lead times, delivery schedule | the world's `suppliers` | `fresh_morning` delivers at 06:00, lead 8 h; `chilled_morning` 05:00, lead 12 h; `hub_twice` 06:00 and 15:00, lead 4 h (chosen, with reasons) |
| Shelf lives | the world's items | 17, 34, 51, 85 or 119 hours at receipt: the chosen 1 to 7 days times 1/sqrt(2). The gate's rule: no recalibration while the incumbent's waste share lies in 2.7% to 10.9%, otherwise a log bisection toward 5.46%, at most six steps. The share was 2.38% at the chosen lives and 3.09% after one step. **The gate does not say whether the bisection stops on entering the band; the driver stops there, a reading fixed in its code before the run.** The other reading would go on toward 5.46% |
| Prices | the world's items | 1 for every item (ADR-062: every term of J is proportional to price) |
| The initial state | `synapse_kernel/release/engine.py` | per item one batch at age zero of ceil(mean demand over the lead time plus the longest interval between the supplier's deliveries); nothing on order |
| The method that recovers stock-out-hidden demand, with its masking check | `scripts/world/fit_release_world.py`, `docs/truth/world/fit-report.json` | the exposure-weighted profile estimator; **its masking check failed the bar fixed before it ran** (MNAR masks +9.5%, evening tails -0.3%), so demand on stocked-out days may be overstated by about 5 to 10%, most in the evening (truth log S5-M-19, S5-D-03) |
| The incumbent's tuned tables, evaluation counts and selection | `synapse_kernel/worlds/incumbent_tables.json`, `docs/truth/world/incumbent-report.json`, `scripts/kernel/tune_incumbent.py` | I1 and I2, each tuned on N, on L and on N+S1+S2+S3 by the sealed coordinate search (2,464 to 13,440 replicate-evaluations); selected: I2-N in N, I2-L in L, I2-P in S1 to S3; the contest's incumbent I2-P |
| `D_c`, `p_c`, `M_c` per cell | the incumbent report | `D_c` 3,822.968 units a day (N, L, S2, S3) and 4,214.519 (S1, whose surge's expected extra is a 120 x 120 midpoint quadrature over its duration and onset, within about 5 parts in a million of a finer grid); `p_c` 1; `M_c` = 0.01 x `D_c` x 0.38 x `p_c`: 14.527 and 16.015 |
| The shock headroom of section 6 | the incumbent report | below |

## The shock headroom, for description only

Validation seeds; the selected incumbent of each shock cell is I2-P. Each entry is the mean
advantage over it in money per store-day with its bootstrap 95% interval, then the per-seed
difference-in-differences against cell N (PREREG-1 section 6: there the oracle arm is I2-P with no
shock to tell, against N's incumbent I2-N, which it trails by 2.2 a store-day; 1.7 when guarded).

| Cell | Margin `M_c` | The gate's oracle | The gate's oracle, guarded | Informed variant | Informed variant, guarded |
|---|---|---|---|---|---|
| S1 surge | 16.015 | +34.04 (+24.6 to +44.0); DiD +36.24 (+26.8 to +46.0) | +29.92 (+23.6 to +36.2); DiD +31.64 (+25.4 to +38.1); clipped 3.9% | +39.84 (+30.5 to +49.2); DiD +42.03 (+32.8 to +51.5) | +29.39 (+23.1 to +36.0); DiD +31.11 (+24.6 to +37.7); clipped 2.5% |
| S2 delay | 14.527 | -84.82 (-109.7 to -63.5); DiD -82.62 (-107.3 to -61.6) | -29.18 (-35.0 to -23.4); DiD -27.47 (-33.0 to -21.8); clipped 6.9% | +0.14 (-3.6 to +4.1); DiD +2.34 (-1.4 to +6.3) | +0.04 (-2.1 to +2.2); DiD +1.76 (-0.4 to +3.9); clipped 5.3% |
| S3 outage | 14.527 | -213.69 (-279.1 to -155.8); DiD -211.50 (-277.6 to -154.0) | -22.04 (-29.2 to -15.2); DiD -20.32 (-27.5 to -13.5); clipped 4.9% | +8.03 (+3.4 to +12.5); DiD +10.23 (+5.7 to +14.8) | +7.94 (+5.1 to +10.9); DiD +9.66 (+6.6 to +12.6); clipped 5.2% |

**The gate's oracle** is the cell's incumbent told the shock's items, onset, size and duration and
planning against them, as the session-5 gate (section 7) defines it: a surge enters the mean
demand it plans against, before its order is clipped at zero; a delay or an outage stretches its
protection interval to the next order's actual arrival. **The informed variant** is a post hoc
design (truth log S5-M-22, S5-D-07): the surge enters as 1 + kappa (u - 1), and in S2 and S3 an
order covers only the demand from its own actual arrival to the next order's, given the stock
projected to that arrival and capped by shelf life; kappa is one factor per item, tuned on the
cell's tuning seeds. **Guarded** clips every order to the D-4(b) interval around the incumbent's.
These are two oracles, not the best possible use of the information, so their gains bound what
knowing the shock is worth from below.

**Read plainly.** In S1 even the gate's oracle clears the margin twice over, and the guard keeps
most of it. In S2 the informed variant gains nothing measurable. In S3 it gains +8.0 (difference
in differences +10.2, interval to +14.8), short of the 14.5 margin. Planning across a delay or an
outage the gate's way loses heavily (S2 -85, S3 -214), because it orders for demand that is lost
before the stock lands and the excess spoils; the guard cuts that loss to -29 and -22. Headroom
binds nothing (PREREG-1 section 6). It is published so that no one reads a shock cell's result
without it, and claim C2 in S2 and S3 should be expected to come out null.

## What this freeze does not fix

The challengers, the composition and its trust map, `s_c` and `n_c`, the analysis code and the
numpy version are freeze C's (PREREG-1 section 5; session 6, before 2026-12-11T00:00:00Z).

## Rules from here

- A later change to any frozen file or choice is a deviation, dated, with its reason and effect, in
  `DEVIATIONS.md`; the confirmatory run is then reported on both worlds, the frozen one primary
  (PREREG-1 sections 5 and 11). A deviation adds files beside the frozen ones; it never edits them.
- New files are allowed, under `synapse_kernel/` and elsewhere: session 6 adds challengers and the
  composition beside the frozen world.
- **Every policy compared on this world decides each replicate as it would alone**: it passes
  `synapse_kernel.release.harness.batch_independent` on exploratory seeds before any comparison,
  and the confirmatory run calls it one replicate at a time, so neither the batch size (a cell's
  `n_c`) nor another replicate reaches it (PREREG-1 section 1).
- **Every comparison runs the challenger in a process of its own**, apart from the harness that
  measures it, imports `synapse_kernel.release.integrity` before any challenger code, and calls
  `assert_frozen()`, `assert_world_frozen(world)` and `assert_tables_frozen(tables)`. They refuse a
  frozen file whose digest differs; a binding of the 14 release modules replaced, changed in place
  or added; a world object altered after loading; and incumbent tables altered in memory. Inside
  one process they cannot see numpy or the standard library patched, nor a checker rebound, which
  is why the challenger runs apart.

## Known limits, stated at the freeze

- The masking check failed its bar (above). The dataset excludes slow movers (no item under about
  4.7 units a day), is a Chinese frontier-warehouse business in spring 2024, and its hold-out week
  sold 8% more than the training months (ADR-062).
- Items do not interact (no shared capacity, no substitution); shelf lives, lead times and the
  schedule are chosen, not fitted.
- The incumbent's mean-demand table is read from its tuning seeds' recorded demand, as sealed, so
  its tuning cost is optimistic: validation costs run 0.5% to 4.2% above tuning costs.
- Decisions happen at supplier cut-offs only, so most of an item's six part-of-day factors never
  apply ("unused" in the tables).
