# spec.yaml Schema (SDD layer)

Every agent has a `agents/<name>/spec.yaml` file. It is the single source of
truth for Spec-Driven Development. The schema lives at
`docs/specs/agent_spec_schema.json` and is enforced by the `spec-validate`
pre-commit hook.

## Minimum required sections

```yaml
agent_name: demand_prophet
version: "1.2.0"
description: "Multi-horizon demand forecasting with conformal intervals"

invariants:
  - id: INV-DP-001
    description: "Every forecast includes conformal intervals"
    assertion: "result.lower <= result.mean <= result.upper"
    severity: critical
  # ... more invariants

preconditions:
  - id: PRE-DP-001
    description: "Kafka topics reachable"
    check: "kafka_healthy() == True"

postconditions:
  - id: POST-DP-001
    description: "Confidence in [0, 1]"
    check: "0 <= result.confidence <= 1"

state_machine:
  initial_state: IDLE
  states: [IDLE, PROPOSING, DEBATING, EXECUTING, LEARNING, ERROR]
  transitions:
    - from: IDLE
      to: PROPOSING
      trigger: forecast_request_received
      guard: kafka_healthy and feast_available
      timeout_seconds: 2.0
```

## ID naming convention

- `INV-<AGENT>-<NNN>` — invariants (e.g., `INV-DP-001` for Demand Prophet)
- `PRE-<AGENT>-<NNN>` — preconditions
- `POST-<AGENT>-<NNN>` — postconditions

Agent abbreviations: DP (Demand Prophet), RN (Routing Navigator),
IS (Inventory Sentinel), PO (Pricing Oracle), DS (Disruption Shield),
ST (Supplier Trust), SA (Sustainability Agent), FG (Freshness Guardian).

## How it wires into tests

1. `spec.yaml` declares `INV-DP-001`.
2. `scripts/generate_tests_from_spec.py` generates the skeleton
   `agents/demand_prophet/tests/test_spec.py::test_inv_dp_001`.
3. Developer fills in the body (RED).
4. Implementation code is added (GREEN).
5. `scripts/check_spec_coverage.py` (pre-commit hook) blocks merges where
   an invariant has no test.

## Forbidden

- Renaming `agent_name` without version bump.
- Removing an invariant without an explicit supersede note.
- Adding an invariant without a test in the same PR.
