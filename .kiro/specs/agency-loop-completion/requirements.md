# Requirements Document

## Introduction

This feature completes the autonomous perceive → decide → act → learn loop that ADR-052 landed for SYNAPSE. The vertical slice (`inventory_sentinel` + `supplier_trust`) proved the loop is real; this feature extends genuine, universal agency to the whole system and makes that agency non-regressable.

Three pillars are in scope, all grounded in the existing codebase:

1. **Binding Pareto arbitration** — the orchestrator already runs NSGA-II Pareto arbitration and computes Pareto-knee weights, but `_build_decision` still selects the ratified action with a raw `argmax` over `utility_score`. The Pareto-knee weights are stored as metadata and never used to select. This pillar makes arbitration binding: the ratified action is chosen by applying the Pareto-knee weights to the per-objective proposal utilities.

2. **Debate that revises proposals** — `_phase_debate` appends LLM analysis to the append-only context but returns proposals unchanged, and every agent's `debate_respond` returns `{"status": "maintained"}`. This pillar lets debate actually revise proposals across rounds via rule-based concession, honestly and within bounded rounds, degrading gracefully when the LLM is unavailable.

3. **Universal real actuation (broaden-to-8)** — six agents (`routing_navigator`, `pricing_oracle`, `demand_prophet`, `disruption_shield`, `freshness_guardian`, `sustainability_agent`) still return the `{"kafka_published": True}` status-dict stub from `execute()`. This pillar converts each remaining agent to actuate the standing world for real (or to flag and honestly no-op where no natural world mutation exists), following the `inventory_sentinel` actuation template.

A fourth, cross-cutting concern makes the result durable: the `agency_truth.py` anti-regression gate must ratchet its stub ceiling toward 0, reaching 0 on completion, so the autonomy cannot silently regress.

The standard for this feature is the highest achievable: agency must be **universal** (all 8 agents actuate or honestly diverge), **binding** (arbitration selects the action), **honest** (degradation never fabricates), and **non-regressable** (mechanically gate-enforced).

## Glossary

- **Consensus_Protocol**: The orchestrator's five-phase consensus engine in `orchestrator/consensus/protocol.py` (`ConsensusProtocol`), responsible for collect → debate → arbitrate → execute → learn.
- **Pareto_Arbitrator**: The NSGA-II arbitration routine `run_pareto_arbitration` in `orchestrator/consensus/pareto.py` that produces a Pareto front and selects a knee point.
- **Binding Arbitration**: Selecting the ratified action by applying the Pareto-knee weights to the per-objective proposal utilities, rather than by raw `argmax` over `utility_score`. The arbitration result determines the selected action, not merely metadata.
- **Pareto Knee**: The knee point of the Pareto front, selected in `run_pareto_arbitration` as the solution minimizing weighted normalized distance to the ideal point; its weight vector is `selected_weights`.
- **Objective Vector (OBJECTIVES)**: The ordered list of 8 objectives in `pareto.py` (`demand_accuracy`, `route_efficiency`, `inventory_fill_rate`, `freshness_score`, `pricing_revenue`, `disruption_readiness`, `supplier_reliability`, `carbon_efficiency`).
- **Agent_Objective_Map**: The `_AGENT_TO_OBJECTIVE` / `_AGENT_OBJECTIVE` table mapping each agent name to its single objective.
- **Debate_Coordinator**: The `_phase_debate` logic in `Consensus_Protocol` that runs bounded debate rounds (`debate_max_rounds`) with conflict detection (`_detect_conflicts`, 0.3 utility divergence) and convergence detection (`_check_convergence`, variance < 0.1).
- **Debate Revision**: A change to an agent's proposal (`utility_score` and/or `payload`) produced during a debate round in response to other proposals.
- **Concession**: A rule-based debate revision in which an agent moves its proposal toward the consensus position by a bounded amount; the chosen design for debate revision (no LLM required for the revision itself).
- **Agent_Handler**: An agent's A2A JSON-RPC handler (`agents/<agent>/a2a/handler.py`) exposing `proposal`, `debate_respond`, and `execute`.
- **Actuation**: A real mutation of the standing world performed in an agent's `execute()` by applying a `WorldAction` through the injected `Actuator`/`WorldActuator`, and/or a real Kafka produce that event-sources the result.
- **World_Runtime**: The standing, ticking digital-twin world `WorldRuntime` in `digital_twin/world/runtime.py`, exposing `perceive()` and `apply_action(WorldAction)`.
- **WorldActionKind**: The actuation kinds the World_Runtime supports today: `REORDER`, `SET_POLICY` (`dispatch_speed`, `order_qty_mult`, `demand_mult`, `restock_threshold`, `lead_time_mult`), `SET_PRICE_MULT`, `INJECT_DISRUPTION`.
- **Divergence**: An honest `execute()` status of `"diverged"`, returned when actuation was attempted but the world applied no effect; contrasted with `"executed"` when an effect was applied.
- **Honest No-Op**: An `execute()` outcome for an agent whose objective has no natural world mutation, in which no fabricated effect is reported and the status reflects that no world change occurred (`"diverged"` or an explicit no-actuation status), pending a new WorldActionKind.
- **Ratchet**: The `agency_truth.py` ceiling (`DEFAULT_MAX_STUBS`) on the number of agents whose `execute()` is still the status-dict-only stub; it may only decrease over time, reaching 0 on completion.
- **Agency_Truth_Gate**: The mechanical anti-regression gate `scripts/audit/agency_truth.py`, enforcing five structural loop invariants plus the Ratchet, wired into `verify_claims` (C57) and `make verify-agency`.
- **Stub_Execute**: An `execute()` that returns a dict literal containing `kafka_published: True` and performs no actuation (no `apply`/`produce` call) — the regression shape the Ratchet forbids.
- **I-3**: Repository invariant requiring payload schema validation against `proto/domain/`.
- **I-7**: Repository invariant requiring honest degradation — never fabricate a result when a dependency is unavailable.
- **I-14**: Repository invariant requiring append-only audit/provenance.

