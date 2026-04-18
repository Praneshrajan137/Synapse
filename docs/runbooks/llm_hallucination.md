# Runbook: LLM Hallucination Detected

**Severity**: P1 (incorrect agent decisions; may breach I-6 price cap or I-14 context append-only)

## Symptoms

- Audit reviewer flags decisions where LLM output references SKUs, store IDs, or
  numeric prices that do not exist in the consensus context.
- Prometheus alert `LLMSchemaValidationFail` fires when `synapse_llm_schema_validation_failures_total` rate > 0.05/s.
- LangSmith trace shows tool call to non-existent tool name (e.g. agent invents `inventory_kafka_publish`).
- Customer-facing P0 ticket: "Order placed for invalid SKU".

## Diagnose

```bash
# Recent failed schema validations
docker logs synapse-orchestrator --tail 500 | grep "schema_validation_failed"

# LangSmith trace search (Tier 3-4 traced at 100%)
# Filter: events.error == True; agent_id == <suspect>
```

For a specific decision id:

```bash
psql "$POSTGRES_DSN" -c \
    "SELECT context_id, agent_id, output_payload, llm_raw_response
     FROM audit_decisions
     WHERE decision_id = '<id>'"
```

## Mitigate

1. **Quarantine the offending model**: If the hallucination is reproducible
   against a specific model version, quarantine it.
   ```bash
   curl -X POST http://localhost:8085/admin/quarantine \
        -d '{"agent": "<agent>", "model_version": "<version>", "reason": "hallucination"}'
   ```
   The orchestrator falls back to the prior MLflow `Production` version.
2. **Rollback model**: Follow `model_rollback.md` if quarantine isn't enough.
3. **Increase context determinism**: Verify `context_builder.py` is appending,
   not mutating, the `ContextMessage` list (I-14). If a recent commit broke
   this, revert and redeploy.
4. **Tighten guardrails**: For Pricing Oracle, ensure the price cap
   (`base_price * 1.30`) is enforced BEFORE LLM output is honored — see
   `agents/pricing_oracle/inference/pipeline.py` `@deal.post` contracts.
5. **Re-prime KV cache**: If hallucination correlates with cache eviction
   (`synapse_ollama_cache_hit_rate` dropped recently), follow `kv_cache_collapse.md`.

## Investigation

For Tier 3-4 hallucinations, pull the LangSmith trace and check:

| Symptom | Likely cause | Fix |
|--------|--------------|-----|
| Tool name invented | Tool masking via prefill broken | Verify `tier_router.get_tool_mask()` returns `{"prefill": '{"name": "rl_'}` for the requesting tier |
| Numeric value out of context | KV cache poisoning by f-string | Run `pre-commit run kv-cache-check --all-files` |
| Past-decision contradiction | Context truncated mid-history | Check `ContextMessage` log for missing `status` rows |
| Schema field invented | System prompt drift | Diff system prompt against MLflow registered prompt artifact |

## Postmortem template

- Decision id and customer impact
- Hallucination class (tool, value, schema, contradiction)
- Detection latency (LLM output → audit reviewer → alert)
- Add concrete failing case to `tests/oracle/test_<agent>_oracle.py`
- Update `CLAUDE.md` error-pattern section
