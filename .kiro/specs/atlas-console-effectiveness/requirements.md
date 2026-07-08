# Requirements Document

## Introduction

Atlas Console is the human-facing command center for SYNAPSE — a multi-agent reinforcement-learning platform running an autonomous quick-commerce supply chain (8 specialized agents, a 4-tier consensus orchestrator, confidence-gated execution with human-in-the-loop escalation, and a cryptographic audit hash-chain). The Console (React 18 + Vite + TypeScript, `frontend/`, package `synapse-console`) already ships a mature, invariant-governed surface set. The completed **Atlas Console Elevation** spec proved *display fidelity*: honesty-gated rendering, 53 registered `FE-INV-*` invariants, the OKLCH chromatic system and motion vocabulary, universal-state coverage, and mechanical contract-fidelity checking. That work is done and is **not** re-covered here.

This feature — **Atlas Console Effectiveness** — closes the dimensions the prior spec left at zero or shallow coverage. The core thesis: *the Console is "complete" only against the backend's API surface, never against the operator's job or the real conditions of that job.* Proving that a route renders and passes an accessibility scan says nothing about whether the Console behaves correctly against real data, makes the operator measurably faster and more accurate, holds under stress, or earns calibrated trust over time. This spec elevates the Console to prove those things to the same mechanical-gate standard SYNAPSE already applies to backend code.

Five workstreams organize the work:

1. **FE-WS-1 — Integration + effectiveness harness (keystone).** Today Playwright runs against `pnpm preview` with no backend, so every `/api` call is `ECONNREFUSED` (evidence E-S12-12) and the suite proves nothing about behavior against data. Run Mock Service Worker (MSW) inside the Playwright browser to drive every Surface against seeded, deterministic fixtures and scripted WebSocket/SSE streams — converting E2E from "routes render + pass axe" into "the Console behaves correctly against data." Bind fixtures to the same Zod domain schemas the app validates against so mocks are provably contract-accurate. Enumerate the operator's Jobs-To-Be-Done and measure task completion. Emit a versioned effectiveness scorecard with a ratchet gate — the UI analog of the backend's `uplift_truth`.
2. **FE-WS-2 — Resilience under real conditions.** Firehose stress, reconnect/replay reconciliation, backend fault transitions, scale (10k+ rows must actually virtualize), and WebGL/spatial correctness in a real browser.
3. **FE-WS-3 — Trust loop + attention model.** Show operators their own longitudinal track record, allocate attention by expected value (not confidence alone), and measure and gate **Interruption Precision** — the single most important metric: of the times the Console demanded human judgment, what fraction were worth it.
4. **FE-WS-4 — Complete the quality system.** Visual-regression gate, real assistive-technology and mobile-reality testing, closure of the permanently-red contract-drift gate, and a reserved Operations slot for system-level uplift.
5. **FE-WS-5 — Retire debt & reconcile.** Fix the stale `ConsensusChoreography` comment and remove/migrate legacy `src/theme/*.js`.

**Honest ceiling (encoded, not hidden).** True effectiveness requires real users (RITE testing with 3–5 operators). Absent that, this harness provides a *scripted proxy* — Jobs-To-Be-Done step/latency measurement plus a heuristic scorecard — that proves the operator's path exists and is efficient but does **not** prove human comprehension. Every effectiveness claim in this spec is bounded by that ceiling and states it explicitly rather than over-claiming.

All existing governance constraints are inherited as hard, non-negotiable requirements: $0-cost / open-source-only (no paid SaaS, no GPL-3.0/AGPL-3.0), every new guarantee registered as an `FE-INV-*` invariant with a test, a deterministic (non-flaky) PR gate, MSW fixtures bound to existing Zod schemas, honesty about the mock (nightly runs against the real stack for fidelity), strict TypeScript, English-only UI, and the Web Vitals budget (LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1).

This document defines *what* the effective Console must do and guarantee. Component design and file layout are deferred to the design phase.

## Glossary

