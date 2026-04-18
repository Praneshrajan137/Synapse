# ADR-021: KV-Cache Optimization Strategy

## Status
Accepted

## Context
KV-cache hit rate is the single most important metric for AI agent system latency. Cache misses force full prefill computation, directly determining whether Tier 2 decisions hit the < 500 ms SLA. Three common practices invalidate the cache: timestamps in system prompts, non-deterministic JSON serialization, and dynamic tool definition changes between tiers. Production deployments by Manus AI and Anthropic show 5-10× latency degradation when KV-cache hit rate drops below 70%.

## Decision
Three-layer KV-cache preservation protocol enforced across all Orchestrator–Ollama interactions:

1. **Stable Prefix** (`orchestrator/llm/context_builder.py`): system prompt is a frozen byte-identical string constant loaded once at startup. Timestamps and dynamic data placed AFTER the system prompt. Unit test: SHA-256 of system prompt across 1000 invocations is identical.

2. **Append-Only Messages** (`orchestrator/consensus/protocol.py`): `context.messages` list is append-only during Phases 1-5. Revisions append new messages referencing prior proposals by ID. Failed proposals remain with `status: 'rejected'`. Enforced by `deal` postcondition `len(new.messages) >= len(old.messages)` (I-14).

3. **Deterministic Serialization** (`packages/synapse_common/a2a_sdk.py`): all JSON uses `json.dumps(obj, sort_keys=True, separators=(',',':'))`. Protobuf payloads (ADR-013) are inherently deterministic. Hypothesis property test: `serialize → deserialize → re-serialize` produces identical bytes.

Prometheus metrics: `synapse_ollama_cache_hit_rate` (Gauge by model/tier), `synapse_ollama_prefill_tokens` (Histogram with buckets 100, 500, 1K, 2K, 5K, 10K, 20K, 50K). Alert `OllamaCacheHitRateLow` fires when Tier 2 cache hit rate drops below 70% for 5 minutes.

## Consequences
- Tier 2 decisions consistently hit the < 500 ms SLA in production.
- Pre-commit hook `kv-cache-check` greps for f-strings, `.format()`, `time.time()` in cache-sensitive files.
- Adds a structural constraint on context construction; new contributors must understand the protocol.
- Prometheus alert provides early warning of regressions.

## Alternatives Rejected
- **Accept cache misses**: rejected — 5-10× latency cost destroys Tier 2 SLA.
- **Custom Ollama fork with persistent KV state**: rejected — high maintenance burden.
- **Reduce to single tier (no LLM)**: rejected — defeats the architecture.
