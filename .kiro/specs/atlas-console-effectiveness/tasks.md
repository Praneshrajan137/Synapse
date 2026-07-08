# Implementation Plan: Atlas Console Effectiveness

## Overview

This plan converts the Atlas Console Effectiveness design into incremental, test-driven coding steps for the existing `frontend/` (React 18 + Vite + TypeScript, package `synapse-console`). It **builds on** the completed `atlas-console-elevation` spec and does **not** re-cover display fidelity — it closes the dimensions that spec left at zero: behaviour against data, operator effectiveness, resilience under real conditions, calibrated trust, and the remaining quality-system gates.

The work is **additive and invariant-governed**: it lands inside the existing `transport → domain → lib → state → hooks → design-system → surfaces` layering, never re-architects the app, and every new guarantee is registered as an `FE-INV-*` invariant (next available id `FE-INV-054`) with a test in `frontend/spec/fe_invariants.yaml`.

Implementation language is **TypeScript**. Property-based tests use **fast-check + Vitest** (already in the stack), each carrying the tag `Feature: atlas-console-effectiveness, Property {number}: {property_text}` and running `numRuns: 100` minimum. E2E and harness-driven behaviour tests use **Playwright + MSW-in-browser**. Tasks are ordered so pure logic and the harness foundation land before the surfaces and gates that consume them, and each step wires into the previous one so no code is orphaned. Test sub-tasks marked `*` are optional and can be skipped for a faster MVP.

The five workstreams are sequenced keystone-first: **FE-WS-1** (integration + effectiveness harness) → **FE-WS-2** (resilience) → **FE-WS-3** (trust loop + attention model) → **FE-WS-4** (quality-system completion) → **FE-WS-5** (debt retirement), with governance conformance (Req 20) folded into the relevant tasks and a final conformance task.

**Honest ceiling (encoded, not hidden):** the harness is a `Scripted_Proxy` that proves an operator path exists and is efficient. It does NOT prove human comprehension, which requires real-user (RITE) testing with 3–5 operators. RITE real-user testing is out of scope; only the scripted-proxy harness work is planned here, and every effectiveness artifact must render that ceiling statement.

## Tasks

