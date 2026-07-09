# Requirements Document

## Introduction

Atlas Console is the human-facing command center for SYNAPSE — a multi-agent reinforcement-learning platform that runs an autonomous quick-commerce supply chain (8 specialized agents, a 4-tier consensus orchestrator, confidence-gated execution with human-in-the-loop escalation, and a cryptographic audit hash-chain). Today the Console (React 18 + Vite + TypeScript, `frontend/`) already ships a mature, invariant-governed surface set: typed Zod clients for every consumed backend route, a chromatic token system authored in OKLCH, a motion vocabulary, honesty/degradation states, and a strong test culture (`frontend/spec/fe_invariants.yaml`, `design-system/color/color-system.spec.yml`).

This feature — **Atlas Console Elevation** — raises the Console to the highest achievable standard as a human–AI collaboration interface, driven by two goals:

1. **Close frontend/backend drift.** Verify the Console fully and correctly expresses the backend's capabilities and stays in sync as contracts evolve, and detect coverage gaps mechanically rather than by inspection.
2. **Elevate the Console into a definitive, agentically-aware experience** in which agency is made visible, trustworthy, and controllable across every agent state; where color carries meaning, motion carries cognition, and spatial visualization carries structure; where craft and accessibility are first-class; and where trust calibration, autonomy control, transparency, cognitive load, and human oversight are explicit design concerns.

The scope is first-principles and evidence-grounded. Requirements deliberately surface unknown-unknowns: agent states the current UI cannot express, trust-calibration gaps, dead moments, and edge realities (different roles, abilities, devices, network/data conditions, degraded and offline states). All existing governance constraints are treated as hard, non-negotiable requirements: English-only UI, chromatic-token-only color, frozen agent→hue encoding, orthogonal color encoding, $0-cost/open-source-only dependencies, strict type safety, and the "every invariant has a test" rule.

This document defines *what* the elevated Console must do and guarantee. Implementation detail (component design, file layout) is deferred to the design phase.

## Glossary

