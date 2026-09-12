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

**Amendment, session 5 (2026-09-09) — D2.5 gains the three-arm comparator, and
`bracketing.upper` is corrected to a measured value.** Conflict M established that the committed
two-pass comparator measured a **no-op** against perfect foresight while reporting the result as
the `(s, S)` regret R5.1 asks for, and that `regret` and `comparator_headroom` were the *same
subtraction* — so `must_be_below_measured_headroom` admitted exactly the margins below the regret
they would be judged against, and every margin inside this section's own bracket forced
`material` by construction. The comparator now runs three arms and the two quantities are
different expressions. **This amendment lands before the run judged against it**, per the rule in
the paragraph above; it changes no threshold, and in particular it does **not** instantiate
`regret_objective.materiality_margin.value`, which remains `null`.

**Amendment, session 7 (2026-09-11) — D2.5 states the derived literal and the value is
instantiated; D2.5.1 records that the oracle arm is NOT an upper bound on achievable
performance, which the three-arm repair did not address and could not have detected.** Run
`34570166681` (sha `e94a1ac`), the first measurement ever taken against the `(s, S)` reference
arm, reported `comparator_headroom = 8.937888952967558` — unchanged from run `34366766968` to
every digit, so `bracketing.upper` needs no correction and arm A's realisation is confirmed
unperturbed by the addition of arm B. It also reported **`regret = -0.8123524459522771`**, with
a 95% interval of `[-0.8273245113311902, -0.7977944274457321]` over 200 of 200 usable
replicates. A negative regret means the incumbent `(s, S)` policy **outperforms the
perfect-foresight arm it is measured against**, so that arm is not an oracle and the difference
is not a regret. This amendment states that measurement, records the excluded mechanisms and
the surviving hypothesis, and adds the non-negativity refusal that makes the defect loud. **It
lands before the run judged against the amended text**, per the rule two paragraphs above.

**Amendment, session 8 (2026-09-11) — D2.5.2's hypothesis is MEASURED. Its direction is
confirmed, its mechanism is corrected, and it turns out to be two independent defects rather
than one.** Run `34590696403` (sha `e02c1c2`) reports the per-term decomposition D2.5.2 named as
its own falsifier. `stockout_rate` dominates at **80.8%** of the regret, as hypothesised — but
the objective also **double-counts that same quantity**, and the arm labelled `perfect_foresight`
turns out to leave **8.2% of demand unmet** while the incumbent leaves none. Removing the
double-count alone leaves the regret **still negative**, so repairing the objective is not
sufficient and repairing the comparator is necessary. Full record in **D2.5.3**.

**Amendment, session 9 — the oracle arm is REPLACED by an arm that is an oracle by
construction, and `regret` and `comparator_headroom` are now computed against it. The retired
arm is retained beside it rather than deleted.** D2.5.3 established by arithmetic that removing
the objective's double-count leaves the regret **still negative**, so task 11's option (b) — an
arm that actually minimises the committed objective over the known trace — was the repair the
measurement demanded. `uplift/foresight.py::HindsightOraclePolicy` sizes each order against
**cumulative** generated-but-not-yet-consumed demand instead of per-window totals, which drives
its unmet demand to zero — the attainable floor of the two terms that inverted the sign — while
holding strictly less than the incumbent's 50–100 unit par band. Full record in **D2.5.4**. **This
amendment lands before the run judged against it**, per the rule at the head of this log; it
changes no threshold and in particular does not touch
`regret_objective.materiality_margin.value`, which stays at the value session 7 instantiated.

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
- **Not unreachably large.** The measured comparator headroom is `8.937888952967558` objective
  units — the **no-op** arm against perfect foresight, measured over 200 of 200 usable
  replicates in run `34366766968` (sha `245d0dc`). It supersedes the `11.79 - 2.93 = 8.86`
  figure this bracket carried from session 1's four-replicate probe, and the correction is a
  measurement update rather than a change of criterion. The fill-rate gap across the same pair
  is `0.9149 - 0.3592 = 55.6` service points. A `5.0`-point margin is roughly 4.5% of the cost
  headroom perfect foresight buys, so the criterion can fire.

