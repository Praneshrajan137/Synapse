# ADR-058: The Inventory Sentinel reads the request it is sent: the envelope, and the state the request carries

## Status

Accepted (operator decision S13.3=a, session 13) for D1-D5. It lands in one commit with
`packages/synapse_common/a2a_envelope.py`, whose `decision_context` D1 reads through. It
supersedes nothing and amends no ADR. Every item under *Open decisions* is the operator's.

## Context

**Finding 112** (`.kiro/specs/decision-quality-proof/tasks.md`, task 29.6). The protocol sends a
proposal agent `params={"decision_context": request}` (`orchestrator/consensus/protocol.py:1040`).
The Sentinel's `handle_request` passed `params` straight to `proposal`, which read `sku_ids` and
`store_id` at the top level. So every proposal was for `SKU001` at `STORE_BLR_001`, on
`decide()`'s missing-entry forecast (mean 10, std 3, on hand 0; `inference/pipeline.py:131-133`):
a reorder of 13.66 units (10 + 1.2206 x 3) at confidence 0.85, whatever the request said.

**What it cost, measured.** E5 (run 41289052859, sha `732ecd9`, task 25): 24000 of 24000 binding
decisions `untranslatable`, a dispatch rate of 0.0, and all three pathway-probe inputs
unresponsive. The consensus arm's mean cost, 6.883, sat beside B-prime's no-op mean of 6.870.

**The operator's decision S13.3=a:** "the envelope fix, plus the Sentinel reading the state the
request already carries: inventory position, demand rate and lead time; every assumption marked
`chosen` and recorded in a new ADR".

**What the request carries.** E5 builds it in
`uplift/consensus_arm.py::observation_to_decision_request`: `sku_ids` (the stocked SKUs, sorted),
`inventory` (on hand, units), `on_order`, `inventory_position` (on hand plus on order), `sim_time`
(engine minutes from 0), `demand_to_date` (demand events per SKU since the run began, counted
when generated), `supplier_lead_time_history` (minutes, landed orders only, one possibly empty
list per declared supplier), `sku_supplier` and `start_weekday`. It carries no store, no review
period and no cost. E5 decides once an hour for 24 hours (`uplift/e5_suite.py::E5_LOOP`).

**The constraint.** The Sentinel may read the request and constants marked `chosen`. It may not
read the world's declared parameters (`digital_twin/simulation/policy.yaml`, `world.*`). Arm O
(`uplift/oracle_arm.py`) is the comparator that does read them; *Consequences* lists the gap.

## Decision

**D1 - The envelope.** `handle_request`'s proposal branch reads `params["decision_context"]`
through `synapse_common.a2a_envelope.decision_context`, which refuses a missing or non-mapping
context and drops `None` values. The refusal is returned as JSON-RPC `-32602` (invalid params),
with a message naming `decision_context`. `sku_ids` and `store_id` are the request's own:
`DEFAULT_SKU_IDS = ("SKU001",)` and `DEFAULT_STORE_ID = "STORE_BLR_001"` (`a2a/handler.py`)
apply only when the key is absent (O2). An `sku_ids` that is not a list of non-empty strings is
refused, because a bare string would be decided one character at a time.

**D2 - The mapping**, `inference/request_state.py::forecast_from_request`. A context with neither
`inventory_position` nor `inventory` reports no stock: the function returns `None`, and
`decide()` keeps its defaults with degraded provenance, exactly as before (O1). Otherwise, for
each SKU either mapping names:

- `on_hand = inventory_position[s]`, else `inventory[s]`;
- `rate = demand_to_date[s] / sim_time`, events per minute;
- `L` = the arithmetic mean of `supplier_lead_time_history[sku_supplier[s]]`, in minutes, or the
  prior below while that supplier has landed nothing or the request names no supplier for `s`;
- `mean = rate * (L + R)`, `std = sqrt(mean)` (Poisson), `lead_time_days = L / 1440`.

`decide()`, the newsvendor and the confidence formula are unchanged. The quantity is
`max(0, mean + 1.2206 * std - on_hand)` (critical fractile 8/9, `models/newsvendor.py`) and the
confidence `clip(1 - 0.5 * std / max(mean, 1), 0.5, 0.99)`, which is `1 - 0.5 / sqrt(mean)` for
`mean >= 1`.

**D3 - The chosen values.** The last test in `agents/inventory_sentinel/tests/test_request_state.py`
pins this table to the module, so neither can change alone.

