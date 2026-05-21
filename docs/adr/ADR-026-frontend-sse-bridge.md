# ADR-026: Frontend SSE bridge for Kafka tails

## Status
Accepted (S1 backend gap-closer; ratified at S6)

## Context
The Atlas Console (ADR-025) needs a real-time event surface across nine
user-visible Kafka topics (`synapse.demand.forecast`,
`synapse.routing.plan`, `synapse.inventory.reorder`,
`synapse.orchestrator.escalation`, `synapse.disruption.alert`,
`synapse.pricing.update`, `synapse.freshness.alert`,
`synapse.orchestrator.decision`, `synapse.audit.log`,
`synapse.metrics.agent`).

Two transports were considered: WebSocket (existing
`/ws/escalation` channel) and Server-Sent Events.

## Decision

**Server-Sent Events** for every Kafka topic tail; WebSocket reserved
for the bidirectional HITL escalation channel only.

Concrete shape:

- Backend bridge: `api/routers/sse.py` exposes
  `GET /api/v1/stream/{topic}` (text/event-stream, allow-listed
  against `infrastructure/kafka/topics.json`,
  consumer-group-per-connection, 15 s heartbeats).
- Frontend hook: `src/shared/realtime/use-sse.ts` (Zod-validated,
  bounded ring-buffer, `Last-Event-ID` resume, full-jitter back-off).
- nginx: dedicated `/api/v1/stream/` `location` with
  `proxy_buffering off`, `chunked_transfer_encoding on`, 24 h read
  timeout (`infrastructure/nginx/nginx.conf`).

## Consequences

### Positive
- One-way cost: HTTP/2 multiplexes through the existing nginx fleet.
- Reconnection is part of the spec (`Last-Event-ID`); no bespoke
  reconnect protocol per surface.
- Survives corporate proxies that strip WebSocket Upgrade headers.
- Each tab gets its own consumer group → a stuck tab can't stall the
  rest, and offsets are independent.
- Auth: the BFF cookie travels with the EventSource without any extra
  client code (`withCredentials: true`).

### Negative
- One TCP connection per topic per tab. The Living City surface
  subscribes to nine, so a single tab opens nine connections. We
  accept this because (a) HTTP/2 multiplexes them onto one TCP, and
  (b) nginx idle keep-alive eats the cost.
- Browser per-origin connection limits exist, but only on HTTP/1.1.
  Production deploys behind HTTP/2 (nginx 1.27 default).

## Alternatives Rejected
- **WebSocket for everything** — bidirectional cost we don't need;
  fragile through corporate WS-stripping proxies.
- **Long-poll** — strictly worse than SSE on every metric.
- **Push-from-server-via-fetch-stream** — non-standard; ecosystem
  tooling (axe, MSW, EventSource resume) all favours SSE.

## References
- Plan §11 / B1 (gap-closer).
- ADR-006 (Kafka topology); ADR-025 (frontend elevation).
