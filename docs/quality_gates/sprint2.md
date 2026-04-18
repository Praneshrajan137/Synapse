# Quality Gate — Sprint 2: Agent Implementation

## Scope
Implement the first three RL agents — Demand Prophet (HGT-TFT), Inventory Sentinel
(3-level MARL + Flower federation), Routing Navigator (transformer + REINFORCE +
distillation + OSRM) — with full canonical structure.

## Milestones
| # | Milestone | Verification |
|---|-----------|--------------|
| 1 | Demand Prophet HGT-TFT trains and serves | `pytest agents/demand_prophet/tests -v` |
| 2 | Inventory Sentinel L1/L2/L3 hierarchy + Flower client/server | `pytest agents/inventory_sentinel/tests -v` |
| 3 | Routing Navigator transformer + pointer + REINFORCE + distilled student | `pytest agents/routing_navigator/tests -v` |
| 4 | All 3 agents expose A2A JSON-RPC via FastAPI on port 808x | `curl /openapi.json` returns spec |
| 5 | All 3 agents register MCP tools | `make test-mcp-tools` |
| 6 | All 3 spec.yaml files validated; tests auto-generated | `python scripts/generate_tests_from_spec.py --check` |
| 7 | Conformal prediction (MAPIE) coverage ≥ 0.85 on holdout | logged to MLflow `calibration_coverage_90` |

## Acceptance criteria
- All milestones green
- 7-layer testing topology partially active (SDD + Contract + Metamorphic per agent)
- Coverage ≥ 80% on each agent
- Mutation survival < 15% on each agent's reward function
- Independent reward functions confirmed by `pre-commit run reward-isolation`

## Verification command
```bash
make sprint2-verify
```
