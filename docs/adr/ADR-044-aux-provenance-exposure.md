# ADR-044: AUX Truth Exposure — Structured Provenance, Decision Anatomy, and Degradation Posture

**Status**: Accepted
**Date**: 2026-06-10
**Sprint**: 15 (Living Interface)
**Relates to**: ADR-040 (honest provenance), ADR-033 (audit chain), ADR-038 (Kafka topology truth), ADR-029 (orders ingress), I-3, I-4, I-5, I-7, I-14

## Context

The backend produces rich agent-intelligence signals that never reach the
operator's eyes:

- The `Provenance` value object (ADR-040: `model_version`, `feature_source`,
  `degraded`, `confidence_basis`) was serialized into free-form
  `justification_trace` strings via `trace_line()`. The orchestrator's
  `_record_input_provenance` read a `payload["provenance"]` dict that **no
  agent ever wrote** — `degraded_agents` was always empty. The honesty
  channel existed on paper and was silent in practice.
- `audit_consensus` columns `debate_rounds`, `pareto_front`,
  `execution_confirmations`, `context_messages`, `outcome`, `prev_hash`,
  `current_hash` were written on every decision and exposed by **no**
  endpoint.
- Brownout level (`BrownoutController`) and circuit-breaker states were
  Prometheus-only. The system could shed Tier-4 work with nothing in the
  UI saying so. Worse, no `BrownoutController` was ever **registered** at
  orchestrator startup, so the E-S9-04 no-op path was permanent.
- HITL escalations published to `synapse.orchestrator.escalation` but the
  `/ws/firehose` multiplexer did not subscribe — the cockpit had to poll.
- Synthetic traffic (Sprint 14 traffic-generator) was distinguishable only
  by an implicit `order_id` prefix convention no consumer formally owned.

## Decisions

### D1 — Extend existing decision endpoints additively; no new "full detail" endpoint

`GET /api/v1/decisions/{id}` already reads the `audit_consensus` row; the
missing data is on the same row. New response keys are additive (old
clients unaffected; FE Zod schemas mark them `.optional()`):

- `/{id}`: `debate_rounds`, `pareto_front`, `execution_confirmations`,
  `context_messages`, `outcome`, `prev_hash`, `current_hash`, plus computed
  `chain_verified` (tri-state: `true` = single-row hash recompute matches,
  `false` = content altered since insert, `null` = pre-Sprint-9 legacy row,
  E-S9-01), `degraded`, `is_synthetic`.
- `/recent`: computed `degraded` and `is_synthetic` (SQL-side
  `jsonb_path_exists`, PG12+; the row-heavy JSONB never leaves the DB).

### D2 — Structured provenance rides INSIDE each proposal

`AgentProposal.provenance: Provenance | None = None` (typed, optional,
frozen). All 8 agent A2A handlers attach `pipeline.last_provenance`.

**Why inside the proposal and not a new audit column or top-level field:**

- `make_canonical_row` (E-S9-02) hashes at insert time over **exactly what
  is stored**, and `synapse audit verify` recomputes from stored rows. A
  key added inside proposal dicts is therefore self-consistent: new rows
  hash over the provenance they store; legacy rows verify over the
  provenance-free proposals they store. No chain break, no migration,
  `make_canonical_row` untouched.
- `proto/domain/consensus_decision.schema.json` declares proposals items as
  open objects but the top level as `additionalProperties: false` — a
  top-level field would violate I-3; an in-proposal field passes.
- Mixed-version note: an orchestrator running pre-044 `synapse_common`
  rejects proposals carrying the new key (`extra="forbid"`). All services
  deploy as one compose wave from the same image tag (ADR-039), so the
  window is bounded by a single `--force-recreate`; acceptable.

The `trace_line()` string in `justification_trace` stays for human
readability and legacy rows. `_record_input_provenance` now reads the typed
field first (payload-dict fallback retained).