| Constant | Value | Provenance | Why |
|---|---|---|---|
| `REVIEW_PERIOD_MIN` | 60.0 | chosen | R. An order placed now must cover demand until the next order can land. The request carries no review period. 60 is E5's cadence, the only caller that sends state, and the `review_min` arm O is built with. |
| `LEAD_TIME_PRIOR_MIN` | 1440.0 | chosen | The lead time planned before a supplier has landed an order: the agent's own `DEFAULT_LEAD_TIME_DAYS = 1.0`, read from `pipeline.py` rather than restated, so it carries nothing of the world. It is long against the primary cell's 4-8 h means, and a long window over-stocks, which the agent's 8:1 `cost_under:cost_over` prices as the cheaper error. |
| `MIN_EVENTS_FOR_RATE` | 1 | chosen | The cold-start rule. With no event (`sim_time` 0, or none observed) the rate would be 0 with a spread of 0, which `decide()` reports at confidence 0.99 from no evidence. Such a SKU gets no `mean` and no `std`, so `decide()` applies its own forecast (mean 10, std 3) to the request's position and lead time. |
| `MINUTES_PER_DAY` | 1440.0 | definitional | `decide()` takes a lead time in days; the request reports minutes. |

Absent entries, each named in the module:

- A SKU absent from `demand_to_date` has had no event, because the twin adds a SKU on its first
  (`digital_twin/simulation/engine.py::_record_demand`). It is cold.
- A SKU absent from both stock mappings gets no entry, so `decide()`'s defaults apply to it in
  full, on hand 0 included.
- `perishable` and `is_essential` are not in the request, and `decide()` reads both as 0, as
  before.

**D4 - A malformed state is refused, never read as absent.** These raise `ValueError` naming the
key: a present key that is not a mapping, a stock level that is negative or not finite, a
negative or non-finite `sim_time`, a count that is not a non-negative integer, a supplier that is
not a non-empty string, a landed lead time that is not finite and > 0, and a forecast that
overflows. The handler returns the error as JSON-RPC `-32000`, and the protocol counts the agent
as failed for that decision. Defaults would hide a defect in the request's producer.

**D5 - The trace says which.** Every proposal's `justification_trace` gains one line from
`request_state.reading_trace`. It reads "Request state absent" with the SKUs on the default
forecast, or "Request state read" with three lists: the SKUs read, the SKUs with no rate, and the
SKUs with no position.

## Consequences

- **Live HTTP requests are unchanged except for the store.** `DecisionRequest`
  (`orchestrator/inference/serve.py:246-252`) carries `order_id`, `store_id`, `items`,
  `agents_involved` and two flags: no `sku_ids` and no state. The proposal is still `SKU001` on
  the default forecast with degraded provenance. Its store is now the request's, which the traffic
  generator draws from five (`scripts/traffic/decision_loop.py:45-51`), instead of always
  `STORE_BLR_001`. A null `store_id` is dropped by the helper, so the default applies.
- **The sensor loop changes more.** `orchestrator/sensor/loop.py::_build_request` sends `sku_ids`
  (its low SKUs) and `store_id` (`store_001` by default), so the Sentinel now decides for those
  SKUs at that store. It reports stock as `world_inventory`, a key the mapping does not read, so
  those decisions stay on the default forecast (O3).
- **E5 now exercises the wired path.** Every key D2 reads is in E5's request, so the Sentinel
  proposes for the ten stocked SKUs on their own position, rate and lead time, and its reorders
  name SKUs the twin stocks. Whether a proposal binds is unchanged. E5's requests carry no
  `agents_involved` or `avg_confidence`, so they route to Tier 2 (`tier_router.py:71-87`), whose
  fast path ratifies the proposal with the highest `utility_score` (`protocol.py:654`) at that
  proposal's confidence (`protocol.py:1775`). The Sentinel's utility is its mean confidence.
- **Confidence is no longer a constant 0.85.** *Falsification* item 3 projects it; no projected
  decision falls below the 0.7 floor.
- **The prior dominates the first rated decision** (inferred). At hour 1 it plans 1500 minutes of
  demand, so the order-up-to level is about 187 units against a position of about 93, an order of
  about 94 units per SKU. The realised lead time of an order placed then (about 190 minutes from
  `sup_a`) would size no order.
- **`reorder_point` mixes units.** `decide()` computes `mean * lead_time_days + ...` and `mean` is
  now demand over the protection window, not per day. Nothing acts on the field: `execute` and the
  E5 translator read `quantity` only.
