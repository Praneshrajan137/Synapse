# PREREG-1 - the release's scientific choices, sealed before any result exists

**Sealed 2026-11-19, truth program session 3**, before the release's world exists (session 5 builds
it) and so before any result on it. Its machine-readable twin is [`prereg-1.json`](prereg-1.json);
**where the two differ, this file governs.** Both are hashed in [`SHA256SUMS`](SHA256SUMS);
`check_prereg.py` checks the seal against itself. The time of sealing is proved by the server-side
merge time of the pull request that adds these files to `main` (GitHub records it; the author
cannot set it); an OpenTimestamps proof of `SHA256SUMS` will be added beside it if the operator
approves that outside action (it adds a proof; it changes no sealed file). This file answers
`docs/truth/PLAN.md` section 5.2 and states the claims of section 5.6 as tests.

**The rule this file enforces.** Nothing below is chosen, or changed, after looking at a result it
governs. No arm was priced under any of these weights before this file was written (session 3,
decision S3-D-03). A change after sealing is a **deviation**: recorded in `DEVIATIONS.md` in this
folder, dated and reasoned, and where it could change a conclusion the analysis is reported both
ways. Before sealing, this file was attacked by a reviewer with fresh context; every finding and its
disposition is in section 12.

Labels on sources: **checked** (read at the source on the date given), **snippet** (seen only in
search results), **recalled** (from standard references; not re-read this session).

## 1. What is compared, and on what terms

- **SYNAPSE** is the governed composition built in session 6 and fixed by freeze C (section 5): the
  incumbent decides unless a challenger is trusted for the regime the store is detected to be in, and
  a deterministic guard passes the quantity (decisions D-2, D-4; the guard in section 3).
- **The incumbent** is the best of two classical rules, tuned as a good planner would (section 3).
- **Parity.** In every cell both arms are built from the same inputs: the world's declared
  parameters for cell N, and the records of the exploratory seeds (section 5) of any cell. No policy
  receives the cell's identity or parameters, calls the world's simulator, generator or random
  streams, or uses any model of the world except one fitted to its own observation history and those
  inputs. A test asserts that each policy's construction inputs are byte-identical across the five
  cells. Both arms act at the same decision points through one action: an order quantity per item,
  in whole units, on the next scheduled delivery. The observation is identical for both arms: sales
  (censored by stock), on-hand stock by batch with each batch's expiry, open orders with their
  placement times, receipts, realised lead times, the time of day and the day of the week. It never
  includes the replicate's day index, its horizon, or any cell or shock parameter.
- **Common random numbers.** Every random draw is keyed by seed, purpose, item or supplier, and time
  slot, never by a policy's actions, so at one seed both arms face identical demand and supply paths.
  Replicate `r` of every cell uses the same seed `seed_r`, so cells can be compared seed by seed.
- **The unit of analysis is one replicate**: one store, a warm-up, then 7 measured days, at one
  seed. Both arms start from the same policy-independent state: per item, on hand at age zero the
  ceiling of the mean demand over the nominal protection interval (lead time plus the time to the
  next delivery), nothing on order. The warm-up lasts the largest nominal shelf life plus the largest
  nominal lead time, rounded up to whole days, and is never priced. Stock left at the end is reported
  per arm. Replicates are independent; days within one are not, and are never used as units.

## 2. The objective, in money

`J_k`, the cost of replicate `k`, is its total over the 7 measured days divided by 7: money per
store-day, in units of each item's price `p_i`:

`J = sum_i p_i * [ (m + g) * L_i + (1 - m) * W_i + r * (1 - m) / 365 * H_i ]` per store-day

| Symbol | Meaning |
|---|---|
| `L_i` | units of demand for `i` not filled (lost sales) |
| `W_i` | units of `i` discarded at the end of their shelf life |
| `H_i` | unit-days of `i` held on hand (the integral of on-hand units over time) |
| `m` | gross margin, as a share of price: a lost sale loses it |
| `g` | loss beyond the item's margin when a sale is lost (order abandoned, customer lost) |
| `1 - m` | unit cost: a discarded unit loses what it cost (no salvage, no disposal cost) |
| `r` | annual inventory carrying rate on unit cost |

