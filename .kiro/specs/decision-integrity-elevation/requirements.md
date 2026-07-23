# Requirements Document

## Introduction

`decision-integrity-elevation` raises SYNAPSE from a demonstrably honest software artifact to a research-grade decision-evaluation artifact. Repository inspection supports claims that SYNAPSE has deterministic synthetic routing fixtures, a Monte Carlo digital twin, append-only audit and outcome records, runtime provenance, synthetic-decision labels, and external publication of audit-chain anchors. Repository inspection does **not** support the stronger claim that SYNAPSE decisions improve business outcomes over credible control policies under matched counterfactual conditions.

The current evaluation primarily checks `TierRouter.classify` against fixtures generated from the same routing thresholds. Existing counterfactual tests point at a nonexistent fixture directory and skip. Current twin oracles test simulator self-consistency and directional shocks, while current outcome scoring often records `unknown` because per-decision realized signals are incomplete. Main CI does not execute `tests/eval` or `tests/oracle`, and current reports do not provide paired policy effects, preregistration, multiplicity control, leakage defenses, ablations, or durable decision-quality evidence.

This feature therefore establishes an evaluation contract, not a predetermined positive conclusion. A valid result may show superiority, equivalence, inferiority, heterogeneous effects, or insufficient evidence. The feature preserves every valid negative or null result and keeps simulated evidence distinct from production evidence.

## Pre-Execution Decision-Integrity Review

### Verified facts

| Repository fact | Evidence | Consequence |
| --- | --- | --- |
| The REST simulation contract accepts shock multipliers, duration, and scenario count but no policy action, matched-policy identifier, or caller-supplied seed ledger. | `digital_twin/inference/serve.py:132-169`; `digital_twin/inference/serve.py:218-259` | The current endpoint cannot by itself estimate policy uplift. |
| The Monte Carlo runner assigns scenario seeds from `0` through `n-1`, calculates operational outcome distributions, and records wall-clock elapsed time. | `digital_twin/simulation/monte_carlo.py:22-60`; `digital_twin/simulation/monte_carlo.py:96-188` | Seeded simulation primitives are reusable, but full output artifacts are not content-deterministic and are not matched policy effects. |
| The Monte Carlo model labels outcome percentiles as confidence intervals without computing inferential intervals for a policy effect. | `digital_twin/simulation/monte_carlo.py:38-60`; `digital_twin/simulation/monte_carlo.py:96-188` | Outcome-distribution percentiles must remain distinct from inferential uncertainty. |
| The named counterfactual replay loads `tests/eval/golden`, while repository fixtures are stored under `tests/eval/golden_traces`; the implemented checks mutate routing inputs rather than compare policy actions and business outcomes. | `tests/eval/test_counterfactual_replay.py:1-91`; `tests/eval/golden_traces/` | Existing counterfactual tests do not establish decision-level uplift. |
| Outcome scoring preserves an `unknown` state and explicitly lacks a joinable per-decision twin-divergence signal. | `data_fabric/jobs/outcome_score.py:1-14`; `data_fabric/jobs/outcome_score.py:30-132` | Existing outcomes are an honesty primitive, not a comparative business-effect measure. |
| Append-only outcomes, audit provenance, synthetic labels, claim-verification scripts, calibration checks, and external audit-anchor publication already exist. | `infrastructure/postgres/08_sprint19_outcomes.sql`; `orchestrator/audit/logger.py`; `scripts/audit/`; `.github/workflows/publish-audit-anchor.yml` | The feature SHALL reuse these integrity capabilities rather than create parallel audit infrastructure. |
| `README.md` describes SYNAPSE as a simulation harness without a live customer pipeline. | `README.md:52-56` | Current decision-value evidence can support simulated claims, not demonstrated production impact. |
| Mainline documentation contains stale state claims relative to the current-state ledger. | `README.md:6-24`; `docs/state/CURRENT.md` | Public claims require mechanical synchronization with verified evidence. |

### Confirmed repository conclusion

The central hypothesis survives repository review in a bounded form: SYNAPSE contains substantial engineering-honesty mechanisms, but the reviewed repository does not contain mechanically reproducible evidence of decision-level business uplift against a credible policy under matched counterfactual conditions. This conclusion describes the inspected repository state; the feature does not assume that a future matched evaluation will favor SYNAPSE.

### Assumptions requiring validation

- A narrow Decision_Family can be expressed through the current orchestrator and Digital_Twin without replacing agent architectures.
- A defensible Status_Quo_Policy can be derived from documented domain practice or repository behavior without granting the Control_Policy privileged information.
- At least one Primary_Endpoint can be action-conditioned in the Digital_Twin and interpreted as a business outcome rather than a routing or software-quality proxy.
- Available compute can support a preregistered sample size after the required power, precision, and cost analysis.

### Hypotheses to test

- The SYNAPSE_Policy produces a practically relevant paired improvement over a versioned Status_Quo_Policy for one narrow Decision_Family within a qualified Digital_Twin Operating_Envelope.
- Uncertainty-aware selective action or abstention improves expected utility or guardrail compliance relative to forced action.
- Individual agents, tier selection, consensus, twin verification, and guardrails contribute measurable value commensurate with cost and latency.

### Risks

- Shared simulator misspecification can rank both policies incorrectly while producing precise-looking estimates.
- Reusing development scenarios for confirmation can optimize SYNAPSE to the Digital_Twin or leak expected outcomes.
- Arbitrary thresholds, optional CI jobs, skipped tests, or post-result analysis changes can manufacture credibility without information.
- Aggregate gains can conceal adverse tail, safety, cost, latency, or environmental effects.
- Evidence artifacts can drift from README, current-state, report, or portfolio claims.

### Tradeoffs

- Paired designs reduce stochastic variance but do not remove Digital_Twin model bias.
- Hidden holdouts reduce leakage but increase scenario-governance and regeneration cost.
- More scenarios improve precision but consume compute and environmental budget; sample size must follow a justified decision criterion rather than a vanity count.
- Strict claim gates may publish ties, losses, regressions, or inconclusive results; that cost is required for research-grade credibility.

### Decisions and priorities

1. **Smallest decisive proof:** evaluate one narrow Decision_Family end to end against a versioned Status_Quo_Policy and applicable No_Action_Policy before broadening coverage.
2. **Reuse before build:** extend the current Digital_Twin, audit/outcome schema, provenance, calibration, claim-verification, and external-anchor mechanisms rather than introducing parallel platforms.
3. **Claim boundary first:** label initial evidence `simulated` and withhold real-world causal claims until independent twin qualification or production experimentation exists.
4. **Precommit before scale:** freeze metrics, thresholds, seed/scenario governance, exclusions, decision rules, and analysis before confirmatory outcomes are visible.
5. **Evidence over infrastructure:** prioritize matched effects, uncertainty, failure regions, ablations, and independent recomputation over dashboards, orchestration layers, or feature expansion.

### Recommendations

