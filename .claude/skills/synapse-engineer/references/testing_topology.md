# 7-Layer Testing Topology (ADR-015)

| # | Layer | What it proves | Tooling | Where it lives |
|---|-------|----------------|---------|----------------|
| 1 | Spec-Driven Development (SDD) | Every invariant in `spec.yaml` has at least one test | `scripts/check_spec_coverage.py` + `scripts/generate_tests_from_spec.py` | `agents/*/tests/test_spec.py` |
| 2 | API Fuzz (Schemathesis) | `/predict` endpoints reject garbage per OpenAPI | `schemathesis` | `tests/api_fuzz/` |
| 3 | Consumer-driven Contracts | Producer/consumer payloads co-evolve | Pydantic models in `agents/*/contracts/` and `orchestrator/contracts/` | In-agent |
| 4 | Metamorphic | Invariants hold under input transforms (12 relations: MR-DP-001 … MR-ST-001) | custom | `agents/*/tests/test_metamorphic.py` |
| 5 | Design-by-Contract (deal) | Pre/post on 7 critical functions | `deal` | `pricing_oracle/inference/pipeline.py`, `orchestrator/{consensus,guardrails,audit}/*` |
| 6 | Twin Oracle | Live decisions agree with Digital Twin expectation (6 scenarios) | custom | `tests/oracle/` |
| 7 | Mutation (mutmut) | Rewards/guardrails/audit survive <15% / <10% mutation | `mutmut` | `tests/mutation/` |

## Merge rule
A PR that breaks **any** invariant in `spec.yaml` is auto-rejected by CI.
A PR that adds a new invariant without a matching test in layer 1 is auto-
rejected by the `spec-coverage` pre-commit hook.
