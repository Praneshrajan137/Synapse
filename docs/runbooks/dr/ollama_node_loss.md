# DR Runbook — Ollama Node Loss

**Trigger:** the Ollama pod (or the GPU node it runs on) is unreachable.

## Symptoms
- `synapse_breaker_state{name="ollama"} = 2` (OPEN).
- Tier 2-4 decisions begin shedding via the Sprint 9 brownout
  controller; `synapse_brownout_decisions_total{level=~"SHED_T4.*"}`
  climbs.
- Tier-1 RL fast path is unaffected.

## Likely Causes
1. GPU driver crash (`nvidia-smi` returns non-zero on the host).
2. Ollama process OOM (large model swap).
3. Network partition between orchestrator and the Ollama service.

## Verification
```bash
kubectl get pods -n synapse -l app=ollama
kubectl logs -n synapse ollama --tail=200
kubectl exec -n synapse ollama -- curl -s localhost:11434/api/tags
```

## Mitigation
1. Brownout already shed Tier-3/4 → no action required for ongoing
   requests.
2. If the GPU node is gone, scale Ollama deployment up so KEDA places
   it on a healthy node.
3. If the failure is OOM → bump the memory limit for the
   `llama3.3:70b-instruct-q4_K_M` model variant first (48 GiB ideal,
   32 GiB minimum).
4. Once Ollama is back, the breaker auto-transitions
   `OPEN → HALF_OPEN → CLOSED` on the first successful call; brownout
   returns to `NONE`.

## Game-Day Drill
Quarterly: `kubectl delete pod -n synapse ollama` during a synthetic
Tier-3 burst and confirm shedding + recovery within 2 min.

## Postmortem Anchor
Capture the breaker-state timeline + tier-budget-exceeded counter +
brownout-decisions counter.