**A derivable guard, enforced by the reader.** The committed margin must be **strictly less
than the measured comparator headroom**. A margin at or above the total headroom is
unfalsifiable by construction: no policy could exceed it, so `material` would be unreachable
and task 11 could only ever proceed. `digital_twin/simulation/policy.py` refuses such a value
rather than recording it.

**THE DERIVED VALUE, INSTANTIATED AT CHECKPOINT A (session 7).** Run `34570166681` measured the
comparator headroom at `8.937888952967558`, unchanged from run `34366766968` to every digit, so
the `bracketing.upper` figure above stands as written and is not re-stated here. At the committed
inputs — five service points, a `points_to_fraction` of `0.01`, and an `unmet_service` weight of
`8.0` — the rule
derives `materiality_margin = 0.40` objective units, and
`digital_twin/simulation/policy.yaml` now commits exactly that value.
`policy.py::materiality_margin` re-derives it from the rule and refuses a value the rule does
not produce, so this literal is a projection of the pre-registered criterion rather than a
second opinion about it; and `0.40 < 8.937888952967558` satisfies
`must_be_below_measured_headroom` against a quantity independent of the one it judges
(D2.5.1). **The value was not chosen with the judged number in hand:** it is the value this rule
has derived since the session-1r pre-registration, and the only thing checkpoint A supplied is
the headroom it is checked against.

#### D2.5.1 The three-arm comparator, and why the bound must be a different subtraction

**Added by amendment in session 5. It exists because the guard immediately above was vacuous,
and the way it was vacuous is the mirror of the defect this whole phase is about.**

Run `34366766968` reported `regret` and `comparator_headroom` equal **to every digit**. That was
not a coincidence, it was an identity: `RegretObjective.regret(policy, reference)` is
`aggregate(policy) - aggregate(reference)`, and the headroom was `mean_baseline - mean_foresight`
over the same two arms. So the guard checked the margin against the very quantity being judged,
and every margin inside the bracket above — `0.264` to `0.709` objective units — satisfied both
`material` clauses by construction. **A number that cannot fail is not a number, and a verdict
that cannot be anything else is not a verdict.**

The comparator therefore runs **three** arms per replicate, at one seed and one cadence:

| Arm | Policy | Role |
|---|---|---|
| A | none (`NoOpRecordingPolicy`) | the **independent** bound: `comparator_headroom = A - C` |
| B | the committed `(s, S)` reference policy | the **subject**: `regret = B - C` |
| C | `ForesightPolicy`, built from A's recorded trace | the oracle |

`regret` and `comparator_headroom` are now different subtractions over different pairs, so the
guard bounds the margin against a quantity independent of the one it judges. `headroom >= regret`
is no longer a tautology but a claim about the world — doing nothing cannot cost less than running
the incumbent — and `uplift/regret.py` reports `unavailable` and exits 2 if it fails, rather than
handing a verdict to a guard it has just invalidated.

**The reference arm is `Par_Level_Reorder`, and it had already landed.** Four documents recorded
it as "another spec's unlanded precondition"; it is on disk at
`uplift/baselines/par_level_reorder.py`, `.kiro/specs/decision-integrity-uplift-proof/` marks its
tasks 2, 2.1 and 2.2 `[x]`, and Property 1 already runs against it. Ownership is that spec's and
this record does not adopt it; availability was never the blocker. The blocker was that the
comparator invoked no `DecisionPolicy` at all. That correction is conflict N.

**Both of its levels are read from the twin, not chosen.** A materiality margin is allowed
exactly one irreducible choice (`service_points`, above); a comparator is allowed none.