- **Atlas_Console**: The SYNAPSE web frontend (`frontend/`, package `synapse-console`); the human command center for the platform. Referred to below as "THE Atlas_Console".
- **Backend_Contract**: The set of HTTP/WebSocket/SSE endpoints, request/response shapes, and channel payloads exposed by the SYNAPSE API gateway and orchestrator (`api/routers/*`) that the Atlas_Console is entitled to consume.
- **Domain_Schema**: A Zod schema in the Atlas_Console that validates a Backend_Contract payload before rendering (the schemas governed by FE-INV-002).
- **Effectiveness_Harness**: The Mock Service Worker (MSW) instance running inside the Playwright browser as a service worker, serving seeded deterministic fixtures and scripted WebSocket/SSE streams so every Surface can be exercised against data without a live backend. The deterministic PR gate.
- **MSW_Fixture**: A seeded, deterministic response or streamed message served by the Effectiveness_Harness, constructed from and validated against the same Domain_Schema the Atlas_Console validates against at runtime.
- **Real_Stack_Run**: A nightly execution of the same task suite against the real SYNAPSE docker stack (live gateway, orchestrator, and datastores) used to confirm the Effectiveness_Harness fixtures remain faithful to real backend behavior.
- **Job_To_Be_Done**: A named, end-to-end operator objective the Console must support, measured for task completion. The enumerated set includes at minimum: resolve an escalation correctly, identify which agent degraded and why, reconstruct a decision's rationale, adjust steering safely, and catch a disruption before it cascades.
- **Task_Completion_Test**: A Playwright test that drives a single Job_To_Be_Done against a seeded scenario in the Effectiveness_Harness and records steps taken, time-to-complete, and error/dead-end rate.
- **Effectiveness_Scorecard**: The versioned artifact recording, per Job_To_Be_Done, the measured steps, latency, and error/dead-end rate produced by the Task_Completion_Tests.
- **Effectiveness_Ratchet**: The CI gate that compares a pull request's Effectiveness_Scorecard against the committed baseline and fails on regression beyond a defined tolerance; the UI analog of the backend's `uplift_truth`.
- **Scripted_Proxy**: The Effectiveness_Harness's method of measuring effectiveness through scripted Task_Completion_Tests and heuristic scoring. It proves an operator path exists and is efficient; it does NOT prove human comprehension, which requires real-user (RITE) testing.
- **Resilience_Scenario**: A named, reproducible adverse condition driven by the Effectiveness_Harness — e.g., message firehose at a target rate, reconnect with `since_seq` replay burst, backend 503, schema-violation payload, 401 storm, WebSocket flap, offline↔online transition, or a 10k+ row dataset.
- **Ring_Buffer**: The bounded in-memory store for streamed messages that caps retained items so sustained streaming does not grow memory without limit.
- **Interruption_Precision**: The North-Star effectiveness metric. Of the decisions for which the Atlas_Console demanded human judgment (escalated / interrupted the operator), the fraction whose human review was warranted — i.e., the review changed the outcome or confirmed a genuinely uncertain, irreversible, or high-blast-radius decision. Formally, warranted interruptions ÷ total interruptions over a defined window.
- **Expected_Review_Value**: The scoring function that ranks a decision's need for human review as a function of confidence, reversibility, and blast-radius — `f(confidence, reversibility, blast_radius)` — replacing a confidence-only escalation model.
- **Reversibility**: A property of a decision indicating whether its effect can be undone (e.g., reversible price nudge vs. an irreversible dispatched shipment). Sourced from a Backend_Contract field on the decision envelope when present; a cross-boundary dependency that must degrade honestly when absent.
- **Blast_Radius**: A property of a decision indicating the breadth of its impact (e.g., single order vs. city-wide reprice). Sourced from a Backend_Contract field on the decision envelope when present; a cross-boundary dependency that must degrade honestly when absent.
- **Trust_Track_Record**: A per-operator longitudinal view of the operator's own past judgments and their realized outcomes (e.g., low-confidence decisions the operator approved, later confirmed vs. diverged), derived from `decision_outcomes` and `audit_escalations`.
- **Visual_Regression_Gate**: The CI gate that captures deterministic screenshots of key Surfaces/stories and fails when a rendered diff exceeds a defined threshold, catching design-token and layout regressions.
- **Assistive_Tech_Flow**: A scripted screen-reader walkthrough (NVDA and/or VoiceOver) of a Surface performing a Job_To_Be_Done, verifying the operator can complete the job non-visually.
- **Mobile_Reality_Profile**: The constrained device/network profile used to test the On_Call_Responder persona: 360px viewport width, touch input, and throttled 3G network.
- **Cross_Boundary_Dependency**: A capability the Atlas_Console needs from the Backend_Contract that may not yet exist; when absent, the Atlas_Console must degrade honestly (render an explicit unavailable state) and the drift report must record the backend gap.
- **Coverage_Status**: The classification of a Backend_Contract capability's representation in the Atlas_Console: `covered`, `partial`, or `uncovered` (as defined in the Atlas Console Elevation spec).
- **Contract_Fidelity_Suite**: The mechanical checks and generated artifacts that compare the Atlas_Console's typed client/domain schemas against the Backend_Contract and report drift (from the Atlas Console Elevation spec).
- **Universal_State**: One of the render conditions every data-bearing Surface defines: loading, empty, error, degraded, offline, and populated (from the Atlas Console Elevation spec).
- **Chromatic_Token**: A color value delivered exclusively via a `var(--syn-*)` custom property; no raw hex/rgb/hsl literal is permitted in `frontend/src/**` (INV-CLR-009).
- **Chromatic_System**: The OKLCH design-token color system governing agent identity (Hue), decision tier (Lightness), confidence (diverging OKLab scale), and semantic/state tokens.
- **Spatial_Visualization**: The purposeful 2D/3D visualization surfaces — the deck.gl/MapLibre living map and the sigma/graphology supply-network graph.
- **Web_Vitals_Budget**: LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1 (FE-INV-010) on the target route/network profile.
- **Operations_Controller**: An `ops`/`admin` operator supervising live agent decisions in Mission Control and the Override Cockpit.
- **Analyst**: An `engineer`/`admin` user investigating decisions, calibration, and the audit trail.
- **On_Call_Responder**: An operator handling escalations and disruptions, often on a constrained device or network.
- **Stakeholder_Viewer**: A `viewer` observing the Demo Theater / live surfaces without mutation rights.
- **Surface**: A top-level Console route/screen: mission-control, decision-theater, override-cockpit, audit-vault, operations, steering, twin-lab, council-theater, agent-council, live-markets, ingress, auth, demo-theater.
- **FE_Invariant**: A frontend guarantee registered in `frontend/spec/fe_invariants.yaml` as `FE-INV-*` with a corresponding implementation and test (next available id is FE-INV-054).

