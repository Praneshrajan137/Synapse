# Runbook: DPDPA Right-to-Erasure Cascade (ADR-035)

**Trigger:** a data subject exercises their DPDPA Article 12 right and
the support team approves the erasure. The runtime erasure operator
invokes `synapse_common.dpdpa.cascade_erasure(subject_id, cities)`.

## What the cascade does

| Store | Action | Identifier |
|---|---|---|
| Postgres `audit_decisions` | DELETE rows where `selected_action.customer_id = subject_id`. | `synapse_erasure_operator` role |
| Neo4j (per city) | `MATCH (n {customer_id: $sid, city: $city}) DETACH DELETE n` | city-filtered (E-S6-05) |
| Feast online (per city, Redis db=0 or db=1) | `HDEL synapse:<city>:feast:<sid>:*` | per-city DB index |
| Kafka `synapse.audit.log` | Emit null-value tombstone keyed `<city>:<sid>` | log compaction drops priors |

Each backend call is wrapped in try/except so a partial failure
surfaces per-store and the caller can retry just the failed stores.

## Verification

```bash
# 1. Run the cascade
python -c "
from synapse_common.dpdpa import cascade_erasure
# wire pg_session / neo4j_driver / feast_redis / kafka_producer here
result = cascade_erasure('test-subject-001', cities=['mumbai'])
print(result)
"

# 2. Confirm Postgres rows are gone
psql -h $POSTGRES_HOST -U synapse_erasure_operator -d synapse_audit \
     -c "select count(*) from audit_decisions where selected_action ->> 'customer_id' = 'test-subject-001';"

# 3. Confirm Neo4j nodes are gone (Mumbai only)
cypher-shell -u neo4j -p $NEO4J_PASSWORD \
     "MATCH (n {customer_id: 'test-subject-001', city: 'mumbai'}) RETURN count(n)"

# 4. Confirm Feast keys are gone (Mumbai db=1)
redis-cli -h redis -n 1 KEYS 'synapse:mumbai:feast:test-subject-001:*'

# 5. Confirm Kafka tombstone landed
# (log compaction drops historical records on next compaction cycle)
```

## Audit chain handling

Tombstoning does NOT modify existing chained-hash rows. The audit
chain remains intact; the row's PII payload is what gets purged via
the DELETE on `audit_decisions`. ``synapse audit verify`` skips
already-deleted rows but reports them as "legacy" gaps.

## Postmortem Anchor

For every erasure, log the `subject_id` + cities + cascade result +
the operator who authorised it. Retain the operator log for 7 years
per the data-protection retention policy (separate from
`audit_consensus`).
