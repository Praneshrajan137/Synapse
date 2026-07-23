# Implementation Plan: Decision-Integrity Uplift Proof

## Overview

This plan builds the closed-loop counterfactual uplift harness in a new top-level `uplift/` package,
plus two honesty gates under `scripts/audit/` and a `make prove-uplift` target. Work proceeds
bottom-up: core interfaces and data models first, then pure baseline policies, then KPI extraction and
persistence, the metric contract and decision rule, the closed-loop harness, the in-process consensus
arm, fidelity disclosure, result assembly, the ratcheted uplift-truth gate, the oracle auditor plus
pricing-oracle repair, and finally the CLI/Makefile reproduction command wired end-to-end.

Language: **Python** (specified by the design; uses `Protocol`, `@dataclass`, `numpy`, and
**Hypothesis** for property-based tests). Property tests are optional sub-tasks marked with `*` and each
validates one design correctness property. All work is `$0`, synthetic-seed-only, and in-process.

## Tasks

- [x] 1. Set up `uplift/` package and core interfaces and data models
  - Create `uplift/__init__.py` and `uplift/interfaces.py`
  - Define `DecisionPolicy` Protocol (`name`, `decide(obs) -> PolicyAction`), immutable `Observation`
    (inventory per SKU, sim time, delivery/spoilage/stockout counters, unit costs, active shock, pending
    order + eligible stores), and `PolicyAction` (per-SKU reorder qty, price, routing assignment,
    disruption action set; may be partial)
  - Define data models `Direction`, `Outcome`, `KpiVector`, `Scenario`, `ScenarioRun`, `ArmResult`,
    `UpliftResult` per the design Data Models section
  - _Requirements: 1.6, 2.3_

- [x] 2. Implement baseline policy suite as pure, tested control code
  - [x] 2.1 Implement `Par_Level_Reorder` in `uplift/baselines/par_level_reorder.py`
    - `(s, S)` policy with `0 ≤ s < S`; reorder `S − projected_level` when `level ≤ s`, else `0`
    - Construct with a deterministic seed; no hidden global state
    - _Requirements: 1.1, 1.2, 1.10_

  - [x] 2.2 Write property test for `Par_Level_Reorder`
    - **Feature: decision-integrity-uplift-proof, Property 1: Par_Level_Reorder honors the (s, S) rule**
    - Hypothesis strategy over `0 ≤ s < S` and inventory level; assert reorder qty branches
    - **Validates: Requirements 1.2, 1.10**

  - [x] 2.3 Implement `Static_Pricing` in `uplift/baselines/static_pricing.py`
    - `price = unit_cost × markup` for `markup ≥ 1.0` and `unit_cost ≥ 0`
    - Negative unit cost: reject with a typed error and produce no price
    - _Requirements: 1.1, 1.3, 1.12_

  - [x] 2.4 Write property test for `Static_Pricing`
    - **Feature: decision-integrity-uplift-proof, Property 2: Static_Pricing is cost-plus and never prices below cost**
    - Assert `price == unit_cost × markup ≥ unit_cost` for non-negative cost; assert error for negative cost
    - **Validates: Requirements 1.3, 1.12**

  - [x] 2.5 Implement `Greedy_Routing` in `uplift/baselines/greedy_routing.py`
    - Assign order to nearest eligible store; break ties by lowest store id
    - Empty eligible set: return no assignment + unroutable error, leave routing state unchanged
    - _Requirements: 1.1, 1.4, 1.11_

  - [x] 2.6 Write property test for `Greedy_Routing`
    - **Feature: decision-integrity-uplift-proof, Property 3: Greedy_Routing selects the nearest store with deterministic tie-breaking**
    - Generate orders + eligible store sets (incl. equidistant + empty); assert min-distance/lowest-id and unroutable edge
    - **Validates: Requirements 1.4, 1.11**

  - [x] 2.7 Implement `No_Op_Disruption` in `uplift/baselines/no_op_disruption.py`
    - Return an empty action set for any disruption event
    - _Requirements: 1.1, 1.5_

  - [x] 2.8 Write property test for `No_Op_Disruption`
    - **Feature: decision-integrity-uplift-proof, Property 4: No_Op_Disruption always returns an empty action set**
    - Generate arbitrary disruption events; assert returned action set is empty
    - **Validates: Requirements 1.5**

  - [x] 2.9 Wire baseline suite exports and documentation
    - Create `uplift/baselines/__init__.py` exporting all four policies through the `DecisionPolicy` interface
    - Create `uplift/baselines/README.md` stating each policy's rule in plain language and labelling it
      as the control representing operation without SYNAPSE
    - _Requirements: 1.1, 1.6, 1.7, 1.8_

  - [x] 2.10 Write determinism + interface-conformance tests for the baseline suite
    - **Feature: decision-integrity-uplift-proof, Property 5: Seeded baseline decisions are deterministic**
    - Property test: identical seed + observation ⇒ identical decisions across two consecutive runs
    - Unit test: each policy satisfies the `DecisionPolicy` interface and each has documented-behavior assertions
    - **Validates: Requirements 1.9** (and unit coverage for 1.7)

