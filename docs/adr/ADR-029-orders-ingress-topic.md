# ADR-029: Orders Ingress Topic — Freeze Exception

## Status
Accepted (Sprint 7)

## Context
Sprint 1 froze the Kafka topic registry at 16 topics. The freeze applies to inter-agent topics, where partition counts and retention drive the consensus protocol's correctness model and capacity planning. Adding new inter-agent topics post-freeze would require ADR-level review per topic.

`api/routers/orders.py` has been publishing customer-order events to a topic name (`synapse.orders.demand`) that does not exist in [infrastructure/kafka/topics.json](../../infrastructure/kafka/topics.json). The publish path is real (the API endpoint accepts orders, validates them, and produces to Kafka), but the topic was never registered. Behaviour today: either Kafka auto-create silently materialised it (forbidden by CLAUDE.md: "NEVER enable `auto.create.topics`"), or messages have been silently dropped. Either way the system has been operating outside its declared contract.

The orders endpoint is a legitimate ingress event source. Removing it would regress real functionality; rerouting it through the orchestrator HTTP path adds a hop on the demand-signal hot path; the simplest and most honest fix is to register the topic.

## Decision
Add `synapse.orders.demand` to the Kafka topic registry as topic #17, classified as `category: "ingress"` (not `"inter-agent"`). Mark as the only freeze exception until Sprint 10. Future ingress topics may use the same exception with a fresh ADR.

Concretely:
- Producer: `api_gateway` (single producer, by contract).
- Consumers: `demand_prophet` (forecast input), `inventory_sentinel` (real-time stock impact), `orchestrator` (audit + decision triggering).
- Partitions: 8 (matches `synapse.demand.forecast` so consumers can co-partition).
- Retention: 24h (orders are processed within seconds; 24h covers replay during an outage).
- Schema: [proto/domain/order_request.schema.json](../../proto/domain/order_request.schema.json), validated at handler boundary.

The API router `api/routers/orders.py` is refactored to:
1. Use the shared `SynapseProducer` singleton from app lifespan (not a fresh producer per request).
2. Validate the payload against `order_request.schema.json` before producing.
3. Inject W3C `traceparent` into Kafka message headers for end-to-end traceability (WS-2).
4. Read the `Idempotency-Key` HTTP header and propagate it as `idempotency_key` in the payload; downstream consumers dedupe.

## Consequences

**Positive**
- The contract gap closes: every `producer.produce(...)` call site references a registered topic. CI test `tests/contracts/test_kafka_topic_registry.py` now passes and stays green.
- The orders ingress path is observable like any other topic: lag metrics, partition counts, retention enforcement.
- Future ingress topics (returns, cancellations, inventory adjustments from third-party WMS) have a precedent for registration without disturbing the inter-agent freeze.

**Negative / Trade-offs**
- The "16 frozen topics" claim in CLAUDE.md needed updating. Replaced with: "Sprint 1 froze inter-agent topics (1-16). Sprint 7 added topic 17 as the only freeze exception per ADR-029."
- The registry now distinguishes `category` for clarity. Existing topics gain `category: "inter-agent"` lazily on next touch; not retro-applied to avoid spurious diff.

**Neutral**
- Partition count (8) chosen to match `synapse.demand.forecast`; this lets `demand_prophet` consume both topics with the same partitioner and avoid cross-partition correlation work.

## Alternatives Rejected

1. **Reroute through orchestrator HTTP.** Adds 1 hop on a hot path (Tier-1 budget = 100 ms; orchestrator HTTP round-trip alone is ~5-15 ms). Also conflates ingress with consensus.
2. **Remove the orders publish path entirely.** Treats real ingress as scaffolding; regresses functionality and would require redesigning the demand signal pipeline (currently consumes orders to update Feast online features).
3. **Use an existing topic.** None of the 16 existing topics carries the "raw customer order" semantic. Misuse of `synapse.inventory.state` or `synapse.demand.forecast` would violate single-producer contracts.

## Related
- [ADR-006: Kafka Event Streaming](ADR-006-kafka-event-streaming.md)
- [ADR-013: Protobuf Payloads](ADR-013-protobuf-payloads.md)
- WS-2 (Distributed Correctness) in the Sprint 7 elevation plan.
