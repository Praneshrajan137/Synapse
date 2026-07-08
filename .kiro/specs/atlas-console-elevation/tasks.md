# Implementation Plan: Atlas Console Elevation

## Overview

This plan converts the Atlas Console Elevation design into incremental, test-driven coding steps for the existing `frontend/` (React 18 + Vite + TypeScript, package `synapse-console`). The work is **additive and invariant-governed**: no re-architecture, every new guarantee lands in the existing `transport → domain → lib → state → hooks → design-system → surfaces` layering and is registered as a `FE-INV-*` / `INV-CLR-*` invariant with a test.

Implementation language is **TypeScript**. Property-based tests use **fast-check + Vitest** (already in the stack), each carrying the tag `Feature: atlas-console-elevation, Property {number}: {property_text}` and running `numRuns: 100` minimum. Color properties (20–26) live in the `design-system/color` suite as `INV-CLR-*` tests; frontend logic properties live under `frontend/src/**/__tests__`.

Tasks are ordered so pure logic lands before the surfaces that consume it, and each step wires into the previous one so no code is orphaned. Test sub-tasks marked `*` are optional and can be skipped for a faster MVP.

## Tasks

- [x] 1. Contract Fidelity foundations — data models and coverage classifier
  - [x] 1.1 Define contract-fidelity data models
    - Create `frontend/spec/contract-fidelity/types.ts` with `CapabilityKind`, `CoverageStatus`, `CapabilityEntitlement`, `ConsoleCapability`, `CoverageRow`, `DriftReport` exactly as in the design Data Models section
    - _Requirements: 1.1, 1.5_

  - [x] 1.2 Implement `classifyCoverage` pure coverage classifier
    - Create `frontend/src/lib/contract-coverage.ts` exporting a pure `classifyCoverage(entitlement, consoleCapability)` that returns `covered` (client method AND complete schema), `partial` (method but incomplete schema or partially-modeled channel), `uncovered` (neither), and `out-of-scope` (entitled=false)
    - Implement `diffContractFields(contractFields, schemaFields)` returning `missingFields = contract − schema` and `overStrictFields = schemaRequired − contract`
    - Implement `computeDriftFailure(rows)` returning `failed = true` iff some entitled row is `uncovered` or `partial`; out-of-scope rows never affect the result
    - _Requirements: 1.1, 1.3, 1.5, 1.6_

  - [x] 1.3 Write property test for coverage classification soundness
    - **Property 1: Coverage classification soundness** — exactly one status per capability; missing-both → uncovered, missing-schema → partial, both → covered
    - **Validates: Requirements 1.1**
    - Place in `frontend/src/lib/__tests__/contract-coverage.property.test.ts`

  - [x] 1.4 Write property test for drift failure predicate
    - **Property 2: Drift failure is exactly the entitled-gap predicate** — `failed` true iff some entitled row is uncovered/partial; out-of-scope rows never change the result
    - **Validates: Requirements 1.5, 1.6**

  - [x] 1.5 Write property test for contract field diff
    - **Property 3: Contract field diff is a set difference** — `missingFields = contract − schema`, `overStrictFields = schemaRequired − contract`
    - **Validates: Requirements 1.3**

- [x] 2. Contract Fidelity Suite harness
  - [x] 2.1 Author the entitlement manifest and channel catalog
    - Create `frontend/spec/contract-fidelity/entitlements.ts` listing every backend capability the Console is entitled to consume across `api/routers/*` (agents, auth, decisions, escalations, firehose, metrics, orders, steering, system, telemetry, topology) with `{ router, method, ref, capabilityId, kind, entitled }`; mark non-consumed capabilities `entitled: false`
    - Create `frontend/spec/contract-fidelity/channels.ts` cataloging WebSocket channels and SSE streams mirrored against `firehose` / `ws-multiplex` channel constants
    - _Requirements: 1.5, 1.6_

  - [x] 2.2 Introspect the console surface and backend contract
    - Add client-method registry introspection from `transport/synapse-api.ts` and domain Zod schema registry from `domain/index.ts` (keyed by `schemaId`)
    - Load the backend contract from the published OpenAPI document (`/openapi.json`) with a checked-in snapshot fallback
    - _Requirements: 1.1, 1.3_

  - [x] 2.3 Generate the drift report and wire the CI check
    - Create `frontend/spec/contract-fidelity/run.ts` that composes entitlements + console surface + contract through `classifyCoverage`/`diffContractFields`, writes `drift-report.json` plus a human-readable summary enumerating every HTTP endpoint, WS channel, and SSE stream with its `Coverage_Status`, missing-field/over-strict drift, and backend gaps (agent-state, oversight)
    - Exit non-zero naming the specific endpoint/channel when any entitled capability is uncovered/partial; out-of-scope never fails
    - Add an npm script and extend `.github/workflows/frontend.yml` to run it
    - _Requirements: 1.1, 1.3, 1.5, 1.6, 2.3, 3.8_