- The reference arm's reorder point `s = 50`, read from `engine.py`'s
  `self._restock_threshold = 50.0`, commented "safety-stock level that triggers restock" — the
  twin's own reorder point, which is what makes this arm the *incumbent* rather than a
  differently-tuned policy that happens to be transparent.
- The reference arm's order-up-to level `S = 100`, read from `engine.py`'s initial inventory of
  `100.0` per SKU — the same literal `regret_objective.normalisers.on_hand_units` already lifts
  as `100.0 x 10 SKUs = 1000.0`. Ordering up to the opening level is the twin's own notion of
  full.

**What is NOT claimed, stated because the bracket above depends on it.** That
`Par_Level_Reorder(s=50, S=100)` *reproduces* the twin's endogenous restock is **unproven**: the
endogenous rule is an internal guard the engine evaluates, while this arm is an external
order-up-to decision applied through `add_stock` on the comparator's cadence. So the lower
bracket's `fill_rate = 0.8556` is a *comparable* reference for this arm, not a measurement of it.
Whoever wants the stronger claim must measure both and report the difference; nothing here
licenses assuming it is zero.

**And one asymmetry is recorded rather than closed.** `Observation.inventory` is declared
`Mapping[str, int]`, so arms driven through the shared observe-decide-apply loop see truncated
stock levels. Arm C is deliberately **not** routed through that loop: it would read levels up to
one unit low per SKU per decision and over-order by up to ~240 units per replicate, which at the
committed `on_hand` normaliser and weight is up to ~0.24 objective units — the same order as the
`0.40` margin — and it would move the oracle's cost up and the measured regret **down**, which is
the self-serving direction. Arm C therefore keeps the arithmetic run `34366766968` measured. The
residual asymmetry is that the oracle observes more precision than the arms it is compared
against; closing it means widening `Observation` (a schema change touching every fixture and
every arm, including the consensus arm) and is not this amendment's to take.

**The ratchet direction is `down`, and unlike the weights this number has one.** D2.3 records
that an objective weight has no better-direction, so the weights are pinned without a ratchet.
The materiality margin is different: **raising it is the self-serving move.** A larger margin
makes `material` harder to reach, which makes Finding 4 harder to falsify, which lets the spec
proceed. So the margin may only ever be *tightened*, and
`infrastructure/quality/ratchets.json` records `direction: down` for exactly that reason. This
is the one threshold in the phase where the motivated error has an obvious sign.

#### D2.5.2 The oracle arm is not an upper bound on achievable performance (session 7)

**Added by amendment after the first measurement ever taken against the `(s, S)` reference arm.
D2.5.1 fixed the identity defect and left a second one standing, and the second one is worse
because it fails in the direction that lets the spec proceed.**

Run `34570166681` (sha `e94a1ac`), 200 of 200 usable replicates, `unusable_seeds: []`:

| quantity | measured |
|---|---|
| `mean_noop_cost` (arm A) | `11.835228527152536` |
| `mean_foresight_cost` (arm C) | `2.897339574184977` |
| `mean_reference_cost` (arm B) | `2.0849871282327` |
| `comparator_headroom` = A - C | `8.937888952967558` (unchanged from run `34366766968`) |
| **`regret` = B - C** | **`-0.8123524459522771`** |
| 95% interval on the judged contrast | `[-0.8273245113311902, -0.7977944274457321]` |
| `headroom_minus_regret` | `9.750241398919835` |

**The interval excludes zero, so the sign is not noise.** Arm C sits strictly between the
other two: better than doing nothing, **worse than the incumbent it is supposed to bound.**

**What that makes `regret`.** R5.1's regret is "how much better a policy could have done given
perfect information", a quantity bounded below by zero. Measuring `-0.81` does not mean the
incumbent is 0.81 better than optimal; it means **arm C is not the optimum and therefore not an
oracle**, so `B - C` is a difference between two ordinary policies and is not a regret at all.

