# SYNAPSE Atlas Console — Frontend Threat Model

**Status:** S6 baseline · revisit on every ADR-025/026/027/028 amendment.

This document is STRIDE per surface, scoped to the Atlas Console SPA
(`frontend/`) and its trust boundaries with the BFF gateway (`api/`)
and the orchestrator. Sister docs:
[`docs/security/SBOM.md`](./SBOM.md) (build-time supply chain) and
[`docs/runbooks/frontend.md`](../runbooks/frontend.md) (operator
response).

## Trust boundaries

```
┌────────────┐   ┌──────────────┐   ┌───────────────┐   ┌────────────────┐
│  Browser   │──►│  nginx (TLS) │──►│  api gateway   │──►│ orchestrator + │
│  (Atlas)   │◄──│  (CSP / CORS)│◄──│  (BFF, Redis)  │◄──│ Postgres/Kafka │
└────────────┘   └──────────────┘   └───────────────┘   └────────────────┘
       │                                  │                       │
       └── HttpOnly cookie + X-CSRF ──────┘── opaque session id ──┘
```

The browser **never sees a JWT**. nginx terminates TLS and applies
strict CSP + Trusted-Types + Permissions-Policy
(`infrastructure/nginx/nginx.conf`). The gateway is the only
component that touches the JWT, and it holds it server-side keyed by
the opaque `synapse_session` cookie (ADR-027).

## STRIDE per surface

### Mission Control (`/{city}/mission-control`)

| Vector | Threat | Mitigation |
|---|---|---|
| **S — Spoofing** | A non-ops user sends a forged "approve" frame | BFF cookie session; CSRF double-submit; ws subprotocol auth via the same cookie |
| **T — Tampering** | Replay of a stale approval after disconnect | Server-side `decision_id` idempotency + client `client_id` ACK matching (`use-offline-queue`) |
| **R — Repudiation** | Operator denies they approved | Append-only `audit_consensus.human_override`; auth-event log on every reauth |
| **I — Information disclosure** | Sensitive proposals rendered to a wrong tab | SameSite=Strict cookie blocks cross-site embedding; surface lives in `frame-ancestors 'none'` |
| **D — Denial of service** | Flood of escalations OOMs the queue | Bounded ring buffer (200) in `useEscalations` + IDB queue; tier-4 ranker keeps signal first |
| **E — Elevation of privilege** | Tier-4 bypass via UI manipulation | Backend re-validates every action; the SPA is advisory only |

### Decision Trace + Audit Vault

| Vector | Threat | Mitigation |
|---|---|---|
| **S** | Forged `audit_trace.hash` to make a tampered decision look clean | Client-side `verifyChain` (sha256 over canonical body) + AAA banner on break + export gated on validity |
| **T** | Mutated audit row in transit | I-4 append-only Postgres role + `Cache-Control: no-store` on PDF export |
| **R** | "Show PII" without audit | Reauth event is logged; PII window is short-lived; URL-driven state means the action is shareable & loggable |
| **I** | PII leak via debugger / DOM scrape | Default redaction; `?pii=true` requires a fresh `elevated_until` in the session |
| **D** | Large evidence pack denial | nginx 30 s read timeout on `/auth/`, separate timeout on `/api/v1/audit/` |
| **E** | Privilege escalation via reauth | Reauth uses the same password as login + same constant-time bcrypt path; no special "admin" token |

### Living City + Twin Studio + Agent Floor

| Vector | Threat | Mitigation |
|---|---|---|
| **T** | XSS via LLM reasoning content rendered as markdown | DOMPurify under a Trusted-Types policy `atlas-dompurify`; nginx `require-trusted-types-for 'script'` enforces no other writer |
| **I** | Map shows operator location to a peeking screen | Map renders only store + rider positions, no operator GPS; residency chip surfaces data origin |
| **D** | SSE flood crashes the tail | Per-topic bounded buffer + drop-oldest backpressure (`useSse`) |

## Cross-cutting

### XSS / Trusted Types
- Every dynamic HTML write goes through DOMPurify under the
  `atlas-dompurify` policy; nginx rejects all other writers via
  `require-trusted-types-for 'script'`.
- React's default escaping covers the rest. We do not use
  `dangerouslySetInnerHTML` outside the DOMPurify wrapper.

### CSRF
- `SameSite=Strict` cookie + `X-CSRF` double-submit on every mutating
  request (`fetcher.ts`).
- nginx CORS allow-list does NOT include `*`; only the deploy origin.

### Supply chain
- pnpm `--frozen-lockfile`; `lockfile-lint` (HTTPS hosts only); `pnpm
  audit --audit-level=high` blocks the CI build.
- License allow-list (I-1) enforced in CI (`frontend.yml` ·
  `Supply Chain` job).
- CycloneDX SBOM emitted on every build, embedded as image label.

### Prototype pollution
- No deep-merge of untrusted config; only Zod-parsed payloads ever
  hit React state.

### Open redirects
- TanStack Router validates every search-param via Zod; the
  Mission-Control modify form's free-text `reason` is escaped via
  React (no anchor href interpolation).

## Critical files registry

CODEOWNERS protects these paths with design + security review:

- `frontend/src/shared/design-tokens/`
- `frontend/.storybook/test-runner.ts`
- `frontend/src/shared/api/fetcher.ts`
- `frontend/src/shared/canonical-json.ts`
- `frontend/src/shared/hash/sha256.ts`
- `frontend/src/surfaces/$city/decisions/model/audit-hash.ts`
- `frontend/src/surfaces/$city/mission-control/model/ranker.ts`
- `api/routers/auth.py`
- `api/routers/audit.py`
- `api/middleware/session.py`
- `infrastructure/nginx/nginx.conf`
- `packages/openapi/openapi.json`

## Open items
- Plan-agent critique: integrate Socket.dev free-tier in CI for
  every dependency upgrade (ADR-025 mentions this; ship the workflow
  in S6 hardening tail).
- Review CSP `connect-src` quarterly — the OpenFreeMap tile origin is
  the only third-party we allow.
