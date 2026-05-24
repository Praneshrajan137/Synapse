# DR Runbook — Postgres Primary Failover

**Trigger:** the primary Postgres pod is unreachable / OOM-killed and the
replica must take over.

## Symptoms
- All `audit_consensus` INSERTs raise `OperationalError`.
- `synapse_breaker_state{name="audit_postgres"}` = OPEN.
- Outbox dispatcher cannot drain → `synapse_outbox_lag_seconds` climbing.

## Likely Causes
1. WAL disk full.
2. OOM-kill on the primary pod after a large query.
3. Network partition between orchestrator and Postgres.

## Verification
```bash
kubectl get pods -n synapse -l app=postgres
kubectl logs -n synapse postgres-primary --tail=200
kubectl exec -n synapse postgres-primary -- pg_isready -U synapse_app
```

## Mitigation
1. Confirm the read replica is healthy:
   `kubectl exec -n synapse postgres-replica -- pg_isready`.
2. Promote the replica: `kubectl exec -n synapse postgres-replica -- pg_ctl promote`.
3. Update the orchestrator's `SYNAPSE_AUDIT_DSN` to point at the new primary.
4. Re-run `synapse audit verify --since=<incident-start>` to confirm the
   chain survived the failover (chain is per-row; replication should
   preserve `prev_hash`/`current_hash`).

## Game-Day Drill
Quarterly: `kubectl delete pod postgres-primary` and observe automatic
promotion + audit chain integrity.

## Postmortem Anchor
Capture the WAL-position of the last committed row pre-failover and
the first post-promotion row — chain `prev_hash` should bridge them.