**`ForesightPolicy`'s own docstring already contained the admission, and drew the opposite
conclusion from it.** It states the arm is "a **lower bound on achievable performance**, which
makes the regret it induces a **conservative** estimate... it can only understate how much room
intelligence has, never overstate it." The first clause is correct and the second does not
follow: a comparator that loses to the subject does not *understate* the room for intelligence,
it **inverts the sign of the quantity being reported**. Nothing in the tree asserted
`regret >= 0`, so nothing objected.

**Three candidate mechanisms were excluded before the fourth was accepted.** Each is recorded
because excluding it is what makes the surviving explanation more than a guess:

1. **Unequal footing between arms B and C — EXCLUDED by construction.** `run_three_pass`
   imports `observe`, `_apply_reorders` and `_derive_unit_costs` from `uplift/harness.py` and
   drives every arm on one cadence with one `restock_threshold`, precisely so that "what an arm
   may see" and "how a reorder reaches the twin" cannot drift between the arms being subtracted.
2. **Lead time penalising just-in-time ordering — EXCLUDED.** `_apply_reorders` applies stock
   through `sim.add_stock`, which is **instantaneous**. Neither arm pays a lead time on the
   orders it places, so the oracle's 60-minute look-ahead is not arriving late. (The engine's
   own `_restock` lead time is disabled in all three arms by `restock_threshold: 0.0`.)
3. **The `Mapping[str, int]` truncation asymmetry D2.5.1 records — EXCLUDED, and this one was
   checked rather than assumed because the ADR predicted an effect of the right order (~0.24
   objective units) in the right direction.** Arm C is genuinely not routed through `_drive`;
   `run_three_pass` constructs it separately and the comment there states the reason. So the
   protection this document claims is in the code, and the inflation it guards against is not
   what happened.

**THE SURVIVING EXPLANATION, STATED AS A HYPOTHESIS WITH A FALSIFIER, NOT AS A FINDING.** The
objective charges `stockout_rate` at weight **8.0** — equal to `unmet_service` and eight times
`on_hand` — and **D3 below records what its numerator counts: a per-step count of SKUs at zero
stock, which "does not count unmet demand".** `ForesightPolicy.decide` orders exactly the
shortfall between foreseen demand and present stock, "no more, no less", so by construction it
drives on-hand toward **zero** at the end of every window; `Par_Level_Reorder(s=50, S=100)`
holds a 50-100 unit buffer and is almost never at zero. Against a term that measures *empty
shelf* rather than *unserved customer*, the efficient policy scores worse than the hoarding one,
at weight 8.0, while the buffer's surplus is charged at weight 1.0 against a 1000-unit
normaliser. **That is sufficient to invert an 0.81-unit difference, and it requires none of the
three mechanisms above.**

**It is a hypothesis because the per-term decomposition was not measured.** The artifact reports
five aggregate costs and no breakdown, so which term dominates each arm is inferred from the
weights and from D3's statement of the numerator, not read off a measurement. **The falsifier is
cheap and is owed:** report the per-term contribution of each arm in `twin-regret.json`, and the
hypothesis is confirmed or killed by one labelled run. Nothing here licenses assuming it.

**Why the D2.5.1 guard could not have caught this, which is the transferable part.**
`_measure` refuses a run in which `headroom >= regret` fails. Substituting the definitions,
`A - C >= B - C` reduces to **`A >= B`** — "doing nothing costs at least as much as the
incumbent". That is a true and unrelated claim, and it is silent about whether C bounds either of
them, because C cancels. **A guard built from two expressions that share a term cannot constrain
that term.** The three-arm repair made `regret` and `comparator_headroom` different
subtractions, which was the fix conflict M needed, and it left the oracle's validity unasserted.

**THE REFUSAL THIS AMENDMENT ADDS.** `uplift/regret.py::_measure` now reports
`status: unavailable` and exits 2 when the measured `regret` is negative, naming the arm costs
in its reason. This is deliberately the same shape as the existing `headroom >= regret` refusal,
for the same reason that guard gives: a measurement whose comparator has been invalidated is
**not** handed to a classifier as a verdict. It fails loudly rather than returning
`inconclusive`, which is what it would otherwise return today.