**Primary values: `m = 0.38`, `g = 0`, `r = 0.25`.** Order cost is **0**: orders ride the store's
scheduled deliveries, whose cost does not depend on the order. The world has **no pack sizes and no
minimum order quantities**. Customer delivery time is not part of `J`: it is not an outcome of a
replenishment decision.

| Value | Source |
|---|---|
| `m = 0.38` | IFPA, *Produce Department Benchmarks*, August 2023: produce gross margin 38% in 2023 and 2022 (15 supermarket chains, over 1,000 US stores). **Checked** 2026-11-18. The 2025 edition is reported at 39% (**snippet**, not used) |
| `g = 0` | The conservative reading: a lost sale costs its margin. Shoppers facing a stock-out buy elsewhere, substitute, delay or do not buy (Corsten and Gruen, *IJRDM* 31(12), 2003; figures **snippet**); in quick commerce a missing item can lose the basket. Carried in the band |
| `r = 0.25` | Practice range of 20% to 30% of inventory value a year (**snippet**, several practitioner sources); one reports a realised benchmark median near 10% (**snippet**) |
| Waste at unit cost | The newsvendor's overage cost at expiry with zero salvage (**recalled**) |
| Calibration target, not a weight | IFPA 2023: produce shrink 5.46% of sales (**checked**). Freeze W reports the incumbent's waste as a share of sales in cell N. Any recalibration of the world happens before freeze W, never after |

**Sensitivity band**, reported for every cell and never used to judge a claim: `m` in
{0.25, 0.38, 0.50}, `g` in {0, 0.5, 1.0}, `r` in {0.10, 0.25, 0.40}, all 27 combinations, re-pricing
the recorded `L`, `W`, `H` of the same runs (decisions stay those tuned at the primary values). The
lower margin reflects Indian quick commerce, whose operators report contribution margins near
break-even (**snippet**, 2026); the higher, high-margin fresh lines.

## 3. The incumbent and the guard

**Two candidates.** Each orders up to `S_{i,t} = ceil(k_{i,d} * mu_i(t))`, where `mu_i(t)` is the
mean demand of item `i` over the protection interval starting at decision time `t` (lead time plus
the time to the next delivery), as the tuning seeds show it per item, day of week and hour, and
`k_{i,d}` is a factor tuned per item and part of the day `d` (six four-hour parts: 00-04, 04-08,
08-12, 12-16, 16-20, 20-24, store time).

- **I1, profile base stock.** Order `max(0, S_{i,t} - IP_i)`, with `IP_i` the units on hand plus on
  order.
- **I2, waste-aware profile base stock.** As I1, with `IP_i` reduced by the units expected to
  outdate: deplete the on-hand batches oldest first by the mean demand up to each batch's expiry; the
  units left in a batch at its expiry are its expected outdating; subtract their sum. This is the
  approach of Broekmeulen and van Donselaar, *Computers & Operations Research* 36(11):3013-3018,
  2009 (existence and venue **checked**; this paragraph is the sealed statement of the method).

With no order cost, no pack sizes and no minimum order, a reorder point below `S - 1` only delays
orders, so base stock is the `(s, S)` family's best member here (**recalled**, the zero-setup result).

**Tuning, identical for both candidates and for every tuned part of the composition.** One
replicate-evaluation is one simulated replicate at one seed. Items are tuned together: every item's
factor moves in the same replicates and each item's own cost `J_i` is read from them (jointly over
items if the world couples them). Cyclic coordinate search over the `k_{i,d}`, parts of the day in
clock order, from `k = 1`, with steps 0.5, 0.25, 0.125, 0.0625 and 0.03125; at each step, sweep
until a sweep changes nothing, then halve; stop after an unchanged sweep at the smallest step. No
cap short of convergence; evaluations used and per-item convergence are published with freeze W.