- [x] 3. Runtime schema boundary hardening
  - [x] 3.1 Enforce forward-compatible, fail-closed schema parsing
    - Audit `frontend/src/domain/*` response schemas to use Zod `.passthrough()` (never `.strict()`) so unknown additive fields pass through; keep request/auth schemas `.strict()`
    - Confirm `transport/http-client.ts` `parseWithSchema` throws a typed `SchemaViolationError`, routes to the `error` Universal_State, never renders the unvalidated payload, and emits a field-whitelisted telemetry event
    - _Requirements: 1.2, 1.4, 14.2_

  - [x] 3.2 Write property test for the schema boundary
    - **Property 4: Schema boundary is fail-closed and forward-compatible** — valid payload + arbitrary disjoint extra keys parses and preserves known fields; missing-required or type-mismatched field raises `SchemaViolationError` with no rendered value
    - **Validates: Requirements 1.2, 1.4**

- [x] 4. Canonical Agent-State Model
  - [x] 4.1 Define the closed Agent-State union and descriptors
    - Create `frontend/src/domain/agent-state.ts` with `AGENT_STATES` const tuple (all 18 states), `AgentState` type, closed `AgentStateSchema = z.enum(...)`, `AgentStateDescriptor` (label, glyph, chromaFactor > 0, `data-agent-state:*` attr), and `RenderableAgentState` union (`live` | `unavailable` | `not-live`)
    - Author the per-state chroma-rationing factor mapping reusing `AGENT_STATE_FACTOR` where defined and assigning new states factors strictly `> 0` (interrupt floor 0.25) in the color token source, not invented in TS
    - _Requirements: 2.1, 2.4, 2.7_

  - [x] 4.2 Implement `deriveAgentState` pure derivation
    - Create `frontend/src/lib/agent-state.ts` exporting `deriveAgentState(events, agent, nowMs, staleMs = 5000): RenderableAgentState` extending `deriveLiveCognition`: map recorded cognition events to a state member, return `not-live` when no backing event within `staleMs`, return `unavailable` for a state with no backing event, and never fabricate activity
    - _Requirements: 2.2, 2.3, 2.5, 2.6_

  - [x] 4.3 Write property test for agent-state closedness
    - **Property 5: Agent-state enumeration is closed** — `AgentStateSchema` parses iff the string is a member of `AGENT_STATES`, and every AUX-produced state is a member
    - **Validates: Requirements 2.1**

  - [x] 4.4 Write property test for honest derivation
    - **Property 6: Agent-state derivation is honest** — `live` only with a backing event; `not-live` when newest backing event exceeds the staleness window; never a fabricated active state
    - **Validates: Requirements 2.2, 2.3, 2.6**

  - [x] 4.5 Write property test for non-color channel and non-zero chroma
    - **Property 7: Every rendered agent state carries a non-color channel and non-zero identity chroma** — descriptor exposes non-empty label + glyph + `data-agent-state` attr and chromaFactor strictly `> 0`
    - **Validates: Requirements 2.4, 2.7**

