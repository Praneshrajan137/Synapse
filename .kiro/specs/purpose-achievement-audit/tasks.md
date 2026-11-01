# Implementation Plan: Purpose Achievement Audit (remediation)

## Overview

This plan implements the remediation design in dependency order: **E1 enforcement spine
-> E2 behavioural probes -> E4 chain verifier -> E3 dispatch choke point -> E5
measurements -> E6 console effectiveness**. E1 comes first because it makes ten of the
fourteen findings mechanically detectable at the commit that introduces them, which is
the cheapest ordering available.

Language: **Python** for gates, orchestrator, and audit paths (`mypy --strict`,
Pydantic v2, `structlog`); **TypeScript** for the frontend harness and scorecard
(fast-check for its properties). No new runtime dependency (I-1) - Hypothesis, PyYAML,
Pydantic, structlog and fast-check are already present.

Verification routing under **I-0**: every task below is verified locally only by
`getDiagnostics` on the changed file plus, at most, a single-file run
(`HYPOTHESIS_PROFILE=dev pytest <one file> -m "not slow" -x -q --tb=line -p no:randomly`).
Every heavy workload (powered uplift, Postgres chain walk, browser harness, mutation,
coverage seeding, golden-trace replay, `@pytest.mark.slow` properties) is wired into a
named workflow under `.github/workflows/` and is **never** run on this machine.

Property tests: exactly one per design property, 37 total. `max_examples` is never
hardcoded - it is inherited from the root `conftest.py` profiles (`dev`=10, `heavy`=100,
`ci`/`default`=500, `nightly`=5000). Properties that drive the SimPy twin, the real
`ConsensusProtocol`, a subprocess harness, or a browser carry `@pytest.mark.slow`.
Every property test carries the tag comment
`# Feature: purpose-achievement-audit, Property {N}: {property text}`.

### Operator decisions required before the tasks that depend on them

- **CF-1 / task 7.7** - confirm that R4.4's "audit record" is satisfied by a joined
  append-only `decision_data_provenance` row (I-4 forbids touching `make_canonical_row`).
- **CF-3 / task 4.1** - the coverage non-vacuity gate is registered only after one
  `ci.yml::quality-gates` run on `main` seeds the nine zero floors.
- **CF-5 / task 8.1** - the dispatch choke point and twin veto change decision
  behaviour and need a new ADR before task 8.5 lands.
- **CF-6 / task 7.3** - the deploy-time chain verify becomes blocking only after the
  migration-boundary constant is committed and one deploy produces a green walk.

## Tasks

- [x] 1. Committed configuration and shared test strategies
  - [x] 1.1 Create the machine-read quality configuration files and their schemas
    - Add `infrastructure/quality/doc-number-pins.yaml`, `gate-mutations.yaml`,
      `blocking-steps.yaml`, `replay-floors.yaml` (KV-cache `0.70`, tier routing `0.80`),
      `ratchets.json`, `dead-modules.yaml`, `required-checks.yaml`, plus the chain
      migration-boundary constant and the anchor freshness bound
    - Add JSON schemas for `required-checks.yaml` and `gate-mutations.yaml`; every file is
      read with `encoding='utf-8'` (E-S13-07)
    - Every threshold this feature introduces lives here so it is pinnable (AD-13)
    - _Requirements: 6.11, 7.2, 7.6, 7.7, 7.8, 11.8, 13.9, 14.1_

  - [x] 1.2 Create Hypothesis and fast-check strategy modules
    - `tests/verify/strategies.py`: check-result multisets, id sets, workflow/step shapes,
      document+source pin pairs, threshold sequences, coverage reports
    - `packages/tests/strategies_audit.py`: `ChainRow` sequences, canonical decisions,
      perturbation operators
    - `frontend/spec/effectiveness/arbitraries.ts`: scorecard rows, job sets, interruption sets
    - No `@settings(max_examples=...)` anywhere; profiles come from the root `conftest.py`
    - _Requirements: 1.1, 6.1, 7.4, 8.1_

- [x] 2. E1 - the enforcement spine
  - [x] 2.1 Implement `scripts/audit/registry_gate.py`
    - `RegistryVerdict` (frozen Pydantic) + `evaluate()` + `run(as_json, check)`; imports
      `verify_claims.collect_results()` **in-process** (no subprocess, no 900s timeout, no
      recursion-guard interaction)
    - Verdict order: no registered ids -> unavailable; missing ids -> fail naming each;
      all-SKIP -> unavailable; any FAIL -> fail naming each id and status; else pass
    - Exit codes `0` / `1` / `2`; `2` is non-passing (I-7: a SKIP is not a PASS)
    - _Requirements: 1.1, 1.3, 1.6, 1.7, 2.9_

  - [x] 2.2 Write property test for the registry verdict
    - **Property 1: Registry verdict is a total function of the result set**
    - **Validates: Requirements 1.1, 1.3, 1.7, 1.8, 2.9**

  - [x] 2.3 Add identity coercion and `--check` to `scripts/audit/verify_claims.py`
    - `_run_check` coerces a result whose `cid` differs from the registered id to `FAIL`
      naming both (AD-14); existing raise/type/status coercions unchanged
    - Fix C46's SKIP branch to return `cid="C46"`; `run()` gains `check: bool` delegating to
      `registry_gate.run(check=True)` so there is one verdict implementation
    - _Requirements: 1.1, 10.5_

  - [x] 2.4 Write property test for reported check identity
    - **Property 10: A check reports the identifier it is registered under**
    - **Validates: Requirements 10.5**

  - [x] 2.5 Make `scripts/audit/doc_truth.py` non-maskable and data-driven
    - `ClaimResult` gains `required: bool`; `evaluate()` returns unavailable when any
      required claim fails or skips, and an `ok` sibling never supplies a passing verdict
    - Mark `_claim_readme_headline_counts` required; migrate `_claim_spec_threshold` into the
      `doc-number-pins.yaml` table; add `NumericPin` with `threshold` / `flag` /
      `blocking-gate` / `required-job` kinds and `yaml_path:` / `json_path:` extractors
    - _Requirements: 1.4, 1.6, 7.5, 7.10, 11.8, 14.3_

  - [x] 2.6 Write property test for claim masking
    - **Property 2: No claim can mask an unavailable required claim**
    - **Validates: Requirements 1.4, 1.6**

  - [x] 2.7 Write property test for numeric pins
    - **Property 5: A documented value equals its mechanical source**
    - **Validates: Requirements 7.5, 7.10, 11.8, 14.3**

  - [x] 2.8 Implement `scripts/audit/ledger_gen.py`
    - `render(verdict, previous)` projects one row per registered check plus summary counts
      and the README headline counts into the delimited
      `<!-- generated:begin -->` / `<!-- generated:end -->` region of `docs/state/CURRENT.md`,
      preserving hand-authored prose outside the markers
    - `--write` / `--check`; `--check` prints a unified diff on drift
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6, 10.7, 10.8, 10.9_

  - [x] 2.9 Write property test for the generated ledger
    - **Property 9: The generated ledger round-trips against its registry execution**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.6, 10.7, 10.8, 10.9**

  - [x] 2.10 Implement `scripts/audit/workflow_shape_truth.py`
    - `StepShape` model; classify `|| true`, `|| echo`, `; exit 0`, `continue-on-error: true`
      as discarding; a step in `blocking-steps.yaml` that does not propagate FAILs naming
      file and step; any other non-propagating step must carry `ADVISORY`/`informational`
    - Include the production-bundle assertion that keeps `window.__atlasHarness` out of the
      shipped bundle (AD-12)
    - _Requirements: 1.8, 6.13, 8.9, 11.3_

  - [x] 2.11 Write property test for exit-status propagation
    - **Property 4: A declared-blocking step propagates its exit status**
    - **Validates: Requirements 1.8, 6.13, 8.9, 11.3**

  - [x] 2.12 Implement `scripts/audit/gate_surface.py`
    - Parse `.github/workflows/*.yml`, evaluate `on:`/`if:` against `push:main`,
      `pull_request`, `tag:v*`, walk `needs:` edges, render `docs/state/GATE_SURFACE.md`
    - A job whose dependency is not selected renders `NOT EXECUTED` and can never be
      reported successful; `--check` diffs like the ledger generator
    - _Requirements: 11.1, 11.2, 11.7, 11.9_

  - [x] 2.13 Write property test for the gate-surface record
    - **Property 11: The generated gate-surface record round-trips and respects dependencies**
    - **Validates: Requirements 11.1, 11.2, 11.7, 11.9**

  - [x] 2.14 Implement `scripts/audit/required_checks_truth.py` and the reconciliation workflow
    - Validate `required-checks.yaml` against its schema; every declared job name must
      resolve to a job defined in a workflow file
    - Add `.github/workflows/required-checks-reconcile.yml`: scheduled `gh api` read of
      `branches/main/protection`, artifact carrying the read timestamp, fail on difference or
      unreadable response - never report a verified set it could not read (I-7)
    - _Requirements: 14.1, 14.2, 14.4, 14.5, 14.6_

  - [x] 2.15 Write property test for the required-check declaration
    - **Property 12: The required-check declaration resolves to real jobs**
    - **Validates: Requirements 14.2**

  - [x] 2.16 Write unit tests for the spine's example-class facts
    - Markdown-only change set still selects the truth-gates job (R1.5, R11.4)
    - `required-checks.yaml` exists and validates against its schema (R14.1)
    - _Requirements: 1.5, 11.4, 14.1_

  - [x] 2.17 Wire the blocking `truth-gates` job and register the spine's checks
    - New `ci.yml::truth-gates` job with **no** `paths-ignore` (CF-2), running
      `registry_gate`, `doc_truth`, `ledger_gen --check`, `gate_surface --check`,
      `workflow_shape_truth`, `required_checks_truth`; no `continue-on-error`, no `|| true`
    - Register the new checks in the Check_Registry so they are enforced, and add
      `push: branches: [main]` to `mutation.yml::mutation-fast` so a merge commit is gated
    - Heavy `quality-gates` keeps its `paths-ignore`
    - _Requirements: 1.1, 1.2, 1.5, 1.8, 11.5, 11.6_

- [ ] 3. Checkpoint - enforcement spine
  - Ensure all tests pass, ask the user if questions arise. Scope local runs to changed
    files under `HYPOTHESIS_PROFILE=dev -m "not slow"`; the full registry execution runs in
    `ci.yml::truth-gates`, not locally (I-0).
  - **DELIBERATELY LEFT UNTICKED. See the consolidated status under checkpoint 13.** Every
    subtask of sections 1-2 has landed and the spine's gates pass locally
    (`registry_gate`, `doc_truth` 11/11, `ledger_gen`, `gate_surface`,
    `required_checks_truth`), but `C64` still FAILs on pre-existing R11.3 debt and the
    instruction here is "ensure all tests pass". Ticking a checkpoint while a declared
    check FAILs is precisely the SKIP-reported-as-PASS pattern this feature exists to
    remove (I-7), so the box stays open and the state is recorded instead.

- [x] 4. E1 - ratchets, coverage floors, and replayed thresholds (R7)
  - [x] 4.1 Add measured-floor enforcement to the coverage scripts
    - `scripts/coverage_per_package.py --require-measured-floors`: a gated package with
      `line: 0.0` and a recorded `measured_at` FAILs naming it; `measured_at: null` reports
      `SKIP - unmeasured`, never PASS (CF-3)
    - `scripts/coverage_ratchet.py --apply` writes `measured_at` and `source_run` beside each
      bumped floor
    - _Requirements: 7.1, 7.2, 7.9_

  - [x] 4.2 Write property test for coverage floors
    - **Property 7: Coverage floors are non-vacuous and named on failure**
    - **Validates: Requirements 7.1, 7.2, 7.9**

  - [x] 4.3 Implement `scripts/audit/ratchet_truth.py`
    - Maintain `infrastructure/quality/ratchets.json` as the highest-ever committed value for
      coverage floors, Stryker `break`, mutation survival ceilings, `UPLIFT_FLOOR`, the
      dead-module baseline, and the actuating-agent baseline
    - A committed value below its recorded high FAILs naming threshold, previous, proposed;
      a ratchet constant differing from the shipped configuration it guards FAILs naming both
      files (the Stryker `26`-vs-`50` hole)
    - _Requirements: 2.10, 7.4, 7.8_

  - [x] 4.4 Write property test for ratchets
    - **Property 6: Ratchets are monotone, config-agreeing, and data-gated**
    - **Validates: Requirements 2.10, 7.4, 7.8**

  - [x] 4.5 Implement `scripts/audit/replay_metrics.py`
    - Replay the 200 golden traces (`tests/eval/generate_traces.py`, seed `0xCAFEBABE`), emit
      measured KV-cache hit rate and tier-routing accuracy against `replay-floors.yaml`
    - Non-zero below floor; unavailable (never PASS) when traces or the harness are missing
    - Runs in `ci.yml::quality-gates` only
    - _Requirements: 7.3, 7.6, 7.7_

  - [x] 4.6 Write property test for measured-threshold gates
    - **Property 8: A measured threshold gate reflects the measurement**
    - **Validates: Requirements 7.3, 7.6, 7.7**

