# Requirements Document

## Introduction

SYNAPSE can already prove it is honest, safe, well-tested, and auditable. It cannot yet prove it is
*intelligent*: nowhere does the codebase measure whether its four-tier consensus decisions produce
better business outcomes (fill rate, delivery time, spoilage/waste, stockouts, margin, CO2) than a
transparent baseline policy operating on the same demand.

The closest existing artifact, `tests/oracle/`, runs the SimPy digital twin **open-loop**: for
example `test_disruption_response_oracle` compares twin-under-shock against twin-under-no-shock, and
SYNAPSE's consensus decision is absent from **both** arms. `test_pricing_impact_oracle` is worse — its
docstring promises "revenue within 20% of predicted delta" while its body only asserts
`n_scenarios == 1000` and `orders_delivered >= 0`. The prose claims intelligence the code never tests.

The instruments to run the missing experiment already exist and were verified this session: the twin
is Tier-4-wired (C7), an append-only `decision_outcomes` stream exists (C51), conformal coverage is
enforced (C40), and twin-fidelity is measured via `synapse_digital_twin_kl_divergence` (C34). The
closed-loop counterfactual experiment itself has never been run.

The **Decision-Integrity Uplift Proof** feature is a reproducible, CI-gated harness that proves — or
honestly refutes — that SYNAPSE's consensus decisions beat a transparent baseline policy on business
KPIs, on the existing SimPy twin. It follows the repo's established honesty-culture pattern: every
prose claim is backed by an executable gate, results are ratcheted, twin-fidelity is disclosed with
every uplift number, and honest negative or mixed findings are treated as valid successful outcomes,
not failures.

### Scope and Constraints

- **$0 cost**: The harness runs entirely on the local SimPy twin with synthetic-only data. No live
  customer pipeline, no external paid services, no real users.
- **Synthetic-only data**: All demand is seed-generated. No live customer data is consumed.
- **Solo-developer cadence**: The harness is one-command reproducible and self-contained.
- **Fidelity-bounded validity**: The uplift number's validity is bounded by twin fidelity; that bound
  MUST be stated openly alongside every reported result.
- **Honest results are successes**: A finding such as "SYNAPSE beats baseline on fill-rate but loses on
  margin under supplier-default" is a credible, valid outcome, not a failure of the feature.

## Glossary

- **Uplift_Harness**: The closed-loop counterfactual system that runs identical seeded demand scenarios
  through the SYNAPSE consensus arm and each baseline arm on the same SimPy twin and records a KPI
  vector per run.
- **Consensus_Arm**: The experimental arm in which SYNAPSE's four-tier consensus orchestrator produces
  the decisions applied to the twin.
- **Baseline_Arm**: A control arm in which a single transparent Baseline_Policy produces the decisions
  applied to the twin.
- **Baseline_Policy**: A transparent, documented control policy representing "what a competent operator
  does without SYNAPSE". The suite comprises Par_Level_Reorder, Static_Pricing, Greedy_Routing, and
  No_Op_Disruption.
- **Par_Level_Reorder**: An (s, S) reordering baseline policy that reorders up to level S when inventory
  falls to or below reorder point s.
- **Static_Pricing**: A static / cost-plus pricing baseline policy that sets price as a fixed markup
  over unit cost.
- **Greedy_Routing**: A greedy nearest-store routing baseline policy that assigns each order to the
  nearest eligible store.
- **No_Op_Disruption**: A disruption-response baseline policy that takes no corrective action when a
  disruption occurs.
- **Scenario**: A seeded demand realization plus shock parameters that is replayable and identical
  across arms.
- **KPI_Vector**: The recorded set of business KPIs for one run: fill_rate, avg_delivery_time_min,
  spoilage_rate (waste), stockout_rate, margin, and co2_estimate.
- **Metric_Contract**: A pre-registered declaration of primary KPI(s), effect-size measure,
  significance test, minimum detectable effect, and the decision rule for "SYNAPSE wins".
- **Minimum_Detectable_Effect (MDE)**: The pre-declared smallest effect size the harness is powered to
  detect, fixed before results are produced.