**And that is why the refusal is not cosmetic.** With both E2c sensitivity flips landed (tasks
12.3 and 13.3), `classify_regret` would map this same negative regret to **`sub-margin`** — the
one verdict that *licenses reading the result as consistent with Finding 4*. Conflict M's defect
forced `material`, which stops the spec loudly; this one would have **confirmed** the premise
quietly, on a comparator that loses to its own subject. **A false stop is recoverable; a false
confirmation is the outcome this entire spec exists to prevent.**

**What is NOT claimed.** That the `(s, S)` policy is near-optimal — nothing here measures that.
That `stockout_rate` is the culprit — see the falsifier above. That the objective's weights are
wrong: D2.3 records them as committed decision-relevance choices, and a term that counts empty
shelves may well be *intended* to be costly. What is claimed is narrower and is measured: **the
arm currently labelled `perfect_foresight` does not bound the arm it is subtracted from, so no
verdict about `(s, S)` regret can be read from their difference.**

#### D2.5.3 The decomposition, measured — one hypothesis, two defects (session 8)

**D2.5.2 named its own falsifier: "report the per-term contribution of each arm". Run
`34590696403` did. This section is that measurement and what it settles.**

Per-term mean weighted cost, 200 of 200 usable replicates, and the per-term attribution of the
judged contrast:

| term | foresight (C) | reference (B) | `regret_by_term` = B - C |
|---|---|---|---|
| `stockout_rate` | `0.6566` | **`0.0000`** | **`-0.6566`** |
| `unmet_service` | `0.6566` | **`0.0000`** | **`-0.6566`** |
| `on_hand` | `0.2402` | `0.7382` | `+0.4980` |
| `delivery_latency` | `1.2849` | `1.2876` | `+0.0027` |
| `spoilage_rate` | `0.0592` | `0.0592` | `0.0000` |

The five terms sum to `-0.8125`, which is `regret` to rounding — **the decomposition identity
holds on real data, not only in the property that asserts it.** `dominant_regret_term` is
`stockout_rate` at a **0.808** share.

**D2.5.2's hypothesis is confirmed in direction and corrected in mechanism.** It predicted that
`stockout_rate`, at weight `8.0`, would dominate because it counts SKUs at zero stock rather
than unmet demand, charging a just-in-time oracle for being efficient. **Direction: right, and
by a wide margin.** But two things it did not predict are now measured, and they are separate
defects with separate owners.

**DEFECT 1 — `stockout_rate` and `unmet_service` are ONE quantity, by construction on this path,
so the objective applies an effective weight of 16.0 to unmet demand.** The decomposition reports
them **bit-identical** for all three arms — verified by `==` on the raw artifact values, not read
off rounded output.

**And the mechanism is structural rather than horizon-specific, which is a correction to this
section's own first draft.** That draft called the identity conditional, reasoning from
`uplift/kpi.py`'s `fill_rate = orders_delivered / max(1, orders_created)`, which shares no
denominator with `stockout_rate = unmet_demand_events / demand_events` and would collapse only
when `orders_created == demand_events`. **That cited the wrong derivation.**
`uplift/regret.py::_measure` reads `SimulationMetrics.fill_rate`, the **engine property**, which is
`(demand_events - unmet_demand_events) / demand_events` and whose own docstring states it is "the
exact complement of `stockout_rate`". Over one shared denominator, `1 - fill_rate == stockout_rate`
identically. **A citation is not a mechanism; read the code path the assertion names.**

