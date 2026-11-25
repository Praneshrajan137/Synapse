# DEVIATIONS - departures from PREREG-1, each dated, reasoned and with its effect

None as of the seal (2026-11-19).

## Deviation 1 (2026-11-24): the calibration's other reading, a second world beside freeze W's

- **What departs.** PREREG-1 section 2: "Any recalibration of the world happens before freeze W, never
  after." The world's shelf lives are recalibrated after freeze W.
- **Decided by** the operator, 2026-11-24 (truth session 6, decision S6-D-03), asked in that session's
  gate: freeze W's driver stopped the calibration on entering the band [2.7%, 10.9%] (3.09%), a reading
  the session-5 gate's text did not fix; the operator chose the other reading, which bisects on toward
  IFPA's 5.46%.
- **What is done.** Nothing frozen is edited. A second world, W-d1, is calibrated by the other reading,
  fixed before it ran, and everything freeze W fixed is recomputed on it by freeze W's own driver; it is
  frozen in `DEVIATION-1.md`, `deviation-1.json` and `SHA256SUMS-D1` (chained to `SHA256SUMS-W`)
  before any challenger runs on it. The result: scale 0.5054, shelf lives 12 to 85 hours, waste share
  4.52% (5.46% is not reachable inside the frozen bracket); the same incumbent versions selected.
- **Effect.** Every claim is judged on freeze W's world, the primary one, as sealed. The confirmatory
  run is reported on W-d1 beside every claim (PREREG-1 section 5: "reported on both worlds, the frozen
  one primary"), with SYNAPSE fitted on W-d1 by the same committed procedure as on W. A conclusion that
  differs between the two worlds is reported as differing.
