# Runbook: Outbox Stuck

**Alert:** `OutboxLag` — `synapse_outbox_lag_seconds > 60` for 5 min
(WS-2 §3, ADR-026).

## Symptoms
- `synapse_outbox_lag_seconds` rising; oldest `audit_outbox` row in
  `PENDING` for >60 s.
- `synapse_outbox_dispatch_total{status="PENDING"}` flat.
- Audit rows exist for recent decisions but downstream agents don't
  see Kafka messages.

## Likely Causes
1. Kafka broker unreachable or rejecting writes.
2. Outbox dispatcher task crashed or never started.
3. Postgres `audit_outbox` table holds rows in `FAILED` state past
   `SYNAPSE_OUTBOX_MAX_ATTEMPTS`.

## Verification
```bash
# 1. Dispatcher heartbeat
kubectl logs deploy/synapse-orchestrator | grep outbox_dispatcher_started

# 2. Pending rows
psql -h $POSTGRES_HOST -U synapse_app -d synapse_audit \
     -c "select status, count(*) from audit_outbox group by status;"

# 3. Latest pending
psql -h $POSTGRES_HOST -U synapse_app -d synapse_audit \
     -c "select id, decision_id, attempts, last_error, created_at
         from audit_outbox where status='PENDING'
         order by created_at limit 5;"
```

## Mitigation
1. If dispatcher is stopped — restart orchestrator pod; the lifespan
   should re-register the task.
2. If Kafka is down — fix Kafka first; dispatcher will drain
   automatically.
3. For `FAILED` rows, inspect `last_error`. If retryable, manually:
   ```sql
   UPDATE audit_outbox SET status='PENDING', attempts=0
   WHERE id IN (...) AND status='FAILED';
   ```

## Postmortem Anchor
Always link the responsible commit + the
`synapse_outbox_lag_seconds` time series.