**FINDING 60 — `fill_rate` HAS TWO INEQUIVALENT DEFINITIONS IN THIS TREE, and which one a
measurement inherits depends on its read path.** The engine metric is the complement of
`stockout_rate`; `KpiExtractor`'s is `orders_delivered / orders_created` and is not. Task 9.1 kept
`orders_created` and `demand_events` as separate counters precisely because they can differ, so the
two definitions genuinely diverge — asserted by construction in
`tests/uplift/test_service_term_identity_property.py` (**Property 64**) rather than left to a
horizon to exhibit. **One domain term, two meanings, one of them silently doubling a committed
weight.** The counters are now reported per arm in `twin-regret.json` so a reader can re-derive the
identity from the artifact instead of trusting this section.

**D3 IS NOT FALSIFIED, and the first draft of this section over-reached in saying so.** D3's claim
that the two "diverge whenever an order..." is about `KpiExtractor`'s derivation, where it is
**true**. D3 and this section were describing different `fill_rate`s. The defect is not that D3 is
wrong; it is that **the term is defined twice and the objective consumes the definition under which
two of its five weights collapse into one.** Both carry `8.0` in D2.3, so a single quantity is
priced at `16.0` while the record describes two independent terms — **and a weight nobody intended
is not a committed decision-relevance choice.**

**DEFECT 2 — the arm labelled `perfect_foresight` leaves 8.2% of demand unmet; the incumbent
leaves none.** `0.6566 / 8.0 = 0.0821`. The reference arm's figure is **exactly zero**: a
par-level policy holding 50–100 units never runs a shelf empty. `ForesightPolicy.decide` orders
"the shortfall between foreseen demand and present stock — no more, no less", so it carries **no
buffer at all**, and any within-window timing or granularity effect becomes unserved demand.
**Perfect foresight of window TOTALS is not perfect foresight of arrival ORDER.** So the arm is
not merely mis-scored by defect 1; on the objective's own service term it is **genuinely worse
at serving demand** than the policy it is supposed to bound. A policy that leaves 8.2% of demand
unmet cannot be a lower bound on achievable cost.

**THE ARITHMETIC THAT SETTLES TASK 11's THREE OPTIONS, and it is why this decomposition was
worth taking before choosing one.** Suppose defect 1 is repaired and the double-count removed —
drop `unmet_service`, keep `stockout_rate`:

```
regret = -0.6566 + 0.4980 + 0.0027 + 0.0000 = -0.1559
```

**Still negative.** So option (c), repairing the objective's numerator, is **necessary and not
sufficient**: the oracle would still lose. Option (b), replacing `ForesightPolicy` with an arm
that actually minimises the committed objective over the known trace — which would give it a
buffer and drive its service term toward the incumbent's zero — **is the repair the measurement
demands.** Option (a) is now discharged: it was the cheapest and it bought the answer.

**Two of D3's insensitivity records are independently confirmed here**, which is a side benefit
worth recording because it cost nothing. `spoilage_rate` is `0.0592` for **all three arms** and
contributes **exactly zero** regret — consistent with D3's statement that `_spoilage` reads
neither inventory level nor order size. `delivery_latency` moves by `0.0027` across arms that
differ enormously in stocking behaviour — consistent with an independent `uniform(10.0, 45.0)`
draw. **The decomposition is therefore also evidence that D3's table is accurate where it claims
insensitivity**, and the two flips tasks 12.3 and 13.3 owe are real work rather than
bookkeeping.

**What is still NOT claimed.** That the 8.2% unmet figure is caused by within-window arrival
order specifically — that is the most plausible reading of a no-buffer policy, and the mechanism
has not been isolated. That defect 1 was unintentional; D2.3 committed both weights and the
record should be read before assuming an error rather than a choice. And that repairing arm C
makes the regret positive: **that is the next measurement, not a prediction to act on.**

#### D2.5.4 The hindsight oracle - an oracle by construction rather than by label (session 9)

**Added by amendment in session 9, and it lands before the run judged against it** per D2.5's own
ordering rule. It exists because D2.5.3 settled task 11's three options by arithmetic: removing the
objective's double-count leaves the regret at `-0.1559`, still negative, so option (c) is necessary
and not sufficient and **option (b) is the repair the measurement demands.**

