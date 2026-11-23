# ADR-062: The release world: hourly slots, integer stock in ageing batches, and counter-based draws

## Status

Accepted (truth program session 5, stage B). It implements the world `docs/truth/sealed/PREREG-1.md`
describes (sections 1, 2 and 6); freeze W fixes it before any challenger runs on it. It supersedes
nothing: the legacy twin and the kernel's legacy mode (ADR-060) stay as they are.

## Context

The legacy twin cannot carry the release's claims. Waste in it is a clock that takes no stock (truth
finding F-30), its ten items are equal (F-13a), and its shocks are announced multipliers. PREREG-1
seals what the new world must be: many items with skewed demand and an intraday and weekly shape
fitted to FreshRetailNet-50K, stock in batches discarded at their shelf life first in first out,
suppliers with lead times and a delivery schedule, whole-unit orders on the next scheduled delivery,
an observation limited to what a store sees, every draw keyed by seed, purpose, entity and time slot
and never by a policy's action, five cells, and a cost in money per store-day. The release also runs
in each visitor's browser through Pyodide, whose numpy is its own build and version; numpy does not
promise its `Generator` streams across versions or CPUs (checked in its v2.5 manual, truth finding
F-36), and freeze W makes any later repair a deviation.

## Decision

1. **Hourly slots.** The data's resolution is the hour. Each hour: expiry, receipts, decisions at
   order cut-offs, sales first in first out, holding by the trapezoid. Only the 7 measured days
   are priced; the warm-up (longest shelf life plus longest lead time, whole days) is not.
2. **Integer state.** Units, hours and batches are integers; the objective is computed from integer
   totals and summed with `math.fsum`. Units are conserved exactly (a test).
3. **Counter-based randomness.** Every draw is Threefry-2x32-20 (Salmon et al. 2011, the generator
   JAX uses) of a counter (purpose, entity, slot, index) under the replicate's seed, in 32-bit
   integer arithmetic, checked against Random123's published answer vectors and a pure-Python form.
   Samplers use exact arithmetic only: Poisson by inversion with an `exp` built from + - * / and
   powers of two (within 2 units in the last place of libm's). No module of the release world calls
   libm's transcendental functions or `numpy.random` (an AST test).
4. **The scenario comes first.** All of a replicate's randomness (demand per item-hour, day factors,
   the shock and its timing) is drawn before the engine starts; the engine holds no generator. A
   policy cannot move a draw by construction, and every cell shares cell N's base demand at a seed.
