# ADR-038 — HTTP-A2A is primary for inter-agent RPC; Kafka is for event-sourcing only

**Status:** Accepted
**Date:** 2026-05-26
**Authors:** WS-3 audit
**Supersedes / Refines:** I-9 (CLAUDE.md "Architecture Rules"); ADR-029 (orders ingress topic)
**Related:** [ADR-026 — W3C trace propagation](./ADR-026-w3c-trace-propagation.md)

## Context

The SYNAPSE registry (`infrastructure/kafka/topics.json` v1.1.0) declared `"all_agents"` as consumers of `synapse.orchestrator.decision`, and every agent's `agent_card.json` declared a `kafka_topics.consumes` array. The implication: agents react to orchestrator decisions and peer agent publications via Kafka subscriptions, forming an event-driven mesh.

The WS-3 audit (May 2026) verified, by exhaustive grep, that **no agent has a `KafkaConsumer.subscribe(...)` call site**. The only Kafka consumer in the repo is `digital_twin/sync/kafka_sync.py`, which subscribes to a parallel `synapse.<agent>.state` naming scheme that does not appear in the registry. Inter-agent RPC happens exclusively over the HTTP A2A endpoint (`POST /a2a`) — orchestrator → agent and agent → agent.

The gap between declared topology and runtime topology was the largest single source of misunderstanding for new contributors and the primary load-bearing finding of the audit.

## Decision

1. **HTTP-A2A is the primary, supported inter-agent RPC protocol.** Every agent exposes `POST /a2a` (JSON-RPC 2.0) and accepts proposals/debate/execute calls there. The orchestrator's consensus protocol fans out to agents via `httpx`.
2. **Kafka is for event-sourcing, audit, and digital-twin synchronisation — not for inter-agent RPC.** Agent publishes become append-only events that downstream consumers (digital twin, audit sink) read for state mirroring and durability. They are NOT the RPC channel.
3. **The topic registry expresses two consumer fields, not one:**
   - `consumers`: the empirical set — every name must have a verifiable `Consumer.subscribe(...)` call site in this repo (enforced by `scripts/audit/topic_consumer_truth.py`).
   - `consumers_planned`: design intent for a future event-driven mode. Documentation only; no runtime guarantee.
4. **The `"all_agents"` shorthand is removed from `topics.json`.** It was always a fiction; making it explicit prevents readers from inferring a topology that does not exist.
5. **Every `agent_card.json` carries the same shape (`consumes`, `consumes_planned`, `topology_note`) so the same tooling can audit them uniformly.**

## Consequences

### Positive
- The codebase reads honestly. A new contributor opening `topics.json` sees what actually flows over Kafka today.
- `scripts/audit/topic_consumer_truth.py` becomes a CI gate (WS-3 deliverable). Future drift — adding a producer without a consumer, or claiming a consumer that doesn't exist — fails the build.
- The HTTP-A2A path gets named as the supported one, which makes it easier to argue for resilience hardening there (timeouts, breakers, retries) rather than spreading effort across two parallel mechanisms.
- The digital twin's parallel `synapse.<agent>.state` topics are now surfaced as a *separate* gap (`non_registered_consumed_topics`) instead of hidden.

### Negative
- Reduces apparent architectural ambition. The repo no longer claims an event-driven mesh; it claims a synchronous-RPC mesh with event-sourced audit, which is less fashionable but verifiably true.
- Any future move to event-driven agents requires a deliberate sprint — adding `Consumer.subscribe(...)` per agent, wiring lifespans, handling ordering/replay semantics. The plan calls this out (`consumes_planned`) so the work is not lost.

### Neutral
- ADR-029 still stands: `synapse.orders.demand` is the only registry change outside the 1–16 freeze. The orders ingress now flows through the outbox (WS-2) and the publication is consumed by `audit_logger` immediately; agent consumption remains `consumers_planned`.

## Alternatives considered

**A. Build out Kafka consumers in every agent to match the declared topology.**
Honest, ambitious, expensive. Would require a Sprint 11+-sized investment in consumer lifecycle, partition-rebalance handling, idempotent processing, and back-pressure. We are not paying that cost in this sprint; we may, deliberately, later.

**B. Leave the docs alone and add a tiny disclaimer.**
Rejected. The disclaimer would itself drift. Mechanical truth (CI-enforced) is the only honest option.

**C. Delete the `consumes_planned` field — only document what exists.**
Rejected. The design intent is real and useful for sequencing. We separate intent from reality rather than erasing intent.

## Verification

- `scripts/audit/topic_consumer_truth.py` walks every topic in `topics.json`, greps for `subscribe("<topic>")` or its equivalent under `agents/`, `orchestrator/`, `digital_twin/`, and asserts the empirical consumer set matches the `consumers` array.
- `scripts/audit/verify_claims.py` adds a `C_TOPIC_TRUTH` check that invokes the above and includes the result in the headline summary.
- CI gate: `.github/workflows/policy.yml` runs `python -m scripts.audit.topic_consumer_truth` on every PR.

## Migration

- All 8 `agent_card.json` files updated: `consumes` → `[]`; `consumes_planned` ← old `consumes`; `topology_note` added.
- `topics.json` v1.1.0 → v1.2.0: `key_consumers` renamed to `consumers`; `consumers_planned` added; `categories` block added; `non_registered_consumed_topics` documents the digital-twin parallel scheme.
- `CLAUDE.md` "Architecture Rules" I-9 clarified to state Kafka's scope explicitly.
- This file (`ADR-038`).