- **Atlas_Console**: The SYNAPSE web frontend (`frontend/`, package `synapse-console`); the human command center for the platform. Referred to below as "THE Atlas_Console".
- **Backend_Contract**: The set of HTTP/WebSocket/SSE endpoints, request/response shapes, and channel payloads exposed by the SYNAPSE API gateway and orchestrator (`api/routers/*`: agents, auth, decisions, escalations, firehose, metrics, orders, steering, system, telemetry, topology) that the Atlas_Console is entitled to consume.
- **Contract_Fidelity_Suite**: The mechanical checks and generated artifacts that compare the Atlas_Console's typed client/domain schemas against the Backend_Contract and report drift.
- **Coverage_Status**: The observable classification of a Backend_Contract capability's representation in the Atlas_Console: `covered` = a typed client method exists AND a domain Zod schema validates that capability's response; `partial` = a typed client method exists but its response schema is incomplete or the channel is only partially modeled; `uncovered` = no typed client method or domain schema exists for the capability.
- **Feedback_Window**: The upper bound (≤ 1 second) within which the Atlas_Console must present explicit success/failure feedback for a mutating action.
- **Agent_State_Model**: The enumerated, canonical set of observable agent lifecycle/process states the Console can render (extends the existing `AgentProcessState` grammar).
- **AUX_Layer**: The agentic-UX presentation layer that renders Agent_State_Model states, council cognition, confidence, provenance, and honesty markers.
- **Oversight_Controls**: The operator affordances for supervising agency — interrupt, override, steer, delegate, recover, and escalate.
- **Trust_Calibration_Layer**: The surfaces and logic that communicate confidence, calibration (reliability vs. actual outcome), provenance, and uncertainty so an operator's trust matches demonstrated reliability.
- **Chromatic_System**: The OKLCH design-token color system (`design-system/color/`, ADR-025) governing agent identity (Hue), decision tier (Lightness), confidence (diverging OKLab scale), and semantic/state/process-state tokens.
- **Motion_System**: The disciplined motion vocabulary (durations, easings, stagger, urgency-as-frequency) defined by the `--syn-motion-*` / `--syn-ease-*` tokens and their reduced-motion fallbacks.
- **Spatial_Visualization**: The purposeful 2D/3D visualization surfaces — the deck.gl/MapLibre living map and the sigma/graphology supply-network graph.
- **Theme_Mode**: One of the rendering modes the Console supports: `light`, `dark`, and `hc` (high-contrast/forced-colors).
- **Reduced_Motion**: The user/OS preference `prefers-reduced-motion: reduce` (and the Console setting mirroring it).
- **Confidence_Gate**: The I-5 thresholds at confidence 0.70 (low bound) and 0.80 (autonomy bound) that govern autonomous execution vs. HITL escalation.
- **Decision_Tier**: One of the 4 orchestrator tiers (Tier 1 RL-only ≤100ms … Tier 4 LLM+Monte-Carlo 15–120s), ordinal, encoded on the Lightness axis.
- **Degraded_State**: A backend-reported reduced-information/fallback condition (`degraded=true`, brownout shedding, or an open dependency breaker) that must be surfaced, never hidden.
- **Synthetic_Decision**: A decision produced by the traffic generator (order id prefixed `synthetic-`, `is_synthetic=true`), which must be visibly marked and excluded from trust aggregates by default.
- **Operator_Role**: The authenticated role governing capability: `viewer`, `ops`, `engineer`, or `admin`.
- **Operations_Controller**: An `ops`/`admin` operator supervising live agent decisions in Mission Control and the Override Cockpit.
- **Analyst**: An `engineer`/`admin` user investigating decisions, calibration, and the audit trail.
- **On_Call_Responder**: An operator handling escalations and disruptions, often on a constrained device or network.
- **Stakeholder_Viewer**: A `viewer` observing the Demo Theater / live surfaces without mutation rights.
- **Surface**: A top-level Console route/screen (e.g., mission-control, decision-theater, override-cockpit, audit-vault, operations, steering, twin-lab, council-theater, agent-council, live-markets, ingress, auth, demo-theater).
- **Universal_State**: One of the render conditions every data-bearing Surface must define: loading, empty, error, degraded, offline, and populated.
- **Chromatic_Token**: A color value delivered exclusively via a `var(--syn-*)` custom property generated from `design-system/color/tokens/*.tokens.json`; no raw hex/rgb/hsl literal is permitted in `frontend/src/**` (INV-CLR-009).
- **APCA**: Accessible Perceptual Contrast Algorithm; contrast targets are tiered by emphasis (primary Lc 75 / secondary 60 / tertiary 45).
- **Web_Vitals_Budget**: LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1 (FE-INV-010) on the target route/network profile.
- **Entry_Bundle_Budget**: The gzipped size budget enforced by `size-limit` (entry ≤ 180 KB; react-vendor ≤ 70 KB).

---

## Requirements

### Requirement 1: Frontend–Backend Contract Fidelity

**User Story:** As an Analyst maintaining the platform, I want the Console's typed client and domain schemas to provably mirror the backend contract, so that the UI never silently misrepresents or omits a backend capability.

#### Acceptance Criteria