**WHY ARM C's RULE CANNOT SERVE, walked to the code rather than cited.** `DemandTrace.record` is
called at demand **generation** time. Stock is decremented, and `unmet_demand_events` incremented,
at the bottom of `engine.py::_delivery` - **after** `_pick_pack_dispatch`'s `normal(8.0, 2.0)`
timeout and `_delivery`'s own `uniform(10.0, 45.0)` travel timeout. So fulfilment lags generation
by a mean of about `8.0 + 27.5 = 35.5` simulated minutes: roughly **59% of a 60-minute window, and
on a single draw it can exceed the window entirely.** `ForesightPolicy` sizes stock against the
units *generated* in `[t, t + w)` and holds nothing back, while the units actually *consumed* in
that interval were generated in roughly `[t - 35.5, t + w - 35.5)`. The two sets differ, the arm
carries no buffer to absorb the difference, and the shortfall is charged at weight `8.0` **twice**
(defect 1 above). **Perfect foresight of window totals is not perfect foresight of arrival order** -
which is the mechanism D2.5.3 explicitly declined to claim, now isolated.

**THE RULE, AND WHY IT NEEDS NO INVENTORY READING AND NO CHOSEN CONSTANT.** Let `G(x)` be the units
the trace records as generated strictly before `x`, `I` the opening stock, and `w` the interval until
this arm's next decision. Every unit consumed in `[t, t + w)` was generated before `t + w`, so
holding `G(t + w) - consumed(t)` units at `t` is **sufficient** to serve every fulfilment that can
arrive before the next decision. Because `add_stock` is instantaneous and the only other mover of
stock is `_delivery`'s decrement, `on_hand(t) = I + supplied(t) - consumed(t)`; substituting it,
**`consumed` and `on_hand` both cancel** and the target reduces to

```
cumulative supply through t + w = max(I, G(t + w))
```

a function of the recorded trace and the opening stock **alone**. Two consequences carry the whole
design:

* **It reads no inventory.** The `Mapping[str, int]` truncation D2.5.1 records therefore cannot bias
  it in either direction, so unlike arm C it can be driven through the **same**
  observe-decide-apply loop as arms A and B. D2.5.1 recorded that asymmetry as accepted debt for
  its owner; this arm **closes** it rather than documenting it again.
* **It contains no additive buffer term at all.** `max(I, G)` is the pointwise-least cumulative
  supply satisfying coverage: `I` is forced because `add_stock` cannot remove stock, and `G(t + w)`
  is the coverage requirement itself. A materiality margin is allowed exactly one irreducible
  choice (D2.5); **a comparator is allowed none**, and
  `tests/uplift/test_hindsight_oracle_admissibility_property.py` asserts the absence rather than
  promising it.

**WHY `regret >= 0` IS NOW STRUCTURAL, and what it reduces to.** The service terms are
`stockout_rate = unmet/demand` and `unmet_service = 1 - fill_rate`, which defect 1 establishes are
the same quantity; this arm attains their **exact floor**, zero, so their contribution to
`regret = B - D` is `cost_B(service) - 0 >= 0`. The remaining terms are holding and latency, where
the arm holds at most `max(I, G)` against the incumbent's 50-100 unit par band. The old guard
`headroom >= regret` substituted to `(A - C) >= (B - C)` and reduced to `A >= B`, in which **the
oracle cancels** - which is precisely why it was silent about C. Nothing reduces away here: the
claim is about arm D's own attained floor, not about a difference in which it appears twice.