- [x] 5. AUX Layer — AgentStatePresenter
  - [x] 5.1 Implement the AgentStatePresenter compound
    - Create `frontend/src/design-system/compounds/AgentStatePresenter.tsx` rendering a `RenderableAgentState`: frozen identity hue (chroma may change, hue never), a non-color channel (status word + `data-agent-state` attr + icon/shape), and explicit `unavailable`/`not-live` markers via a non-color channel
    - Reflect a state change within 100ms of the backing event; render the council as not-live via a non-color channel when the stream is stale > 5s
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 5.2 Write property test for frozen identity hue across transitions
    - **Property 8: State transitions preserve frozen identity hue** — for any agent and any pair of process states, rendered identity colors share the frozen hue coordinate (|Δhue| < 2°) and differ only in chroma
    - **Validates: Requirements 2.5**

- [x] 6. Checkpoint — foundations and AUX
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Oversight Controls
  - [x] 7.1 Implement oversight pure predicates
    - Create/extend `frontend/src/lib` helpers: `defaultFocusAction(confidence)` returning `reject`/`modify` when `< 0.80` else `approve`; `clampSteering(x)` clamping finite values to `[0,1]` and collapsing non-finite (NaN/±∞) to `0`; `isCapabilityActionable(role, capability)` (backing endpoint required; role within required-role set; out-of-scope → present-but-disabled)
    - _Requirements: 3.2, 3.7, 3.8, 3.9, 12.5_

  - [x] 7.2 Implement the OversightControls compound with audit-row-first commits
    - Create `frontend/src/design-system/compounds/OversightControls.tsx` rendering interrupt, override (approve/reject/modify), steer, delegate, recover, escalate-next/prev, dismiss; reuse the audit-row-first override mutation and `useCockpitShortcuts`
    - Commit the audit row before local apply for override and steering; on audit-commit failure leave the decision un-acted / revert the steering value and surface an error; treat the WS ack as operational confirmation only
    - Full keyboard operability for every action; `viewer` sees controls disabled and visibly non-actionable (never hidden); expose interrupt/recover to `ops`/`engineer`/`admin` where a backing endpoint exists
    - _Requirements: 3.1, 3.2, 3.3, 3.6, 3.8, 3.9, 12.5_

  - [x] 7.3 Write property test for sub-threshold focus demotion
    - **Property 9: Sub-threshold confidence demotes Approve from default focus** — `defaultFocusAction` returns reject/modify below 0.80, approve only at or above 0.80
    - **Validates: Requirements 3.2**

  - [x] 7.4 Write property test for authorization and visibility predicate
    - **Property 10: Authorization and visibility predicate** — no backing endpoint → backend gap and never actionable; backed capability actionable iff role in required set; out-of-scope → present-but-disabled with communicated restriction, never hidden, never silently allowed
    - **Validates: Requirements 3.8, 3.9, 12.5**

  - [x] 7.5 Write property test for steering clamp and sanitization
    - **Property 11: Steering values are clamped and sanitized** — finite in-range preserved, finite out-of-range clamped to nearest bound, non-finite collapses to 0
    - **Validates: Requirements 3.7**

  - [x] 7.6 Write unit tests for audit-row-first ordering and keyboard operability
    - Cover audit-commit-before-apply for override and steering, revert-on-failure, WS-ack-is-not-commit, and full keyboard reachability of each oversight action
    - _Requirements: 3.1, 3.3, 3.6_

- [x] 8. Guardrail violation rendering
  - [x] 8.1 Implement `normalizeViolations` and extend EscalationCard
    - Add `normalizeViolations(violations)` (pure) preserving count, giving every row a code/message/severity, defaulting a missing severity to `medium`, never dropping a violation
    - Extend `EscalationCard` to render every violation with code/message/severity and an explicit "no violations recorded" region when the list is empty (never omitted)
    - _Requirements: 3.4, 3.5_

  - [x] 8.2 Write property test for guardrail violation normalization
    - **Property 12: Guardrail violations render completely with severity** — preserves count, every row has code/message/severity, missing severity defaults to `medium`, never dropped or collapsed
    - **Validates: Requirements 3.4**

  - [x] 8.3 Write unit test for empty-violations copy
    - Assert the explicit "no violations recorded" region renders for an empty list
    - _Requirements: 3.5_

