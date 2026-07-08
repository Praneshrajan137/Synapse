/**
 * Effectiveness_Harness — Resilience_Scenario descriptor types (FE-WS-2, Req 6–10).
 *
 * A Resilience_Scenario is a named, reproducible adverse condition the harness
 * drives (Requirements glossary: "message firehose at a target rate, reconnect
 * with `since_seq` replay burst, backend 503, schema-violation payload, 401
 * storm, WebSocket flap, offline↔online transition, or a 10k+ row dataset").
 *
 * These descriptors are the transport-free single source of truth the
 * `*.resilience.spec.ts` E2E scenarios (design "E2E — Resilience_Scenarios")
 * drive against, so the adverse conditions and their pass criteria stay named
 * and testable rather than hand-kept per test. Task 7.1 seeds the firehose
 * stress scenario; later tasks (8.4, 9.3) extend the same registry with the
 * reconnect/replay, fault-transition, and scale scenarios.
 */

import type { SchemaId } from "../schema-registry";

/** The class of adverse condition a Resilience_Scenario exercises (Req 6–10). */
export type ResilienceKind =
  | "firehose-stress" // Req 6 — sustained high message rate
  | "reconnect-replay" // Req 7 — drop + since_seq replay burst
  | "fault-transition" // Req 8 — 503 / schema-violation / 401 storm / WS flap / offline
  | "scale-virtualization"; // Req 9 — 10k+ row dataset

/**
 * The Web Vitals budget a Resilience_Scenario must hold within (the governance
 * budget inherited from the requirements: LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1).
 * Req 6.1 asserts INP specifically, so it is the field the firehose stress E2E
 * gates on.
 */
export interface WebVitalsBudget {
  /** Largest Contentful Paint ceiling, milliseconds. */
  readonly lcpMs: number;
  /** Interaction to Next Paint ceiling, milliseconds (Req 6.1). */
  readonly inpMs: number;
  /** Cumulative Layout Shift ceiling (unitless). */
  readonly cls: number;
}

/** The governance Web_Vitals_Budget (LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1). */
export const WEB_VITALS_BUDGET: WebVitalsBudget = {
  lcpMs: 2_500,
  inpMs: 200,
  cls: 0.1,
};

/**
 * A message-rate profile the firehose stress scenario streams at. Both a
 * realistic and an adversarial rate are exercised so the bound and INP budget
 * are proven under normal load and under a burst (Req 6.1, 6.2).
 */
export interface StreamRateProfile {
  /** Human label for reports (e.g. "realistic", "adversarial"). */
  readonly label: string;
  /** Messages per second the harness streams at this profile. */
  readonly messagesPerSecond: number;
  /** How long to sustain this rate, milliseconds. */
  readonly durationMs: number;
}

/**
 * A single connectivity/fault transition applied in a fault-transition chain,
 * paired with the distinct rendered outcome the Console must produce in
 * response. Making the chain and its expected outcomes an explicit,
 * transport-free descriptor keeps a fault-transition scenario's pass criteria
 * named and testable — rather than hand-kept per E2E — and lets the E2E assert
 * that every step renders the correct DISTINCT state and NEVER latches on a
 * prior state (Req 8.6).
 */
export type FaultTransitionEvent =
  | "http-503" // a 503 for a data request → degraded (Req 8.1)
  | "schema-violation" // a schema-violating payload → error via the schema path (Req 8.2)
  | "auth-401-storm" // repeated 401s exhausting the single-flight refresh (Req 8.3)
  | "ws-flap" // a not-live WebSocket flap → not-live/reconnecting (Req 8.4)
  | "offline" // the browser transitions offline (Req 8.5)
  | "online" // the browser transitions back online (Req 8.5)
  | "recover"; // a successful data response / live socket — the healthy recovery

/**
 * The rendered outcome a fault step must produce. Mirrors the app's
 * `UniversalState` plus the auth `login` redirect (Req 8.3), kept as a local
 * string union so this spec module stays free of the app's `@`-alias graph.
 */
export type FaultRenderedState =
  | "loading"
  | "empty"
  | "error"
  | "degraded"
  | "offline"
  | "populated"
  | "login";

/** One step of a fault-transition chain: the event applied and the distinct
 *  Universal_State (or auth redirect) it must render (Req 8.6). */
export interface FaultStep {
  /** Human label for reports (e.g. "503 for a data request"). */
  readonly label: string;
  /** The connectivity/fault transition applied at this step. */
  readonly event: FaultTransitionEvent;
  /** The distinct rendered state this step must produce. */
  readonly expected: FaultRenderedState;
}

/** The terminal render status a reconciled decision row can hold (mirrors
 *  `src/lib/reconcile.ts` `RowStatus`). `acted` is monotonic/terminal: once a
 *  decision is acted it must stay acted (Req 7.2). */
export type ReplayRowStatus = "pending" | "acted";

