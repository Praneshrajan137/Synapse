# ADR-055: The simulated world must reward intelligence - five structures, one scalar regret objective, and a claim that can fail

## Status

Accepted - **declaration only. No structure is implemented by this ADR.** This is the
Decision_Relevance_Record required by `decision-quality-proof` R5.5, R5.6, R5.7, R5.33 and
R5.34, and it is committed **before any change to `digital_twin/simulation/engine.py` made
under R5** (R5.7). Task 8.1 landed this ADR. Tasks 9.x land E2a's instrumentation, task 10
measures `(s, S)` regret against the objective declared here, and tasks 12-13 land the five
structures.

Supersedes nothing. Amends no ADR. Constrains the twin described by
[ADR-036](ADR-036-single-vm-not-gke.md) only in what it simulates, never in where it runs -
every measurement named here is a CI workload under **I-0**.

**Amendment log.** Task 8.1 landed sections D1-D4 and D6. **D2.5 (the materiality margin's
derivation rule) was added later**, in the session-1r protocol revision, and **before checkpoint A
— the first run any margin is judged against.** That ordering is the point: R5.2 defers the
margin's *magnitude* until it has been measured, and D2.5 exists so the *criterion* is not
deferred with it. Recorded here because "task 8.1 landed this ADR" would otherwise read as
covering the whole document, and a decision record that changes without saying so is exactly the
drift this project gates against. Any future amendment appends a line here and lands **before**
the run judged against the amended text.

**This ADR is written to be falsifiable, and task 10 is the attempt.** Its central premise -
that a base-stock `(s, S)` policy is near-optimal on today's twin, so intelligence cannot pay
- is *analytical, not measured*. R5.1-R5.4 are the criteria that falsify it. If task 10
measures material `(s, S)` regret on the unmodified twin, this ADR's premise is **wrong**,
R5's scope shrinks substantially, and this record is amended rather than executed. That
outcome is a success of the method, not a failure of the plan.

## Context

### The finding this ADR exists to answer

SYNAPSE claims that multi-agent consensus makes better supply-chain decisions than a simpler
system. `uplift/` exists to measure that. But a measurement of decision quality is only
meaningful in a world where decisions *have* consequences, and reading
`digital_twin/simulation/engine.py` as an operations researcher gives five reasons to doubt
that today's world is one:

1. **Demand is stationary Poisson.** `_order_arrival` draws
   `self._rng.exponential(1.0 / (order_arrival_rate * demand_mult))` - a homogeneous process
   with no hour-of-day, day-of-week or promotional structure.
2. **The ten SKUs are identical and independent.** `{f"sku_{i}": 100.0 for i in range(10)}`,
   with no cross-SKU substitution and no per-SKU demand rate.
3. **Lead times are i.i.d. and uncorrelated with demand.** `_restock` draws
   `self._rng.uniform(30.0, 120.0) * lead_time_mult`.
4. **There is no capacity anywhere.** A repository-wide search for `simpy.Resource`,
   `simpy.Container`, `simpy.Store` and `PriorityResource` returns **no match**. Delivery
   wait is an independent `self._rng.uniform(10.0, 45.0)` draw, unrelated to load.
5. **Spoilage is decoupled from order quantity.** `_spoilage` applies
   `decay_rate = 0.01 * spoilage_rate_multiplier` against a fixed `0.3` threshold, reading
   neither inventory level nor order size.

### Why those five, together, are a theorem and not a list

Classical inventory theory is unambiguous here. Under stationary demand, independent and
identical items, i.i.d. lead times uncorrelated with demand, and no capacity coupling, the
optimal replenishment policy for a per-period cost that is linear in holding and in shortage
**is a base-stock `(s, S)` policy**. That is the standard result, and its conditions are
exactly items 1-5 above.