- [x] 9. Trust Calibration Layer
  - [x] 9.1 Implement confidence, outcome, and chain-integrity pure helpers
    - In `frontend/src/surfaces/operations/logic.ts` (extending `confidence.ts`): `formatConfidence(x)` producing exactly two decimals matching `^[01]\.\d{2}$`; anchor `confidenceColor` stops at `{0.00, 0.70, 0.80, 1.00}`; `outcomeMix` yielding exactly `confirmed | diverged | unknown` (confirmed clamped to scored total, `unknown` never folded into confirmed); `chainIntegrity(chain_verified)` mapping true→verified, false→altered, null→pre-chain/legacy (null never verified)
    - _Requirements: 4.1, 4.2, 4.3, 4.10_

  - [x] 9.2 Implement calibration disclosure, provenance, degraded, and synthetic segmentation
    - Calibration displays always disclose sample size, window, and "as of" timestamp; flag provisional when `< 30` scored outcomes; render "awaiting scored outcomes" with no evidence; render an explicit no-value marker ("—") for a null metric (never `0`)
    - `ProvenanceChip` renders model version/feature source/confidence basis when present; absent/incomplete → explicit "provenance unavailable"
    - Render an explicit degraded text label when `degraded=true` (never suppressed); exclude synthetic decisions from trust aggregates by default with a labelled include toggle
    - _Requirements: 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

  - [x] 9.3 Wire decision presentation with single-activation audit navigation
    - Render every decision with its Decision_Tier, two-decimal confidence, numeric confidence as text, and a single-activation audit-row link reachable by one pointer click OR one keyboard activation
    - _Requirements: 4.1, 4.2_

  - [x] 9.4 Write property test for decision confidence formatting and gate-anchored color
    - **Property 13: Decisions carry two-decimal confidence, a gate-anchored color, and numeric text** — output contains tier, confidence matching `^[01]\.\d{2}$`, numeric text; color stops sit exactly at {0.00, 0.70, 0.80, 1.00}
    - **Validates: Requirements 4.1, 4.2**

  - [x] 9.5 Write property test for tri-state outcome partition
    - **Property 14: Decision outcomes partition into a tri-state** — exactly three non-overlapping buckets; confirmed clamped to scored total; unknown counted distinctly, never folded into confirmed
    - **Validates: Requirements 4.3**

  - [x] 9.6 Write property test for calibration statistical power and null handling
    - **Property 15: Calibration discloses statistical power and never renders null as zero** — provisional iff `n < 30`; always discloses sample size/window/as-of; null → no-value marker, numeric 0 → "0"
    - **Validates: Requirements 4.4, 4.6**

  - [x] 9.7 Write property test for provenance rendering
    - **Property 16: Provenance is rendered when present, marked unavailable otherwise** — complete provenance rendered in full; absent/incomplete → explicit "provenance unavailable"
    - **Validates: Requirements 4.7**

  - [x] 9.8 Write property test for degraded honesty marker
    - **Property 17: Degraded honesty marker is never suppressed** — `degraded=true` always yields an explicit degraded text label
    - **Validates: Requirements 4.8**

  - [x] 9.9 Write property test for synthetic exclusion
    - **Property 18: Synthetic decisions are excluded from trust aggregates by default** — default aggregate excludes every `is_synthetic` record; the labelled toggle adds exactly those records
    - **Validates: Requirements 4.9**

  - [x] 9.10 Write property test for chain-integrity tri-state
    - **Property 19: Audit-chain integrity is an exhaustive tri-state** — exactly one of verified/altered/pre-chain-legacy; null never maps to verified
    - **Validates: Requirements 4.10**