**Implementation note**: the `Provenance` definitions moved from
`synapse_common/provenance.py` into `synapse_common/models.py` (the
proposal needs the type; `provenance.py` imports from `models.py` — the
move keeps the import graph acyclic). `synapse_common.provenance` re-exports
everything; every existing import path works unchanged.

### D3 — Escalation realtime = a firehose channel, zero new topics

`CHANNEL_TOPIC["escalation"] = "synapse.orchestrator.escalation"` (topic
#13, Sprint-1 frozen — this is a consumer addition, not a topic change).
The registry now also records `api_firehose` as a real consumer of all 9
channels it multiplexes, closing a WS-3-era gap where the firehose consumed
8 topics unregistered (`topics.json` v1.3.0; verified by
`topic_consumer_truth.py` against the `AIOKafkaConsumer` call site).

### D4 — Degradation posture is polled, not pushed

- Orchestrator: `GET /api/v1/status/posture` →
  `{"brownout": {city: level}, "breakers": {dep: state}, "degraded": bool}`
  from the brownout registry + `synapse_common.breakers.all_breakers()`.
  Startup now **registers** `BrownoutController`s for both cities (with the
  documented `ollama`/`postgres` breaker names), closing the E-S9-04 no-op.
- Gateway: `GET /api/v1/system/posture` (JWT, VIEWER) proxies it; the FE
  polls ~15s for the DegradedBanner. Pushing would require touching the
  frozen topic set for a signal that changes on the order of seconds.

### D5 — `is_synthetic` derivation has one owner

`synapse_common/synthetic.py` owns the `"synthetic-"` order-id prefix rule
(Sprint 14 traffic generator). The `order_id` reaches a decision only via
the `decision_request` context message (I-14), so detection scans
`context_messages`. Consumers: the audit outbox payload (firehose envelope
now carries `degraded` + `is_synthetic`), the decisions API (SQL jsonpath
with the prefix passed as a variable), and—in the frontend—the
SyntheticBadge.

### D6 — Hash primitives shared via `synapse_common.audit_chain`

The API image ships only `packages/` + `api/` — it cannot import
`orchestrator/`. The pure functions (`GENESIS_HASH`,
`hash_payload_for_row`, `make_canonical_row`, new `verify_row_hash`) moved
to `packages/synapse_common/audit_chain.py`;
`orchestrator/audit/hash_chain.py` re-exports them and remains the
canonical import path for orchestrator code. E-S9-02 (canonical field set
changes only via chain-rewrite migration) applies to the shared
implementation unchanged. The mutation PR-gate keeps its targets; the
shared module is pinned by the byte-level hash tests in
`orchestrator/tests/test_hash_chain.py` (which import through the
re-export) plus new shared-module tests.

## Consequences

- The firehose decision envelope and both decision endpoints now carry the
  honesty fields; the frontend can render degradation, synthetic traffic,
  reasoning depth, and audit integrity without regex-parsing trace strings
  (Phases 3–4 of the Living Interface plan).
- `degraded_agents` in the append-only context is now populated from real
  agent provenance instead of being permanently empty.
- New rows' chain hashes cover the provenance they store; legacy rows
  verify unchanged. `chain_verified` gives per-row integrity in the API;
  the full chain walk remains `synapse audit verify`'s job.
- Posture exposes which dependency is degrading the system, not just that
  "something" is.

## Alternatives rejected

- **New `/full-detail` endpoint** — duplicates JWT/DSN/error plumbing and
  the FE client for zero contract benefit; the data is on the same row.
- **New `provenance` audit column** — requires a migration and a second
  source of truth; the proposal already travels through consensus → audit
  → API as one object.
- **Posture over Kafka/WS push** — frozen topic set; a 15s poll against an
  in-process read is the honest cost/benefit.
- **Parsing `trace_line()` strings in the API** — regex-scraping a
  human-readable string as a machine contract; exactly the fragility
  ADR-040 warned against.
