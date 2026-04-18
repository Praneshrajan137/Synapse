# Runbook: Kafka Consumer Lag

**Severity**: P2 (decisions made on stale state); P1 if lag > 60 minutes.

## Symptoms

- `synapse_kafka_consumer_lag{topic, group} > 10000` for >5 minutes (Prometheus alert `KafkaConsumerLagHigh`).
- Demo run blocks because `wait_for_zero_lag()` in `scripts/demo/_common.py` times out (E-S6-06).
- Decision events in `audit_decisions.context` reference data older than 5 minutes.

## Diagnose

```bash
# Lag per group, per partition
docker exec synapse-kafka kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 --describe --all-groups | grep -v "^GROUP"

# Producer rate vs consumer rate
curl -s http://localhost:9090/api/v1/query?query=rate\(kafka_server_brokertopicmetrics_messagesin_total\[5m\]\) | jq '.data.result'
curl -s http://localhost:9090/api/v1/query?query=rate\(synapse_kafka_messages_consumed_total\[5m\]\) | jq '.data.result'

# Consumer health
docker logs synapse-orchestrator --tail 100 | grep -E "kafka|consumer|rebalance"
```

## Mitigate

1. **Rebalance triggered by slow consumer**: Identify the slow agent
   (`synapse_kafka_messages_consumed_total{agent}` rate is the lowest).
   Restart the agent — `confluent-kafka` will rejoin the group.
   ```bash
   docker compose restart <agent-name>
   ```
2. **Backpressure from downstream Postgres / Neo4j**: Check
   `synapse_postgres_pool_wait_seconds` and `synapse_neo4j_pool_wait_seconds`.
   If either is > 1s p95, follow `neo4j_disk.md` or scale Postgres connections.
3. **Topic partition imbalance**: For topics with consistent lag on the same
   partitions, increase partitions:
   ```bash
   docker exec synapse-kafka kafka-topics.sh \
       --bootstrap-server kafka:9092 \
       --alter --topic synapse.events.orders --partitions 12
   ```
   Note: partition count is FROZEN per Sprint 1 — requires architecture review.
4. **Consumer group skew**: Force a rebalance:
   ```bash
   docker exec synapse-kafka kafka-consumer-groups.sh \
       --bootstrap-server kafka:9092 \
       --group synapse-orchestrator --reset-offsets --to-current --execute --all-topics
   ```

## Mitigate (production overflow)

If lag exceeds 1 hour AND business impact is critical, the operator may apply
a one-time offset skip (data loss accepted):

```bash
docker exec synapse-kafka kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 \
    --group synapse-orchestrator --reset-offsets --to-latest --execute --topic <topic>
```

This MUST be logged to `audit_decisions.model_lifecycle` with reason
`KAFKA_OFFSET_SKIP` and reviewed at the next sprint exit.

## Postmortem template

- Topic + group + peak lag value
- Producer rate spike or consumer slowdown?
- Downstream dependency at fault?
- Number of decisions delayed; SLA breach minutes
- Update `synapse_kafka_consumer_lag` alert thresholds if false positive