- [x] 10. Checkpoint — oversight and trust
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Chromatic System conformance
  - [x] 11.1 Extend chromatics helpers and author any new process-state tokens
    - Ensure `frontend/src/lib/chromatics.ts` exposes `confidenceColor`, `processStateColor`, `rationedAgentColor`, `degradedStateColor`, `syntheticStateColor`; author any new process-state token in OKLCH in the DTCG source and regenerate `design-system/color/dist/` artifacts (frozen hues untouched)
    - _Requirements: 5.1, 5.4, 5.5, 5.9, 15.4_

  - [x] 11.2 Write property test for token resolution across themes
    - **Property 20: Every semantic token resolves in every theme** — every semantic token resolves to a concrete non-empty value in light/dark/hc; unresolved token fails the check naming token + theme, never a raw literal
    - **Validates: Requirements 5.2, 5.3**
    - Place in the `design-system/color` suite as an `INV-CLR-*` test

  - [x] 11.3 Write property test for tier/confidence monotonicity
    - **Property 21: Tier lightness and confidence hue are monotonic** — L(tier1) > L(tier2) > L(tier3) > L(tier4); increasing confidence yields non-decreasing OKLCH hue on the diverging scale
    - **Validates: Requirements 5.4**

  - [x] 11.4 Write property test for WCAG AA contrast
    - **Property 22: WCAG AA contrast holds for every pair in every theme** — ≥ 4.5:1 body text, ≥ 3.0:1 large text and UI components for every text/component-on-surface pair in each theme
    - **Validates: Requirements 5.6**

  - [x] 11.5 Write property test for APCA Lc targets
    - **Property 23: APCA Lc target holds for every text pair in every theme** — absolute APCA Lc meets emphasis-tier target (primary ≥ 75, secondary ≥ 60, tertiary ≥ 45)
    - **Validates: Requirements 5.7**

  - [x] 11.6 Write property test for CVD distinctness
    - **Property 24: Agent identities stay distinguishable under color-vision deficiency** — all 28 agent-color pairs differ by at least the minimum ΔE-OK under deuteranopia/protanopia/tritanopia in each theme
    - **Validates: Requirements 5.8**

  - [x] 11.7 Write property test for degraded chroma floor
    - **Property 25: Degraded chroma is below every full-saturation state** — degraded chroma ≤ `degraded_max_chroma` and ≥ `degraded_min_chroma_gap` below the min chroma of every full-saturation semantic state
    - **Validates: Requirements 5.9**

  - [x] 11.8 Write property test for color-is-never-sole-channel
    - **Property 26: Color is never the sole information channel** — every color-coded affordance also carries a text/icon/shape signal
    - **Validates: Requirements 5.10**

- [x] 12. Motion System
  - [x] 12.1 Enforce token-only motion with static fallbacks
    - Ensure all timing/easing use `--syn-motion-*` / `--syn-ease-*` tokens with no inline durations/easings in component source; reduced-motion zeroes duration tokens; every animated state (acting pulse, synthetic pulse, escalation beacon, decision arrival) keeps a static representation (status word + `data-*`); urgency encoded as frequency (urgent cadence = half ambient); declare and honor the no-animate exclusion set (text being read, focus targets during keyboard nav)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 12.2 Write property test for motion-is-never-sole-channel
    - **Property 27: Motion is never the sole information channel** — every animated state has a static representation that still conveys the full state under `prefers-reduced-motion`
    - **Validates: Requirements 6.2, 6.3**