`Par_Level_Reorder` **is** that policy. So on today's twin, the transparent baseline is not
merely a reasonable comparator - it is provably near-optimal, and the theoretical headroom
above it is close to zero. A forecast cannot pay when demand is stationary. A dispatch policy
cannot pay when capacity is infinite. A dynamic safety stock cannot pay when lead-time
variance carries no signal. Cross-SKU pricing cannot pay when SKUs do not interact.

**Therefore measuring "uplift" on this twin would measure the harness, not the intelligence**,
and a null result would be uninterpretable: indistinguishable from a world in which nothing
could have won.

### The instrumentation problem that comes first, and why it is separate

There is a second defect, and it is prior to the first. **All six `KpiVector` fields are blind
to stock availability.** `_delivery` increments `orders_delivered` and
`total_delivery_time_min` *unconditionally*, before depleting stock:

```python
self._inventory[sku] = max(0.0, self._inventory[sku] - 1.0)
```

A stockout costs nothing measurable. `fill_rate` cannot fall. This contradicts
`uplift/kpi.py`'s own docstring and contradicts `digital_twin/world/runtime.py:18-21`, which
claims that with auto-restock disabled "stock genuinely runs out and `fill_rate` falls" -
false today.

That matters for sequencing, and the order is load-bearing (R5.35): **the twin must be
instrumented before the regret measurement, or a regret of zero is an instrumentation
artefact rather than a fact about the world.** E2a (task 9) is instrumentation; E2b (task 10)
is measurement; E2c (tasks 12-13) is physics. "The unmodified twin" in R5.1 therefore means
*the twin with E2a's instrumentation and none of E2c's structures*, and Property 49's second
clause makes that claim mechanically checkable rather than asserted.

## Decision

### D1 - Five structures, each justified by the agent decision it unlocks

**Nothing is added for realism's sake.** Every structure below names the decision it makes
non-trivial, and a structure that unlocks no decision does not belong in this list.

| # | Structure | Criteria | Agent decision unlocked | Why it is a no-op today |
|---|---|---|---|---|
| 1 | Non-stationary demand: intra-day and day-of-week intensity, plus promotion windows | R5.8-R5.14 | `demand_prophet` | Forecasting has **zero** value under stationary Poisson demand - the optimal forecast is the constant rate |
| 2 | Finite rider pool and finite pick stations, as contended resources whose queue state drives delivery wait | R5.15-R5.20 | `routing_navigator`, dispatch prioritisation | With infinite capacity, dispatch **policy is a no-op**: nothing waits, so ordering nothing matters |
| 3 | Lead times correlated with concurrent demand and autocorrelated across days, attributed to named suppliers whose realised history enters the `Observation` | R5.21-R5.24 | `supplier_trust`, `inventory_sentinel` safety stock | Under i.i.d. lead times a **static** safety stock is optimal; there is no signal to condition on |
| 4 | Spoilage as a function of age-at-arrival and of order size | R5.25, R5.26 | `freshness_guardian` | Spoilage reads neither inventory nor order quantity, so bulk ordering is free |
| 5 | Substitution: a zero-stock demand event diverts a committed fraction to declared substitutes | R5.27 | `pricing_oracle` cross-SKU pricing, `freshness_guardian` markdown | Ten identical independent SKUs never interact |

Structures 4 and 5 together create the multi-objective tension R5.28 tests: order small and
spoil less but stock out more; order large and fill more but waste more.

### D2 - The scalar regret objective (R5.33)

**Why this is declared here rather than derived in code.** `uplift/metric_contract.yaml`
declares per-KPI hypothesis tests, and `MetricContract.classify` returns a three-valued
`Outcome` - **not a cost**. There is no scalar objective anywhere in the tree, so regret has
no units, no sign convention and no aggregation rule until this section exists. Declaring it
after the run that it judges would be metric-shopping.

#### D2.1 Terms and signs

Five terms, drawn from `KpiVector` plus the R5.40 on-hand measure that task 9.3 adds. Each is
stated as a **cost** - lower is better - so the objective is a cost to be minimised and regret
is non-negative by construction:

| Term | Source | Sign transform | Cost interpretation |
|---|---|---|---|
| `stockout_rate` | `KpiVector` | identity | shortage cost |
| `spoilage_rate` | `KpiVector` | identity | waste cost |
| `avg_on_hand_units` | R5.40, task 9.3 | identity, normalised | holding cost |
| `avg_delivery_time_min` | `KpiVector` | identity, normalised | service-latency cost |
| `fill_rate` | `KpiVector` | `1 - fill_rate` | unmet-service cost |

**`margin` and `co2_estimate` are deliberately excluded, and the exclusion is recorded rather
than silent.** Both are `KpiVector` fields, so excluding them is a choice. Two reasons: they
are not terms of the classical `(s, S)` cost objective whose near-optimality this ADR's premise
rests on, so including them would mean the regret measured is not the regret the theorem is
about; and their derivations were not verified while authoring this record, so admitting them
would put unaudited quantities into the objective that decides the whole phase. Either may be
added by amendment **before** a run judged against the amended objective.

`fill_rate` and `stockout_rate` are related but not redundant after E2a: `fill_rate` is
delivered over created, `stockout_rate` is unmet-demand events over demand events. They
diverge whenever an order is created and never delivered for a reason other than stock.

#### D2.2 Normalisation

Three terms are already dimensionless fractions in `[0, 1]`. Two are not, and are divided by
**committed reference scales**, never by a measured quantity of the run being judged - a
normaliser derived from the run it normalises makes the objective self-referential:

- `avg_on_hand_units` is divided by the committed initial stock per SKU times the SKU count
  (today `100.0 * 10`), read from the policy file.
- `avg_delivery_time_min` is divided by a committed reference delivery time, read from the
  policy file.

Both normalisers are values this project already commits or will commit in
`digital_twin/simulation/policy.yaml`, so no term requires a measurement to be computable.
That is deliberate: an objective that cannot be evaluated until something is measured cannot
be used to decide whether to measure.

#### D2.3 Weights, and where they come from

**The two load-bearing weights are read from a source this repository already commits, not
invented here.** `agents/inventory_sentinel/models/newsvendor.py` declares
`cost_under: float = 8.0` and `cost_over: float = 1.0` - an **8:1 shortage-to-holding ratio**
that is already this project's committed opinion about the newsvendor critical ratio. Using it
means the regret objective and the inventory agent's own reward are consistent about what
matters, which is the AD-13 move: read the number, do not restate it.

| Term | Weight | Provenance |
|---|---|---|
| `stockout_rate` | 8.0 | `newsvendor.py::cost_under` - **read, not chosen** |
| `avg_on_hand_units` (normalised) | 1.0 | `newsvendor.py::cost_over` - **read, not chosen** |
| `1 - fill_rate` | 8.0 | same shortage class as `stockout_rate` |
| `spoilage_rate` | 1.0 | same over-stocking class as holding; waste is the realised form of over-ordering |
| `avg_delivery_time_min` (normalised) | 1.0 | **declaration-time choice, flagged as such** |

The delivery-latency weight is the one number here with no committed antecedent. It is
declared at `1.0` and **recorded as a choice rather than a derivation**, pinned like the
others, and open to amendment before any run judged against it. Stating which weights are read
and which are chosen is the difference between a committed objective and a plausible one.

Every weight and both normalisers are committed to
`digital_twin/simulation/policy.yaml`, pinned in `doc-number-pins.yaml`, and carry a
`ratchets.json` entry whose extractor is verified **by running it** (task 8.3).

#### D2.4 Aggregation over replicates

The per-replicate objective is aggregated by the **arithmetic mean**, and regret is the
difference of means between the policy under test and the reference policy on **the same
replicate seeds**.

Mean, not median, and the reason is decision-theoretic rather than statistical taste: this is a
cost, expected cost is the quantity an inventory decision is made against, and a median would
discard exactly the tail where policy differences live - a policy that stocks out badly once in
twenty replicates is meaningfully worse than one that never does, and the median cannot see it.