## Requirements

### Requirement 1: Binding Pareto Arbitration Selects the Ratified Action

**User Story:** As an orchestrator operator, I want the ratified action to be selected by applying the Pareto-knee weights to the per-objective proposal utilities, so that the NSGA-II arbitration the system already computes actually governs the decision instead of being discarded in favor of raw argmax.

#### Acceptance Criteria

1. WHEN the Consensus_Protocol completes Pareto arbitration for a decision, THE Consensus_Protocol SHALL compute a single weighted score for each candidate proposal by aggregating that proposal's per-objective utilities (derived from the Agent_Objective_Map and the Objective Vector) under the Pareto-knee weights, and SHALL select the proposal with the highest weighted score as the ratified action.
2. WHEN the Consensus_Protocol selects the ratified action on the full path, THE Consensus_Protocol SHALL NOT determine the selected action by raw `argmax` over `utility_score`.
3. WHEN the Consensus_Protocol maps a proposal to its objective for binding arbitration, THE Consensus_Protocol SHALL use the existing `_AGENT_TO_OBJECTIVE` / `_AGENT_OBJECTIVE` table and the `OBJECTIVES` ordering defined in `pareto.py`.
4. WHEN two or more candidate proposals receive weighted scores that are equal within a tolerance of 1e-9 under the Pareto-knee weights, THE Consensus_Protocol SHALL break the tie deterministically by preferring the proposal whose mapped objective appears earliest in the `OBJECTIVES` ordering, and SHALL break any remaining tie by ascending agent name.
5. IF a candidate proposal has no entry in the Agent_Objective_Map, THEN THE Consensus_Protocol SHALL exclude that proposal from binding-arbitration selection and SHALL record the exclusion without assigning it a fabricated score (I-7).
6. WHERE a decision follows the Tier-1 or Tier-2 fast path that does not run Pareto arbitration, THE Consensus_Protocol SHALL retain the existing fast-path selection behavior.

### Requirement 2: Binding Arbitration Is Deterministic and Auditable