- [x] 3. Checkpoint - baseline policies
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement KPI extraction and persistence
  - [x] 4.1 Implement `KpiExtractor` in `uplift/kpi.py`
    - Derive `KpiVector` from twin `SimulationMetrics` + applied decisions: `fill_rate`, `spoilage_rate`,
      `stockout_rate` (harness-side unmet-demand counter), `avg_delivery_time_min`, `margin`, `co2_estimate`
    - Shared identically by both arms so derivation cannot bias attribution
    - _Requirements: 2.3_

  - [x] 4.2 Write property test for `KpiVector` range invariants
    - **Feature: decision-integrity-uplift-proof, Property 7: Every recorded KPI_Vector satisfies its range invariants**
    - Assert `fill_rate`/`spoilage_rate`/`stockout_rate ∈ [0,1]`, `avg_delivery_time_min ≥ 0` finite, `margin`/`co2_estimate` finite
    - **Validates: Requirements 2.3**

  - [x] 4.3 Implement KPI persistence in `uplift/persistence.py`
    - Persist each `KpiVector` with its arm identifier and scenario seed; provide load/reload
    - _Requirements: 2.6_

  - [x] 4.4 Write property test for KPI persistence round-trip
    - **Feature: decision-integrity-uplift-proof, Property 8: KPI_Vector persistence round-trips**
    - Persist then reload a generated set; assert identical set with arm id + seed preserved
    - **Validates: Requirements 2.6**

- [x] 5. Implement the pre-registered metric contract and decision rule
  - [x] 5.1 Create `uplift/metric_contract.yaml` and the loader/validator in `uplift/contract.py`
    - Version-controlled artifact declaring `primary_kpis` + directions, `effect_size`,
      `significance_test`, `alpha`, per-KPI `mde`, and the decision rule
    - Loader builds an immutable `MetricContract`; validate schema, `alpha ∈ (0,1)`, non-empty primary
      KPIs, numeric MDEs; raise typed `MetricContractError` and exit with failure status (no uplift outcome)
      on missing/malformed contract
    - _Requirements: 3.1, 3.3, 3.4, 3.6, 3.9, 3.10_

  - [x] 5.2 Write unit tests for contract schema and malformed-contract handling
    - Valid contract loads; missing/malformed contract raises `MetricContractError` and yields failure/no outcome
    - _Requirements: 3.1, 3.3, 3.4, 3.10_

  - [x] 5.3 Implement effect-size computation and the `classify` decision rule in `uplift/contract.py`
    - Cohen's d + relative % change; declared significance test at `alpha`
    - Total deterministic `classify(consensus, baseline, kpi) -> Outcome` applying
      significant-and-favorable-and-meets-MDE rule
    - _Requirements: 3.2, 3.5_

  - [x] 5.4 Write property test for effect-size computation
    - **Feature: decision-integrity-uplift-proof, Property 11: Effect-size computation matches the reference formula**
    - Compare computed Cohen's d + relative % change against reference formulas over generated arrays
    - **Validates: Requirements 3.2**

  - [x] 5.5 Write property test for the decision rule
    - **Feature: decision-integrity-uplift-proof, Property 12: The decision rule is a total deterministic mapping**
    - Assert exactly one of `{SYNAPSE_WINS, BASELINE_WINS, TIE_INCONCLUSIVE}`; identical inputs ⇒ identical outcome
    - **Validates: Requirements 3.5**

