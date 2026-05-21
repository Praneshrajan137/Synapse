# ADR-027: Causal envelope on every A2A call

## Status
Accepted (Sprint 7)

## Context
A consensus decision involves up to 8 agents, each making A2A calls to peers
or to the orchestrator. Today the audit row records the decision but not the
*causal lineage* — which agent's proposal triggered which other agent's
debate, and which root user request started the cascade. Triaging a
production incident required reading orchestrator logs and reconstructing
the DAG by hand.

## Decision
Extend the JSON-RPC envelope (`proto/a2a/jsonrpc.schema.json`) with two
optional fields, both populated by `synapse_common.a2a_sdk`:

- **`correlation_id`** — stable per originating user/decision flow. Set
  once at the API gateway, propagated unchanged across every hop.
- **`causation_id`** — id of the *immediately upstream* envelope that
  triggered this one. Forms a parent edge in the causal DAG.

Server handlers call `bind_causal_context(...)` on inbound envelopes; outbound
`send_a2a_request(...)` reads `ContextVar`s set by that bind and stamps the
next envelope. Persistence: `audit_consensus.correlation_id` (string,
indexed) and `audit_consensus.causation_chain` (JSONB array of envelope ids),
added by Postgres migration `001_causal_envelope_and_rationale.sql`.

## Consequences
- Given any `decision_id`, a single SQL query reconstructs the full upstream
  DAG of agent calls and root user request.
- Honors I-2 (auditability) — the audit record is now causally complete.
- Adds two optional string fields per A2A call (≤ 70 bytes); negligible cost.
- OTel spans pick up `synapse.correlation_id` so distributed traces and
  audit lineage are joinable.

## Alternatives Rejected
- **OTel trace_id only** — OTel is sampled in production; correlation_id
  must be unsampled and persistent for compliance.
- **W3C Trace Context propagation** — covers HTTP headers but not the
  envelope schema. Used in addition (header `X-Correlation-Id`).
- **Logging-only** — logs are sampled and ephemeral; lineage must live in
  the immutable audit ledger.