- Make the existing Digital_Twin action-conditioned and capable of executing matched policy pairs before adding broader scenario catalogs.
- Use one primary business endpoint with a small set of cost, latency, safety, and environmental guardrails for the first proof.
- Require every threshold to carry a version, rationale, evidence source, approver, and preregistration hash; do not treat conventional numerical defaults as repository facts.
- Preserve and publish valid favorable, tied, adverse, regressed, and inconclusive outcomes with complete run accounting.

### Open questions

- Which narrow Decision_Family has the strongest credible Status_Quo_Policy and action-sensitive twin outcome today?
- Which independent observations, if any, can qualify the Digital_Twin Operating_Envelope?
- Which business stakeholder or documented source can justify the Minimum_Relevant_Effect and Guardrail_Metric margins?
- What compute, latency, monetary, safety, and environmental budgets constrain confirmatory precision?
- Which artifact host and immutable record can support public external verification without private credentials?

## Glossary
- **Decision_Integrity_Elevation_System**: The evaluation capability that specifies, executes, analyzes, gates, and publishes evidence about SYNAPSE decision quality.
- **SYNAPSE_Policy**: The complete decision path being evaluated, including participating agents, consensus, guardrails, fallbacks, and actuation choice.
- **Control_Policy**: A versioned comparator that receives the same permitted information and action constraints as the SYNAPSE_Policy.
- **Status_Quo_Policy**: A Control_Policy representing a documented current or conventional operating rule for a decision domain.
- **No_Action_Policy**: A Control_Policy that applies no discretionary intervention while retaining mandatory safety behavior.
- **Oracle_Policy**: A hindsight or privileged-information policy used only to estimate an upper bound and never presented as a deployable Control_Policy.
- **Decision_Family**: A preregistered class of comparable decisions sharing an action space, outcome horizon, and business objective.
- **Scenario**: A versioned initial state, exogenous event stream, observation schedule, action constraints, and evaluation horizon.
- **Scenario_Pair**: Two executions of one Scenario that differ only by evaluated policy.
- **Pair_ID**: A stable identifier derived from Scenario identity, Seed, and compared policy versions.
- **Seed**: A recorded input controlling every pseudorandom stream in one Scenario_Pair.
- **Exogenous_Event**: A scenario event that no evaluated policy controls.
- **Confirmatory_Corpus**: A frozen collection of Scenario_Pairs used once for preregistered confirmatory analysis.
- **Development_Corpus**: Scenarios available for implementation, debugging, and policy tuning.
- **Hidden_Holdout**: Confirmatory scenarios whose outcomes and generation parameters are unavailable to policy developers before the Preregistration is locked.
- **Evaluation_Manifest**: A machine-readable record binding an Evaluation_Run to code, data, configuration, models, policies, metrics, analysis, environment, and seeds.
- **Preregistration**: An immutable declaration of hypotheses, endpoints, populations, exclusions, sample size, effect thresholds, statistical methods, and correction families created before confirmatory outcomes are observed.
- **Metric_Ontology**: A versioned catalog defining every evaluation metric's identity, business meaning, unit, direction, population, horizon, aggregation, missingness, and evidence scope.
- **Primary_Endpoint**: The single confirmatory business-outcome metric selected for one Decision_Family.
- **Secondary_Endpoint**: A preregistered supportive metric that cannot independently establish the primary claim.
- **Exploratory_Endpoint**: A metric analyzed without confirmatory claim status.
- **Guardrail_Metric**: A metric with a preregistered non-inferiority or safety bound that a claimed improvement must respect.
- **Minimum_Relevant_Effect**: The preregistered smallest paired improvement that has practical business meaning.
- **Superiority_Claim**: A claim that a policy improves a Primary_Endpoint by at least the Minimum_Relevant_Effect with required uncertainty and multiplicity controls.
- **Non_Inferiority_Margin**: The largest preregistered acceptable degradation on a Guardrail_Metric.
- **Comparison_Family**: A preregistered set of confirmatory hypotheses controlled together for multiplicity.
- **Paired_Effect**: The within-Scenario difference between the SYNAPSE_Policy outcome and a Control_Policy outcome after metric direction normalization.
- **Confidence_Interval**: A preregistered inferential interval for a population effect estimate, distinct from outcome-distribution percentiles.
- **Confidence_Level**: A versioned, justified, and preregistered coverage target used to construct a Confidence_Interval.
- **Decision_Criterion**: A versioned and preregistered rule that maps practical effect, uncertainty, multiplicity, missingness, and Guardrail_Metric results to a claim status.
- **Adjusted_P_Value**: A hypothesis probability measure corrected within a Comparison_Family by the preregistered method.
- **Seed_Ledger**: An immutable mapping from each Pair_ID to every pseudorandom stream identifier and Seed used by policy, scenario, simulator, model, and analysis code.
- **Negative_Control**: A preregistered exposure, outcome, or policy contrast expected to show no policy effect and used to detect leakage, confounding, or evaluator defects.
- **Selective_Action_Profile**: A curve or table relating action coverage, abstention rate, decision utility, calibration, and Guardrail_Metric outcomes across preregistered uncertainty thresholds.
- **Resource_Tradeoff_Profile**: A matched comparison of decision value with monetary cost, compute use, latency, safety outcomes, and environmental impact.
- **Evidence_Maturity_Level**: One of `integrity_only`, `paired_simulation`, `qualified_simulation`, `prospective_shadow`, or `production_experimental`, assigned only when the corresponding evidence contract is satisfied.
- **Public_Claim_Surface**: Any README, current-state document, generated report, portfolio artifact, release note, or public-facing text that states SYNAPSE decision-quality capability or results.
- **Evidence_Scope**: One of `simulated`, `historical_observational`, `prospective_shadow`, or `production_experimental`.
- **Twin_Validity_Report**: Evidence comparing Digital_Twin outputs with independent observations and declaring the supported operating envelope.
- **Digital_Twin**: The SYNAPSE simulation environment used to generate policy outcomes under controlled scenarios.
- **Operating_Envelope**: The parameter and state region for which available validation evidence supports Digital_Twin use.
- **Sensitivity_Analysis**: A preregistered analysis of outcome and policy-ranking changes under parameter perturbation and model-form alternatives.
- **Failure_Region**: A reproducible subset of scenario space where a policy violates a Primary_Endpoint, Guardrail_Metric, or declared operating bound.
- **Ablation**: A matched evaluation that disables or replaces one claimed decision component while holding other conditions constant.
- **Contamination_Event**: Exposure, derivation coupling, leakage, or tuning activity that compromises a Confirmatory_Corpus or its analysis.
- **Evidence_Bundle**: A content-addressed package containing preregistration, manifest, pair-level results, exclusions, analyses, reports, claim decisions, and integrity metadata.
- **Claim_Ledger**: An append-only record mapping each public claim to evidence scope, status, supporting bundle, limitations, and superseding evidence.
- **Claim_Gate**: A deterministic CI decision that returns `pass`, `fail`, or `not_evaluated` for a proposed claim.
- **External_Verifier**: A documented evaluator that validates an Evidence_Bundle and recomputes reported results without access to private services or mutable repository state.
- **Negative_Result**: A valid null, inferior, heterogeneous, invalidated, or inconclusive evaluation result.
- **Failed_Run**: An Evaluation_Run that does not satisfy its preregistered execution or data-quality contract.
- **Evaluation_Run**: One identified execution of a preregistered policy comparison.
- **Evidence_Origin**: The source category and immutable identifier of every scenario input and observed outcome.
- **Analysis_Lock**: The content hash that freezes Preregistration, Metric_Ontology, policy versions, scenario allocation, and analysis rules before confirmatory execution.
- **Decision_Quality_Report**: A human-readable rendering of an Evidence_Bundle that presents estimates, uncertainty, failures, limitations, and claim status.