- [x] 6. Checkpoint - KPI and contract layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement the adversarial scenario suite and closed-loop harness
  - [x] 7.1 Define scenarios in `uplift/scenarios.py`
    - Exactly four seeded, replayable `Scenario`s via `ShockParams`: demand-spike, supplier-default,
      monsoon-disruption, cold-start-city (empty initial inventory/freshness)
    - _Requirements: 4.1_

  - [x] 7.2 Implement `UpliftHarness` closed loop in `uplift/harness.py`
    - `run_scenario` / `run_arm` / `run`: `start` twin with scenario seed + shock, then repeatedly
      observe → `policy.decide` → apply `PolicyAction` → `advance(step)` until horizon (closed loop)
    - Same seed ⇒ identical demand realization + shocks across arms; guarantee ≥ 1000 completed scenarios
      per arm (INV-TW-002, `ValueError` guard on under-power); `ProcessPoolExecutor` parallelism
    - On policy error/unavailability: record failed `ScenarioRun`, exclude from aggregation, continue
    - Compute per-arm mean/std per KPI; report per-arm completed + failed counts
    - _Requirements: 2.1, 2.2, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9_

  - [x] 7.3 Write property test for identical seeded demand across arms
    - **Feature: decision-integrity-uplift-proof, Property 6: Arms receive identical seeded demand**
    - For a generated seed, assert consensus and every baseline arm receive identical demand + shock params
    - **Validates: Requirements 2.1, 2.5, 4.2**

  - [x] 7.4 Write property test for aggregation integrity under failures
    - **Feature: decision-integrity-uplift-proof, Property 9: Aggregation integrity under failures**
    - Arbitrary failing subset: failed runs excluded, completed aggregated, execution continues,
      completed + failed counts sum to attempts
    - **Validates: Requirements 2.7, 2.9**

  - [x] 7.5 Write property test for per-arm aggregate statistics
    - **Feature: decision-integrity-uplift-proof, Property 10: Per-arm aggregates match the reference statistics**
    - Assert harness per-arm mean/std equal reference mean/std over the completed set
    - **Validates: Requirements 2.8**

  - [x] 7.6 Write closed-loop cadence and INV-TW-002 guard unit tests
    - Spy test: at each step, decide is called with current state and returned action applied before `advance`
    - Requesting < 1000 scenarios per arm raises `ValueError`
    - _Requirements: 2.2, 2.4_

- [x] 8. Implement the in-process consensus arm adapter
  - [x] 8.1 Implement `ConsensusArm` in `uplift/consensus_arm.py`
    - Construct `ConsensusProtocol` with an in-process A2A transport dispatching to agents' + twin's
      in-process handler functions (no HTTP, no external service)
    - Map `Observation` → `decision_request`, run `run_consensus` on a per-scenario event loop, translate
      the binding `ConsensusDecision` action into a `PolicyAction`
    - On construction failure or `run_consensus` raise: surface as a failed run (never fabricate a decision)
    - _Requirements: 1.6, 2.2, 2.7_

- [x] 9. Implement twin-fidelity disclosure
  - [x] 9.1 Implement `FidelityReport` in `uplift/fidelity.py`
    - Read `synapse_digital_twin_kl_divergence` (C34) and compare to `TwinConfig.kl_divergence_threshold`
    - `confidence`: `unknown` when value unavailable (not fidelity-validated); `low_confidence_divergent`
      when `> threshold`; `within_fidelity_bound` when `≤ threshold`
    - _Requirements: 5.1, 5.3, 5.4, 5.5_

  - [x] 9.2 Write property test for fidelity annotation mapping
    - **Feature: decision-integrity-uplift-proof, Property 20: Fidelity annotation follows the C34 threshold mapping**
    - Generate KL values incl. `None`; assert the three-way confidence mapping against the threshold
    - **Validates: Requirements 5.3, 5.4, 5.5**