1. WHEN the Contract_Fidelity_Suite runs against the Backend_Contract, THE Contract_Fidelity_Suite SHALL report, for each router in `api/routers/*`, whether every path the Atlas_Console is entitled to consume has a corresponding typed client method.
2. WHEN a Backend_Contract response is received at runtime, THE Atlas_Console SHALL validate the payload against its domain Zod schema before rendering, and IF the payload omits a required field or presents a field whose type mismatches the schema, THEN THE Atlas_Console SHALL surface a typed schema-violation error through the error Universal_State and SHALL NOT render the unvalidated payload; the presence of unknown additive fields SHALL NOT constitute a validation failure (consistent with criterion 4).
3. WHERE the backend publishes an OpenAPI document, THE Contract_Fidelity_Suite SHALL compare the Console's generated types against that document and report every field present in the contract but absent from the Console's schema, and every field the Console requires that is absent from the contract.
4. WHEN a Backend_Contract response includes fields not present in the Console's schema, THE Atlas_Console SHALL preserve forward compatibility by passing through unknown additive fields without raising a validation error.
5. THE Contract_Fidelity_Suite SHALL produce a drift report enumerating every endpoint, WebSocket channel, and SSE stream the Backend_Contract exposes and the Console's Coverage_Status (`covered`, `partial`, or `uncovered`) for each, and SHALL mark any capability the Console is not entitled to consume as out-of-scope so it is not counted as a coverage gap.
6. IF the Contract_Fidelity_Suite detects a Coverage_Status of `uncovered` or `partial` for a capability the Console is entitled to consume, THEN THE Contract_Fidelity_Suite SHALL fail the check with a non-zero exit status and name the specific endpoint or channel; capabilities marked out-of-scope SHALL NOT trigger a failure.

### Requirement 2: Canonical Agent-State Model

**User Story:** As an Operations_Controller supervising autonomous agents, I want every meaningful agent lifecycle state to be an explicit, named, observable state, so that I always know what each agent is doing and no agent activity is invisible.

#### Acceptance Criteria

1. THE Agent_State_Model SHALL define a canonical, CLOSED, enumerated set of agent states covering, at minimum: idle, thinking, searching, planning, acting, streaming, waiting, asking, uncertain, confident, delegating, escalating, interrupting, recovering, failing, succeeding, handing-off, and completing, and every state the AUX_Layer renders SHALL be a member of that set.
2. WHERE the Backend_Contract emits an event that maps to an Agent_State_Model state, THE AUX_Layer SHALL render that state from the recorded event and SHALL NOT fabricate a state that has no backing event.
3. IF the Backend_Contract exposes no event for an Agent_State_Model state, THEN THE Contract_Fidelity_Suite SHALL record that state as a backend gap in the drift report, and THE AUX_Layer SHALL render it as unavailable — carrying an explicit non-color indication of unavailability — rather than inventing activity.
4. WHILE an agent is in any Agent_State_Model state, THE AUX_Layer SHALL communicate that state through at least one non-color channel (text label, icon, shape, or `data-*` attribute) in addition to any chromatic encoding.
5. WHEN an agent's state changes, THE AUX_Layer SHALL reflect the new state within 100 milliseconds of receiving the backing event, and SHALL preserve the agent's frozen identity hue across the transition such that chroma MAY change but hue SHALL NOT.
6. WHILE the live cognition stream is stale (no backing event within 5 seconds), THE AUX_Layer SHALL render the council as not-live through an explicit non-color channel rather than showing a frozen state as active.
7. THE Agent_State_Model SHALL map each state to its existing chroma-rationing factor where one is defined, and THE Agent_State_Model SHALL keep every state's identity chroma factor strictly greater than zero — never chroma-drained to neutral gray — so agent identity hue remains identifiable in every state, including interrupted and failing.

### Requirement 3: Human Oversight and Autonomy Control

**User Story:** As an On_Call_Responder, I want first-class controls to interrupt, override, steer, delegate, recover, and escalate agent activity, so that a human always retains meaningful authority over the autonomous system.

#### Acceptance Criteria