---

## Requirements

### Requirement 1: MSW-in-Browser Integration Harness (Keystone)

**User Story:** As an Analyst maintaining the platform, I want every Surface driven against seeded, deterministic backend behavior inside the E2E browser, so that end-to-end tests prove the Console behaves correctly against data rather than only that routes render.

#### Acceptance Criteria

1. THE Effectiveness_Harness SHALL run Mock Service Worker as a browser service worker inside the Playwright-controlled browser and SHALL intercept every HTTP request the Atlas_Console issues to a Backend_Contract path so that no request reaches a live network endpoint during a harness-mode test.
2. THE Effectiveness_Harness SHALL serve scripted WebSocket and SSE streams for every real-time channel the Atlas_Console subscribes to, delivering a deterministic, ordered sequence of messages for a given seed.
3. WHEN a harness-mode test runs against a fixed seed, THE Effectiveness_Harness SHALL produce byte-identical fixture responses and an identical stream message order on every run so that the PR gate is deterministic and non-flaky.
4. THE Effectiveness_Harness SHALL cover every Surface in the surface list (mission-control, decision-theater, override-cockpit, audit-vault, operations, steering, twin-lab, council-theater, agent-council, live-markets, ingress, auth, demo-theater) with at least one seeded scenario that reaches the populated Universal_State.
5. WHILE the Effectiveness_Harness is active, THE Atlas_Console SHALL make zero calls to any live or third-party network endpoint, consistent with the $0-cost / no-paid-SaaS constraint.
6. IF a harness-mode test issues a Backend_Contract request for which no MSW_Fixture is registered, THEN THE Effectiveness_Harness SHALL fail the test and name the unhandled path rather than silently returning an empty or default response.

### Requirement 2: Contract-Accurate Fixtures Bound to Domain Schemas

**User Story:** As an Analyst, I want the harness fixtures validated against the same schemas the app validates against, so that a passing harness test cannot be built on a mock that misrepresents the real contract.

#### Acceptance Criteria

1. WHEN an MSW_Fixture is constructed, THE Effectiveness_Harness SHALL validate that fixture against the same Domain_Schema the Atlas_Console applies to that payload at runtime, and IF the fixture fails Domain_Schema validation, THEN THE Effectiveness_Harness SHALL fail at build or setup time and name the offending fixture and schema.
2. THE Effectiveness_Harness SHALL derive every MSW_Fixture's shape from a Domain_Schema and SHALL NOT hand-author a fixture whose shape is not schema-bound.
3. WHEN a Domain_Schema changes such that an existing MSW_Fixture no longer validates, THE Effectiveness_Harness SHALL fail the affected test so that fixture drift from the contract is caught mechanically.
4. WHERE a Backend_Contract capability has no Domain_Schema (a schema-less capability), THE Effectiveness_Harness SHALL mark the corresponding fixture as schema-less and SHALL surface that classification in the harness report rather than treating it as schema-bound.
5. THE Effectiveness_Harness SHALL seed at least one fixture per streamed channel that produces a schema-violating payload on demand, so that Requirement 8's schema-violation transition can be exercised deterministically.

