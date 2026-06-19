# Implementation Plan: Agency Loop Completion

## Overview

This plan completes the autonomous perceive → decide → act → learn loop across four pillars, implemented in **Python** (the design uses Python grounded in the existing codebase). Work proceeds bottom-up: the two pure cores (binding selector, concession helper) land first with property tests, then they are wired into the orchestrator protocol, then the eight agent handlers are converted to real actuation or honest divergence, and finally the anti-regression gate is ratcheted to zero and wired into verification with the two required e2e proofs.

Each task builds on the previous and ends with integration so no code is orphaned. Property-based tests are placed close to the implementation they validate, and every property task references its property number and the requirements clause it checks.

## Tasks

- [x] 1. Implement the pure binding selector
  - [x] 1.1 Add `BindingSelection` dataclass and `select_binding_action` to `orchestrator/consensus/pareto.py`
    - Add frozen `BindingSelection` dataclass (`selected_agent`, `selected_index`, `weighted_scores`, `excluded_agents`, `tie_break_applied`, `tie_break_reason`)
    - Implement pure `select_binding_action(proposals, knee_weights, *, neutral_baseline=0.5, tolerance=1e-9)` reusing `_AGENT_TO_OBJECTIVE` and the `OBJECTIVES` ordering
    - Compute each eligible proposal's weighted score (own objective gets `utility_score`, others get `neutral_baseline`), exclude proposals with no objective-map entry without assigning a score, and select argmax via a stable sort over `(-score, OBJECTIVES.index(obj), agent_name)`
    - Record deterministic tie-break (objective order, then ascending agent name) into `tie_break_applied`/`tie_break_reason`
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 2.1_

  - [x]* 1.2 Write property tests for the binding selector
    - **Property 1: Binding selection maximizes the knee-weighted score** — Validates: Requirements 1.1, 1.3
    - **Property 2: Binding tie-break is deterministic** — Validates: Requirements 1.4, 2.5
    - **Property 3: Unmapped proposals are excluded without a fabricated score** — Validates: Requirements 1.5
    - Location: `orchestrator/tests/consensus/test_binding_arbitration_pbt.py`

- [x] 2. Wire binding selection into the full-path protocol
  - [x] 2.1 Update `_build_decision` in `orchestrator/consensus/protocol.py` to consume a `BindingSelection`
    - Add `selection: BindingSelection | None` and `fast_best: AgentProposal | None` parameters
    - When `selection` is provided, set `selected_action`/`confidence` from `proposals[selection.selected_index]` and append knee weights, per-candidate weighted scores, selected identity, exclusions, and tie-break reason to `audit_trace` (append-only)
    - Remove the `max(..., key=...utility_score)` expression from `_build_decision`; retain fast-path argmax only via `fast_best` from `_fast_path`
    - _Requirements: 1.2, 1.6, 2.2, 2.4, 2.5_

  - [x] 2.2 Invoke `select_binding_action` in the full path and append the binding-selection context record
    - After `_phase_arbitrate` returns the knee `selected_weights`, call `select_binding_action(proposals, weights)` and pass the result into `_build_decision`
    - Append a `binding_selection` `ContextMessage` to the append-only context, mirroring the pareto-result append
    - _Requirements: 1.1, 2.4_

  - [x]* 2.3 Write property test for binding audit completeness
    - **Property 5: The binding decision's audit trace is complete** — Validates: Requirements 2.2
    - Location: `orchestrator/tests/consensus/test_binding_arbitration_pbt.py`

  - [x]* 2.4 Write property test for binding determinism
    - **Property 4: Binding selection is deterministic and byte-stable (round-trip determinism)** — Validates: Requirements 2.1, 2.3, 10.6
    - Assert byte-identical `to_deterministic_json` output across repeated evaluations
    - Location: `orchestrator/tests/consensus/test_binding_arbitration_pbt.py`

  - [x]* 2.5 Write unit tests for fast-path retention and argmax divergence
    - Verify Tier-1/2 fast path still selects by raw `utility_score` argmax (R1.6)
    - Verify a crafted case where knee selection differs from raw argmax selects the knee proposal (R1.2)
    - _Requirements: 1.2, 1.6_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement the shared, pure concession helper
  - [x] 4.1 Create `packages/synapse_common/debate/concession.py`
    - Implement `consensus_position(utility_scores)` (arithmetic mean)
    - Implement `within_convergence_band(current, consensus, *, variance_threshold=0.1)` (true when `|current - consensus| <= sqrt(variance_threshold)`)
    - Implement `concede_toward(current, consensus, *, max_fraction=0.5)` (moves at most 50% of the gap, never overshooting consensus)
    - _Requirements: 3.2, 3.3, 3.9_

  - [x]* 4.2 Write property test for the concession helper
    - **Property 8: Concession is bounded, monotone toward consensus, and honest** — Validates: Requirements 3.2, 3.3, 3.7, 3.9
    - Location: `packages/tests/debate/test_concession_pbt.py`

