# Runbook: KV-Cache Collapse

**Severity**: P2 (LLM cost & latency rise; eventual P1 if Tier 3-4 SLO breaches)

## Symptoms

- `synapse_ollama_cache_hit_rate{tier="tier_2"} < 0.70` for >15 minutes
  (Prometheus alert `KVCacheCollapse`).
- LLM call p95 latency (`synapse_ollama_request_seconds_bucket`) doubles.
- Cost-tracker dashboard shows token spend rising while throughput is flat.
- Decisions appear correct (no hallucinations), only slower.

## Why it matters (ADR-021)

KV cache reuse depends on **stable prefix + append-only context + deterministic
serialization** (I-13, I-14). Any drift in the prompt prefix (timestamp,
random sample, dict key reorder) invalidates the cache for the entire
conversation, forcing Ollama to recompute attention over the full prompt.

## Diagnose

```bash
# Confirm collapse, not just low traffic
curl -s "http://localhost:9090/api/v1/query?query=synapse_ollama_cache_hit_rate"

# Recent commits to KV-cache-sensitive files
git log --since="24 hours ago" --oneline -- \
    orchestrator/llm/context_builder.py \
    orchestrator/consensus/protocol.py \
    orchestrator/llm/ollama_client.py \
    packages/synapse_common/contracts.py

# Check pre-commit hook would now flag
pre-commit run kv-cache-check --all-files
```

## Common causes

| Cause | Detect | Fix |
|------|--------|-----|
| f-string in system prompt | `kv-cache-check` hook flags it | Replace with constant + tool-call argument |
| `time.time()` or `datetime.now()` injected | hook flags it | Move timestamp out of prompt; pass via tool input |
| Dict serialization order changed | manual diff vs prior MLflow prompt artifact | Use `json.dumps(obj, sort_keys=True, separators=(',',':'))` |
| Context list re-ordered or items removed | `audit_decisions.context` row count drops | Restore append-only invariant (I-14); add status row instead of removing |
| New tool added to mask without prefix | LangSmith trace shows mixed tool name format | Re-add `rl_`/`feast_`/`graph_`/`llm_`/`twin_`/`playbook_` prefix per ADR-022 |

## Mitigate

1. **Revert the offending commit** when `git log` plus the hook surface a
   recent change. This is the cheapest fix and restores cache hit rate within
   ~10 minutes as new conversations rebuild the KV cache.
2. **Force-rebuild KV cache** by replaying the canonical conversation
   warm-up:
   ```bash
   python scripts/warm_kv_cache.py --tier 2 --conversations 100
   ```
3. **Tighten contracts**: Add a `@deal.pre` precondition on
   `OllamaClient.chat_completion` asserting `messages[0]['content']` matches
   the registered system prompt hash.

## Recovery verification

- Cache hit rate climbs back above 0.70 within 15 minutes
- Token spend per decision drops to baseline
- LLM p95 latency returns to baseline

## Postmortem template

- Trigger commit / config change
- Time to detect, time to revert
- Cost impact (additional tokens billed)
- Add a regression test in `tests/test_kv_cache_invariants.py`
- Update `kv-cache-check` pre-commit hook to catch the new pattern