## Requirements

### Requirement 1: Establish the claim boundary

**User Story:** As an evidence reviewer, I want every decision-quality statement tied to a verified evidence scope, so that software honesty cannot be mistaken for business effectiveness.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL classify every decision-quality result by Evidence_Scope.
2. WHEN evidence originates only from the Digital_Twin, THE Decision_Integrity_Elevation_System SHALL label the result `simulated`.
3. IF a claim lacks an Evidence_Bundle that satisfies the Claim_Gate, THEN THE Decision_Integrity_Elevation_System SHALL assign the claim status `unsupported`.
4. WHEN repository integrity evidence lacks comparative business outcomes, THE Decision_Integrity_Elevation_System SHALL report integrity and effectiveness as separate claim categories.
5. IF production outcome evidence is absent, THEN THE Decision_Integrity_Elevation_System SHALL assign production-effectiveness claims the status `not_evaluated`.
6. THE Decision_Integrity_Elevation_System SHALL preserve the distinction between an outcome percentile and a Confidence_Interval.

### Requirement 2: Define decision families and credible controls

**User Story:** As an evaluator, I want each SYNAPSE decision compared with credible alternatives, so that measured effects answer a practical policy question.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL define the action space, observation set, business objective, and outcome horizon for each Decision_Family.
2. THE Decision_Integrity_Elevation_System SHALL register at least one Status_Quo_Policy for each confirmatory Decision_Family.
3. THE Decision_Integrity_Elevation_System SHALL register a No_Action_Policy where discretionary inaction is valid for the Decision_Family.
4. WHEN a Control_Policy is evaluated, THE Decision_Integrity_Elevation_System SHALL record the Control_Policy version and rationale.
5. WHEN a Control_Policy is evaluated, THE Decision_Integrity_Elevation_System SHALL enforce the same permitted information and action constraints used by the SYNAPSE_Policy.
6. WHERE an Oracle_Policy is included, THE Decision_Integrity_Elevation_System SHALL label the Oracle_Policy as a non-deployable upper-bound diagnostic.
7. IF a comparator receives privileged information unavailable to the SYNAPSE_Policy, THEN THE Decision_Integrity_Elevation_System SHALL exclude the comparator from Superiority_Claim decisions.

### Requirement 3: Execute paired seeded counterfactual scenarios

**User Story:** As a researcher, I want policy comparisons on matched stochastic worlds, so that policy choice is the intended source of within-pair outcome differences.

#### Acceptance Criteria

1. WHEN the Decision_Integrity_Elevation_System creates a Scenario_Pair, THE Decision_Integrity_Elevation_System SHALL assign one Pair_ID and a complete Seed_Ledger to both policy executions.
2. WHEN the Decision_Integrity_Elevation_System executes a Scenario_Pair, THE Decision_Integrity_Elevation_System SHALL provide both policies the same initial state.
3. WHEN the Decision_Integrity_Elevation_System executes a Scenario_Pair, THE Decision_Integrity_Elevation_System SHALL provide both policies the same Exogenous_Event stream.
4. WHEN the Decision_Integrity_Elevation_System executes a Scenario_Pair, THE Decision_Integrity_Elevation_System SHALL apply the same observation schedule, constraints, and evaluation horizon to both policies.
5. WHEN a policy selects an action, THE Decision_Integrity_Elevation_System SHALL condition downstream Digital_Twin state transitions and outcomes on the selected action.
6. THE Decision_Integrity_Elevation_System SHALL isolate policy-specific state between the two executions in a Scenario_Pair.
7. THE Decision_Integrity_Elevation_System SHALL derive scenario allocation and seed ordering from the Analysis_Lock rather than execution completion order.
8. IF either execution in a Scenario_Pair is incomplete, THEN THE Decision_Integrity_Elevation_System SHALL classify the pair using the preregistered missing-pair rule.
9. WHEN a complete Scenario_Pair is scored, THE Decision_Integrity_Elevation_System SHALL retain both policy outcomes and the Paired_Effect.
10. WHEN the same Evaluation_Manifest is executed in the same supported environment, THE Decision_Integrity_Elevation_System SHALL reproduce every deterministic pair-level outcome exactly.

### Requirement 4: Freeze metrics and analysis before confirmatory execution

**User Story:** As a skeptical reviewer, I want hypotheses and analysis choices fixed before outcomes are visible, so that researcher degrees of freedom cannot manufacture a favorable conclusion.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL define one Primary_Endpoint for each confirmatory Decision_Family.
2. THE Decision_Integrity_Elevation_System SHALL define each evaluation metric in the Metric_Ontology with a stable identifier and version.
3. THE Decision_Integrity_Elevation_System SHALL define each evaluation metric's unit, favorable direction, population, horizon, aggregation, missingness rule, and Evidence_Scope.
4. THE Decision_Integrity_Elevation_System SHALL classify every non-primary metric as a Secondary_Endpoint, Exploratory_Endpoint, or Guardrail_Metric.
5. THE Decision_Integrity_Elevation_System SHALL record a versioned Minimum_Relevant_Effect for every Primary_Endpoint.
6. THE Decision_Integrity_Elevation_System SHALL record a versioned Non_Inferiority_Margin for every Guardrail_Metric used by a Superiority_Claim.
7. THE Decision_Integrity_Elevation_System SHALL bind every effect threshold, uncertainty threshold, missingness tolerance, calibration tolerance, and guardrail bound to a rationale, Evidence_Origin, approver, version, and Preregistration hash.
8. THE Decision_Integrity_Elevation_System SHALL record hypotheses, Comparison_Families, exclusions, sample-size rationale, stopping rules, Decision_Criteria, and analysis methods in the Preregistration.
9. THE Decision_Integrity_Elevation_System SHALL produce the Analysis_Lock before confirmatory policy outcomes are observed.
10. IF the Preregistration changes after the Analysis_Lock, THEN THE Decision_Integrity_Elevation_System SHALL classify subsequent analysis as exploratory or create a new Confirmatory_Corpus.
11. WHEN the Metric_Ontology is serialized and parsed, THE Decision_Integrity_Elevation_System SHALL recover a semantically equivalent Metric_Ontology.
12. WHEN the Preregistration is serialized and parsed, THE Decision_Integrity_Elevation_System SHALL recover a semantically equivalent Preregistration.

