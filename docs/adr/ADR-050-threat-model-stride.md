# ADR-050: Threat Model (STRIDE) for the SYNAPSE Control Plane

## Status
Accepted (2026-06-17) — **living document.** Findings F1–F4 are tracked below;
the Tier-P activation gate (see Consequences) blocks always-on production until
the HIGH/▲ findings are closed. Relates to
[ADR-049](ADR-049-two-tier-cost-model.md) (the tier this protects),
[ADR-036](ADR-036-gcp-single-vm-not-gke.md) (single-VM topology),
[ADR-039](ADR-039-gcp-deploy-pull-from-artifact-registry.md) (supply chain).

## Context

[ADR-049](ADR-049-two-tier-cost-model.md) made production-intent explicit. A real
operation needs a real threat model *before* Tier P is activated — not security
theatre. This ADR is the standing methodology (STRIDE per element across trust
boundaries) and the current findings register, grounded in the **actual** code,
not aspiration.

**Tier context matters for severity.** Tier D (the standing mode — ADR-049) is a
single VM, up ~30 min/week, behind an edge (nginx + IAP on admin/SSH), serving
synthetic data. Tier P is always-on, public-facing, real data. A finding that is
LOW for Tier D can be HIGH for Tier P; severities below are stated **for Tier P**
(the bar we must clear before activation), with the Tier-D mitigation noted.

### Trust boundaries

```
 Internet ─┬─▶ nginx edge (rate-limit $binary_remote_addr, TLS)
           │      └─▶ API gateway  ── JWT RS256, role-gated (VIEWER/OPS), app rate-limit
           │              ├─▶ orchestrator ──(A2A HTTP, internal)──▶ 8 agents / digital-twin
           │              └─▶ data fabric: Postgres · Kafka · Neo4j · Redis (internal net)
           └─▶ /ws/firehose (WebSocket)  ◀── ⚠ see F1
 GitHub Actions (WIF, no SA keys) ─▶ Cosign-signed images ─▶ Artifact Registry ─▶ VM (IAP SSH)
```

Boundaries: (B1) Internet→edge, (B2) edge→API, (B3) API→orchestrator,
(B4) orchestrator→agents/twin (internal A2A), (B5) services→data fabric,
(B6) CI/CD→registry→VM.

## Decision

Adopt **STRIDE** as the standing threat-modelling method, maintain the findings
register below, and **gate Tier-P activation on closing F1–F3.**

### STRIDE register (grounded in current code)

| # | STRIDE | Element | Threat | Existing control | Gap / finding | Sev (Tier P) |
|---|---|---|---|---|---|---|
| 1 | **Spoofing** | API (B2) | Forged caller identity | JWT RS256, role-gated (`api/middleware/jwt.py`); JWKS hook | OK for REST | — |
| 2 | **Spoofing** | Firehose WS (B1/B2) | Anonymous client streams live decision/pricing/twin data | none — `websocket.accept()` with no token (`api/routers/firehose.py`) | **F1** — WS unauthenticated while REST is gated | **▲ HIGH** |
| 3 | **Tampering** | Audit (B5) | Decision-log alteration | Tamper-evident hash-chain (`synapse_common.audit_chain`); append-only `decision_outcomes`; UPDATE-revoked under I-4 | OK | — |
| 4 | **Tampering** | Supply chain (B6) | Malicious image to VM | Cosign keyless sign + verify-on-pull; SBOM diff + CVE budget gates; WIF (no static SA keys) | OK | — |
| 5 | **Tampering** | Ingress (B2) | Malformed order corrupts consensus | Shared-producer + outbox + `proto/domain` schema validation (WS-2); deterministic serialization | Verify field-level bounds on all ingress | ◆ MED |
| 6 | **Repudiation** | Decisions | "I didn't authorize that" | JWT identity + audit hash-chain + `audit_steering`/`audit_escalations` | Bind principal→audit row end-to-end (verify) | ◆ MED |
| 7 | **Info disclosure** | Firehose WS | Bulk exfil of operational signals | (see F1) | **F1** | **▲ HIGH** |
| 8 | **Info disclosure** | Logs/PII | PII leaks to logs/cache | `redact_pii` structlog processor; KV-cache PII guard; DPDPA cascade | OK; re-verify on real data path (Tier P) | ◆ MED |
| 9 | **Info disclosure** | CORS | Hostile origin reads API in a victim's browser | none explicit (same-origin via nginx assumed) | **F2** — no explicit CORS/TrustedHost policy | ◆ MED |
| 10 | **DoS** | API/edge | Request flood | nginx per-IP rate-limit; **app-layer** `RateLimitMiddleware` (`api/middleware/ratelimit.py`) | **F4** — limiter is in-memory per-process (not shared) | ○ LOW |
| 11 | **DoS** | Firehose/Kafka | Slow consumer backs up the loop | PR-5 backpressure (`SEND_TIMEOUT`, bounded poll) | OK | — |
| 12 | **Elevation** | Secrets (B5/B6) | Credential theft → priv-esc | Fail-fast DSN/JWT (no hardcoded creds, C35); IAP (no public SSH); WIF | **F3** — SOPS is a *skeleton*; no real secret store / rotation | ◆ MED |
| 13 | **Elevation** | DB roles | App role over-privileged | Non-superuser app role; erasure uses privileged role only | OK (E-S9-10) | — |