- [x] 5. Make debate revise proposals via concession and degrade honestly
  - [x] 5.1 Upgrade `debate_respond` in all eight agent handlers
    - Replace the `{"status": "maintained"}` constant in each `agents/<agent>/a2a/handler.py` with logic that computes the consensus position, returns maintained when within the convergence band (R3.9), otherwise builds a bounded concession via `concede_toward`, builds an honest revised payload, and validates it against `proto/domain/` before returning `"revised"`; on schema failure return maintained with `rationale="revision_failed_schema"`
    - _Requirements: 3.2, 3.3, 3.6, 3.7, 3.9, 3.10_

  - [x] 5.2 Implement revise-iff-valid round logic in `_phase_debate` (`orchestrator/consensus/protocol.py`)
    - Per round compute consensus, invoke each conflicting agent's `debate_respond` over A2A, replace a proposal only with a `"revised"` response whose payload re-validates schema-side, otherwise retain the prior proposal
    - Append each round's revisions to the append-only context; re-evaluate `_check_convergence` and stop on convergence or at `debate_max_rounds`
    - _Requirements: 3.1, 3.4, 3.5, 3.8, 3.10_

  - [x] 5.3 Add honest LLM degradation to `_phase_debate`
    - Bound LLM analysis to a 30s per-round timeout and at most 2 attempts; on failure append a degraded-round entry (`degraded=true`, `degraded_reason`) and proceed to arbitration with the most-recent proposals while concession continues
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x]* 5.4 Write property test for revise-iff-valid replacement
    - **Property 7: Debate replaces a proposal only with a schema-valid revision** — Validates: Requirements 3.1, 3.10
    - Location: `orchestrator/tests/consensus/test_debate_concession_pbt.py`

  - [x]* 5.5 Write property test for the debate round bound
    - **Property 9: Debate terminates within the round bound** — Validates: Requirements 3.5
    - Location: `orchestrator/tests/consensus/test_debate_concession_pbt.py`

  - [x]* 5.6 Write property test for revised payload schema validity
    - **Property 10: Every emitted or revised payload is schema-valid** — Validates: Requirements 3.6, 10.1
    - Location: `orchestrator/tests/consensus/test_debate_concession_pbt.py`

  - [x]* 5.7 Write unit tests for LLM degradation behavior
    - LLM raises/times out → degraded round recorded and arbitration proceeds (R4.1, R4.3); at most 2 attempts (R4.4); concession runs while LLM down (R4.2); convergence stops debate (R3.4)
    - _Requirements: 3.4, 4.1, 4.2, 4.3, 4.4_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Convert all eight agents to real actuation or honest divergence
  - [x] 7.1 Convert `pricing_oracle` `execute()` to apply a `SET_PRICE_MULT` WorldAction
    - Inject `actuator`/`kafka_producer`, read `city`, validate the ratified payload, build one `SET_PRICE_MULT` action per actionable item with `price_mult > 0`, apply via the actuator, event-source honestly, and apply the uniform honest status rule (`executed` iff a non-empty effect was applied, else `diverged`; `kafka_published` only on real produce; `world_effects` always the real effect)
    - _Requirements: 5.1, 5.2, 5.6, 5.7, 5.8, 5.9, 5.10, 7.1, 7.2, 7.3, 7.4_

  - [x] 7.2 Convert `demand_prophet` `execute()` to apply a `SET_POLICY` `demand_mult` WorldAction
    - Build the `demand_mult` lever value within range (`>= 0.01`) from the ratified forecast and apply per actionable item using the uniform honest status rule
    - _Requirements: 5.1, 5.3, 5.6, 5.7, 5.8, 5.9, 5.10, 7.1, 7.2, 7.3, 7.4_

  - [x] 7.3 Convert `routing_navigator` `execute()` to apply a `SET_POLICY` `dispatch_speed` WorldAction
    - Build the `dispatch_speed` lever value within range (`>= 0.1`) from the ratified route decision and apply per actionable item using the uniform honest status rule
    - _Requirements: 5.1, 5.4, 5.6, 5.7, 5.8, 5.9, 5.10, 7.1, 7.2, 7.3, 7.4_

  - [x] 7.4 Convert `disruption_shield` `execute()` to apply a `SET_POLICY` `lead_time_mult` WorldAction
    - Build the `lead_time_mult` lever value within range (`>= 0.1`) from the ratified mitigation and apply per actionable item using the uniform honest status rule
    - _Requirements: 5.1, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 7.1, 7.2, 7.3, 7.4_

  - [x] 7.5 Convert `freshness_guardian` `execute()` to actuate via the closest `SET_POLICY` `dispatch_speed` lever
    - Raise `dispatch_speed` (within range `>= 0.1`) to lower spoilage exposure as the closest existing lever (R6.3); apply the uniform honest status rule, falling back to Honest No-Op if no spoilage-relevant `perceive()` change occurs
    - _Requirements: 5.6, 5.7, 5.8, 5.9, 5.10, 6.1, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4_

  - [x] 7.6 Convert `sustainability_agent` `execute()` to an Honest No-Op
    - Construct no fabricated effect; return status `"diverged"`, empty `world_effects`, `reason="no_carbon_lever"`, never `"executed"`, while still performing an honest `self._kafka.produce` event-source so the gate marks it converted; leave `perceive()` state unchanged
    - _Requirements: 6.1, 6.2, 6.4, 6.5, 6.6, 7.4_

  - [x]* 7.7 Write parametrized actuation property tests for the lever agents
    - **Property 11: One WorldAction per actionable item** — Validates: Requirements 5.1
    - **Property 12: Actuation levers stay within the world's accepted range** — Validates: Requirements 5.2, 5.3, 5.4, 5.5
    - **Property 13: An applied effect yields an honest "executed" status** — Validates: Requirements 5.6
    - **Property 14: `kafka_published` reflects a real produce** — Validates: Requirements 5.7
    - **Property 15: Actuation routes to the request's city** — Validates: Requirements 5.8
    - Location: `agents/tests/test_actuation_pbt.py`

  - [x]* 7.8 Write property test for the sustainability Honest No-Op
    - **Property 16: Honest No-Op leaves the world unchanged** — Validates: Requirements 6.1, 6.2
    - Location: `agents/tests/test_sustainability_noop_pbt.py`

  - [x]* 7.9 Write the degradation property test across converted agents
    - **Property 17: Unavailable world and Kafka degrade honestly (degradation property)** — Validates: Requirements 5.9, 5.10, 6.4, 6.5, 7.1, 7.2, 7.4, 10.7
    - Location: `agents/tests/test_actuation_pbt.py`

  - [x]* 7.10 Write unit/edge tests for per-agent actuation
    - Missing/unknown city (R5.9), no actionable item / empty actions (R5.10), and degradation logging captured with agent name and reason (R7.3)
    - _Requirements: 5.9, 5.10, 7.3_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Verify append-only audit and provenance across the loop
  - [x]* 9.1 Write the append-only property test
    - **Property 6: Audit and provenance records are append-only** — Validates: Requirements 2.4, 3.8, 6.6, 10.2
    - Cover the decision `audit_trace`, the context message list, and an agent's actuation/provenance record
    - Location: `orchestrator/tests/consensus/test_append_only_pbt.py`

