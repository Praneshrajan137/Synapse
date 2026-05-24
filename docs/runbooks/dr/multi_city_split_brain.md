# DR Runbook — Multi-City Split-Brain

**Trigger:** Bengaluru and Mumbai orchestrators issue conflicting
decisions for a shared customer / SKU during a network partition.

## Symptoms
- `synapse_audit_chain_tamper_detected_total > 0` on either city's
  audit chain.
- Audit-verify CLI flags a `prev_hash` mismatch on rows created during
  the partition window.
- DPDPA erasure cascade (Sprint 9 §M-life-3) sees Postgres rows for a
  city it shouldn't.

## Likely Causes
1. Cross-city Linkerd mTLS handshake failure.
2. Kafka broker partition between the two regions (Sprint 9 keeps a
   shared Kafka cluster — Sprint 10 may move to per-city brokers).
3. Brownout controller registered for the wrong city (regression in
   Sprint 9 §M1 wiring).

## Verification
```bash
# 1. Confirm both city orchestrators are alive.
kubectl get pods -A -l app=orchestrator

# 2. Check brownout registry.
kubectl exec -n synapse orchestrator-bengaluru-0 -- \
  python -c "from orchestrator.consensus.brownout import _REGISTRY; print(_REGISTRY)"

# 3. Walk the audit chain for the incident window.
SYNAPSE_AUDIT_DSN=... synapse audit verify --since=<incident-start>
```

## Mitigation
1. If the partition is still active, freeze one side: scale Mumbai
   orchestrator to 0 replicas. Bengaluru continues to serve global
   decisions until the partition heals.
2. After the partition heals, re-run `synapse audit verify`. If the
   chain breaks at the partition boundary, file a P0 — the chain is
   not designed to merge concurrent insert streams (Sprint 10 may
   introduce per-city sub-chains).
3. For DPDPA: re-run `cascade_erasure(subject_id, cities=["bengaluru","mumbai"])`
   on any subject that touched either side during the partition.

## Game-Day Drill
Annual: simulate a 30-minute east-west partition with `tc` netem on
the Linkerd dataplane. Acceptance:
- No tamper events on either chain after the partition heals.
- Brownout per-city isolation holds (Mumbai degradation does not
  shed Bengaluru traffic).

## Postmortem Anchor
Capture the breaker timelines + audit chain hashes around the
partition boundary + the brownout-decisions counter per city.
