# Runbook: Neo4j Disk Pressure

**Severity**: P1 (graph queries throttle; routing/inventory degrade)

## Symptoms

- Prometheus alert `Neo4jDiskUsageHigh` (`neo4j_dbms_pool_other_used_bytes / neo4j_dbms_pool_other_total_bytes > 0.85`).
- `synapse_neo4j_pool_wait_seconds` p95 > 1s.
- Routing Navigator falls back to OSRM straight-line distance (graceful degrade per I-7).
- Disk space alerts on the volume backing `/data` in the Neo4j container.

## Diagnose

```bash
docker exec synapse-neo4j df -h /data
docker exec synapse-neo4j du -sh /data/databases/* /data/transactions/*

# Page cache hit rate
docker exec synapse-neo4j cypher-shell -u neo4j -p "$NEO4J_PASS" \
    "CALL dbms.queryJmx('org.neo4j:instance=kernel#0,name=Page cache') YIELD attributes RETURN attributes.HitRatio"

# Long-running transactions
docker exec synapse-neo4j cypher-shell -u neo4j -p "$NEO4J_PASS" \
    "CALL dbms.listTransactions() YIELD transactionId, currentQuery, elapsedTimeMillis WHERE elapsedTimeMillis > 5000 RETURN transactionId, currentQuery, elapsedTimeMillis"
```

## Mitigate

1. **Compact + checkpoint**: Force a transaction-log rotation:
   ```bash
   docker exec synapse-neo4j cypher-shell -u neo4j -p "$NEO4J_PASS" \
       "CALL dbms.checkpoint()"
   ```
2. **Prune old transaction logs**: They keep around for replication; safe to prune
   if not running causal cluster.
   ```bash
   docker exec synapse-neo4j neo4j-admin database tx-log prune neo4j --to-id-of-tx <safe-id>
   ```
3. **Kill runaway query**:
   ```bash
   docker exec synapse-neo4j cypher-shell -u neo4j -p "$NEO4J_PASS" \
       "CALL dbms.killTransaction('<transactionId>')"
   ```
4. **Expand volume** (k3s): edit `infrastructure/k3s/infra.yaml`
   `volumeClaimTemplates.resources.requests.storage` and `kubectl apply`.
5. **Rebuild indexes** if degraded:
   ```bash
   docker exec synapse-neo4j cypher-shell -u neo4j -p "$NEO4J_PASS" \
       "CALL db.indexes() YIELD name, state WHERE state = 'FAILED' RETURN name"
   # Then: DROP INDEX <name>; CREATE INDEX ...
   ```

## Recovery verification

```bash
# Pool wait p95 returns < 100 ms
curl -s http://localhost:9090/api/v1/query?query=histogram_quantile\(0.95,rate\(synapse_neo4j_pool_wait_seconds_bucket\[5m\]\)\)
# Routing Navigator stops falling back to OSRM-only
curl -s http://localhost:9090/api/v1/query?query=synapse_routing_fallback_total
```

## Postmortem template

- Disk usage at alarm time + capacity remaining
- Cause: log accumulation, large query, missing index, data growth
- Did Routing Navigator graceful-degrade work? (count of fallback decisions)
- Long-term: schedule periodic `dbms.checkpoint()` cron in `infrastructure/k3s/`