### Requirement 5: Quantify effects, uncertainty, and multiplicity

**User Story:** As a quantitative reviewer, I want paired effects with uncertainty and controlled comparisons, so that random variation and metric shopping are visible.

#### Acceptance Criteria

1. WHEN a confirmatory comparison completes, THE Decision_Integrity_Elevation_System SHALL report the paired effect estimate for the Primary_Endpoint.
2. WHEN a confirmatory comparison completes, THE Decision_Integrity_Elevation_System SHALL report a Confidence_Interval computed with the preregistered paired method and Confidence_Level.
3. WHEN a confirmatory comparison completes, THE Decision_Integrity_Elevation_System SHALL report the raw hypothesis probability measure and the Adjusted_P_Value where the preregistered method uses hypothesis probability measures.
4. THE Decision_Integrity_Elevation_System SHALL preregister a versioned multiplicity-control method and error criterion for each Comparison_Family.
5. THE Decision_Integrity_Elevation_System SHALL justify the multiplicity-control method and error criterion using the claim stakes, hypothesis structure, and cited methodological Evidence_Origins.
6. THE Decision_Integrity_Elevation_System SHALL determine confirmatory sample size before the Analysis_Lock using a versioned power or precision target justified by the Minimum_Relevant_Effect, outcome variability assumptions, decision stakes, and resource budget.
7. THE Decision_Integrity_Elevation_System SHALL execute the preregistered complete-pair sample size or apply the preregistered stopping and inconclusive-result rule.
8. WHEN pair-level effects violate assumptions of the primary estimator under the preregistered diagnostic, THE Decision_Integrity_Elevation_System SHALL use the preregistered robust or resampling method.
9. IF the paired effect does not reach the Minimum_Relevant_Effect under the Decision_Criterion, THEN THE Decision_Integrity_Elevation_System SHALL withhold the Superiority_Claim.
10. IF the adjusted confirmatory criterion is not met, THEN THE Decision_Integrity_Elevation_System SHALL withhold the Superiority_Claim.
11. IF any required Guardrail_Metric exceeds the Non_Inferiority_Margin, THEN THE Decision_Integrity_Elevation_System SHALL withhold the Superiority_Claim.
12. WHEN a subgroup effect is not preregistered, THE Decision_Integrity_Elevation_System SHALL label the subgroup result exploratory.

### Requirement 6: Establish digital-twin validity and sensitivity

**User Story:** As a model-risk reviewer, I want the simulator's limits measured independently, so that precise simulated effects are not presented as real-world truth.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL record the Evidence_Origin for every Digital_Twin calibration and validation input.
2. WHEN independent observed outcomes are available, THE Decision_Integrity_Elevation_System SHALL reserve validation observations that were not used for Digital_Twin calibration.
3. WHEN independent validation observations are available, THE Decision_Integrity_Elevation_System SHALL report preregistered prediction error and interval coverage for each Primary_Endpoint and Guardrail_Metric.
4. WHEN independent validation observations are available, THE Decision_Integrity_Elevation_System SHALL define the Operating_Envelope from measured validation coverage.
5. IF independent validation observations are unavailable, THEN THE Decision_Integrity_Elevation_System SHALL label the Digital_Twin `unvalidated_for_real_world_prediction`.
6. IF a Scenario lies outside the Operating_Envelope, THEN THE Decision_Integrity_Elevation_System SHALL exclude the Scenario from real-world generalization claims.
7. THE Decision_Integrity_Elevation_System SHALL record every influential Digital_Twin parameter with value, allowed range, source, and uncertainty.
8. THE Decision_Integrity_Elevation_System SHALL perform Sensitivity_Analysis across preregistered parameter ranges and model-form alternatives.
9. WHEN Sensitivity_Analysis changes a policy ranking or claim decision, THE Decision_Integrity_Elevation_System SHALL report the affected region and withdraw the unconditional ranking.
10. WHEN the SYNAPSE_Policy and a Control_Policy are evaluated in the same Digital_Twin, THE Decision_Integrity_Elevation_System SHALL state that the comparison estimates simulated relative performance conditional on the Digital_Twin.
11. THE Decision_Integrity_Elevation_System SHALL report outcome-distribution percentiles separately from inferential Confidence_Intervals.

### Requirement 7: Prevent leakage and evaluation overfitting

**User Story:** As an independent evaluator, I want confirmatory evidence isolated from policy development, so that reported generalization does not arise from test-set tuning.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL maintain disjoint Development_Corpus and Confirmatory_Corpus identities.
2. THE Decision_Integrity_Elevation_System SHALL include a Hidden_Holdout in each confirmatory evaluation intended to support a generalization claim.
3. THE Decision_Integrity_Elevation_System SHALL derive Hidden_Holdout labels and outcomes independently of evaluated policy thresholds and expected actions.
4. THE Decision_Integrity_Elevation_System SHALL freeze scenario definitions, policy versions, metric versions, and analysis versions in the Analysis_Lock.
5. WHEN temporal or geographic generalization is claimed, THE Decision_Integrity_Elevation_System SHALL use a corresponding temporal or geographic holdout.
6. WHEN policy developers access Hidden_Holdout outcomes before claim finalization, THE Decision_Integrity_Elevation_System SHALL record a Contamination_Event.
7. IF a Contamination_Event affects a confirmatory comparison, THEN THE Decision_Integrity_Elevation_System SHALL invalidate the affected confirmatory claim.
8. WHEN an affected confirmatory claim is re-evaluated, THE Decision_Integrity_Elevation_System SHALL use a newly frozen Hidden_Holdout.
9. THE Decision_Integrity_Elevation_System SHALL preserve invalidated results and the associated Contamination_Event in the Evidence_Bundle.
10. THE Decision_Integrity_Elevation_System SHALL prevent current routing thresholds from serving as both fixture-generation rules and independent expected outcomes.

### Requirement 8: Map robustness and failure regions

**User Story:** As an operator, I want the conditions under which SYNAPSE fails or loses advantage disclosed, so that aggregate averages do not hide unsafe operating regions.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL preregister nominal, boundary, tail, and combined-shock regions for each confirmatory Decision_Family.
2. THE Decision_Integrity_Elevation_System SHALL evaluate the SYNAPSE_Policy and each required Control_Policy on matched Scenario_Pairs within every preregistered region.
3. WHEN a policy violates a Primary_Endpoint threshold, THE Decision_Integrity_Elevation_System SHALL record a Failure_Region.
4. WHEN a policy violates a Guardrail_Metric bound, THE Decision_Integrity_Elevation_System SHALL record a Failure_Region.
5. THE Decision_Integrity_Elevation_System SHALL report scenario-space coverage for the robustness evaluation.
6. THE Decision_Integrity_Elevation_System SHALL report pair counts and uncertainty for each Failure_Region.
7. WHEN no observed failure exists in a tested region, THE Decision_Integrity_Elevation_System SHALL report the tested coverage and detection limit instead of claiming universal safety.
8. IF a Failure_Region intersects the claimed Operating_Envelope, THEN THE Decision_Integrity_Elevation_System SHALL include the region in the Claim_Ledger limitation.
9. WHEN a worst-case search identifies a reproducible scenario, THE Decision_Integrity_Elevation_System SHALL include the scenario definition and Seed_Ledger in the Evidence_Bundle.
10. THE Decision_Integrity_Elevation_System SHALL preregister at least one Negative_Control for each confirmatory Decision_Family.
11. WHEN a Negative_Control indicates an effect beyond its preregistered tolerance, THE Decision_Integrity_Elevation_System SHALL invalidate the affected confirmatory claim pending investigation.
12. THE Decision_Integrity_Elevation_System SHALL evaluate preregistered adversarial, stress, and combined-failure scenarios against the same required Control_Policies.
13. WHEN a generalization claim covers temporal, geographic, demand, supplier, or disruption shift, THE Decision_Integrity_Elevation_System SHALL report matched policy effects and uncertainty separately for the corresponding distribution-shift region.

