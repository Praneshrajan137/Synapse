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
