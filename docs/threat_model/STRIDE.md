# SYNAPSE Threat Model — STRIDE per Agent

This document applies the STRIDE framework (Spoofing, Tampering, Repudiation,
Information disclosure, Denial of service, Elevation of privilege) to every
SYNAPSE component. It is the authoritative threat-model reference for security
review and the basis for the controls enforced in CI/CD.

## Trust boundaries

| Boundary | Inside (trusted) | Outside (untrusted) | Crossing protected by |
|---------|------------------|---------------------|------------------------|
| Internet → API Gateway | Agents, Orchestrator, Twin, Data Fabric | All external clients | nginx + JWT (RS256) + rate limiting (ADR-017) |
| API Gateway → Orchestrator | Orchestrator FSM | Gateway request workers | mTLS in production; Vault-issued service tokens |
| Orchestrator → Agent | Agent process | Orchestrator | A2A JSON-RPC + JWT scope claim per agent |
| Agent → Tool (MCP) | Tool (Feast, Neo4j, OSRM) | Agent process | Tool-specific creds from Vault KV v2 |
| Operator → Vault | Vault server | Operator workstation | OIDC + transit engine for sensitive ops |

## STRIDE per component

### API Gateway (`api/`)
| Threat | Vector | Control |
|--------|--------|---------|
| **S**poofing | Replayed JWTs, forged client identity | RS256 JWT, jti claim with Redis nonce cache, 5-minute clock skew window |
| **T**ampering | Body modification in transit | TLS 1.3 termination at nginx; HSTS preload; integrity hash on Celery task payloads |
| **R**epudiation | "I never placed that order" | Audit log row per request with JWT subject, IP, body hash; immutable per I-4 |
| **I**nfo disclosure | Verbose 500 leaks stack traces | Custom exception handler returns generic JSON; structlog redacts via `processor=hide_sensitive` |
| **D**oS | Bulk-order endpoint flood (scenario `kafka_backpressure`) | Per-IP token bucket (10 r/s default, 100 r/s for HITL ops); Celery queue depth alerts |
| **E**levation | Tier escalation via crafted `decision_type` | Pydantic validation + scope claim check before forwarding to Orchestrator |

### Orchestrator
| Threat | Vector | Control |
|--------|--------|---------|
| **S**poofing | Forged `agent_id` in A2A response | A2A SDK verifies sender JWT signature; rejects unsigned proposals |
| **T**ampering | KV-cache poisoning via system prompt mutation | I-13 enforced: stable-prefix check in `context_builder.py`; `kv-cache-check` pre-commit hook (Phase 2) blocks f-strings |
| **R**epudiation | Operator denies override | HITL writes operator identity (Vault token) to `audit_decisions.operator` |
| **I**nfo disclosure | Decision context leaked via tracing | LangSmith sampling capped at 10 % for Tier-2; Tier-3/4 traces redact PII via `langsmith_client.py` filter |
| **D**oS | Consensus deadlock (5 phases blocked) | Per-phase timeout (Tier-1: 100 ms, Tier-4: 120 s); circuit breaker on agent failure |
| **E**levation | Sub-agent claims orchestrator authority | Bearer scope `agent:write` ≠ `orchestrator:write`; tool router rejects mismatched scopes |

### Agents (8) — generic threats
| Threat | Vector | Control |
|--------|--------|---------|
| **S**poofing | Bypass tier router by direct call | Each agent verifies caller has `orchestrator:write` scope; reject direct external traffic |
| **T**ampering | Adversarial RL input (extreme demand spike) | Pyro Bayesian uncertainty floor; conformal coverage check (MAPIE) gates execution |
| **R**epudiation | "The model never made that prediction" | MLflow run id logged with every prediction; immutable artifact in Postgres |
| **I**nfo disclosure | Federated gradient leakage (Inventory Sentinel) | Flower with secure aggregation; gradient-only serialization (I-11, DPDPA-A) |
| **D**oS | Costly inference (Tier-4) saturating GPU | Ollama queue depth alarm; tier router degrades to Tier-2 when alarm fires |
| **E**levation | Reward hacking → policy gains unintended capability | Independent reward functions (I-2); mutation-test survival < 15 % on rewards |