- **Adversarial_Scenario_Suite**: The set of stress scenarios (demand spike, supplier default, monsoon
  disruption, cold-start city) run through every arm.
- **Fidelity_Report**: The reported twin KL-divergence value (`synapse_digital_twin_kl_divergence`,
  C34) that accompanies every uplift claim.
- **Uplift_Truth_Gate**: The honesty gate (`scripts/audit/uplift_truth.py` + a `verify_claims` row)
  that fails CI when measured uplift regresses below a ratcheted floor.
- **Uplift_Floor**: The ratcheted minimum uplift value below which the Uplift_Truth_Gate fails, in the
  BASELINE-ratchet style of `scripts/audit/training_truth.py`.
- **Reproduction_Command**: The single command `make prove-uplift` that regenerates the headline uplift
  number (within a stated noise tolerance) on a clean clone.
- **Oracle_Test_Auditor**: The gate that verifies each `tests/oracle/` test's prose docstring matches
  what the test body actually asserts.
- **Twin**: The existing SimPy digital twin driven by `digital_twin.simulation.monte_carlo.MonteCarloRunner`.
- **Verify_Claims**: The repo's existing `scripts/audit/verify_claims.py` mechanical claim-verification
  gate, whose check rows are mirrored in `docs/state/CURRENT.md`.

## Requirements

### Requirement 1: Baseline policies as first-class, tested control code

**User Story:** As a solo developer proving SYNAPSE's intelligence, I want transparent baseline
policies implemented as first-class tested code, so that I have a defensible control arm representing
"what a competent operator does without SYNAPSE".

#### Acceptance Criteria

1. THE Baseline_Policy_Suite SHALL provide Par_Level_Reorder, Static_Pricing, Greedy_Routing, and
   No_Op_Disruption as importable policy implementations.
2. WHEN Par_Level_Reorder receives an inventory level at or below reorder point s, where s and S
   satisfy 0 ≤ s < S, THE Par_Level_Reorder SHALL emit a reorder quantity equal to level S minus the
   projected inventory level.
3. WHEN Static_Pricing receives a non-negative unit cost, THE Static_Pricing SHALL return a price equal
   to the unit cost multiplied by a fixed configured markup factor that is greater than or equal to 1.0.
4. WHEN Greedy_Routing receives an order and a non-empty set of eligible stores, THE Greedy_Routing
   SHALL assign the order to the eligible store with the smallest distance to the order destination,
   and SHALL break ties among equidistant stores by selecting the store with the lowest store
   identifier.
5. WHEN No_Op_Disruption receives a disruption event, THE No_Op_Disruption SHALL return an empty action
   set.
6. THE Baseline_Policy_Suite SHALL expose each Baseline_Policy through a decision interface identical to
   the interface the Consensus_Arm uses to act on the Twin.
7. THE Baseline_Policy_Suite SHALL include automated tests that assert each Baseline_Policy's documented
   behavior.
8. THE Baseline_Policy_Suite SHALL include, for each Baseline_Policy, documentation that states the
   policy rule in plain language and identifies it as the control representing operation without SYNAPSE.
9. WHERE a Baseline_Policy is configured with a deterministic seed, THE Baseline_Policy SHALL produce
   identical decisions for identical inputs across at least two consecutive runs.
10. IF Par_Level_Reorder receives an inventory level strictly above reorder point s, THEN THE
    Par_Level_Reorder SHALL emit a reorder quantity of zero.
11. IF Greedy_Routing receives an order with an empty set of eligible stores, THEN THE Greedy_Routing
    SHALL return no store assignment and an error indication identifying the order as unroutable, and
    SHALL leave the order's routing state unchanged.
12. IF Static_Pricing receives a negative unit cost, THEN THE Static_Pricing SHALL reject the input and
    return an error indication without producing a price.

### Requirement 2: Closed-loop counterfactual harness on identical seeded scenarios

**User Story:** As a developer measuring decision quality, I want a closed-loop harness that runs the
same seeded demand scenarios through the consensus arm and each baseline arm on the same twin, so that
KPI differences are attributable to the decision policy rather than to differing demand.

#### Acceptance Criteria

