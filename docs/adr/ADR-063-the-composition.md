# ADR-063: SYNAPSE on the release world: the lane first, a challenger only where it has earned trust, always behind the guard

## Status

Accepted (truth program session 6, stage C). It implements PREREG-1's composition (sections 1, 3,
5 and 7) and the operator's decisions D-2 (incumbent first), D-4 (the guard and the autonomy mark)
and D-5 (named components, for ablation) on the release world of ADR-062. Freeze C fixes it,
with its fitted numbers for both worlds (freeze W's world, primary, and deviation 1's, secondary).
It supersedes nothing: the legacy consensus path stays as it is.

## Context

- **The legacy path was the Sentinel.** On the legacy world SYNAPSE's decision reduced to the
  Inventory Sentinel's newsvendor (#104). The agents' own models (isolation forest, LSTM, GNN,
  Pyro, Prophet/TFT) are untrained, heavy, and not bit-exact in a browser.
- **PREREG-1 fixes the comparison.** It requires parity (no cell identity, no simulator call), the
  incumbent first, a guard on every quantity, a zero-margin autonomy mark for letting a challenger
  act, tuning identical to the incumbent's for every tuned part, and everything fitted on
  exploratory seeds only, frozen before the confirmatory round.
- **Stage B measured each component alone** on the first development range (D1, 128 seeds, both
  worlds; `docs/truth/challengers/measure-d1-*.json`):
  - The surge response, planning today's hours: -2.37 a store-day in S1, exactly 0 elsewhere.
  - Same-day sensing: about 0 in N, -1.86 in S1 (it senses surged days), +0.90 in L.
  - The supply response at kappa 1 is the incumbent itself.
  - The Sentinel is far worse (+60 to +970).
- **Findings that bound the claims.** C2 and C3 are out of reach for a blind challenger (findings
  F-43, F-44), and D-4(a)'s zero margin makes trust hard to earn (F-46).

## Decision

1. **Components are the agents' jobs, as light exact kernel policies** (`synapse_kernel/challengers/`):
   - the shelf-life lane (Freshness Guardian, `shelf.py`);
   - same-day demand sensing (Demand Prophet, `sensing.py`);
   - a store-level surge test pooling every item, with a per-item end-of-surge filter (Disruption
     Shield, `surge.py`, decision S6-D-06);
   - a supplier flag for overdue orders (Supplier Trust, `supply.py`);
   - the Sentinel's rule, as built and for this world (`sentinel_release.py`).
2. **The lane gives SYNAPSE's incumbent** (gate item 1). It is I2-P in lane P and I2-L in lane L.
   The store is in lane L once any observed life at receipt is shorter than its item's declared
   life (decision S6-D-10). That uses no parameter of cell L.
3. **Regimes per item.** An item is *supply* while its supplier has an order older than the declared
   lead time; else *surge* while the store's surge alarm stands and the item is attributed to it;
   else *calm*. Regimes are assessed only when a lane-P entry is trusted; lane L's surge and supply
   entries stay with the incumbent, since no exploratory cell can show their effect.
4. **The trust map sends `(lane, regime)` to one decider** (`composition.py`; `fit.py trust`, gate
   item 7). There is one candidate per entry: the lowest D1 mean J pooled over the lane's cells,
   behind the guard, at kappa 1 (S6-D-08). The candidate's tuned composition must beat the lane
   incumbent on D1 before D2 is opened for it. On D2 it must pass D-4(a) with zero margin against the
   composition without it, in every cell of its lane. Entries are taken in the order L/calm, P/calm,
   P/surge, P/supply. The whole is then re-checked against the lane incumbent in all five cells,
   removing entries in reverse order until it passes. Every look at D2 is published with its
   intervals and per-seed deltas.
5. **Every quantity passes the guard** around the lane incumbent's (`release.guard`). A digest of each
   replicate's decision record (lane, regime, decider, `q_I`, the decider's quantity, the order
   placed) is kept, with the clipped share per decider.