1. WHEN an Operations_Controller submits an override for a decision, THE Atlas_Console SHALL commit the audit row via the audit-row-first endpoint before marking the decision as acted, and THE Atlas_Console SHALL treat the WebSocket acknowledgement as operational confirmation, not as the commit, and IF the audit-row commit fails, THEN THE Atlas_Console SHALL leave the decision un-acted and surface an error.
2. WHILE a decision's confidence is below the Confidence_Gate autonomy bound of 0.80, THE Atlas_Console SHALL demote the Approve action from default keyboard focus and place default focus on Reject or Modify.
3. THE Oversight_Controls SHALL be fully operable by keyboard alone on the Override Cockpit, and each of approve, reject, modify, escalate-to-next, escalate-to-previous, and dismiss-dialog SHALL be reachable and activatable without a pointer.
4. WHEN an escalation carries guardrail violations, THE Atlas_Console SHALL render every violation with its code, message, and severity, and IF a violation's severity is absent, THEN THE Atlas_Console SHALL default the severity to medium rather than hiding the violation.
5. WHEN an escalation carries no guardrail violations, THE Atlas_Console SHALL render an explicit "no violations recorded" indication rather than omitting the violations region.
6. WHERE an operator adjusts steering (Pareto objective weights or per-tier escalation thresholds), THE Atlas_Console SHALL commit the change to the audit trail before applying it locally, and IF the audit commit fails, THEN THE Atlas_Console SHALL revert to the pre-adjustment value and indicate that the change was not applied.
7. WHEN an operator sets a steering value, IF the input is a finite value outside [0, 1], THEN THE Atlas_Console SHALL clamp the value into the range [0, 1], and IF the input is non-finite (NaN, positive infinity, or negative infinity), THEN THE Atlas_Console SHALL collapse the value to 0.
8. WHERE the Backend_Contract exposes an interrupt or recovery affordance for an in-flight agent action, THE Oversight_Controls SHALL expose that affordance to operators holding the `ops`, `engineer`, or `admin` role, and IF no such backend affordance exists, THEN THE Contract_Fidelity_Suite SHALL record it as a backend gap in the drift report.
9. WHILE an operator holds the `viewer` role, THE Atlas_Console SHALL present Oversight_Controls in a disabled, visibly non-actionable state rather than hiding the existence of oversight capability.

### Requirement 4: Trust Calibration and Confidence Communication

**User Story:** As an Analyst, I want the Console to communicate confidence, calibration, provenance, and uncertainty honestly, so that my trust in an agent matches its demonstrated reliability rather than its presentation.

#### Acceptance Criteria

1. THE Atlas_Console SHALL render every decision with its Decision_Tier, its confidence formatted as a value in the range 0.00–1.00 with exactly two decimal places, and a single-activation navigation to the decision's audit row reachable by one pointer click OR one keyboard activation.
2. WHEN confidence is displayed as color, THE Atlas_Console SHALL anchor the confidence color scale's stops exactly at the Confidence_Gate positions (0.00, 0.70, 0.80, 1.00) and SHALL also communicate confidence through a non-color channel that renders the numeric confidence value as text.
3. THE Trust_Calibration_Layer SHALL render decision outcomes as exactly three distinct states — confirmed, diverged, and unknown — and SHALL NOT fold `unknown` (not yet realized / no evidence) into `confirmed`.
4. THE Trust_Calibration_Layer SHALL always disclose sample size, evaluation window, and an "as of" timestamp alongside any calibration or reliability display, and IF the display is backed by fewer than 30 scored outcomes, THEN THE Trust_Calibration_Layer SHALL flag the display as provisional.
5. IF no scored evidence exists for a calibration metric, THEN THE Trust_Calibration_Layer SHALL render "awaiting scored outcomes".
6. IF a calibration metric value is null, THEN THE Trust_Calibration_Layer SHALL render an explicit no-value marker rather than rendering the value as 0.
7. WHERE a decision carries structured provenance (model version, feature source, confidence basis), THE Atlas_Console SHALL render that provenance, and IF a decision's provenance is absent or incomplete, THEN THE Atlas_Console SHALL render an explicit "provenance unavailable" marker rather than omitting provenance silently.
8. WHERE a decision reports `degraded=true`, THE Atlas_Console SHALL render the degraded honesty marker as an explicit text label and SHALL NOT suppress it.
9. THE Trust_Calibration_Layer SHALL exclude Synthetic_Decision records from trust aggregates by default and SHALL expose a labelled control to include them.
10. WHEN the Atlas_Console renders audit-chain integrity for a decision, THE Atlas_Console SHALL render exactly three distinct states — verified, altered, and pre-chain/legacy — and SHALL NOT render a legacy (null) chain state as verified.