1. WHEN the Uplift_Harness runs a Scenario, THE Uplift_Harness SHALL apply the same seeded demand
   realization and shock parameters to the Consensus_Arm and to each Baseline_Arm.
2. WHILE a Scenario runs, THE Uplift_Harness SHALL, at each Twin simulation step and before advancing
   to the next step, feed the current Twin state to the active decision policy and apply that policy's
   returned decisions back into the Twin, forming a closed loop.
3. WHEN a Scenario completes for an arm, THE Uplift_Harness SHALL record one KPI_Vector for that arm
   containing fill_rate, spoilage_rate, and stockout_rate as fractions in the range 0.0 to 1.0,
   avg_delivery_time_min as a non-negative number of minutes, and margin and co2_estimate as numeric
   values.
4. THE Uplift_Harness SHALL ensure that at least 1000 completed scenarios per arm contribute to KPI
   aggregation, satisfying the Twin's INV-TW-002 minimum-scenario invariant.
5. IF the Consensus_Arm and a Baseline_Arm are run with the same scenario seed, THEN THE Uplift_Harness
   SHALL supply both arms the identical demand realization for that seed.
6. THE Uplift_Harness SHALL persist every recorded KPI_Vector with its arm identifier and scenario seed.
7. IF a decision policy is unavailable or raises an error during a Scenario, THEN THE Uplift_Harness
   SHALL record the affected arm and scenario seed as a failed run, exclude that run from KPI
   aggregation, and continue executing the remaining scenarios.
8. THE Uplift_Harness SHALL compute, per arm, the mean and standard deviation of each KPI across all
   completed scenarios.
9. WHEN the Uplift_Harness finishes a run, THE Uplift_Harness SHALL report, per arm, the count of
   completed scenarios and the count of failed runs.

### Requirement 3: Pre-registered metric contract

**User Story:** As a developer committed to honest measurement, I want a pre-registered metric contract
declaring the primary KPI, effect size, significance test, minimum detectable effect, and decision
rule, so that the result cannot be produced by metric-shopping after the fact.

#### Acceptance Criteria

1. THE Metric_Contract SHALL declare the primary KPI or KPIs — a non-empty subset of the KPI_Vector
   fields — used to judge whether SYNAPSE wins, and SHALL declare for each the improvement direction
   (whether a higher or lower value is better).
2. THE Metric_Contract SHALL declare the effect-size measure as Cohen's d and relative percentage
   change between the Consensus_Arm and the Baseline_Arm.
3. THE Metric_Contract SHALL declare the significance test applied to the per-scenario KPI
   distributions and a numeric significance level in the open interval (0, 1).
4. THE Metric_Contract SHALL declare a numeric Minimum_Detectable_Effect, expressed as an effect-size
   value, for each primary KPI, fixed before any result is produced.
5. THE Metric_Contract SHALL declare a decision rule that maps computed effect size, significance, and
   Minimum_Detectable_Effect to exactly one outcome — "SYNAPSE wins", "baseline wins", or
   "tie / inconclusive" — such that the same inputs always yield the same outcome (a deterministic
   if-and-only-if mapping).
6. THE Metric_Contract SHALL be stored as a version-controlled artifact that is read by the
   Uplift_Harness rather than embedded ad hoc in analysis code.
7. WHEN the Uplift_Harness evaluates a result, THE Uplift_Harness SHALL apply the decision rule exactly
   as declared in the Metric_Contract.
8. IF a reported KPI is not declared in the Metric_Contract as a primary KPI, THEN THE Uplift_Harness
   SHALL label that KPI as secondary in the result output.
9. THE Metric_Contract SHALL be committed to version control before any result generated under it is
   reported, and WHEN the Metric_Contract is changed, THE change SHALL be recorded in version control
   before results generated under the new contract are reported.
10. IF the Uplift_Harness reads a Metric_Contract that is missing or malformed, THEN THE Uplift_Harness
    SHALL exit with a failure status and report the contract as invalid without producing an uplift
    outcome.

### Requirement 4: Adversarial scenario suite with mandatory honest-loss reporting

**User Story:** As a developer who values credibility over marketing, I want an adversarial scenario
suite that reports where the baseline wins or ties as well as where SYNAPSE wins, so that the proof is
honest rather than cherry-picked.