- [x] 5. E2 - behavioural probes
  - [x] 5.1 Implement `scripts/audit/gate_fault_injection.py`
    - `MutationOperator` / `FaultInjectionResult`; `inject()` applies an operator inside a
      **temporary copy of the real tree**; `falsifies()` runs the gate as a **subprocess** and
      reports whether it exited non-zero naming the mutated subject
    - Never monkeypatch a gate's evaluator; a check with no declared operator is reported in
      the `reporting_tool` set and excluded from PASS-eligibility
    - _Requirements: 1.2, 9.5, 12.3, 12.7_

  - [x] 5.2 Write property test for declared falsification
    - **Property 3: Every gate is falsified by its declared mutation**
    - **Validates: Requirements 1.2, 9.5, 12.3, 12.7**

  - [x] 5.3 Make `scripts/audit/agency_truth.py` classify by observed world delta
    - `ActuationClass` (`ACTUATING` / `EVENT_ONLY` / `INERT` / `UNCLASSIFIED`) and
      `AgentActuationReport`; verdict from a `WorldRuntime.perceive()` snapshot -> `execute()`
      -> re-read delta, with the AST pass demoted to a fast pre-filter over **reachable**
      statements only
    - `producer_wired` read from each `agents/*/inference/serve.py`; an agent claiming
      `kafka_published=True` with no wired producer FAILs; an unparseable handler is
      `UNCLASSIFIED` **and** a FAIL naming the file; the reported count is the compared count
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.6, 9.7, 9.8, 9.9_

  - [x] 5.4 Write property test for actuation classification (slow)
    - **Property 30: Actuation classification is behavioural and total**
    - **Validates: Requirements 9.1, 9.2, 9.4, 9.6, 9.7, 9.8**
    - `@pytest.mark.slow` (drives a real `WorldRuntime`); runs in `ci.yml::uplift-verify`

  - [x] 5.5 Derive oracle-layer membership in `scripts/audit/oracle_truth.py`
    - `OracleSubject` with `imports_subject`, `invokes_subject_on_asserted_path`,
      `reference_independent`, `tolerance_constraining`
    - Re-register `tests/oracle/test_pricing_impact_oracle.py` as Layer 4 Metamorphic and add a
      genuine Layer 6 oracle test that imports `agents.pricing_oracle`, invokes its elasticity
      path, and compares against the twin; add the dated-rationale + removal-condition schema
      check to C61's allowlist
    - _Requirements: 12.1, 12.2, 12.5, 12.6_

  - [x] 5.6 Write property test for oracle membership
    - **Property 37: Oracle-layer membership is earned, not declared**
    - **Validates: Requirements 12.1, 12.2, 12.5, 12.6**

  - [x] 5.7 Make `frontend/spec/check_fe_invariants.py` read executed assertions
    - Consume the Vitest/Playwright JSON reporter output instead of calling `.exists()`; an
      invariant marked `enforced` requires at least one executed, non-skipped assertion tagged
      `FE-INV-###`; file existence and an all-skipped run are both rejected
    - `FE-INV-056` fails until task 11.1 lands - that is the honest state (I-7)
    - _Requirements: 8.7, 12.4_

  - [x] 5.8 Write property test for enforced invariants
    - **Property 35: An enforced invariant has an executed assertion**
    - **Validates: Requirements 8.7, 12.4**

- [ ] 6. Checkpoint - probes
  - Ensure all tests pass, ask the user if questions arise. The slow agency probe and the
    fault-injection subprocess sweep run in `ci.yml::uplift-verify`; do not run them locally.
  - **UNTICKED, and this one cannot honestly be closed from this machine at all.** The two
    things it asks about - the slow agency probe and the fault-injection subprocess sweep -
    are exactly what it forbids running locally (I-0, category 3/4). Their first real signal
    is `ci.yml::uplift-verify`. Sections 4-5 have all landed. See checkpoint 13.

- [x] 7. E4 - audit chain verification (R6)
  - [x] 7.1 Implement the pure walker `orchestrator/audit/chain_walk.py`
    - `ChainRow` (frozen), `BreakKind` (`PAYLOAD` / `LINKAGE` / `NULL_AFTER_BOUNDARY` /
      `HEAD_UNREACHABLE`), `ChainBreak`, `WalkReport`, `walk(rows, boundary, recorded_head, max_rows)`
    - Recompute `hash_payload_for_row(prev_walked, row.canonical)` for payload breaks and
      compare stored `prev_hash` against the walked predecessor's `current_hash` for linkage
      breaks; the `row.prev_hash or prev_hash` fallback is removed (AD-8)
    - Legacy pre-boundary null rows counted separately and excluded from `verified`; zero rows
      -> `not_verified`; report `snapshot_upper_bound`; exceed row/wall-clock bound -> non-zero
    - `make_canonical_row` is **not** touched (I-4, byte-pinned)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.13_

  - [x] 7.2 Write property test for chain perturbation detection
    - **Property 18: Chain verification detects every single-row perturbation**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.10**

  - [x] 7.3 Implement `orchestrator/audit/cli.py` and unswallow its call sites
    - `python -m orchestrator.audit.cli verify [--dsn] [--since] [--max-rows] [--timeout]`:
      ordered snapshot in one transaction, `ChainRow`s via the untouched `make_canonical_row`,
      `walk()`, ASCII-only report, exit `0` verified / `1` broken / `2` unavailable
    - `scripts/synapse_cli/audit_verify.py` becomes a thin delegating alias keeping its argv
      contract; drop `|| echo` from `Makefile:592` and `cd-gcp.yml:542` (blocking per CF-6,
      once the boundary constant is committed)
    - _Requirements: 6.9, 6.13, 6.14_

  - [x] 7.4 Implement `scripts/audit/command_path_truth.py`
    - Resolve every `python -m <module>` path and console-script name named by an
      audit-verification step in the workflows and Makefile against the tree and
      `pyproject.toml` entry points; FAIL naming each unresolvable path and each such step
      whose exit status is discarded
    - _Requirements: 6.14_

  - [x] 7.5 Write property test for named-command resolution
    - **Property 20: Every named command resolves**
    - **Validates: Requirements 6.14**

  - [x] 7.6 Anchor to the chain head and gate anchor freshness
    - `orchestrator/audit/anchorer.py`: `AnchorRecord` commits to the chain **head hash**
      (compact JSON, E-S9-03); add a scheduled caller in `publish-audit-anchor.yml`
    - New `scripts/audit/anchor_truth.py` reports the chain **unverifiable** when no anchor
      exists or the newest is older than the committed freshness bound - never verified
    - _Requirements: 6.11, 6.12_

  - [x] 7.7 Write property test for anchoring
    - **Property 19: An anchor commits to the head it claims**
    - **Validates: Requirements 6.11, 6.12**

  - [x] 7.8 Add the append-only `decision_data_provenance` table (CF-1)
    - `DecisionDataProvenance` in `orchestrator/audit/models.py` (`decision_id`,
      `source_class`, `is_synthetic`, `feed_revision`, `observed_at`)
    - Canonical migration under `orchestrator/audit/migrations/`, mirrored under
      `infrastructure/postgres/` for Docker init (E-S9-14), with UPDATE/DELETE revoked from
      `synapse_app`; follows the `decision_outcomes` precedent, `make_canonical_row` untouched
    - _Requirements: 4.4_

  - [x] 7.9 Write property test for canonical rows and append-only history
    - **Property 21: Canonical rows round-trip and audit history is append-only**
    - **Validates: Requirements 4.4** (and invariant I-4)

  - [x] 7.10 Write integration and unit tests for chain scope
    - Integration in `integration.yml` (has Postgres): seeded row deletion detected non-zero;
      one append-during-walk snapshot isolation case (R6.10)
    - Unit: `api/routers/decisions.py`'s `chain_verified` field and the Atlas copy state
      row-level integrity only, making no deletion or re-link claim (R6.15)
    - _Requirements: 6.2, 6.10, 6.15_

- [x] 8. E3 - production choke points (requires the CF-5 ADR)
  - [x] 8.1 Record the dispatch ADR and add `ConfidenceThresholdProvider`
    - Write the new ADR (next free number) covering the single dispatch choke point,
      Fast_Path guardrail/HITL application, and the Tier-4 twin veto; note that uplift numbers
      measured before and after are not comparable
    - `ConfidenceThresholdProvider` protocol (`current()`, `reload()`) backed by
      `orchestrator/config.py`; the engine reads `current()` per validation instead of
      capturing a float at construction; reload builds a new settings instance, mutating no
      frozen model and feeding no LLM system prompt (I-13 unaffected)
    - _Requirements: 5.4_

  - [x] 8.2 Write property test for threshold reload
    - **Property 24: Escalation tracks the configured threshold**
    - **Validates: Requirements 5.4**

  - [x] 8.3 Make guardrail configuration total in `orchestrator/guardrails/rules.py`
    - `_validate_configuration()` at construction raises `GuardrailConfigurationError` naming
      any `HARD_GUARDRAILS` entry declaring BLOCK/REJECT/ESCALATE with no check function
    - Implement `_check_privacy_boundary` (no cross-store raw demand payload in the selected
      action, consistent with I-11) so the existing `BLOCK` declaration becomes true rather
      than downgrading a stated guarantee; the essential-price CLIP stays a clip
    - _Requirements: 5.3_

  - [x] 8.4 Write property test for guardrail configuration totality
    - **Property 23: Guardrail configuration is total**
    - **Validates: Requirements 5.3**

  - [x] 8.5 Add `_ratify_and_dispatch` to `orchestrator/consensus/protocol.py`
    - Single path from built decision to dispatched action, traversed by `_fast_path` **and**
      `_full_path`; the only caller of `GuardrailEngine.validate_decision`,
      `HitlEscalator.escalate`, `guardrails.rules.execute_consensus` (putting the `@deal.pre`
      I-5 / `@deal.post` I-4 contract on the production path) and `_phase_execute`
    - A BLOCK violation or a sub-threshold confidence withholds dispatch on every tier and
      leaves `execution_confirmations` empty; `escalate` still awaits a human future only
    - _Requirements: 5.1, 5.2, 5.6, 5.7, 13.7_

  - [x] 8.6 Write property test for the confidence gate on every tier (slow)
    - **Property 22: The confidence gate applies on every tier**
    - **Validates: Requirements 5.1, 5.2, 5.6, 5.7**
    - `@pytest.mark.slow` (real `ConsensusProtocol`); runs in `ci.yml::uplift-verify`

  - [x] 8.7 Make selection and twin verdicts consequential
    - `_phase_twin_verify` returns a `TwinVerdict`; disagreement beyond the declared bound
      withholds dispatch or escalates instead of only stamping `audit_trace`
    - `_build_decision` records the Pareto front as the set selection ran over and asserts the
      ratified action is a member; a debate round that changed no payload and no selection is
      stamped `advisory: true`
    - _Requirements: 13.4, 13.5, 13.8_

  - [x] 8.8 Write property test for selection and twin consequence (slow)
    - **Property 26: Selection and twin verdicts are consequential**
    - **Validates: Requirements 13.4, 13.5, 13.8**
    - `@pytest.mark.slow` (drives the twin and the real protocol)

  - [x] 8.9 Make HITL timeout records honest in `orchestrator/hitl/escalation.py`
    - Replace `{"action": "timeout_<name>"}` with
      `{"action": "timeout_no_action", "requested": ..., "dispatched": False}`;
      `dispatched: True` only when a matching `execution_confirmations` entry exists
    - A timed-out escalation is resolved and its pending entry removed; two outstanding
      escalations resolve independently
    - _Requirements: 5.5, 5.8, 5.9_

  - [x] 8.10 Write property test for timeout records
    - **Property 25: Timeout records match dispatch reality**
    - **Validates: Requirements 5.5, 5.8, 5.9**

  - [x] 8.11 Enforce module liveness in `scripts/audit/module_liveness.py`
    - Total classification (alive / tooling / test / seam-exempt / dead); the only exemption is
      a `# synapse: seam(reason=..., adr=ADR-0NN)` marker; `DEAD_BASELINE` moves to the named
      `infrastructure/quality/dead-modules.yaml`
    - Two projections: a property test whose target no non-test module imports is reported as
      validating a model; a symbol encoding an invariant pre/postcondition that only tests
      invoke FAILs naming symbol and invariant
    - Register the check so it can bite
    - _Requirements: 13.1, 13.2, 13.3, 13.7, 13.9_

  - [x] 8.12 Write property test for liveness classification
    - **Property 27: Liveness classification is total and baseline-consistent**
    - **Validates: Requirements 13.1, 13.2, 13.3, 13.7, 13.9**