### Requirement 9: Measure end-to-end decision outcomes

**User Story:** As a portfolio reviewer, I want evaluation to cover decisions through consequences, so that routing correctness is not substituted for business value.

#### Acceptance Criteria

1. WHEN a policy execution is evaluated for decision quality, THE Decision_Integrity_Elevation_System SHALL execute the complete applicable path from observation through selected action to outcome horizon.
2. THE Decision_Integrity_Elevation_System SHALL record the selected action, execution status, realized outcome, and outcome horizon for each policy execution.
3. IF a realized outcome is unavailable, THEN THE Decision_Integrity_Elevation_System SHALL record the outcome as `unknown`.
4. IF either member of a Scenario_Pair has an `unknown` Primary_Endpoint, THEN THE Decision_Integrity_Elevation_System SHALL apply the preregistered missing-pair rule.
5. THE Decision_Integrity_Elevation_System SHALL report the fraction and reason distribution of `unknown` outcomes by policy.
6. IF policy-specific `unknown` rates exceed the preregistered tolerance, THEN THE Decision_Integrity_Elevation_System SHALL invalidate the affected Superiority_Claim.
7. WHEN an evaluation executes only tier classification, THE Decision_Integrity_Elevation_System SHALL classify the result as routing evidence rather than decision-quality evidence.
8. WHEN a surrogate metric replaces a Primary_Endpoint, THE Decision_Integrity_Elevation_System SHALL label the result exploratory unless independent validity evidence for the surrogate is present.

### Requirement 10: Attribute value through matched ablations

**User Story:** As a system designer, I want claimed component contributions tested by ablation, so that architectural complexity is justified by measured decision value.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL define an Ablation for every component named as a cause of a decision-quality improvement.
2. WHEN an Ablation is executed, THE Decision_Integrity_Elevation_System SHALL use the same Scenario_Pairs used for the corresponding full-policy comparison.
3. WHEN an Ablation is executed, THE Decision_Integrity_Elevation_System SHALL change only the preregistered component or replacement behavior.
4. WHERE a corresponding component participates in the evaluated Decision_Family, THE Decision_Integrity_Elevation_System SHALL include matched ablations for each participating agent, tier selection, consensus, learned-policy use, Digital_Twin verification, uncertainty gating, and fallback behavior.
5. WHERE safety guardrails are ablated, THE Decision_Integrity_Elevation_System SHALL restrict execution to simulation.
6. WHEN an Ablation produces no practically relevant contribution, THE Decision_Integrity_Elevation_System SHALL report the component contribution as unsupported.
7. WHEN an Ablation degrades one metric and improves another, THE Decision_Integrity_Elevation_System SHALL report the tradeoff without collapsing the result into a single favorable label.
8. IF an interaction is required to explain a claimed component effect, THEN THE Decision_Integrity_Elevation_System SHALL preregister and report the corresponding interaction ablation.

### Requirement 11: Preserve negative results and complete accounting

**User Story:** As a research reviewer, I want null, adverse, failed, and excluded results retained, so that selective reporting is detectable.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL retain every Evaluation_Run with a stable identifier and terminal status.
2. WHEN an Evaluation_Run is valid and non-favorable, THE Decision_Integrity_Elevation_System SHALL preserve the Negative_Result in the Evidence_Bundle.
3. WHEN an Evaluation_Run fails, THE Decision_Integrity_Elevation_System SHALL preserve the Failed_Run reason and available diagnostics.
4. WHEN a Scenario_Pair is excluded, THE Decision_Integrity_Elevation_System SHALL preserve the Pair_ID and preregistered exclusion reason.
5. THE Decision_Integrity_Elevation_System SHALL reconcile generated, attempted, completed, excluded, missing, failed, and analyzed pair counts.
6. IF pair accounting does not reconcile, THEN THE Decision_Integrity_Elevation_System SHALL fail the Claim_Gate.
7. WHEN an analysis correction supersedes a prior result, THE Decision_Integrity_Elevation_System SHALL append the corrected result and retain the prior result.
8. THE Decision_Integrity_Elevation_System SHALL distinguish `unsupported`, `not_evaluated`, `inconclusive`, `inferior`, and `supported` claim statuses.
9. IF a Negative_Result satisfies the preregistered validity contract, THEN THE Decision_Integrity_Elevation_System SHALL permit publication of the Negative_Result as the final result.

### Requirement 12: Bind reproducibility and provenance

**User Story:** As an external reproducer, I want every result bound to exact inputs and executable versions, so that evidence can be recreated and drift can be detected.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL create one Evaluation_Manifest for every Evaluation_Run.
2. THE Decision_Integrity_Elevation_System SHALL bind the Evaluation_Manifest to the repository commit and working-tree state.
3. THE Decision_Integrity_Elevation_System SHALL bind the Evaluation_Manifest to dependency-lock, runtime-image, platform, and environment identifiers.
4. THE Decision_Integrity_Elevation_System SHALL bind the Evaluation_Manifest to scenario, Evidence_Origin, Seed ledger, Metric_Ontology, Preregistration, and analysis hashes.
5. THE Decision_Integrity_Elevation_System SHALL bind the Evaluation_Manifest to SYNAPSE_Policy, Control_Policy, model, checkpoint, feature snapshot, Digital_Twin code, and Digital_Twin configuration hashes.
6. THE Decision_Integrity_Elevation_System SHALL record start time, completion time, terminal status, and evaluator version for every Evaluation_Run.
7. WHEN an Evaluation_Manifest is serialized and parsed, THE Decision_Integrity_Elevation_System SHALL recover a semantically equivalent Evaluation_Manifest.
8. WHEN an Evidence_Bundle is regenerated from identical deterministic inputs, THE Decision_Integrity_Elevation_System SHALL reproduce pair-level values and content hashes exactly.
9. WHERE nondeterministic hardware behavior is permitted, THE Decision_Integrity_Elevation_System SHALL declare the tolerance before execution and verify results within the declared tolerance.
10. IF a required provenance field is missing, THEN THE Decision_Integrity_Elevation_System SHALL fail the Claim_Gate.