**THE DOMAIN THE OPTIMALITY CLAIM HOLDS OVER, stated so it is not overclaimed.** The arm is optimal
given **instantaneous replenishment and no ordering lead time**, which is the twin's committed
comparator configuration (`comparator.restock_threshold: 0.0` disables the engine's own `_restock`
lead time, and `_apply_reorders` applies through `sim.add_stock`). Under a non-zero lead time the
true optimum would order earlier. And the trace records **generation** times only - never the
pick/pack and travel draws that decide *when* a unit is consumed - so a policy able to observe
fulfilment times could hold strictly less. This arm is therefore a **lower bound on achievable
performance** and the regret it induces is **conservative**: it can only understate how much room
intelligence has, never overstate it. That is the safe direction. Unlike arm C's identical claim,
it is not contradicted by the arm losing to its own subject on the service terms.

**WHAT WOULD MAKE THIS WRONG - two falsifiers, both mechanical rather than remembered.**

1. **`hindsight_attains_zero_unmet` is `False`.** Arm D covers cumulative outstanding demand at
   every decision, so it can only stock out if the coverage inequality was violated: a coverage
   hole, an arm pair that did not share a demand path, or a decision cadence wider than the window.
   A `False` means this subsection's construction argument has **failed**, not that a number looks
   wrong. `_measure` sums the counter over every usable replicate and reports the boolean, because
   one replicate exhibiting zero is not the claim.
2. **`hindsight_arm_is_pointwise_best` is `False`.** `regret.py::hindsight_min` takes the least cost
   any declared arm achieved at each replicate. An arm optimal by construction must **be** that
   minimum at every replicate, so a `False` says another arm beat the arm the verdict is read
   against, on the run's own numbers. The two together are a per-run test of the claim rather than a
   re-reading of this document.

**`hindsight_min` IS NOT THE COMPARATOR, and the distinction matters.** A best-of-the-arms-we-ran
floor is a **within-sample** bound: it can only ever be as good as the best arm present, would
report zero regret against a family of uniformly bad policies, and would *rise* if a worse arm were
added. It is reported as a sanity floor and as falsifier 2, never as the subject.

**ARM C IS RETAINED, NOT DELETED, and the fourth arm's cost is paid rather than avoided.** Runs
`34570166681` and `34590696403` were judged against arm C; deleting it would make both unreadable,
and `ForesightPolicy` would become the "declared but instantiated nowhere" defect finding 39
recorded. The comparator therefore runs **four** arms, at **+33%** on the dominant term of
`uplift.yml::twin-regret`. What that buys: one run reports both the retired and the current oracle,
so the repair's effect is measurable **within a single run** rather than across two runs at two
shas, and `comparator_headroom_vs_foresight` remains available as session 7's prediction-1 check -
it must still read `8.937888952967558`, which is what would prove adding arm D perturbed neither
arm A nor arm C, exactly as adding arm B perturbed neither.

**KEY MEANINGS THAT MOVED, recorded because a silent one would be the defect.** `regret` and
`comparator_headroom` keep their **form** - `mean_reference - mean_<oracle>` and
`mean_noop - mean_<oracle>` - and change **which arm** supplies the subtrahend. `oracle_arm` and
`judged_contrast` are reported in the artifact so no reader has to infer it, and both prior
quantities are retained under `regret_vs_foresight` and `comparator_headroom_vs_foresight`.

**DEFECT 1 IS ORTHOGONAL AND STILL OWED TO THE OPERATOR.** Repairing this comparator does not
repair the objective, and this subsection deliberately does not touch
`regret_objective.weights`: moving a committed weight's meaning is a D4-class change affecting
D2.3, D3 and every historical value quoting them. **The two interact in one direction only, and it
is favourable:** with arm D and the incumbent both at zero unmet demand, the service terms **cancel
in the judged contrast**, so the 16.0 double-count contributes exactly nothing to `regret` even
while it stands. That is why `reference_attains_zero_unmet` is reported beside
`hindsight_attains_zero_unmet` - the pair is what licenses that sentence on the run's own numbers.
Defect 1 still gates **checkpoint B**, whose task 13.5 defines dominance over every KPI the R5.33
objective names, and there the double-count does not cancel.

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
