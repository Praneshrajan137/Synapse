# ADR Index (24 decisions)

| ID | Title | One-line summary |
|----|-------|------------------|
| ADR-001 | 8-agent specialization | One agent per bounded context; no monolith |
| ADR-002 | A2A JSON-RPC 2.0 | Inter-agent protocol |
| ADR-003 | CTDE via RLlib | Centralized training, decentralized execution; Apache 2.0 |
| ADR-004 | Neo4j Community for knowledge graph | Free; migrate to Aura in cloud |
| ADR-005 | Kafka 16 pre-provisioned topics | No auto-create; frozen after Sprint 1 |
| ADR-006 | Redis dual-purpose (cache + Feast online) | DB 0 = Bengaluru, DB 1 = Mumbai |
| ADR-007 | LangGraph StateGraph for orchestration | 5-phase consensus with Postgres checkpoints |
| ADR-008 | Containerization tiering | Compose (dev) / K3s (prod) / Oracle (free) |
| ADR-009 | MAPIE conformal + Pyro Bayesian | Demand intervals + lead-time posteriors |
| ADR-010 | EconML Double ML | Causal price elasticity |
| ADR-011 | Flower FedAvg | Federated Inventory Sentinel L2 (DPDPA) |
| ADR-012 | React 18 + Deck.gl + MapLibre GL | No Mapbox cost |
| ADR-013 | Protobuf inside JSON-RPC envelope | KV-cache-friendly determinism |
| ADR-014 | Ollama on-device LLMs | phi3:mini + deepseek-r1:14b |
| ADR-015 | 7-layer testing topology | Invariant-blocking merge rule |
| ADR-016 | Full Jitter retry | `synapse_common.retry.retry_with_jitter` |
| ADR-017 | 4-tier rate limiting (Stripe model) | Request rate → concurrency → fleet → worker |
| ADR-018 | Pinecone Starter semantic cache | 2 indexes; ChromaDB fallback |
| ADR-019 | DragonflyDB evaluation criteria | 30% latency drop + license + ARM64 |
| ADR-020 | Ralph loop automation | Bash loop + Claude Code CLI; one invariant per iteration |
| ADR-021 | KV-cache optimization | Stable prefix + append-only + deterministic serialization |
| ADR-022 | Tool masking via logit constraints | Tier-prefixed tool names + Ollama prefill |
| ADR-023 | Error retention in runtime context | Append-only; failed proposals kept with status |
| ADR-024 | Structured recitation for long-horizon tasks | `recite_objective()` every 10 tool calls |

## How to use
- Always cite the ADR ID when making a design claim.
- When proposing a change that contradicts an ADR, create a superseding ADR;
  do not silently break the prior decision.
