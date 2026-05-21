# ADR-029: Idempotency-Key on decision and order endpoints

## Status
Accepted (Sprint 7)

## Context
Quick-commerce traffic retries aggressively — mobile networks drop, the
app retries. Without idempotency, a single user tap could land as two
orders, two pricing decisions, two consensus runs. The `Idempotency-Key`
header is the de-facto standard (Stripe, Square) and was missing on
`/api/v1/orders` and `/api/v1/decisions`.

## Decision
A Redis-backed `IdempotencyMiddleware` (`synapse_common.idempotency`)
intercepts every mutating verb (POST/PUT/PATCH/DELETE) that carries an
`Idempotency-Key` header:

- First request: handler runs; response cached at
  `idem:{tenant}:{key}` with 24 h TTL holding the response status, body,
  and a SHA-256 of the request body.
- Replay with the *same* body: cached response returned with
  `X-Idempotent-Replay: true`.
- Replay with a *different* body but the same key: HTTP 422, error code
  `idempotency_key_conflict`. Surfaces races; never silently overwrites.

Mutating verbs without an `Idempotency-Key` and read-only verbs are passed
through. Redis outage → degrade open with structured WARN log (I-7);
critical decisions never block on the cache.

## Consequences
- Mobile retries are safe.
- A second tier of replay protection sits behind the orchestrator's
  decision_id uniqueness constraint.
- TTL = 24 h matches the typical user behaviour window.
- Adds ~3 Redis ops per keyed mutation; sub-millisecond.

## Alternatives Rejected
- **Database UNIQUE constraint on a key column** — couples idempotency to
  the schema of every mutating endpoint. Middleware is uniform.
- **In-process LRU cache** — fails the moment we scale to N FastAPI
  workers. Redis is already in the stack.
- **Outbox pattern** — solves a different problem (exactly-once *publish*),
  not request-deduplication.
