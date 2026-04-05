# SYNAPSE Architecture Reference

## Four Coherent Layers
1. **Orchestration Layer**: LangGraph + Ollama (DeepSeek-R1, Llama 3.3 70B Q4). Five-phase consensus protocol. Pareto arbitration via pymoo NSGA-II. Append-only audit.
2. **Agent Layer**: 8 specialized agents in Docker containers. Independent RL reward functions (CTDE paradigm). A2A JSON-RPC inter-agent communication.
3. **Digital Twin Layer**: Neo4j graph + SimPy + Mesa ABM. Monte Carlo simulation (1,000+ scenarios). KL divergence monitoring (threshold 0.1).
4. **Data Fabric Layer**: Kafka streams (16 topics) + Feast feature store + Redis online store. Point-in-time correct retrieval. Zero data leakage.

## 14 Architectural Invariants
I-1: Zero Cost | I-2: Independent Rewards | I-3: Ontology-Bound Outputs
I-4: Append-Only Audit | I-5: Confidence-Gated Execution | I-6: Hard Guardrails
I-7: Graceful Degradation | I-8: Reproducible ML Pipeline | I-9: A2A + MCP Protocol
I-10: Tiered Latency | I-11: Federated Privacy | I-12: Twin Fidelity
I-13: KV-Cache Preservation | I-14: Append-Only Runtime Context

## Dependency DAG (Critical Path)
Infrastructure -> Demand Prophet -> Inventory Sentinel -> Orchestrator
(Routing Navigator and others parallelize with Sprint 2-3)

## Decision Tier SLAs
Tier 1: <100ms (RL-only, ~80% of decisions)
Tier 2: <500ms (RL + features + lightweight LLM)
Tier 3: 2-15s (Full LLM reasoning via DeepSeek-R1)
Tier 4: 15-120s (Monte Carlo + LLM planning via Llama 3.3 70B)