### Requirement 3: Operator Job-To-Be-Done Task Completion

**User Story:** As an Operations_Controller, I want the Console measured on whether an operator can actually complete the core jobs, so that "done" means the operator's job is supported, not just that an endpoint is wired.

#### Acceptance Criteria

1. THE Effectiveness_Harness SHALL enumerate a named set of Jobs-To-Be-Done covering at minimum: resolve an escalation correctly, identify which agent degraded and why, reconstruct a decision's rationale, adjust steering safely, and catch a disruption before it cascades.
2. WHERE a Job_To_Be_Done is enumerated, THE Effectiveness_Harness SHALL provide a Task_Completion_Test that drives that job against a seeded scenario and records steps taken, time-to-complete, and error/dead-end rate.
3. WHEN a Task_Completion_Test runs, THE Task_Completion_Test SHALL assert the operator reaches the correct terminal outcome for its seeded scenario (e.g., the escalation is resolved with the correct action) and SHALL fail if the terminal outcome is wrong or unreachable.
4. IF a Task_Completion_Test encounters a dead-end (a required affordance is missing, disabled without cause, or leads to a non-recoverable state), THEN THE Task_Completion_Test SHALL record the dead-end and fail.
5. THE Task_Completion_Test for "resolve an escalation correctly" SHALL verify the override commits the audit row before the decision is marked acted, consistent with the audit-row-first guarantee, when driven through the Effectiveness_Harness.
6. THE Effectiveness_Harness SHALL state, in the report for every Task_Completion_Test, that the measurement is a Scripted_Proxy that demonstrates path existence and efficiency and does NOT establish human comprehension.

### Requirement 4: Effectiveness Scorecard and Ratchet Gate

**User Story:** As a maintainer, I want a versioned, gated record of Console effectiveness per job, so that a change that makes an operator slower or more error-prone fails CI the way a code regression does.

#### Acceptance Criteria

1. WHEN the Task_Completion_Tests complete, THE Effectiveness_Harness SHALL emit an Effectiveness_Scorecard recording, per Job_To_Be_Done, the measured steps, time-to-complete, and error/dead-end rate.
2. THE Effectiveness_Scorecard SHALL be versioned and committed to the repository so that each measurement is comparable against a stored baseline.
3. WHEN the Effectiveness_Ratchet runs on a pull request, IF any Job_To_Be_Done's steps, latency, or error/dead-end rate regresses beyond the defined tolerance relative to the committed baseline, THEN THE Effectiveness_Ratchet SHALL fail the check with a non-zero exit status and name the regressed job and metric.
4. THE Effectiveness_Ratchet SHALL define its regression tolerance explicitly and SHALL derive pass/fail from deterministic harness measurements so the gate is not flaky.
5. WHEN an improvement lowers a job's steps or latency below the baseline, THE Effectiveness_Ratchet SHALL permit updating the committed baseline so the ratchet advances monotonically.
6. THE Effectiveness_Scorecard SHALL record the seed and harness version used for each measurement so a result is reproducible.

### Requirement 5: Nightly Real-Stack Fidelity

**User Story:** As an Analyst, I want the harness fixtures checked against the real backend on a schedule, so that the deterministic mock never quietly diverges from real backend behavior.

#### Acceptance Criteria

1. THE Real_Stack_Run SHALL execute the same Task_Completion_Test suite against the real SYNAPSE docker stack on a nightly schedule.
2. WHEN a Real_Stack_Run completes, IF a Task_Completion_Test that passes under the Effectiveness_Harness fails against the real stack, THEN THE Real_Stack_Run SHALL report the divergence and name the job and the observed contract difference.
3. THE Real_Stack_Run SHALL be separate from the pull-request gate so that real-stack latency and nondeterminism never make the deterministic PR gate flaky.
4. WHERE a Real_Stack_Run reveals that an MSW_Fixture no longer matches real backend behavior, THE Real_Stack_Run report SHALL identify the fixture requiring reconciliation.
5. THE Real_Stack_Run SHALL record the backend build SHA it ran against so a fidelity divergence is traceable to a backend version.

### Requirement 6: Firehose Stress Resilience

**User Story:** As an Operations_Controller watching a live surge, I want the Console to stay responsive and memory-stable under a high message rate, so that a busy period never degrades supervision.

#### Acceptance Criteria

