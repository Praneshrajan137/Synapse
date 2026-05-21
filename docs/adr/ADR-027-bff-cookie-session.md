# ADR-027: Backend-for-Frontend cookie session

## Status
Accepted (S1 backend gap-closer; ratified at S6)

## Context
The Atlas Console SPA must authenticate against the orchestrator. We
considered three patterns:

1. **JWT in memory + refresh token in HttpOnly cookie** (the modern
   "tokens in JS" pattern).
2. **Backend-for-Frontend (BFF)** — opaque session cookie, JWT held
   server-side in Redis, exchanged for the upstream service.
3. **Direct OIDC against the gateway**, no SPA-side state.

## Decision

**BFF cookie session.**

Concrete shape:

- `api/routers/auth.py` mints an RS256 JWT (`python-jose`), stashes it
  under an opaque session id in Redis db=2, and returns
  `Set-Cookie: synapse_session=<sid>; HttpOnly; Secure; SameSite=Strict`.
- `api/middleware/session.py` resolves the cookie on every request,
  hydrates `request.state.session`, and gates protected paths.
- A double-submit `X-CSRF` token returned at login is required on
  POST/PUT/PATCH/DELETE (`SessionMiddleware`).
- Reauth (`POST /auth/reauth`) opens a short-lived
  `elevated_until` window — used by the Audit Vault PII reveal.
- nginx forwards `Set-Cookie` and the `X-CSRF` request header
  (`infrastructure/nginx/nginx.conf`).

## Consequences

### Positive
- **No XSS-token-theft surface**. A compromised script literally
  cannot read the session id (HttpOnly) and cannot read the JWT
  (server-side only).
- **CSRF**: `SameSite=Strict` blocks cross-site cookie use; the
  double-submit `X-CSRF` is belt-and-braces.
- **Page refresh keeps you logged in** (cookie persists; SPA does not
  rehydrate from `localStorage`).
- **Single auth-event log point** (DPDPA / I-11) — every login,
  refresh, logout, and reauth is a structured-log line in the gateway.
- **Reauth-as-elevation** maps cleanly onto the Audit Vault PII
  workflow without additional plumbing.

### Negative
- A revoked session needs a Redis lookup on every request (mitigated
  by `Redis db=2` being a single-purpose hot key per request).
- The gateway becomes stateful on auth. We accept this because Redis
  was already a hard dependency for KV-cache + session in the
  orchestrator (ADR-018).

## Alternatives Rejected
- **JWT in memory + refresh in cookie**: an XSS becomes a session
  hijack. The Atlas Console renders LLM reasoning chains; we want
  zero token-theft surface.
- **OIDC direct from SPA**: redirect chains break the keyboard-first
  Mission Control flow; refresh storms during shift handoffs.

## References
- Plan §6.4 / §11 (gap B3).
- ADR-018 (Redis usage); ADR-025 (frontend elevation).
- I-11 (DPDPA at-store residency).