5. **Decision points are order cut-offs** (a supplier's delivery hour less its lead time). Reasons:
   a store raises indents at fixed times; an order placed between cut-offs rides the same delivery,
   so hourly decisions would add no lever; the release's Play orders at delivery slots. Stated
   consequences: an item's part-of-day factors outside its cut-offs never apply ("unused"), and the
   guard of decision D-4(b) is not pinned at zero by hourly quantities that would mostly be zero.
6. **The observation is exactly PREREG-1 section 1's, with no absolute time**: sales and receipts
   since the last decision, batches with hours to expiry, open orders with hours since placement,
   realised lead times, hour of day, day of week. Shifting the clock by whole weeks changes no byte
   (a test). Policies are built from `PolicyInputs`: cell N's declared parameters and exploratory
   records, the same bytes whichever cell they run in.
7. **Prices are 1.** Every term of J is proportional to an item's price, so per-item decisions do
   not depend on it; units then weigh equally in J, in `s_c` and in `n_c`.
8. **Implementation choices the sealed text leaves open** are fixed in the session-5 gate (section
   7) and frozen with the world: shock hours by their start, arrivals at the first whole hour at or
   after a continuous time, S3's outage orders at its end plus lead time (sealed) and its cancelled
   deliveries at its end (chosen), cell N's warm-up and calendar in every cell, replicates starting
   on a Monday.

## The fit (session 5, `scripts/world/fit_release_world.py`, report `docs/truth/world/fit-report.json`)

- **Data.** FreshRetailNet-50K revision `c374e85975c82816c495acfa904cc55ab14a47d3` (CC BY 4.0,
  registered in `infrastructure/data/dataset-licences.yaml`): 50,000 store-product series, 898
  stores, 90 days of hourly sales and stock flags; the following 7 days are the hold-out.
- **Two readings the card did not give, measured.** Units are 10 x the hourly value (99.56% of
  positive values lie on a 0.1 lattice and the noise floor of daily totals has slope near one), so
  the store's volume is fitted, not chosen (finding F-35, falsified). The stock flag is 1 for out of
  stock, the complement of the paper's censoring indicator (F-37).
- **Stock-out-hidden demand** is recovered by the exposure-weighted profile estimator (the Poisson
  MLE of a day's level from its in-stock hours under the profile), alternated with the profile
  per category group and weekday to a fixed point (38 iterations). **Its masking check failed the
  bar fixed before it ran**: on held-out fully in-stock days, the pre-declared MNAR masks (stock a
  share of the day's own total) give a day-total bias of +9.5% (95% interval 8.7% to 10.3%); the
  evening-tail masks give -0.3% (-1.1% to +0.5%); a post hoc mask with stock fixed before the day
  gives +5.3%. The named fallback (weekday-type profiles) fails the same way. By the gate's rule
  the smaller-bias method is used, read as the smaller worst case over both pre-declared families:
  the named estimator (9.5%) over uniform fill (17.2%, which understates evening tails). So demand
  recovered on stocked-out days may be overstated by about 5 to 10%, most in the hours that stock
  out (the evening); an inverse-sampling correction for the hitting-time selection is a recorded
  candidate, not adopted, because a method chosen after its check fails voids the check.
- **The store.** 300 items at evenly spaced quantiles of each category group's within-store rate
  distribution, times the median store's median: 3,823 units a day, 4.7 to 237 per item, the top
  fifth carrying 47% of units (the paper reports 52% for transactions). Fourteen 168-hour profiles.
  Day-level variance 0.090 (store-day 0.010, item-day 0.079), gamma tables of 16 points; no excess
  of two-unit purchases (slope 0.94, so the pair share is 0).
- **Gaps stated.** No item sells under about 4.7 units a day: the dataset's series exclude slow
  movers (its selection rule is not published), so the world's skew is narrower than a dark store's
  long tail, and "mostly slow movers" in S1 means the slower of these. The data is a Chinese
  frontier-warehouse business (3 km, about 30 minutes) in spring 2024, not an Indian dark store; the
  hold-out week sold 8% more than the training months (median ratio), a seasonal drift the world
  does not model. Shelf lives, lead times and the hub's second delivery are chosen, with reasons.

## The calibration (session 5, stage D, `scripts/kernel/tune_incumbent.py`)

- **Shelf lives times 1/sqrt(2).** The gate fixed the rule before any result: the waste share
  (units discarded over units sold) of the better of I1 and I2, tuned on cell N's tuning seeds,
  must lie in [2.7%, 10.9%] (a factor of two around IFPA's 5.46%, which includes shrink other than
  expiry); otherwise one global scale on shelf lives, bisected in log scale in [0.5, 2], at most six
  steps, stopping on entering the band. At the chosen 1, 2, 3, 5 and 7 days the share was 2.38%; at
  scale 1/sqrt(2) it was 3.09%, so the frozen shelf lives are 17, 34, 51, 85 and 119 hours, and the
  world's provenance says so. Volume, items and the schedule did not move.
- **The frozen world**: a 6-day warm-up (the longest shelf life plus the longest lead time, whole
  days) and 7 measured days, 13 days per replicate.

## Consequences

- Waste rises with stock held (a ladder test), the repair of F-30.
- The same seed gives the same bits on Windows and Linux (pinned digests, `test_golden.py`), and by
  construction in Pyodide, which session 8 measures.
- A batch of replicates is one array computation; each replicate's result is the same alone or in a
  batch (a test), so tuning and the confirmatory run vectorise over seeds.
- Items do not interact (no shared capacity, no substitution): one item's orders leave every other
  item's path unchanged (a test). Tuning items together is therefore exact. This is a stated
  simplification of a dark store.

## Alternatives Rejected

- **SimPy events per unit** (the legacy engine's form): slow at thousands of units a day, and slot
  keying is unnatural there.
- **numpy `Generator` distributions**: not stable across numpy versions and CPUs (F-36).
- **Hourly decision points**: no extra lever, and the guard would bind at zero almost always.
- **Coupled items**: would make the sealed tuning joint over items for no claim of PREREG-1's.
