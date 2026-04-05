# SYNAPSE Testing Reference — Seven-Layer Topology

## Layer 1: Spec-Driven (SDD)
- Tool: Custom YAML specs + auto-generated pytest
- When: Every push
- What it catches: Missing invariants, unspecified behavior, spec drift

## Layer 2: Schemathesis API Fuzz
- Tool: Schemathesis (MIT, Hypothesis-based)
- When: PRs to main
- What it catches: API edge-case crashes, schema violations

## Layer 3: Consumer-Driven Contract Tests
- Tool: Custom Pydantic-based consumer contracts
- When: Every push
- What it catches: Silent inter-agent regressions

## Layer 4: Metamorphic ML Tests
- Tool: Custom pytest + Hypothesis strategies
- When: PRs to main + policy regression CI
- What it catches: ML behavioral drift across retraining

## Layer 5: Design-by-Contract (deal)
- Tool: deal (MIT) + auto-gen Hypothesis tests
- When: Runtime + CI
- What it catches: Runtime invariant violations on critical paths

## Layer 6: Digital Twin Oracle
- Tool: Custom pytest + SimPy Monte Carlo
- When: Policy regression CI
- What it catches: Locally optimal but globally suboptimal agent decisions

## Layer 7: Mutation Testing (mutmut)
- Tool: mutmut (MIT)
- When: Weekly CI cron
- What it catches: Weak tests with blind spots
- Max survival rates: <15% rewards, <10% guardrails/audit

## Quality Gate Rule
No code merges to main unless ALL seven layers pass.
Layers 1-5: every PR. Layer 6: model checkpoint updates. Layer 7: weekly.
