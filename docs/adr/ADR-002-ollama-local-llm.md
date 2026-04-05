# ADR-002: Ollama for Local LLM Inference

## Status
Accepted

## Context
SYNAPSE requires LLM reasoning for Tier 3-4 decisions but has a zero-cost constraint (I-1).

## Decision
Use Ollama for all LLM inference. Required models: phi3:mini (Tier 2), qwen2.5:7b (Tier 2), deepseek-r1:14b (Tier 3), llama3.3:70b-instruct-q4_K_M (Tier 4). KV-cache preservation (I-13) via stable prefixes, append-only context, deterministic serialization.

## Consequences
- Zero API cost for LLM inference
- Hardware-dependent: 16GB minimum for Tier 2, 64GB+ for Tier 4
- KV-cache hit rate must be monitored (>70% target)

## Alternatives Rejected
- OpenAI/Anthropic APIs: violates I-1 (zero cost)
- vLLM: more complex deployment, less developer-friendly for local use