- [ ] 9. Checkpoint - choke points
  - Ensure all tests pass, ask the user if questions arise. Confirm the CF-5 ADR is in place
    before 8.5/8.7 are merged, and that no slow property was run locally (I-0).
  - **UNTICKED.** Sections 7-8 landed, and ADR-054 (the CF-5 dispatch ADR) is in place - but
    task 12.6 records that **ADR-054 is now partly stale**: its D1 order of operations is
    four steps where the code has five, and its Context item 2 still calls the `@deal.pre`
    contract test-only. 12.1a amended `_ratify_and_dispatch`'s docstring but not the ADR. So
    "confirm the CF-5 ADR is in place" is satisfied in letter and not in substance. No slow
    property was run locally (confirmed: the only pytest invocations this session were
    `tests/verify/test_required_checks_resolution_property.py` and
    `tests/verify/test_property_inventory_consistency.py`, both non-slow, single-file). See
    checkpoint 13.

- [x] 10. E5 - the three missing measurements
  - [x] 10.1 Add run provenance to the uplift artifact
    - `UpliftProvenance` in `uplift/harness.py` (`arms`, `replicates_per_arm`, `revision`,
      `run_id`, `seeds`, `written_at`); artifact carries `incomplete: false`, finite
      `headline_uplift`, numeric `kl_divergence`, boolean `within_fidelity_bound`
    - Serialise with `json.dumps(obj, sort_keys=True, separators=(',',':'))` so two runs of the
      same seed set are byte-comparable; add `PoweredProof.from_artifact`
    - _Requirements: 2.3_

  - [x] 10.2 Write property test for artifact round-tripping
    - **Property 14: The uplift artifact round-trips losslessly and canonically**
    - **Validates: Requirements 2.3**

  - [x] 10.3 Rewrite the verdict path in `scripts/audit/uplift_truth.py`
    - `admit(artifact, run) -> Admission` rejects incomplete, unpowered
      (`< MIN_POWERED_REPLICATES`), provenance-mismatched, or version-controlled artifacts with
      the reason printed; replace the `headline_uplift`-only `read_measured_uplift`
    - `verdict(proof)` derives from the currently-uncalled `uplift.uplift_floor.is_proven_uplift`
      (`EXIT_REGRESSION` below floor, `EXIT_UNAVAILABLE` otherwise); a floor raise is admitted
      only through `ratchet_to_measured` against a same-run `PoweredProof`
    - Remove `artifacts/uplift/result.json` from version control and git-ignore it; outside the
      generating job the check reports SKIP and is excluded from the PASS count (AD-9, CF-4)
    - _Requirements: 2.1, 2.2, 2.4, 2.8, 2.9, 2.10_

  - [x] 10.4 Write property test for uplift admissibility
    - **Property 13: The uplift gate rejects inadmissible evidence**
    - **Validates: Requirements 2.1, 2.2, 2.4, 2.8**

  - [x] 10.5 Add the scheduled `.github/workflows/uplift.yml`
    - One job so evidence and verdict share a run: `python -m uplift.cli --full --replicates
      1000 --out artifacts/uplift/result.json` then
      `python -m scripts.audit.uplift_truth --check --require-fresh-run`
    - The job records a non-passing result when the harness cannot run; never executed locally
      (I-0 forbids `MIN_SCENARIOS`-scale runs on this machine)
    - _Requirements: 2.7_

  - [x] 10.6 Write property test for harness determinism (slow)
    - **Property 15: The harness is deterministic across processes**
    - **Validates: Requirements 2.5**
    - `@pytest.mark.slow` (two OS processes driving the harness)

  - [x] 10.7 Write property test for identical arms (slow)
    - **Property 16: Identical arms measure no uplift**
    - **Validates: Requirements 2.6**
    - `@pytest.mark.slow`; noise tolerance read from committed configuration, never hardcoded

  - [x] 10.8 Harden the published-checkpoint and task-claim checks
    - `scripts/audit/published_checkpoint_truth.py`: three-way absent / smoke / real
      classification with distinguishing details, `coverage_p90` floor comparison reporting
      measured and floor, `final_crps` recompute from the sidecar's held-out predictions within
      a declared tolerance, refusal to substitute a locally built checkpoint when the recorded
      sha cannot be fetched from the zero-cost source
    - New `scripts/audit/task_claim_truth.py`: a task record asserting a landed registry entry
      FAILs naming the record when the registry holds no validated non-placeholder entry
    - _Requirements: 3.1, 3.3, 3.4, 3.6, 3.7, 3.9_

  - [x] 10.9 Write property test for checkpoint claims
    - **Property 17: Checkpoint claims are classified honestly**
    - **Validates: Requirements 3.1, 3.3, 3.4, 3.6, 3.9**

  - [x] 10.10 Write unit and integration tests for checkpoint scope
    - Unit: the tmp-dir serving proof is labelled transport-and-adapter validation only and is
      not counted as evidence that a checkpoint is published (R3.8)
    - Integration (`training-smoke`): one resolution of a published entry through the serving
      path returning `degraded=false` with the recorded sha in its version string (R3.2)
    - _Requirements: 3.2, 3.8_

  - [x] 10.11 Derive world provenance and implement the external feed
    - `SourceProvenance` (`SEEDED` / `EXTERNAL` / `STUB`) and `WorldSource.provenance()`;
      `WorldState.is_synthetic` computed from the active source rather than pinned `True`
    - Implement `ExternalFeedSource.poll_arrivals` against `synapse.orders.demand` via
      `synapse_common.kafka_client` with jittered retries from `synapse_common.retry`
      (ADR-016); configured-but-unreachable returns a degraded state with zero arrivals and
      never falls back to the seeded generator
    - Initial inventory read from a non-seeded source; absent inventory degrades rather than
      substituting the literal default at `engine.py:334`
    - New `scripts/audit/feed_provenance.py` classifies every implementation and treats an
      unconditionally empty `poll_arrivals` as `STUB`; record provenance into
      `decision_data_provenance`
    - _Requirements: 4.2, 4.4, 4.5, 4.8, 4.9_

  - [x] 10.12 Write property test for derived provenance
    - **Property 28: World provenance is derived, never asserted**
    - **Validates: Requirements 4.2, 4.5, 4.8, 4.9**

  - [x] 10.13 Write property test for non-synthetic ingestion and replay (slow)
    - **Property 29: Non-synthetic input is ingested faithfully and replays deterministically**
    - **Validates: Requirements 4.1, 4.6**
    - `@pytest.mark.slow` (drives the twin and the sensor loop end to end)

  - [x] 10.14 Wire the stream-materialization consumer and register the topic check
    - Add a `data_fabric/feast/stream_materialization.py` service with a healthcheck to
      `docker/docker-compose.gcp.yml` (C50)
    - Register `scripts/audit/topic_consumer_truth.py` (reachable today only from `Makefile:22`)
      in the Check_Registry so a topic recorded with agent consumers must have a consuming
      service
    - _Requirements: 4.7_

  - [x] 10.15 Write unit test for topic-to-compose agreement
    - Every topic in `infrastructure/kafka/topics.json` recorded with `consumers` (not
      `consumers_planned`) resolves to a service in the deployed compose file
    - _Requirements: 4.7_

