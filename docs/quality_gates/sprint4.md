# Quality Gate — Sprint 4: Remaining Agents + API Gateway + Frontend

## Scope
Complete the remaining 5 agents (Pricing Oracle, Disruption Shield, Supplier Trust,
Sustainability Agent, Freshness Guardian), implement the FastAPI gateway + Celery
workers, and ship the React frontend with 5 pages + AgentDebate component.

## Milestones
| # | Milestone | Verification |
|---|-----------|--------------|
| 1 | Pricing Oracle EconML Double-ML elasticity model | `pytest agents/pricing_oracle/tests -v` |
| 2 | Disruption Shield Bayesian model | `pytest agents/disruption_shield/tests -v` |
| 3 | Supplier Trust graph + RL | `pytest agents/supplier_trust/tests -v` |
| 4 | Sustainability Agent carbon footprint scorer | `pytest agents/sustainability_agent/tests -v` |
| 5 | Freshness Guardian discard-recommendation policy | `pytest agents/freshness_guardian/tests -v` |
| 6 | API Gateway (FastAPI + Celery) routes orders/decisions/agents | `pytest api/tests -v` |
| 7 | React UI: Dashboard, DecisionLog, OverrideConsole, AgentStatus, DigitalTwin | `cd ui && npm test && npm run build` |
| 8 | AgentDebate component renders consensus phase live | manual smoke against running orchestrator |

## Acceptance criteria
- All 8 agents have canonical structure + spec.yaml + tests
- I-6 (price cap ≤ base × 1.30) enforced in `agents/pricing_oracle/inference/pipeline.py`
- All metamorphic relations from `docs/testing/metamorphic_relations.md` covered
- Frontend bundles < 500 KB gzipped per chunk

## Verification command
```bash
make sprint4-verify
```
