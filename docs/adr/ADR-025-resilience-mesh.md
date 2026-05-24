# ADR-025: Resilience Mesh

## Status
Accepted (Sprint 7, 2026-05-17)

## Context

Three confirmed code paths in Sprint 5 could stall the orchestrator on a
single slow dependency:

1. `requests.post()` and `psycopg2.connect()` called inside `async def`
   handlers (`api/routers/decisions.py`) — blocks the event loop.
2. `packages/synapse_common/a2a_sdk.py` ships hardcoded `timeout=5.0`,
   no traceparent, no retry, no circuit breaker.
3. Every external call site opens its own `httpx.AsyncClient` per
   request — no shared connection pool, no bulkhead between deps.

The Tier-1 <100 ms SLO (I-10) is unachievable while a single Ollama
hang or Neo4j flap fans out into the whole orchestrator.

## Decision

Introduce the **inner resilience ring** at the Python layer:

- **Native asyncio circuit breakers** in
  `packages/synapse_common/breakers.py`, keyed by name, with
  Prometheus gauge `synapse_breaker_state{name}` (0=closed,
  1=half_open, 2=open). Wrap Ollama, Neo4j, Pinecone, Feast, audit
  Postgres, and Kafka producer calls.
- **Per-dependency `httpx.AsyncClient` bulkheads** in
  `packages/synapse_common/clients.py`. Each profile pins
  `max_connections` so Pinecone slowness cannot starve Ollama of
  connections.
- **Tier-aware A2A timeouts** in `packages/synapse_common/a2a_sdk.py`:
  T1=2 s, T2=10 s, T3=30 s, T4=120 s. Full-Jitter retry on
  `httpx.TransportError` only — never on 4xx.
- **Graceful shutdown** via
  `packages/synapse_common/lifespan.py:graceful_shutdown(...)`.
  SIGTERM → readiness=false → up-to-25 s in-flight drain → run hooks
  LIFO.

Linkerd / KEDA / Flagger remain the **outer ring** scheduled for
Sprint 9 (WS-10). The two rings compose: Linkerd handles connection-
level faults; the inner ring expresses semantic policy
(tier-aware timeouts, brownout, retry-on-transport-error-only).

## Consequences

**Easier:**
- Tier-1 budget enforcement: a stuck Ollama opens the breaker in <30 s.
- Brownout (ADR-028) can read breaker state directly.
- Replay (ADR-026 sibling) sees consistent failure modes — open
  breaker = "didn't even try" not "hung forever".

**Harder:**
- Every external call site must now use the named bulkhead. A
  CI grep test (`tests/contracts/test_async_hygiene.py`) catches bare
  `httpx.AsyncClient()` constructions and direct `psycopg2` /
  `requests` calls inside `async def`.

## Alternatives Rejected

1. **`aiobreaker` (MIT)** — works but adds a transitive dep that we'd
   have to wrap anyway for Prometheus integration. The native
   implementation is ~150 lines and fully under our control.
2. **Only Linkerd retries/breakers** — would be cleaner if every dep
   were HTTP, but Kafka producers and Postgres connections are not
   HTTP; we need an in-process policy seam.