- [x] 10. Ratchet the anti-regression gate to zero and wire verification
  - [x] 10.1 Add the binding-arbitration check, `converted_count`, and ratchet `DEFAULT_MAX_STUBS` 6→0 in `scripts/audit/agency_truth.py`
    - Implement `_binding_arbitration_check` (AST-assert `select_binding_action` is referenced, `_full_path` reaches binding selection, and `_build_decision` contains no `max(..., key=...)`)
    - Expose the check in `evaluate()`/`--json`, add an explicit integer `converted_count` (0..8) computed independently of the binding check, and set `DEFAULT_MAX_STUBS = 0`
    - Preserve the five structural loop invariants in `--check`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 9.1, 9.2_

  - [x] 10.2 Wire the gate verdict into `verify_claims` (C57) and `make verify-agency`
    - Ensure `evaluate().ok` (including the binding check and the 0-stub ratchet) flows into C57 and the `make verify-agency --check` exit code
    - _Requirements: 9.3, 9.4, 9.5_

  - [x]* 10.3 Write property test for the gate classifier
    - **Property 18: The gate classifies actuating handlers as converted, not stubs** — Validates: Requirements 8.6
    - Location: `packages/tests/test_agency_truth_gate.py`

  - [x]* 10.4 Write unit tests for the gate
    - `DEFAULT_MAX_STUBS == 0` (R8.2), `evaluate()` reports 0 stubs (R8.1) and the binding-arbitration check is present and ok (R9.1), `converted_count` is an int in `[0,8]` (R9.2), the five structural invariants are present (R8.7), `evaluate(max_stubs < stubs).ok is False` with stubs listed (R8.3), and C57 reflects `probe.ok` with simulated argmax or <8 converted → FAIL (R9.4)
    - _Requirements: 8.1, 8.2, 8.3, 8.7, 9.1, 9.2, 9.4_