#### Acceptance Criteria

1. THE Adversarial_Scenario_Suite SHALL include exactly four seeded, replayable Scenarios — a
   demand-spike Scenario, a supplier-default Scenario, a monsoon-disruption Scenario, and a
   cold-start-city Scenario — each supplying an identical demand realization across all arms.
2. WHEN the Adversarial_Scenario_Suite runs, THE Uplift_Harness SHALL execute every Scenario through
   the Consensus_Arm and through each Baseline_Arm using the same scenario seed across all arms for a
   given Scenario.
3. WHEN the Uplift_Harness produces the adversarial result, THE Uplift_Harness SHALL classify each
   (Scenario, primary KPI) pair into exactly one outcome — "SYNAPSE wins", "baseline wins", or
   "tie / inconclusive" — determined by the decision rule declared in the Metric_Contract.
4. THE Uplift_Harness SHALL report every executed Scenario in the adversarial result and SHALL NOT
   omit or filter any Scenario on the basis of its outcome.
5. IF every (Scenario, primary KPI) pair is classified "SYNAPSE wins" with no baseline win or tie,
   THEN THE Uplift_Harness SHALL emit, in the result output, a warning that the absence of any
   baseline win or tie is itself a signal to scrutinize the harness.
6. THE Uplift_Harness SHALL treat any completed adversarial run as a valid outcome and SHALL exit with
   a success status regardless of which arm wins.
7. IF an adversarial Scenario cannot complete for an arm, THEN THE Uplift_Harness SHALL record a failed
   run, mark the adversarial result as incomplete, and SHALL NOT default the affected (Scenario,
   primary KPI) pair to "SYNAPSE wins".

### Requirement 5: Mandatory twin-fidelity disclosure with every uplift claim

**User Story:** As a reader judging an uplift claim, I want the twin's KL divergence reported alongside
every uplift number, so that I can judge how much to trust the claim given the twin's fidelity to
reality.

#### Acceptance Criteria

1. WHEN the Uplift_Harness reports an uplift number, THE Uplift_Harness SHALL include the
   Fidelity_Report as the numeric KL-divergence value sourced from `synapse_digital_twin_kl_divergence`
   (C34).
2. WHEN the Uplift_Harness reports an uplift number, THE Uplift_Harness SHALL state, co-located with
   that number, that the validity of the uplift number is bounded by twin fidelity.
3. IF the Fidelity_Report value is unavailable at report time, THEN THE Uplift_Harness SHALL mark the
   fidelity as "unknown" and SHALL NOT present the uplift number as fidelity-validated.
4. IF the Fidelity_Report value is strictly greater than the C34 re-sync threshold, THEN THE
   Uplift_Harness SHALL annotate the uplift result as low-confidence due to twin divergence.
5. IF the Fidelity_Report value is at or below the C34 re-sync threshold, THEN THE Uplift_Harness SHALL
   annotate the uplift result as within the twin-fidelity bound.
6. THE Uplift_Harness SHALL co-locate, for each reported uplift number, the Fidelity_Report value, its
   comparison to the C34 re-sync threshold, and the resulting confidence annotation in the same result
   output, so that no uplift number is presented without its fidelity context.

### Requirement 6: Uplift_truth honesty gate with ratcheted floor

**User Story:** As a maintainer of the honesty culture, I want an `uplift_truth` gate that fails CI when
measured uplift regresses below a ratcheted floor, so that a proven gain cannot silently rot away.

#### Acceptance Criteria

1. THE Uplift_Truth_Gate SHALL be implemented as `scripts/audit/uplift_truth.py` and SHALL expose a
   `--check` mode.
2. THE Uplift_Truth_Gate SHALL define the Uplift_Floor as a single declared numeric BASELINE constant
   in the ratchet style of `scripts/audit/training_truth.py`.
3. WHEN measured uplift is greater than or equal to the Uplift_Floor, THE Uplift_Truth_Gate SHALL exit
   with exit code 0.
4. IF measured uplift is strictly below the Uplift_Floor, THEN THE Uplift_Truth_Gate SHALL exit with
   exit code 1 and SHALL emit the measured value, the Uplift_Floor, and a regression indication to its
   output.