- [x] 1. FE-WS-1 — Contract-accurate fixture foundation (keystone)
  - [x] 1.1 Promote the schema registry to a shared module
    - Extract `DOMAIN_SCHEMA_REGISTRY` (currently in `frontend/spec/contract-fidelity/introspect.ts`, keyed by the exact `schemaId` strings passed to `http-client.parseWithSchema` and the firehose per-channel `SCHEMAS` map) into a shared `frontend/spec/effectiveness/schema-registry.ts` imported by BOTH the contract-fidelity drift suite and the harness, so a single registry binds fixtures and runtime validation
    - Preserve existing drift-suite behaviour; this is a move-and-re-export, no schema changes
    - _Requirements: 2.1, 2.2, 20.6_

  - [x] 1.2 Implement the schema-bound fixture factory
    - Create `frontend/spec/effectiveness/fixture-factory.ts` that derives every `MSW_Fixture`'s shape from a `Domain_Schema` in the shared registry and validates the constructed fixture against that same schema at build/setup time; fail with the offending fixture + schema named when validation fails
    - Mark a capability with no `Domain_Schema` as `schema-less` and surface that classification in the harness report rather than treating it as schema-bound
    - Provide a per-channel factory that can emit a schema-violating payload on demand (for Requirement 8's schema-violation path)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 20.6_

  - [x] 1.3 Write property test for fixture–schema soundness
    - **Feature: atlas-console-effectiveness, Property 1: Every generated fixture validates against its bound Domain_Schema, and any schema change that invalidates a fixture fails at build/setup naming the fixture and schema**
    - **Validates: Requirements 2.1, 2.2, 2.3**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/spec/effectiveness/__tests__/fixture-factory.property.test.ts`

  - [x] 1.4 Write property test for schema-less classification
    - **Feature: atlas-console-effectiveness, Property 2: A capability with no Domain_Schema is classified schema-less and surfaced as such, never treated as schema-bound**
    - **Validates: Requirements 2.4**
    - fast-check + Vitest, `numRuns: 100`

- [x] 2. FE-WS-1 — MSW browser worker, handlers, and stream driver
  - [x] 2.1 Add the MSW browser worker and full schema-bound handler set
    - Create `frontend/spec/effectiveness/browser-worker.ts` using `msw/browser` `setupWorker` and generate `public/mockServiceWorker.js`; **reuse and extend** the existing `src/test/msw-handlers.ts` `handlers` array rather than duplicating it
    - Register handlers built from the fixture factory covering every Surface (mission-control, decision-theater, override-cockpit, audit-vault, operations, steering, twin-lab, council-theater, agent-council, live-markets, ingress, auth, demo-theater) with at least one seeded scenario reaching the populated Universal_State
    - Intercept every Backend_Contract HTTP path so no request reaches a live endpoint; make zero calls to any live/third-party endpoint while active; fail the test naming the unhandled path when a request has no registered fixture
    - _Requirements: 1.1, 1.4, 1.5, 1.6_

  - [x] 2.2 Implement the scripted WS/SSE stream driver
    - Create `frontend/spec/effectiveness/stream-driver.ts` feeding the same `WebSocket`/`EventSource` surfaces `ws-multiplex`/`firehose`/the demo SSE consume, delivering a deterministic ordered message sequence keyed by seed for every real-time channel
    - For a fixed seed, produce byte-identical fixture responses and identical stream message order on every run; seed at least one channel that can emit a schema-violating payload on demand
    - _Requirements: 1.2, 1.3, 2.5_

  - [x] 2.3 Write property test for harness determinism
    - **Feature: atlas-console-effectiveness, Property 3: For a fixed seed the harness yields byte-identical fixture responses and an identical stream message order across runs**
    - **Validates: Requirements 1.3**
    - fast-check + Vitest, `numRuns: 100`

  - [x] 2.4 Write property test for unhandled-path failure
    - **Feature: atlas-console-effectiveness, Property 4: A Backend_Contract request with no registered fixture fails the test and names the unhandled path, never returning an empty/default response**
    - **Validates: Requirements 1.6**
    - fast-check + Vitest, `numRuns: 100`

- [x] 3. FE-WS-1 — Jobs-To-Be-Done task-completion suite
  - [x] 3.1 Enumerate Jobs-To-Be-Done and author scenario descriptors
    - Create `frontend/spec/effectiveness/scenarios/*.ts` descriptors enumerating at minimum: resolve an escalation correctly, identify which agent degraded and why, reconstruct a decision's rationale, adjust steering safely, and catch a disruption before it cascades — each bound to a seeded harness scenario
    - _Requirements: 3.1_

  - [x] 3.2 Implement the Task_Completion_Tests
    - Create `frontend/tests/e2e/*.jtbd.spec.ts` driving each Job_To_Be_Done against its seeded scenario through the harness, recording steps taken, time-to-complete, and error/dead-end rate
    - Assert the operator reaches the correct terminal outcome for the seed and fail if it is wrong or unreachable; record and fail on any dead-end (missing/unjustifiably-disabled affordance or non-recoverable state)
    - For "resolve an escalation correctly", verify the override commits the audit row before the decision is marked acted (audit-row-first) when driven through the harness
    - State in every test's report that the measurement is a `Scripted_Proxy` that demonstrates path existence and efficiency and does NOT establish human comprehension
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 20.5_

- [x] 4. FE-WS-1 — Effectiveness scorecard and ratchet gate
  - [x] 4.1 Emit and commit the Effectiveness_Scorecard
    - Have the Task_Completion_Tests write a single versioned `scorecard.json` recording, per Job_To_Be_Done, measured steps, time-to-complete, and error/dead-end rate, plus the seed and harness version, and a reserved field for Interruption_Precision; commit a baseline so measurements are comparable
    - _Requirements: 4.1, 4.2, 4.6_

  - [x] 4.2 Implement the Effectiveness_Ratchet pure comparator
    - Create `frontend/src/lib/effectiveness-ratchet.ts` as a pure, I/O-free comparator that loads the committed baseline and a fresh scorecard and returns pass/fail plus named regressions; define the regression tolerance explicitly; fail (non-zero) naming the regressed job and metric when steps/latency/error-rate regress beyond tolerance; permit advancing the baseline monotonically on improvement
    - Add the CI invocation script that reads the artifacts and calls the comparator
    - _Requirements: 4.3, 4.4, 4.5_

  - [x] 4.3 Write property test for the ratchet comparator
    - **Feature: atlas-console-effectiveness, Property 5: The ratchet fails iff some job's steps/latency/error-rate regresses beyond tolerance relative to baseline, and an improvement permits a monotonic baseline advance**
    - **Validates: Requirements 4.3, 4.4, 4.5**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/src/lib/__tests__/effectiveness-ratchet.property.test.ts`

- [x] 5. FE-WS-1 — CI wiring: deterministic PR gate and nightly Real_Stack_Run
  - [x] 5.1 Extend `.github/workflows/frontend.yml` with the deterministic harness gate
    - Add an `e2e-harness` job (Playwright + MSW browser worker running the Task_Completion_Tests and Resilience_Scenarios) and an `effectiveness-ratchet` job that compares the fresh scorecard against the committed baseline; both derive pass/fail from seeded, byte-identical harness measurements so the PR gate stays deterministic and non-flaky
    - _Requirements: 1.3, 4.3, 4.4, 20.3_

  - [x] 5.2 Wire the nightly Real_Stack_Run in a separate scheduled workflow
    - In a scheduled workflow separate from the PR gate (`.github/workflows/integration.yml`, which already runs on cron), add a job that boots the real SYNAPSE docker stack, runs the identical Task_Completion_Test suite with the MSW worker disabled, records the backend build SHA, and reports any test that passes under the harness but fails against the real stack — naming the job, the observed contract difference, and any MSW_Fixture requiring reconciliation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 20.3_

- [x] 6. Checkpoint — FE-WS-1 harness green
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. FE-WS-2 — Firehose stress resilience
  - [x] 7.1 Lift the bounded ring-buffer model and add the firehose stress scenario
    - Lift the existing per-channel bounded buffer (`state/firehose.store.ts` `newBounded`/`appendBounded`, FE-INV-017) into a shared `frontend/src/lib/ring-buffer.ts` for reuse and property testing without changing runtime caps
    - Add a firehose `Resilience_Scenario` streaming at realistic and adversarial rates; assert INP stays within the Web_Vitals_Budget (≤ 200ms), no reflow/reorder jank of already-rendered content on the target profile, and a final state consistent with the deduplicated applied message set (no lost, no double-counted items)
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

  - [x] 7.2 Write property test for the ring-buffer bound
    - **Feature: atlas-console-effectiveness, Property 6: The ring buffer never retains more than its cap regardless of how many messages arrive**
    - **Validates: Requirements 6.2**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/src/lib/__tests__/ring-buffer.property.test.ts`

  - [x] 7.3 Write property test for at-most-once application under firehose
    - **Feature: atlas-console-effectiveness, Property 7: A message whose sequence was already applied is dropped, so no message applies more than once**
    - **Validates: Requirements 6.3**
    - fast-check + Vitest, `numRuns: 100`

- [x] 8. FE-WS-2 — Reconnect and replay reconciliation
  - [x] 8.1 Implement the acted-never-reverted reconcile reducer
    - Add a pure reconcile reducer in `frontend/src/lib/reconcile.ts` that, on reconnect, requests replay from the last applied sequence (`since_seq`), reconciles the replay burst without duplicate rows, keeps an already-acted decision in its acted state (never reverting to pending), and reconnects with bounded Full-Jitter backoff (reusing `fullJitterDelay`/`isFreshSeq` from `transport/ws-multiplex.ts`)
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

  - [x] 8.2 Write property test for reconciliation as a dedup union
    - **Feature: atlas-console-effectiveness, Property 8: After reconnect+replay the reconciled row set equals the deduplicated union of pre-drop and replayed state with no duplicate, lost, or reverted rows**
    - **Validates: Requirements 7.2, 7.4**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/src/lib/__tests__/reconcile.property.test.ts`

  - [x] 8.3 Write property test for bounded Full-Jitter backoff
    - **Feature: atlas-console-effectiveness, Property 9: Reconnect delay is Full-Jitter bounded by the exponential cap for every attempt**
    - **Validates: Requirements 7.3**
    - fast-check + Vitest, `numRuns: 100`

  - [x] 8.4 Add the reconnect/replay Resilience_Scenario verified at rendered output
    - Add a `Resilience_Scenario` scripting a drop, a `since_seq` replay burst containing at least one already-acted decision, and a resumed live stream; add `frontend/tests/e2e/*.resilience.spec.ts` asserting at the rendered output (not only the reducer) that acted decisions stay acted and no duplicate rows appear
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

- [x] 9. FE-WS-2 — Fault-transition state correctness
  - [x] 9.1 Extend fault/connectivity transition resolution
    - Route each harness fault through the existing universal-state resolver so a 503 renders error/degraded (never populated-healthy), a schema-violating payload renders error via the schema-violation path (never the unvalidated payload), a 401 storm triggers a single-flight token refresh and, on failure/second 401, clears the session and routes to login without a full reload, a repeated WebSocket flap renders the not-live/reconnecting state through a non-color channel and recovers, and an offline↔online transition renders offline (never stale-as-live) and restores populated on return; a chained sequence renders the correct distinct state at every step without latching
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 9.2 Write property test for fault-transition correctness
    - **Feature: atlas-console-effectiveness, Property 11: Fault/connectivity transition resolution is total and distinct — every transition maps to the correct distinct Universal_State and never latches on a prior state or renders false-healthy**
    - **Validates: Requirements 8.1, 8.6**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/src/lib/__tests__/fault-transition.property.test.ts`

  - [x] 9.3 Add fault-transition Resilience_Scenarios and E2E assertions
    - Add harness scenarios and `*.resilience.spec.ts` coverage for 503, schema-violation, 401 storm, WS flap, and offline↔online chains, asserting each distinct state renders and recovers correctly
    - _Requirements: 8.2, 8.3, 8.4, 8.5_

- [x] 10. FE-WS-2 — Scale virtualization retrofit
  - [x] 10.1 Retrofit AuditVault and DecisionTheater with row virtualization
    - Retrofit `surfaces/audit-vault/AuditVault.tsx` and `surfaces/decision-theater/DecisionTheater.tsx` to use `@tanstack/react-virtual` (+ `@tanstack/react-table` where useful — both already installed); remove the `limit: 200` / `limit: 100` query caps so the full seeded row set is reachable by scrolling, keeping mounted row nodes bounded and far below the total row count and each scrolled-in row aligned to its seeded fixture
    - _Requirements: 9.1, 9.3, 9.4_

  - [x] 10.2 Write property test for the virtualization window
    - **Feature: atlas-console-effectiveness, Property 10: The virtualization window yields a bounded mounted-row count independent of total rows, and each windowed row maps to the datum at its index**
    - **Validates: Requirements 9.1, 9.4**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/src/lib/__tests__/virtual-window.property.test.ts`

  - [x] 10.3 Add the 10k-row Resilience_Scenario and E2E scale assertions
    - Seed a `Resilience_Scenario` of at least 10,000 rows for both the Audit Vault and Decision Theater; add E2E asserting mounted row nodes stay bounded (far below 10k), the full set is reachable by scrolling, and scroll/interaction INP stays within the Web_Vitals_Budget (≤ 200ms)
    - _Requirements: 9.1, 9.2, 9.5_

- [x] 11. FE-WS-2 — Spatial visualization correctness in a real browser
  - [x] 11.1 Add WebGL smoke and chromatic-encoding checks for spatial surfaces
    - Seed deterministic geospatial and network-graph fixtures; add Playwright checks in a real browser asserting each Spatial_Visualization initializes its WebGL context without throwing (smoke), encodes agent/tier/confidence with the same Chromatic_Token values as the rest of the Console (verified against resolved token values, not jsdom), renders the error Universal_State with a retry affordance on WebGL init failure (never a blank canvas), and exposes a keyboard/screen-reader-reachable non-spatial equivalent plus the loading state while loading
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 12. Checkpoint — FE-WS-2 resilience green
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. FE-WS-3 — Longitudinal operator trust track record
  - [x] 13.1 Implement the Trust_Track_Record pure aggregation
    - Create `frontend/src/lib/trust-track-record.ts` aggregating from `decision_outcomes` / `audit_escalations` signal (`DecisionDetailResponse.outcome`, `CalibrationResponse` bins, `AuditRow.operator_token_ref`): render outcomes as the three distinct states confirmed / diverged / unknown (never folding `unknown` into `confirmed`), report low-confidence-approved counts as distinct confirmed vs diverged values, disclose sample size / window / "as of", flag provisional below the defined minimum scored outcomes, return "awaiting scored outcomes" when none exist, and exclude Synthetic decisions by default
    - _Requirements: 11.2, 11.3, 11.4, 11.5, 11.6_

  - [x] 13.2 Render the Trust_Track_Record surface
    - Render the authenticated operator's Trust_Track_Record over the defined window with the tri-state outcomes, distinct counts, disclosures/provisional flag, "awaiting scored outcomes" honest empty state, and a labelled control to include Synthetic decisions
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [x] 13.3 Write property test for the tri-state outcome partition
    - **Feature: atlas-console-effectiveness, Property 12: Trust outcomes partition into exactly confirmed/diverged/unknown with unknown never folded into confirmed**
    - **Validates: Requirements 11.2, 11.3**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/src/lib/__tests__/trust-track-record.property.test.ts`

  - [x] 13.4 Write property test for provisional/awaiting honesty
    - **Feature: atlas-console-effectiveness, Property 13: The track record is flagged provisional iff scored outcomes are below the minimum and renders "awaiting scored outcomes" when none exist, always disclosing sample size/window/as-of**
    - **Validates: Requirements 11.4, 11.5**
    - fast-check + Vitest, `numRuns: 100`

  - [x] 13.5 Write property test for synthetic exclusion
    - **Feature: atlas-console-effectiveness, Property 14: The default aggregate excludes every Synthetic decision and the labelled toggle adds exactly those records**
    - **Validates: Requirements 11.6**
    - fast-check + Vitest, `numRuns: 100`

- [x] 14. FE-WS-3 — Expected-value attention model
  - [x] 14.1 Implement Expected_Review_Value with honest degradation
    - Create `frontend/src/lib/expected-review-value.ts` computing `f(confidence, reversibility, blast_radius)` and ranking a decision's need for review by that value; use the Backend_Contract Reversibility/Blast_Radius fields when present; when absent (a Cross_Boundary_Dependency — confirmed absent from `DecisionEnvelopeSchema`/`AuditRowSchema` today) fall back to confidence-only ranking, expose an explicit "reversibility/blast-radius unavailable" indication, and record the missing fields as a backend gap in the drift report — never fabricating a value
    - _Requirements: 12.1, 12.4, 12.5_

  - [x] 14.2 Supersede confidence-only focus and escalate on stakes
    - Supersede `lib/oversight.ts` `defaultFocusAction` so default keyboard focus among override actions derives from Expected_Review_Value rather than confidence alone; escalate an irreversible or high-blast-radius decision for review even when confidence is at/above the 0.80 autonomy gate; render an explicit non-color indication of why review was demanded (irreversible and/or high blast-radius)
    - _Requirements: 12.2, 12.3, 12.6_

  - [x] 14.3 Write property test for stakes-based escalation
    - **Feature: atlas-console-effectiveness, Property 15: An irreversible or high-blast-radius decision is escalated for review even when confidence is at or above the 0.80 gate**
    - **Validates: Requirements 12.1, 12.2**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/src/lib/__tests__/expected-review-value.property.test.ts`

  - [x] 14.4 Write property test for honest degradation
    - **Feature: atlas-console-effectiveness, Property 16: When reversibility/blast-radius are absent, Expected_Review_Value falls back to confidence-only ranking and flags the fields unavailable, never fabricating a value**
    - **Validates: Requirements 12.5**
    - fast-check + Vitest, `numRuns: 100`

  - [x] 14.5 Write property test for ERV-derived focus
    - **Feature: atlas-console-effectiveness, Property 17: Default override focus is derived from Expected_Review_Value, superseding the confidence-only focus model**
    - **Validates: Requirements 12.3**
    - fast-check + Vitest, `numRuns: 100`

- [x] 15. FE-WS-3 — Interruption Precision measurement and gate (North-Star)
  - [x] 15.1 Implement and record Interruption_Precision
    - Create `frontend/src/lib/interruption-precision.ts` computing warranted interruptions ÷ total interruptions over the defined window (warranted = review changed the outcome or confirmed a genuinely uncertain/irreversible/high-blast decision); compute it over the seeded scenarios and record it in the Effectiveness_Scorecard, presented as the primary (North-Star) metric; state that it is measured over a Scripted_Proxy and its real-world value requires validation with real operators
    - _Requirements: 13.1, 13.2, 13.4, 13.5, 20.5_

  - [x] 15.2 Gate Interruption_Precision in the ratchet
    - Extend the Effectiveness_Ratchet so that if Interruption_Precision regresses below its committed baseline beyond tolerance the check fails and names Interruption_Precision as the regressed metric
    - _Requirements: 13.3_

  - [x] 15.3 Write property test for the Interruption_Precision ratio
    - **Feature: atlas-console-effectiveness, Property 18: Interruption_Precision equals warranted ÷ total interruptions over the window and is bounded within [0, 1]**
    - **Validates: Requirements 13.1**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/src/lib/__tests__/interruption-precision.property.test.ts`

- [x] 16. Checkpoint — FE-WS-3 trust loop green
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. FE-WS-4 — Visual-regression gate
  - [x] 17.1 Add the deterministic Visual_Regression_Gate
    - Capture deterministic screenshots of a defined set of key Surfaces/Storybook stories under fixed viewport, theme, and seed with fixed fonts, disabled animation, and masked volatile regions; add a PR job to `.github/workflows/frontend.yml` that fails naming the changed Surface/story when a screenshot diff exceeds the defined threshold; cover at least one Surface per Theme_Mode (light, dark, hc); support updating the committed baseline for an approved change; use only $0-cost / OSS tooling (Playwright screenshot diffing — no paid SaaS)
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 20.2_

- [x] 18. FE-WS-4 — Assistive-technology and mobile reality
  - [x] 18.1 Add the Assistive_Tech_Flow with live-region announcements
    - Script a screen-reader (NVDA and/or VoiceOver) walkthrough of resolving a live escalation in the Override Cockpit, asserting the operator can perceive the escalation, its violations, and the action outcome non-visually, and that the override outcome is announced through an appropriate live region; state the ceiling that scripted flows demonstrate operability but do not replace real assistive-technology users
    - _Requirements: 15.1, 15.2, 15.6, 20.5_

  - [x] 18.2 Add the Mobile_Reality_Profile flows and mobile Lighthouse gate
    - Verify key Surfaces under the Mobile_Reality_Profile (360px viewport, touch input, throttled 3G) with all primary Jobs-To-Be-Done reachable/operable and the Web_Vitals_Budget met (LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1); add the OSS Lighthouse CI dependency (`@lhci/cli`/`lighthouse` — currently a stub script only) and a mobile-profile Lighthouse job to `.github/workflows/frontend.yml` on the defined key routes that fails when a route falls below its mobile budget
    - _Requirements: 15.3, 15.4, 15.5, 20.2_

- [x] 19. FE-WS-4 — Close the contract-drift red gate
  - [x] 19.1 Classify schema-less capabilities in the contract-fidelity suite
    - Extend `frontend/spec/contract-fidelity/*` so each schema-less Backend_Contract capability (no response body or open/unconstrained shape) is classified either "no-body/open-shape ⇒ covered" (treated as covered, not failing the drift gate for a missing response schema) or "tracked-partial" (recorded with a named rationale, not an untracked failure); the drift gate reaches green for the entitled surface with every schema-less capability resolved; a new unclassified, non-entitled-out-of-scope schema-less capability fails and is named
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [x] 19.2 Write property test for schema-less drift closure
    - **Feature: atlas-console-effectiveness, Property 19: A schema-less capability resolved to either classification never leaves an untracked failure, and an unclassified non-entitled schema-less capability fails the gate and is named**
    - **Validates: Requirements 16.2, 16.3, 16.5**
    - fast-check + Vitest, `numRuns: 100`; place in `frontend/spec/contract-fidelity/__tests__/schema-less.property.test.ts`

- [x] 20. FE-WS-4 — Operations uplift slot
  - [x] 20.1 Reserve and honestly gate the Operations uplift slot
    - Reserve a defined slot in the Operations Surface for a system-level uplift display; when the Backend_Contract exposes an uplift measure render it with its sample size, window, and "as of" timestamp; when it does not (a Cross_Boundary_Dependency) render "awaiting uplift measure" and record the missing capability as a backend gap in the drift report rather than hiding the slot; never fabricate an uplift value
    - _Requirements: 17.1, 17.2, 17.3, 17.4_

- [x] 21. Checkpoint — FE-WS-4 quality system green
  - Ensure all tests pass, ask the user if questions arise.

- [x] 22. FE-WS-5 — Reconcile the ConsensusChoreography comment
  - [x] 22.1 Update the stale ConsensusChoreography comment
    - Update the `ConsensusChoreography.tsx` source comment (~line 33) that claims live cognition is deferred (ADR-051) to reflect that live cognition is now wired (per C48), referencing the current wiring accurately and dropping the "deferred" claim; make no functional change and preserve existing component behaviour
    - _Requirements: 18.1, 18.2, 18.3_

- [x] 23. FE-WS-5 — Retire legacy theme JavaScript
  - [x] 23.1 Audit and remove/migrate `src/theme/*.js`
    - Audit `src/theme/*.js` (including `agents.js` and `useTheme.js`) for any live import path; remove each unreferenced (dead) file and migrate any referenced file to strict TypeScript updating its importers with behaviour preserved, so no `.js` file remains under `src/theme/` and `tsc --noEmit` passes under strict settings
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 20.4_

- [x] 24. Governance conformance
  - [x] 24.1 Register the new invariants and extend mutation coverage
    - Register `FE-INV-054`..`FE-INV-071` in `frontend/spec/fe_invariants.yaml` binding each new guarantee to an implementation and a test: harness/zero-live-network (Req 1), schema-bound fixtures (Req 2), JTBD task completion (Req 3), scorecard + ratchet (Req 4), nightly Real_Stack_Run (Req 5), firehose ring-buffer bound + at-most-once (Req 6), reconnect/replay acted-never-reverted (Req 7), fault-transition correctness (Req 8), scale virtualization (Req 9), spatial WebGL/chromatic correctness (Req 10), Trust_Track_Record honesty (Req 11), Expected_Review_Value + honest degradation (Req 12), Interruption_Precision gate (Req 13), Visual_Regression_Gate (Req 14), assistive/mobile/Lighthouse (Req 15), contract-drift closure (Req 16), Operations uplift slot (Req 17), and no-legacy-`.js`-under-`src/theme` (Req 19); extend the Stryker critical-module set to include `effectiveness-ratchet.ts`, `ring-buffer.ts`, `reconcile.ts`, `expected-review-value.ts`, `interruption-precision.ts`, and `trust-track-record.ts`; ensure `check_fe_invariants.py` fails on any gap
    - _Requirements: 20.1_

  - [x] 24.2 Final conformance sweep
    - Confirm the feature introduces no paid or GPL-3.0/AGPL-3.0 dependency and makes zero paid-SaaS calls (license + egress audit); the PR gate stays deterministic with all real-stack/nondeterministic checks isolated to the scheduled workflow; `tsc --noEmit` passes under strict settings; the UI ships English only (no new locale catalog, switcher, or detector); every effectiveness result (scorecard rows, Interruption_Precision, Assistive_Tech_Flow, Operations uplift slot) renders the Scripted_Proxy ceiling statement; and every MSW_Fixture stays bound to an existing Domain_Schema
    - _Requirements: 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_

- [x] 25. Final checkpoint — full suite green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (property and other test sub-tasks) and can be skipped for a faster MVP; core implementation tasks are never optional.
- Each task references specific requirement sub-clauses for traceability, and each property sub-task references a numbered property tagged `Feature: atlas-console-effectiveness, Property {number}: {property_text}` running fast-check + Vitest at `numRuns: 100` minimum.
- Behaviour-against-data, resilience, scale, and spatial checks run through the MSW-in-browser harness under Playwright; visual-regression, assistive-technology, and mobile-reality checks run under Playwright with $0/OSS tooling.
- The pull-request gate (`.github/workflows/frontend.yml`) stays deterministic; the nightly Real_Stack_Run lives in a separate scheduled workflow so real-stack latency and nondeterminism never make the PR gate flaky.
- This spec builds on `atlas-console-elevation` and does not re-cover display fidelity; it is additive within the existing layering and must keep the invariant-coverage, strict-TypeScript, and $0-cost governance gates green throughout.
- Honest ceiling: RITE real-user testing (3–5 operators) is out of scope; the harness is a Scripted_Proxy that proves path existence and efficiency only, and every effectiveness artifact states that ceiling.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "22.1", "23.1"] },
    { "id": 1, "tasks": ["1.2", "3.1"] },
    { "id": 2, "tasks": ["1.3", "1.4", "2.1", "2.2", "7.1", "9.1", "10.1", "11.1", "13.1", "14.1", "19.1", "20.1"] },
    { "id": 3, "tasks": ["2.3", "2.4", "3.2", "7.2", "7.3", "8.1", "9.2", "9.3", "10.2", "10.3", "13.2", "19.2"] },
    { "id": 4, "tasks": ["4.1", "8.2", "8.3", "8.4", "13.3", "13.4", "13.5", "14.2"] },
    { "id": 5, "tasks": ["4.2", "14.3", "14.4", "14.5", "15.1", "17.1"] },
    { "id": 6, "tasks": ["4.3", "5.1", "15.2"] },
    { "id": 7, "tasks": ["5.2", "15.3", "18.1", "18.2"] },
    { "id": 8, "tasks": ["24.1"] },
    { "id": 9, "tasks": ["24.2"] }
  ]
}
```
