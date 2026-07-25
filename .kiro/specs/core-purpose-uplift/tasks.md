# Implementation Plan: core-purpose-uplift

## Overview

This is a wiring, measurement, and truth-pinning feature — not a new-subsystem feature. The existing modules (`harness.py`, `contract.py`, `fidelity.py`, `interfaces.py`, `scenarios.py`, `uplift_floor.py`, `ConsensusProtocol`, `TierRouter`, `InProcessA2ATransport`, the agent/twin A2A handlers, the audit hash-chain, and the honesty gates) are reused as-is. The coding work is:

1. Add the single new assembly seam `build_consensus_arm()` and wire it into the CLI so the harness measures the real four-tier consensus over an in-process, network-free, $0 transport.
2. Lock in the reused measurement, classification, attribution, power, fidelity, and floor/gate behaviors with property-based tests (Hypothesis, ≥ 100 iterations each, one test per design property).
3. Ratchet the `UPLIFT_FLOOR` only against a co-located powered proof artifact and verify the C60 three-way exit.
4. Populate and verify the flagship `demand_prophet` checkpoint registry entry (C43).
5. Add the new C56 `doc_truth` headline-count-pinning claim and replace the stale README literal, enforcing `verify_claims` status totality.
6. Preserve the 623-test regression floor and the core invariants.

Language: **Python** (matching the existing repo and its `tests/uplift/` Hypothesis suites). Each property test is tagged `Feature: core-purpose-uplift, Property {number}: {property_text}` and lives in its own test module to keep property tasks independently runnable.

## Tasks

- [x] 1. Assemble the real in-process consensus arm
  - [x] 1.1 Implement `build_consensus_arm` in `uplift/consensus_arm.py`
    - Add the assembly function that builds (or accepts injected) the eight agent `handle_request` handlers keyed by `AGENT_ENDPOINTS`, plus the twin `handle_request` handler
    - Wrap handlers in `InProcessA2ATransport.from_agents(...)` and construct a real `ConsensusProtocol` reusing the real `TierRouter`, guardrails, audit logger, HITL escalation, context builder, meta-RL, and semantic cache unchanged
    - Return `ConsensusArm(protocol=..., transport=..., name=DEFAULT_CONSENSUS_ARM)`; raise `ConsensusArmUnavailable` when the network cannot be assembled (no stub fabrication)
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 9.8_

  - [x] 1.2 Write property test for network-free consensus decisions
    - **Property 1: Consensus arm decides only through the in-process transport (network-free)**
    - Use stub agent/twin handlers injected through `build_consensus_arm`; assert recorded transport calls > 0 and no socket is opened
    - **Validates: Requirements 1.2**

  - [x] 1.3 Write property test for reachable-observation translation
    - **Property 2: A reachable observation yields a translated PolicyAction, not unavailability**
    - **Validates: Requirements 1.3**

  - [x] 1.4 Write example test for assembly wiring shape
    - Assert the assembled transport exposes exactly the 8 agent URLs + `TWIN_ENDPOINT` and the return value satisfies the `DecisionPolicy` protocol (`name` + `decide`)
    - _Requirements: 1.1_

- [x] 2. Wire the real arm into the one-command CLI with honest failure
  - [x] 2.1 Modify `uplift/cli.py::_build_consensus_arm` to call `build_consensus_arm()`
    - Replace the `ConsensusArm(transport=None)` body with a call to `build_consensus_arm()`
    - Preserve the existing `try/except` that falls back to `_UnavailableConsensusArm(reason)` so a plain environment degrades to honest failed runs; keep the consensus arm first under `DEFAULT_CONSENSUS_ARM`; no signature change
    - _Requirements: 1.5, 7.1, 7.5_

  - [x] 2.2 Write property test for honest failed runs
    - **Property 3: Unavailable consensus is an honest failed run, never a fabricated decision**
    - **Validates: Requirements 1.5, 7.5, 9.6**

  - [x] 2.3 Write property test for reproduction disclosures and labels
    - **Property 12: Reproduction output carries required disclosures and labels**
    - **Validates: Requirements 3.4, 7.2, 7.6**

  - [x] 2.4 Write property test for contract-failure priority
    - **Property 22: Missing/malformed contract fails first, printing and writing no headline**
    - **Validates: Requirements 7.3, 7.4**

  - [x] 2.5 Write example test for the `--smoke` one-command path
    - Assert `python -m uplift.cli --smoke` records ≥ 1 completed consensus run for ≥ 1 adversarial scenario and writes the artifact at the C60-read path (`artifacts/uplift/result.json`)
    - _Requirements: 1.4, 7.1_

- [x] 3. Checkpoint - Ensure all tests pass
  - Deferred to CI per I-0 (`.kiro/steering/local-compute-budget.md`): verified by the
    `uplift-verify` job in `.github/workflows/ci.yml`, not on the dev laptop.