1. WHILE the Effectiveness_Harness drives a Resilience_Scenario streaming messages at the defined realistic and adversarial rates, THE Atlas_Console SHALL keep INP within the Web_Vitals_Budget (≤ 200ms).
2. WHILE a sustained firehose Resilience_Scenario runs, THE Atlas_Console SHALL retain streamed messages in a bounded Ring_Buffer whose size does not grow beyond its defined cap regardless of how many messages arrive.
3. WHEN a streamed message carries a sequence already applied, THE Atlas_Console SHALL drop the duplicate and SHALL NOT apply any message more than once, consistent with the at-most-once sequence guarantee.
4. WHILE a firehose Resilience_Scenario runs, THE Atlas_Console SHALL NOT reflow or reorder already-rendered content in a way that produces dropped-frame jank on the target device profile.
5. WHEN the firehose Resilience_Scenario ends, THE Atlas_Console SHALL reflect a state consistent with the applied (deduplicated) message set with no lost and no double-counted items.

### Requirement 7: Reconnect and Replay Reconciliation

**User Story:** As an On_Call_Responder on an unstable network, I want the Console to reconcile cleanly after a reconnect and replay burst, so that my acted decisions never revert and I never see duplicate rows.

#### Acceptance Criteria

1. WHEN a real-time connection drops and reconnects, THE Atlas_Console SHALL request replay from its last applied sequence (`since_seq`) and SHALL reconcile the replay burst without rendering duplicate rows.
2. WHEN a replayed message references a decision the operator has already acted on, THE Atlas_Console SHALL keep that decision in its acted state and SHALL NOT revert it to pending, verified at the rendered output and not only at the reducer level.
3. WHILE reconnecting, THE Atlas_Console SHALL reconnect with bounded Full-Jitter backoff.
4. WHEN a reconnect-and-replay Resilience_Scenario completes, THE rendered row set SHALL equal the deduplicated union of pre-drop and replayed state with no duplicate, lost, or reverted rows.
5. THE Effectiveness_Harness SHALL provide a Resilience_Scenario that scripts a drop, a `since_seq` replay burst containing at least one already-acted decision, and a resumed live stream, so this reconciliation is exercised deterministically.

### Requirement 8: Fault-Transition State Correctness

**User Story:** As an On_Call_Responder, I want every backend fault and connectivity transition to render the correct distinct state, so that I am never shown a false-healthy screen during a disruption.

#### Acceptance Criteria

1. WHEN the Effectiveness_Harness returns a 503 for a data request, THE Atlas_Console SHALL render the error (or degraded, where the payload signals degradation) Universal_State for the affected Surface and SHALL NOT render a populated healthy state.
2. WHEN the Effectiveness_Harness returns a schema-violating payload, THE Atlas_Console SHALL render the error Universal_State through the schema-violation path and SHALL NOT render the unvalidated payload.
3. WHILE the Effectiveness_Harness drives a 401 storm, THE Atlas_Console SHALL attempt a single-flight token refresh and, IF refresh fails or a second 401 occurs, THEN THE Atlas_Console SHALL clear the session and route to login without a full page reload.
4. WHEN the Effectiveness_Harness flaps the WebSocket connection repeatedly, THE Atlas_Console SHALL render the not-live / reconnecting state through a non-color channel and SHALL recover to the live state when the flap ends.
5. WHEN the Effectiveness_Harness transitions the browser offline and back online, THE Atlas_Console SHALL render the offline Universal_State while offline, SHALL NOT present stale data as live, and SHALL restore the populated state on return to online.
6. WHERE a Resilience_Scenario chains multiple transitions in sequence, THE Atlas_Console SHALL render the correct distinct Universal_State at every step of the chain rather than latching on a prior state.

### Requirement 9: Scale Virtualization

**User Story:** As an Analyst reviewing a large audit trail, I want dense tables to virtualize at scale, so that ten thousand rows do not degrade responsiveness or truncate the data.

#### Acceptance Criteria

1. WHEN the Effectiveness_Harness seeds a dataset of at least 10,000 audit or decision rows, THE Atlas_Console SHALL render the Audit Vault and Decision Theater with row virtualization actually engaged such that the count of mounted row nodes remains bounded and far below the total row count.
2. WHILE a virtualized dataset of at least 10,000 rows is displayed, THE Atlas_Console SHALL keep scroll and interaction responsiveness within the Web_Vitals_Budget (INP ≤ 200ms).
3. THE Atlas_Console SHALL NOT cap a virtualized dataset at a fixed row limit (e.g., 200 rows) that hides available rows from the operator; the full seeded row set SHALL be reachable by scrolling.
4. WHEN a virtualized row is scrolled into view, THE Atlas_Console SHALL render that row's data consistent with its seeded fixture so virtualization does not misalign row content.
5. THE Effectiveness_Harness SHALL provide a Resilience_Scenario seeding at least 10,000 rows for both the Audit Vault and Decision Theater so virtualization is verified against data, not asserted by inspection.

