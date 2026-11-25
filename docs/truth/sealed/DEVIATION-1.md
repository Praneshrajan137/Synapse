# DEVIATION 1 - the calibration's other reading: a second world, frozen beside freeze W's

**Decided by the operator on 2026-11-24, after freeze W** (truth session 6, decision S6-D-03: "Override
it", to "Keep the frozen reading?"). Recorded in [`DEVIATIONS.md`](DEVIATIONS.md). Check it anywhere
with the standard library: `python docs/truth/sealed/check_deviation_1.py`. CI runs that check beside
the seal's and freeze W's (`.github/workflows/seals.yml`).

## What departs from the sealed text, and what does not

PREREG-1 section 2 says: "Any recalibration of the world happens before freeze W, never after." This
deviation recalibrates after freeze W. It does so the only way the sealed text allows a later change
(sections 5 and 11): **nothing frozen is edited**, a second world is added beside the frozen one, and
the confirmatory run is "reported on both worlds, the frozen one primary". Every claim C1 to C3 is
judged on freeze W's world exactly as before; W-d1's results are reported beside each of them.

## Why

The session-5 gate fixed the calibration as "bisected in log scale toward 5.46%, at most six
iterations", with no recalibration while the incumbent's waste share lies in [2.7%, 10.9%]. It does
not say whether the bisection stops once the share enters that band. Freeze W's driver stopped there
(3.09%, at scale `1/sqrt(2)`), a reading committed in the driver before its run (truth log S5-M-28,
S5-D-07). The other reading goes on toward IFPA's 5.46% produce shrink. The operator chose to see the
store under that reading too.

## The reading, fixed before it ran (session 6's gate, stage A2)

From the uncalibrated world, the frozen driver's own loop with one change: it does not stop on entering
the band; it bisects the log scale toward 5.46% (a share below it moves to shorter shelf lives, above
it to longer) for the frozen six steps after scale 1, in the frozen bracket [0.5, 2]; W-d1's scale is
the evaluated scale whose share is closest to 5.46% (ties: the larger), the gate's own "freeze at the
closest point". Same tuning seeds, tuner, measure and rounding. Then everything freeze W fixed is
recomputed on W-d1 by the frozen driver's own `main`, unchanged, writing new files.

## What came out (measured 2026-11-24, one run, 5,248 s for the driver)

| | Freeze W (primary) | W-d1 |
|---|---|---|
| Shelf-life scale | `1/sqrt(2)` = 0.7071 | **0.5054** (5.46% not reachable in [0.5, 2]: the closest point, 0.94 points short) |
| Shelf lives at receipt | 17, 34, 51, 85, 119 hours | 12, 24, 36, 61, 85 hours |
| Waste share of the better incumbent in N (tuning seeds) | 3.09% | 4.52% |
| Calibration steps | 2.38%, 3.09% | 2.38%, 3.09% (the same two), 3.72%, 4.24%, 4.38%, 4.40%, 4.52% |
| Selected incumbent | I2-N in N, I2-L in L, I2-P in S1 to S3; contest I2-P | the same |
| N's incumbent: validation cost, waste, fill | 189.69, 3.23% of sales, 91.9% | 300.45, 4.79% of sales, 86.0% |
| L's incumbent: validation cost | 395.91 | 482.03 |
| `M_c` | 14.527; S1 16.015 | 14.527; S1 16.063 (a 5-day warm-up moves the measured week, and with it the surge's expected extra) |
| Headroom S1, the gate's oracle, guarded | +29.92 | +36.05 |
| Headroom S2, informed, guarded | +0.04 | -2.28 |
| Headroom S3, informed, guarded | +7.94 | +7.74 |

Steps 0 and 1 reproduced freeze W's record number for number, and the uncalibrated world, scaled by
`sqrt(0.5)`, is freeze W's world exactly (provenance aside): both worlds come from one fit. The
uncalibrated world is committed (`release_world_uncalibrated.json`), so this deviation reproduces
without the dataset.

## The files (all new; `SHA256SUMS-D1` lists them, and `SHA256SUMS-W` with them)

`synapse_kernel/worlds/release_world_uncalibrated.json`, `release_world_d1.json`,
`incumbent_tables_d1.json`; `docs/truth/world/incumbent-report-d1.json`; `scripts/kernel/deviation_1.py`
and its tests; `synapse_kernel/deviation1.py`, the run-time check that loads W-d1 and refuses it if its
files, world or tables differ from these; this statement, `deviation-1.json` and its checker. The time
witnesses are this pull request's server-side merge time and an OpenTimestamps proof of
`SHA256SUMS-D1`.

## Rules from here

- No challenger runs on W-d1 before this deviation is merged.
- A comparison on W-d1 imports `synapse_kernel.release.integrity` before any challenger code, asserts
  freeze W (the kernel that runs is freeze W's), and loads W-d1 only through
  `synapse_kernel.deviation1.load`.
- SYNAPSE is fitted on W-d1 by the same committed procedure as on W, from W-d1's own inputs; freeze C
  fixes both fits.

## Known limits

Freeze W's, plus one: 5.46% is not reachable inside the frozen bracket, so W-d1 sits 0.94 points of
waste share below IFPA's figure, which itself includes shrink other than expiry.
