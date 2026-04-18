# ADR-013: Binary Payload Encoding — Protobuf for A2A Payloads

## Status
Accepted

## Context
A2A messages (proposal, debate_respond, execute) carry per-agent payloads — forecasts, route plans, inventory actions. JSON payloads are ~5-10× larger than equivalent Protobuf and incur non-deterministic field ordering, breaking KV-cache hits in Ollama context (I-13). Pure gRPC would replace JSON-RPC entirely, losing ecosystem compatibility with the A2A spec. We need binary payload efficiency without abandoning JSON-RPC.

## Decision
A2A messages use **JSON-RPC 2.0** as the envelope (preserved per ADR-001) but the `params.payload` field is **Protobuf-encoded** and base64-wrapped. Schema definitions live in `proto/a2a/*.proto`. Generated Python stubs land in `packages/synapse_common/proto_gen/`. The `synapse_common.a2a_sdk` provides transparent encode/decode. JSON Schema (`.schema.json`) is retained for the envelope; Protobuf schemas govern the payload.

## Consequences
- Payload size drops 5-8× → faster Kafka throughput, smaller Ollama context windows.
- Deterministic byte-level serialization → KV-cache friendly (I-13, ADR-021).
- Adds protoc generation step to CI; pre-commit hook runs on `*.proto` changes.
- Two schema systems to maintain (JSON for envelope, Protobuf for payload); justified by the cache-hit-rate benefit.
- Backwards compatibility managed via Protobuf field numbering (never reuse a tag).

## Alternatives Rejected
- **Pure JSON payloads**: rejected — non-deterministic ordering breaks I-13.
- **gRPC only**: rejected — abandons A2A JSON-RPC envelope.
- **MessagePack**: rejected — schema-less; loses contract enforceability.