### Requirement 5: Chromatic Semantic System

**User Story:** As a user with color-vision differences working in varied lighting, I want color to carry consistent, accessible meaning across light, dark, and high-contrast themes, so that I can interpret agent identity, tier, confidence, and state reliably.

#### Acceptance Criteria

1. THE Atlas_Console SHALL source every color exclusively from a Chromatic_Token and SHALL contain no raw hex, `rgb()`, or `hsl()` color literal in `frontend/src/**` outside generated files.
2. THE Chromatic_System SHALL resolve every semantic token to a concrete, non-empty value in each Theme_Mode (light, dark, and hc), with no unresolved, empty, or `initial` value.
3. IF a semantic token fails to resolve in a Theme_Mode, THEN THE Chromatic_System conformance check SHALL fail and name the specific token and Theme_Mode rather than falling back to a raw color literal.
4. THE Chromatic_System SHALL encode agent identity on Hue, Decision_Tier on Lightness, and confidence on the diverging OKLab scale, and SHALL NOT cross these three encoding axes.
5. THE Chromatic_System SHALL keep the 8 agent→hue assignments frozen, and IF an agent hue assignment changes, THEN the change SHALL require a version bump and an ADR supersede note.
6. THE Atlas_Console SHALL meet WCAG 2.1 AA contrast (≥ 4.5:1 body text, ≥ 3.0:1 large text and UI components) for every text-on-surface and component-on-surface pair in each Theme_Mode.
7. THE Atlas_Console SHALL meet its APCA Lc target per emphasis tier (primary ≥ 75, secondary ≥ 60, tertiary ≥ 45) for every text-on-surface pair in each Theme_Mode.
8. THE Chromatic_System SHALL keep the 8 agent identity colors mutually distinguishable such that all 28 unordered agent-color pairs differ by at least the Chromatic_System's defined minimum pairwise perceptual distance under deuteranopia, protanopia, and tritanopia simulation in each Theme_Mode.
9. THE Chromatic_System SHALL render the Degraded_State with an OKLCH chroma strictly lower than the minimum chroma of every full-saturation semantic state.
10. THE Atlas_Console SHALL never use color as the sole carrier of meaning; every color-coded agent, tier, confidence, or status affordance SHALL also expose a text, icon, or shape signal.
11. THE Chromatic_System SHALL provide defined fallbacks per user preference: WHERE `prefers-contrast` is set, THE Chromatic_System SHALL apply the `hc` token set; WHERE `forced-colors` is active, THE Chromatic_System SHALL defer to system colors while preserving every non-color distinction; and WHILE Reduced_Motion is active, THE Chromatic_System SHALL apply a static, non-animated chroma/lightness swap.

### Requirement 6: Motion as Cognition

**User Story:** As an Operations_Controller, I want motion to explain causality and urgency rather than decorate, and to respect reduced-motion needs, so that animation aids understanding without causing distraction, discomfort, or performance cost.

#### Acceptance Criteria