**User Story:** As a compliance reviewer, I want binding arbitration to be deterministic and recorded in the audit trail, so that every ratified decision can be reproduced and explained after the fact.

#### Acceptance Criteria

1. WHEN the Consensus_Protocol selects a ratified action through binding arbitration with a fixed set of proposals and a fixed Pareto-knee weight vector, THE Consensus_Protocol SHALL produce the same selected action — defined as the identical selected proposal identity and a byte-identical serialized action — on every repeated execution with those identical inputs, including across separate process invocations.
2. WHEN the Consensus_Protocol produces a ratified decision, THE Consensus_Protocol SHALL include in the decision's `audit_trace` the Pareto-knee weight vector, the per-objective weighted score for every candidate proposal evaluated, and the identity of the selected proposal.
3. WHEN the Consensus_Protocol serializes a ratified decision through `to_deterministic_json`, THE Consensus_Protocol SHALL produce byte-identical output for identical decision inputs across repeated executions and separate process invocations.
4. WHEN the Consensus_Protocol records a binding-arbitration selection, THE Consensus_Protocol SHALL append it to the append-only context without mutating or removing prior context entries (I-14).
5. WHEN a tie occurs during binding-arbitration selection, THE Consensus_Protocol SHALL record the tie occurrence and the deterministic tie-break outcome in the decision's `audit_trace`.

### Requirement 3: Debate Revises Proposals via Rule-Based Concession

**User Story:** As an orchestrator operator, I want agents to actually revise their proposals during debate, so that conflicting proposals can converge through honest concession rather than the debate phase being a no-op that returns proposals unchanged.

#### Acceptance Criteria

1. WHEN the Debate_Coordinator detects a conflict among proposals using the existing `_detect_conflicts` 0.3 utility-divergence threshold, THE Debate_Coordinator SHALL invoke each conflicting agent's `debate_respond` and SHALL replace that agent's prior proposal for the next round only with a returned revision that passed schema validation, retaining the prior proposal otherwise.
2. WHEN an Agent_Handler receives a `debate_respond` request during a conflicting round, THE Agent_Handler SHALL compute the consensus position as the arithmetic mean of the current round's proposal `utility_score` values and SHALL return either a maintained position or a revised proposal produced by bounded rule-based concession toward that consensus position.
3. WHEN an Agent_Handler produces a concession, THE Agent_Handler SHALL bound the magnitude of the revision so that a single round moves its `utility_score` toward the consensus position by no more than 50 percent of the distance between its current `utility_score` and the consensus position, and SHALL NOT move the `utility_score` past the consensus position.
4. WHEN the Debate_Coordinator applies revised proposals, THE Debate_Coordinator SHALL evaluate convergence using the existing `_check_convergence` variance < 0.1 rule and stop debate when convergence is reached.
5. THE Debate_Coordinator SHALL limit the number of debate rounds to `debate_max_rounds`, a positive integer of at least 1, and SHALL stop debate once that number of rounds has executed even if convergence has not been reached.
6. WHEN an Agent_Handler revises a proposal during debate, THE Agent_Handler SHALL validate the revised payload against its `proto/domain/` schema before returning it (I-3).
7. WHEN an Agent_Handler returns a revised proposal, THE Agent_Handler SHALL report the revision honestly such that the returned `utility_score` and `payload` reflect the actual revised position and not a fabricated value (I-7).
8. WHEN the Debate_Coordinator records each debate round, THE Debate_Coordinator SHALL append the round's revisions to the append-only context without altering prior entries (I-14).
9. IF an Agent_Handler's current `utility_score` already lies within the `_check_convergence` variance < 0.1 bound of the consensus position, THEN THE Agent_Handler SHALL return a maintained position rather than a revised proposal.
10. IF a revised payload fails validation against its `proto/domain/` schema, THEN THE Agent_Handler SHALL return its maintained prior position and SHALL NOT return the invalid revision (I-3, I-7).

### Requirement 4: Debate Degrades Honestly When the LLM Is Unavailable

**User Story:** As an orchestrator operator, I want debate to continue safely when the LLM is unreachable, so that a degraded mediator never stalls or fabricates a decision.