**Which tuning, in which cell.** In N, each candidate is tuned on N's 32 tuning seeds. In L, each is
tuned on L's tuning seeds (shelf life is a product attribute a planner knows). In S1, S2 and S3,
each candidate is tuned twice, on N's tuning seeds and on the pooled tuning seeds of N, S1, S2 and
S3. **In every cell the incumbent is the version with the lowest mean `J` on that cell's 32
validation seeds**; ties go to I1, the simpler.

**The guard (D-4(b)).** A challenger's quantity for an item at a decision outside `[0.5 q_I, 2 q_I]`,
with `q_I` the incumbent's quantity there, is clipped to the nearest end of that interval: in the
simulation no person is present to approve it. When `q_I = 0` the interval is `{0}`, so a challenger
cannot order where the incumbent orders nothing; this is the operator's decision D-4(b), and the share
of clipped challenger decisions is reported per cell.

## 4. Margins

Per cell `c`, in money per store-day, from the world's **declared** parameters (fixed at freeze W),
never from a result:

`M_c = 0.01 * D_c * (m + g) * p_c`

with `D_c` the expected units demanded per store-day in cell `c` and `p_c` the demand-weighted mean
price (shocks contribute their expected extra demand). Read: **one point of fill rate, at equal
waste and stock.** At the primary values a store expecting 2,000 units a day at unit prices has
`M = 7.6` price-units a day. Fill rate, everywhere in this file, is units filled over units demanded,
all items pooled, over the replicate's 7 measured days.

## 5. Freezes and seeds

- **Freeze W**, at the end of session 5 and before any challenger or composition runs on the new
  world, fixes and publishes: the kernel; the world (every declared parameter, the item set,
  suppliers and their items, lead times, the delivery schedule, shelf lives, prices, the initial
  state, and the method that recovers stock-out-hidden demand, with its masking check); the
  incumbent's tuned tables, evaluation counts and selection; `D_c`, `p_c` and `M_c` per cell; the
  shock headroom of section 6. Every world parameter not fitted to data carries a cited source or is
  marked "chosen" with its reason. A later change to any of these is a deviation, and the
  confirmatory run is then reported on both worlds, the frozen one primary.
- **Freeze C**, before the confirmatory round below, fixes and publishes: the composition, its named
  components and its trust map (fitted on exploratory seeds only, evaluation counts published); `s_c`
  and `n_c` (section 6) computed with the frozen arms; the analysis code; the numpy version.
- **Exploratory seeds** are public: `seed_k` is the first 8 bytes, big-endian, of
  `SHA-256("synapse/prereg-1/explore/" || k)`, shifted right by one bit, with `k` as 8 bytes
  big-endian. `k` in [0, 32) are the **tuning** seeds, [32, 64) the **validation** seeds, 64 and above
  **development**.
- **Confirmatory seeds come from a public randomness beacon round that does not exist when this file
  is sealed.** The beacon is drand `quicknet`: chain hash
  `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971`, public key
  `83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a`,
  genesis 1692803367, a round every 3 seconds, scheme `bls-unchained-g1-rfc9380` (chain information
  **checked** 2026-11-18). Round `r` is emitted at `genesis + (r - 1) * 3`; "the round at time `t`"
  means the first round emitted at or after `t`. The confirmatory round is **R_C = 34714612**,
  emitted at **2026-12-11T00:00:00Z**. With `sig` its 48-byte signature, verified against the public
  key, replicate `j` of every cell uses `seed_j`, the first 8 bytes, big-endian, of
  `SHA-256("synapse/prereg-1/confirm/" || sig || j)` shifted right by one bit, `j` as 8 bytes
  big-endian, `j = 0, 1, ...`.
- **Freeze C is pushed before 2026-12-11T00:00:00Z.** If it is not, the confirmatory time becomes 24
  hours after its push, R_C becomes the round at that time, and the change is a deviation.
- **R_C is fixed.** It is replaced only if no public drand relay serves it by 2026-12-12T00:00:00Z,
  and then by the first round served after service resumes. A failure to fetch or verify on our side
  never replaces it; verification by two implementations is reported, not a trigger.