1. THE Motion_System SHALL express all timing and easing through the defined motion and easing tokens (`--syn-motion-*`, `--syn-ease-*`) and SHALL NOT introduce ad-hoc inline durations or easings in component source.
2. WHILE Reduced_Motion is active, THE Motion_System SHALL zero the motion-duration tokens and THE Atlas_Console SHALL present a static fallback that preserves all information conveyed by the animated state.
3. THE Atlas_Console SHALL never use motion as the sole information channel; every animated state (acting pulse, synthetic pulse, escalation beacon, decision arrival) SHALL retain a static representation carrying the same information.
4. WHEN urgency is encoded through motion, THE Motion_System SHALL encode it as frequency such that the urgent cadence is distinct from the ambient cadence.
5. THE Motion_System SHALL restrict continuously-running animation to a defined minimal set and SHALL NOT animate large layout-affecting properties in a way that risks dropped frames on the target device profile.
6. WHEN content updates arrive as a stream, THE Motion_System SHALL apply entrance/settle motion that communicates arrival and ordering without reflowing already-read content.
7. THE Motion_System SHALL define which elements MUST NOT animate (e.g., text being read, focus targets during keyboard navigation) and THE Atlas_Console SHALL honor those exclusions.

### Requirement 7: Purposeful Spatial and 3D Visualization

**User Story:** As an Analyst investigating supply-chain structure, I want spatial and network visualizations that reveal real structure and load efficiently, so that visualization adds insight without harming performance or accessibility.

#### Acceptance Criteria

1. THE Atlas_Console SHALL load Spatial_Visualization libraries (deck.gl, MapLibre, sigma/graphology, visx) as asynchronous chunks that never appear in the entry bundle.
2. THE Spatial_Visualization map SHALL render only self-hosted PMTiles and SHALL NOT register any remote tile server.
3. WHEN a Spatial_Visualization renders agent, tier, or confidence data, THE Spatial_Visualization SHALL use the same Chromatic_Token encoding as the rest of the Atlas_Console.
4. WHERE a Spatial_Visualization conveys information visually, THE Atlas_Console SHALL provide an equivalent non-spatial representation (table, list, or text summary) reachable by keyboard and screen reader.
5. WHILE a Spatial_Visualization is loading, THE Atlas_Console SHALL render a loading state, and IF the visualization fails to load, THEN THE Atlas_Console SHALL render an error state with a retry affordance rather than a blank canvas.
6. WHEN a long-running simulation (e.g., a Monte Carlo Twin Lab run) is requested, THE Atlas_Console SHALL render progress and SHALL reject a hung run with a typed timeout within the defined SLA window (≤ 120 seconds, matching the Tier 4 Decision_Tier upper bound).

### Requirement 8: World-Class Craft

**User Story:** As any operator, I want layout, typography, information density, and feedback to be deliberate and consistent, so that the Console feels precise and reduces cognitive load under pressure.

#### Acceptance Criteria

1. THE Atlas_Console SHALL render every user-visible string through the i18next catalog and SHALL ship English only (single `en` catalog, `supportedLngs` = `["en"]`, no language switcher, no language detector).
2. THE Atlas_Console SHALL provide a keyboard command surface (command palette) that can reach every primary Surface without a pointer.
3. WHEN an operator performs a mutating action, THE Atlas_Console SHALL provide explicit feedback of success or failure within the Feedback_Window (≤ 1 second) rather than leaving the action's outcome ambiguous.
4. THE Atlas_Console SHALL maintain a consistent typographic and spacing scale across every Surface such that equivalent information roles share equivalent visual treatment.
5. WHERE a Surface presents dense tabular or streaming data, THE Atlas_Console SHALL virtualize rendering so that large datasets do not degrade interaction responsiveness below the Web_Vitals_Budget.
6. THE Atlas_Console SHALL surface the deployed build SHA in the Shell so an operator can distinguish a stale cached UI from a current deploy.

### Requirement 9: Accessibility and Inclusive Design

**User Story:** As a user relying on assistive technology or facing a situational limitation, I want the Console to be perceivable, operable, understandable, and robust, so that I can supervise the system regardless of ability, device, or context.

#### Acceptance Criteria

