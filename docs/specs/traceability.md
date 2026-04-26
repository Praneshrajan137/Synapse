# SYNAPSE — Invariant Traceability Matrix

> Generated index of the 14 system invariants (I-1 .. I-14) and the artefacts
> that enforce them. Source of truth: [`invariants.yaml`](./invariants.yaml).
> Per-agent invariants (INV-DP-*, INV-IS-*, …) live in
> [`agents/<name>/spec.yaml`](../../agents/) and are exercised by
> `agents/<name>/tests/test_spec.py`.

| ID    | Status | Name                                  | Primary enforcement                                                                                       | Primary tests                                                |
|-------|--------|---------------------------------------|-----------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| I-1   | GREEN  | Zero paid dependencies                | CI grep + license audit in [`ci.yml`](../../.github/workflows/ci.yml)                                     | n/a (static gate)                                            |
| I-2   | GREEN  | Reward isolation per agent            | CI grep in `ci.yml` + `sprint6-verify`                                                                     | `agents/*/tests/test_reward.py`                              |
| I-3   | GREEN  | Schema-validated agent outputs        | [`scripts/validate_schemas.py`](../../scripts/validate_schemas.py)                                        | `tests/integration/test_agent_pipeline.py`                   |
| I-4   | GREEN  | Immutable audit log                   | `orchestrator/audit/`, [`infrastructure/postgres/init.sql`](../../infrastructure/postgres/)                | `orchestrator/tests/test_audit.py`                           |
| I-5   | GREEN  | Confidence-gated execution + HITL     | `orchestrator/hitl/escalation.py`, `orchestrator/guardrails/rules.py`                                      | `orchestrator/tests/test_hitl_escalation.py`                 |
| I-6   | GREEN  | Explainable consensus                 | `orchestrator/consensus/`                                                                                  | `orchestrator/tests/test_consensus.py`                       |
| I-7   | GREEN  | Recitation interval bounded           | [`packages/synapse_common/fsm.py`](../../packages/synapse_common/fsm.py)                                   | `packages/tests/test_fsm.py`                                 |
| I-8   | GREEN  | Deterministic JSON serialization      | `packages/synapse_common/models.py`                                                                        | `packages/tests/test_models.py`                              |
| I-9   | GREEN  | A2A vs MCP protocol separation        | Agent card validation in `sprint6-verify`                                                                  | `packages/tests/test_a2a_sdk.py`                             |
| I-10  | YELLOW | Spec-first agents                     | `scripts/generate_tests_from_spec.py`, `scripts/check_spec_coverage.py`                                    | `agents/*/tests/test_spec.py` (R1: assertions still stubbed) |
| I-11  | YELLOW | 7-layer testing pyramid               | `mutation.yml` + `scripts/check_mutation_threshold.py`                                                     | `tests/fuzz/`, `tests/oracle/`, contracts (R2/R3 in flight)  |
| I-12  | GREEN  | Twin–live divergence alerting         | `digital_twin/sync/divergence_monitor.py`                                                                  | `digital_twin/tests/test_simulation.py::TestKLDivergence`    |
| I-13  | GREEN  | KV-cache preservation                 | CI grep + `orchestrator/llm/context_builder.py`                                                            | `orchestrator/tests/test_llm.py`                             |
| I-14  | GREEN  | Append-only runtime context           | CI grep in `ci.yml`                                                                                        | `orchestrator/tests/test_state_machine.py`                   |

## Status legend

- **GREEN** — invariant has both an enforcement mechanism and a green test.
- **YELLOW** — invariant has an enforcement mechanism but tests are
  incomplete or partially skipped. Tracked in
  [`plans/now-we-have-completed-joyful-goose.md`](../../../plans/) under R1
  (SDD), R2 (fuzz), R3 (DbC).
- **RED** — would mean an invariant was claimed but had no enforcement at
  all. None remain after the elevation pass.

## How to verify locally

```bash
make verify-v4-compliance         # static gates (I-1, I-2, I-9, I-13, I-14)
pytest agents/*/tests/test_reward.py -q                    # I-2 runtime
pytest agents/*/tests/test_spec.py -q                      # I-10 (after R1)
pytest tests/oracle/ -q                                    # I-12 + twin claims
pytest packages/tests/ --cov=synapse_common --cov-fail-under=80   # I-11 unit
```

## Per-agent invariants

Each agent maintains its own set of invariants in `spec.yaml`. The system
invariants above are intentionally cross-cutting; agent-level invariants
remain owned by the agent team and exercised by `agents/<name>/tests/`.

| Agent                | Spec                                                   | Count of agent-level invariants |
|----------------------|--------------------------------------------------------|---------------------------------|
| demand_prophet       | `agents/demand_prophet/spec.yaml`                      | INV-DP-001 .. 009               |
| inventory_sentinel   | `agents/inventory_sentinel/spec.yaml`                  | INV-IS-* (see file)             |
| routing_navigator    | `agents/routing_navigator/spec.yaml`                   | INV-RN-* (see file)             |
| pricing_oracle       | `agents/pricing_oracle/spec.yaml`                      | INV-PO-* (see file)             |
| freshness_guardian   | `agents/freshness_guardian/spec.yaml`                  | INV-FG-* (see file)             |
| disruption_shield    | `agents/disruption_shield/spec.yaml`                   | INV-DS-* (see file)             |
| supplier_trust       | `agents/supplier_trust/spec.yaml`                      | INV-ST-* (see file)             |
| sustainability_agent | `agents/sustainability_agent/spec.yaml`                | INV-SA-* (see file)             |