#### Acceptance Criteria

1. IF the LLM connection fails, returns an error, or does not respond within the bounded per-round LLM timeout of 30 seconds during a debate round, THEN THE Debate_Coordinator SHALL treat the LLM as unavailable, append a degraded-round entry recording the failure reason to the append-only context (I-14), and proceed to arbitration using the most recent set of proposals collected (the current round's revisions where present, otherwise the prior round's proposals).
2. WHILE the LLM is unavailable, THE Debate_Coordinator SHALL continue to permit rule-based concession revisions, because Concession does not require the LLM.
3. WHEN the Debate_Coordinator records a debate round in which the LLM was unavailable, THE Debate_Coordinator SHALL mark that round entry with an explicit degraded indicator and the failure reason so that the audit trail distinguishes a degraded round from a normal round (I-7).
4. IF the LLM is unavailable, THEN THE Debate_Coordinator SHALL complete the decision within the `debate_max_rounds` bound and SHALL NOT retry a single LLM invocation more than a total of 2 attempts before treating it as unavailable, rather than retrying indefinitely.

### Requirement 5: Universal Real Actuation Across All Eight Agents

**User Story:** As a system architect, I want every one of the eight agents to actuate the standing world for real on `execute()`, so that the autonomous loop is universal rather than limited to the two-agent vertical slice.

#### Acceptance Criteria

1. WHEN an Agent_Handler for `routing_navigator`, `pricing_oracle`, `demand_prophet`, `disruption_shield`, `freshness_guardian`, or `sustainability_agent` receives an `execute` request with a ratified proposal, THE Agent_Handler SHALL apply one `WorldAction` to the World_Runtime through the injected `Actuator`/`WorldActuator` for each actionable item in the proposal — an actionable item being a proposal item that supplies a ratified value for the agent's mapped WorldActionKind lever — using the WorldActionKind appropriate to that agent's objective.
2. WHEN the `pricing_oracle` Agent_Handler actuates, THE Agent_Handler SHALL apply a `SET_PRICE_MULT` WorldAction whose price multiplier lies within the lever's accepted range defined by the World_Runtime, so that the ratified price multiplier scales world demand through the existing price lever.
3. WHEN the `demand_prophet` Agent_Handler actuates, THE Agent_Handler SHALL apply a `SET_POLICY` WorldAction using the `demand_mult` lever within the lever's accepted range defined by the World_Runtime, so that the ratified demand expectation adjusts the world's demand policy.
4. WHEN the `routing_navigator` Agent_Handler actuates, THE Agent_Handler SHALL apply a `SET_POLICY` WorldAction using the `dispatch_speed` lever within the lever's accepted range defined by the World_Runtime, so that the ratified routing decision adjusts the world's dispatch policy.
5. WHEN the `disruption_shield` Agent_Handler actuates, THE Agent_Handler SHALL apply a `SET_POLICY` WorldAction using the `lead_time_mult` lever within the lever's accepted range defined by the World_Runtime, so that a ratified mitigation adjusts the world's lead-time policy.
6. WHEN an Agent_Handler applies a `WorldAction` that the World_Runtime accepts and applies an effect for, THE Agent_Handler SHALL return status `"executed"`.
7. WHEN an Agent_Handler event-sources its ratified result to Kafka, THE Agent_Handler SHALL set `kafka_published` to reflect an actual successful produce and SHALL NOT return a bare `True` when no produce occurred (I-7).
8. WHEN an Agent_Handler applies a `WorldAction`, THE Agent_Handler SHALL route the action to the correct city's World_Runtime using the `city` supplied in the execute request.
9. IF the `city` supplied in the execute request is missing or does not correspond to a known World_Runtime, THEN THE Agent_Handler SHALL NOT report status `"executed"` and SHALL NOT report a fabricated world effect.
10. IF a ratified proposal contains no actionable item for the agent's mapped lever, THEN THE Agent_Handler SHALL NOT report status `"executed"` and SHALL report that no world effect was applied.

### Requirement 6: Agents Without a Natural World Mutation Diverge Honestly

