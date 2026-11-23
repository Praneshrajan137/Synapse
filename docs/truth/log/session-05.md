# docs/truth/log/session-05 - the running record of session 5 (Port, Build and Freeze)

Written so that a successor with none of this session's context can resume. Newest entries at the
bottom of each section. Labels as in [`../LOG.md`](../LOG.md) and session 3's record: **measured** (a
command run in this session; the command is given), **read**, **checked** (an outside page opened by
the main session that day), **snippet** (a search result only), **reported** (a subagent's return,
not re-checked), **recalled**, **inferred**, **hypothesis**, **unknown**. Identifiers: S5-M-nn
measurements, S5-D-nn decisions, F-nn findings (continuing `TRUTH-MAP.md`).

## How to resume

1. Read "State" below, then the stage you are in under "Stages".
2. Re-check the preservation snapshot (S5-M-09) before changing anything.
3. Outside actions are approved only as listed in the gate, section 9: O1 to O5 approved at the
   gate; every merge (O6) and the freeze-W push (O7) are asked for at the time.
4. Subagents: at most two or three at a time, each with a cap on calls, this file written first.
5. No challenger, composition or component of SYNAPSE runs on the new world before freeze W is
   pushed. Run the legacy twin with no `TW_*` variable set (E-TP-04).

## State

