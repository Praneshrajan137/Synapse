# Runbook: Brownout Active

**Alert:** `BrownoutActive` —
`rate(synapse_brownout_decisions_total[5m]) > 0` for 2 min (WS-1 §5,
ADR-028).

## Symptoms
- `synapse_brownout_decisions_total{level=SHED_T4|SHED_T4_T3|SHED_LLM_ONLY}`
  counter incrementing.
- Tier-4 (or lower) decisions returning with `degraded=true`.
- Tier-1 latency may *improve* (the brownout is doing its job).

## Likely Causes
1. Ollama breaker is open/half-open (see `breaker_open.md`).
2. Postgres breaker is degraded.
3. Manual override set (test/admin pinned).

## Verification
```promql
# Brownout level distribution per city
sum by (level, city) (rate(synapse_brownout_decisions_total[5m]))

# Driving breaker state
synapse_breaker_state{name=~"ollama|postgres"}
```

## Mitigation
1. Fix the upstream dependency that triggered the brownout (Ollama,
   Postgres). Brownout is a symptom, not the cause.
2. Once breakers close, brownout auto-recovers to `NONE`.
3. If `essential=true` decisions are being shed, that is a bug —
   open an issue and roll back.

## Postmortem Anchor
Brownout transitions + breaker state series + chaos-test replay.
