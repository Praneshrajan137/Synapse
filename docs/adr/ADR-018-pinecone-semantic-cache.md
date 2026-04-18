# ADR-018: Pinecone Dual-Use — Playbook Retrieval + Semantic Decision Cache

## Status
Accepted

## Context
The Disruption Shield retrieves response playbooks via vector similarity over historical incidents (768-dim embeddings of incident descriptions). Independently, the Orchestrator benefits from caching prior consensus decisions by semantic key — two near-identical decision requests should reuse a prior LLM-generated reasoning chain (saves Tier 3 latency from 15s to <100ms). Operating two separate vector stores doubles cost and operational surface. Pinecone Starter (free) provides 2 GB / 5 indexes — ample for both use cases.

## Decision
Use **Pinecone Starter** (2 GB, 5 indexes free tier) as the **single semantic cache** with two indexes:
1. `synapse-playbooks` — pre-computed disruption response playbooks (768-dim, ~500 vectors).
2. `synapse-decision-cache` — Orchestrator decision embeddings keyed by consensus prompt hash (768-dim, FIFO eviction at 10K entries).

Implementation:
- `agents/disruption_shield/inference/playbook_retriever.py` queries `synapse-playbooks` (top-3, threshold 0.85).
- `orchestrator/llm/semantic_cache.py` queries `synapse-decision-cache` (top-1, threshold 0.92); cache hit short-circuits Phases 2-3.

Fallback: if Pinecone Starter is exhausted or unavailable, both indexes failover to ChromaDB (Apache 2.0, self-hosted, embedded) with no API change.

## Consequences
- Single vector store = single integration point.
- Decision cache hit eliminates Tier 3 LLM calls for repeat scenarios — measurable via `synapse_orchestrator_cache_hit_rate` Prometheus metric.
- Pinecone API key stored in Vault; no $0 violation as long as Starter limits respected.
- Compact playbook corpus (~3 MB) leaves enormous headroom in the 2 GB free tier.

## Alternatives Rejected
- **No caching**: rejected — Tier 3 latency too high without cache.
- **Two separate vector stores**: rejected — duplicate ops surface.
- **In-memory cache only**: rejected — no semantic similarity, only exact-key hits.
