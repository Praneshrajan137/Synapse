# Runbook: Ollama OOM (out-of-memory)

**Severity**: P1 (degraded LLM-backed decisions; Tier 3-4 unavailable)

## Symptoms

- Prometheus alert `OllamaContainerOOM` fires (`container_memory_max_usage_bytes{name="synapse-ollama"} > 0.95 * limit`).
- Agents log `httpx.ReadTimeout` against `OLLAMA_URL` for >5s.
- `synapse_ollama_cache_hit_rate` drops to 0 because the model crashed and reloaded with empty KV cache.
- Grafana dashboard `SYNAPSE / LLM` shows request rate flat-lined.

## Diagnose

```bash
docker stats synapse-ollama --no-stream
docker logs synapse-ollama --tail 200 | grep -i "killed\|oom\|cuda out of memory"
dmesg -T | tail -50 | grep -i ollama
```

For k3s:

```bash
kubectl -n synapse top pod -l app=ollama
kubectl -n synapse describe pod ollama-0 | grep -A5 "Last State"
```

## Mitigate

1. **Immediate (degrade gracefully)**: Force the orchestrator to skip Tier 3-4
   (LLM tiers) for 30 minutes. The tier router falls back to Tier 1-2 RL-only
   decisions per I-7 graceful degradation.
   ```bash
   curl -X POST http://localhost:8085/admin/tier-cap -d '{"max_tier": 2, "duration_min": 30}'
   ```
2. **Restart with reduced model footprint**: Switch to `phi3:mini` only
   (skip `deepseek-r1:14b` which uses ~12 GB) by editing `OLLAMA_MODELS`
   environment variable in `docker-compose.yml` and restarting the container.
   ```bash
   docker compose up -d --force-recreate ollama
   ```
3. **Increase memory limit**: Edit `infrastructure/k3s/infra.yaml`
   `resources.limits.memory` (or compose `mem_limit`) to next bracket.
4. **Confirm KV cache rebuild**: After Ollama is healthy, watch
   `synapse_ollama_cache_hit_rate` climb back above 0.7 within 10 minutes.

## Rollback trigger

If `synapse_ollama_cache_hit_rate{tier="tier_2"} < 0.70` for 15 minutes after
mitigation, follow `mlflow_promotion.md` rollback for any models promoted in
the prior 24 hours — system prompt drift is the most common cause.

## Postmortem template

- Time of first alert
- Memory pressure cause (model weights, concurrent requests, KV cache growth)
- Decisions degraded count (query `audit_decisions WHERE tier <= 2 AND timestamp BETWEEN ...`)
- Customer impact (orders late, HITL escalations)
- Add error pattern to `CLAUDE.md` if root cause is novel