**User Story:** As a system architect, I want agents whose objective has no natural world-mutation lever to be explicitly flagged and to report an honest divergence, so that the system never fabricates an actuation effect that did not occur.

#### Acceptance Criteria

1. WHERE an agent's objective has no corresponding WorldActionKind in the World_Runtime, THE Agent_Handler SHALL either actuate through a newly defined WorldActionKind that mutates the relevant world state, or return an Honest No-Op whose result reports that no world effect was applied and for which the World_Runtime state observed via `perceive()` immediately after the execute request is identical to the state observed immediately before it.
2. THE `sustainability_agent` Agent_Handler SHALL be treated as having no natural world mutation for `carbon_efficiency` under the current World_Runtime levers, and SHALL either drive a newly defined carbon-related WorldActionKind or return an Honest No-Op, and WHEN it returns an Honest No-Op it SHALL NOT report status `"executed"`.
3. THE `freshness_guardian` Agent_Handler SHALL be treated as having no direct spoilage-reduction lever under the current World_Runtime levers, and SHALL either drive a newly defined freshness-related WorldActionKind or actuate through the closest existing `SET_POLICY` lever that changes the World_Runtime spoilage-relevant state observed via `perceive()`, or return an Honest No-Op.
4. WHEN an Agent_Handler applies a `WorldAction` and the World_Runtime objective-relevant state observed via `perceive()` immediately after the apply is identical to the state observed immediately before the apply, THE Agent_Handler SHALL return status `"diverged"` rather than `"executed"`.
5. WHEN an Agent_Handler returns an Honest No-Op, THE Agent_Handler SHALL set its result status to `"diverged"` or an explicit no-actuation status, SHALL record that no world mutation was applied, and SHALL NOT set status `"executed"` or any world-effect field to a value that implies a world change occurred (I-7).
6. WHEN an Agent_Handler returns a Divergence or an Honest No-Op, THE Agent_Handler SHALL append the no-effect outcome to the append-only audit/provenance record without removing or mutating prior entries (I-14).

### Requirement 7: Actuation Degrades Honestly When World or Kafka Is Unavailable

**User Story:** As an operator, I want each agent's actuation to degrade honestly when the world or Kafka is unavailable, so that an outage produces a truthful status rather than a fabricated success.

#### Acceptance Criteria

1. IF the injected `Actuator`/`WorldActuator` is absent or its `apply_action` raises an error when an Agent_Handler attempts actuation, THEN THE Agent_Handler SHALL return status `"diverged"` reflecting that no world effect was applied and SHALL NOT report `"executed"`.
2. IF the Kafka producer is unavailable, or a produce does not complete within a bounded produce timeout of 5 seconds, when an Agent_Handler attempts event-sourcing, THEN THE Agent_Handler SHALL set `kafka_published` to `false` and SHALL return its result to the caller without propagating an exception.
3. WHEN an Agent_Handler degrades due to an unavailable world or Kafka, THE Agent_Handler SHALL log the degradation with the agent name and the reason (I-7).
4. WHEN an Agent_Handler returns its execute result, THE Agent_Handler SHALL include the world effect actually applied by the World_Runtime, reporting a zero or empty effect when none was applied, so that the orchestrator's outcome scorer reads a real actuation signal rather than a constant.

### Requirement 8: Anti-Regression Ratchet Reaches Zero and Cannot Increase

**User Story:** As a maintainer, I want the agency-truth ratchet to drop to zero and stay there, so that the autonomy this feature delivers can never silently regress to status-dict stubs.

#### Acceptance Criteria