### Requirement 10: Spatial Visualization Correctness in a Real Browser

**User Story:** As an Analyst using the map and network graph, I want the spatial surfaces verified for WebGL rendering and correct color encoding in a real browser, so that the most impressive surfaces are also the most proven.

#### Acceptance Criteria

1. WHEN a Spatial_Visualization renders in the Playwright browser, THE Atlas_Console SHALL initialize its WebGL context successfully and SHALL render without throwing an uncaught error (a WebGL smoke check).
2. WHEN a Spatial_Visualization encodes agent, tier, or confidence data, THE Spatial_Visualization SHALL use the same Chromatic_Token encoding as the rest of the Atlas_Console, verified against the resolved token values in a real browser rather than in jsdom.
3. IF a Spatial_Visualization fails to initialize its WebGL context, THEN THE Atlas_Console SHALL render the error Universal_State with a retry affordance rather than a blank canvas.
4. WHILE a Spatial_Visualization is loading, THE Atlas_Console SHALL render the loading Universal_State and SHALL provide the equivalent non-spatial representation (table, list, or text summary) reachable by keyboard and screen reader.
5. THE Effectiveness_Harness SHALL seed deterministic geospatial and network-graph fixtures so the chromatic-encoding correctness check is reproducible.

### Requirement 11: Longitudinal Operator Trust Track Record

**User Story:** As an Operations_Controller, I want to see my own track record of past judgments and how they turned out, so that my trust in my own and the agents' decisions is calibrated by evidence over time.

#### Acceptance Criteria

1. THE Atlas_Console SHALL render a Trust_Track_Record for the authenticated operator, derived from `decision_outcomes` and `audit_escalations`, summarizing the operator's past judgments and their realized outcomes over a defined window.
2. WHEN the Trust_Track_Record summarizes low-confidence decisions the operator approved, THE Atlas_Console SHALL render the count later confirmed and the count later diverged as distinct values (e.g., "12 approved → 10 confirmed, 2 diverged").
3. THE Trust_Track_Record SHALL render outcomes as the three distinct states confirmed, diverged, and unknown, and SHALL NOT fold `unknown` (not yet realized) into `confirmed`.
4. THE Trust_Track_Record SHALL disclose its sample size, evaluation window, and an "as of" timestamp, and IF fewer than the defined minimum scored outcomes exist, THEN THE Atlas_Console SHALL flag the display as provisional.
5. IF no scored outcomes exist for the operator in the window, THEN THE Atlas_Console SHALL render "awaiting scored outcomes" rather than a fabricated or zeroed track record.
6. THE Trust_Track_Record SHALL exclude Synthetic decisions from its aggregates by default and SHALL expose a labelled control to include them.

### Requirement 12: Expected-Value Attention Model

**User Story:** As an Operations_Controller, I want the Console to demand my attention based on the true stakes of a decision, so that irreversible or high-impact decisions get human review even when confidence is high, and low-stakes decisions do not waste my attention.

#### Acceptance Criteria

1. THE Atlas_Console SHALL compute Expected_Review_Value as a function of confidence, Reversibility, and Blast_Radius, and SHALL rank a decision's need for human review by that value rather than by confidence alone.
2. WHERE a decision is irreversible or high-blast-radius, THE Atlas_Console SHALL escalate it for human review even when its confidence is at or above the 0.80 autonomy gate.
3. WHEN the Atlas_Console places default keyboard focus among override actions, THE Atlas_Console SHALL derive the focus from Expected_Review_Value rather than from confidence alone, superseding the confidence-only focus-demotion model.
4. WHERE the Backend_Contract decision envelope provides Reversibility and Blast_Radius fields, THE Atlas_Console SHALL use those fields in Expected_Review_Value.
5. IF the Backend_Contract does not provide Reversibility or Blast_Radius (a Cross_Boundary_Dependency), THEN THE Atlas_Console SHALL degrade honestly — fall back to the confidence-based ranking, render an explicit indication that reversibility/blast-radius are unavailable, and record the missing fields as a backend gap in the drift report — rather than fabricating a value.
6. THE Atlas_Console SHALL render, for each decision it escalates on stakes rather than confidence, an explicit non-color indication of why it demanded review (irreversible and/or high blast-radius).

### Requirement 13: Interruption Precision Measurement and Gate