### Requirement 13: Produce durable evidence and reports

**User Story:** As a hiring panel or technical auditor, I want inspectable evidence artifacts, so that conclusions can be checked without trusting screenshots or prose.

#### Acceptance Criteria

1. WHEN an Evaluation_Run reaches a terminal status, THE Decision_Integrity_Elevation_System SHALL produce a content-addressed Evidence_Bundle.
2. THE Decision_Integrity_Elevation_System SHALL include the Preregistration, Analysis_Lock, Evaluation_Manifest, Metric_Ontology, and policy specifications in the Evidence_Bundle.
3. THE Decision_Integrity_Elevation_System SHALL include pair-level outcomes, exclusions, missingness, Failed_Runs, analysis outputs, and claim decisions in the Evidence_Bundle.
4. THE Decision_Integrity_Elevation_System SHALL produce a Decision_Quality_Report from the Evidence_Bundle.
5. THE Decision_Quality_Report SHALL present absolute outcomes, Paired_Effects, Confidence_Intervals, Adjusted_P_Values, pair counts, and Guardrail_Metric results.
6. THE Decision_Quality_Report SHALL present Negative_Results, Failure_Regions, sensitivity findings, ablations, limitations, and Evidence_Scope.
7. THE Decision_Quality_Report SHALL identify every deviation from the Preregistration.
8. WHEN no confirmatory claim is supported, THE Decision_Quality_Report SHALL state that conclusion in the summary.
9. THE Decision_Quality_Report SHALL present Selective_Action_Profiles and Resource_Tradeoff_Profiles for the evaluated policy and required controls.
10. WHEN an Evidence_Bundle is serialized and parsed, THE Decision_Integrity_Elevation_System SHALL recover a semantically equivalent Evidence_Bundle.
11. IF the Decision_Quality_Report disagrees with recomputed Evidence_Bundle values, THEN THE Decision_Integrity_Elevation_System SHALL fail the Claim_Gate.

### Requirement 14: Enable independent verification

**User Story:** As an external reviewer, I want to recompute evidence without privileged access, so that credibility does not depend on repository authors.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL provide an External_Verifier for every claim-bearing Evidence_Bundle.
2. WHEN the External_Verifier receives a complete Evidence_Bundle, THE Decision_Integrity_Elevation_System SHALL verify every content hash and schema.
3. WHEN the External_Verifier receives a complete Evidence_Bundle, THE Decision_Integrity_Elevation_System SHALL recompute pair accounting, metric aggregates, uncertainty results, multiplicity results, and claim decisions from pair-level records.
4. THE Decision_Integrity_Elevation_System SHALL permit External_Verifier execution without cloud credentials, private services, or a mutable database.
5. THE Decision_Integrity_Elevation_System SHALL publish the Evidence_Bundle digest in a publicly inspectable immutable record.
6. WHEN an external digest differs from the Evidence_Bundle digest, THE Decision_Integrity_Elevation_System SHALL fail verification.
7. WHEN a required artifact is absent, THE Decision_Integrity_Elevation_System SHALL return a failed verification result with the missing artifact identifier.
8. THE Decision_Integrity_Elevation_System SHALL document one bounded verification procedure from artifact retrieval through claim recomputation.
9. THE Decision_Integrity_Elevation_System SHALL expose one deterministic command that validates prerequisites, reproduces the declared evaluation scope, builds the Evidence_Bundle, recomputes the Decision_Quality_Report, and returns a nonzero status on any failed required stage.
10. WHEN the one-command procedure cannot execute a confirmatory stage, THE Decision_Integrity_Elevation_System SHALL return `not_evaluated` for the affected claim rather than reuse or fabricate a favorable result.
11. WHEN the External_Verifier completes, THE Decision_Integrity_Elevation_System SHALL emit a machine-readable verification receipt containing verifier version, bundle digest, checks performed, and status.

### Requirement 15: Gate claims and evaluation changes in CI

**User Story:** As a maintainer, I want evidence claims mechanically gated, so that code or prose cannot silently outrun the evaluation.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL make Claim_Gate status deterministic for a fixed Evidence_Bundle and verifier version.
2. THE Decision_Integrity_Elevation_System SHALL execute evaluation-contract tests when policy, scenario, Digital_Twin, baseline, metric, analysis, reporting, or claim files change.
3. THE Decision_Integrity_Elevation_System SHALL execute paired smoke comparisons on the pull-request path without substituting smoke results for confirmatory evidence.
4. THE Decision_Integrity_Elevation_System SHALL execute the External_Verifier against every modified claim-bearing Evidence_Bundle on the pull-request path.
5. IF a claim-bearing report changes without a matching verified Evidence_Bundle, THEN THE Decision_Integrity_Elevation_System SHALL fail the Claim_Gate.
6. IF a claim exceeds the Evidence_Scope recorded in the Claim_Ledger, THEN THE Decision_Integrity_Elevation_System SHALL fail the Claim_Gate.
7. IF confirmatory analysis violates the Analysis_Lock, THEN THE Decision_Integrity_Elevation_System SHALL fail the Claim_Gate.
8. IF a required evaluation is skipped, THEN THE Decision_Integrity_Elevation_System SHALL return `not_evaluated` rather than `pass`.
9. WHEN a scheduled confirmatory evaluation fails or regresses, THE Decision_Integrity_Elevation_System SHALL retain the Evidence_Bundle and expose a blocking claim status.
10. WHEN a claim is superseded, THE Decision_Integrity_Elevation_System SHALL retain the prior Claim_Ledger entry and link the superseding entry.
11. THE Decision_Integrity_Elevation_System SHALL include `tests/eval` contract coverage in a required CI path.
12. THE Decision_Integrity_Elevation_System SHALL include Digital_Twin validity and oracle contract coverage in a required CI path when affected evaluation surfaces change.
13. THE Decision_Integrity_Elevation_System SHALL derive CI scope from versioned path and schema dependencies rather than contributor-selected labels.
14. IF a required test collection contains zero executed tests or an unapproved skip, THEN THE Decision_Integrity_Elevation_System SHALL fail the Claim_Gate.
15. WHEN a Public_Claim_Surface changes, THE Decision_Integrity_Elevation_System SHALL verify every material decision-quality claim against the Claim_Ledger and supporting Evidence_Bundle.
16. IF documentation states a threshold or result that differs from the versioned Preregistration or verified Evidence_Bundle, THEN THE Decision_Integrity_Elevation_System SHALL fail the Claim_Gate.

### Requirement 16: Separate simulated, observational, and production evidence

