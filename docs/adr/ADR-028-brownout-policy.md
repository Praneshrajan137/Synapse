# ADR-028: Brownout Policy

## Status
Accepted (Sprint 7, 2026-05-17)

## Context

Under sustained burn (Ollama hang, Neo4j degradation, multi-city
overload) we observed the tier router happily sending Tier-4
Monte-Carlo work into a system already missing its Tier-1 budget. The
queue grows, breakers stay closed because individual calls succeed,
but tail latency explodes. We need a higher-level shedding policy
that consults breaker state and degrades gracefully.

## Decision

`orchestrator/consensus/brownout.py:BrownoutController` keyed by
`(city, tier)`:

- `NONE` — full service.
- `SHED_T4` — Tier-4 falls back to Tier-3 with `degraded=true`.
- `SHED_T4_T3` — Tier-3 and Tier-4 fall back to Tier-2.
- `SHED_LLM_ONLY` — LLM-mediated decisions disabled; RL-only.

State is computed from:
- Ollama breaker state (`closed`/`half_open`/`open`).
- Postgres breaker state (audit writes).
- Manual override (test/admin hook).

`should_shed(tier, essential)` returns `True` when the caller must
accept a lower-tier route. Essentials (`essential=true`) are NEVER
shed, even at `SHED_LLM_ONLY`. Each shed increments
`synapse_brownout_decisions_total{level, city}` for postmortem trace-
ability.

Brownout is per-city: a Mumbai Ollama outage does not affect
Bengaluru routing.

## Consequences

**Easier:**
- Tier-1 fast path stays inside its 100 ms budget when LLM/Twin paths
  are stalled.
- Multi-city blast radius is bounded.
- Brownout state is observable and drives the burn-rate alerts (WS-4).

**Harder:**
- Tier-4 callers must tolerate Tier-3 fallback; the consensus
  protocol now emits a `degraded=true` flag callers can inspect.
- New chaos test required (`test_brownout_transitions.py`) — covers
  all four levels and the per-city isolation guarantee.

## Alternatives Rejected

1. **Linkerd retry budgets alone** — kicks in only on HTTP-level
   failures; can't shed semantically.
2. **Single global brownout level** — would shed Bengaluru during a
   Mumbai outage. Unacceptable; ADR-028 enforces per-city.