**User Story:** As a maintainer, I want the Console's interruption precision measured and gated, so that the Console is held to demanding human judgment only when it is worth it.

#### Acceptance Criteria

1. THE Atlas_Console SHALL define Interruption_Precision as the fraction of interruptions (escalations demanding human judgment) that were warranted — where the review changed the outcome or confirmed a genuinely uncertain, irreversible, or high-blast-radius decision — over a defined window.
2. WHEN the Task_Completion_Tests run over the seeded scenarios, THE Effectiveness_Harness SHALL compute Interruption_Precision and record it in the Effectiveness_Scorecard.
3. WHEN the Effectiveness_Ratchet runs, IF Interruption_Precision regresses below its committed baseline beyond the defined tolerance, THEN THE Effectiveness_Ratchet SHALL fail the check and name Interruption_Precision as the regressed metric.
4. THE Effectiveness_Scorecard SHALL present Interruption_Precision as the primary (North-Star) effectiveness metric.
5. THE Effectiveness_Harness SHALL state that Interruption_Precision is measured over a Scripted_Proxy of seeded scenarios and that its real-world value requires validation with real operators.

### Requirement 14: Visual-Regression Gate

**User Story:** As a maintainer of a design-token-heavy Console, I want a screenshot-diffing gate, so that an unintended token or layout change fails CI instead of shipping silently.

#### Acceptance Criteria

1. THE Visual_Regression_Gate SHALL capture deterministic screenshots of a defined set of key Surfaces and/or Storybook stories under fixed viewport, theme, and seed.
2. WHEN the Visual_Regression_Gate runs on a pull request, IF a captured screenshot differs from its committed baseline beyond the defined pixel/perceptual threshold, THEN THE Visual_Regression_Gate SHALL fail the check and identify the changed Surface or story.
3. THE Visual_Regression_Gate SHALL render screenshots deterministically (fixed fonts, disabled animation, fixed seed, masked volatile regions) so that the gate is not flaky.
4. WHEN an intended visual change is made, THE Visual_Regression_Gate SHALL permit updating the committed baseline so an approved change advances the baseline.
5. THE Visual_Regression_Gate SHALL cover at least one Surface per Theme_Mode-sensitive rendering (light, dark, and hc) so a token regression in any mode is caught.
6. THE Visual_Regression_Gate SHALL use only $0-cost / open-source tooling and SHALL NOT depend on a paid visual-diffing SaaS.

### Requirement 15: Assistive-Technology and Mobile Reality

**User Story:** As an On_Call_Responder using a screen reader on a phone over a slow network, I want the cockpit proven usable under real assistive-technology and mobile conditions, so that I can handle a live escalation regardless of device or ability.

#### Acceptance Criteria

1. THE Atlas_Console SHALL provide an Assistive_Tech_Flow that scripts a screen-reader (NVDA and/or VoiceOver) walkthrough of resolving a live escalation in the Override Cockpit, asserting the operator can perceive the escalation, its violations, and the action outcome non-visually.
2. WHEN the Assistive_Tech_Flow performs an override, THE Atlas_Console SHALL announce the action outcome through an appropriate live region so it is conveyed to assistive technology.
3. THE Atlas_Console SHALL pass its key Surfaces under the Mobile_Reality_Profile (360px viewport, touch input, throttled 3G) with all primary Jobs-To-Be-Done reachable and operable.
4. WHILE under the Mobile_Reality_Profile, THE Atlas_Console SHALL meet the Web_Vitals_Budget (LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1) on the measured key routes.
5. THE Atlas_Console SHALL extend Lighthouse CI to a mobile profile on the defined key routes and SHALL fail the check when a route falls below its defined mobile budget.
6. THE Atlas_Console SHALL state the ceiling that scripted Assistive_Tech_Flows demonstrate operability but do not replace validation with real assistive-technology users.

### Requirement 16: Close the Contract-Drift Red Gate

**User Story:** As a maintainer, I want the schema-less capabilities resolved to an honest, non-red state, so that the contract-fidelity gate stays meaningful and a permanently-red gate does not corrode the honesty culture.

#### Acceptance Criteria

