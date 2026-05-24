# ADR-026: W3C Trace Context Propagation + Outbox

## Status
Accepted (Sprint 7, 2026-05-17)

## Context

Sprint 5 wired OpenTelemetry but never installed a propagator, so
`traceparent` did not flow across A2A JSON-RPC, FastAPI, or Kafka
header boundaries. The audit table records `decision_id` but the
`trace_id` flow is broken: a Jaeger span ends at the API gateway and a
new orphan span starts inside the orchestrator. End-to-end forensics
is impossible.

Separately, the orchestrator writes the audit row first, then publishes
to Kafka — two unrelated writes. A crash between them yields either a
ghost audit (no Kafka message) or a phantom Kafka message (no audit).

## Decision

**Trace propagation (WS-2 §1):**
- `synapse_common.tracing.configure_tracing` now installs a W3C
  `CompositePropagator([TraceContext, Baggage, B3])` globally.
- `synapse_common.tracing.inject_a2a_headers(headers)` writes the
  current span context into an HTTP-style header dict.
- `KafkaHeaderCarrier` adapts confluent-kafka's
  `list[tuple[str, bytes]]` to OTel's TextMap so `traceparent` rides
  the Kafka header on every produce.
- `SynapseConsumer.poll_with_headers()` returns the header list so the
  consumer can call `extract_kafka_context(headers)` and continue the
  trace.

**Outbox pattern (WS-2 §3):**
- New table `audit_outbox` (migration
  `orchestrator/audit/migrations/0002_outbox.sql`) with INSERT +
  SELECT + UPDATE grants only.
- `synapse_common.outbox.enqueue(session, ...)` writes the outbox row
  in the SAME transaction as the audit row.
- `orchestrator/outbox/dispatcher.py` is an asyncio worker registered
  via `Lifespan.on_shutdown`. It drains `status='PENDING'` rows,
  publishes via `SynapseProducer` (`enable.idempotence=true`), marks
  `SENT`, and retries with Full Jitter on failure.

**Idempotency (WS-2 §2):**
- `synapse_common.idempotency.enforce_idempotency` is a FastAPI
  dependency. POST endpoints read `Idempotency-Key`, hash
  `method + path + canonical_body`, and short-circuit on cache hit.

## Consequences

**Easier:**
- Forensics: `decision_id → trace_id → Jaeger` is one click.
- Recovery: orchestrator crash mid-flight no longer creates ghost
  audit rows or phantom Kafka messages.
- Replay (ADR-026 sibling): the replay engine reads outbox row +
  audit row in one query.

**Harder:**
- The outbox dispatcher is a new failure mode. Chaos test
  `tests/integration/test_outbox_after_crash.py` covers it.
- Idempotency requires Redis on the hot path of POSTs (already in the
  stack).

## Alternatives Rejected

1. **Dual-write with at-least-once compensating delete** — fragile
   under partial failure.
2. **Debezium CDC on `audit_consensus`** — heavy; pulls in Kafka
   Connect for one consumer.
3. **Skip W3C, use only B3** — the rest of the OSS ecosystem has
   settled on W3C; B3 is kept as a fallback inside the composite for
   long-tail clients.