- **What the Sentinel still lacks against arm O:**
  - *The declared demand profile.* Arm O integrates hourly x weekday x promotions over
    `[t, t + L + R)`. The Sentinel's run-average rate trails the profile: at hour 19 it is 0.84 of
    the flat rate while the hour runs at 1.80, under half of the evening peak (inferred).
  - *A cost-derived ratio.* Arm O derives `b` and `h` from the committed objective and orders at
    `(b + tau h) / (b + (tau + 1) h)`. The Sentinel uses the newsvendor's fixed 8/9.
  - *A Poisson quantile.* Arm O orders up to `poisson_quantile(lam, cr)`. The Sentinel uses the
    normal `mean + 1.2206 sqrt(mean)`, which differs most when the mean is small.
  - *A lead-time model.* Arm O scales the declared supplier mean by the current coupling factor and
    the geometric mean of landed ratios. The Sentinel averages landed minutes, which runs low early
    because only the faster orders have landed (right-censoring), and falls back on one day where
    arm O has the declared mean.
- **A test that sends flat params now gets `-32602`.**
  `tests/integration/test_agent_pipeline.py::TestA2AProposalRoundTrip::test_inventory_sentinel_a2a`
  sends `{"sku_ids": ["SKU001"], "store_id": "S1"}` flat, the shape finding 112 names. It has to
  move to the envelope.

## Open decisions

- **O1 - Refuse when state is absent?** A request without stock still decides on the default
  forecast with degraded provenance. Refusing would end the Sentinel's proposals on every live
  request, since none carries state today.
- **O2 - The `SKU001` default.** It is kept only for an absent `sku_ids`. Live requests name their
  SKUs in `items[].sku_id`, which the Sentinel does not read.
- **O3 - The sensor's `world_inventory`.** Read it as `inventory`, rename it at the sensor, or leave
  sensor decisions on the default forecast.
- **O4 - R for other callers.** 60 minutes fits E5 only. The traffic generator posts every 4-5
  minutes, and no request states its cadence.
- **O5 - The lead-time prior.** The agent's one day, or a pooled prior from other suppliers' landed
  orders once any has landed.

## Falsification

Each prediction below is inferred from code and parameters read for this ADR. None is measured.

1. **The pathway probe (R7.21).** With the Sentinel binding, each of `on_order`,
   `supplier_lead_time_history` and `demand_to_date` changes at least one of its pairs, because
   each moves the position, `L` or the rate. All three were unresponsive in run 41289052859. An
   input that stays unresponsive while the Sentinel binds falsifies the wiring.
2. **Dispatch.** E5's `dispatch.json` reports more than 0 of 24000 reorders applied. None applied
   while the Sentinel binds falsifies the claim that its reorders now name stocked SKUs.
3. **Escalations.** Expected confidence per hour, at the weekday mean, 0.2 demand events per minute
   per SKU at intensity 1 (`TwinConfig.order_arrival_rate` 2.0 over ten SKUs drawn uniformly), and
   first orders placed at hour 1 landing after 190, 284 and 379 minutes (supplier means x the
   hour-1 coupling factor 0.79). "prior" marks a supplier with nothing landed yet.

   | hour | rate (/min) | sup_a mean, conf | sup_b mean, conf | sup_c mean, conf | mean of 10 |
   |---|---|---|---|---|---|
   | 0 | none (cold) | 10 +/- 3, 0.850 | 10 +/- 3, 0.850 | 10 +/- 3, 0.850 | 0.850 |
   | 1 | 0.1140 | 171.0, 0.962 (prior) | 171.0, 0.962 (prior) | 171.0, 0.962 (prior) | 0.962 |
   | 6 | 0.0483 | 12.1, 0.856 | 16.6, 0.877 | 72.5, 0.941 (prior) | 0.888 |
   | 12 | 0.1325 | 33.1, 0.913 | 45.6, 0.926 | 58.2, 0.934 | 0.923 |
   | 18 | 0.1611 | 40.2, 0.921 | 55.5, 0.933 | 70.8, 0.941 | 0.930 |
   | 23 | 0.1996 | 49.8, 0.929 | 68.7, 0.940 | 87.6, 0.947 | 0.938 |

   A SKU falls below the 0.7 floor only when its mean lies between 0.36 and 2.78. The lowest
   expected per-SKU value is 0.849 (`sup_a`, hour 6, weekday factor 0.92), and 0.750 even with
   every landed lead time at the 30-minute floor. So the prediction is zero escalations caused by
   the Sentinel's confidence in E5's 24000 decisions. A `dispatch.json` counting more than 240
   (1%) decisions `withheld_for_confidence` falsifies it, unless another agent bound them.
4. **Calibration.** If `(mean, std)` is right, realised demand over `[t, t + L + R)` exceeds the
   order-up-to level about 1/9 of the time, the newsvendor fractile's complement. No job measures
   this yet; the twin's demand trace and arrived orders hold what it needs. Predicted: above 1/9
   for windows that open after the morning ramp, where the run-average rate trails the profile.
   An exceedance rate far from 1/9 measures what D2 gets wrong.