- [x] 11. E6 - console effectiveness (R8)
  - [x] 11.1 Implement the browser harness `frontend/spec/effectiveness/harness.ts`
    - `window.__atlasHarness` with `runTaskCompletion`, `driveResilience`, `driveFault`,
      `seedScenario`, `failWebGL`, imported only by an `import.meta.env`-guarded e2e-only entry
      excluded from the production bundle by a Rollup input split (AD-12)
    - Un-skip the six e2e specs that currently call `test.skip(true, ...)`
    - _Requirements: 8.1, 8.3_

  - [x] 11.2 Make the scorecard complete-or-failed and remove the SKIP escape hatches
    - **NOTE (orchestrator, from task 11.1): `frontend.yml::e2e-harness` currently selects
      ZERO harness specs, so FE-INV-056 cannot attest and R8 has no measured signal.**
      The job runs `pnpm build` (the production bundle, which by AD-12 has no harness) and
      `pnpm test:e2e --project=chromium task-completion.jtbd resilience.spec || true`, but
      the `chromium` project now carries `testIgnore: HARNESS_SPEC_PATTERN`, so those
      positional filters match nothing runnable. Fix is two lines: `pnpm build:e2e` and
      `pnpm test:e2e:harness` with the `|| true` removed.
      `playwright.harness.config.ts` already writes
      `artifacts/test-reports/playwright-harness.json`, which `frontend.yml:171` already
      passes to the gate via `--report`
    - **NOTE (from task 11.7): `spec/effectiveness/run-ratchet.ts` still loads the baseline
      through `parseScorecard`, not `checkCommittedBaseline`**, so the ratchet still accepts
      an authored ceiling. Wire the new check in, and add one blocking
      `pnpm effectiveness:baseline` step to the `effectiveness-ratchet` job. Expect it RED
      on landing: the committed baseline fails with 5 `missing-stamp` + 1 `uniform-metrics`,
      which is R8.10's finding becoming mechanical. Sequence it deliberately - it clears
      only once this task's emitter produces a measured baseline via `buildBaseline`
    - **NOTE: `frontend/tests/e2e/reconnect-replay.resilience.spec.ts` is deliberately
      still skipping** and must not be counted. Three blockers, none in 11.1's scope: no
      `[data-decision-row]` / `[data-decision-status]` identity anywhere in
      `frontend/src/**` (task 11.9 owns those surfaces), no `replay`-plan driver in
      `driveResilience`, and `src/lib/reconcile.ts` is still imported only by its own
      property tests (audit R13)
    - Emission requires a bijection between rows and the five declared Jobs-To-Be-Done; an
      unreachable harness, a missing job, a zero executed count, or any skipped job, resilience
      scenario, or fidelity comparison is a **failed result**, never a shorter scorecard
    - Remove `real-stack-fidelity.ts:376`'s "a real-stack SKIP is informational" rule and record
      it as a divergence; drop `|| true` from `frontend.yml:163` and `:288`
    - _Requirements: 8.1, 8.2, 8.3, 8.6, 8.8, 8.9_

  - [x] 11.3 Write property test for scorecard completeness
    - **Property 32: The scorecard is complete or the job fails**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.6, 8.8**
    - fast-check in `frontend/spec/effectiveness/`; browser-driven cases marked slow and run in
      `frontend.yml`
    - Landed as `frontend/spec/effectiveness/__tests__/scorecard-completeness.property.test.ts`,
      13 facets, biconditional (a complete run is ACCEPTED as well as an incomplete one failing)
    - **NOTE: `evaluateEmission` never cross-checks the ledger against the row set.** A run can
      report a job scenario `outcome: "skipped"` while offering a measured, stamped row for that
      same job; the only failure raised is `skipped-scenario` and the contradiction itself is
      invisible. Not exploitable today (the skip already fails the run, so nothing is emitted).
      Facet 8 pins the *current* behaviour rather than the arguable one. Worth a
      `skipped-job-with-row` kind if the ledger and the rows should have to agree
    - **NOTE: this file cannot establish R8.1's "the harness becomes reachable in the browser
      within its declared timeout."** It quantifies over the boolean a browser produces and does
      assert the `false` branch, but that `window.__atlasHarness` is ever actually observed stays
      observable only in `frontend.yml::e2e-harness` - which 11.2's NOTE records as selecting
      ZERO harness specs. Keep a browser-driven companion on the books until that fix lands

  - [x] 11.4 Write property test for ratchet sensitivity
    - **Property 33: The ratchet is sensitive to any degradation**
    - **Validates: Requirements 8.4**
    - Landed as `frontend/spec/effectiveness/__tests__/ratchet-sensitivity.property.test.ts`,
      7 facets. The metric set is derived from an exhaustive `Record<RatchetMetric, MetricFacet>`,
      so a fifth metric is a compile error rather than a silent coverage gap; the sensitivity
      facets loop over metric x subject every run instead of sampling one
    - **NOTE (R8.4 tolerance-policy gap, NEEDS A DECISION - not fixed):** `stepsPct` is a
      *relative* tolerance, so R8.4's own literal mutation - "adds one navigation step to each
      Job_To_Be_Done path" - is **invisible** whenever a baseline row carries `steps >= 20`,
      because `21 > 20 * 1.05` is false (`20 * 1.05 === 21` exactly in IEEE-754). The committed
      `scorecard.baseline.json` records `steps: 20` for all five jobs, so **a +1-step mutant
      passes the ratchet today.** The test deliberately does NOT assert this case: doing so would
      assert against the comparator's own documented semantics rather than against a defect, so
      the file is GREEN against shipped behaviour and the gap is recorded instead of hidden.
      Closing it needs a policy choice - give `steps` an absolute floor (regress on
      `> baseline + 1` OR `> baseline * 1.05`, whichever is smaller), or have the mutated variant
      add steps beyond 5%. Once chosen, the clause drops in as one more facet method
    - **NOTE: two further insensitivities, both deliberate elsewhere.** `interruptionPrecision` is
      compared only when *both* scorecards carry a value, so a fresh scorecard that LOST the
      measurement (`null`) silently skips the North-Star comparison (per R13.3; honest-emission
      side is 11.5). And a job present in the baseline but absent from the fresh scorecard is
      skipped, not named - the audit's zero-comparison finding, owned by Property 32

  - [x] 11.5 Compute interruption precision from collected data
    - `frontend/src/lib/interruption-precision.ts` computes precision as warranted / total from
      the run's collected interruptions; a literal-only computation FAILs
    - _Requirements: 8.5_

  - [x] 11.6 Write property test for interruption precision
    - **Property 34: Interruption precision responds to its inputs**
    - **Validates: Requirements 8.5**
    - Landed as
      `frontend/spec/effectiveness/__tests__/interruption-precision-responsiveness.property.test.ts`,
      8 facets. Threshold loaded from `infrastructure/quality/effectiveness-precision.json` via
      `parseInterruptionPrecisionPolicy` - `0.01` appears nowhere in the test. Generated
      interruptions are realized as *observed facts* and recorded through
      `openInterruptionLedger` -> `record` -> `seal` -> `compute`; the test never writes a
      `warranted` field, so it cannot drift from R13.1's warrant rules
    - The adversarial-constant facet is the falsifier: a bare number cannot reach
      `auditSeedResponsiveness` at all (branded outcome, not `number`), so the constant is
      realized as its observable signature - two runs, different inputs, coinciding values,
      divergence 0 - and must be reported `unresponsive`
    - **NOTE (expected RED on landing, two upstream causes):** no caller of
      `openInterruptionLedger` exists in `spec/effectiveness/harness.ts` yet, so **no run has
      ever produced a precision value**; and `PRECISION_SCAN_SCOPE` includes
      `frontend/tests/e2e/task-completion.jtbd.spec.ts`, which per the module's own docs still
      carries the four-object mirror the audit named - so `findCommittedInterruptionLiterals`
      reports findings there the day the scan first runs. Both belong to 11.1/11.2's CI wiring
    - **NOTE: `interruptionPrecision` (the pure kernel) is Property 18's subject** in
      `frontend/src/lib/__tests__/interruption-precision.property.test.ts` - bounds, empty-window
      `null`, all/none boundaries, independent oracle. Property 34 tests the *measurement*
      pipeline (ledger, policy, audit, scanner), not the formula. No overlap

  - [x] 11.7 Extend the effectiveness baseline schema
    - Per-row `harnessVersion`, `seed`, `capturedAt`; `proxyCeiling` kept verbatim; reject a
      baseline whose rows all carry identical `steps` and identical `latencyMs` as an authored
      ceiling
    - _Requirements: 8.10_

  - [x] 11.8 Write property test for the baseline
    - **Property 36: A baseline is a measurement, not a ceiling**
    - **Validates: Requirements 8.10**
    - Landed as `frontend/spec/effectiveness/__tests__/baseline-measurement.property.test.ts`,
      12 facets. Policy read from `infrastructure/quality/effectiveness-baseline.json` through
      `loadBaselinePolicy` - not one threshold restated, so a weakened policy shows up as a
      failing facet rather than a test that agrees with itself. Deliberately does NOT assert the
      committed `scorecard.baseline.json` is valid (it is not); `checkCommittedBaseline` is
      exercised on generated input only
    - The `none`-case / uniform-rows tension was resolved BOTH ways on purpose: acceptance facets
      spread the drawn metrics into running totals (`withDistinctMetrics`) so they can assert
      plain acceptance, and one facet keeps the raw generator output and asserts "accepted, or
      rejected *solely* as `uniform-metrics`" while independently recomputing the distinct counts
      - so the disjunction cannot absorb an unrelated failure
    - **NOTE: `serializeBaseline` re-derives `proxyCeiling`.** It rebuilds through
      `buildBaseline`, which writes `SCRIPTED_PROXY_CEILING` unconditionally, so a baseline
      accepted with a *non-canonical* retained statement would silently acquire the canonical one
      if re-serialized. Verbatim preservation is therefore only assertable through
      `assembleBaselineDocument` / `validateBaselineText`. Defensible (`checkCommittedBaseline`
      rejects non-canonical anyway) but it is an asymmetry between "kept verbatim on read" and
      "regenerated on write" that R8.10's reviewer should see
    - **NOTE: `baselineCaseArb`'s `missing-stamp` case always drops `capturedAt`** - its `.map`
      re-stamps every row, overriding whichever stamp `capturedScorecardRowArb` dropped. So
      `capturedScorecardRowArb`'s own `dropped` draw is unreachable through `baselineCaseArb`,
      which a reviewer may not expect. The "quantify over *which* stamp" obligation is composed
      locally instead. Not a defect, but worth knowing before reusing that generator

  - [x] 11.9 Render degradation and synthetic provenance on every displaying surface
    - Every surface displaying a value derived from a degraded pipeline response renders the
      declared degraded state; aggregates derived from an `is_synthetic` state are labelled
      synthetic-sourced; a component with no data endpoint renders its declared empty state and
      the surface states that no data path exists
    - _Requirements: 3.5, 4.3, 13.6_

  - [x] 11.10 Write property test for degradation rendering
    - **Property 31: Degradation is rendered wherever degraded data is shown**
    - **Validates: Requirements 3.5, 4.3, 13.6**
    - Landed at **`frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts`**, not
      under `spec/effectiveness/__tests__/`. Both directories are in `vitest.config.ts`'s
      `include` and both run under the global `jsdom` environment, so either would *execute* -
      but only `src/**` is inside `tsconfig.json`'s `include` and inside `biome check ./src`, so
      only `src/**` is covered by `pnpm typecheck` and `pnpm lint`. Precedent:
      `src/app/__tests__/primary-surfaces.property.test.ts`
    - 11 facets, driving the real `resolveDataPath` / `DataPathNotice` and reading state back
      **off the DOM** (`data-data-path`, `data-synthetic-sourced`) rather than trusting the
      resolver's return value, because R3.5/R4.3/R13.6 are obligations about what an operator
      sees. Every rendered copy key is asserted to resolve to something other than itself, so a
      registered panel with missing catalog copy goes RED instead of rendering a raw key. Both
      directions of R3.5 and R13.6 are stated, so neither passes on a resolver that returns one
      kind for everything. Registry: 12 ids, 2 absent, 10 present, all read at runtime
    - **NOTE: nothing forces a NEW panel to call `surfaceDataPath` at all.** The facets are total
      over the *registry*, not over the set of modules that display pipeline values -
      `data-paths.ts` says so in its own docstring and this test does not close it. All ten
      registered panels do currently render a notice, so no surface is reported RED. Closing the
      residual hole needs a source-level enumeration of surface modules intersected with
      `SURFACE_DATA_PATH_IDS`, which is a gate, not a property test. Worth its own task if R3.5
      should stay mechanical against panels added later
    - **NOTE: `[data-decision-row]` / `[data-decision-status]` still do not exist in
      `frontend/src/**`.** Task 11.9 did not add them; a repo-wide search finds them only in the
      skipped spec's own selectors, in `scorecard-emission.ts`'s declared blocker string, and in
      this file. So blocker #1 of `frontend/tests/e2e/reconnect-replay.resilience.spec.ts` is
      unchanged and that spec stays deliberately skipped

