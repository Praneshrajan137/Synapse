# Requirements Document

## Introduction

SYNAPSE is a multi-agent quick-commerce supply-chain optimizer whose stated reason to exist is a single, falsifiable claim: **its four-tier consensus orchestrator makes measurably better supply-chain decisions than a transparent baseline operator.** A rigorous measurement apparatus already exists to test that claim — the closed-loop counterfactual `uplift/` harness that drives the SimPy digital twin under identical seeds across arms (attribution by construction), aggregates results under a pre-registered metric contract (`uplift/metric_contract.yaml`), bounds validity by twin fidelity, and degrades to honest failure. An execution-verified audit established that the claim is currently **unproven**, for three concrete reasons:

1. **The consensus arm is never wired in.** `uplift/cli.py::_build_consensus_arm()` constructs `ConsensusArm(transport=None)`, which always raises `ConsensusArmUnavailable`, so it is replaced by `_UnavailableConsensusArm` whose every `decide()` fails. `python -m uplift.cli --smoke` produces `headline_uplift: 0.0, incomplete: true`. No code path ever assembles the real 8 agent A2A handlers + the twin handler + a real `ConsensusProtocol` into the harness.
2. **No real model exists.** Zero trained weight files are committed; `infrastructure/ml/published_checkpoints.json` is a bare `__placeholder__`. C43/C46 SKIP. Every agent serves honest DEGRADED/fallback output at runtime (I-7).
3. **The value gate passes as a tautology.** The C60 `uplift_truth` gate compares the measured `0.0` against `UPLIFT_FLOOR = 0.0`, so `0.0 >= 0.0` PASSES without any proven gain. The README headline ("16 PASS / 3 FAIL") is stale versus the real 53 checks, and the C56 `doc_truth` gate does not pin that headline.

This feature exists to close that gap: make SYNAPSE **genuinely, verifiably** achieve its purpose by producing a real, powered, honestly-measured, **positive** decision-integrity uplift of the four-tier consensus over the baseline suite on the pre-registered primary KPI (`fill_rate`), backed by at least one real trained-and-published model serving non-degraded calibrated output, with the whole proof reproducible at $0 on synthetic seeds. Success is defined **non-circularly**: it cannot be satisfied by adding more code or more tests. It requires a measured positive number within a stated fidelity bound that is independently reproducible by re-running a single command. The strong, already-passing component engineering (623 tests, the consensus protocol, tier routing, audit hash-chain, honesty modules) MUST be preserved, not rebuilt.

## Glossary

