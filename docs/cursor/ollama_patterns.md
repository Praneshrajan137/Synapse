# SYNAPSE Ollama Patterns Reference

## KV-Cache Preservation (I-13, ADR-021)
Three rules that MUST be followed to maintain cache hit rate >70%:

1. STABLE PREFIX: System prompt is byte-identical across invocations.
   - Store as frozen string constant loaded once at startup.
   - NEVER put timestamps or dynamic data in the system prompt.
   - Dynamic data goes AFTER the system prompt in user messages.

2. APPEND-ONLY MESSAGES: During consensus phases 1-5, context.messages
   only grows. Revisions append new messages referencing prior by ID.
   Failed proposals remain with status='rejected'.

3. DETERMINISTIC SERIALIZATION: All JSON uses sort_keys=True, separators=(',',':').
   This ensures identical byte sequences for identical data.

## Tier Routing
- Tier 1 (<100ms): RL policy only. No LLM. ~80% of decisions.
- Tier 2 (<500ms): RL + Feast features + Phi-3/Qwen2.5 (lightweight).
- Tier 3 (2-15s): Full reasoning via DeepSeek-R1 14B.
- Tier 4 (15-120s): Monte Carlo planning via Llama 3.3 70B Q4.

## Tool Masking (ADR-022)
ALL tools defined in system prompt permanently. Availability per tier:
- rl_*, feast_*: Tiers 1-4
- graph_*: Tiers 2-4
- llm_*, playbook_*: Tiers 3-4
- twin_*: Tier 4 only

For Tier 1-2: response prefill forces RL tool call.
For Tier 3-4: no prefill — model selects freely.

## Memory Management
- Ollama auto-unloads after 5 minutes of inactivity.
- Pre-warm models when Tier Router detects escalation probability >0.3.
- On 16GB: swap models. On 32GB+: keep Phi-3 + DeepSeek-R1 resident.
- 70B model: 64GB+ RAM or Oracle Cloud only.

## Required Models (Sprint 1)
- phi3:mini (Tier 2, ~2.3GB) — REQUIRED
- qwen2.5:7b (Tier 2, ~4.4GB) — REQUIRED

## Optional Models (Sprint 2+)
- deepseek-r1:14b (Tier 3, ~8.8GB) — Sprint 2
- llama3.3:70b-instruct-q4_K_M (Tier 4, ~40GB) — Sprint 4