- [x] 13. Universal State coverage, degraded banner, SLO burn, and reconnect dedup
  - [x] 13.1 Implement the universal-state resolver
    - Create `frontend/src/lib/universal-state.ts` with `UniversalState`, `UniversalStateInput`, and `resolveUniversalState(i)` as a total function over the priority order offline > error > degraded > loading > empty > populated (every input maps to exactly one state)
    - _Requirements: 10.1, 10.8_

  - [x] 13.2 Wire universal states into every data-bearing surface
    - Route each data-bearing surface through `resolveUniversalState`, rendering a distinct view for loading/empty/error/degraded/offline/populated and distinguishing "no data yet" from "failed to load"
    - _Requirements: 10.1, 10.7, 10.8_

  - [x] 13.3 Implement degraded posture banner and SLO burn honesty
    - Mount `DegradedBanner` above every route naming what is degraded (brownout shedding / open breaker); render "posture unknown" when the posture fetch fails (never healthy)
    - Render the SLO burn board with both fast and slow windows and an explicit severity word; render "burn unknown" when the metrics source is unreachable or a window is null (never a healthy bar or fabricated 0)
    - _Requirements: 10.5, 10.9_

  - [x] 13.4 Harden retry policy and real-time reconnect dedup
    - Confirm `jitter-retry.ts` `decideRetry` retries transient (5xx/network) with Full-Jitter bounded by the exponential cap, honors `Retry-After` on 429, and short-circuits on non-429 4xx
    - Confirm the WS multiplex reconnects with bounded Full-Jitter and deduplicates replayed messages by sequence so no message applies twice and no acted item resets to pending
    - _Requirements: 10.2, 10.3, 10.4, 10.6_

  - [x] 13.5 Write property test for universal-state totality
    - **Property 30: Universal-state resolution is total and distinct** — exactly one of six states under fixed priority; empty/error/offline mutually distinct
    - **Validates: Requirements 10.1**

  - [x] 13.6 Write property test for retry policy
    - **Property 31: Retry policy is correct across failure classes** — Full-Jitter retry on transient bounded by cap; `Retry-After` honored on 429; short-circuit on non-429 4xx
    - **Validates: Requirements 10.2, 10.3, 10.4**

  - [x] 13.7 Write property test for degraded posture honesty
    - **Property 32: Degraded posture is honest and never false-healthy** — banner names what is degraded on brownout/open breaker; posture-fetch failure derives "posture unknown", never healthy
    - **Validates: Requirements 10.5**

  - [x] 13.8 Write property test for at-most-once message application
    - **Property 33: Replayed real-time messages apply at most once** — each sequence number applied at most once; an acted entry never reset to pending
    - **Validates: Requirements 10.6**

  - [x] 13.9 Write property test for SLO burn honesty
    - **Property 34: SLO burn is honest and never false-healthy** — both windows render with a severity word; unknown source or null window → "burn unknown", never healthy or fabricated 0
    - **Validates: Requirements 10.9**

- [x] 14. Checkpoint — chromatic, motion, universal state
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Deterministic Decision Replay and Transparency
  - [x] 15.1 Harden replay purity, phase parameter, tool gating, and council reconstruction
    - Ensure `replay.ts` `replayDecision` is referentially transparent (no `Date.now`, no `Math.random`, no I/O) so a decision renders identically per load
    - Encode the active phase in a URL search param, validate/clamp to `[1, 5]`, fall back to the decision's terminal phase when absent/invalid
    - Gate per-tier tool visibility (tiers 1–2 show only `rl_*` tools, tier ≥ 3 may show the full toolset), consistent with the recorded phase
    - Reconstruct only recorded phases in the Council Theater ("no debate — fast path" for zero-debate, empty-front state for null Pareto front), never fabricating a transcript
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 15.2 Implement decision-safe audit export
    - Ensure the audit export emits exactly the decision-safe field set (audit id, decision id, tier, confidence, city, created-at, escalated) with no operator PII
    - _Requirements: 11.5_

  - [x] 15.3 Write property test for replay referential transparency
    - **Property 35: Decision replay is referentially transparent** — two `replayDecision` invocations produce deeply-equal slices
    - **Validates: Requirements 11.1**

  - [x] 15.4 Write property test for replay phase parameter
    - **Property 36: Replay phase parameter is validated, clamped, and falls back** — parsed phase within [1, 5]; valid preserved; absent/invalid falls back to terminal phase
    - **Validates: Requirements 11.2**

  - [x] 15.5 Write property test for tier tool-visibility gating
    - **Property 37: Tool visibility is gated by tier consistent with the recorded phase** — only `rl_*` tools for tiers 1–2; full toolset allowed for tier ≥ 3
    - **Validates: Requirements 11.3**

  - [x] 15.6 Write property test for council reconstruction fidelity
    - **Property 38: Council reconstruction never fabricates deliberation** — reconstructed phases are a subset of recorded phases; zero-debate and null-front render explicit empty states
    - **Validates: Requirements 11.4**

  - [x] 15.7 Write property test for decision-safe audit export
    - **Property 39: Audit export contains decision-safe fields only** — exported keys are exactly the decision-safe set, no operator PII
    - **Validates: Requirements 11.5**