Paired on seeds, because `Scenario` guarantees that an identical `seed` yields an identical
demand realisation across arms (R2.1/R2.5), and pairing removes demand variance from the
contrast. The interval comes from task 15.2's estimator at `1 - alpha`, with `alpha` **read**
from `uplift/metric_contract.yaml` (a committed `0.05`) - never inlined.

#### D2.5 The materiality margin - the rule is declared here, the value is measured later

R5.2 forbids pinning the `(s, S)` materiality margin before it has been measured, because no
such measurement exists in this tree. Every other threshold in this phase is pinned **before**
the run judged against it. Combined naively, those two rules license choosing the margin with
the number already in hand - which would decide the task 11 verdict by the choice of margin,
and that is metric-shopping wearing a different hat.

**So the two halves are separated. The derivation rule is committed here, before any run. Only
the magnitude is instantiated after the first measuring run.** This is the shape of a minimum
detectable effect: the rule is pre-registered, the value is measured.

**The rule.** The margin is expressed in **service-point equivalents** - the objective cost of
one percentage point of fill rate:

```
materiality_margin = service_points * 0.01 * weight(1 - fill_rate)
```

At the D2.3 weight of `8.0`, one service point costs `0.08` objective units, so the margin is
`service_points * 0.08`. Stating it this way is the point: the single decision-relevance choice
lands in units a supply-chain reader can evaluate ("a better policy would have to recover at
least this many points of fill rate, or its cost-equivalent in any mix of the five terms")
rather than in abstract objective units nobody has intuition for.

**`service_points = 5.0`, and it is a choice, not a derivation.** Flagged exactly as the
delivery-latency weight is flagged in D2.3, because a materiality margin contains exactly one
irreducible decision-relevance judgement and pretending otherwise would be false precision.
What makes `5.0` defensible rather than arbitrary is that it is bracketed on both sides by
committed or measured quantities:

- **Not trivially small.** The twin's own endogenous `(s, S)` restock measures
  `fill_rate = 0.8556`, while the newsvendor critical ratio this repository commits
  (`cost_under / (cost_under + cost_over) = 8/9`) targets `0.8889`. The incumbent policy's
  shortfall against its *own* theoretical target is therefore about **3.3 service points**. A
  margin below that would call the incumbent's known, accepted shortfall "material".
- **Not unreachably large.** The measured comparator headroom is `11.79 - 2.93 = 8.86`
  objective units, and the fill-rate gap across the same pair is `0.9149 - 0.3592 = 55.6`
  service points. A `5.0`-point margin is roughly 4.5% of the cost headroom perfect foresight
  buys, so the criterion can fire.

**A derivable guard, enforced by the reader.** The committed margin must be **strictly less
than the measured comparator headroom**. A margin at or above the total headroom is
unfalsifiable by construction: no policy could exceed it, so `material` would be unreachable
and task 11 could only ever proceed. `digital_twin/simulation/policy.py` refuses such a value
rather than recording it.

**The ratchet direction is `down`, and unlike the weights this number has one.** D2.3 records
that an objective weight has no better-direction, so the weights are pinned without a ratchet.
The materiality margin is different: **raising it is the self-serving move.** A larger margin
makes `material` harder to reach, which makes Finding 4 harder to falsify, which lets the spec
proceed. So the margin may only ever be *tightened*, and
`infrastructure/quality/ratchets.json` records `direction: down` for exactly that reason. This
is the one threshold in the phase where the motivated error has an obvious sign.

### D3 - Per-KPI observable sensitivity (R5.34)

R5.34 requires this record to state, **per KPI named in the objective**, whether that KPI is
observably sensitive to the inventory policy on the unmodified twin. Recording it is what makes
R5.35 enforceable, and the honest answer today is **no for all of them**:

| Objective KPI | Observably sensitive to inventory policy on the unmodified twin? | Evidence |
|---|---|---|
| `fill_rate` | **No** | `_delivery` increments `orders_delivered` unconditionally; the ratio cannot fall on a stockout |
| `stockout_rate` | **No** | numerator is `uplift/harness.py`'s per-step count of SKUs at zero, which scales with `n_steps * |SKU|` and saturates in `_clamp_fraction`; it does not count unmet demand |
| `spoilage_rate` | **No** | `_spoilage` reads neither inventory level nor order size |
| `avg_delivery_time_min` | **No** | an independent `uniform(10.0, 45.0)` draw, unrelated to stock or load |
| `avg_on_hand_units` | **Does not exist yet** | `SimulationMetrics` carries no inventory-time term; task 9.3 adds it |

**This table is the reason E2a precedes E2b, and it has a hard consequence (R5.35, task 10.5):
a regret below the materiality margin measured while any objective KPI is recorded here as not
observably sensitive is reported `inconclusive`, and must NOT be reported as confirming the
premise.** A null produced by an insensitive instrument is not evidence of absence. This table
is expected to be amended to "yes" by task 9's property tests, and each flip must be backed by
the property that demonstrates it - not by assertion.

### D4 - `spoilage_rate` changes meaning, and the change is recorded not absorbed

`SimulationMetrics.orders_spoiled` increments **per SKU per tick**, not per spoiled unit. So
`spoilage_rate` as derived today is **a tick count, not a spoiled-units fraction**, and the two
are not proportional: the tick count depends on the simulation step size, and the units
fraction does not.

Structure 4 makes spoilage a function of age-at-arrival and order size, which changes what the
numerator counts. **That change is disclosed here rather than absorbed silently**, because a KPI
whose meaning moves without a record makes every historical value quoting it incomparable. Any
document comparing a pre-E2c `spoilage_rate` with a post-E2c one must state that they measure
different quantities.

### D5 - The reference policy set for R5.28's Pareto comparison

R5.28 asks whether any single-objective policy is Pareto-optimal. **Without a declared
reference set the criterion is unsatisfiable by construction**, because the Pareto frontier of a
finite non-empty set is non-empty - evaluate only the four single-objective policies and one of
them is trivially on the frontier, proving nothing.

The reference set the four are evaluated **together with** is the committed Baseline_Policy
suite plus the consensus arm:

- `Par_Level_Reorder`
- `Static_Pricing`
- `Greedy_Routing`
- `No_Op_Disruption`
- the consensus arm under test

That suite is owned by `.kiro/specs/decision-integrity-uplift-proof/` and is a **precondition
of R5.28, not a deliverable of R5.** Dominance is interval-aware (R5.29): one policy dominates
another only if it is no worse on every objective KPI and strictly better on at least one
**with their reported intervals disjoint**.

### D6 - The negative-control repetition count and rate tolerance (R6.15)

Declared here rather than left to an amendment, because R6.15 reads both numbers from *this*
record and would otherwise be unsatisfiable until task 16.3 patched it.

**Why a repetition is needed at all:** a single negative-control run classifies only four pairs
(`primary_kpis: fill_rate` across four scenarios), and **four pairs cannot estimate a rate**.

- **Independent seed sets: 20.** Chosen so the expected number of false positives at
  `alpha = 0.05` is exactly 1, which is the smallest count at which a false-positive rate is
  estimable at all rather than merely bounded.
- **Rate tolerance: the observed proportion of repetitions reporting a proven gain must not
  exceed `0.20`.** This is a **pre-registered target, not a measurement**, and it is
  deliberately loose against the nominal `alpha = 0.05`: at 20 repetitions the exact binomial
  upper bound on an `alpha = 0.05` process is 4/20 = 0.20 at roughly the 98th percentile, so a
  correctly-calibrated instrument passes this bound almost always while an instrument reporting
  gains on a third of its null repetitions fails it. Tightening the bound to `0.05` itself would
  fail a correct instrument roughly a quarter of the time, which is a gate that punishes the
  truth.

Both numbers are committed to `digital_twin/simulation/policy.yaml` and pinned. **A tolerance
committed here is judged against runs that come after it, never against a run already
performed.**

## The falsifiable claim (R5.6)

Stated so that it can be shown false, and measured by task 13.7:

> **After E2c, a base-stock `(s, S)` policy - `Par_Level_Reorder` - is measurably sub-optimal on
> this twin.** Specifically: the scalar regret of `Par_Level_Reorder` against the perfect-foresight
> comparator, computed under D2 over paired replicate seeds, is **strictly positive and at or
> above the materiality margin committed in `digital_twin/simulation/policy.yaml`, with its
> `1 - alpha` interval excluding that margin.**

Three ways this claim can fail, each of which must be reported rather than reframed:

1. **Regret is not strictly positive after E2c.** The structures did not make the world
   decision-relevant. R5.14's converse applies: report *non-stationarity too weak to make
   forecasting pay*, and do not proceed to measure consensus uplift on a world where nothing can
   win.
2. **Regret is material on the *unmodified* twin (task 10).** This ADR's premise is falsified.
   Amend this record, re-cut R5, and do not implement structures the evidence says are
   unnecessary.
3. **Any single-objective policy is Pareto-optimal after E2c (task 14).** Consensus is provably
   unnecessary; the experiment has no room to win and must not be run.

## Consequences

**What this buys.** A world in which the agents' decisions have consequences a KPI can see, so
that a measured uplift means something and a measured null also means something. Without it,
`uplift/`'s entire output is uninterpretable.

**What it costs, stated plainly.**

- **Named RNG substreams change every realised number on the seeded path** (task 9.4). This is
  the single largest expected-value churn in the design, and it is unavoidable: without
  substreams, adding a queue in structure 2 perturbs the demand stream, and every seeded
  expectation breaks for a reason unrelated to the structure being added.
- **The two-pass foresight comparator doubles the twin cost per replicate** (task 10.2), which
  is why the regret measurement gets its own `uplift.yml` job rather than sharing
  `uplift-proof`'s 350-minute budget.
- **Committed expectations move, and each must state its new value with a reason** (task 9.7,
  R5.31). Named casualties include
  `test_world_runtime.py::test_demand_depletes_inventory_and_auto_restock_is_disabled` (which
  this **repairs**), `test_env_response.py::test_good_action_beats_bad_over_seeds`, and
  `test_simulation.py::TestSimPyEngine::test_run_produces_valid_metrics`. **No assertion may be
  weakened to absorb a change.**
- Every twin measurement named here is a category-3/4 workload under **I-0** and runs in
  `uplift.yml` or `ci.yml`, never on a development machine.

**What is deliberately not done.** The twin is **not** bound to the repository's OSRM container
(`docker/docker-compose.mumbai.yml::osrm-mumbai`) for structure 2's travel times: that would
make every twin run a category-1 workload under I-0. The OSRM claim is instead **removed** from
both the `SupplyChainSimulation` and `_delivery` docstrings and replaced with a description of
the travel time the code actually produces (R5.20).

## Ratchet / deferred

- **The `(s, S)` materiality margin is NOT committed by this ADR.** R5.2 forbids pinning it
  before measurement, because no such measurement exists. Sequence: task 10.3 runs, task 10.4
  reads the reported regret and its interval and commits the margin, and only *subsequent* runs
  are judged against it. Committed-after-measurement is not committed-late; what is forbidden is
  judging a run against a threshold committed after that run.
- **The utilisation ladder and near-saturation band (R5.18, R5.19) inherit the same pattern** and
  are committed after structure 2's first measuring run.
- **The D3 sensitivity table is expected to be amended to "yes"**, and each flip must cite the
  property test that demonstrates it.
- **The delivery-latency weight (D2.3) has no committed antecedent** and is the first candidate
  for ratification against evidence.
- Every threshold this phase commits gets a `ratchets.json` entry whose extractor is verified by
  **running it** (task 8.3). A pin whose extractor resolves to nothing compares `None` to `None`
  and reports green having compared nothing.