- [x] 11. Provide the required end-to-end proofs
  - [x]* 11.1 Write `test_binding_arbitration_overrides_argmax_e2e`
    - Construct proposals where the highest-`utility_score` proposal is not the knee selection, run the full path, and assert the ratified `selected_action` is the knee-selected payload and differs from the raw-argmax proposal (follows `orchestrator/tests/test_agentic_loop_e2e.py`)
    - _Requirements: 9.6_

  - [x]* 11.2 Write `test_real_actuation_changes_world_e2e`
    - With a live `WorldRuntime` and in-process actuator, execute a converted lever-agent (e.g. `pricing_oracle` → `SET_PRICE_MULT`), assert the observed `perceive()` state changed and the agent returned status `"executed"`
    - _Requirements: 9.7_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP, but the property and e2e tests are how Requirements 9.5, 9.6, 9.7, and 10.5–10.7 are demonstrated.
- Each task references specific requirement clauses for traceability; each property task names the design property number and the requirements it validates.
- The pure cores (`select_binding_action`, concession helper) land first so the orchestrator and handlers can build on tested foundations.
- Cross-cutting quality gates from Requirement 10 (`ruff`, `mypy --strict`, the coverage gate) are enforced in CI against the pre-feature baseline rather than as standalone tasks; all new code uses full type annotations consistent with `pareto.py`.
- `protocol.py` edits (tasks 2.1, 2.2, 5.2, 5.3) are sequenced across waves because they touch the same file; agent `handler.py` edits sequence `debate_respond` (5.1) before `execute` conversions (7.1–7.6).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "4.1"] },
    { "id": 1, "tasks": ["2.1", "1.2", "4.2", "5.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["5.2", "2.3", "2.4", "2.5"] },
    { "id": 4, "tasks": ["5.3"] },
    { "id": 5, "tasks": ["5.4", "5.5", "5.6", "5.7", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6"] },
    { "id": 6, "tasks": ["7.7", "7.8", "7.9", "7.10", "9.1"] },
    { "id": 7, "tasks": ["10.1"] },
    { "id": 8, "tasks": ["10.2", "10.3", "10.4"] },
    { "id": 9, "tasks": ["11.1", "11.2"] }
  ]
}
```
