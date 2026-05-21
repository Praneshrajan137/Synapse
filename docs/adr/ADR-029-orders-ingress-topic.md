# ADR-029: Orders Ingress Topic — Freeze Exception

## Status
Accepted (Sprint 7, 2026-05-17)

## Context

`infrastructure/kafka/topics.json` declared 16 topics and was frozen
after Sprint 1 (CLAUDE.md Kafka Rules). The 16 topics describe
**inter-agent** flow: agent → agent, agent → orchestrator, twin →
orchestrator, audit. They do not describe ingress.

In Sprint 5 the API gateway started accepting demand orders at
`POST /api/v1/orders`. The implementation in
[api/routers/orders.py:34-42](api/routers/orders.py:34) produces to
`synapse.orders.demand` — a topic that does not exist in the registry.
Either auto-create kicks in (forbidden by Kafka Rules in CLAUDE.md) or
messages silently land in a non-existent topic. The Sprint-7 audit
flagged this as the most visible compliance gap.

## Decision

Add `synapse.orders.demand` as topic #17:

```json
{"name": "synapse.orders.demand",
 "partitions": 8,
 "retention_hours": 24,
 "producer": "api_gateway",
 "key_consumers": ["demand_prophet", "inventory_sentinel", "orchestrator"]}
```

Partition count (8) is sized for store-id key cardinality; partition
key is the `store_id` field so per-store ordering is preserved.
Retention (24 h) matches the freshness window for the demand pipeline.
Payload schema is `proto/domain/order_request.schema.json` (Draft-07).

This is the **only** freeze exception until Sprint 10. The rule
distinction is now explicit:

- **Inter-agent topics (16)** — frozen post-Sprint 1. Any change
  requires an ADR superseding ADR-029.
- **Ingress topics (1, growing under explicit ADR)** — a different
  topology category. New ingress sources require their own ADR and a
  CI test entry but do not violate the inter-agent freeze.

A new CI gate (`tests/contracts/test_kafka_topic_registry.py`) AST-walks
the codebase and fails on any `.produce("synapse.…")` call whose
literal topic is not present in `topics.json`. This guarantees that
future drift between code and registry surfaces immediately.

The API router in [api/routers/orders.py](api/routers/orders.py) is
refactored as part of the same PR to:

- use the `SynapseProducer` singleton (CLAUDE.md Kafka Rules) instead
  of a bare `confluent_kafka.Producer()` per request;
- read and verify the `Idempotency-Key` header
  (`packages/synapse_common/idempotency.py`);
- inject W3C `traceparent` Kafka headers (ADR-026).

## Consequences

**Easier:**
- `synapse.orders.demand` is provisioned at boot via
  `scripts/create_kafka_topics.sh` rather than relying on
  auto-create.
- The topic-registry test catches future ingress drift in CI.
- Multi-city order ingress is partition-keyed by `store_id`, keeping
  Bengaluru vs Mumbai partitions cleanly separable.

**Harder:**
- The frozen-contract narrative now requires a small clarification
  ("inter-agent vs ingress") in CLAUDE.md.
- Every future ingress topic addition requires its own ADR.

## Alternatives Rejected

1. **Re-route to an existing topic** (e.g. `synapse.demand.forecast`).
   Rejected: pollutes the forecast topic with raw orders and breaks the
   producer/consumer contract advertised in `topics.json`.
2. **Remove the orders endpoint and demand it be filed against the
   orchestrator instead.** Rejected: the API gateway is the canonical
   ingress; the orchestrator must not be a public-facing handler.
3. **Lift the freeze on `topics.json` entirely.** Rejected: the freeze
   is the mechanism that keeps inter-agent contracts stable across
   sprints; lifting it weakens the whole testing topology.

## References

- CLAUDE.md, "Kafka Rules"
- ADR-006: Kafka event streaming
- ADR-026: W3C trace propagation (sibling change in Sprint 7)
- `proto/domain/order_request.schema.json`
- `tests/contracts/test_kafka_topic_registry.py`