- [x] 10. Assemble uplift result, adversarial classification, and fidelity-co-located reporting
  - [x] 10.1 Implement result assembly + reporting in `uplift/harness.py`
    - Apply the contract decision rule exactly as declared; classify each `(scenario, primary KPI)` pair
      into exactly one outcome; label non-primary reported KPIs as secondary
    - Report every executed scenario without outcome-based filtering; emit all-wins self-scrutiny warning
      iff every pair is `SYNAPSE_WINS`; exit success for any completed run regardless of winner
    - On incomplete scenario: record failed run, mark result incomplete, never default pair to `SYNAPSE_WINS`
    - Co-locate each uplift number with its `FidelityReport` value, threshold comparison, confidence
      annotation, and the fixed fidelity-bound statement
    - _Requirements: 3.7, 3.8, 4.3, 4.4, 4.5, 4.6, 4.7, 5.2, 5.6_

  - [x] 10.2 Write property test that the harness applies the contract rule exactly
    - **Feature: decision-integrity-uplift-proof, Property 13: The harness applies the contract rule exactly as declared**
    - Assert harness outcome equals `MetricContract.classify` outcome for the same inputs
    - **Validates: Requirements 3.7**

  - [x] 10.3 Write property test for primary/secondary KPI partition
    - **Feature: decision-integrity-uplift-proof, Property 14: Reported KPIs partition into primary and secondary**
    - Every reported non-primary KPI is labelled secondary; no KPI labelled both
    - **Validates: Requirements 3.8**

  - [x] 10.4 Write property test that each (scenario, primary KPI) pair is classified once
    - **Feature: decision-integrity-uplift-proof, Property 15: Every (scenario, primary KPI) pair is classified exactly once**
    - **Validates: Requirements 4.3**

  - [x] 10.5 Write property test that every executed scenario is reported
    - **Feature: decision-integrity-uplift-proof, Property 16: Every executed scenario is reported without filtering**
    - Reported scenario set equals executed set for any outcome distribution
    - **Validates: Requirements 4.4**

  - [x] 10.6 Write property test for the all-wins self-scrutiny warning
    - **Feature: decision-integrity-uplift-proof, Property 17: All-wins triggers the self-scrutiny warning**
    - Warning emitted iff every pair is `SYNAPSE_WINS`
    - **Validates: Requirements 4.5**

  - [x] 10.7 Write property test that any completed adversarial run exits success
    - **Feature: decision-integrity-uplift-proof, Property 18: Any completed adversarial run exits success**
    - **Validates: Requirements 4.6**

  - [x] 10.8 Write property test that incomplete pairs are never credited to SYNAPSE
    - **Feature: decision-integrity-uplift-proof, Property 19: Incomplete pairs are never credited to SYNAPSE**
    - Incomplete scenario ⇒ failed run recorded, result marked incomplete, pair never `SYNAPSE_WINS`
    - **Validates: Requirements 4.7**

- [x] 11. Checkpoint - harness and results
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Implement the uplift-truth honesty gate (C60)
  - [x] 12.1 Implement `uplift/uplift_floor.py` and `scripts/audit/uplift_truth.py`
    - Single declared numeric `UPLIFT_FLOOR` BASELINE constant (ratchet style of `training_truth.py`)
    - `--check`: exit `0` when measured uplift `≥ UPLIFT_FLOOR`; exit `1` with measured value + floor +
      regression indication when `<`; distinct non-zero code (`2`) when uplift unavailable (never a pass)
    - `--json`: `{ "measured_uplift", "uplift_floor", "regression": bool }`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.7_

  - [x] 12.2 Write property test for gate exit codes
    - **Feature: decision-integrity-uplift-proof, Property 21: Uplift_truth gate exit codes follow the floor mapping**
    - Generate measured uplift + floor incl. unavailable; assert `0` / `1`(+payload) / distinct non-zero mapping
    - **Validates: Requirements 6.3, 6.4, 6.5**

  - [x] 12.3 Write property test for the uplift floor ratchet
    - **Feature: decision-integrity-uplift-proof, Property 22: The uplift floor ratchet is monotonic**
    - For any sequence of floor updates, committed floor is never below its previously committed value
    - **Validates: Requirements 6.8**

  - [x] 12.4 Wire C60 into `verify_claims.py` and `docs/state/CURRENT.md`
    - Add the `C60` uplift_truth check row to `scripts/audit/verify_claims.py` and the mirrored row in
      `docs/state/CURRENT.md`
    - _Requirements: 6.6_

