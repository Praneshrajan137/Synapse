# ADR-022: Tool Masking via Logit Constraints

## Status
Accepted

## Context
SYNAPSE has 4 decision tiers, each with a different valid tool set. The naive approach — re-emit a different tool definition block per tier — invalidates the KV-cache (ADR-021, I-13) on every tier transition, costing 5-10× latency. Maintaining separate Ollama sessions per tier multiplies memory pressure. Free-text tool selection allows the model to invent invalid tool names. We need per-tier tool restriction without modifying the system prompt.

## Decision
**ALL tools are defined in the system prompt permanently** with a tier-prefixed naming convention:

| Tool Group | Prefix | Available Tiers | Examples |
|-----------|--------|-----------------|----------|
| RL Policy | `rl_` | 1, 2, 3, 4 | `rl_demand_forecast`, `rl_route_optimize` |
| Feature Retrieval | `feast_` | 1, 2, 3, 4 | `feast_get_features`, `feast_get_entity` |
| Graph Query | `graph_` | 2, 3, 4 | `graph_query_supply_network` |
| LLM Reasoning | `llm_` | 3, 4 | `llm_analyze_conflict` |
| Twin Simulation | `twin_` | 4 | `twin_monte_carlo`, `twin_what_if` |
| Playbook Retrieval | `playbook_` | 3, 4 | `playbook_search`, `playbook_retrieve` |

Tier restriction is enforced via **response prefill** (Ollama `prefill` parameter) constraining the JSON tool-call output. For Tier 1-2: `prefill='{"name": "rl_'` forces an immediate RL tool call. For Tier 3-4: no prefill — the model selects freely from all visible prefixes.

The system prompt remains byte-identical across all tier transitions, preserving KV-cache.

## Consequences
- KV-cache hit rate is preserved across all tier transitions.
- Tool-set restrictions are mechanically enforced at decode time, not via prompt instructions the model could ignore.
- Adding a new tool group requires only a new prefix and tier mapping update.
- The system prompt is large (~3K tokens for all 6 groups), but loaded once.

## Alternatives Rejected
- **Dynamic tool removal per tier**: rejected — invalidates KV-cache.
- **Separate Ollama sessions per tier**: rejected — quadruples memory.
- **Free-text tool selection**: rejected — invalid tool names possible.