/**
 * One scripted decision row in a reconnect-replay scenario, keyed by its stream
 * `seq` (the dedup key — a replayed `seq` can never render a duplicate row,
 * Req 7.2/7.4). Mirrors `src/lib/reconcile.ts` `Row` but is kept local to this
 * transport-free descriptor module.
 */
export interface ReplayRow {
  /** Monotonic per-stream sequence; the structural dedup key. */
  readonly seq: number;
  /** The decision this row renders (stable across a replayed `seq`). */
  readonly decisionId: string;
  /** The row's render status at this point in the script. */
  readonly status: ReplayRowStatus;
}

/**
 * The scripted drop → `since_seq` replay burst → resumed live stream a
 * `reconnect-replay` Resilience_Scenario drives (Req 7.5). Making the whole
 * sequence an explicit, transport-free descriptor keeps the scenario's pass
 * criteria named and testable — rather than hand-kept per E2E — and lets the
 * E2E assert AT THE RENDERED OUTPUT (not only the reducer) that acted decisions
 * stay acted (Req 7.2) and no duplicate rows appear (Req 7.1/7.4).
 */
export interface ReconnectReplayPlan {
  /**
   * The rows present and rendered before the connection drops (the baseline).
   * At least one MUST be `acted` so the replay burst can carry an already-acted
   * decision (Req 7.5), and the E2E can prove it stays acted (Req 7.2).
   */
  readonly preDrop: readonly ReplayRow[];
  /**
   * The `since_seq` the client requests on reconnect — its last applied
   * sequence before the drop (Req 7.1). Equals the highest `preDrop` `seq`.
   */
  readonly sinceSeq: number;
  /**
   * The replay burst delivered after reconnect. It MUST re-carry at least one
   * already-acted decision (a `seq` whose `preDrop` row was `acted`), typically
   * as a stale `pending`, so the acted-never-reverted guarantee is exercised
   * (Req 7.2); replayed `seq`s already held must not render duplicate rows
   * (Req 7.1/7.4).
   */
  readonly replay: readonly ReplayRow[];
  /**
   * The resumed live stream delivered after the replay burst drains (Req 7.5).
   * These are fresh `seq`s appended after reconciliation completes.
   */
  readonly live: readonly ReplayRow[];
}

/**
 * A named, reproducible adverse condition the Effectiveness_Harness drives.
 * `seed` fixes byte-identical fixtures and stream order (Req 1.3); `budget` is
 * the Web_Vitals_Budget the scenario must hold within; `rates` describes the
 * realistic and adversarial streaming profiles for a firehose scenario;
 * `faultChain` describes the ordered fault/connectivity transitions and the
 * distinct rendered outcome each must produce for a fault-transition scenario;
 * `replay` describes the drop / `since_seq` replay burst / resumed live stream
 * for a reconnect-replay scenario.
 */
export interface ResilienceScenario {
  /** Stable id used by the E2E spec and reports (e.g. "resilience.firehose-stress"). */
  readonly id: string;
  /** The class of adverse condition. */
  readonly kind: ResilienceKind;
  /** Deterministic seed fixing fixtures and stream order (Req 1.3). */
  readonly seed: number;
  /** Short human title for reports. */
  readonly title: string;
  /** One-sentence description of the adverse condition and what it proves. */
  readonly narrative: string;
  /** The Web_Vitals_Budget the scenario must hold within (Req 6.1). */
  readonly budget: WebVitalsBudget;
  /**
   * The Domain_Schema ids whose fixtures/streams the harness must seed. Every
   * id must resolve in the shared schema registry (asserted at module load),
   * binding the scenario to contract-accurate fixtures (Req 2.2).
   */
  readonly seedSchemaIds: readonly SchemaId[];
  /**
   * The realistic and adversarial streaming rate profiles (firehose scenarios).
   * Absent for non-streaming resilience kinds.
   */
  readonly rates?: readonly StreamRateProfile[];
  /**
   * The ordered chain of fault/connectivity transitions and the distinct
   * rendered outcome each must produce (fault-transition scenarios). Absent for
   * other resilience kinds. Req 8.6 — the chain must render the correct
   * distinct state at every step and never latch on a prior state.
   */
  readonly faultChain?: readonly FaultStep[];
  /**
   * The scripted drop / `since_seq` replay burst / resumed live stream for a
   * `reconnect-replay` scenario (Req 7.5). Absent for other resilience kinds.
   */
  readonly replay?: ReconnectReplayPlan;
  /**
   * The number of rows the harness must seed for a scale scenario. For a
   * `scale-virtualization` scenario this MUST be at least {@link SCALE_MIN_ROWS}
   * (Req 9.1, 9.5); absent for non-scale resilience kinds.
   */
  readonly seedRowCount?: number;
}

/**
 * The minimum seeded row count a `scale-virtualization` Resilience_Scenario
 * must reach so virtualization is proven against a genuinely large dataset
 * rather than asserted by inspection (Req 9.1, 9.5: "at least 10,000 rows").
 */
export const SCALE_MIN_ROWS = 10_000;
