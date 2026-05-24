# Runbook: Tier-Budget Exceeded

**Alert source:** `rate(synapse_tier_budget_exceeded_total{tier="tier_1"}[5m]) > 0.1`
(WS-8 §M13, ADR-032).

## Symptoms
- `synapse_tier_budget_exceeded_total{tier="tier_1"}` incrementing.
- Tier-1 fast-path handler completed but exceeded its 100 ms budget.
- Sprint 8: metric-only, no automatic shedding. Sprint 9: brownout
  controller sheds Tier-3/4 traffic when sustained.

## Likely Causes
1. **Ollama queue depth high** — even a Tier-1 RL call may stall if
   Ollama is mid-restart or a heavy Tier-4 prefill is in flight. Check
   the Ollama breaker (`synapse_breaker_state{name="ollama"}`).
2. **Postgres lock contention** — audit-writer fan-out into outbox
   may block. Check `synapse_outbox_lag_seconds` (Sprint 7 metric).
3. **Cold Pinecone bulk lookup** — semantic-cache miss + per-vector
   query. Sprint-8 `retrieve_batch` is the mitigation (consumer
   refactor is Sprint 9).
4. **Profiler running** — `SYNAPSE_PROFILE=1` adds 5-30 ms overhead
   per request. Make sure profiling is disabled in production.

## Verification
```promql
# Slow handlers in the last 5 minutes
topk(10, rate(synapse_tier_budget_exceeded_total{tier="tier_1"}[5m]))

# Drill-in by service
synapse_inference_latency_seconds{quantile="0.99", tier="tier_1"}

# Concurrent breakers / outbox state
synapse_breaker_state
synapse_outbox_lag_seconds
```

## Mitigation
1. If Ollama is unhealthy → see `breaker_open.md`.
2. If Postgres locks are accumulating → see `outbox_stuck.md`.
3. If a single handler is consistently slow, profile it:
   `SYNAPSE_PROFILE=1 make profile`.
4. Sprint 9 wires automatic brownout shedding; in Sprint 8 you may
   need to manually invoke
   `BrownoutController.set_manual_override(BrownoutLevel.SHED_T4)`.

## Sprint-9 promotion path
Sprint 9 adds a per-city `BrownoutController` registry and graduates
the decorator's `on_exceed="brownout"` mode (currently raises
`NotImplementedError`). After cutover, sustained Tier-1 budget
violations auto-shed Tier-4 work.

## Postmortem Anchor
Tier-1 budget = 100 ms p99. Sustained burn for more than 15 min is a
P1 — page the on-call.