- **2026-11-23.** Stage A done and green (#104, open: its merge awaits the operator's yes). Stage B
  done (#105, open, CI running): the world built, fitted, its masking check failing the bar fixed
  before it ran (recorded, method chosen by the pre-declared rule). Stage C measured natively;
  native-browser bit parity measured on the golden cases. Stage D's code written (uncommitted on
  `feat/release-world`'s working tree, to go on its own branch) and its full run started. Next:
  read stage D's result, the Pyodide timing on the release world, freeze W, stage E.
- **2026-11-20 to 23.** No work between the evening of 2026-11-20 and 2026-11-23 (the session's
  process was idle); nothing moved on `origin` meanwhile (`main` still `ea205a4`).
- **2026-11-19, after the gate.** The operator approved the gate through plan mode. Stage A is
  under way. Record branch: `docs/truth-session-5`.

## Usage of the Claude plan

Not measured: the operator waived it on 2026-11-18.

## The gate (approved 2026-11-19)

The full text approved, as it was approved; the plan file itself lives outside the repository.

### Context

Session 5 must give the release a world worth deciding in, frozen before any challenger sees it:
SYNAPSE's decision core in the kernel, the world PREREG-1 describes built and fitted to
FreshRetailNet-50K, the strong incumbent tuned exactly as sealed, and freeze W pushed and anchored,
so session 6 can build challengers and push freeze C before **2026-12-11T00:00:00Z**. Tripwire
(PLAN 9.3): sessions 3 to 5 done by **2026-12-06**.

### 0. Session 3's return to Section 0, recorded now

Its record holds no answer; the answers this session acts on: nothing asked for the next prompt;
PREREG-1 names sessions, so running ahead turned calendar labels into sealed commitments (a seal
should bind conditions, not session numbers); two green PRs turned `main` red together (E-TP-07);
the hooks the documents cite never ran (F-34); no time budget per replicate was set (stage C); the
seal's date needed a witness beyond GitHub (S3-M-34/35); the Docker credit was never confirmed.

### 1. What changed since session 3 (measured 2026-11-19; mains power, Balanced plan, battery 70%, 18-50% background CPU; i5-12450HX, 12 logical CPUs, 15.7 GB)

- **S5-M-01** `origin/main` = `main` = `ea205a4` (#103 merged after the close; #100, #101 before
  it). `git ls-remote origin | sha256sum` `48ec643a42b98626`. One stash; eight worktrees
  (`frontend-gates` holds #89's work); only open PR #89 (draft, held, S3-D-02). `main` green at
  `ea205a4`: SYNAPSE CI, Truth Gates and CD all succeeded (runs 44563424191/-251/-211).
- **S5-M-02** The seal: `check_prereg.py` "OK the seal agrees with itself"; every sealed sha256
  equals S3-M-33/-35.
- **S5-M-03** `python -m scripts.verdict`: PASS, 54.3 s (shards 331+8s / 333+18s; consensus
  3.9073, tuned 2.5119, -1.3954, worse 12/12; pins unchanged). Session 3: 44.6-46.7 s on mains.
- **S5-M-04** `pytest tests/kernel tests/beacon`: 24 passed, 55.7 s.
- **S5-M-05** Kernel, legacy world, one 24 h replicate (10 SKUs, ~2,565 demand events): arm E
  median 0.068 s (0.058-0.093), arm O 0.086 s; import 0.25 s. (Legacy harness: ~0.5-0.6 s.)
- **S5-M-06 The Sentinel alone equals the eight-agent consensus arm, 12 of 12, to the bit.**
  Read-only: the legacy Sentinel's own `forecast_from_request` + `InventorySentinelPipeline.decide`
  + the consensus arm's reorder translation, driven by the kernel's `run_replicate` on
  `legacy_primary.json` and priced by `replicate_cost`, equals every consensus pin in
  `verdict-pins.json` as `float.hex`; 1.2 s for all twelve (the eight-agent arm: ~2.2 s each).
- **S5-M-07** Kernel passes `mypy --strict` (10 files) and `ruff`; CI lints neither the kernel nor
  `scripts/verdict` (`ci.yml:81-92` covers `packages/synapse_common`, `agents`, `orchestrator`).
- **S5-M-08** `.venv`: numpy 2.4.4, pandas 2.3.3, pyarrow 23.0.1, scipy 1.17.1; no `pre-commit`,
  no `opentimestamps`. Node 24.11.0.
- **Checked, FreshRetailNet-50K** (HF API and card, arXiv 2505.16319 v5 of 2026-06-18): licence
  `cc-by-4.0`, "ready for commercial/non-commercial use", cite the paper; **not gated**; revision
  `c374e85975c82816c495acfa904cc55ab14a47d3` (lastModified 2026-10-09); `data/train.parquet`
  106,436,287 B (LFS sha256 `6706832d...`), `data/eval.parquet` 8,440,124 B (`1b118840...`);
  898 stores, 18 cities, 50,000 store-product series x 90 days; fields include `hours_sale`,
  `hours_stock_status`, `stock_hour6_22_cnt`, category ids (encoded), discount, holiday, activity,
  weather. **Sales are "globally normalised and multiplied by an undisclosed coefficient"** (F-35
  below). Paper: "frontier warehouse" fresh e-commerce, 3 km radius, ~30-min delivery; stock
  indicator 1 = in stock (Eq. 1); restocking at 6 AM, stockouts <2% then up to 26% near 8 PM;
  weekday peaks 9 AM and 4 PM, weekends one larger 9 AM peak; power law alpha 2.83, top 20% of
  SKUs = 51.8% of transactions; recovery benchmarked by a "Controlled MNAR Simulation" masking
  in-stock periods: TimesNet WAPE 27.62%, WPE 1.43% (best of seven). Contradictions: card 865
  SKUs vs abstract 863; "three-month period" vs March-June 2024.
- **Checked, numpy's random compatibility policy (v2.5 manual):** `Generator` distribution
  streams may change in feature releases; reproducibility needs "the same build ... same
  environment ... same machine"; different CPUs can change edge cases that cascade.
- **F-35 (checked + inferred). The dataset fixes shapes and relative skew, not absolute volume.**
  An undisclosed scale coefficient multiplies every sale. *False if* the hourly values lie on an
  integer lattice whose step recovers unit counts, or the Poisson noise floor identifies the scale
  (stage B tests both).
- **Checked, Pyodide 314.0.8 docs:** ships numpy **2.4.6** (laptop: 2.4.4); **simpy is not
  shipped** (pure-Python wheel via micropip only). **Checked, Random123 `kat_vectors`:** three
  Threefry-2x32-20 answer vectors (e.g. counter 0, key 0 -> `6b200159 99ba4efe`).
- **F-36 (checked + inferred). A world drawn with numpy `Generator` distributions cannot promise
  native-browser bit parity**, because Pyodide ships its own numpy build and version; after freeze
  W, repairing that is a deviation. *False if* the native and Pyodide streams agree for every
  distribution used, across the numpy versions involved.

### 2. Frontier calibration for this session's properties

Rows 1-16, PV, P1-P6, KB, U, W of session 3's scorecard carry forward unchanged in definition.
New rows:

| # | Property | Leading practice, its number (label) | SYNAPSE now (measured) | Target this session |
|---|---|---|---|---|
| P7 | Decision core in the kernel | - (definitional: the browser shows what was measured) | Not ported (S3-D-05); legacy code equals consensus 12/12 (S5-M-06) | Kernel port equal per decision and per cost, 12/12, run by the verdict |
| P8 | Truth to perishable grocery | Research test beds: fixed shelf life, FIFO issuing, lost sales, lead times (Broekmeulen & van Donselaar 2009, C&OR 36(11), venue checked S3; Haijema & Minner 2019, IJPE 209, 11,177 instances, snippet); dark stores restock 2-3x a day (TechCrunch 2024, snippet) | Waste a clock (F-30); 10 equal items; one profile | Batches by age, FIFO outdating; many skewed items; a 168-hour shape; supplier schedules; five cells as sealed |
| P9 | Fit to real data, error stated | FRN paper: recovery by masking, TimesNet WAPE 27.62%, WPE 1.43% (checked) | Declared shape, no fit | Named method's masking WAPE and bias with intervals, beside a no-recovery baseline under the same protocol |
| P10 | Stock-out-hidden demand recovered | Stock-out timing is "almost all you need": 76.1% of the censoring loss recovered (Jain, Rudi & Wang 2015, OR 63(1), snippet); FRN: underestimation 7.37% to near zero (checked) | None | Exposure-weighted profile estimator (the hourly form of timing MLE), bias by masking < the raw-sales bias |
| P11 | Draw independence and cross-runtime exactness | Counter-based RNGs keyed by stream and counter (Salmon et al. 2011, Random123, answer vectors checked); JAX's default PRNG is `threefry2x32`, counter-based (checked); numpy streams not stable across versions/CPUs (checked) | Named numpy substreams; demand independent of actions within a run; Generator distributions (version-dependent) | Every draw a pure function of (seed, purpose, entity, slot), generated before any policy runs; integer state; no libm in the draw path |
| P12 | Legacy-mode parity | Characterisation tests beside an untouched legacy (recalled) | Equal to the bit, arms E and O, 12 seeds | Unchanged, plus the Sentinel |
| P13 | Speed: replicate, tuning run, browser day | GPU simulation optimisation for perishables in JAX (Farrington et al. 2025, AOR, snippet; no per-replicate figure taken); PLAN target 3 s per simulated day in a browser | Legacy replicate 0.068 s (24 h, 10 SKUs); new world unbuilt | Measured per replicate, per batch of seeds, per tuning evaluation, natively and on CI; Pyodide measured if approved; budget for sessions 5-8 derived |
| P14 | Incumbent strength | Base stock is the (s,S) optimum with zero setup (recalled); age-aware base stock (EWA, BSP-low-EW) near-optimal (snippet) | One (s,S) per supplier (strawman, F-29) | I1 and I2 tuned per item and part of the day to convergence; evaluation counts and per-item convergence published; generalisation gap tuning vs validation reported |
| P15 | Hook layer enforcement | Every cited gate runs in CI (E-TP-08) | 0 of 15 hooks ever ran (F-34) | Each hook run over the tree; wired into a job or retired by D-5 |

### 3. Questions, ranked by leverage

1. **Can native and browser runs give the same bits** given F-36? Decides the randomness design,
   which freeze W then fixes. Answer by design (counter-based, integer state) and by measurement
   (Pyodide, if approved).
2. **Does FRN carry recoverable volumes (F-35)?** Lattice step or noise floor; else the store's
   scale is declared (chosen) and said so.
3. **Does the named censoring method recover masked in-stock hours with small bias**, especially
   evening tails (F-13a's lesson: the evening decides cost)? If it fails, the fitted evening shape
   is wrong.
4. **Uncomfortable: does D-4(b)'s guard leave C2 any room?** With q_I = 0 the guard pins a
   challenger to 0, and S1 surges hit mostly slow movers. The guard-headroom report answers it
   before session 6.
5. **Is the incumbent's waste share in N near IFPA's 5.46%** with cited shelf lives? If not, the
   pre-declared calibration (section 7) runs before freeze W.
6. **Can tuning to convergence be afforded, and does it converge to the lattice optimum** rather
   than overfit 32 seeds? Counts, timings, 1-D profiles at the optimum, a restart sample, and the
   tuning-validation gap.
7. **Does the kernel port equal the consensus arm per decision**, not only per cost?
8. **Uncomfortable: can a stateful policy recover the day index or horizon by counting calls?**
   Yes, in principle; the observation hides them, end stock is reported (sealed). Recorded as a
   rule session 6 must test for its challengers.
9. Which ambiguities in the sealed text could let a later choice bias a claim? Section 7 fixes
   every one found before any result.
10. Which of the 15 hooks fail on the tree today, and which duplicate a CI job?

### 4. Assumptions

- **Verified:** section 1; FRN licence, revision and sizes; the numpy policy; kernel strict-clean.
- **Inferred:** `hours_sale` and `hours_stock_status` hold 24 hourly values; status 1 = in stock
  (paper Eq. 1, to be confirmed against zero sales); the scale coefficient is global; Dingdong's
  frontier warehouses are close kin of Indian dark stores (3 km, ~30 min vs ~10 min).
- **Unknown:** FRN's absolute scale; the world's speed and bit parity under Pyodide; the incumbent's waste share;
  shock headroom; tuning cost; whether the operator claims a Docker credit (not needed: the laptop
  suffices, S5-M-05).

### 5. What must be preserved, and the proof

| What | Proof |
|---|---|
| Legacy behaviour | Verdict PASS on every PR with pins unchanged; `tests/kernel/test_legacy_parity.py` green |
| Sealed files and sealed source sets | `check_prereg.py` OK; `git diff --name-only origin/main...<branch>` lists nothing under `docs/truth/sealed/` (except new freeze-W files), `uplift/`, `digital_twin/`, `infrastructure/quality/comparator-tuning.yaml` |
| Kernel lightness | `test_closure.py` extended to new modules: third-party = numpy (+ simpy for legacy mode) |
| Worktrees, stash, `.kiro/settings/` | Porcelain digests before and after; `.kiro/settings/` never staged |
| No component of SYNAPSE on the new world before freeze W | The Sentinel port accepts only the legacy observation type; no test or script runs it on the new world |
| Main stays green | Each PR synced with `main` and green on the synced head before merge (E-TP-07) |

### 6. The stages (order A, B, C, D, E; each complete, verified, committed before the next)

### A. The decision core in the kernel (branch `feat/kernel-sentinel`)
- `synapse_kernel/policies/sentinel.py`: the request the consensus arm builds for the Sentinel
  (only the keys it reads, with identical int/float conversions), `forecast_from_request`'s rules
  (rate since start, landed lead-time mean or the 1-day prior, review 60 min, Poisson std, the
  missing-entry defaults mean 10 / std 3), the newsvendor (Acklam inverse normal at 8/9: central
  branch, rational only), `round(.., 2)`, and the reorder translation. Light: no pydantic,
  structlog or `synapse_common`. Accepts only the legacy observation type.
- Tests: light job, kernel port vs `verdict-pins.json` consensus costs on its 12 seeds (float.hex);
  parity job, kernel port vs the legacy Sentinel code **decision by decision** on the 12 seeds.
- The verdict runs it: prices the kernel port beside the miniature (about 1 s) and compares it
  **with the pins** (which equal the measured consensus whenever the verdict passes), so a change
  to the agents still reads WORSE or CHANGED and a change to the port alone reads as itself. New
  outcome `KERNEL_DIVERGED = 8`, ranked **after CHANGED** (just above PASS): re-pinning the
  consensus then forces the port to move in the same PR. `tests/verdict`, `verdict.yml`'s code
  list and the fault proof updated; two new cases (a planted edit in the port; an edit in the
  agents' newsvendor with pins re-written) plus all 16 old cases classifying as before.
- CI: kernel light job adds `ruff` + `mypy --strict synapse_kernel/`; verdict workflow paths add
  `synapse_kernel/**`, `tests/kernel/**`.
- ADR-060 (the decision kernel beside the legacy) and ADR-061 (the verdict) written here, where
  both change (ADR-059 is taken on #89's branch). This moves stage E's ADR item earlier, on purpose.
- *Accepted when* the comparison is a test, its result (identical, or the first divergence
  diagnosed) is recorded, and the verdict runs it. *Rejected:* importing the legacy agent code
  (breaks the light closure); a safety-shard test against pins (mislabels a divergence as SAFETY
  and can pass stale pins).

### B. The truer world, as sealed (branches `feat/release-world`; may land as two PRs: machinery, then fit)
Design (ADR-062):
- **Hourly slots**, matching the data's resolution. Per hour: scheduled receipts land as one batch
  per item (expiry = arrival + remaining shelf life), expired batches are discarded (W), a
  supplier's cut-off is a decision point, then sales: `min(demand, on hand)` issued **first in,
  first out**, the rest lost (L); holding H by the trapezoid over the hour.
- **Integer state** (units, hours, batches); J computed from integer totals with `math.fsum`.
- **Randomness, counter-based:** every draw is Threefry-2x32-20 (Salmon et al. 2011; JAX's
  generator) of key = seed, counter = (purpose, entity, slot, index), in numpy uint32 arithmetic,
  checked against Random123's published answer vectors and an independent pure-Python version.
  Samplers from uniforms with exact arithmetic only: Poisson by inversion (one uniform per item-hour)
  with an `exp` built from + - * / and `ldexp`; day-level multipliers from fitted K-point tables
  stored as data. **The whole scenario of a replicate (demand per item-hour, day factors, shock
  draws) is generated before any policy acts**, so a policy cannot move a draw by construction.
  No `numpy.random` and no libm call in the world's draw path (an AST check enforces it).
- **Demand:** item rates at evenly spaced quantiles of FRN's recovered within-store rate
  distribution (stratified by category); a 168-hour-of-week profile (per category group if the data
  support it), mean exactly one; day-level variance components (store-day and item-day) fitted.
  Scale: recovered (F-35's two tests: an integer lattice in the hourly values; the Poisson noise
  floor, the slope of CV^2 of daily totals on 1/mean across series), else declared: 2,000 units per
  store-day, the magnitude PREREG-1 section 4 uses, marked chosen. Item count N chosen in stage B
  from the fitted assortment and stage C's timing, between 200 and 600 (default 300).
- **Censoring method (named):** the exposure-weighted profile estimator: a series-day's level =
  in-stock sales / profile mass of in-stock hours (Poisson MLE under a known profile; the hourly
  checkpoint form of Jain, Rudi & Wang 2015), alternated with the profile fit until stable.
  **Masking check:** on fully in-stock series-days, two mask families: (1) MNAR, like real
  stock-outs: a synthetic stock level drawn as a share of the day's total, every hour after
  cumulative sales reach it masked and the crossing hour partly observed; (2) evening tails from
  the empirical first-stock-out-hour distribution. Report WAPE and signed bias of masked hours and
  of daily totals, with store-bootstrap intervals, beside zero-fill and raw-sales baselines under
  the same protocol; plus the hold-out error of the fitted shape on the eval split. Before use,
  confirm status 1 = in stock against zero sales. Fit scripts live in `scripts/world/`
  (pandas/pyarrow, outside the kernel); outputs committed as JSON with the dataset revision, file
  sha256s and the CC BY 4.0 attribution (title, authors, link, licence, changes made; D-19).
- **Supply (chosen/cited):** suppliers mapped from encoded first categories; fresh produce daily at
  06:00 (FRN's 6 AM restock, checked), a hub 2x a day (2-3x a day, snippet); lead times chosen;
  one supplier per item; no pack sizes, no MOQ (sealed).
- **Decision points = order cut-offs** (delivery time - lead time), per supplier; an order in whole
  units rides the next scheduled delivery. Reasons, in order: a store raises indents at fixed
  times; an order placed between cut-offs rides the same delivery, so hourly decisions add no lever;
  PLAN 4.2's Play orders at delivery slots. Stated consequences: with one or two cut-offs a day,
  most of an item's six part-of-day factors never apply (reported "unused"); and hourly decisions
  would have left q_I at 0 most hours, so the guard would pin any challenger to 0. ADR-062 says
  both, since the cadence is a world choice that also bears on challengers.
- **Shelf life:** remaining shelf life at receipt per item, chosen in 1-7 days, independent of the
  item's rate; marked chosen, because no strong source was found (context, snippets only: 3-9 days
  in van Donselaar & Broekmeulen 2025; 7.7-10.4 days from delivery to use-by in a small UK online
  grocery survey). One global scale is the calibration knob (section 7).
- **Observation** exactly PREREG-1 section 1: hourly sales since the last call (censored), on hand
  by batch with expiry, open orders with placement times, receipts, realised lead times, hour of
  day, day of week. No day index, horizon, cell or shock field, and **no absolute time**: expiry as
  hours remaining, placement and receipt as hours ago (an absolute clock would reveal the day
  index). Test: shifting the clock origin by whole weeks leaves the observation's bytes unchanged.
- **Construction inputs:** one `PolicyInputs` object (cell N's declared parameters + exploratory
  records), whose canonical bytes are the same for every cell.
- Prices all 1 (chosen: every term of J is proportional to p_i, so per-item decisions do not depend
  on it; p_c = 1). Initial state, warm-up and horizon exactly as sealed.
- Licence: FRN registered in `infrastructure/data/dataset-licences.yaml` with all six R8.1 fields,
  read at the source; C74 run.
- *Accepted when:* W rises with stock held (a ladder of order-up-to factors, several seeds; fails
  on the legacy clock); the masking check is reported with its error; a test shows orders move no
  draw (scenario bytes identical under opposite policies; the engine has no generator); a test shows
  no policy can read cell, shock, day index or horizon, and construction inputs are byte-identical
  across the five cells; legacy mode still equals the harness; closure stays light; plus
  conservation (received = sold + discarded + end stock, exact), FIFO, item non-interference,
  batch-of-seeds = per-seed runs to the bit, cell rules, provenance on every parameter. Each test
  shown failing on a planted fault (LIFO, action-keyed draw, leaked day index, waste clock).
- *Rejected:* SimPy events (slow at thousands of units a day; slot keying unnatural); numpy
  `Generator` distributions (F-36); deep-learning recovery (heavy, opaque, not needed for aggregate
  shape); coupled items (would make tuning joint; stated as a simplification); Colab (the fit is
  closed-form and runs on the laptop; a departure from PLAN 6, not sealed).
- *Pre-mortem:* browser bits differ (prevented by design, measured); the evening shape biased
  (masking by evening tails); "not fitted" (state what is fitted vs chosen); end-of-horizon gaming
  (end stock reported).

### C. Fast enough (branch `feat/kernel-bench`)
- `python -m scripts.kernel.bench`: time per replicate (one seed; batches of 32 and 128 seeds as an
  array axis), per scenario, per tuning evaluation, natively (with power state) and on CI (a step in
  `kernel.yml`); Pyodide under Node if approved (one simulated day, one replicate, digest equality).
- Derive, not guess: tuning cost = evaluations x time; confirmatory = up to 2,000 x 5 cells x arms
  (+ ablations); browser = simulated day vs 3 s. Optimise until all three fit, or state each cost.

### D. The incumbent tuned as sealed, then freeze W (branches `feat/incumbent`, then `docs/freeze-w`)
- I1, I2 and the tuner exactly as PREREG-1 section 3, with section 7's implementation choices;
  tuned in N, L and pooled shocks; selected per cell on validation seeds; contest incumbent chosen.
- Report: tuned tables, evaluation counts, per-item convergence, tuning-validation gap, 1-D profiles
  and a restart sample; waste share in N vs 5.46%; D_c, p_c, M_c per cell (from declared
  parameters, exactly); shock headroom (oracle told the shock, validation seeds); **exploratory:
  headroom inside the guard** (the oracle clipped to the whole-unit guard of section 7, with the
  clipped share).
- **Freeze W:** `docs/truth/sealed/FREEZE-W.md` + `freeze-w.json` + `SHA256SUMS-W` + a stdlib
  `check_freeze_w.py` that recomputes every digest and ticks PREREG-1 section 5's list item by item
  (the kernel's file list, the world, the item set, suppliers, lead times, schedule, shelf lives,
  prices, initial state, the censoring method and its masking check, the incumbent's tables,
  counts and selection, D_c, p_c, M_c, headroom). CI fails on an edit to a listed file; new files
  are allowed (session 6 adds challengers); a run-time check refuses a run whose frozen modules
  differ from their digests or were patched in memory. Fresh-context attack before the push. Time
  witnesses as for the seal: the PR's server-side merge time and OpenTimestamps (S3-M-34/35). Push
  only on the operator's yes at the time.

### E. The debts (branch `chore/pre-commit-hooks`)
- Make `.pre-commit-config.yaml` parse (inline `python -c` bodies moved to `scripts/hooks/*.py`);
  run each of the 15 hooks over the tree and record its verdict; per hook: wire it (a CI job runs
  it; a hook that duplicates a job is rewired to run that job's own command), fix it (a hook bug,
  or a real violation small enough to repair), or retire it on D-5's grounds only (cannot be made
  to fail, or tests only what a document says); each kept hook shown failing on a planted
  violation; `CLAUDE.md` cites no hook a job does not run.

### 7. Implementation choices fixed now, before any result (frozen at W)

- **Tuning, literally as sealed:** one global loop; at each step a sweep visits parts of the day
  in clock order and, for every item at once, evaluates k+delta and k-delta (k >= 0) in the same
  replicates; an item moves to the lower J_i only if strictly below its current J_i (exact tie
  between the two: the smaller k); the step halves after a sweep in which **no** item moved; stop
  after an unchanged sweep at 1/32. Evaluation counts are those actually run; per-item
  convergence = the sweep of each item's last move. Parts with no decision of an item are reported
  "unused". J_i at the primary weights, per store-day, over the tuning seeds. A non-interference
  test (one item's orders leave every other item's path unchanged) proves "items tuned together"
  is exact here.
- **mu and the protection interval:** the N version reads N's 32 tuning seeds, the L version L's,
  the pooled version those of N, S1, S2 and S3 together; the table is the recorded (uncensored)
  demand per item x day of week x hour over all simulated hours. The protection interval of an
  order placed at t runs from t to the delivery after the one this order rides (lead time plus
  the time to the next delivery). I2 depletes the on-hand batches oldest first by the same table
  from t to each batch's expiry; its order is `max(0, ceil(S - IP + expected outdating))`.
- **Cells:** shock times drawn continuous; an hour belongs to a shock if its start lies in
  [onset, onset + duration); a continuous arrival time lands at the first hour boundary at or after
  it (never earlier). S2 applies at placement: lead time x v, then the next scheduled delivery.
  **S3 literally as sealed:** an order placed during the outage arrives at outage end + lead time
  (an unscheduled receipt); deliveries scheduled inside the window do not happen and their orders
  arrive at the outage end (chosen: the sealed text is silent on them). Warm-up and calendar from
  cell N's nominal parameters in every cell (a reading of "nominal", recorded); replicates start
  Monday 00:00 (chosen). Any delivery-side randomness keyed by (supplier, scheduled delivery),
  never by an order.
- **Fixed at freeze W, not later:** the item count and the store's volume (PLAN 6 lets session 8
  set the item count; after W that would be a deviation, so stage C sizes it for the browser now;
  any Play or phone world is a separate configuration that carries no claim); the schema of the
  exploratory records in `PolicyInputs` (per seed and cell: hourly demand, sales, receipts and
  stock by item).
- **The guard** is a pure, parameter-free kernel function frozen at W (D-4 puts it in session 5;
  session 6 composes with it), used here only inside the headroom report the operator asked for.
- **Masking check, judged in advance:** passes if the named method's signed bias on masked daily
  totals (MNAR masks) is within +-3% with its 95% interval inside +-5%, and its WAPE beats both
  baselines. Else the named fallback runs (the same estimator with profiles stratified by category
  and weekday type), and if that also fails, the smaller-bias method is used and labelled as
  failing.
- **Prices of 1** also set how items weigh against each other in J, s_c and n_c (units weigh
  equally): stated in ADR-062.
- **Hooks (F-34):** a hook that duplicates a CI job is rewired to run that job's own command (one
  definition); a hook is retired only on D-5's grounds (cannot be made to fail, or tests only what
  a document says).
- **Waste calibration, "if at all":** measure = units discarded / units sold in N (= retail value
  at unit prices), of whichever of I1 and I2 has the lower mean J on the **tuning** seeds, on the
  tuning seeds. IFPA's 5.46% includes non-expiry shrink, so expiry alone should sit at or below it:
  **no recalibration if the share lies in [2.7%, 10.9%]** (a factor of two around 5.46%); otherwise
  one knob, a global scale on shelf lives in [0.5, 2.0], bisected in log scale toward 5.46%, at most
  six iterations, each recorded; volume and item set fixed first and never moved with it; if the
  response is non-monotone or the band unreachable, freeze at the closest point and report the gap.
  The validation seeds are opened once, for the final selection. Never after freeze W.
- **Initial state:** per item, one batch at age zero of `ceil(mean demand over L_j + R_j)` from
  hour 0, with `R_j` the interval between the supplier's consecutive deliveries; nothing on order.
- **Guard in whole units (for the guard-headroom report, frozen for session 6):** the admissible
  interval is `[ceil(q_I / 2), 2 q_I]`; `q_I = 0` gives `{0}` (sealed).
- **Headroom oracle (description only):** the cell's selected incumbent version, with the shock
  inserted into what it plans against: S1, the affected items' mean demand times u over the
  window's overlap with the protection interval; S2 and S3, the protection interval and the
  pipeline's arrival times as they will actually land. Reported unclipped and clipped by the guard,
  with the clipped share.
- **Parity, read with section 3:** the incumbent's versions (I1 and I2, each tuned in N, in L and
  on pooled shocks) are separate named policies; the parity test asserts each version's
  construction inputs are byte-identical across the five cells. Which version stands as "the
  incumbent" in a cell is the sealed selection rule applied by the analysis, never told to the
  policy. Session 6 must decide, before freeze C, which incumbent SYNAPSE contains (recorded as an
  open question for it).
- **The frozen set:** every file under `synapse_kernel/` at freeze W (later additions allowed,
  edits are deviations), the world and incumbent JSON, and the fit and masking scripts with their
  outputs. The observation names the deciding supplier, which the declared schedule already
  implies.

### 8. Verification, end to end

Per stage: the new tests (each shown failing on a planted fault), `make verdict` PASS,
`pytest tests/kernel tests/beacon tests/verdict`, `check_prereg.py`, ruff + `mypy --strict` on new
code, the truth gates (`verify_claims`, `doc_truth`, `gate_surface`, `workflow_shape_truth`, C74),
CI green on the synced head, and before each merge the composed tree rehearsed with CI's inline
shell gates as well as the Python ones (E-TP-07). At the close: the merged `main` re-measured (verdict, kernel parity,
bench), the panel summoned, scorecard filled, session 6's prompt saved locally (git-ignored).

### 9. Outside actions for one yes (the merges and the freeze push are asked at the time)

| # | Action |
|---|---|
| O1 | Download FreshRetailNet-50K revision `c374e859`, two parquet files, 114.9 MB, from huggingface.co (CC BY 4.0, not gated) into `C:\Users\Pranesh\Projects\synapse-data\freshretailnet-50k\` (outside the repository) |
| O2 | `pre-commit` (MIT) from PyPI into a scratch environment, plus what its local hooks install (pyyaml, jsonschema); no remote hook repositories unless kept |
| O3 | `pyodide` from npm, with its numpy, into a scratch folder, to measure the world under WebAssembly |
| O4 | `opentimestamps` 0.4.5 (LGPL-3, scratch only, not a dependency) from PyPI; stamp freeze W's sums file (nonce-blinded digest to the four public calendars) and later upgrade |
| O5 | Push this session's branches and open their PRs (A, B, C, D, freeze W, E, the record) |
| O6 | **ask at the time** - merge each PR once green on a head synced with `main` (or a standing approval like S3-D-04, if the operator prefers) |
| O7 | **ask at the time** - push freeze W |
| - | Not requested: Docker sandbox, Colab, Google Cloud (none needed) |

### 10. The attack at the gate (one fresh-context reviewer, 10 tool calls, 2026-11-19)

Checked before use. **Adopted:** B1 (S3 implemented literally: orders placed in an outage arrive
at its end plus lead time; verified in `prereg-1.json` `cells.S3.orders_during`); M1's design point
(the port is compared with the pins and `KERNEL_DIVERGED` ranks after CHANGED); M2 (the four
incumbent ambiguities settled in section 7); M3 (headroom oracle defined, censoring code hashed,
item count and volume fixed at W, record schema fixed); M4 (calibration measure, band, bracket and
stopping rule; volume fixed first; selection inside the loop on tuning seeds); M5 (no absolute time
in the observation; clock-shift test); M6 (new files allowed; run-time digest check); and the minor
points (cut-off rationale stated with its consequence for the guard; the sealed global sweep
implemented literally; N's warm-up recorded as a reading; delivery randomness keyed by delivery;
price weighting stated; the guard a frozen pure function; hooks rewired rather than retired for
duplication; CC BY 4.0 attribution; the masking check's pass condition and fallback named).
**Did not hold:** M1's scenario (session 3's record shows F2, F3 and Q1 were caught as SAFETY,
which outranks any new outcome); "ADR-055's outcome text" (ADR-055 defines no verdict outcomes).
The questions it raised for the operator are settled in this text, except the outside actions.

### 11. The panel at the gate

Domain expert: passes with a condition (scale and shelf lives honestly marked; the guard question
answered before session 6). Architect: passes (one engine, integer state, keyed draws, legacy
untouched). Adversary: passes with a note (counting policies; Q8). Verifier: passes if every new
test is shown failing on a planted fault. Operator at 3 a.m.: passes (verdict names a kernel
divergence). Release engineer: passes (small PRs, synced before merge). Maintainer: passes (ADRs
060-062). User, store manager, stranger: not yet (nothing visitor-facing this session). Performance
engineer: pending stage C's measurements.

## Decisions of this session

- **S5-D-01 (2026-11-19). The gate is approved, with its outside actions O1 to O5.** Merges (O6) and
  the push of freeze W (O7) are asked for at the time.
- **S5-D-02 (2026-11-19). The record lands last.** This file lives on `docs/truth-session-5`, is
  pushed as the stages land and merged at the session's close, so `main`'s `LOG.md` points here once
  the session's work is on `main`.

## Stages

### Preparation

- **S5-M-09 Preservation snapshot (measured, before any change; kept in the session's scratch
  folder, not in the repository).** Heads and porcelain-status digests of all eight worktrees (`main`
  `ea205a4`, 1 line: `.kiro/settings/`; `frontend-gates` `9da8ceb`, 20 lines, its 17 changed files
  hashed; the other six clean), the stash (1 entry, digest `adb7c37156c3ac6a`), `.kiro/settings/`
  (digest `15f381d03b8eebcc`) and the ref list (144 refs, digest `f3d6af1473fbc192` without
  `refs/codex/`).
- **S5-M-10 FreshRetailNet-50K downloaded (O1; measured).** `curl` from
  `huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K/resolve/c374e85975c82816c495acfa904cc55ab14a47d3/data/`
  into `C:\Users\Pranesh\Projects\synapse-data\freshretailnet-50k\rev-c374e859\data\` (outside the
  repository): `eval.parquet` 8,440,124 B, sha256
  `1b118840664280c6b88bffc84c80ee1f54c05d911e354b7599e5da10995e960e`; `train.parquet` 106,436,287 B,
  sha256 `6706832db892bbae4969c19d87e07975d2543d2ba7d7d4756360654785de5a3d`: both equal the
  dataset's LFS object ids read from the Hugging Face API.

### A. The decision core in the kernel (PR #104, branch `feat/kernel-sentinel`, commit `cac4246`)

- **What was built.** `synapse_kernel/policies/sentinel.py`, the Sentinel alone: the request the
  consensus arm builds for the Inventory Sentinel (only the keys it reads), `forecast_from_request`'s
  rules, the newsvendor at the fractile 8/9 (Acklam's inverse normal: the central branch, a rational
  function, no transcendental call) and the consensus arm's translation, in the legacy order of
  floating-point operations; numpy and simpy only; it refuses any observation but the legacy world's.
  The verdict prices it and compares it with the consensus pins: new outcome `KERNEL_DIVERGED = 8`,
  ranked after CHANGED; `--repin` refuses unless the port reproduces the measured consensus. CI: the
  kernel's light job runs the new test plus ruff and `mypy --strict synapse_kernel/`. ADR-060 (the
  kernel) and ADR-061 (the verdict) written here, moving stage E's ADR item earlier on purpose.
- **S5-M-11 Identical, not diagnosed (measured).** On E5's twelve seeds the port costs exactly what
  the eight-agent consensus arm costs (`float.hex`, 12 of 12), and equals the legacy pathway (the
  consensus arm's own request builder, the Sentinel's own A2A handler, the arm's own translator) on
  every one of 288 decisions and 2,880 quantities (`tests/kernel/test_sentinel_*.py`). So S3-D-05's
  question has its answer: on the measured cell SYNAPSE's eight-agent decision is one newsvendor
  rule, to the bit, and nothing downstream of the Sentinel's proposal (fast path, guardrails,
  dispatch classification) moved a quantity on these seeds. Both tests fail on a planted one-decimal
  rounding fault, naming the first divergence (60 min, `sku_0`, 95.1 against 95.15). The port's
  inverse normal equals the agent's on 20,000 random points.
- **S5-M-12 The verdict with the port (measured).** Laptop, mains power: PASS in 53.0 s, "kernel
  Sentinel alone: equal to the measured consensus on 12 of 12 seeds", pins unchanged. CI on Linux
  (run 44577842343): PASS in 30.8 s on 4 CPUs, the same line, pins unchanged. All 20 checks of #104
  green (kernel light 19 s, kernel parity 3 min 55 s, verdict 4 min, truth gates 3 min 30 s). On a
  clean export of the commit: `verify_claims` 57 PASS / 0 FAIL / 11 SKIP (as `main`), `doc_truth`
  20/20, `gate_surface --check` OK after regenerating `GATE_SURFACE.md` for the workflow edits.
  In the working checkout `verify_claims` also fails C44 (module liveness) on a stale
  `frontend/node_modules` path: environmental, absent from a clean checkout of `main`.
- **S5-M-13 The fault proof's 16 old cases (measured; the first run died when the session's process
  exited: `git archive` failed with Windows status 0xC0000142, and was re-run).** On `cac4246`: the
  clean tree PASS three times (29.3, 27.8, 28.8 s); F1, F2, F3, F4, F5, Q1, Q4 and Q4b SAFETY; Q3, Q5,
  Q6b and Q7 CONTROL_MOVED; Q6 REFUSED_ENV; every case within its expected set. Q4 and Q4b are now
  caught by the safety shards, where session 3 saw a changed decision and a cross-process repeat.
  That run used `main`'s copy of the script, without the two new kernel cases.
- **S5-M-17 The fault proof, 18 of 18 (measured; run from a worktree of the stage A branch on
  `cac4246`; record `infrastructure/quality/verdict-fault-proof.json`, commits `6af19bb`, `b8e810d`).**
  The 16 cases above, judged the same, plus K1 (the port rounds to one decimal): KERNEL_DIVERGED,
  and K2 (a consensus pin one ulp dearer): CHANGED, which outranks the port's divergence from the
  same pin. **Correction:** commit `6af19bb`'s subject says "21 of 21"; the count is 18 (16 + 2),
  a miscount of mine, corrected here and on the PR; the history is not rewritten.

### B. The truer world (branch `feat/release-world`)

- **S5-M-14 What the dataset is, measured (10% sample, then all 4,500,000 rows).** 50,000
  store-product series, 898 stores, 865 products, 32 encoded first categories, 90 days
  (2024-03-28 to 2024-06-25); the eval split is the following 7 days (2024-06-26 to 07-02), a clean
  time hold-out. Each row holds 24 hourly values. A store holds 50 sampled series at the median
  (1 to 164), not its whole assortment. The top five categories carry 71% of units.
- **F-35 falsified (measured).** The card says sales are normalised by an undisclosed coefficient,
  but 99.56% of positive hourly values are multiples of 0.1 (most common 0.1, 0.2, 0.3), and, with
  units = 10 x value, the noise floor across 4,431 series with at least 20 fully in-stock days is
  CV^2 = 1.287 / mean + 0.107: a slope near one, as counts of purchases give. So unit counts are
  recoverable; the slope above one says some purchases take two units, and the intercept is
  day-to-day variability.
- **F-37 The stock flag is an out-of-stock flag (measured and checked).** `hours_stock_status` = 1
  means out of stock: it sums over hours 6 to 21 to `stock_hour6_22_cnt` on 100% of 450,000 sampled
  rows, and sales occur in 28.7% of status-0 hours against 2.9% of status-1 hours. The paper's
  censoring indicator (its Eq. 1, checked 2026-11-19) is 1 for stock available: the complement. The
  gate assumed the paper's reading; the data settled it before any use.
- **S5-M-15 The shape the data shows (raw, 10% sample).** On fully in-stock days the hourly share
  peaks at 09:00 (9.4%) and 16:00 (8.6%) and is under 1% from 23:00 to 05:00. The out-of-stock share
  is 4.8% at 07:00, after the 06:00 restock, and rises to 41.7% by 22:00: raw evening sales are
  heavily censored, so recovery decides the evening shape (F-13a's lesson). Weekends sell 15-19%
  more than the mean day. Only 40% of series-days are fully in stock.
- **The machinery (commit `e3ae6cf`).** `synapse_kernel/release/`: Threefry-2x32-20 keyed by seed
  and read by (purpose, entity, slot, index); exact samplers; declared world with provenance; the
  five cells; whole scenarios drawn before any policy acts; the hourly engine (expiry, receipts,
  cut-off decisions, FIFO sales, trapezoid holding), batched over replicates, with no generator;
  the sealed observation with no absolute time; J from integer totals. ADR-062.
- **S5-M-16 Its tests (measured).** 53 tests in `tests/kernel/release/`, all passing (with the
  kernel's other tests, 65). Threefry equals Random123's three published vectors and a pure-Python
  form on 2,000 random inputs; `exp_neg` stays within 1 ulp of libm on [0, 600]. Each acceptance
  test fails on its planted fault, run in scratch copies: LIFO issuing, demand moved by orders, an
  absolute clock in the observation, waste as a clock (`plant_faults.py` in the scratch folder).
  On a synthetic 300-item world: units conserved exactly in every run; waste rises with stock held
  (8,609, 44,035, 103,921 and 281,558 units at order-up-to factors 0.5, 1, 1.5 and 2.5; in the legacy
  twin, spoilage was the same whatever was held); about 55 ms to draw a scenario and 51 to 85 ms per
  replicate in batches of 32.

- **S5-M-18 The fit (measured; `python -m scripts.world.fit_release_world --data <folder>`; commit
  `e68e982`, PR #105).** The exposure-weighted profile estimator settles in 38 iterations (a first
  full run did not settle in 500: the usable series-days were re-decided each iteration and rows
  flipped in and out; fixing the set before iterating made it a contraction; on a 10% sample it had
  converged anyway). Store: 300 items, 3,823 units a day, 4.7 to 237 per item (median 8.7), the top
  fifth carrying 47% of units; fourteen 168-hour profiles (13 categories with at least 1,000 series,
  one pooled); recovery lifts the afternoon and evening (Monday 16:00: 9.6% of the day, raw 8.6%).
  Day-level variance 0.090 (store-day 0.010, item-day 0.079); the slope of CV^2 on 1/mean over
  44,100 series is 0.94, so no excess of two-unit purchases (pair share 0). Hold-out (the next 7
  days): profile L1 distance 0.065 per day; recovered demand 8% higher (median ratio), a seasonal
  drift the world does not model.
- **S5-M-19 The masking check failed its pre-declared bar (measured; the report's
  `masking_check`).** On held-out series' fully in-stock days, day-total bias (95% store-bootstrap
  interval): pre-declared MNAR masks +9.5% (8.7 to 10.3); evening tails -0.3% (-1.1 to +0.5); the
  named fallback +9.6% and -0.3%; uniform fill -1.4% and -17.2%; no recovery -32% and -46%. Post hoc,
  labelled as such: with stock fixed before the day (0.6 to 1.4 times the series' usual day) +5.3%
  (4.8 to 5.8). Diagnosis (inferred): the pre-declared mask set stock as a share of the day's own
  total, so stock-outs selected purely on within-day noise; and even a fixed stock leaves the
  hitting-time selection of a ratio estimator. **S5-D-03 (2026-11-20).** By the gate's rule the
  smaller-bias method is used: "smaller bias" read as the smaller worst case over BOTH pre-declared
  families (the gate asked for both), which keeps the named estimator (9.5%) over uniform fill
  (17.2%, which would flatten the evening that F-13a says decides cost); labelled failing; a test
  pins the verdict as it came out. The inverse-sampling correction is recorded as a candidate, not
  adopted: a method chosen after its check fails voids the check. Consequence: demand recovered on
  stocked-out days may be overstated by about 5 to 10%, most in the evening.
- **S5-M-20 Native speed on the release world (measured 2026-11-23, mains power, battery 65%,
  11-19% background CPU; `python -m scripts.kernel.bench`).** Drawing a scenario: 75 ms. One 15-day
  replicate with the incumbent's rule: I1 33 ms alone, 36 ms each in a batch of 128; I2 44 ms alone,
  33 ms each in a batch of 32, 55 ms in a batch of 128. A simulated day of one replicate: 2.2 to
  2.9 ms. (The I1 batch of 32 read 86 ms each, an outlier left as measured.)
- **S5-M-21 Native and browser give the same bits (measured 2026-11-20; `parity.mjs` in the
  scratch folder, Pyodide 314.0.8 from npm, numpy 2.4.6 from its CDN, under Node 24).** The pinned
  golden cases of `tests/kernel/release/test_golden.py` (four scenarios' demand digests, an engine
  run's outcome digest, three costs as `float.hex`) are identical in WebAssembly (Python 3.14.2) and
  natively (Windows, Python 3.11.15, numpy 2.4.4). Pyodide loaded in 3.9 s; on the 12-item fixture
  a scenario took 25 ms and three replicates 0.13 s there.
- **S5-M-22 The headroom oracle, designed on the fixture world only (measured; no SYNAPSE
  component).** "The incumbent told the shock" first lost in the supply cells (S3 -3.0 to -5.0)
  because, with lost sales, extending the protection interval over a delay orders for demand that
  is lost before the stock lands, and the excess spoils; a bug of mine also applied the informed
  rule to every decision of the shocked supplier's items (fixed). Rewritten as a projected,
  lost-sales-aware cover from the order's actual arrival to the next order's, capped by shelf life
  (which also pre-stocks before an outage): it cuts lost sales sharply but over-stocks (S3: lost
  2,284 to 1,268 units, wasted 248 to 1,603). Hence one response factor per item, tuned by the
  sealed coordinate search on the shock cell's tuning seeds (alone, and with the guard in the
  loop). On the fixture: surge +1.03 tuned (+0.75 guarded), outage +0.42 (+0.35), delay -0.05,
  against margins of about 0.35 to 0.39. Lesson for session 6: naive use of supply-shock
  information hurts a perishable, lost-sales store; the D-4(b) guard turns most of that loss back
  into a small gain.

### E. The debts (branch `chore/pre-commit-hooks`, commit `258fc71`, off `main` at `ea205a4`)

- **S5-M-23 F-34 confirmed with pre-commit itself (measured 2026-11-23; pre-commit 4.7.0, MIT,
  from PyPI into a scratch environment, O2).** `pre-commit validate-config` on `main`'s
  `.pre-commit-config.yaml`: "while scanning a simple key, line 43 ... could not find expected
  ':', line 44", exit 1. The file holds **14 hooks, not the 15** the gate counted: ruff, ruff-format
  and mypy from two remote repositories, and 11 local.
- **S5-M-24 Each hook's own check over `main`'s tree (measured; each inline body run as written,
  `scratchpad/run_hooks.py`).** Pass: schema-validate, spec-validate, reward-isolation,
  spec-coverage (at its default threshold of 50, where CI runs 99). Fail: no-paid-apis (it scans
  the tests CI leaves out, and the parity test holds the pattern strings); jitter-enforcement (8
  files: any `time.sleep` in a file lacking the string `retry_with_jitter`, so periodic loops, a
  clock's pace, polls, and the jittered retry in `synapse_common/features.py`); contract-validate (17
  of 23 files: package inits, `tests/contracts`, and contracts whose Pydantic type is imported, not
  defined); kv-cache-check (any f-string in its three files, exception text included: 36 in
  `orchestrator/consensus/protocol.py`); no-raw-hex (20 lines: a Python linter that disagrees with
  CI's `lint-hex.mjs`, which accepts `rgb(var(--syn-*))`); color-spec-validate (F-38).
- **F-38 PR #77 broke the colour spec's structure and nothing noticed (measured).** On 2026-07-09
  it replaced the `preconditions:` header of `design-system/color/color-system.spec.yml` with seven
  new invariants (INV-CLR-019 to 025), which left PRE-CLR-001 and PRE-CLR-002 inside the
  `invariants` list: 8 schema errors. The colour job's spec coverage reads ids by regular
  expression, so it passed; the hook that validates the spec against its schema never ran (F-34).
  The header is restored; the spec validates.
- **S5-D-04 (2026-11-23). Each hook, by the gate's rule (section 7).** Nine duplicate a CI step and
  now run that step's own `run:` text, read from the workflow when the hook runs
  (`scripts/hooks/run_ci_step.py`), so each has one definition: ruff, ruff format, the two blocking
  mypy steps (the agents step is informational in CI, so the hook does not block on it), schema
  validation, spec validation, I-1, I-2, spec coverage at 99, and INV-CLR-009 (the stale Python
  linter is removed). Four that no job ran are kept, repaired where their rule could not pass on
  correct code, and run over the tree by a new job, `hooks.yml`: jitter-enforcement (a fixed sleep
  says `# not-a-retry: <reason>`; a jittered delay passes directly or through a name assigned from
  a jitter call; 10 sleeps marked), contract-validate (consumer contract modules only, imports
  followed to a Pydantic class), kv-cache-check (the system prompt is literal text, which is what
  I-13 says), color-spec-validate. None is retired: none meets D-5's grounds. **gitleaks is neither
  wired nor retired**: it reads the staged index, which CI does not have, so a CI job running it
  could never fail (wiring it would be theatre); and on a machine with gitleaks installed it can
  fail, so D-5 does not retire it. It stays local-only, says so in the config, and CI's secret scan
  stays `security.yml`'s advisory gitleaks step with its recorded pending condition. Left to the
  operator as an open question for session 6's prompt.