- **Uplift_Harness**: The closed-loop counterfactual experiment (`uplift/harness.py`) that drives the digital twin through the observe → decide → apply → advance loop for each arm and aggregates per-KPI results.
- **Consensus_Arm**: The `DecisionPolicy` (`uplift/consensus_arm.py::ConsensusArm`) that makes each decision by running SYNAPSE's real four-tier `ConsensusProtocol.run_consensus` over an in-process A2A transport wired to the real agent and twin handlers. Named `"consensus"` (`DEFAULT_CONSENSUS_ARM`).
- **Baseline_Arm**: The pooled transparent control operator formed from the four pre-registered baseline policies (`Par_Level_Reorder`, `Static_Pricing`, `Greedy_Routing`, `NoOpDisruption`); every non-consensus arm is treated as baseline during result assembly.
- **In_Process_Transport**: `InProcessA2ATransport`, which dispatches A2A JSON-RPC calls to in-process agent/twin `handle_request` handler functions instead of over HTTP, keeping the run network-free and $0.
- **Headline_Uplift**: The relative percentage improvement of the Consensus_Arm over the Baseline_Arm on the contract's primary KPI, expressed in percentage points.
- **Metric_Contract**: The pre-registered, version-controlled artifact (`uplift/metric_contract.yaml`) declaring primary KPI(s) and direction, effect-size measure, significance test and alpha, per-KPI Minimum_Detectable_Effect, and the deterministic decision rule — fixed before any result is produced.
- **Minimum_Detectable_Effect (MDE)**: The smallest effect size (Cohen's d) the experiment is required to be able to detect, declared per primary KPI in the Metric_Contract.
- **Fidelity_Bound**: The statement, co-located with every headline number, that the uplift's validity is bounded by twin fidelity, quantified by the twin-vs-reference KL divergence against a committed threshold.
- **Powered_Run**: A fully-powered proof run with at least `MIN_SCENARIOS` (1000) completed scenarios per arm, satisfying INV-TW-002; runs below the floor are reduced-cost smoke runs and are not proof-grade.
- **Degraded_Serving**: Honest fallback output produced by an agent when no real trained model is available (I-7); it is never presented as a real model's output.
- **Published_Checkpoint**: A real, non-smoke, adequately-calibrated trained model published to the $0 serving source (HF Hub) and recorded in `infrastructure/ml/published_checkpoints.json`, verified by the C43 gate.
- **Attribution**: The property that any KPI delta between arms is caused only by the decision policy, because replicate `i` of every arm is driven by the identical seeded twin realization (`replicate_seed` depends only on `(scenario.seed, index)`).
- **Uplift_Floor**: The single ratcheted numeric constant `UPLIFT_FLOOR` (`uplift/uplift_floor.py`) the C60 gate enforces; raised only to lock in a verified gain, never lowered.
- **All_Wins_Guard**: The self-scrutiny warning raised when every classified pair is `SYNAPSE_WINS`, prompting a measurement-bias review before the result is trusted.
- **Honest_Failure**: The contract whereby an unavailable arm/model yields a recorded failed run (excluded from aggregation) or a distinct non-zero exit, never a fabricated decision or a fabricated pass.

## Requirements

### Requirement 1: Wire the real consensus arm into the uplift harness in-process

**User Story:** As a SYNAPSE maintainer, I want the harness to run SYNAPSE's real four-tier consensus as the Consensus_Arm over an in-process transport, so that the uplift experiment measures the actual product instead of an always-failing stub.

#### Acceptance Criteria

1. THE Uplift_Harness SHALL provide an assembly function that constructs a real `ConsensusProtocol` and an `InProcessA2ATransport` wired to the eight real agent A2A handlers and the real twin A2A handler.
2. WHEN the consensus arm is assembled through the assembly function, THE Consensus_Arm SHALL make each decision by invoking `ConsensusProtocol.run_consensus` over the In_Process_Transport, without opening any network socket or contacting any external service.
3. WHEN the assembled Consensus_Arm runs a scenario whose observation is reachable by the assembled agents, THE Consensus_Arm SHALL return a translated `PolicyAction` derived from a binding `ConsensusDecision` rather than raising `ConsensusArmUnavailable`.
4. WHEN `python -m uplift.cli --smoke` is executed, THE Uplift_Harness SHALL record at least one completed (non-failed) Consensus_Arm run for at least one adversarial scenario.
5. IF the in-process agent or twin network cannot be assembled in the current environment, THEN THE Consensus_Arm SHALL record the affected runs as failed runs carrying a diagnostic reason and SHALL NOT fabricate a decision.
6. THE assembly function SHALL reuse the existing `ConsensusProtocol`, tier router, agent handlers, and twin handler without modifying their decision logic.

### Requirement 2: Produce a complete, credited uplift result

**User Story:** As a SYNAPSE maintainer, I want a harness run that completes the consensus arm on every declared scenario, so that the assembled `UpliftResult` is not marked incomplete and the consensus-vs-baseline comparison is credited to SYNAPSE.

#### Acceptance Criteria

1. WHEN, for every declared adversarial scenario, both the Consensus_Arm and every compared Baseline_Arm have at least one completed run AND zero failed runs, THE Uplift_Harness SHALL assemble an `UpliftResult` whose `incomplete` field is `false` (matching `_run_is_incomplete`).
2. WHILE the assembled `UpliftResult` is not incomplete, THE Uplift_Harness SHALL compute a numeric Headline_Uplift as the direction-oriented relative percentage change (in percentage points) of the Consensus_Arm pooled mean over the pooled Baseline_Arm mean on the FIRST declared primary KPI in the Metric_Contract, such that a positive value always denotes improvement (raw for higher-is-better, negated for lower-is-better).
3. WHEN the result artifact is written for a non-incomplete run, THE Uplift_Harness SHALL persist a finite numeric `headline_uplift` field to `artifacts/uplift/result.json` with `incomplete` set to `false`.
4. IF any declared scenario has zero completed Consensus_Arm runs, THEN THE Uplift_Harness SHALL mark the assembled `UpliftResult` as incomplete and SHALL NOT credit any incomplete pair to SYNAPSE.
5. IF a scenario has some but not all Consensus_Arm replicates completed (at least one failed replicate), THEN THE Uplift_Harness SHALL mark the run incomplete and SHALL classify the affected pair as `TIE_INCONCLUSIVE`, never `SYNAPSE_WINS`.
6. WHERE no explicit baseline arm is designated, THE Uplift_Harness SHALL pool the completed samples of every non-consensus arm into a single Baseline_Arm distribution per `(scenario, KPI)`.
7. THE Uplift_Harness SHALL classify each scenario pair using the Metric_Contract decision rule exactly as declared, without substituting an alternative rule.

### Requirement 3: Deliver a fully-powered, reproducible uplift measurement

**User Story:** As a SYNAPSE maintainer, I want a fully-powered proof run at n ≥ 1000 per arm that reproduces within a committed noise tolerance, so that the headline number is proof-grade and independently repeatable.

#### Acceptance Criteria

1. WHEN a proof run is executed with `--full` or `--n` greater than or equal to `MIN_SCENARIOS`, THE Uplift_Harness SHALL complete at least `MIN_SCENARIOS` (1000) scenarios per arm, satisfying INV-TW-002.
2. IF fewer than `MIN_SCENARIOS` completed scenarios per arm are requested through `run_arm` or `run`, THEN THE Uplift_Harness SHALL raise the INV-TW-002 under-power error and SHALL NOT produce a proof-grade aggregation.
3. WHEN the same proof configuration and seeds are run twice, THE Uplift_Harness SHALL produce Headline_Uplift values differing by no more than the committed noise tolerance of 1.0 percentage point.
4. THE Uplift_Harness SHALL label every reduced-cost smoke run in its output as NOT a fully-powered proof.
5. WHERE the operator requests a fully-powered proof, THE Uplift_Harness SHALL emit the Headline_Uplift number co-located in the same output with its Fidelity_Bound report.
6. THE uplift proof SHALL be reproducible using synthetic seed-generated data only, reading no real, scraped, or purchased data.
7. THE uplift proof SHALL run fully in-process at $0, invoking no external paid service (I-1).

### Requirement 4: Ratchet the uplift floor only on a verified positive gain

**User Story:** As a SYNAPSE maintainer, I want `UPLIFT_FLOOR` raised above 0.0 only after a verified positive gain is measured and committed, so that the C60 gate stops being a `0.0 >= 0.0` tautology without ever asserting an unproven gain.

#### Acceptance Criteria

1. THE Uplift_Floor SHALL remain a single declared numeric constant in `uplift/uplift_floor.py`.
2. WHEN a fully-powered proof run measures a positive Headline_Uplift within the Fidelity_Bound, THE maintainer SHALL, as a single atomic obligation, raise `UPLIFT_FLOOR` to a value greater than 0.0 and less than or equal to the measured Headline_Uplift AND commit that change to version control together; the raise SHALL NOT be considered fulfilled while the commit is pending or has failed.
3. IF a proposed `UPLIFT_FLOOR` update is strictly below the previously committed value, THEN THE ratchet helper SHALL raise `FloorRatchetError` and reject the update.
4. WHEN the measured Headline_Uplift read from the result artifact is available AND greater than or equal to `UPLIFT_FLOOR`, THE C60 `uplift_truth` gate SHALL exit with the pass status.
5. IF the measured Headline_Uplift is available AND strictly below `UPLIFT_FLOOR`, THEN THE C60 gate SHALL exit with the regression status and SHALL emit the measured value and the floor; regression handling SHALL be triggered only when the measurement is properly available.
6. IF the measured Headline_Uplift is unavailable for any reason (missing/unreadable/invalid/non-finite artifact value), THEN THE C60 gate SHALL exit with the distinct unavailable status and SHALL NOT report a pass, and this unavailable rule SHALL apply whenever the measurement is unavailable, not only while the gate is actively exiting.
7. THE `UPLIFT_FLOOR` value greater than 0.0 SHALL NOT be committed unless a co-located fully-powered proof result artifact records a Headline_Uplift greater than or equal to that value.

### Requirement 5: Train and publish one real flagship checkpoint via the $0 path

**User Story:** As a SYNAPSE operator, I want at least one real `demand_prophet` checkpoint trained and published through the free-GPU $0 runbook and recorded in the registry, so that C43/C46 flip from SKIP to PASS and at least one agent serves a real calibrated model instead of degraded output.

#### Acceptance Criteria

1. WHEN the operator completes `docs/runbooks/train-and-publish-checkpoint.md`, THE published checkpoint SHALL be a non-smoke production artifact served from the $0 serving source (HF Hub).
2. THE operator SHALL replace the `__placeholder__` entry in `infrastructure/ml/published_checkpoints.json` with a real registry entry keyed by the serving name `demand_prophet_hgt_tft`, recording the repo, checkpoint sha, coverage, and training metadata.
3. WHEN the C43 `published_checkpoint_truth` gate runs with the registry populated and the remote reachable, THE C43 gate SHALL report a pass status when the published sidecar is non-smoke, its `last_coverage_p90` is greater than or equal to the coverage floor of 0.85, and the recorded sha matches the published version.
4. IF the published sidecar is marked as a smoke artifact, THEN THE C43 gate SHALL report a failure status.
5. IF the published held-out calibration coverage is below the 0.85 coverage floor, THEN THE C43 gate SHALL report a failure status.
6. IF the sha recorded in the registry is not present in the published version string, THEN THE C43 gate SHALL report a failure status indicating drift.
7. WHEN the published checkpoint is loaded through the serving path, THE flagship agent SHALL serve non-degraded model output rather than Degraded_Serving output.
8. THE training and publishing pipeline SHALL complete at $0 using only free-GPU and free-hosting resources (I-1).

### Requirement 6: Guarantee the uplift measurement is trustworthy

**User Story:** As a skeptical reviewer, I want the uplift measurement to be attribution-clean, adequately powered, fidelity-bounded, and self-scrutinized, so that the reported gain reflects real decision quality rather than a measurement artifact.

#### Acceptance Criteria

1. THE Uplift_Harness SHALL derive each replicate seed from only the scenario seed and replicate index, so that replicate `i` of the Consensus_Arm and of every Baseline_Arm is driven by the identical seeded twin realization.
2. IF an arm would be driven by a seed that does not match the replicate seed derived from `(scenario.seed, replicate_index)`, THEN THE Uplift_Harness SHALL reject that configuration rather than accept it — both arms MUST use the exact derived replicate seed.
3. THE Uplift_Harness SHALL apply the identical closed-loop cadence, unit-cost derivation, and twin construction to the Consensus_Arm and every Baseline_Arm, so that no arm-asymmetry favors one arm.
4. WHEN the assembled result classifies a pair as favorable to SYNAPSE, THE Uplift_Harness SHALL require the effect to be statistically significant at the contract alpha and to meet or exceed the per-KPI MDE before classifying it as `SYNAPSE_WINS`.
5. THE Uplift_Harness SHALL compute the twin-vs-reference KL divergence and report whether the result is within the committed Fidelity_Bound threshold.
6. IF the twin KL divergence exceeds the committed Fidelity_Bound threshold, THEN THE Uplift_Harness SHALL report the result as outside the Fidelity_Bound.
7. WHEN every classified pair is `SYNAPSE_WINS`, THE Uplift_Harness SHALL raise the All_Wins_Guard warning prompting a measurement-bias review.
8. THE Consensus_Arm and Baseline_Arm SHALL observe only the same twin state fields, so that no arm receives privileged information (no leakage).

### Requirement 7: One-command $0 reproduction with honest failure semantics

**User Story:** As an independent verifier, I want a single documented command that reproduces the proof at $0 and fails honestly when a required input or capability is missing, so that I can trust the result is real and repeatable rather than fabricated.

#### Acceptance Criteria

1. THE Uplift_Harness SHALL expose a single command (`python -m uplift.cli`) that runs the closed-loop counterfactual on the declared adversarial seeds and writes the result artifact read by the C60 gate.
2. WHEN the reproduction command runs, THE command SHALL disclose in its output that data provenance is synthetic-only and that no external paid service is used.
3. IF the pre-registered Metric_Contract is missing or malformed, THEN THE command SHALL exit with a non-zero status naming the missing input and SHALL strictly print no Headline_Uplift number to stdout and write none to the result artifact.
4. IF no scenario completes for any arm, THEN THE command SHALL exit with its no-completed-run failure status; HOWEVER a missing or malformed Metric_Contract failure (per criterion 3) SHALL take priority over and override the no-completed-run status.
5. WHEN the Consensus_Arm or the required model is unavailable, THE command SHALL degrade to Honest_Failure by recording failed runs and marking the result incomplete rather than crashing or fabricating a decision.
6. THE reproduction command SHALL state the version-controlled noise tolerance of no more than 1.0 percentage point in its output.

### Requirement 8: Pin documentation and headline claims to mechanical reality

**User Story:** As a reader of the repository, I want the README/docs headline pinned to the real mechanical verification output, so that the stated pass/fail counts and the uplift claim cannot silently diverge from what the gates actually report.

#### Acceptance Criteria

1. THE README headline SHALL report the PASS, FAIL, PARTIAL, and SKIP counts and the TOTAL that each equal the corresponding value in the machine-readable summary emitted by executing the current `verify_claims` suite (currently 53 registered checks), replacing the stale "16 PASS / 3 FAIL / 0 SKIP" literal.
2. THE C56 `doc_truth` gate SHALL register a claim that pins each README headline count (PASS, FAIL, PARTIAL, SKIP, and TOTAL) to the corresponding value obtained by executing the `verify_claims` suite and reading its emitted summary, and SHALL derive those actual counts from the suite output at evaluation time rather than from any value hardcoded in the gate.
3. IF any README headline count differs from the corresponding value in the `verify_claims` suite summary, THEN THE C56 gate SHALL exit with a non-zero failure status that names each drifted status category together with its README-claimed value and the suite-reported value.
4. WHERE the uplift claim is stated in the README or docs, THE documentation SHALL describe the uplift as proven only when a co-located fully-powered proof result artifact (a run of at least the INV-TW-002 MIN_SCENARIOS replicate floor per arm) records a Headline_Uplift greater than or equal to the committed `UPLIFT_FLOOR`, and SHALL otherwise describe the uplift as unproven.
5. IF a source file that a pinned C56 claim depends on is missing or unreadable, THEN THE C56 gate SHALL report a skip status for that claim naming the absent source, and SHALL NOT count that claim as a pass.
6. IF the `verify_claims` suite cannot be executed or its emitted summary cannot be parsed when the C56 headline-count claim is evaluated, THEN THE C56 gate SHALL report a skip status for that claim naming the failure, and SHALL NOT report a pass.
7. WHILE the `verify_claims` suite executes, THE suite SHALL assign every registered check to exactly one status category it emits (PASS, FAIL, PARTIAL, or SKIP), such that the four category counts sum to the reported TOTAL and no check is silently omitted from the count.

### Requirement 9: Preserve existing passing tests and invariants

**User Story:** As a SYNAPSE maintainer, I want all 623 currently passing tests and the core invariants to keep passing after this feature lands, so that closing the uplift gap does not regress the genuinely strong existing engineering.

#### Acceptance Criteria

1. WHEN the full existing test suite is run after this feature is implemented, THE test suite SHALL report at least the 623 previously passing tests as passing.
2. THE feature SHALL preserve invariant I-1 by adding no paid-API dependency to any reproduction or verification path.
3. THE feature SHALL preserve invariant I-2 by keeping agent reward signals independent.
4. THE feature SHALL preserve invariant I-3 by validating decision-request and decision schemas at the harness/consensus boundary.
5. THE feature SHALL preserve invariant I-5 by keeping confidence-gated human-in-the-loop escalation intact in the consensus path.
6. THE feature SHALL preserve invariant I-7 by keeping honest degradation behavior for unavailable models and arms.
7. THE feature SHALL preserve invariant I-14 by keeping consensus context append-only.
8. THE feature SHALL reuse the existing consensus protocol, tier router, audit hash-chain, and honesty-contract modules without rewriting their logic.

### Requirement 10: Scope limits and non-goals

**User Story:** As a SYNAPSE maintainer, I want explicit scope boundaries for this feature, so that the proof effort stays focused on measured uplift and does not expand into out-of-scope production concerns.

#### Acceptance Criteria

1. THE feature SHALL NOT introduce real customer data ingestion; all measurement SHALL use synthetic seeds.
2. THE feature SHALL NOT introduce multi-tenancy.
3. THE feature SHALL NOT require a GKE or other paid cloud deployment to reproduce the uplift proof.
4. THE feature SHALL scope its trained-model obligation to at least one flagship checkpoint (`demand_prophet`) and SHALL NOT require every agent to serve a real model for the proof to be valid.
5. THE feature SHALL define success as a Powered_Run (n ≥ MIN_SCENARIOS per arm) measuring a Headline_Uplift strictly greater than 0.0 percentage points, within the committed Fidelity_Bound, reproducible via a single command within the committed 1.0 pp noise tolerance, and SHALL NOT treat the presence of additional code or tests alone as satisfying that success.
6. IF a Powered_Run honestly measures a Headline_Uplift that is zero, negative, unavailable, or incomplete, THEN THAT outcome SHALL be treated as a valid non-success result (not an integrity failure of this feature) and SHALL NOT ratchet `UPLIFT_FLOOR` above 0.0.
7. IF a measured result falls outside the committed Fidelity_Bound, THEN it SHALL NOT count as success regardless of the Headline_Uplift magnitude.
