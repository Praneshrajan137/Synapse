# SYNAPSE Chaos Engineering — Sprint 5

## Overview

This directory contains **Phase 1 chaos logic validation tests** for all 9
documented failure modes.  Each test instantiates the relevant fallback
component in-process and verifies detection, recovery, and SLA compliance.

**Phase 2** (Sprint 6+) will introduce infrastructure-level fault injection
via Chaos Mesh / Litmus against a running Docker Compose stack.

## Failure Modes and SLAs

| # | Failure Mode | SLA | Test File |
|---|---|---|---|
| 1 | GNN nonsensical demand spike (10x) | <1 min | `test_gnn_spike.py` |
| 2 | LLM hallucination (invalid JSON) | <100ms | `test_llm_hallucination.py` |
| 3 | Agent deadlock (circular proposals) | <5s | `test_deadlock.py` |
| 4 | Digital Twin drift (50% demand shift) | <2 min | `test_twin_drift.py` |
| 5 | Supplier trust cold-start bias | Preventive | `test_supplier_bias.py` |
| 6 | RL policy instability (adversarial reward) | <60s | `test_rl_instability.py` |
| 7 | Kafka broker failure mid-stream | <30s | `test_kafka_failure.py` |
| 8 | Ollama process crash (SIGKILL) | <5s | `test_ollama_crash.py` |
| 9 | GPU OOM during RL training | <2 min | `test_gpu_oom.py` |

## Running

```bash
# All chaos tests
python tests/chaos/run_all.py

# Via pytest marker
pytest -m chaos -v

# Single failure mode
pytest tests/chaos/test_gnn_spike.py -v
```