- **S5-M-25 Each hook fails on a planted violation and passes on the tree, through pre-commit
  (measured; `scratchpad/plant_hooks.sh`, a throwaway clone, one plant at a time).** 13 of 14:
  clean tree exit 0; planted exit 1. Plants: an unused import (ruff), an unformatted line (ruff
  format), an untyped function in `synapse_common` (mypy), a schema with type `not-a-type`, a spec
  without `state_machine`, a cross-agent import in a `rewards.py`, `import openai` in `scripts/`,
  `agents/demand_prophet/tests/test_spec.py` deleted (coverage under 99), `"#ff0000"` in
  `frontend/src/main.tsx`, an unmarked `time.sleep(3)`, a contract with no Pydantic type,
  `SYSTEM_PROMPT` rebound to an f-string, the colour spec's header removed again. gitleaks exits 0
  with a fake key staged, because gitleaks is not installed here: it cannot be shown failing on
  this machine.
- **S5-M-26 Gates (measured).** 15 hook tests pass in an environment of pytest, PyYAML and
  jsonschema only; `verify_claims` 57 PASS, 0 FAIL, 11 SKIP; C23, which passed on the string
  "raw-hex" in a file that did not parse, now resolves the CI step the hook runs; gate surface
  regenerated (744 rows); workflow shape and doc truth pass. `CLAUDE.md` (the INV-CLR-009 line and
  E-TP-08), the engineer skill and `CURRENT.md` now cite each hook through the job that runs it.
- **F-39 Seen in passing, not repaired (measured).** `orchestrator/contracts/twin_simulation_contract.py`
  is collected by no job (pytest's default `test_*.py` pattern does not match its name, and no
  workflow names it), and types its expectation with a dataclass from the sealed twin.
  `docs/state/MODULE_INVENTORY.md` is ungated and stale (an older format, 186 lines against 683
  regenerated today) and still lists the removed linter. The commit message first said eleven
  sleeps were marked; it was ten, corrected before the push by amending the unpushed commit.