- [x] 12. Final integration and routing
  - [x] 12.1 Register every remaining new check and regenerate the generated documents
  - **DONE. Final registry: 52 PASS / 3 FAIL / 0 PARTIAL / 9 SKIP / 64 TOTAL.**
    `ledger_gen --check`, `gate_surface --check` and `required_checks_truth --check` all pass
  - Registered **C66-C72**, not C63 as the task's NOTE said - that NOTE predated 10.14 and 2.17.
    Verified before assigning: `C62` = topic-service, `C63`/`C64`/`C65` =
    gate-surface/workflow-shape/required-checks. `required_checks_truth` was the eighth name on
    the task's list and 2.17 had **already registered it as C65**, so it was not double-registered
  - `gate-mutations.yaml`: operators declared for C65, C66, C68, C69, C70, C71, C72. **C67 left
    deliberately UNDECLARED** - its subject (published anchor files) is not in this tree, so any
    operator would be decorative, and a decorative operator converts an undeclared gap into false
    assurance (I-7). Recorded in the file with that reasoning
  - `verify_claims.py` `GATE_STATUS` maps `unavailable` -> `SKIP` (non-passing, excluded from the
    PASS count), never `PASS`
  - `ratchets.json`: added `mutation-survival:audit-chain-walk` (direction down, bound 10) for
    12.2's new ceiling, and **verified the extractor resolves** via `ratchet_truth --check` -
    which is exactly why 12.2 declined to author it blind
  - `blocking-steps.yaml`: recorded `frontend.yml::e2e-visual` and
    `ci.yml::training-smoke`'s coverage step in `unlabelled_discarding_steps`, and declared
    12.4's new R3.2 step blocking (it is R3.2's single executed proof, and nothing would have
    failed if someone later appended `|| true`)
  - **CORRECTION to 12.2's finding: `frontend.yml::e2e-visual` does NOT fail
    `workflow_shape_truth`.** It is not in the unlabelled-advisory list. 12.2 inferred the failure
    from reading rather than running; the record is still useful documentation but the predicted
    RED was wrong
  - **CORRECTION: `unlabelled_discarding_steps` is a work record, NOT a suppression** - the file
    says so and the gate confirms it. Adding entries there documents a finding but does not change
    C64's verdict. That is the honest design and it is why C64 stays FAIL at
    `unlabelled-advisory=10`
  - **Fixed a real gate defect found by running the gate: the AD-12 bundle assertion was a FALSE
    POSITIVE.** `_scan_for_harness` did a bare `HARNESS_GLOBAL in text`, and
    `frontend/src/lib/interruption-precision.ts:101` carries a **comment stating the module does
    not touch `window.__atlasHarness`**. The gate read its own subject matter as a violation and
    reported `bundle-assertion=fail`. **This is the same defect class 12.5 just fixed in
    `ledger_gen` - second occurrence in this repo, so it is a class, not a one-off: a checker that
    matches a literal textually cannot tell prose *about* the thing from the thing.** New
    `strip_js_comments` removes block comments first (a `//` inside a JSDoc header would otherwise
    truncate its line), and `_scan_for_harness` now returns a third `documented_only` tuple so a
    comment-only mention is **reported in the detail, never silently dropped** (I-7). Stays
    fail-closed w.r.t. executable code: a mention inside a comment cannot execute. Bundle
    assertion now `[OK] ... ; 1 file(s) mention it in comments only`
  - **Closed the three-way `stryker-break` drift, which was a live R7.8 hole** (`ratchets.json`'s
    own note said "Remediation is task 12.1"). Sprint 13 Phase 4.1 bumped
    `frontend/stryker.conf.json` to `break: 50` and **three mirrors stayed at 26**:
    `verify_claims.py::STRYKER_BREAK_NOW`, `CLAUDE.md:46`, and `ratchets.json`'s
    `guard_constant.value` + `agrees_with_shipped: false`. Frozen at 26 the gate accepted any
    config >= 26, so **a silent regression from the shipped 50 down to 26 PASSED C16.** All three
    now read 50. This *strengthens* the gate rather than raising a ratchet - the enforced floor is
    the config and it is unchanged; `hard_floor` STRYKER_BREAK_MIN stays 20
  - **The README headline is a genuine self-referential fixpoint, now understood and documented.**
    C56 validates the headline by *executing the suite*, and its own status is inside the count it
    validates. The recursion guard (`SYNAPSE_DOC_TRUTH_NESTED`) makes the spawned suite skip only
    the headline claim, so the nested C56 reports SKIP - meaning **the value C56 enforces is the
    nested run's `51 PASS / 3 FAIL / 0 PARTIAL / 10 SKIP / 64 TOTAL`, while a top-level run
    reports `52 / 3 / 0 / 9`** (one more PASS, one fewer SKIP). README now states the enforced
    nested value and **explains the asymmetry in prose** rather than leaving it as an apparent
    discrepancy. `doc_truth --check` = 11/11 claims match
  - **I first misdiagnosed this as suite nondeterminism** (SKIP counts appeared to move 8 -> 9 ->
    10 across runs). A two-executions-in-one-process diagnostic proved the registry is
    **deterministic** - identical 51/4/9 twice. The apparent drift was my own edits landing
    between runs. Diagnostic script deleted
  - **NOTE: `ledger_gen` and `doc_truth` disagree about what README should say** - `ledger_gen`
    emits the *top-level* counts for transcription (R10.9) while C56 enforces the *nested* ones.
    Following `ledger_gen`'s emitted line makes C56 fail, and vice versa. Not resolved here
    (either the emitted line should carry the nested value, or C56 should count its own row as
    PASS when every other claim passes). **Worth its own task - it is a trap for the next person
    who follows the emitted line in good faith**
  - **NOTE: 4 pre-existing ruff findings in `verify_claims.py`** (unused `subprocess` import,
    `typing.Callable`, unused local `main` at 1020, E501 at 1315). None on a line this task
    touched, and CI's ruff scope is `packages/synapse_common/ agents/ orchestrator/`, so `scripts/`
    is ungated - which is itself the reason they survived. Left alone as out of scope
  - **Remaining 3 FAIL, all honest:** `C44` module_liveness (Windows-only
    `FileNotFoundError [WinError 3]` on a deep `frontend\node_modules\.pnpm\...\@bufbuild\protobuf`
    path - pre-existing, Linux CI unaffected); `C64` workflow_shape_truth
    (`unlabelled-advisory=10`, pre-existing R11.3 debt across 7 workflows, each needing one word
    in a step name - not renamed because `blocking-steps.yaml` declares step names by string);
    `C69` task_claim_truth (**expected** - `core-purpose-uplift` tasks 9/9.1 are `[x]` against an
    unchanged `__placeholder__`, which is R3.6's finding becoming mechanical)
    - Register `command_path_truth`, `anchor_truth`, `feed_provenance`, `task_claim_truth`,
      `ratchet_truth`, `replay_metrics`, `gate_fault_injection`, `required_checks_truth` in the
      Check_Registry with declared mutation operators in `gate-mutations.yaml`
    - Run `ledger_gen --write` and `gate_surface --write` so `docs/state/CURRENT.md` and
      `docs/state/GATE_SURFACE.md` are projections of a real execution
    - _Requirements: 1.1, 1.7, 10.1, 10.6, 11.1_
    - **NOTE (orchestrator, from task 10.14): `C62` is already taken** -
      `check_topic_service_truth` was registered under it. Start the remaining
      registrations at **C63**. Task 10.8 recommends `C63` for the hardened
      `published_checkpoint_truth.assess()` and `C64` for `task_claim_truth`.
    - **NOTE: `verify_claims.py`'s `{"ok","fail","skip"}` mapping cannot express
      `assess()`'s four outcomes** - it would `KeyError`. Map `unavailable` -> `SKIP`
      (non-passing, excluded from the PASS count), never to `PASS`.
    - **NOTE: registering these checks makes `README.md:24`'s headline counts stale**
      (`53 TOTAL` is already `54` after C62). Only `ledger_gen --write` in CI can
      recompute them; do not hand-edit the numbers (I-7).
    - **NOTE: `gate-mutations.yaml` has no operators for the new gates**, so they are
      reported UNDECLARED and excluded from PASS-eligibility until operators are declared.
    - **NOTE: `task_claim_truth` is expected to FAIL on landing** - `core-purpose-uplift`
      tasks 9 and 9.1 are `[x]` against an unchanged `__placeholder__`. That is R3.6's
      finding becoming mechanical, not a gate defect; sequence it deliberately.

  - [x] 12.1a Repair the `@deal.pre` confidence-floor conflict (unowned until now)
  - **DONE - both halves, because the two candidate repairs answer different invariants.**
    I-4 decides the ordering (an append-only row written before a crash cannot be retracted, so
    the precondition must be decided before the append); R5.4/ADR-054 D4 decides the literal
    (`0.7` was a second, stale copy of a *reloadable* boundary)
  - **The task's framing of option 2 was wrong and the agent was right to say so: this repo never
    commits to 0.7 as an absolute floor.** The table calls it `default_threshold`,
    `OrchestratorConfig.confidence_threshold` defaults to the same number, and ADR-054 D4 makes
    it reloadable. Treating a *default* as a floor would state a guarantee nothing declares
    (I-7). I-6 is satisfied by "the boundary in force is enforced unconditionally, at one choke
    point, ahead of any dispatch"
  - **Option 2 as literally worded is not implementable**: `execute_consensus` carries both
    `@deal.pre` and `@deal.post(result.audit_id is not None)`. The post can only hold after the
    append; the pre must be decided before it. One call site cannot satisfy both by moving the
    call. What moved is the precondition, evaluated earlier
  - `rules.py`: new `DEFAULT_CONFIDENCE_FLOOR` read from the committed table (never a literal),
    new public `satisfies_confidence_floor(...)` used as BOTH the `@deal.pre` validator and the
    pre-flight, `confidence_floor` keyword on `execute_consensus`. `@deal.post` and
    `make_canonical_row` untouched. The default is load-bearing:
    `orchestrator/tests/test_deal_contracts.py` calls `execute_consensus(decision)` positionally
    three times, so a required parameter would have broken it
  - `protocol.py::_ratify_and_dispatch`: reads `self._guardrails.confidence_threshold` **once**
    and uses that one snapshot for both the pre-flight and the contract - reading twice would
    leave the window open for a reload landing between them. A sub-floor decision is now a
    recorded withhold with a stated reason, never an exception. `violations` is rebound, not
    mutated in place (with a shared `(True, [])` double the list is the double's)
  - Reads the boundary from the **engine**, not `self._config`: `reload()` rebinds the provider's
    settings, `self._config` stays as captured at construction, so sourcing it there would
    reintroduce exactly the staleness R5.4 forbids
  - Three test doubles gained `"confidence_threshold": 0.0` (`test_binding_fastpath.py`,
    `test_cognition_phase.py`, `test_binding_arbitration_e2e.py`) - each already answers
    `(True, [])`, so the honest value is "imposes no floor of its own". Without it
    `float >= <MagicMock>` raises `TypeError`
  - **NOTE (ACTION REQUIRED, Property 22): widening its bounds to `0.0` turns
    `test_an_escalation_awaits_a_human_and_dispatches_nothing` RED**, and the task's "nothing
    else in this file changes" is wrong. It pins `confidence=0.0` and asserts a human was
    queued, on the claim that zero guarantees the sub-threshold branch "for every generated
    boundary" - true only for a boundary strictly above 0. At `threshold=0.0, blocked=False` the
    decision legitimately dispatches. That test needs its own strictly-positive strategy
    (`exclude_min=True`). The other four clauses are fine at `0.0`
  - **NOTE: Property 23's bounds must NOT be widened.** `test_guardrail_totality_property.py`
    never calls `execute_consensus`; its `[THRESHOLD, 1.0]` range keeps the confidence rule
    quiet so a violation is *attributable* to the rule under test. Widening turns at least two
    tests RED (`test_the_declared_clip_stays_a_clip`, and the `service_level_minimum` witness
    loses attribution because `validate_decision` returns early on the confidence rule). Only
    its stale docstring paragraph needs changing. **Property 24 is already `[0.0, 1.0]`** -
    nothing to widen, only stale "task 12.1's to repair" sentences
  - **NOTE (behavioural delta, needs a decision): `OrchestratorConfig.confidence_threshold` has
    no bounds** (`config.py:39`, plain `float = 0.7`). The old hardcoded `0.7` was an accidental
    backstop against a negative configured threshold - it crashed rather than dispatched. After
    this repair a negative threshold means every decision satisfies the floor, i.e. **fail-open**.
    Recommend `Field(0.7, ge=0.0)` - `ge` only, since `le=1.0` would remove a legitimate
    fail-closed knob (an operator setting 1.1 to escalate everything). It would also make
    `thresholds.py`'s documented I-7 reload claim actually true; today `-1.0` is accepted silently
  - **NOTE: Property 26's file carries the same stale literal** -
    `test_selection_and_twin_consequence_property.py:185` has `_EXECUTE_CONSENSUS_PRE_FLOOR = 0.7`
    and `_RATIFIABLE_FLOOR = max(...)`. Stays GREEN (both are 0.7, real engine) but the `max()`
    is now dead scaffolding
  - **NOTE: ADR-054 may want an amendment** - D1's committed order of operations is now five
    steps, not four, and its Context item 2 describes the contract as test-only.
    `_ratify_and_dispatch`'s docstring records the amendment inline; the ADR does not
  - **NOTE (tooling, affects every task that reasons from one grep): `grep_search` results are
    pruned by relevance and can omit real hits.** A repo-wide search for `execute_consensus` did
    not list `orchestrator/tests/test_deal_contracts.py:11`, which imports and calls it three
    times - the single most important caller for a signature change. Found only by auditing
    `guardrails=` construction sites
    - `orchestrator/guardrails/rules.py`'s `execute_consensus` `@deal.pre` hardcodes
      `0.7` while task 8.1 made the threshold reloadable. An operator reloading *below*
      `0.7` lets a decision in `[threshold, 0.7)` pass `validate_decision` and then trip
      `PreContractError` inside the choke point - fail-closed, but raised **after** the
      I-4 audit append, so the operator sees a crash rather than a governed withhold
    - Either make the precondition read the threshold provider, or move the contract
      before the audit append so the failure precedes the row
    - Properties 22, 23 and 24 currently generate *around* this region and asasert
      nothing about it; when the repair lands, their lower bound becomes `0.0`
    - _Requirements: 5.3, 5.4_

  - [x] 12.2 Route every heavy workload to its named workflow
    - **NOTE (orchestrator, from tasks 8.6/8.8): the slow routing is currently broken.**
      `ci.yml::uplift-verify`'s slow step selects `tests/uplift tests/verify` only, so it
      never collects `orchestrator/tests/consensus/` where Properties 22 and 26 live.
      Worse, `ci.yml::quality-gates` runs `pytest packages/tests agents orchestrator
      digital_twin api` with **no `-m` filter and no `HYPOTHESIS_PROFILE`**, so those two
      slow modules execute there at the `default` 500-example budget. The `slow` marker
      does **not** keep them out. Add the path to the slow step and exclude `-m slow`
      from `quality-gates`.
    - `ci.yml::uplift-verify`: cheap properties at the `ci` profile plus a
      `HYPOTHESIS_PROFILE=heavy -m slow` step for properties 15, 16, 22, 26, 29, 30
    - `integration.yml`: chain tamper against Postgres and a scheduled verifier against the live
      chain; nightly `real-stack` with SKIP now a divergence
    - `mutation.yml`: add `orchestrator/audit/chain_walk.py` to the targets under the <10% audit
      survival ceiling (Linux runners only, E-S13-05)
    - Confirm no workflow step in `blocking-steps.yaml` carries a discarding construct
    - **NOTE (from task 11.2): `integration.yml::real-stack-run` has the IDENTICAL
      zero-selection bug 11.1 found in `e2e-harness`** - it runs
      `pnpm test:e2e --project=chromium --reporter=json task-completion.jtbd`, and the
      `chromium` project carries `testIgnore: HARNESS_SPEC_PATTERN`, so it selects nothing.
      With the informational-SKIP rule now removed, the reporter emits five
      `missing-comparison` divergences and the nightly goes RED. **There is a real design
      question underneath: after 11.1 the JTBD suite REQUIRES `window.__atlasHarness`, which
      by AD-12 lives only in `dist-e2e`, while the real-stack run's whole point is MSW
      disabled against the real gateway. "Run the identical suite" and "no harness in the
      shipped bundle" are now in tension.** Decide it deliberately; do not paper over it
    - **NOTE (from tasks 11.1/11.2): `frontend/tsconfig.json`'s `include` covers neither
      `frontend/tests/**` nor most of `frontend/spec/**`**, so `pnpm typecheck` and the
      `tsc --noEmit` inside `pnpm build` never type-check `run-ratchet.ts`,
      `check-baseline.ts`, `real-stack-fidelity.ts`, `scorecard-emission.ts`,
      `scorecard-gate.ts`, or any e2e spec. Several agents' confidence in those files rests
      on the editor language service, which is not CI. Either widen `include` or add a
      `tsconfig.spec.json` plus a `typecheck:spec` script
    - **NOTE (CONFIRMED and wider, from tasks 11.3/11.4/11.6/11.8/11.10).** The exact
      `include` is
      `["src", "src/test/**/*", "vite.config.ts", "vitest.config.ts", "playwright.config.ts", "playwright.harness.config.ts", "spec/effectiveness/harness.ts", "spec/effectiveness/e2e-entry.ts"]`.
      So `spec/effectiveness/**` is outside it apart from those two files - including
      `arbitraries.ts` and **all eight property tests** in
      `spec/effectiveness/__tests__/` (`fixture-factory`, `harness-determinism`,
      `schema-less`, `unhandled-path`, plus 11.3/11.4/11.6/11.8's four new ones).
      `pnpm lint` is `biome check ./src`, so they are not linted either. They execute under
      vitest, esbuild-transpiled without a type check, so a type error surfaces only when the
      runner reaches that line. **This is the class of finding this audit exists to make
      mechanical: a directory CI runs but never checks.** Task 11.10 was placed under
      `src/surfaces/__tests__/` specifically to sit inside both gates. Adding
      `"spec/effectiveness/**/*.ts"` (and `spec/contract-fidelity/**`) to `include` is the
      two-line fix; note it may surface pre-existing errors in the four older tests
    - _Requirements: 1.8, 6.13, 8.9, 11.3, 11.5_

  - **12.2 DONE. Slow-routing hole closed at both ends.** `quality-gates` gained `-m "not slow"`;
    the `uplift-verify` slow step's paths gained `orchestrator/tests/consensus` **and**
    `digital_twin/tests`. Nine slow-marked files verified by reading the marker lines; each now
    has exactly one selecting job at `heavy` (100). Before: Properties 22 and 26 and
    `digital_twin/tests/test_simulation.py` (INV-TW-002, 1000 scenarios) ran in `quality-gates`
    at the `default` **500** budget and were selected by no slow step. `digital_twin/tests` is
    the easy one to miss - adding only `orchestrator/tests/consensus` would have orphaned it.
    `timeout-minutes` 45 -> 60. Step **names** deliberately unchanged: `blocking-steps.yaml`
    declares them, and a rename would make those declarations resolve to no step
  - **12.2: new `integration.yml::audit-chain-tamper` job** with a `services: postgres:16-alpine`
    and `SYNAPSE_AUDIT_CHAIN_IT_DSN` set. `tests/integration/test_audit_chain_tamper_postgres.py`
    says in its own docstring that no workflow sets that variable, so it **SKIPped everywhere** -
    R6.2/R6.10 had no executed proof against a database. Deliberately a dedicated job rather than
    a step in `integration-e2e` (whose closure has no sqlalchemy/asyncpg, so `importorskip` would
    turn the proof back into a skip). Runs on PR *and* the nightly cron
  - **12.2: `mutation.yml`** gained `orchestrator/audit/chain_walk.py` in both trigger filters,
    the intersection `case`, and its own step/`case` under the <10% audit ceiling. Label is
    `audit/chain-walk`, **not** `audit`, because `ratchets.json` extracts the audit ceiling with
    `--label "audit"` and reusing it would give the extractor two matching sites.
    `HYPOTHESIS_PROFILE=heavy` bounds each mutant's run at 100 (mutmut re-runs per mutant; 500
    would blow the 90-minute budget). `pip install pyyaml` added to both jobs - `chain_walk.py`
    imports `yaml` at module level and was satisfied only transitively via schemathesis
  - **12.2: chose `frontend/tsconfig.spec.json` + `typecheck:spec` + a standalone
    `frontend.yml::spec-typecheck` job over widening the base `include`.** The deciding fact is
    that `pnpm build` is `tsc --noEmit && vite build`, and in `frontend.yml` `build` gates `e2e`,
    `e2e-visual`, `e2e-harness`, `mobile-lighthouse`, `effectiveness-ratchet` and
    `fe-invariants` - so **one pre-existing error in one e2e spec would have skipped the entire
    console-effectiveness spine** and rendered all of it NOT EXECUTED. The new project is
    *wider* than the widening would have been (`spec/**/*.ts` + `tests/**/*.ts` in full,
    including `spec/contract-fidelity/**`, which was not even on the known list). Also touched
    `frontend/package.json` and `frontend.yml` (one script line, one job) - outside the declared
    file set, additive, flagged
  - **12.2: real-stack - NEEDS A HUMAN DECISION, left honestly RED.** The command was fixed
    (`pnpm test:e2e:harness task-completion.jtbd`; the old `--project=chromium` form selected
    **zero** specs because `chromium` carries `testIgnore: HARNESS_SPEC_PATTERN`) and the step
    relabelled ADVISORY - it carried an unlabelled `continue-on-error: true` that was in neither
    `blocking-steps.yaml` nor its `unlabelled_discarding_steps`, an unrecorded R11.3 violation.
    But the AD-12 conflict is real and not resolvable in this file set: the JTBD suite now
    *requires* `window.__atlasHarness`, which exists only in `dist-e2e`, and the console has **no
    configurable API base URL** (no `VITE_API_*` anywhere in `frontend/`), so serving `dist-e2e`
    on its own origin points every request at a port with no backend. Options recorded in the
    workflow. **Recommended permanent fix: inject the harness via Playwright `addInitScript`
    rather than bundling it** - that dissolves the tension entirely (the harness would be in no
    bundle at all, which is AD-12's intent stated more strongly). No `|| true` was added
  - **12.2: declined to add a "scheduled verifier against the live chain" to `integration.yml`,
    deliberately.** Nothing there writes `audit_consensus` rows through the production writer, so
    such a job could only ever report `unavailable` - a permanently-red gate with no green path.
    The verifier against a genuinely live chain already exists and is already blocking:
    `cd-gcp.yml::deploy-to-vm` "Audit-chain integrity (Sprint 9 verifier)", declared in
    `blocking-steps.yaml::steps`, on the weekly scheduled deploy
  - **12.2 NOTE (FOR 12.4 - the slow-routing fix is 95%, not 100%):** `ci.yml::training-smoke`'s
    "Measure per-package coverage under full ML stack" still runs `pytest packages/tests agents
    orchestrator digital_twin api ml_pipelines` with **no `-m` and no `HYPOTHESIS_PROFILE`**, so
    Properties 22 and 26 and the 1000-scenario twin still execute there at **500 examples** on
    `main`/`develop`/`sprint-*`. It is `continue-on-error: true` so it gates nothing, but it is a
    second full run of the real protocol. **One-line fix: add `-m "not slow"`.** 12.2 was told
    not to touch that job
  - **12.2 NOTE (will FAIL a gate): `frontend.yml::e2e-visual` -> "Generate + commit Linux
    baselines if none are committed yet"** carries `pnpm test:visual:update || true` with **no**
    ADVISORY/`informational` marker and is **not** recorded in
    `blocking-steps.yaml::unlabelled_discarding_steps`. `workflow_shape_truth` applies the R11.3
    name rule to every non-propagating step, so this fails with no record explaining why. The
    `|| true` is defensible (the compare step below is the real gate); the fix is one word in the
    step name, or a record
  - **12.2 NOTE: `ratchets.json` has no entry for the new `audit/chain-walk` ceiling.**
    `ratchet_truth` enforces the entries present, not the converse, so a shipped
    `--threshold 10` could later be raised to 40 without failing. Not authored because
    `agrees_with_shipped` is validated by *running* an extractor regex and an unverifiable regex
    would be a guess with a gate attached (I-7). Suggested shape:
    `"mutation-survival:audit-chain-walk"`, `direction: down`, `bound: 10`, extractor
    `regex:--threshold (?P<value>\d+) --label "audit/chain-walk"`
  - **12.2 NOTE (new finding class): `frontend/package.json` names four scripts whose files do
    not exist** - `domain:gen`, `openapi:gen`, `spec:check`, `audit:licenses` all point into
    `frontend/scripts/`, which contains only `check-supply-chain.mjs`. This is
    `command_path_truth`'s finding class (R6.14) applied to npm scripts, which that gate does not
    cover. **`spec:check` is the concerning one** - it reads like the FE-INV gate, and the real
    gate is `python frontend/spec/check_fe_invariants.py`. Worth its own task
  - **12.2 NOTE: `frontend/tsconfig.node.json` is referenced by nothing** - no `references`, no
    script, no workflow, and its `include` (`scripts/**/*.ts`) is now empty of `.ts` files.
    `module_liveness` does not cover TypeScript configs
  - **12.2 NOTE (measurement integrity): `get_diagnostics` returned empty for all four YAML
    workflow files too.** For TS/JSON that is already known to mean nothing; for **YAML** the
    agent could not distinguish "clean" from "no YAML language server answering" without
    inserting a deliberate syntax error into a required-check definition, which it declined to
    do. So the four workflow files are **authored and hand-reviewed, not validated by any tool**.
    The first GitHub Actions parse is the first real signal on YAML validity

  - [x] 12.3 Write the property-inventory consistency test
  - **DONE as `tests/verify/test_property_inventory_consistency.py`** - 11 deterministic tests,
    no `@given`, so it has no `max_examples` of its own to hardcode. Deterministic on purpose:
    the claim is a fact about one repo and one document, not a universally-quantified statement,
    and 500 examples re-reading the same 37 files is the budget burn I-0 forbids
  - **The count is exactly 37, verified by enumeration.** Design headings run 1..37, no
    duplicates, each claimed by exactly one file, none unclaimed, none extra. 32 Python + 5
    TypeScript. **No integer `37` appears in any assertion** - the count is derived from the
    design headings on one side and `DECLARED_INVENTORY` on the other, so the two must agree
    with each other rather than both with a typed number, and a failure names the property
    rather than an arithmetic difference
  - Tag convention enforced: a whole-line comment (`#` / `//`) whose whitespace-collapsed text
    *starts with* the expected tag. Wrapping is **normalised, not banned** - `tag_blocks` joins
    a tag line with the comment lines immediately following it, which covers all 16 wrapped tags
    and Property 29's 122-char single-line form under its `# ruff: noqa: E501`. **Nothing had to
    be rewritten.** Prefix rather than equality, so section rules and `# Clause 1:` headers do
    not break it. `(slow)` is stripped from the design title before comparison (six headings
    carry it, no tag repeats it)
  - `max_examples` clause scoped to the declared **Python** files, stated explicitly in the
    module docstring with the reason. Matcher is `max_examples[ \t]*=(?!=)` - an *assignment*,
    not a mention, because every file in the feature discusses it in prose to say it is never
    set. TypeScript gets the honest analogue rather than a silent exemption: `numRuns >= 100` on
    every declared value, since fast-check has no profile to inherit from
  - Also asserts every declared file actually uses its language's generator (`@given(` /
    `fc.assert(`) - a tag over no generator is a label, not a property test - and that no file
    outside the inventory carries a feature tag (the additive half of "exactly 37")
  - **NOTE: more pre-existing `max_examples` violations than the earlier count recorded** - add
    `tests/verify/test_verify_claims_status_partition_property.py` (200),
    `test_headline_count_pin_property.py`, `test_headline_pin_skip_property.py` (200 each),
    `tests/uplift/test_uplift_floor_monotonic_ratchet_property.py` (300, 200) and
    `test_uplift_floor_ratchet_property.py` (200 twice) to the known list. All out of scope, all
    documented in the new module's docstring so a future widener sees the bill
  - **NOTE: this test reads `.kiro/specs/purpose-achievement-audit/design.md`.** Precedented -
    `scripts/audit/task_claim_truth.py` already reads `.kiro/specs` via `checkpoint-truth.yaml`.
    If a CI job ever sparse-checkouts without `.kiro/`, the first clause fails by name rather
    than passing silently
  - **NOTE: no gate registration added.** If 12.1 wants this in the Check_Registry it needs a
    `scripts/audit/` wrapper around the same predicates
    - Assert exactly 37 property tests exist, each carrying its
      `# Feature: purpose-achievement-audit, Property {N}: ...` tag, each mapped to a design
      property, and none containing a hardcoded `max_examples`
    - _Requirements: 1.2_
    - **NOTE (orchestrator): pre-existing `max_examples` violations exist outside this
      feature** - `tests/uplift/test_headline_artifact_roundtrip_property.py` (200, twice),
      `tests/uplift/test_arm_aggregate_property.py` (200, 50), and
      `tests/verify/test_published_checkpoint_gate_property.py` (250). Scope the check to
      this feature's 37 files, or fix those first, or the check is born red for someone
      else's debt.
    - **NOTE: Property 26 is one file carrying 4 tagged `@given` tests** (a three-clause
      conjunction). Count one tagged test per property *file*, not per property number.
    - **NOTE (from task 10.13): the tag comment is NOT reliably one line.**
      `tests/verify/test_oracle_membership_property.py` wraps its Property 37 tag across two
      comment lines, and Property 29's tag is 122 characters against ruff's
      `line-length = 100`, so
      `tests/verify/test_nonsynthetic_ingestion_replay_property.py` carries a documented
      file-level `# ruff: noqa: E501`. Several Property 27 / Property 21 files wrap too.
      A single-line tag regex will under-count. Decide which convention 12.3 enforces and
      make the matcher agree with it
    - **NOTE (from section 11): five of the 37 property tests are TypeScript, not Python**,
      so the tag is `// Feature: ...` and there is no `max_examples` to look for. The five:
      `frontend/spec/effectiveness/__tests__/scorecard-completeness.property.test.ts` (32),
      `.../ratchet-sensitivity.property.test.ts` (33),
      `.../interruption-precision-responsiveness.property.test.ts` (34),
      `.../baseline-measurement.property.test.ts` (36), and - **outside
      `spec/effectiveness/`** - `frontend/src/surfaces/__tests__/degradation-rendering.property.test.ts`
      (31). A matcher that globs only `tests/**/*.py` finds none of them and the count
      lands at 32, not 37. The fast-check analogue of the `max_examples` rule is
      `numRuns`, which fast-check has no profile mechanism for: all five hardcode
      `{ numRuns: 100 }`, matching the four pre-existing effectiveness property tests. That
      is the established convention, so the `max_examples` clause should apply to the Python
      files only - state that scoping explicitly rather than letting the check quietly not
      cover a third of the inventory (I-7)

- [x] 12.5 Repair three assertions that pin pre-2.17 / pre-12.1 transient state
  - **DONE. `ledger_gen --check` now exits 1 (drift) with a real diff, was 2 (unavailable).
    Task 12.1 is UNBLOCKED.** Verify `--check` returns 1, not 2, before running `--write`
  - Repair 1: `test_the_committed_declaration_resolves_against_the_committed_workflows` now
    expects `.github/workflows/truth-gates.yml::truth-gates` in `report.resolved`, not in
    `report.pending`, and asserts the positive form (declared, `section == "required"`, right
    workflow) instead of dropping the clause. **8 passed, exit 0**, verified
  - Repair 1b (not in the original scope, found while reading): `PENDING_JOBS` still listed
    `"truth-gates"` as a job "never written into the tree" - now false. Renamed to
    `("future-spine-gate", "not-yet-landed", "unlanded-oracle-gate")`; `strategies.py:638`
    generates job ids as `job-{index}`, so none can collide. The property stays universally
    quantified. Same stale premise also corrected in `scripts/audit/required_checks_truth.py`'s
    docstring
  - Repair 2: **scoped the marker counter rather than escaping the prose.** New
    `_standalone_marker_offsets` + `generated_region_bounds` in `scripts/audit/ledger_gen.py`
    recognise a marker only when it owns its line. Escaping line 320 would have restored the
    verdict and left the trap armed for the next person who documents the format. Scoping also
    fixed a latent second bug: `partition()` split on the *first* textual occurrence, so a prose
    mention placed *before* the region would have made `--write` overwrite hand-authored prose.
    Byte-exactness preserved. `test_ledger_gen_property.py` was itself RED (it counted marker
    literals on the real document) - rewritten onto `generated_region_bounds`, plus a new
    universal clause that prose quoting the markers must project and drift, never `unavailable`
  - Repair 3: `mutation-fast-required-job` stays pending; `activates_after` no longer names a
    landed task but the real precondition (widening `mutation.yml`'s `pull_request` path filter
    AND promoting into `required:`). Activating today FAILs mechanically. Rephrasing the
    CLAUDE.md claim was considered and declined - recorded in the file
  - Repair 4: `blocking-steps.yaml` `pending:` is now empty; new `steps:` entry for
    `.github/workflows/truth-gates.yml::truth-gates` with `all_steps: true`. **The job has NINE
    steps, not the seven the pending entry's prose implied** - six gates plus `checkout`,
    `setup-python`, `Install dependencies`. Declaring the environment steps blocking is
    deliberate: several checks report SKIP on a missing optional import, so a swallowed
    `pip install` would turn PASSes into SKIPs and change the counts `doc_truth` pins.
    `workflow_shape_truth --check` confirms 7 declarations, 0 `blocking-unresolved`
  - **NOTE for 12.1: `gate_surface --check`'s diff grew by design** - the new `blocking-steps`
    entry changes `GATE_SURFACE.md`'s declared-blocking anchors. Run `gate_surface --write` in
    the same change. The `cd-gcp-blocking-verify-steps` pin is unaffected (its regex requires
    `verify_live.py`; the new rows do not match, so the count stays `two`)
  - **NOTE (latent, not fixed): `scripts/audit/gate_surface.py` carries the same marker trap**
    (`GENERATED_BEGIN in existing` then `split(..., 1)`, ~lines 1222-1226). `GATE_SURFACE.md`
    does not currently quote its markers in prose, so it is latent rather than live.
    `ledger_gen.generated_region_bounds` is importable if a follow-up wants to converge the two
    on one definition, which AD-2 already says the marker convention should have
  - **MERGE-BLOCKING (from task 2.17).**
    `tests/verify/test_required_checks_resolution_property.py::test_the_committed_declaration_resolves_against_the_committed_workflows`
    pins `truth-gates` as `pending:` and unresolved. Task 2.17 created the job (in its
    own workflow file, resolving CF-2) and promoted it to `required:`, so all three
    clauses are now false. `tests/verify` runs in `uplift-verify`, a declared required
    check, so this must land in the same PR. Fix: expect `truth-gates` in
    `report.resolved` under `.github/workflows/truth-gates.yml`, drop the
    `not in declared` clause
  - **BLOCKS `ledger_gen --write` (from task 2.17).** `docs/state/CURRENT.md` contains
    **two** `<!-- generated:begin -->` marker pairs - the real region, and line ~320's
    prose sentence quoting the markers. `ledger_gen` counts marker literals textually,
    sees 2 and 2, and reports "no usable generated region", so it exits 2 (unavailable)
    rather than 1 (drift). **Task 12.1 cannot simply run `--write` until the prose is
    escaped or the counter scoped**
  - `infrastructure/quality/doc-number-pins.yaml`'s `mutation-fast-required-job` pin
    records `activates_after: task 2.17`, but the premise moved: `mutation-fast`'s
    `pull_request` trigger is still path-filtered so it stays ineligible, and activating
    the pin now would FAIL. Keep it pending, or rephrase CLAUDE.md's claim
  - `infrastructure/quality/blocking-steps.yaml`'s `pending:` entry still records
    `workflow: .github/workflows/ci.yml, job: truth-gates` - stale in two ways. Promote
    its seven steps into `steps:` so a re-swallow FAILs by declaration, not only by the
    name rule
  - _Requirements: 14.1, 14.2, 10.7, 11.7_

- [x] 12.4 Add the CI steps the new tests need in order to run at all
  - **DONE.** New blocking step `R3.2 serving-resolution proof (recorded entry resolves,
    BLOCKING)` in `ci.yml::training-smoke`, placed after the C42 gate (so a real artifact exists)
    and before the coverage step (so that step's `continue-on-error` + `|| true` cannot discard
    this exit status). No `continue-on-error`, no `|| true`, no existing step renamed
  - The agent chased every prerequisite rather than assuming the task's command was sufficient.
    **The delta over C42 is real and would have reintroduced the skip if the closure were
    thinner:** the test imports `agents.demand_prophet.inference.serve` and calls the same
    `serve._build_model_registry` the app lifespan calls, so it needs `fastapi`,
    `pydantic-settings`, `mlflow`, `prometheus-client` - which C42 does not, because C42 builds
    `ModelRegistry` itself. All four arrive via the job's `for req in agents/*/requirements.txt`
    loop, so the step as written is sufficient. No DSN, no extra artifact path, no new dependency
  - Verified the assertion most likely to be a silent trap: `save_checkpoint` returns
    `sha256(bytes)[:16]`, `train.py` writes `version = "smoke_" + that_sha`, and
    `ModelRegistry._load_from_checkpoint` recomputes `[:16]` over the same bytes - so
    `resolved_sha in loaded.version` holds. **Had `train.py` used a sha7, the step would have
    looked like proof and failed.** The I-7 branch also resolves correctly: the registry is still
    `__placeholder__`, so the test asserts `ArtifactClass.SMOKE`. A green run here proves
    *resolution*, not publication (R3.8)
  - **Pull-request reach: DECIDED, post-merge-only accepted, recorded in the workflow comment as
    a decision rather than an oversight.** Against: structurally the same gap R14 records for
    branch protection, and the one 2.17 closed for `mutation.yml` with a `push: main` trigger.
    For, and decisive: `mutation.yml`'s fix worked because a mutation run needs no artifact -
    here the proof needs a trained checkpoint, and smoke-training on every PR is exactly the
    category-4 workload I-0 and this whole feature keep off the PR path. What would close it
    without paying that cost - a committed fixture checkpoint, or a lighter smoke artifact -
    does not exist today. **No `continue-on-error` was added to make the question disappear**
  - Second edit (handed over from 12.2): `-m "not slow"` added to the "Measure per-package
    coverage under full ML stack" step, closing the residual half of the slow-routing fix. All
    three slow modules now have exactly one selecting job. Verified by grep that those three are
    the only `mark.slow` sites under the six selected trees, so nothing else changed selection
  - **The coverage consequence is recorded in the step comment under a
    `MEASUREMENT CHANGED - read before running scripts/coverage_ratchet.py --apply` heading**, and
    that mattered: excluding those modules lowers the `orchestrator` and `digital_twin` numbers,
    and `digital_twin`'s floor is still `0.0`/CI-MUST-MEASURE so its **first** bound floor comes
    from the new smaller measurement. Correct trade - a floor bound from a 500-example run of the
    real protocol and the real twin is a floor nobody should reproduce, and floors never
    decrease, so binding an unreproducible number pins it permanently. Both candidate ratchet
    inputs (`coverage.xml` from `quality-gates`, `coverage-full.xml` from here) now exclude the
    slow modules, so the two measurements moved together rather than diverging
  - **NOTE (for 12.1): `docs/state/GATE_SURFACE.md` will drift** - it enumerates
    `training-smoke`'s steps by name (~lines 270-278), so the new step adds a row.
    `gate_surface --write` covers this together with 12.5's `blocking-steps` entry and 2.17's
    pre-existing staleness
  - **NOTE (for 12.1): the coverage step is a live R11.3 case, pre-existing.**
    `continue-on-error: true` + `|| true`, name carries neither ADVISORY nor `informational`, and
    it is in neither `blocking-steps.yaml::steps` nor `unlabelled_discarding_steps`.
    `GATE_SURFACE.md` already renders it `conditional - advisory (unlabelled: ...)`. Same class as
    12.2's `frontend.yml::e2e-visual` finding. Not renamed (renames break the name-string
    declarations); fix is one word in the name **or** a record
  - **NOTE (for 12.1): the new R3.2 step is not declared blocking.** It propagates today so no
    gate objects, but nothing in `blocking-steps.yaml` would fail if someone later appended
    `|| true` - only the R11.3 name rule would. Given it is R3.2's single executed proof, it is a
    strong candidate for a `steps:` entry
  - **NOTE: R3.2's first execution is genuinely unproven** - the test has never run anywhere,
    which is the premise of the task. Confidence rests on reading the resolution chain end to
    end, not on execution. The two likeliest first-run failures, in order: the
    `assert Path(serve.SERVING_CHECKPOINT_DIR) == checkpoint_dir` hard equality, and the
    `fastapi`/`starlette` pairing in this job's closure, which unlike `quality-gates` carries no
    explicit `starlette>=0.37.2,<0.38.0` pin

- [x] 12.6 Close the four follow-ups tasks 12.1a and 12.2 named but were told not to make
  - **Property 22 widened to `[0.0, 1.0]`** in `test_confidence_gate_universality_property.py`;
    `CONTRACT_FLOOR` and the now-unused `HARD_GUARDRAILS` import deleted; two stale docstring
    paragraphs replaced with what actually holds. New `positive_thresholds()` (`exclude_min=True`)
    used by **only** `test_an_escalation_awaits_a_human_and_dispatches_nothing`, whose premise
    ("zero is below every generated boundary") was true only for a boundary strictly above zero
  - **The widened band is now the regression test the defect never had**, verified three ways by
    reading: pre-repair, `threshold=0.3, confidence=0.5` appends the audit row then raises
    `PreContractError` out of `_ratify_and_dispatch` (the clause errors before any assertion, and
    Hypothesis shrinks toward `0.0/0.0` which is still in the defective region); a *reintroduced*
    literal floor fails as a wrong verdict rather than a crash (`dispatched is not expected`); and
    the repaired semantics are positively asserted in the band, not merely un-crashed
  - Honest addition the agent volunteered: at `threshold=0.0` the "withholding side" of
    `gate_cases()` is empty (`nextafter(0.0, 0.0) == 0.0`, and the model pins `confidence >= 0`),
    so that draw collapses to a passing case. The side is a search heuristic and `gate_passes`
    recomputes the verdict from the drawn values, so the example still asserts something - stated
    rather than left for a reader to trip over
  - **Property 23's range deliberately NOT widened**, and both RED claims verified against
    `validate_decision`'s call order (privacy -> price cap -> rider shift -> **confidence floor,
    early return** -> service level). `test_the_declared_clip_stays_a_clip` would fail because a
    sub-0.7 confidence produces a non-clip-worded violation; the `service_level_minimum` witness
    would lose attribution because `_check_service_level` never runs. **Two more would also
    break** (`test_dropping_a_declaration_never_weakens_enforcement`,
    `test_a_clip_class_violation_cannot_rescue_a_blocking_violation`), which strengthens the
    conclusion. Only the stale docstring paragraph changed, and it now records *why the range
    must stay* so the next agent does not widen it
  - Property 24: range already `[0.0, 1.0]`; both stale "task 12.1's to repair" sites rewritten.
    Property 26: deleted `_EXECUTE_CONSENSUS_PRE_FLOOR = 0.7` and the dead
    `_RATIFIABLE_FLOOR = max(...)`; `_confidences` now reads from the committed table alone.
    Behaviour unchanged (both values were 0.7). Not executed - it is `slow` and drives the real
    protocol
  - **`orchestrator/config.py`: `confidence_threshold: float = Field(0.7, ge=0.0)`.** Closes a
    fail-open window the repair opened: the old hardcoded `0.7` was an accidental backstop, so a
    negative configured threshold used to crash rather than dispatch; now it would make every
    decision satisfy the floor. `ge` only - **no `le=1.0`**, because a boundary above 1.0 is a
    legitimate fail-closed knob (`ConsensusDecision` pins `confidence <= 1`, so `1.1` escalates
    everything). Also makes `thresholds.py`'s documented I-7 reload claim true for `-1.0`, which
    was previously accepted silently. Swept every construction site: **nothing sets a negative
    threshold today**, so no test newly raises
  - **NOTE (residual, outside the agent's file set): `StaticConfidenceThresholdProvider` is still
    unbounded.** `GuardrailEngine(confidence_threshold=-1.0)` is accepted and is still fail-open.
    Every in-repo caller passes a non-negative literal or a config-backed provider, so nothing is
    broken today - but the guarantee is "the *configured* boundary cannot be negative", not "the
    boundary cannot be negative". Closing it needs a validator in `thresholds.py` /
    `resolve_threshold_provider`
  - **NOTE: `satisfies_confidence_floor` is deliberately not in Property 22's
    `PRIVILEGED_OPERATIONS`.** After 12.1a the pre-flight is a gating operation, but it is a pure
    predicate, so a second call site is harmless and adding it would create a clause that can go
    RED for a benign reason. Worth a deliberate decision by whoever owns the structural clause
  - **NOTE: `ADR-054` still describes a four-step order and a test-only contract.** 12.1a recorded
    the amendment in `_ratify_and_dispatch`'s docstring only; the ADR itself is still outstanding
  - **NOTE: `test_selection_and_twin_consequence_property.py` still carries a "Note for task 12.2"
    paragraph** claiming `uplift-verify` does not collect `orchestrator/tests/consensus` and that
    `quality-gates` runs it at `default`. Both were fixed by 12.2. Left alone deliberately - it is
    a claim about `ci.yml`, which was mid-edit by another agent at the time. Should be updated now
    that `ci.yml` has settled
  - **R3.2 has no executed proof until this lands.**
    `tests/integration/test_published_entry_serving_resolution.py` skips everywhere
    except `ci.yml::training-smoke` (it needs the artifact only that job produces), so
    today it is a silent `s` in every green run. Add, in `training-smoke`, after the
    C42 runtime-substance gate and BEFORE the `continue-on-error` coverage step, with no
    `continue-on-error` and no `|| true`:
    `SYNAPSE_SMOKE_RUN=1 PYTHONPATH=. pytest tests/integration/test_published_entry_serving_resolution.py -q --tb=short`
  - Note `training-smoke` is `if: main || develop || sprint-*`, so R3.2 never runs on a
    pull request. Decide deliberately whether that is acceptable
  - _Requirements: 3.2_

- [ ] 13. Final checkpoint
  - ## CONSOLIDATED STATUS - all 96 implementation tasks landed; 4 checkpoints deliberately open
  -
  - **What is mechanically verified, by execution, on this machine:**
    - `registry_gate` = **52 PASS / 3 FAIL / 0 PARTIAL / 9 SKIP / 64 TOTAL**
    - `doc_truth --check` = **11/11 doc claims match source** (was 2 drifted)
    - `ledger_gen --check` = OK, `docs/state/CURRENT.md` is a projection of a real execution
    - `gate_surface --check` = pass, 513 surface rows match the parsed workflow tree
    - `required_checks_truth --check` = pass, 24 declared jobs resolve, 0 unresolved pending
    - `workflow_shape_truth` AD-12 bundle assertion = pass (was a false positive)
    - `tests/verify/test_required_checks_resolution_property.py` = **8 passed**
    - `tests/verify/test_property_inventory_consistency.py` = **12 passed** - which
      mechanically confirms **all 37 property tests exist, carry their correct tag, drive a
      real generator, contain no hardcoded `max_examples` (32 Python), and declare
      `numRuns >= 100` (5 TypeScript)**. This is the single strongest piece of evidence in
      the feature: the design-to-test correspondence R1.2 asks for is now a passing check
      rather than a sentence in a document
  -
  - **The 3 remaining FAILs, all honest and all named:** `C44` (Windows-only
    `FileNotFoundError` on a deep pnpm path; Linux CI unaffected), `C64`
    (`unlabelled-advisory=10`, pre-existing R11.3 debt across 7 workflows, each one word in a
    step name - not renamed because `blocking-steps.yaml` declares step names by string),
    `C69` (**expected**: `core-purpose-uplift` tasks 9/9.1 are `[x]` against an unchanged
    `__placeholder__` - R3.6's finding becoming mechanical)
  -
  - **What was NEVER verified, and must not be read as verified (I-7):**
    - **The entire frontend.** `getDiagnostics` returns no TypeScript signal in this
      workspace - four agents proved it independently by inserting a deliberate type error
      and getting an empty result, including for a file *inside* `tsconfig.json`'s `include`.
      So every "diagnostics-clean" claim against a frontend task in this file means *the tool
      was silent*, not *the code is correct*. The five new TS property tests (Properties 31,
      32, 33, 34, 36) are **authored and hand-reviewed, never type-checked and never
      executed**
    - **YAML validity.** Same problem: empty diagnostics on all workflow files, and nobody
      would corrupt a required-check definition to prove the tool answers. The first GitHub
      Actions parse is the first real signal
    - Every `slow` property, the Playwright suites, the mutation sweeps, the uplift harness,
      the real-stack run - all category 1/3/4 under I-0 and correctly never run here
  -
  - **Expected RED on first CI run, deliberately not softened:** `frontend.yml::spec-typecheck`
    (30+ files meeting `noUncheckedIndexedAccess`/`exactOptionalPropertyTypes` for the first
    time - pre-existing debt becoming visible, fix the types and never narrow the project);
    `integration.yml::real-stack-run` (the AD-12 conflict below); `integration.yml::audit-chain-tamper`
    (never executed anywhere before); `mutation.yml` audit-chain-walk (survival never measured);
    `ci.yml::quality-gates` per-package coverage floor (possible - excluding slow tests removed
    their contribution; **re-measure and ratchet, never lower a floor**); the R3.2 step
    (never executed anywhere)
  -
  - ## THREE DECISIONS THAT NEED THE USER - none of them safe for an agent to take
  - 1. **The AD-12 / real-stack conflict.** After task 11.1 the JTBD suite *requires*
       `window.__atlasHarness`, which by AD-12 exists only in `dist-e2e`, while
       `real-stack-run`'s purpose is MSW disabled against the real gateway. There is no
       app-level escape - the console has no configurable API base URL. The zero-selection
       bug is fixed and the step honestly labelled, but the job stays RED with a named
       reason. **Recommended: inject the harness via Playwright `addInitScript` instead of
       bundling it** - that dissolves the tension entirely (the harness would then be in no
       bundle at all, which is AD-12's intent stated more strongly). Alternative: serve
       `dist-e2e` behind the real nginx gateway and amend AD-12's wording. Both change a
       recorded architecture decision
  - 2. **R8.4's `steps` tolerance is relative, so its own mutation is invisible.**
       `stepsPct` means a +1-step regression is undetectable whenever a baseline row carries
       `steps >= 20`, and the committed baseline records exactly 20 for all five jobs - so
       **a +1-step mutant passes the ratchet today.** Property 33 deliberately does not
       assert this (it would assert against the comparator's documented semantics rather
       than a defect). Closing it is a policy choice: give `steps` an absolute floor
       (regress on `> baseline + 1` OR `> baseline * 1.05`, whichever is smaller), or have
       the mutated variant add steps beyond 5%
  - 3. **`ledger_gen` and `doc_truth` disagree about the README headline.** `ledger_gen`
       emits the *top-level* counts for transcription (R10.9); C56 enforces the *nested*
       ones, because its recursion guard makes the spawned suite self-exclude. Following the
       emitted line in good faith makes C56 fail. README now carries the enforced nested
       value with the asymmetry explained in prose, but the two gates should be reconciled -
       either the emitted line carries the nested value, or C56 counts its own row as PASS
       when every other claim passes
  -
  - **One class-level finding worth acting on:** a checker that matches a literal textually
    cannot distinguish prose *about* the thing from the thing. It bit twice in this feature -
    `ledger_gen`'s marker counter (fixed in 12.5 by scoping to standalone lines) and the
    AD-12 bundle assertion (fixed in 12.1 by stripping comments). **`gate_surface.py` carries
    the same latent trap** (`GENERATED_BEGIN in existing` then `split(..., 1)`);
    `GATE_SURFACE.md` does not currently quote its markers in prose, so it is latent rather
    than live. `ledger_gen.generated_region_bounds` is importable if a follow-up wants to
    converge them on one definition, which AD-2 already says the marker convention should have
  -
  - **NOTE (orchestrator, MEASUREMENT-INTEGRITY - read before trusting any "diagnostics-clean"
    claim in this file).** `getDiagnostics` returns **no TypeScript signal at all** in this
    workspace. Four agents independently inserted a deliberate type error
    (e.g. `const probe: number = "not a number";`) into a frontend file, re-ran
    `getDiagnostics`, and got an empty result; the probes were removed. This reproduces for a
    file **inside** `tsconfig.json`'s `include` (`src/surfaces/__tests__/`), so it is not the
    `include` gap in 12.2 - no TS language server is answering. Consequence under I-7: every
    "diagnostics-clean" result recorded against a **frontend** task in this file means *the
    tool was silent*, not *the code is correct*. Those files are **authored and hand-reviewed
    against the production signatures, never type-checked and never executed.** The first
    `pnpm typecheck` / `pnpm lint` / `pnpm test:coverage` run in `frontend.yml::quality` is
    the first real signal. Python tasks are unaffected (ruff/mypy diagnostics did report).
    Do not let this checkpoint read as verified for the frontend
  - Ensure all tests pass, ask the user if questions arise. Then confirm the design's
    non-circular definition of done against an observed CI run on `main`: a mutated check on a
    scratch branch turns the run red; both generated documents match their generators; the chain
    verifier detects a seeded deletion; a powered uplift run writes `incomplete: false` and C60's
    verdict comes from `is_proven_uplift`; the agency verdict comes from a `perceive()` delta; the
    scorecard carries five measured rows and a one-extra-step variant fails the ratchet.

## Notes

- Tasks marked `*` are optional test tasks and can be skipped for a faster path; core
  implementation tasks are never optional.
- **I-0 local verification protocol** for every task: `getDiagnostics` on changed files, then
  at most one single-file run -
  `HYPOTHESIS_PROFILE=dev pytest <one file> -m "not slow" -x -q --tb=line -p no:randomly`.
  Never a bare `pytest`, never `-n auto`, never a background verification process, never
  `docker build` / `docker compose up`, never `uplift.cli --full`, never `mutmut`. Sweep for
  surviving processes before finishing a task.
- **Never hardcode `max_examples`.** Profiles come from the root `conftest.py`. Slow-marked
  properties (15, 16, 22, 26, 29, 30 and the browser-driven 32-34) run at
  `HYPOTHESIS_PROFILE=heavy` in CI only.
- **I-4**: `make_canonical_row` is never modified and audit rows are never UPDATEd or DELETEd.
  New facts go in new append-only tables (task 7.8).
- **I-7**: every new gate has a distinct unavailable outcome. A SKIP is never a PASS and an
  all-SKIP run is a non-passing run.
- **I-1**: no new paid dependency. Gates are stdlib plus already-vendored PyYAML, Pydantic,
  structlog, Hypothesis, fast-check.
- Conventions for every touched file: `mypy --strict` type hints, Pydantic v2 models,
  `structlog` in library code (CLI entry points keep the existing `print` reporting style of
  `verify_claims.py`), `json.dumps(obj, sort_keys=True, separators=(',',':'))`,
  `encoding='utf-8'` on every `read_text` (E-S13-07), ASCII-only console output.
- Spec-driven flow per commit: touch the machine-read configuration or spec first, let the
  generated/property test fail, implement, go green, commit.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.3", "2.5", "2.10", "2.12", "2.14", "4.1", "4.3", "4.5"] },
    { "id": 2, "tasks": ["2.2", "2.4", "2.6", "2.7", "2.8", "2.11", "2.13", "2.15", "4.2", "4.4", "4.6", "5.1", "5.3", "5.5", "5.7"] },
    { "id": 3, "tasks": ["2.9", "2.16", "5.2", "5.4", "5.6", "5.8", "7.1", "7.4", "7.6", "7.8"] },
    { "id": 4, "tasks": ["2.17", "7.2", "7.3", "7.5", "7.7", "7.9", "8.1", "8.3"] },
    { "id": 5, "tasks": ["7.10", "8.2", "8.4", "8.5", "8.9", "8.11"] },
    { "id": 6, "tasks": ["8.6", "8.7", "8.10", "8.12", "10.1", "10.8", "10.11", "10.14"] },
    { "id": 7, "tasks": ["8.8", "10.2", "10.3", "10.9", "10.10", "10.12", "10.13", "10.15", "11.1"] },
    { "id": 8, "tasks": ["10.4", "10.5", "10.6", "10.7", "11.2", "11.5", "11.7", "11.9"] },
    { "id": 9, "tasks": ["11.3", "11.4", "11.6", "11.8", "11.10", "12.1"] },
    { "id": 10, "tasks": ["12.2", "12.3"] }
  ]
}
```