1. THE Atlas_Console SHALL present zero automated accessibility violations (axe-core) on every route in the smoke matrix and on every Storybook story.
2. THE Atlas_Console SHALL be fully operable by keyboard on every primary Surface, including a visible focus indicator and a logical focus order.
3. WHEN state changes that an operator must notice occur (escalation arrival, degradation, action outcome), THE Atlas_Console SHALL announce them to assistive technology through an appropriate live region.
4. THE Atlas_Console SHALL preserve all conveyed information under `forced-colors` (high-contrast) mode and SHALL meet the contrast requirements of Requirement 5 in that mode.
5. WHERE the Console already provides sonification of agent/decision activity, THE Atlas_Console SHALL keep sonification optional and SHALL NOT make it the sole channel for any information.
6. THE Atlas_Console SHALL respect OS-level user preferences for reduced motion, increased contrast, and color scheme without requiring in-app configuration.
7. WHEN a form input is invalid, THE Atlas_Console SHALL associate a text error message with the input programmatically so assistive technology conveys the error.

### Requirement 10: Universal State Coverage

**User Story:** As an On_Call_Responder on a degraded network, I want every data-bearing surface to handle loading, empty, error, degraded, and offline conditions explicitly, so that I am never shown a blank screen or a false-healthy state.

#### Acceptance Criteria

1. THE Atlas_Console SHALL define, for every data-bearing Surface, a distinct rendering for each Universal_State: loading, empty, error, degraded, offline, and populated.
2. IF a data request fails with a transient error, THEN THE Atlas_Console SHALL retry with Full-Jitter backoff.
3. IF a data request receives a 429 response carrying `Retry-After`, THEN THE Atlas_Console SHALL honor the `Retry-After` delay before retrying.
4. IF a data request fails with a non-retriable 4xx error, THEN THE Atlas_Console SHALL short-circuit without retrying.
5. WHILE the system reports a Degraded_State (brownout shedding or an open dependency breaker), THE Atlas_Console SHALL display a non-dismissible banner above every route naming what is degraded, and IF the posture fetch itself fails, THEN THE Atlas_Console SHALL render "posture unknown" rather than a healthy state.
6. WHEN a real-time connection drops, THE Atlas_Console SHALL reconnect with bounded Full-Jitter backoff and SHALL deduplicate replayed messages by sequence so no message is applied twice and no acted item is reset to pending.
7. WHILE the Console is offline, THE Atlas_Console SHALL indicate the offline condition and SHALL NOT present stale data as live.
8. WHEN a Surface has no data to display, THE Atlas_Console SHALL render an explicit empty state that distinguishes "no data yet" from "failed to load".
9. THE Atlas_Console SHALL surface an SLO burn view that renders both fast and slow burn windows with an explicit severity word, and IF the metrics source is unreachable, THEN THE Atlas_Console SHALL render "burn unknown" rather than a healthy bar or a fabricated 0.

### Requirement 11: Deterministic Decision Replay and Transparency

**User Story:** As an Analyst, I want to replay any recorded decision deterministically and share it by URL, so that investigation and demonstration are reproducible and cannot be fabricated.

#### Acceptance Criteria

1. WHEN a decision is loaded by its decision id, THE Atlas_Console SHALL render it identically on every load, with replay computed as a pure function (no `Date.now`, no `Math.random`, no I/O).
2. THE Atlas_Console SHALL encode the active replay phase in a URL search parameter, validate and clamp it to the valid phase range, and fall back to the decision's terminal phase when the parameter is absent or invalid.
3. WHILE replaying a decision, THE Atlas_Console SHALL gate per-tier tool visibility such that lower tiers show only RL tools and higher tiers show the full toolset, consistent with the recorded phase.
4. WHEN the Council Theater reconstructs a decision, THE Atlas_Console SHALL render only recorded phases and SHALL NOT fabricate deliberation that has no backing record.
5. THE Atlas_Console SHALL render the audit export with decision-safe fields only (audit id, decision id, tier, confidence, city, created-at, escalated) and SHALL NOT include personally identifying operator data.

### Requirement 12: Security, Identity, and Privacy

**User Story:** As a platform owner, I want the Console to protect operator identity, enforce role scope, and avoid data leakage, so that the command center is trustworthy and compliant.

