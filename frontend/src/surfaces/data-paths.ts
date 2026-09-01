import {
  type DataPathNoticeState,
  type DataPathSignals,
  type DataPathSpec,
  resolveDataPath,
} from "@ds/compounds/DataPathNotice";

/**
 * The registry of every console panel that displays a value derived from a
 * pipeline read - one row per panel, naming the read it actually performs
 * (R3.5, R4.3, R13.6).
 *
 * Why a registry, and why it is not just a hand-maintained mirror
 * ---------------------------------------------------------------
 * Three things make this mechanical rather than documentary:
 *
 *  1. It is the ONLY way a panel gets its notice. Panels call
 *     `surfaceDataPath(id, signals)`; they do not hand-author a degraded label.
 *     So a panel and its declared data path cannot drift apart - there is one
 *     value, used by both.
 *  2. `SurfaceDataPathId` is a closed union derived from this object. A panel
 *     that passes an unregistered id does not compile, so "displays a pipeline
 *     value but declares no data path" is a type error rather than an omission
 *     a reviewer has to notice.
 *  3. `endpoint: null` REQUIRES `absentDetailKey` (see `DataPathSpec`). R13.6's
 *     "the surface states that no data path exists" therefore cannot be
 *     skipped: a no-endpoint panel with no statement does not compile.
 *
 * The residual hole is honestly named: nothing here forces a NEW panel to call
 * `surfaceDataPath` at all. Closing that needs an enumeration of surface
 * modules intersected with `SURFACE_DATA_PATH_IDS` - which is why the ids below
 * are exported as a tuple, so the Property 31 suite can iterate them and assert
 * one rendered `[data-data-path]` per row.
 */

const SPECS = {
  // ── Mission Control ───────────────────────────────────────────────────────
  /**
   * The two authoritative counters in the KPI band. Both are server totals over
   * the standing WorldRuntime, so both inherit that world's computed
   * `is_synthetic`.
   */
  "mission-control.autonomy-counters": {
    endpoint: "GET /api/v1/system/autonomy",
    dataClass: "pipeline",
    syntheticSource: "world",
  },
  /**
   * The live-window tiles: counts and means over the last N events this client
   * received. Synthetic-sourced whenever any decision in the window carries
   * `is_synthetic` - the window does not filter them out.
   */
  "mission-control.live-window": {
    endpoint: "WS /ws/firehose (decision, routing, disruption)",
    dataClass: "client-window",
    syntheticSource: "decision",
  },

  // ── Operations ────────────────────────────────────────────────────────────
  "operations.escalation-pressure": {
    endpoint: "GET /api/v1/escalations/analytics",
    dataClass: "pipeline",
    syntheticSource: "never",
  },
  "operations.calibration": {
    endpoint: "GET /api/v1/system/calibration",
    dataClass: "pipeline",
    syntheticSource: "decision",
  },
  "operations.confidence-distribution": {
    endpoint: "GET /api/v1/decisions/recent",
    dataClass: "pipeline",
    syntheticSource: "decision",
  },
  "operations.slo-burn": {
    endpoint: "GET /api/v1/system/slo",
    dataClass: "pipeline",
    syntheticSource: "never",
  },
  /**
   * R13.6, instance 1. No per-operator longitudinal outcomes read exists: the
   * component is rendered propless, so its `outcomes` default is `[]` and every
   * count it shows is a structural zero, not a measurement.
   */
  "operations.trust-track-record": {
    endpoint: null,
    absentDetailKey: "datapath.absent_trust_track",
  },
  /**
   * R13.6, instance 2. No system-level uplift read exists. The slot is
   * deliberately always present (it must not hide), which is exactly why the
   * surface has to say the absence is structural.
   */
  "operations.uplift": {
    endpoint: null,
    absentDetailKey: "datapath.absent_uplift",
  },

  // ── Twin Lab ──────────────────────────────────────────────────────────────
  /**
   * KL divergence against the live distribution (I-12). The value is null until
   * a scenario has actually run: `null` must read as "not measured", never as
   * `0.000`, which on this meter is the strongest possible fidelity claim.
   */
  "twin-lab.divergence": {
    endpoint: "POST /simulate + WS /ws/firehose (twin)",
    dataClass: "pipeline",
    syntheticSource: "world",
  },
  "twin-lab.autonomy-world": {
    endpoint: "GET /api/v1/system/autonomy",
    dataClass: "pipeline",
    syntheticSource: "world",
  },

  // ── Live Markets ──────────────────────────────────────────────────────────
  /**
   * The Demand Prophet / Pricing Oracle / Freshness Guardian streams. These
   * payloads carry NO provenance block (no `degraded`, no `is_synthetic`), so
   * both signals arrive `null` and the notice resolves to "unknown" - the
   * honest state for the flagship agent's output while no checkpoint is
   * published (R3.5). Filed as a backend gap, not papered over here.
   */
  "live-markets.agent-streams": {
    endpoint: "WS /ws/firehose (pricing, freshness, demand)",
    dataClass: "client-window",
    syntheticSource: "world",
  },

  // ── Agent Council ─────────────────────────────────────────────────────────
  /**
   * Status + latency percentiles + calibration coverage per agent. The health
   * payload carries no model provenance, so it cannot say whether an agent
   * serves a published checkpoint or a degraded fallback.
   */
  "agent-council.health": {
    endpoint: "GET /api/v1/agents",
    dataClass: "pipeline",
    syntheticSource: "never",
  },
} as const satisfies Record<string, DataPathSpec>;

export type SurfaceDataPathId = keyof typeof SPECS;

export const SURFACE_DATA_PATHS: Readonly<Record<SurfaceDataPathId, DataPathSpec>> = SPECS;

/** Every registered id, in declaration order, for enumeration by the checks. */
export const SURFACE_DATA_PATH_IDS = Object.keys(SPECS) as ReadonlyArray<SurfaceDataPathId>;

/**
 * Resolve the notice a panel must render, from its registered data path and
 * whatever the current read told it.
 *
 * Fail-closed by construction (see `resolveDataPath`): a `degraded` signal of
 * `null` - the shape a payload with no degradation flag produces - can never
 * resolve to "live".
 */
export function surfaceDataPath(
  id: SurfaceDataPathId,
  signals: DataPathSignals,
): DataPathNoticeState {
  return resolveDataPath(SURFACE_DATA_PATHS[id], signals);
}

/** The R13.6 subset: panels that have no data endpoint at all. */
export const ABSENT_DATA_PATH_IDS: ReadonlyArray<SurfaceDataPathId> = SURFACE_DATA_PATH_IDS.filter(
  (id) => SURFACE_DATA_PATHS[id].endpoint === null,
);