**User Story:** As a decision maker, I want evidence scopes rendered without ambiguity, so that simulation results cannot imply demonstrated production impact.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL propagate Evidence_Scope from Evidence_Origin through pair-level records, reports, bundles, and Claim_Ledger entries.
2. WHEN all evaluated outcomes originate from the Digital_Twin, THE Decision_Integrity_Elevation_System SHALL prefix the conclusion with `simulated evidence`.
3. WHEN historical observations lack prospective policy assignment, THE Decision_Integrity_Elevation_System SHALL label causal production effects `not_evaluated`.
4. WHERE a historical observational analysis is included, THE Decision_Integrity_Elevation_System SHALL report the identification assumptions and measured covariate limitations.
5. WHEN prospective shadow evidence lacks real action assignment, THE Decision_Integrity_Elevation_System SHALL withhold production business-outcome claims.
6. WHEN a production-experimental claim is proposed, THE Decision_Integrity_Elevation_System SHALL require a preregistered assignment mechanism and measured production outcomes.
7. IF an Evidence_Bundle mixes Evidence_Scopes, THEN THE Decision_Integrity_Elevation_System SHALL report results separately by Evidence_Scope.
8. THE Decision_Integrity_Elevation_System SHALL exclude synthetic traffic from production-effect aggregates by default.
9. WHERE synthetic traffic is included for diagnostics, THE Decision_Integrity_Elevation_System SHALL report synthetic traffic in a separately labeled segment.

### Requirement 17: Handle evaluation failures without fabricated evidence

**User Story:** As an evidence custodian, I want failures represented explicitly, so that infrastructure problems cannot become favorable data.

#### Acceptance Criteria

1. IF a policy execution raises an error, THEN THE Decision_Integrity_Elevation_System SHALL record the execution as failed with the Pair_ID and error class.
2. IF a Control_Policy cannot execute under matched conditions, THEN THE Decision_Integrity_Elevation_System SHALL withhold the affected comparative claim.
3. IF a required random stream is unseeded, THEN THE Decision_Integrity_Elevation_System SHALL fail the Evaluation_Run before confirmatory analysis.
4. IF pair-level provenance is incomplete, THEN THE Decision_Integrity_Elevation_System SHALL exclude the pair under a preregistered rule and preserve the exclusion.
5. IF the observed pair count falls below the preregistered sample size, THEN THE Decision_Integrity_Elevation_System SHALL classify the confirmatory result `inconclusive`.
6. IF the External_Verifier cannot reproduce a claim decision, THEN THE Decision_Integrity_Elevation_System SHALL assign the claim status `unsupported`.
7. WHEN an evaluation dependency is unavailable, THE Decision_Integrity_Elevation_System SHALL record `not_evaluated` instead of a successful result.
8. IF Digital_Twin numerical instability exceeds a preregistered tolerance, THEN THE Decision_Integrity_Elevation_System SHALL fail the affected Scenario_Pairs.
9. WHEN a Failed_Run is retried, THE Decision_Integrity_Elevation_System SHALL create a new Evaluation_Run identifier linked to the Failed_Run.

### Requirement 18: Enforce explicit non-goals

**User Story:** As a project owner, I want scope boundaries recorded, so that decision-evaluation rigor is completed without unrelated platform expansion or inflated claims.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL treat live customer ingestion as outside the feature scope.
2. THE Decision_Integrity_Elevation_System SHALL treat production policy deployment and autonomous production experimentation as outside the feature scope.
3. THE Decision_Integrity_Elevation_System SHALL treat replacement of agent training architectures as outside the feature scope unless a replacement is required to define a Control_Policy.
4. THE Decision_Integrity_Elevation_System SHALL treat user-interface redesign as outside the feature scope except for generated Decision_Quality_Report artifacts.
5. THE Decision_Integrity_Elevation_System SHALL treat infrastructure topology changes as outside the feature scope unless a change is required for reproducible evaluation.
6. THE Decision_Integrity_Elevation_System SHALL treat proof of real-world causal impact from simulated evidence as an invalid objective.
7. THE Decision_Integrity_Elevation_System SHALL treat a predetermined positive SYNAPSE result as an invalid objective.
8. THE Decision_Integrity_Elevation_System SHALL treat optimization against Hidden_Holdout outcomes as a Contamination_Event.
9. THE Decision_Integrity_Elevation_System SHALL treat routing accuracy, code coverage, mutation score, and subjective LLM-judge score as supporting software evidence rather than Primary_Endpoint business outcomes.
10. THE Decision_Integrity_Elevation_System SHALL preserve existing audit, provenance, and synthetic-label honesty guarantees while adding decision-quality evaluation.

### Requirement 19: Measure selective-action value and operating tradeoffs

**User Story:** As a decision owner, I want abstention and resource tradeoffs measured with decision outcomes, so that higher confidence or complexity is valuable only when the complete operating result improves.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL define the action, abstention, escalation, and fallback semantics for each evaluated SYNAPSE_Policy and Control_Policy.
2. THE Decision_Integrity_Elevation_System SHALL preregister versioned uncertainty thresholds and calibration criteria before generating a confirmatory Selective_Action_Profile.
3. WHEN an evaluated policy can abstain or escalate, THE Decision_Integrity_Elevation_System SHALL report action coverage, abstention rate, calibration, Primary_Endpoint effect, and Guardrail_Metric outcomes across the preregistered uncertainty thresholds.
4. WHEN selective action is evaluated, THE Decision_Integrity_Elevation_System SHALL compare forced action, selective action, abstention or fallback, and required Control_Policies on matched Scenario_Pairs.
5. WHEN policies act on different fractions of Scenario_Pairs, THE Decision_Integrity_Elevation_System SHALL report both conditional-on-action outcomes and population-level outcomes.
6. THE Decision_Integrity_Elevation_System SHALL record monetary cost, compute consumption, end-to-end latency, safety outcomes, and environmental impact for every confirmatory policy execution.
7. WHEN a resource measure is unavailable, THE Decision_Integrity_Elevation_System SHALL label the Resource_Tradeoff_Profile incomplete and identify the missing measure.
8. THE Decision_Integrity_Elevation_System SHALL report non-dominated value and resource tradeoffs without collapsing tradeoffs into one score unless the score and weights are justified, versioned, and preregistered.
9. IF a policy violates a preregistered cost, latency, safety, or environmental bound, THEN THE Decision_Integrity_Elevation_System SHALL withhold an unconditional Superiority_Claim.
10. WHEN an uncertainty threshold changes the policy ranking or claim decision, THE Decision_Integrity_Elevation_System SHALL report the affected action-coverage region.

### Requirement 20: Advance evidence maturity through the smallest decisive proof

**User Story:** As a project owner, I want evidence capability delivered in falsifiable stages, so that portfolio credibility improves before broader completion work creates feature sprawl.

#### Acceptance Criteria