- [x] 16. Security, Identity, Privacy, and Self-Observability
  - [x] 16.1 Enforce operator-identity, canonical JSON, 401 refresh, and CSP
    - Render operator identity only as a Vault token reference while authenticated (never a raw username, empty when unauthenticated)
    - Serialize every outbound payload via `canonicalJson` (sorted keys, no insignificant whitespace, dropped `undefined`)
    - Single-flight 401 refresh with in-flight replay; on failure or a second 401 clear the session and route to `/login` without a full reload
    - Enforce strict production CSP and no `dangerouslySetInnerHTML` in component source
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [x] 16.2 Implement telemetry whitelisting, error boundary, city query keys, and build SHA
    - Emit Web Vitals (CLS/INP/LCP) through the batched telemetry helper via `navigator.sendBeacon`; whitelist fields before forwarding; record schema-violation and render-boundary errors as field-whitelisted telemetry events
    - Add a render error boundary that shows a recovery affordance (never a blank screen)
    - Carry the active city discriminator on every metric query key so switching cities invalidates stale data cleanly
    - Surface the deployed build SHA in the Shell and via `/version`
    - _Requirements: 8.6, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4_

  - [x] 16.3 Write property test for operator identity
    - **Property 40: Operator identity is never a raw username** — rendered identity is a Vault token reference, empty when unauthenticated
    - **Validates: Requirements 12.1**

  - [x] 16.4 Write property test for canonical JSON
    - **Property 41: Outbound payloads are canonical JSON** — sorted keys, no insignificant whitespace, dropped `undefined`, idempotent
    - **Validates: Requirements 12.4**

  - [x] 16.5 Write property test for city query keys
    - **Property 42: Every metric query key carries the active city** — constructed query key includes the active city discriminator
    - **Validates: Requirements 13.4**

  - [x] 16.6 Write property test for telemetry whitelisting
    - **Property 43: Telemetry payloads are field-whitelisted** — forwarded payload contains only whitelisted fields
    - **Validates: Requirements 14.1**

  - [x] 16.7 Write unit tests for 401 refresh flow, error boundary, and build-SHA presence
    - Cover single-flight refresh + replay, clear-and-route on failure/second 401, error-boundary recovery affordance, and build-SHA visibility in the Shell
    - _Requirements: 12.2, 14.3, 8.6, 14.4_

- [x] 17. Craft, Command Palette, and Accessibility
  - [x] 17.1 Implement the command palette and craft consistency
    - Provide a keyboard command palette that reaches every primary Surface without a pointer; route every user-visible string through the i18next `en` catalog (no switcher/detector); maintain consistent typographic/spacing scale; virtualize dense tabular/streaming surfaces to stay within the Web_Vitals_Budget; provide explicit success/failure feedback for mutating actions within the Feedback_Window (≤ 1s)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 17.2 Implement accessibility affordances
    - Ensure keyboard operability with visible focus and logical focus order on every primary Surface; announce must-notice state changes (escalation arrival, degradation, action outcome) via live regions; keep sonification optional and never sole-channel; respect OS reduced-motion/contrast/color-scheme preferences; associate text error messages with invalid inputs via `aria-describedby`/`aria-invalid`; preserve all information under `forced-colors`
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [x] 17.3 Write property test for command-palette route coverage
    - **Property 28: The command palette reaches every primary Surface** — every primary Surface in the route registry has a keyboard-activatable palette entry
    - **Validates: Requirements 8.2**

  - [x] 17.4 Write property test for form-error programmatic association
    - **Property 29: Invalid form input is programmatically associated with its error** — invalid field marked invalid and associated (`aria-describedby`/`aria-invalid`) with a text error message
    - **Validates: Requirements 9.7**

  - [x] 17.5 Write unit tests for live-region announcements and feedback window
    - Cover live-region announcement of escalation/degradation/action outcome and success/failure feedback within ≤ 1s
    - _Requirements: 9.3, 8.3_

