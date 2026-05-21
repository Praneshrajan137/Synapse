# ADR-025: Dual-layer payload validation (Pydantic + JSON Schema)

## Status
Accepted (Sprint 7)

## Context
Pydantic v2 guards every payload at *construction* time inside a single Python
process. But payloads cross two further boundaries — A2A (JSON-RPC over HTTP)
and Kafka — where Pydantic is no longer in the picture. The 11
`proto/domain/*.schema.json` and 2 `proto/a2a/*.schema.json` files were the
declared source of truth for these wire formats but were never enforced at
runtime. Drift between Pydantic models and the schemas was undetectable until
a downstream consumer broke. I-3 (deterministic JSON + contract integrity)
was a paper guarantee.

## Decision
Validate every outbound payload twice:

1. **Pydantic** stays the *intra-process* gate (model construction, field
   validators, `@field_validator`).
2. **JSON Schema** becomes the *inter-process* gate, applied at:
   * `synapse_common.kafka_client.SynapseProducer.produce(..., schema=...)`,
   * `synapse_common.a2a_sdk.send_a2a_request(...)` (for the envelope), and
   * any function decorated with `@validates_schema("...")`.

Schemas are loaded once at process start by `synapse_common.schema_registry`
(jsonschema Draft-07 validators, cached in a module-level singleton). Failures
raise `SchemaViolation` aggregating every error path — the message is dropped,
not silently sent.

## Consequences
- Wire-format drift surfaces synchronously instead of at the consumer.
- A non-conformant test (`method="propose"` vs schema enum `proposal`) was
  caught and fixed during rollout.
- Adds a one-time validator-compile cost (sub-millisecond) per process boot.
- Round-trip parity (Pydantic → JSON → schema) becomes a CI invariant.

## Alternatives Rejected
- **Pydantic-only**: cheap but assumes every consumer is Python + Pydantic.
- **Protobuf everywhere**: ADR-013 already retired protobuf for JSON; bringing
  it back for validation would re-import the dependency we shed.
- **Avro**: introduces a schema registry service (Confluent or Apicurio) we
  don't run. Stays open as a future option for binary efficiency.