5. IF the measured uplift is unavailable when the gate runs, THEN THE Uplift_Truth_Gate SHALL exit with
   a non-zero exit code distinct from the regression exit code and SHALL NOT report a passing result.
6. THE Uplift_Truth_Gate SHALL be surfaced as a new check row in `scripts/audit/verify_claims.py` with
   a corresponding row in `docs/state/CURRENT.md`, using check identifier C60 (the next identifier
   after the current highest, C59).
7. THE Uplift_Truth_Gate SHALL provide a `--json` output mode reporting measured uplift, the
   Uplift_Floor, and a boolean regression status field.
8. WHEN the Uplift_Floor is raised after a verified gain, THE Uplift_Truth_Gate SHALL record the new
   floor in version control and SHALL NOT record a floor lower than the previously committed value.

### Requirement 7: One-command reproduction

**User Story:** As a solo developer or reviewer on a clean clone, I want a single command that produces
the headline uplift number, so that the proof is reproducible without bespoke setup.

#### Acceptance Criteria

1. THE Reproduction_Command SHALL be invocable as `make prove-uplift`.
2. WHEN `make prove-uplift` runs on a clean clone — a freshly checked-out repository with no
   pre-existing harness artifacts and no manual configuration beyond the repository's declared setup —
   THE Reproduction_Command SHALL execute the Uplift_Harness and print the headline uplift number.
3. WHEN `make prove-uplift` is run repeatedly with the same configured seeds, THE Reproduction_Command
   SHALL reproduce the headline uplift number within a version-controlled noise tolerance not exceeding
   1.0 percentage point, measured as the absolute run-to-run difference.
4. WHEN `make prove-uplift` reports the headline uplift number, THE Reproduction_Command SHALL state
   the applied noise tolerance in its output.
5. THE Reproduction_Command SHALL run using synthetic, seed-generated data only and SHALL NOT consume
   any live customer data.
6. THE Reproduction_Command SHALL NOT require any external paid service.
7. WHEN `make prove-uplift` completes successfully, THE Reproduction_Command SHALL emit the headline
   uplift number together with its Fidelity_Report in the same output.
8. IF a required input for the Uplift_Harness is missing, THEN THE Reproduction_Command SHALL exit with
   a failure status, report the identity of the missing input, and SHALL NOT print a headline uplift
   number.

### Requirement 8: Repair the latent oracle honesty gap

**User Story:** As a maintainer of the code-honesty culture, I want the oracle tests' prose docstrings
to match what their code actually asserts, so that the test suite does not claim verification it never
performs.

#### Acceptance Criteria

1. WHEN `test_pricing_impact_oracle` runs, THE pricing-impact oracle test SHALL assert that the
   observed revenue impact is within 20% of the predicted delta stated in its docstring, and SHALL fail
   when that bound is not met, rather than only asserting scenario count and non-negative delivered
   orders.
2. THE Oracle_Test_Auditor SHALL flag a `tests/oracle/` test as a candidate mismatch when the test has
   a non-empty docstring that describes a measurable outcome for which the test body contains no
   assertion referencing that outcome.
3. IF a `tests/oracle/` test meets the mismatch condition, THEN THE Oracle_Test_Auditor SHALL report
   that test as a docstring-body mismatch, identifying the fully qualified test name and the specific
   unasserted claim.
4. THE Oracle_Test_Auditor SHALL provide a `--check` mode that exits non-zero when any unresolved
   docstring-body mismatch remains and exits zero when none remain.
5. WHEN a `tests/oracle/` test is repaired, THE repaired test SHALL either contain an assertion that
   verifies the behavior its docstring claims or have its docstring rewritten to describe what the test
   actually asserts.
6. THE Oracle_Test_Auditor SHALL be surfaced through the Verify_Claims gate (`verify_claims.py` plus a
   `docs/state/CURRENT.md` row) so that a reintroduced docstring-body mismatch fails CI.
7. IF a `tests/oracle/` test has no docstring or its docstring describes no measurable outcome, THEN THE
   Oracle_Test_Auditor SHALL NOT flag that test as a mismatch.
