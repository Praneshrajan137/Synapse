# ADR-015: Seven-Layer Testing Topology

## Status
Accepted

## Context
A multi-agent RL system has at least seven distinct failure classes: undocumented behavior, API edge crashes, silent inter-agent regressions, ML behavioral drift across retraining, runtime invariant violations, locally-optimal-globally-suboptimal decisions, and weak tests with blind spots. A single test framework (e.g., pytest unit + integration only) cannot catch all seven. We need a topology where each failure class has a dedicated tooling layer and each layer is independently auditable in CI.

## Decision
Adopt a 7-layer testing topology, each layer addressing one failure class with one MIT/Apache/BSD-licensed tool:

| Layer | Failure Class | Tool | When |
|-------|---------------|------|------|
| 1 | Spec drift, unspecified behavior | Custom `spec.yaml` + auto-gen pytest | Every push |
| 2 | API edge crashes, schema violations | Schemathesis (MIT) | PR to main |
| 3 | Silent inter-agent regressions | Pydantic-based consumer contracts | Every push |
| 4 | ML behavioral drift across retraining | Custom pytest + Hypothesis (12 MR-* relations) | PR to main |
| 5 | Runtime invariant violations | `deal` (MIT) + auto-gen Hypothesis tests | Runtime + CI |
| 6 | Locally-optimal-globally-suboptimal decisions | SimPy Monte Carlo Twin Oracle | Policy CI |
| 7 | Weak tests with blind spots | mutmut (MIT) | Weekly cron |

No code merges to main unless layers 1-5 pass. Layer 6 runs on model checkpoint updates. Layer 7 runs weekly. A failure in any layer blocks the pipeline.

## Consequences
- Comprehensive coverage of agent-system failure modes; total tooling cost remains $0.
- CI pipeline grows to 7 jobs; budget tracked in plan §11 (~1,200 min/month within 2,000 min free tier).
- Each layer requires explicit per-agent contributions: spec.yaml (L1), OpenAPI (L2), Pydantic contracts (L3), metamorphic relations (L4), `@deal.pre/post` (L5), oracle test (L6), reward function (L7 mutation target).
- Onboarding cost is higher; mitigated by Ralph loop (ADR-020) auto-generating test stubs.

## Alternatives Rejected
- **Unit + integration only**: rejected — misses ML drift, runtime contracts, and global suboptimality.
- **BDD Gherkin everywhere**: rejected — adds layer of indirection without catching new failure classes.
- **Single property-based framework (e.g., Hypothesis only)**: rejected — does not exercise inter-agent contracts or twin oracle.