- **One run, logged before it is opened.** An attempt is any execution that reads R_C's signature;
  each is logged publicly (a pushed commit) before its output is opened. The first complete run is
  **primary** and its verdicts stand. A run corrected for a defect uses the same seeds and is reported
  beside the primary as a deviation; a defect is a failure of a test committed before freeze C, or a
  crash. A claim is supported only if it passes in both.

## 6. The cells

Every cell is the world session 5 builds and freeze W fixes (many items with skewed demand, an
intraday and weekly shape fitted to FreshRetailNet-50K, stock held in batches discarded at their
modelled shelf life, first in, first out), plus:

| Cell | Definition |
|---|---|
| N | No shock |
| L | Every item's shelf life halved, rounded down to whole hours, at least 12 hours |
| S1 demand surge | Items drawn uniformly by count without replacement, 30% of them (rounded up), so mostly slow movers under skew; their demand multiplied by one `u ~ U(1.5, 3.0)` drawn once per shock, for `U(1, 3)` days |
| S2 supplier delay | One uniformly chosen supplier's lead times multiplied by `v ~ U(2, 4)`, for `U(2, 4)` days |
| S3 supply outage | One uniformly chosen supplier delivers nothing for `U(1, 3)` days; an order placed during the outage arrives at its end plus its lead time |

One shock per replicate in S1 to S3. Its onset is drawn uniformly between the start of measured day 1
and the end of measured day 7 less its duration, from a dedicated substream of the replicate's seed,
so both arms meet the same shock at the same instant. **No policy is told a shock exists** (section 1).

**Headroom, for description only.** Before freeze W, an oracle arm told each shock's items, onset,
size and duration runs on the validation seeds; its mean advantage over the incumbent in each shock
cell is published with freeze W. For every shock cell the per-replicate difference-in-differences
`delta_{S,k} - delta_{N,k}` (same seeds) is reported with its interval.

**Replicates per cell**: `n_c = min(2000, max(200, ceil((2 * 1.96 * s_c / M_c)^2)))`, with `s_c` the
standard deviation of the paired differences on the 32 validation seeds, fixed at freeze C.

## 7. The claims and their tests

For replicate `k` of cell `c`, `delta_k = J_SYNAPSE,k - J_incumbent,k` (section 2's per-store-day
cost). Intervals are BCa bootstrap intervals over replicates (Efron 1987, **recalled**), 10,000
resamples, with `z0` counting bootstrap values equal to the estimate as one half, and the interval
taken as that value when every `delta_k` is equal. The bootstrap's generator is numpy's
`Generator(PCG64(s))`, `s` the first 8 bytes, big-endian, of
`SHA-256("synapse/prereg-1/bootstrap/" || sig)` shifted right by one bit, drawing cells in the order
N, L, S1, S2, S3.

| Claim | Test | False if |
|---|---|---|
| **C1** SYNAPSE is never materially worse than the incumbent | In every cell: the upper end of the two-sided 95% interval of mean `delta` is below `M_c`, AND the lower end of the two-sided 95% interval of the mean fill-rate difference (SYNAPSE minus incumbent) is above -0.01. Every cell must pass (an intersection-union test, so no multiplicity adjustment; Berger 1982, **recalled**) | Any cell fails either part |
| **C2** SYNAPSE is materially better where shocks arrive unannounced | Per shock cell S1, S2, S3: the lower one-sided bound of mean `-delta` exceeds `M_c` | Stated per cell; no shock cell passes means C2 is false |
| **C3** SYNAPSE wastes less at equal fill where shelf lives are short | In L: the upper one-sided bound of the mean difference in waste at cost, `sum_i (1 - m) p_i W_i` per store-day, is below `-M_L`, AND the lower one-sided bound of the mean fill-rate difference is above -0.01 | Either part fails |