1. WHEN all eight agents have been converted to real actuation or Honest No-Op actuation, THE Agency_Truth_Gate SHALL emit a Stub_Execute count of exactly 0 in its `--check` output.
2. WHEN the broaden-to-8 work completes, THE Agency_Truth_Gate ratchet ceiling `DEFAULT_MAX_STUBS` SHALL be 0.
3. IF the count of Stub_Execute agents exceeds the ratchet ceiling, THEN THE Agency_Truth_Gate SHALL fail its `--check` run with a non-zero exit code and SHALL identify each agent counted as a Stub_Execute.
4. WHEN the count of Stub_Execute agents is less than or equal to the ratchet ceiling, THE Agency_Truth_Gate SHALL terminate its `--check` run with a zero exit code.
5. THE Agency_Truth_Gate ratchet ceiling `DEFAULT_MAX_STUBS` SHALL NOT be increased above its committed value once set.
6. WHEN an Agent_Handler `execute()` performs actuation through an `apply` or `produce` call, THE Agency_Truth_Gate SHALL classify that agent as converted rather than as a Stub_Execute.
7. WHILE the Agency_Truth_Gate runs its `--check`, THE Agency_Truth_Gate SHALL enforce the five existing structural loop invariants (`autonomous_trigger`, `sensor_wired`, `standing_world`, `learn_from_world`, `real_actuation`) and SHALL return a non-zero exit code if any one regresses.

### Requirement 9: Binding Arbitration and Real Actuation Are Independently Verifiable

**User Story:** As a reviewer, I want binding arbitration and universal real actuation to each be independently verifiable, so that I can confirm each capability is genuine without relying on the other.

#### Acceptance Criteria

1. THE Agency_Truth_Gate SHALL expose a structured, deterministic signal that distinguishes a system using binding arbitration from one using raw `argmax` selection.
2. THE Agency_Truth_Gate SHALL expose an integer actuation-count signal in the range 0 to 8 that counts converted agents, computed independently of the binding-arbitration check.
3. WHEN `verify_claims` (C57) runs, THE Agency_Truth_Gate SHALL contribute its structured verdict.
4. IF the system selects the ratified action by raw `argmax`, or fewer than 8 agents are converted, THEN THE Agency_Truth_Gate SHALL cause `verify_claims` (C57) to fail.
5. IF any tracked regression is present WHEN `make verify-agency` runs, THEN THE Agency_Truth_Gate SHALL execute its `--check` and return a non-zero exit code, otherwise it SHALL return a zero exit code.
6. THE feature SHALL provide an end-to-end test, following the pattern of `orchestrator/tests/test_agentic_loop_e2e.py`, that proves the ratified action is the Pareto-knee selection and not the raw `argmax` selection in a case where the two diverge.
7. THE feature SHALL provide an end-to-end test that proves real actuation by observing a World_Runtime state change and a resulting `"executed"` status.

### Requirement 10: Quality, Determinism, and Coverage Floors Are Preserved

**User Story:** As a maintainer, I want all new code to honor the repository's existing quality invariants, so that completing the loop does not lower the engineering standard.

#### Acceptance Criteria

1. WHEN the feature emits or revises an agent payload, THE feature SHALL validate that payload against its `proto/domain/` schema before the payload is used downstream, and IF the payload fails schema validation, THEN THE feature SHALL reject it and SHALL NOT propagate the invalid payload (I-3).
2. WHEN the feature produces a decision, debate, or actuation record, THE feature SHALL append that record to the existing audit and provenance structures without removing or mutating any prior entry (I-14).
3. THE feature source SHALL pass `ruff` lint such that the number of `ruff` violations introduced by the feature, measured against the pre-feature baseline on the same `ruff` configuration, is zero.
4. THE feature source SHALL pass `mypy --strict` such that the number of `mypy --strict` errors introduced by the feature, measured against the pre-feature baseline on the same configuration, is zero.
5. THE feature SHALL provide property-based and unit tests covering binding arbitration, debate concession, and each of the eight converted agents' actuation, such that the repository's existing coverage-gate threshold is met or exceeded and is not lowered by the feature.
6. WHEN binding-arbitration selection is evaluated at least twice with identical valid proposal sets and identical Pareto-knee weight vectors, THE selection SHALL yield the identical selected action across all evaluations (round-trip determinism property).
7. WHEN a converted Agent_Handler's `execute()` is tested with an unavailable World_Runtime and an unavailable Kafka producer, THE Agent_Handler SHALL return a result whose status is not `"executed"`, SHALL set `kafka_published` to `false`, and SHALL NOT report any world effect that did not occur (degradation property).
