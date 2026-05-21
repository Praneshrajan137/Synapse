# ADR-030: Streaming feature materialization via Feast push API

## Status
Accepted (Sprint 7)

## Context
The seven Feast feature views are batch-materialized hourly from the
Parquet offline store into Redis. Demand Prophet's tier-1 path reads from
Redis, so a hot SKU's "orders_last_5m" can be ≤ 60 minutes stale. Tier-1
forecasts ride on a sliding rolling counter that's, in the worst case, a
full hour behind reality. I-4 (training/serving parity) was a paper
guarantee for batch but undefined for streaming.

## Decision
Add a *streaming* layer additively, leaving the offline batch path
untouched:

- **`data_fabric/feast/stream_materialization.py`** — a `StreamMaterializer`
  consumes the existing 16 Kafka topics via `synapse_common.kafka_client`,
  maintains per-key `RollingWindow`s for 1-min and 5-min spans, and pushes
  results into the Feast online store using `FeatureStore.push(..., to=PushMode.ONLINE)`.
- **`data_fabric/feast/feature_views_streaming.py`** — declarative
  PushSource-backed views (subset of the existing 7).

Late-arriving events past 5 min are routed to quarantine via
`gate_freshness` (ADR-026). Online/offline parity is enforced by an
oracle test that re-computes the rolling window offline against a fixed
Kafka segment and asserts equality within ε.

## Consequences
- Tier-1 features are fresh to within 30 s p95 (vs. 1 hour batch).
- I-6 preserved — no new Kafka topics; reuses the 16.
- Feast PushMode.ONLINE is a stable API since Feast 0.34.
- Marginal Redis traffic (~10× current write rate, well within DragonflyDB's
  ADR-019 throughput envelope).

## Alternatives Rejected
- **Kafka Streams / Flink** — heavyweight; adds operator burden disjoint
  from the rest of the stack.
- **Kafka KTable in-process** — couples feature freshness to a single agent's
  uptime. Feast keeps the source of truth shared.
- **Redis-direct writes bypassing Feast** — silently breaks training/serving
  parity (I-4). Feast push API enforces the same write path.
