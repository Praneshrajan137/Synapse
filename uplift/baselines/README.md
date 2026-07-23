# Baseline Policy Suite

The **baseline policy suite** is the *control arm* of the Decision-Integrity Uplift
Proof. Every policy here answers one question: **what does a competent operator do
_without_ SYNAPSE?** These are deliberately transparent, textbook rules — no consensus,
no four-tier orchestration, no learning. They exist so that any KPI difference measured
against SYNAPSE's Consensus_Arm can be attributed to SYNAPSE's decisions and nothing else.

Each policy below is a **control representing operation without SYNAPSE** (R1.8). Each is
pure, deterministic, and seed-stable (identical inputs → identical decisions across runs,
R1.9), and each implements the single shared `uplift.interfaces.DecisionPolicy` interface
(`decide(obs) -> PolicyAction`) that the Consensus_Arm also uses (R1.6). The harness loop
drives all arms identically.

The suite comprises exactly four policies (R1.1), one per decision domain:

| Policy | Module | Class | Domain |
| --- | --- | --- | --- |
| Par-level reorder | `par_level_reorder.py` | `Par_Level_Reorder` | Inventory reordering |
| Static pricing | `static_pricing.py` | `Static_Pricing` (alias `StaticPricing`) | Pricing |
| Greedy routing | `greedy_routing.py` | `Greedy_Routing` | Order routing |
| No-op disruption | `no_op_disruption.py` | `NoOpDisruption` | Disruption response |

Import them all from the package:

```python
from uplift.baselines import (
    Par_Level_Reorder,
    Static_Pricing,
    Greedy_Routing,
    NoOpDisruption,
)
```

---

## Par_Level_Reorder — the (s, S) reorder control

**Plain-language rule.** Keep two thresholds per SKU: a low-water reorder point `s` and an
order-up-to target `S`, with `0 ≤ s < S`. Each step, look at each SKU's current inventory
level:

- If the level is **at or below `s`**, order enough to refill up to the target — that is,
  order `S − level` units (R1.2).
- If the level is **strictly above `s`**, order **nothing** (quantity `0`) (R1.10).

This is the classic (s, S) inventory policy taught in every operations textbook. It reacts
only to the current stock level; it does not forecast demand, weigh spoilage, or coordinate
across SKUs.

**Why it's the control without SYNAPSE.** It represents the ordinary reordering discipline
an operator applies by hand or with a simple ERP rule, with none of SYNAPSE's demand
prediction or consensus reasoning.

---

## Static_Pricing — the cost-plus pricing control

**Plain-language rule.** Price every unit at a **fixed markup over its cost**:
`price = unit_cost × markup`. The markup is a configured constant `≥ 1.0`, so the policy
never prices below cost (R1.3). It ignores demand, competition, freshness, and time.

- A **non-negative** unit cost yields `unit_cost × markup` (R1.3).
- A **negative** unit cost is invalid input: the policy rejects it with a typed error
  (`NegativeUnitCostError`) and produces **no price** — it never fabricates a price for a
  nonsensical cost (R1.12).

**Why it's the control without SYNAPSE.** Cost-plus pricing is the simplest defensible
pricing rule an operator uses when they have no dynamic-pricing intelligence. It is the
static counterpart to SYNAPSE's demand-, freshness-, and competition-aware pricing.

---

## Greedy_Routing — the nearest-store routing control

**Plain-language rule.** Assign each pending order to the **closest eligible store** by
Euclidean distance to the order's destination. When two stores are equidistant, break the
tie deterministically by choosing the **lowest store id** (R1.4).

- With a **non-empty** eligible set, pick the nearest store (ties → lowest id) (R1.4).
- With an **empty** eligible set, return **no assignment**, flag the order as
  **unroutable** with an explanatory error, and leave the order's routing state unchanged
  (R1.11).

**Why it's the control without SYNAPSE.** "Send it to the nearest store" is the obvious
greedy heuristic an operator reaches for without network-level routing optimization. It
optimizes one order in isolation, ignoring load balancing and downstream effects.

---

## NoOpDisruption — the do-nothing disruption control

**Plain-language rule.** When a disruption occurs, take **no corrective action**. For any
observation — shocked or not — the policy returns an **empty disruption action set** (R1.5),
letting the twin absorb the shock unaided.

**Why it's the control without SYNAPSE.** It is the honest floor for disruption response:
an operation with no automated disruption handling simply does nothing. It isolates the
value of SYNAPSE's disruption-shield decisions by comparing against taking no action at all.

---

## Shared contract

All four policies share the same guarantees so the harness can treat them uniformly:

- **One interface (R1.6).** Every policy exposes a `name` attribute and a
  `decide(obs: Observation) -> PolicyAction` method — the same `DecisionPolicy` protocol the
  Consensus_Arm implements.
- **Determinism / seed-stability (R1.9).** Policies hold no hidden global state. Where a
  policy accepts a `seed`, it is constructed with an instance-local RNG so identical inputs
  yield identical decisions across at least two consecutive runs. (Several policies are pure
  functions of their inputs and accept a `seed` only for interface symmetry.)
- **Partial actions.** A `PolicyAction` may set only the lever a policy controls (reorder
  quantities, price, routing assignment, or disruption actions); unset levers stay at their
  neutral defaults so the harness applies nothing for them.