### Digital Twin (Neo4j + SimPy + Gym)
| Threat | Vector | Control |
|--------|--------|---------|
| **S**poofing | Inject malicious graph node | Neo4j role `synapse_app` has no CREATE on label whitelist outside seed scripts |
| **T**ampering | Mutate edge weights to bias routing | All edges have `created_by` property; ALTER blocked at role level |
| **R**epudiation | Sim run that "never happened" | SimPy run id + seed logged to Kafka topic `synapse.twin.runs` |
| **I**nfo disclosure | Cypher injection via parameter | Always-parameterized queries; `cypher-shell` not permitted in production |
| **D**oS | Pathological shortest-path query (scenario `neo4j_concurrent`) | Query timeout 5 s; Bolt connection pool cap 50 |
| **E**levation | Gym env writes back to production | Twin runs in isolated Neo4j database `twin`; cross-DB writes denied |

### Data Fabric (Kafka, Feast, Postgres, Redis, OSRM, MLflow)
| Threat | Vector | Control |
|--------|--------|---------|
| **S**poofing | Producer claims topic ownership | Kafka ACLs per service principal; topic naming locked in `topics.json` (frozen post-Sprint 1) |
| **T**ampering | Audit row deletion | Postgres `audit_decisions` revokes DELETE/UPDATE from `synapse_app`; only `synapse_erasure` operator role can delete (DPDPA-B) |
| **R**epudiation | "Feature value was different at decision time" | Feast point-in-time correctness; offline+online dual-store (I-3) |
| **I**nfo disclosure | Redis dump leaks secrets | Redis db=0 (Bengaluru) and db=1 (Mumbai) hold features only; secrets in Vault KV |
| **D**oS | Producer floods Kafka, consumer lag explodes | Per-topic quota (200 MB/s); alarm on `synapse_kafka_consumer_lag > 10 000` |
| **E**levation | Service token escalates to admin | Vault policies separate `synapse_app` (KV read) from `synapse_admin` (transit + KV write) |

### UI (React + Celery)
| Threat | Vector | Control |
|--------|--------|---------|
| **S**poofing | Session hijack | HttpOnly + SameSite=Strict cookies; CSRF token on all POSTs |
| **T**ampering | XSS in decision-log render | React JSX auto-escaping; `dangerouslySetInnerHTML` banned (lint rule) |
| **R**epudiation | "I didn't approve that override" | OverrideConsole logs operator + reason + timestamp to `audit_decisions` |
| **I**nfo disclosure | Map tile cache exposes geolocation | deck.gl uses anonymized hex bins for non-operator views |
| **D**oS | WebSocket flood on HITL channel (scenario `hitl_flood`) | Per-session WS limit 5; backpressure via server-side rate limiter |
| **E**levation | Operator role escalates to admin | RBAC enforced server-side in API gateway; UI flags are advisory only |

## Highest residual risks (open)

| Risk | Severity | Mitigation in flight |
|------|----------|----------------------|
| Vault unsealed in dev (file backend) | M | Migrate to Shamir + auto-unseal via OCI Vault for production; runbook in `docs/runbooks/model_rollback.md` |
| LangSmith traces may include PII at Tier-3 | M | Redaction filter in `langsmith_client.py`; quarterly sampling audit |
| OSRM ARM64 image not signed | L | Build in CI with cosign; verify in `cd.yml` |
| Federated client trust assumption (Flower) | L | Add secure aggregation in Sprint 7; current Flower runs on trusted intra-cluster network |

## Process

- This document is reviewed at every sprint exit.
- Any new component added to the system MUST add a STRIDE row before merge
  (enforced by reviewer checklist in `.github/PULL_REQUEST_TEMPLATE.md`).
- New ADRs that introduce trust boundaries reference this file.
