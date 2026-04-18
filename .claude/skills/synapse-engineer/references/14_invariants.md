# 14 Architectural Invariants

| ID | Name | Enforcement |
|----|------|-------------|
| I-1 | Zero-cost stack (no paid APIs) | `no-paid-apis` pre-commit hook + CI grep |
| I-2 | Independent reward functions per agent | `reward-isolation` pre-commit hook (AST scan) |
| I-3 | All agent outputs validate against `proto/domain/*.schema.json` | `schema-validate` hook + Schemathesis layer |
| I-4 | Audit log immutability (Postgres role permissions) | Role grants in init SQL; chaos test `test_audit_immutability` |
| I-5 | Confidence-gated execution (HITL escalation below threshold) | `orchestrator/hitl/escalation.py` + metric `synapse_hitl_escalation_total` |
| I-6 | Essential SKU price cap <= 1.3x base | `deal.post` in `pricing_oracle/inference/pipeline.py` + compose-file grep |
| I-7 | Graceful degradation when Ollama unreachable | Fallback paths in every `inference/pipeline.py`; chaos test `test_ollama_unreachable` |
| I-8 | 4-tier decision routing (<100ms / <500ms / 2-15s / 15-120s) | `orchestrator/consensus/tier_router.py` + p99 Prometheus alert |
| I-9 | A2A (JSON-RPC 2.0) ≠ MCP (tool protocol) — never conflated | Schemathesis contract tests; agent_card.json schema |
| I-10 | API latency <2s p99 | Prometheus alert `SynapseAPILatencyHigh` |
| I-11 | Federated learning keeps raw data at-store (DPDPA) | Flower gradient-only aggregation; `test_dpdpa.py` |
| I-12 | Digital Twin KL divergence vs live <0.1 | Prometheus metric `synapse_digital_twin_kl_divergence` + alert |
| I-13 | KV-cache stable prefix (deterministic serialization + no dynamic data in system prompt) | `kv-cache-check` pre-commit hook + SHA-256 unit test |
| I-14 | Runtime context append-only during Phases 1–5 | `ContextMessage` frozen=True + `deal` postcondition + `test_context_immutability.py` |

## Failure modes to know
- **Breaking I-1**: CI gate fails on `import openai`. Use Ollama.
- **Breaking I-2**: a reward function imports another agent's module — the
  AST scan in `reward-isolation` catches it.
- **Breaking I-13**: KV-cache hit rate drops <70%; Tier 2 SLA misses.
- **Breaking I-14**: cyclical failure patterns — the model repeats mistakes
  because the failure trace was removed.