- [x] 13. Implement the oracle test auditor and repair the pricing oracle
  - [x] 13.1 Implement `scripts/audit/oracle_truth.py`
    - AST-walk each `tests/oracle/` test; flag a mismatch when a non-empty docstring describes a
      measurable outcome for which the body has no assertion referencing it
    - Report fully qualified test name + specific unasserted claim; `--check` exits non-zero iff any
      unresolved mismatch; never flag no-docstring / no-measurable-outcome tests
    - _Requirements: 8.2, 8.3, 8.4, 8.7_

  - [x] 13.2 Write property test for the oracle auditor
    - **Feature: decision-integrity-uplift-proof, Property 24: The oracle auditor flags exactly the docstring-body mismatches**
    - Generate synthetic tests (with/without docstring, with/without asserting the claim); assert iff-flagging + `--check` behavior
    - **Validates: Requirements 8.2, 8.4, 8.7**

  - [x] 13.3 Repair `test_pricing_impact_oracle` in `tests/oracle/`
    - Run a price-changed arm and a baseline arm through the twin; assert observed revenue impact is
      within 20% of the docstring-predicted delta, failing when the bound is not met (replacing the
      `n_scenarios == 1000` / `orders_delivered >= 0` stand-ins)
    - _Requirements: 8.1, 8.5_

  - [x] 13.4 Wire the oracle auditor into `verify_claims.py` and `docs/state/CURRENT.md`
    - Add the oracle-auditor check row to `scripts/audit/verify_claims.py` and the mirrored row in
      `docs/state/CURRENT.md` so a reintroduced mismatch fails CI
    - _Requirements: 8.6_

- [x] 14. Wire the one-command reproduction end-to-end
  - [x] 14.1 Implement `uplift/cli.py` (`python -m uplift.cli`)
    - Run the harness on declared seeds; print the headline uplift number together with its `FidelityReport`
    - State the applied version-controlled noise tolerance (≤ 1.0 percentage point); synthetic seed data
      only; no external paid service
    - On a missing required input: exit failure, name the missing input, print no headline number
    - _Requirements: 5.2, 5.6, 7.2, 7.5, 7.6, 7.7, 7.8_

  - [x] 14.2 Add the `prove-uplift` target to the `Makefile`
    - `.PHONY` target invoking `python -m uplift.cli`, mirroring `verify-claims` / `verify-intelligence`
    - _Requirements: 7.1_

  - [x] 14.3 Write property test for reproduction stability
    - **Feature: decision-integrity-uplift-proof, Property 23: Reproduction is stable within the declared tolerance**
    - Reduced-cost seeded config, modest iterations: run-to-run headline diff ≤ 1.0 percentage point
    - **Validates: Requirements 7.3**

  - [x] 14.4 Write integration test for the reproduction command
    - Run `make prove-uplift` / CLI end-to-end on a small seeded config: headline number + fidelity printed,
      noise tolerance stated; missing-input case exits failure with named input and no number
    - _Requirements: 7.2, 7.3, 7.4, 7.8_

- [x] 15. Final checkpoint - full harness reproducible and gated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (property, unit, and integration tests) and can be skipped for a
  faster MVP; core implementation tasks are never optional.
- Each task references specific requirement clauses for traceability; each property test references its
  design property number and the requirement clauses it validates.
- Property-based tests use **Hypothesis** with a minimum of 100 iterations (Property 23 uses a
  reduced-cost seeded configuration and a modest iteration count since it drives the real twin).
- The one-command reproduction (7.2) and the repaired pricing oracle (8.1) are integration tests — they
  verify full-stack wiring/reproducibility rather than an input-varying property.
- Checkpoints ensure incremental validation at natural layer boundaries.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.3", "2.5", "2.7", "4.1", "5.1", "7.1", "8.1", "9.1", "12.1", "13.1", "13.3"] },
    { "id": 2, "tasks": ["2.2", "2.4", "2.6", "2.8", "2.9", "4.2", "4.3", "5.2", "5.3", "9.2", "12.2", "12.3", "13.2"] },
    { "id": 3, "tasks": ["2.10", "4.4", "5.4", "5.5", "7.2", "12.4"] },
    { "id": 4, "tasks": ["7.3", "7.4", "7.5", "7.6", "10.1", "13.4"] },
    { "id": 5, "tasks": ["10.2", "10.3", "10.4", "10.5", "10.6", "10.7", "10.8", "14.1"] },
    { "id": 6, "tasks": ["14.2", "14.3"] },
    { "id": 7, "tasks": ["14.4"] }
  ]
}
```