### Prioritised findings

- **F1 ▲ HIGH — Firehose WebSocket is unauthenticated.** `/ws/firehose` streams
  the same `decision`/`pricing`/`twin`/`escalation` data the JWT-gated REST
  endpoints protect, to *any* client that can reach it. *Tier-D mitigant:* the VM
  is mostly off and edge-fronted. *Fix (pre-Tier-P):* require a VIEWER JWT on WS
  connect (query param or `Sec-WebSocket-Protocol`), validated before
  `accept()`; the FE already holds a token (auth-refresh). Needs FE coordination
  → tracked as a follow-up.
- **F2 ◆ MED — No explicit CORS/TrustedHost policy.** Add `CORSMiddleware` with an
  allow-list + `TrustedHostMiddleware` before public exposure.
- **F3 ◆ MED — Secrets are a skeleton.** Complete a real flow (GCP Secret Manager
  + documented rotation) before Tier P; JWT keys must not be ephemeral in prod.
- **F4 ○ LOW — In-memory rate limiter.** Per-process; for Tier-P multi-instance,
  back `RateLimiter` with Redis so limits are global.

### Controls already in place (credited, not re-litigated)

JWT RS256 role-gated REST · app + edge rate limiting · IAP (no public SSH) · WIF
(no SA keys) · Cosign sign + verify-on-pull · SBOM diff + CVE-budget CI gates ·
tamper-evident audit hash-chain · DPDPA cascade + PII redaction · fail-fast
secrets (no hardcoded creds) · `proto/domain` schema validation on ingress + Zod
on the firehose envelope · deterministic serialization (I-13).

## Consequences

- **Tier-P activation gate (binds ADR-049):** always-on production must not be
  activated until **F1, F2, F3** are closed. F4 is a Tier-P scaling item.
- F1/F2 become tracked follow-ups; F1 needs a small FE change (token on WS).
- Nothing here is Tier-D-blocking — the standing demo posture is acceptable
  behind the edge with the VM mostly off.
- This ADR is living: new components add a STRIDE row in the PR that introduces
  them (documentation discipline — a threat worth finding once is worth a row).

## Alternatives considered

- **No formal threat model (rely on ad-hoc review).** Rejected: production-intent
  without a threat model is how the firehose-auth gap (F1) stayed invisible.
- **Full DREAD scoring / attacker personas.** Deferred: STRIDE-per-element with a
  3-tier severity is proportionate for a single-developer, single-region system;
  heavier formalism would be ceremony, not leverage, at this stage.
