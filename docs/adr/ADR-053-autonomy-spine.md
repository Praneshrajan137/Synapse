# ADR-053: The Autonomy Spine — surfacing the closed loop to the operator

## Status
Accepted

## Context
ADR-052 (C57) closed the perceive→decide→act→learn loop in the backend: a per-city
`WorldRuntime` runs on its own clock, the orchestrator `SensorLoop` convenes consensus
**with no human trigger and no demo ticker**, agents actuate the world for real, and
meta-RL learns from the realized world. The operator console, however, was authored
against the *previous* mental model — "operator injects order → consensus → supervise"
— and surfaces **none** of the new autonomy. Two concrete, load-bearing gaps:

1. **Decision origin is not typed.** The `SensorLoop` mints `order_id="auto-<city>-<trigger>-<seq>"`
   for its self-initiated decisions (`orchestrator/sensor/loop.py`). These are real,
   autonomous decisions — `is_synthetic=false` — but the only origin field exposed was
   the binary `is_synthetic` (ADR-044, which owns only the `synthetic-` prefix). So the
   frontend could distinguish demo-vs-real, but **not operator-vs-autonomous**, and would
   have had to regex an `order_id` it never receives cleanly — exactly the anti-pattern
   ADR-044 eliminated for `synthetic-`. The single most important truth of the new system
   ("a decision just happened with no human and no ticker") was invisible.

2. **The world and sensor have no gateway contract.** Live `world_state` lived only on the
   twin (A2A `world_state` + REST `GET /world/state`); sensor liveness was only a
   `sensor_loop="running"|"stopped"` string in the orchestrator `/health`. The browser
   reaches only the JWT/CORS/rate-limited gateway, so neither was surfaceable without
   either a gateway seam or bypassing the gateway front door.

A third, adjacent gap surfaced during the work: the `metric` firehose channel (topic 17
`synapse.metrics.agent`) was registered with `api_firehose` as a consumer since ADR-044
but had **no producer anywhere in the codebase** — a registered-but-dead channel. Typing
it on the frontend and reading it would have rendered nothing (the dead-channel defect
class the repo fights), so "wire the metric channel" honestly requires *producing* it
first.

## Decision
A **minimal, additive, governed gateway seam** makes the loop observable, plus a real
producer for the metric channel. No frozen contract changes; every field is additive.

**D1 — One source of truth for the three-way origin.** `packages/synapse_common/synthetic.py`
gains `AUTONOMOUS_ORDER_PREFIX = "auto-"`, `is_autonomous_order_id`, and a total,
disjoint classifier `initiator_of_order_id` / `initiator_of_decision` returning
`DecisionInitiator = Literal["autonomous", "synthetic", "operator"]`. `operator` is the
default — a missing/malformed tag is a real human decision, never hidden as synthetic nor
over-claimed as autonomous. `is_synthetic_*` is unchanged (an autonomous decision stays
`is_synthetic=false`).

**D2 — `initiator` carried additively.** The decisions API (`/recent` via a second
`jsonb_path_exists`, `/{decision_id}` via `initiator_of_decision`) and the firehose
decision envelope (`orchestrator/audit/logger.py`) emit `initiator`. The canonical hashed
audit row is untouched (the field is computed at the read/publish boundary, not stored),
so the tamper-evidence chain is byte-stable.

**D3 — `GET /api/v1/system/autonomy` (VIEWER).** A gateway proxy (`api/routers/system.py`,
pattern-matched to `system_posture`) joins the twin's per-city `world_state` with the
orchestrator's new `GET /api/v1/status/autonomy` (`SensorLoop.status()`: running + polls +
`decisions_triggered`) server-side. Honest degradation (I-7): an unreachable part →
`null` + `degraded=true`; a stalled sim clock (`clock_advancing=false`) reads degraded;
only a *total* blackout is a 503, so the FE can tell "partly degraded" from "blind".

**D4 — A real producer for the metric channel.**
`orchestrator/consensus/firehose_signals.emit_agent_metrics` event-sources one telemetry
event per proposal onto `synapse.metrics.agent` as consensus collects proposals (mirroring
`emit_agent_signals`, best-effort, I-7). The payload is genuine measured data (agent,
decision, tier, confidence, degraded, confidence_basis, ts) matching the new
`proto/domain/agent_metric.schema.json`. `proto/domain/world_state.schema.json` closes the
I-3 gap for `WorldState`.

**D5 — Mechanical gates.** `verify_claims.py::check_initiator_truth` (**C58**) imports the
classifier and asserts an `auto-` id is `autonomous`, never `synthetic`, plus the wiring in
the API + logger. `check_autonomy_visibility` (**C59**) asserts the gateway proxy, the
orchestrator status endpoint, the metric producer, and both proto schemas exist.

## Consequences
- The operator can, for the first time, see the system act on its own: live world vitals
  (perceive), a typed `initiator` badge distinguishing autonomous from operator and demo
  (decide), self-initiation counters, and the metric channel is live end-to-end.
- The `metric` firehose channel is no longer dead; the KPI band can prefer real
  server-aggregated reads (this endpoint / SLO) over buffer-window proxies.
- Everything is additive: no frozen Kafka topic changed, no hashed audit row changed, and
  the browser still speaks only to the JWT/CORS/rate-limited gateway.
- Honesty is preserved by construction: the sim world is always labeled `is_synthetic`, a
  stalled clock reads degraded, autonomous is never mislabeled synthetic, and metric KPIs
  are only claimed authoritative where a real source exists.

## Alternatives Rejected
- **Frontend-only (call the twin directly + regex the order_id).** Faster, but re-introduces
  the exact prefix-matching anti-pattern ADR-044 removed and bypasses the gateway front
  door (JWT/CORS/rate-limit) that every other browser call respects. Rejected.
- **Type the `metric` channel and just read it.** It has no producer — the channel would
  render nothing (the Sprint-15 dead-channel defect class). Rejected in favour of producing
  it first, schema-first.
- **Push `world_state` on a new Kafka topic.** The inter-agent topic set is frozen; world
  state changes on the order of seconds and a ~10-15s poll against an in-process snapshot is
  honest engineering (same reasoning as ADR-044 D4's posture poll). Rejected.

## Ratchet / deferred
- The KPI band's rebuild onto the real metric channel + `getAutonomy` counts (frontend
  workstream) lands with the frontend surfaces; until then it stays honestly labeled as a
  live window.
- Only the inventory-reorder slice emits `auto-` decisions today (ADR-052 P3/P4 ratchet);
  the FE renders every future autonomous decision the moment it carries `initiator=autonomous`.