- [x] 4. Lock in result assembly, classification, and guard integrity
  - [x] 4.1 Write property test for the incomplete flag
    - **Property 4: `incomplete` flag exactly tracks run completeness**
    - **Validates: Requirements 2.1**

  - [x] 4.2 Write property test for non-crediting of incomplete/partial pairs
    - **Property 5: Incomplete or partial pairs are never credited to SYNAPSE**
    - **Validates: Requirements 2.4, 2.5**

  - [x] 4.3 Write property test for headline direction orientation
    - **Property 6: Headline uplift is direction-oriented so positive always means improvement**
    - **Validates: Requirements 2.2**

  - [x] 4.4 Write property test for headline artifact round-trip
    - **Property 7: Headline uplift round-trips through the result artifact**
    - **Validates: Requirements 2.3**

  - [x] 4.5 Write property test for baseline pooling
    - **Property 8: Unnamed baseline pools all non-consensus arms**
    - **Validates: Requirements 2.6**

  - [x] 4.6 Write property test for verbatim contract classification
    - **Property 9: Assembly classifies pairs by the contract rule verbatim**
    - **Validates: Requirements 2.7**

  - [x] 4.7 Write property test for the all-wins guard
    - **Property 21: The all-wins guard fires exactly when every pair is a SYNAPSE win**
    - **Validates: Requirements 6.7**

- [x] 5. Lock in harness attribution, power, reproducibility, and arm symmetry
  - [x] 5.1 Write property test for arm-independent replicate seeds
    - **Property 17: Replicate seeds are arm-independent and deterministic (attribution)**
    - **Validates: Requirements 6.1, 6.2**

  - [x] 5.2 Write property test for the under-power guard
    - **Property 10: The under-power guard is total over n**
    - **Validates: Requirements 3.2**

  - [x] 5.3 Write property test for reproducibility within noise tolerance
    - **Property 11: Identical seeds reproduce within the committed noise tolerance**
    - **Validates: Requirements 3.3**

  - [x] 5.4 Write property test for arm symmetry and no leakage
    - **Property 18: Arms run under identical cadence, costs, and twin construction (no asymmetry, no leakage)**
    - **Validates: Requirements 6.3, 6.8**

- [x] 6. Lock in contract significance/MDE and fidelity reporting
  - [x] 6.1 Write property test for the SYNAPSE_WINS gate
    - **Property 19: SYNAPSE_WINS requires significance and MDE**
    - **Validates: Requirements 6.4**

  - [x] 6.2 Write property test for headline/fidelity co-location
    - **Property 13: Every headline number is co-located with its fidelity context**
    - **Validates: Requirements 3.5**

  - [x] 6.3 Write property test for the fidelity confidence mapping
    - **Property 20: Fidelity confidence maps KL divergence deterministically**
    - **Validates: Requirements 6.5, 6.6**

- [x] 7. Checkpoint - Ensure all tests pass
  - Deferred to CI per I-0 (`.kiro/steering/local-compute-budget.md`): verified by the
    `uplift-verify` job in `.github/workflows/ci.yml`, not on the dev laptop.

- [x] 8. Ratchet the uplift floor and verify the C60 value gate
  - [x] 8.1 Confirm/implement the monotonic ratchet in `uplift/uplift_floor.py`
    - Keep `UPLIFT_FLOOR` a single declared numeric constant starting at `0.0`; ensure `ratchet(previous, proposed)` raises `FloorRatchetError` when `proposed < previous`
    - Encode the data-gated obligation as a helper/guard that only accepts a raise to `0 < v ≤ measured` against a co-located, non-incomplete powered proof artifact (the actual value bump is committed by the operator only after a powered proof run measures a positive within-bound headline)
    - _Requirements: 4.1, 4.2, 4.3, 4.7_

  - [x] 8.2 Write property test for the ratchet monotonicity
    - **Property 14: The uplift floor is a monotonic ratchet**
    - **Validates: Requirements 4.2, 4.3**

  - [x] 8.3 Write property test for the C60 three-way exit
    - **Property 15: The C60 gate exit is a total three-way mapping** (pass / regression / distinct unavailable, unavailable never maps to pass)
    - **Validates: Requirements 4.4, 4.5, 4.6**

- [x] 9. Populate and verify the flagship checkpoint registry
  - [x] 9.1 Replace the `__placeholder__` entry in `infrastructure/ml/published_checkpoints.json`
    - Write the real `demand_prophet_hgt_tft` registry entry (repo, sha, coverage, `final_crps`, `trained_at`, `rows`) produced by the existing `docs/runbooks/train-and-publish-checkpoint.md` $0 free-GPU runbook, and confirm the serving path loads it so the flagship serves non-degraded output
    - Note: the actual free-GPU training + HF Hub publication is an operator runbook step; this task lands the resulting registry entry and validates schema + serving-path loading in code
    - _Requirements: 5.1, 5.2, 5.7, 5.8_

  - [x] 9.2 Write property test for the C43 published-checkpoint gate decision
    - **Property 16: The C43 published-checkpoint gate decision is correct over sidecar/registry inputs**
    - **Validates: Requirements 5.3, 5.4, 5.5, 5.6**