**The superiority family.** C2's three cells and C3 are one family of four hypotheses, tested by
Holm's procedure at familywise one-sided 0.025 (Holm 1979, **recalled**): with `h` hypotheses not yet
rejected, reject each whose one-sided BCa bound at level `1 - 0.025/h` clears its margin (for C3,
both parts); repeat until a step rejects none.

**The operator's autonomy mark, beside C1.** D-4(a) sets the pass mark for letting a challenger act
in a regime: its executed actions may not raise the objective above the incumbent's at the upper end
of a 95% interval (a zero margin), nor lower fill rate by more than one point. Its per-cell result is
reported beside C1; C1's margin `M_c` is `PLAN.md` 5.6's.

**Ablations (D-5).** For each component named at freeze C, SYNAPSE-without-it runs on the
confirmatory seeds. A component has no measured effect only if, in every cell, the two-sided 90% BCa
interval of mean `J_without - J_SYNAPSE` lies inside `(-M_c, M_c)`. Ablations never change C1 to C3.

Every cell is reported whatever its result, with per-item breakdowns, the clipped-decision share and
the 27-point band as description. **A negative result is published as prominently as a positive one.**

## 8. The public contest

The contest tests no claim; it shows that the comparison is reproducible by anyone. It runs the
freeze-C composition against the incumbent tuned on pooled shocks (of I1 and I2 so tuned, the one
with the lower mean `J` over the validation seeds of S1, S2 and S3 together), in cell N's world with
shocks arriving as a Poisson process of rate one per 14 simulated days for each of the three types
(parameters drawn as in S1 to S3), for 120 simulated days, on the seed `CONTEST-PROTOCOL.md` derives
from a beacon round announced at least 72 hours before launch. Its one statistic, computed once after
the last day: the mean daily paired cost difference with a 95% moving-block bootstrap interval, block
7 days, 10,000 resamples (Kunsch 1989, **recalled**), generator seeded as in section 7 from
`"synapse/prereg-1/contest-bootstrap/" || sig` with the launch round's signature. Interim figures are
labelled descriptive.

## 9. What is not sealed here

The implementation, which must follow the procedures above; the world's parameters and the
censoring method, which freeze W fixes before any challenger runs on the world; exploratory analyses,
always labelled as such.

## 10. Dates

| Event | Deadline |
|---|---|
| Freeze W | End of session 5, before session 6 runs any challenger on the world |
| Freeze C | Pushed before 2026-12-11T00:00:00Z |
| R_C emitted | 2026-12-11T00:00:00Z (round 34714612) |
| R_C replaced only if unserved | 2026-12-12T00:00:00Z |

## 11. Deviations

`DEVIATIONS.md` in this folder lists every departure, dated, with its reason and its effect. It
starts empty.

## 12. The attack before sealing (2026-11-18)

A reviewer with fresh context (one subagent, 8 tool calls) attacked the first draft; its findings were
checked against `DECISIONS.md` and the arithmetic before use. Adopted: parity of information and
action (blocker 1); an incumbent that follows the weekly shape, is re-tuned in L and tuned on pooled
shocks, selected per cell (2); tuning defined by evaluation unit and run to convergence, with I2's
outdating stated (3); two freezes, W before any challenger runs on the world (4); `J_k` as a
per-store-day mean (5); no redraw of R_C by our own failure, and a primary first run (6); D-4(a)'s fill
floor in C1 (7, checked against `DECISIONS.md` D-4); one Holm family for C2 and C3 at one-sided
0.025 (8); C3 with a material margin and defined measures (9); a common initial state, a longer
warm-up and no horizon in the observation (10); the contest's cell and arms sealed here (12); shocks
lengthened to days, with headroom and difference-in-differences reported (13); ablations pre-registered
(14); and minor findings 15 to 22. Adapted: an external timestamp (11) is the pull request's
server-side merge time now, with an OpenTimestamps proof pending the operator's approval of that
outside action. Not adopted: none. One factual claim did not hold: `CONTEST-PROTOCOL.md` exists, on
the beacon branch (pull request #98), where the reviewer did not look; its substance (the contest
sealed here) was adopted.