1. THE Decision_Integrity_Elevation_System SHALL assign one Evidence_Maturity_Level to every decision-quality claim.
2. THE Decision_Integrity_Elevation_System SHALL assign the existing repository decision-value state `integrity_only` until a verified matched policy-effect Evidence_Bundle exists.
3. WHEN one narrow Decision_Family has action-conditioned matched comparisons, preregistered analysis, complete tradeoff reporting, and external recomputation, THE Decision_Integrity_Elevation_System SHALL permit the `paired_simulation` level for claims within that Decision_Family.
4. WHEN independent twin validation establishes an Operating_Envelope and required sensitivity analyses preserve the bounded claim, THE Decision_Integrity_Elevation_System SHALL permit the `qualified_simulation` level within that Operating_Envelope.
5. WHEN prospective shadow outcomes satisfy a preregistered observation and missingness contract, THE Decision_Integrity_Elevation_System SHALL permit the `prospective_shadow` level without implying production causal impact.
6. WHEN a preregistered production assignment mechanism and measured production outcomes satisfy the Claim_Gate, THE Decision_Integrity_Elevation_System SHALL permit the `production_experimental` level.
7. IF a claim lacks any criterion for a proposed Evidence_Maturity_Level, THEN THE Decision_Integrity_Elevation_System SHALL retain the highest lower level whose criteria are complete.
8. THE Decision_Integrity_Elevation_System SHALL complete the first `paired_simulation` Evidence_Bundle before expanding confirmatory coverage to additional Decision_Families.
9. WHEN a maturity-level result is tied, inferior, regressed, or inconclusive, THE Decision_Integrity_Elevation_System SHALL preserve the result and permit the evidence capability to mature without upgrading the performance claim.
10. THE Decision_Integrity_Elevation_System SHALL rank implementation work by expected reduction in claim uncertainty, evidence validity risk, and external verification burden.

## Formal Correctness Properties

The following properties define high-value property-based tests for pure evaluation logic. External publication, production services, and full Digital_Twin execution require representative integration tests rather than 100 networked property iterations.

1. **Property P1 — Paired-world identity**  
   For every valid Scenario_Pair, removing policy identity, policy actions, and downstream policy effects from both execution inputs yields equal initial state, Exogenous_Event stream, observation schedule, constraints, horizon, and Seed.  
   **Validates:** Requirements 3.1–3.5.

2. **Property P2 — Pair identity stability**  
   For every valid Scenario and Seed, repeated Pair_ID derivation with identical policy versions yields the same Pair_ID; changing Scenario identity, Seed, or either policy version changes the Pair_ID.  
   **Validates:** Requirements 2.4, 3.1, 12.4–12.5.

3. **Property P3 — Paired-effect antisymmetry**  
   For every finite metric outcome pair `(a, b)`, `effect(a, b) = -effect(b, a)` after applying the metric's favorable direction.  
   **Validates:** Requirements 4.3, 5.1, 13.5.

4. **Property P4 — Identical-policy neutrality**  
   For every deterministic Scenario and policy, comparing the policy with the same policy version under the same Seed produces a zero Paired_Effect for every deterministic metric.  
   **Validates:** Requirements 3.2–3.5, 5.1.

5. **Property P5 — Seed-order confluence**  
   For every set of complete pair-level records, permuting execution order or aggregation order leaves counts, point estimates, intervals, adjusted results, and claim decisions unchanged within declared numerical tolerance.  
   **Validates:** Requirements 5.1–5.4, 12.8, 15.1.

6. **Property P6 — Deterministic replay idempotence**  
   For every deterministic Evaluation_Manifest, executing the manifest twice yields identical normalized pair-level records and Evidence_Bundle content hashes.  
   **Validates:** Requirements 3.8, 12.8.

7. **Property P7 — Complete accounting partition**  
   For every Evaluation_Run, generated pairs partition into exactly one of completed, excluded, missing, or failed; analyzed pairs form a subset of completed pairs permitted by the Preregistration; category counts sum to generated pairs.  
   **Validates:** Requirements 11.4–11.6.

8. **Property P8 — Unknown-outcome honesty**  
   For every execution lacking a realized Primary_Endpoint, scoring yields `unknown`; adding unrelated metadata cannot transform `unknown` into a favorable observed outcome.  
   **Validates:** Requirements 9.3–9.6, 17.7.

9. **Property P9 — Multiplicity monotonicity**  
   For every valid Comparison_Family, each Adjusted_P_Value is greater than or equal to the corresponding unadjusted value and remains within `[0, 1]`; reordering hypotheses leaves hypothesis-to-adjusted-value mapping unchanged.  
   **Validates:** Requirements 5.3–5.4.

10. **Property P10 — Claim-gate soundness**  
    For every generated claim record, Claim_Gate returns `pass` only when provenance is complete, hashes verify, pair accounting reconciles, analysis matches the Analysis_Lock, evidence scope covers the claim, the External_Verifier agrees, the Primary_Endpoint meets both inferential and practical thresholds, and every required Guardrail_Metric remains within margin.  
    **Validates:** Requirements 5.8–5.10, 11.6, 12.10, 14.2–14.7, 15.5–15.8.

11. **Property P11 — Evidence-scope non-escalation**  
    For every transformation from Evidence_Origin to pair record to report to Claim_Ledger, the resulting Evidence_Scope is equal to or more restrictive than the source scope; no transformation upgrades `simulated` evidence to a production scope.  
    **Validates:** Requirements 1.1–1.5, 16.1–16.7.

12. **Property P12 — Round-trip artifact equivalence**  
    For every valid Metric_Ontology, Preregistration, Evaluation_Manifest, and Evidence_Bundle, `parse(serialize(x))` is semantically equivalent to `x`, and canonical reserialization produces the same content hash.  
    **Validates:** Requirements 4.10–4.11, 12.7, 13.9.

13. **Property P13 — Append-only evidence preservation**  
    For every Claim_Ledger or result history, appending a correction or superseding entry retains every prior entry byte-for-byte and increases history length by exactly one.  
    **Validates:** Requirements 11.7, 15.10.

14. **Property P14 — Ablation isolation**  
    For every valid Ablation pair, normalized manifests differ only in the preregistered ablated component and fields causally derived from that component.  
    **Validates:** Requirements 10.2–10.3.

15. **Property P15 — Zero-perturbation sensitivity identity**  
    For every valid scenario and model configuration, a zero-magnitude parameter perturbation reproduces the unperturbed outcome within the declared numerical tolerance.  
    **Validates:** Requirements 6.7–6.9.

16. **Property P16 — Report recomputation consistency**  
    For every valid Evidence_Bundle, recomputing all report tables from pair-level records yields the values in the Decision_Quality_Report within declared formatting tolerance.  
    **Validates:** Requirements 13.4–13.10, 14.3.

17. **Property P17 — Contamination invalidates confirmatory status**  
    For every confirmatory comparison, adding a Contamination_Event affecting the Hidden_Holdout changes the claim decision away from `supported` while preserving the contaminated result.  
    **Validates:** Requirements 7.6–7.9.

18. **Property P18 — Missing requirement cannot become pass**  
    For every Claim_Gate input, removing any required artifact, provenance field, verification result, or confirmatory execution changes `pass` to `fail` or `not_evaluated`, never to another `pass`.  
    **Validates:** Requirements 12.10, 14.7, 15.5–15.8.

## Completion Standard

The feature is complete only when Requirements 1–18 are satisfied together. A routing-only gate, simulator-only oracle, report-only enhancement, or favorable benchmark without preregistration and external recomputation is an incomplete elevation. The acceptable final conclusion is evidence-dependent; completion does not require SYNAPSE to outperform a Control_Policy.
