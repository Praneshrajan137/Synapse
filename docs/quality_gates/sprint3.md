# Quality Gate — Sprint 3: Orchestrator + Digital Twin

## Scope
Implement the LangGraph orchestrator with 5-phase consensus, the tier router,
the HITL escalation channel, the Ollama LLM client with KV-cache preservation,
and the Digital Twin (Neo4j graph + SimPy + Mesa + Monte Carlo + Gymnasium).

## Milestones
| # | Milestone | Verification |
|---|-----------|--------------|
| 1 | LangGraph 5-phase consensus FSM (Proposal→Debate→Arbitration→Execution→Learning) | `pytest orchestrator/tests/test_consensus.py -v` |
| 2 | 4-tier router (<100ms / <500ms / 2-15s / 15-120s) with tool masking | `pytest orchestrator/tests/test_tier_router.py -v` |
| 3 | HITL escalation channel via WebSocket | manual smoke + `pytest orchestrator/tests/test_hitl.py` |
| 4 | Ollama client with KV-cache stable prefix (I-13) | `pre-commit run kv-cache-check` clean |
| 5 | Audit logger writes to Postgres `audit_decisions` (I-4) | `pytest tests/security/test_audit_immutability.py` |
| 6 | Digital Twin Neo4j graph schema + SimPy + Gym env | `pytest digital_twin/tests -v` |
| 7 | Twin Oracle 6 oracle tests pass | `pytest tests/oracle -v` |

## Acceptance criteria
- All milestones green
- Consensus FSM completes Tier-1 decision in < 100 ms p99
- Tool masking via Ollama prefill verified per tier (ADR-022)
- Append-only context confirmed (I-14, `test_context_immutability.py`)

## Verification command
```bash
make sprint3-verify
```
