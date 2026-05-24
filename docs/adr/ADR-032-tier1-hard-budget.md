# ADR-032: Tier-1 Hard Budget Decorator (Sprint 8 — metric only)

## Status
Accepted (Sprint 8, 2026-05-17)

## Context

I-10 mandates a Tier-1 p99 latency <100 ms. Sprint 7 brought SLO YAMLs
and a multi-window multi-burn-rate alert ([infrastructure/observability/slos/orchestrator-tier1.slo.yaml](infrastructure/observability/slos/orchestrator-tier1.slo.yaml)),
but enforcement was monitoring-only — slow handlers still ran to
completion and gradually burnt the budget.

Sprint 7 also shipped the per-(city, tier) `BrownoutController` ([orchestrator/consensus/brownout.py:62](orchestrator/consensus/brownout.py:62)),
which can shed Tier-3/4 work when burn-rate spikes. What's missing is a
**per-handler stopwatch** that flags individual Tier-1 calls exceeding
their 100 ms budget so the brownout controller has a fine-grained
signal (Sprint 9) and ops has incident-time visibility (Sprint 8).

## Decision

**Sprint 8 ships the decorator metric-only.**

```python
from synapse_common.budget import tier_budget
from synapse_common.models import DecisionTier

@tier_budget(ms=100, tier=DecisionTier.TIER_1)
async def fast_path_handler(...):
    ...
```

When wall-clock latency exceeds the budget:
- `synapse_tier_budget_exceeded_total{tier="tier_1"}` increments,
- a structured warning is logged with handler name + elapsed_ms,
- **the handler still returns its result** (no exception, no shedding).

**Sprint 9 ships the brownout wiring.** A per-city
`BrownoutController` registry (currently absent) lets the decorator
call `set_manual_override("SHED_T4")` when sustained budget violations
trip a threshold. Sprint 8 deliberately raises
`NotImplementedError` if a caller passes `on_exceed="brownout"`.

## Consequences

**Easier:**
- Ops can grep Prometheus for the new counter and find slow handlers.
- The decorator is a single import + one-line wrap — adoption is cheap.
- Sprint 9's brownout wiring lands with the seam already in place.

**Harder:**
- Two-sprint delivery for the full enforcement loop. Acceptance:
  Sprint 9 needs the per-city registry, which is its own design call.
- The decorator measures wall-clock; CPU-bound mock libraries may
  yield false-positive budget violations in stress tests.

## Alternatives Rejected

1. **Full brownout wiring in Sprint 8.** Requires the per-city
   controller registry, which depends on Sprint 9's WS-10 (Helm/Linkerd)
   topology decisions.
2. **Raise an exception when the budget is exceeded.** Crashes
   in-flight requests — strictly worse for user-visible latency.
3. **Sleep + reject when over budget.** Useless on already-completed
   requests; pre-emptive cancellation is Sprint 10 territory.

## References

- I-10: Decision tier latency budgets.
- ADR-028: Brownout Policy (Sprint 7).
- [infrastructure/observability/slos/orchestrator-tier1.slo.yaml](infrastructure/observability/slos/orchestrator-tier1.slo.yaml)
- [packages/synapse_common/budget.py](packages/synapse_common/budget.py)