- [x] 10. Pin documentation and headline claims to mechanical reality
  - [x] 10.1 Add the C56 headline-count-pinning claim in `scripts/audit/doc_truth.py`
    - Add `_claim_readme_headline_counts` to `_CLAIMS` that executes the `verify_claims` suite at evaluation time, parses its summary into `{PASS, FAIL, PARTIAL, SKIP, TOTAL}`, extracts the README headline counts, and FAILs naming each drifted category with (claimed, actual); SKIP naming the cause when a source is missing/unreadable or the suite cannot run/parse; never hardcode counts
    - _Requirements: 8.2, 8.3, 8.5, 8.6_

  - [x] 10.2 Replace the stale README headline literal and enforce `verify_claims` totality
    - Replace `16 PASS / 3 FAIL / 0 SKIP` with the live counts derived from the current `verify_claims` suite (currently 53 registered checks); in `scripts/audit/verify_claims.py` ensure every registered check is assigned exactly one status in `{PASS, FAIL, PARTIAL, SKIP}` and the four counts sum to the reported TOTAL with no check omitted
    - _Requirements: 8.1, 8.7_

  - [x] 10.3 Write property test for the headline-count pin
    - **Property 23: The headline-count pin passes iff every count matches, else fails naming each drift**
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [x] 10.4 Write property test for unavailable source/suite skip semantics
    - **Property 24: Unavailable pinned source or suite yields skip, never a pass**
    - **Validates: Requirements 8.5, 8.6**

  - [x] 10.5 Write property test for the verify_claims status partition
    - **Property 25: The verify_claims status partition is exhaustive and disjoint**
    - **Validates: Requirements 8.7**

  - [x] 10.6 Write property test for the proven/success predicate
    - **Property 26: Uplift is "proven" only for a within-bound, powered, floor-clearing positive measurement**
    - **Validates: Requirements 8.4, 10.6, 10.7**

- [x] 11. Preserve existing tests and invariants
  - [x] 11.1 Write regression/smoke assertions for the preserved baseline
    - Assert the full existing suite reports ≥ 623 passing tests; assert `build_consensus_arm` imports the real `ConsensusProtocol`/`AGENT_ENDPOINTS` (no forked decision logic); assert reproduction/verification paths read only synthetic seeds and run in-process with sockets/paid clients monkeypatched to fail; assert `UPLIFT_FLOOR` is a single importable numeric constant; keep the I-2/I-3/I-5/I-7/I-14 invariant suites passing
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 10.1, 10.3_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Deferred to CI per I-0 (`.kiro/steering/local-compute-budget.md`). The
    `uplift-verify` job runs `tests/uplift` + `tests/verify` in two steps
    (`-m "not slow"` at the 500-example `ci` budget, `-m "slow"` at the 100-example
    `heavy` budget) and carries the 623-test regression floor. Not run locally.

## Notes

- Tasks marked with `*` are optional test tasks and can be skipped for a faster MVP, but they are the primary way this feature's correctness is locked in — the design defines success non-circularly (Requirement 10.5), so the property suite is strongly recommended.
- This feature reuses existing decision logic unchanged; the only load-bearing new code is `build_consensus_arm()` (1.1) and its CLI wiring (2.1), plus the C56 claim (10.1) and floor/registry/README edits.
- Each correctness property (Properties 1–26) is implemented by a single Hypothesis property test with ≥ 100 iterations, in its own module, tagged `Feature: core-purpose-uplift, Property {number}: {property_text}`.
- Consensus-arm property tests (1, 2, 3, 18) use injected stub agent/twin handlers so `run_consensus` executes in-process with no real models and no sockets (I-1, $0).
- No property or reproduction test performs a real 1000-scenario twin run; the powered proof and the `UPLIFT_FLOOR` raise are separate operator-run steps outside these coding tasks.
- Checkpoints ensure incremental validation at reasonable breaks.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "8.1", "9.1", "10.1"] },
    { "id": 1, "tasks": ["2.1", "10.2"] },
    { "id": 2, "tasks": ["1.2", "1.3", "1.4", "2.2", "2.3", "2.4", "2.5", "4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "5.1", "5.2", "5.3", "5.4", "6.1", "6.2", "6.3", "8.2", "8.3", "9.2", "10.3", "10.4", "10.5", "10.6"] },
    { "id": 3, "tasks": ["11.1"] }
  ]
}
```