6. **Fitted numbers are per world, by one committed procedure:**
   - the surge threshold, the smallest power of two above every evidence seen without a surge
     (`calibrate_surge.py`);
   - kappa tables, by the sealed coordinate search (`fit.py tune`). Its final table, re-evaluated in
     reported mode, must give the tuning's `J_i` to the bit (S6-D-09);
   - the trust map.

   They are written to `docs/truth/composition/params-<world>.json`.
7. **Exact arithmetic and isolation.**
   - The decision path uses + - x /, comparisons, `frexp`/`ldexp`, an exact `ln` from an atanh
     series, and the kernel's `exp_neg` bits.
   - Golden decision digests recorded on Windows (numpy 2.4.4) are reproduced on Linux (numpy 2.4.6).
   - Every reported replicate runs the composition in a fresh child process. The child imports
     `integrity` first, asserts the freeze, closes itself off with an audit hook, and is checked by
     an outcome replay and a decision replay.
8. **Named components, for the ablations** (D-5): the lane rule (the composition holding lane P in
   every part) and each trusted entry's decider (its entry removed). The guard and the arbiter are
   governance and are not ablated.

## The fitted composition (truth session 6, 2026-11-25)

Both worlds end with the same map: **`{P/surge: surge_today}`**. That is the lane incumbent
everywhere, plus the surge response planning today's hours (its tuned kappa) for items attributed to
a surge while the store's alarm stands. The surge thresholds are 2^12 on W and 2^13 on W-d1.

- **D1 checks** (the candidate alone against the lane incumbent, pooled over the lane's cells):
  - `P/surge` opened D2 on both worlds (-0.50 and -0.53).
  - `P/calm` (same-day sensing) opened it on W only (-0.16).
  - `L/calm` and `P/supply` stayed closed. Tuned supply helped in S2 but hurt in S3 out of sample.
- **D2** (D-4(a), zero margin, 128 seeds a cell):
  - W's `P/calm` failed. It helped on average in every cell, but its upper ends lay above zero in
    N, S2 and S3 (+0.07 to +0.08).
  - `P/surge` passed: S1 -1.94 [-2.54, -1.50] on W and -2.15 [-2.89, -1.62] on W-d1, exactly 0 in
    N, S2 and S3.
  - The whole map passed in all five cells.
- **Records.** `docs/truth/composition/trust-{W,W-d1}.json` holds every look with its per-seed
  deltas and the run files' digests; `params-{W,W-d1}.json` holds the parameters freeze C fixes.

## Consequences

- **The claims, honestly.** C1 holds by the lane's construction unless a trusted entry fails a cell.
  C2 in S1 needs about 19 a store-day against a surge response worth about 2. C3 is out of reach.
  The release reports these as found.
- **In N, SYNAPSE's incumbent is I2-P**, which costs +2.4 a store-day against N's selected I2-N. The
  autonomy mark against the cell's incumbent therefore fails in N by construction. It is reported
  beside the mark against the lane incumbent.
- **In L, the first decision comes before any receipt.** The cell-blind lane orders as I2-P once.
  The trace reaches the measured week on a few seeds (4 of 128 on W, at most +0.089).
- **Coupled tuning.** The pooled surge detector couples items, so the sealed search's per-item record
  goes stale. The search runs as sealed, and the check is fidelity (S6-D-09).
- **Compute.** Long runs are spread over GitHub's runners; the repository is public, so they are
  free. The isolation tests run on every runner before its part.

## Alternatives rejected

- **Porting the agents' models:** untrained, heavy, not bit-exact in a browser.
- **Per-item surge evidence (the gate's first design):** a median of 40 hours late at a
  zero-false-alarm threshold, and its no-sales days were overstated.
- **The gate's "lane P for good":** it locked lane P on deviation 1's world.
- **I2-N as the default incumbent, or switching incumbents by detected shocks.** The first loses in
  three cells instead of one. The second is a challenger for the trust map, not a default.
- **Opening D2 for every configuration at once:** it would compute comparisons the procedure never
  looks at. The planner asks for each D2 step only once the steps before it are decided.
