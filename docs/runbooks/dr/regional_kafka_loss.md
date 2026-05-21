# DR Runbook — Regional Kafka Loss

**Trigger:** entire Kafka cluster in a region is unreachable for >5 min.

## Symptoms
- `synapse_kafka_consume_lag` flat (no new messages).
- Orchestrator outbox lag climbing (`synapse_outbox_lag_seconds > 60`).
- Breaker for the Kafka producer reports OPEN (M2 §breakers).
- Brownout escalates to `SHED_LLM_ONLY` for the affected city.

## Likely Causes
1. Cloud-provider zone outage.
2. Disk pressure on every broker simultaneously (rare; usually KRaft quorum loss).
3. Network partition between agents and the broker cluster.

## Verification
```bash
kubectl get pods -n kafka -l app=kafka
kubectl logs -n kafka -l app=kafka --tail=200 | grep -i quorum
kubectl exec -n kafka kafka-0 -- bin/kafka-broker-api-versions --bootstrap-server localhost:9092
```

## Mitigation
1. If a single broker is down → wait for ISR to recover.
2. If quorum lost → restore from the latest snapshot in S3
   (`kafka-snapshots/<date>/`). Sprint 9 schedules daily snapshots
   via `data_fabric/scheduler` (Sprint 10 wires the real upload).
3. While Kafka is down → the orchestrator outbox holds new decisions
   (Sprint 7 §M8). Decisions queue; deliver-on-recovery is automatic.
4. Audit trail is unaffected — Postgres + chain hash run independently.

## Game-Day Drill
Quarterly: scale Kafka StatefulSet to 0 replicas for 10 minutes.
Acceptance:
- Brownout transitions to `SHED_T4_T3` within 30s.
- Outbox lag rises but Postgres audit chain stays intact.
- Recovery: outbox drains in ≤5 min after Kafka comes back.

## Postmortem Anchor
Link the Kafka broker logs + the outbox lag time series + the
brownout-decisions counter for the incident window.