1. THE Contract_Fidelity_Suite SHALL define, for each schema-less Backend_Contract capability (a capability with no response body or an open/unconstrained shape), an explicit classification of either "no-body/open-shape ⇒ covered" or "tracked-partial".
2. WHERE a schema-less capability is classified "no-body/open-shape ⇒ covered", THE Contract_Fidelity_Suite SHALL treat it as covered and SHALL NOT fail the drift gate for the absence of a response schema.
3. WHERE a schema-less capability is classified "tracked-partial", THE Contract_Fidelity_Suite SHALL record it as a tracked partial with a named rationale and SHALL NOT leave it as an untracked failure.
4. WHEN the Contract_Fidelity_Suite runs after this classification, THE drift gate SHALL reach a green (passing) state for the entitled surface with every schema-less capability resolved to one of the two classifications.
5. IF a new schema-less capability appears that is neither classified nor entitled-out-of-scope, THEN THE Contract_Fidelity_Suite SHALL fail and name it so the classification decision is forced rather than silently absorbed.

### Requirement 17: Operations Uplift Slot

**User Story:** As a Stakeholder_Viewer, I want a reserved place in the Operations surface for system-level uplift, so that when the backend exposes an uplift measure it can be displayed honestly without re-architecting the surface.

#### Acceptance Criteria

1. THE Atlas_Console SHALL reserve a defined slot in the Operations Surface for a system-level uplift display.
2. WHERE the Backend_Contract exposes a system-level uplift measure, THE Atlas_Console SHALL render it in the reserved slot with its sample size, window, and "as of" timestamp.
3. IF the Backend_Contract exposes no system-level uplift measure (a Cross_Boundary_Dependency), THEN THE Atlas_Console SHALL render the slot as "awaiting uplift measure" and SHALL record the missing capability as a backend gap in the drift report rather than hiding the slot.
4. THE Atlas_Console SHALL NOT fabricate an uplift value when none is provided by the Backend_Contract.

### Requirement 18: Reconcile the ConsensusChoreography Comment

**User Story:** As an Analyst reading the code, I want stale ADR references corrected, so that documentation reflects the wired reality and does not mislead.

#### Acceptance Criteria

1. THE Atlas_Console SHALL update the `ConsensusChoreography` source comment that states live cognition is deferred (referencing ADR-051) to reflect that live cognition is now wired (per C48).
2. THE reconciled comment SHALL reference the current wiring accurately and SHALL NOT retain the "deferred" claim.
3. WHEN the comment is reconciled, THE Atlas_Console SHALL preserve the existing behavior of the `ConsensusChoreography` component and SHALL make no functional change under this requirement.

### Requirement 19: Retire Legacy Theme JavaScript

**User Story:** As a maintainer of a strict-TypeScript codebase, I want legacy JavaScript theme files audited and removed or migrated, so that no dead or untyped code lingers in the source tree.

#### Acceptance Criteria

1. THE Atlas_Console SHALL audit `src/theme/*.js` (including `agents.js` and `useTheme.js`) to determine whether each file is referenced by any live import path.
2. WHERE a `src/theme/*.js` file is unreferenced (dead), THE Atlas_Console SHALL remove it.
3. WHERE a `src/theme/*.js` file is referenced, THE Atlas_Console SHALL migrate it to strict TypeScript and update its importers, preserving existing behavior.
4. WHEN the audit is complete, THE Atlas_Console SHALL contain no `.js` file under `src/theme/` and SHALL pass `tsc --noEmit` under strict settings.

### Requirement 20: Governance Conformance and Honest Ceiling

**User Story:** As a maintainer, I want every new effectiveness guarantee mechanically enforced and every effectiveness claim honestly bounded, so that this spec's standard cannot silently regress and cannot over-claim.

#### Acceptance Criteria

1. WHERE this feature introduces a frontend guarantee, THE feature SHALL register it as an FE_Invariant in `frontend/spec/fe_invariants.yaml` (next available id FE-INV-054) with a corresponding implementation and test, and THE invariant-coverage check SHALL fail if any such invariant lacks a test.
2. THE feature SHALL introduce no dependency that is paid or licensed GPL-3.0/AGPL-3.0 and SHALL make zero calls to paid SaaS providers.
3. THE feature SHALL keep the pull-request gate deterministic (non-flaky), isolating all real-stack and nondeterministic checks to nightly or scheduled runs.
4. THE feature SHALL pass `tsc --noEmit` under strict type settings with no type errors.
5. THE Effectiveness_Harness and Effectiveness_Scorecard SHALL state, wherever an effectiveness result is presented, that the measurement is a Scripted_Proxy that proves path existence and efficiency and does NOT prove human comprehension, which requires real-user (RITE) testing with 3–5 operators.
6. THE feature SHALL keep every MSW_Fixture bound to an existing Domain_Schema (per Requirement 2) so the honesty of the mock is mechanically enforced.
7. THE Atlas_Console SHALL ship English only and SHALL NOT introduce any non-English locale catalog, language switcher, or language detector.
