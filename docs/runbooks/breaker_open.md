# Runbook: Circuit Breaker Open

**Alert:** `BreakerOpen` — `synapse_breaker_state{name=~".+"} == 2`
for 2 min (WS-1 §2, ADR-025).

## Symptoms
- Specific named breaker (`ollama`, `neo4j_http`, `feast_http`,
  `pinecone`, `a2a:<host>`) reports state 2 (OPEN).
- Calls through that dependency fail fast with
  `CircuitBreakerOpenError`.
- Tier-aware brownout (ADR-028) likely active.

## Likely Causes
1. Dependency is genuinely down or overloaded.
2. A2A SDK is retrying on a non-retryable 4xx (bug — file an issue).
3. Connection-pool exhaustion (look at `httpx` Limits in
   `clients.py`).

## Verification
```promql
# State per breaker
synapse_breaker_state

# Recent error rate from the breaker's dependency
rate(synapse_inference_latency_seconds_count{tier="tier_3"}[5m])
```

## Mitigation
1. **Ollama open** — restart Ollama pod; verify `/api/tags` responds.
2. **Neo4j open** — check disk pressure (`docs/runbooks/neo4j_disk.md`)
   first; if disk OK, check JVM heap.
3. **Pinecone open** — non-critical (semantic cache). Tier-1/2 RL
   policies should continue; investigate when load permits.
4. The breaker will half-open automatically after
   `reset_timeout` (30 s default).

## Postmortem Anchor
Link breaker state series + the upstream dependency's own dashboard.