#### Acceptance Criteria

1. THE Atlas_Console SHALL never render raw operator usernames and SHALL render operator identity only as a Vault token reference, and only while authenticated.
2. WHEN a request returns 401, THE Atlas_Console SHALL attempt a single-flight token refresh and replay in-flight requests on success, and IF refresh fails or a second 401 occurs, THEN THE Atlas_Console SHALL clear the session and route to the login screen without a full page reload.
3. THE Atlas_Console SHALL enforce a strict Content Security Policy in production and SHALL NOT use `dangerouslySetInnerHTML` in component source.
4. THE Atlas_Console SHALL serialize every outbound payload as canonical JSON (sorted keys, no insignificant whitespace, dropped undefined fields).
5. WHERE a Surface or action is outside the authenticated Operator_Role's scope, THE Atlas_Console SHALL prevent the action and SHALL communicate the restriction rather than failing silently.

### Requirement 13: Performance and Resource Budgets

**User Story:** As an operator on a modest device or network, I want the Console to load and respond within defined budgets, so that supervision is fast under real conditions.

#### Acceptance Criteria

1. THE Atlas_Console SHALL keep the entry bundle within the Entry_Bundle_Budget (entry ≤ 180 KB gzip, react-vendor ≤ 70 KB gzip).
2. THE Atlas_Console SHALL meet the Web_Vitals_Budget (LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1) on the target route under the defined network profile.
3. THE Atlas_Console SHALL load heavy visualization libraries only on demand via lazy boundaries and SHALL NOT block first paint on them.
4. WHEN the active city changes, THE Atlas_Console SHALL carry the city discriminator on every metric query key and SHALL invalidate stale city data cleanly.
5. THE Atlas_Console SHALL emit Web Vitals beacons through the batched telemetry helper using `navigator.sendBeacon` so measurement does not block interaction.

### Requirement 14: UI Self-Observability

**User Story:** As an Analyst diagnosing UI issues, I want the Console to report its own health and key events, so that frontend problems are observable rather than invisible.

#### Acceptance Criteria

1. THE Atlas_Console SHALL emit Web Vitals (CLS, INP, LCP) to the telemetry endpoint, which whitelists fields before forwarding.
2. WHEN a domain schema validation fails at runtime, THE Atlas_Console SHALL record the failure as a structured, field-whitelisted telemetry event rather than only logging to the console.
3. WHEN an unhandled render error occurs, THE Atlas_Console SHALL catch it at an error boundary, render a recovery affordance, and SHALL NOT leave the operator on a blank screen.
4. THE Atlas_Console SHALL expose the deployed build SHA both in the Shell and via the backend `/version` endpoint so a stale UI is diagnosable.

### Requirement 15: Governance Conformance and Test Culture

**User Story:** As a maintainer, I want every elevation guarantee to be mechanically enforced and every invariant to have a test, so that the Console's standard cannot silently regress.

#### Acceptance Criteria

1. THE Atlas_Console SHALL introduce no dependency that is paid, or licensed GPL-3.0/AGPL-3.0, and SHALL make zero calls to paid SaaS providers.
2. THE Atlas_Console SHALL pass `tsc --noEmit` under strict type settings with no type errors.
3. WHERE this feature introduces a frontend invariant, THE feature SHALL register it in `frontend/spec/fe_invariants.yaml` (or the color spec for chromatic invariants) with a corresponding implementation and test, and THE invariant-coverage check SHALL fail if any invariant lacks a test.
4. WHERE this feature introduces or changes a color token, THE feature SHALL author it in OKLCH in the DTCG token source, regenerate the deterministic `dist/` artifacts, and commit them.
5. THE Atlas_Console SHALL keep mutation survival below the defined threshold on the critical modules covered by Stryker.
6. THE Atlas_Console SHALL NOT reintroduce any non-English locale catalog, language switcher, or language detector.