- [x] 18. Spatial and 3D Visualization
  - [x] 18.1 Enforce async-chunk loading, PMTiles-only, and shared chromatics
    - Load deck.gl / MapLibre / sigma / graphology / visx as async chunks only (never in the entry bundle); render only self-hosted PMTiles (no remote tile server); use the same Chromatic_Token encoding as the rest of the Console
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 18.2 Implement non-spatial equivalents, load/error states, and Twin Lab timeout
    - Provide a keyboard/SR-reachable non-spatial equivalent (table/list/summary) for every spatial surface; render a loading state and an error state with a retry affordance on load failure (never a blank canvas); render progress for long-running Twin Lab runs and reject a hung run with a typed timeout within the ≤ 120s SLA
    - _Requirements: 7.4, 7.5, 7.6_

- [x] 19. Governance conformance and integration/smoke suite
  - [x] 19.1 Register invariants and extend mutation coverage
    - Register new `FE-INV-*` / `INV-CLR-*` entries in `frontend/spec/fe_invariants.yaml` / `design-system/color/color-system.spec.yml` binding each new capability (Contract Fidelity Suite + coverage classifier, canonical Agent-State Model, universal-state resolver, oversight authorization predicate, command-palette route coverage) to an implementation and a test; ensure `check_fe_invariants.py` fails on any gap
    - Extend the Stryker critical-module set to include `contract-coverage.ts`, `agent-state.ts`, `universal-state.ts` alongside existing modules, keeping mutation survival below threshold
    - _Requirements: 15.3, 15.4, 15.5_

  - [x] 19.2 Wire integration/smoke conformance checks
    - Add/confirm CI checks: axe-core zero-violations across the route matrix and Storybook (9.1); bundle-size budgets (13.1, 13.3); no-raw-color-literal (5.1); no inline motion (6.1); self-hosted-PMTiles-only (7.2); CSP + no `dangerouslySetInnerHTML` (12.3); license/egress audit (15.1); `tsc --noEmit` strict (15.2); deterministic token build (15.4); English-only conformance (8.1, 15.6)
    - _Requirements: 5.1, 6.1, 7.2, 8.1, 9.1, 12.3, 13.1, 13.3, 15.1, 15.2, 15.4, 15.6_

- [x] 20. Final checkpoint — full suite green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (unit, property, and integration tests) and can be skipped for a faster MVP; core implementation tasks are never optional.
- Each task references specific requirement sub-clauses for traceability, and each property sub-task references a numbered property from the design's Correctness Properties section.
- Property-based tests use fast-check + Vitest at `numRuns: 100` minimum, tagged `Feature: atlas-console-elevation, Property {number}: {property_text}`.
- Color properties (20–26) live in the `design-system/color` suite as `INV-CLR-*` tests; all other logic properties live under `frontend/src/**/__tests__`.
- Checkpoints ensure incremental validation at natural boundaries; the elevation is additive and must keep the existing invariant-coverage, type-safety, and $0-cost governance gates green throughout.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.1", "4.1", "11.1", "12.1", "13.1", "15.1", "16.1"] },
    { "id": 2, "tasks": ["1.3", "1.4", "1.5", "2.3", "3.2", "4.2", "4.3", "4.4", "4.5", "7.1", "8.1", "9.1", "11.2", "11.3", "11.4", "11.5", "11.6", "11.7", "11.8", "13.2", "13.3", "13.4", "15.2", "16.2", "18.1"] },
    { "id": 3, "tasks": ["5.1", "7.2", "8.2", "8.3", "9.2", "9.3", "12.2", "13.5", "13.6", "13.7", "13.8", "13.9", "15.3", "15.4", "15.5", "15.6", "15.7", "16.3", "16.4", "16.5", "16.6", "16.7", "17.1", "17.2", "18.2"] },
    { "id": 4, "tasks": ["5.2", "7.3", "7.4", "7.5", "7.6", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9", "9.10", "17.3", "17.4", "17.5", "19.1"] },
    { "id": 5, "tasks": ["19.2"] }
  ]
}
```
