# Metamorphic Relations Coverage Matrix

The v4.0 plan defines twelve metamorphic relations spanning the eight agents.
Each relation is a property that should hold across pairs of related inputs:
e.g. *if temperature increases, ice-cream demand should not decrease*. This
matrix maps every relation to the test file that enforces it and the invariant
it ultimately protects.

## Coverage matrix

| ID | Agent | Relation | Test file | Invariant |
|----|-------|----------|-----------|-----------|
| MR-DP-001 | Demand Prophet | Demand non-decreasing in event-context strength (IPL proximity) | `agents/demand_prophet/tests/test_metamorphic.py::test_demand_monotone_in_event_strength` | I-3 schema, business correctness |
| MR-DP-002 | Demand Prophet | Forecast scale-invariant under unit-conversion (kg ↔ g) | `agents/demand_prophet/tests/test_metamorphic.py::test_demand_unit_invariant` | I-3 deterministic schema |
| MR-RN-001 | Routing Navigator | Route distance non-increasing as orders are removed (subset relation) | `agents/routing_navigator/tests/test_metamorphic.py::test_distance_subset_monotone` | I-3, business correctness |
| MR-RN-002 | Routing Navigator | Symmetric routes for swapped origin/destination (round-trip) | `agents/routing_navigator/tests/test_metamorphic.py::test_route_symmetry` | I-3 |
| MR-IS-001 | Inventory Sentinel | Safety stock non-decreasing in demand variance | `agents/inventory_sentinel/tests/test_metamorphic.py::test_safety_stock_variance_monotone` | I-2 (independent reward), I-3 |
| MR-IS-002 | Inventory Sentinel | Reorder point non-decreasing in lead-time | `agents/inventory_sentinel/tests/test_metamorphic.py::test_reorder_point_lead_time_monotone` | I-3 |
| MR-PO-001 | Pricing Oracle | Price recommendation respects price cap (≤ base × 1.30) under any input perturbation | `agents/pricing_oracle/tests/test_metamorphic.py::test_price_cap_invariant` | I-6 |
| MR-PO-002 | Pricing Oracle | Price elasticity sign preserved under affine transform | `agents/pricing_oracle/tests/test_metamorphic.py::test_elasticity_sign_invariant` | I-3, business correctness |
| MR-DS-001 | Disruption Shield | Disruption severity score monotone in affected-zones cardinality | `agents/disruption_shield/tests/test_metamorphic.py::test_severity_zone_monotone` | I-3 |
| MR-FG-001 | Freshness Guardian | Discard recommendation monotone in time-since-receipt | `agents/freshness_guardian/tests/test_metamorphic.py::test_discard_recency_monotone` | I-3 |
| MR-SU-001 | Sustainability Agent | Carbon footprint non-decreasing in delivery distance | `agents/sustainability_agent/tests/test_metamorphic.py::test_carbon_distance_monotone` | I-3, sustainability ESG |
| MR-ST-001 | Supplier Trust | Trust score non-increasing in failed-delivery count | `agents/supplier_trust/tests/test_metamorphic.py::test_trust_failure_monotone` | I-3, business correctness |

## How relations are checked

Each `test_metamorphic.py` follows the same pattern using Hypothesis:

```python
from hypothesis import given, strategies as st

@given(base=base_input_strategy(), delta=delta_strategy())
def test_<relation>(base, delta):
    out_base = agent.predict(base)
    out_perturbed = agent.predict(apply_delta(base, delta))
    assert relation_holds(out_base, out_perturbed), (
        f"MR-XX-NNN violated: base={out_base}, perturbed={out_perturbed}"
    )
```

## Running

```bash
# All metamorphic tests across all agents
pytest agents/*/tests/test_metamorphic.py -v

# Single relation
pytest agents/pricing_oracle/tests/test_metamorphic.py::test_price_cap_invariant -v

# As part of the v4.0 compliance gate
make verify-v4-compliance
```

## Hypothesis settings

All metamorphic tests run with:

- `max_examples=200` in CI, `max_examples=1000` in `mutation.yml`
- Deterministic seed via `HYPOTHESIS_PROFILE=ci`
- Database `.hypothesis/` cached in CI for shrink-replay determinism

## Adding a new relation

1. Append a row to the matrix above with the next free ID (e.g. `MR-DP-003`).
2. Add the test to the agent's `tests/test_metamorphic.py`.
3. Reference the related invariant in `spec.yaml` `invariants:` block so
   `pre-commit run spec-coverage` enforces test presence.
4. Add a Hypothesis strategy to `tests/strategies.py` if the input shape is new.

## Invariant cross-reference

| Invariant | Relations enforcing it |
|-----------|-------------------------|
| I-2 (independent rewards) | MR-IS-001 |
| I-3 (deterministic schema) | All twelve |
| I-6 (price cap) | MR-PO-001 |
| Business correctness | MR-DP-001, MR-RN-001, MR-PO-002, MR-FG-001, MR-SU-001, MR-ST-001 |

The matrix is regenerated quarterly by scanning `tests/test_metamorphic.py`
files for `MR-*` markers; mismatches between this file and source-of-truth
markers fail the `pre-commit run contract-validate` hook.
