import { cn } from "@lib/cn";
import { useTranslation } from "react-i18next";
import { SyntheticBadge } from "./SyntheticBadge";

/**
 * The Honesty Channel's *data-path* marker (R3.5, R4.3, R13.6).
 *
 * `ProvenanceChip` answers "how was THIS output produced". This answers the
 * question one level up, which no component answered before: "where does the
 * number I am looking at come from, and can I read it as a healthy pipeline
 * read at all". Three obligations, deliberately kept separate because they can
 * hold in any combination:
 *
 *  1. R3.5 - a value derived from a DEGRADED pipeline response renders the
 *     declared degraded state. `kind === "degraded"`.
 *  2. R4.3 - an aggregate derived from a state whose `is_synthetic` is true is
 *     labelled synthetic-sourced. `syntheticSourced === true`, computed
 *     INDEPENDENTLY of `kind` so no precedence ordering can swallow it: a
 *     degraded synthetic aggregate renders both.
 *  3. R13.6 - a component with NO data endpoint renders its declared empty
 *     state and the surface states that no data path exists.
 *     `kind === "absent"` and `statesNoDataPath === true`.
 *
 * Why this is mechanical rather than conventional
 * -----------------------------------------------
 * `resolveDataPath` is TOTAL and FAIL-CLOSED. `kind === "live"` is reachable
 * only from an affirmative `degraded === false`; a missing signal (`null`)
 * resolves to `"unknown"`, never to `"live"`. Under I-7 that is the whole
 * point: absence of a degradation flag is not proof of a healthy read, so a
 * payload that carries no flag (the demand/pricing/agent-health reads today)
 * cannot render as live by omission. Likewise a `DataPathSpec` with
 * `endpoint: null` CANNOT be constructed without `absentDetailKey` - the union
 * below makes the R13.6 statement a compile-time obligation, not a habit.
 *
 * Every rendered notice carries `data-data-path` and `data-synthetic-sourced`
 * so a DOM- or browser-level check reads the state off the surface rather than
 * matching copy.
 */

/** How a displayed value was obtained. */
export type DataPathClass = "pipeline" | "client-window";

/**
 * Which `is_synthetic` flag, if any, governs the values on this path.
 *
 *   "world"    - `WorldState.is_synthetic`, which since the source-provenance
 *                change is COMPUTED from the active `WorldSource`
 *                (SEEDED / EXTERNAL / STUB), not pinned. The console must
 *                surface whatever it computes to, including `false`.
 *   "decision" - the per-decision envelope flag (traffic-generator pulses).
 *   "never"    - the path carries no world- or decision-sourced values, so no
 *                synthetic claim is made in either direction.
 */
export type SyntheticSource = "world" | "decision" | "never";

/**
 * A registered data path.
 *
 * The `endpoint: null` arm is the R13.6 case, and it REQUIRES
 * `absentDetailKey`: a panel cannot be registered as endpoint-less without
 * copy that states no data path exists. That is the mechanical half of R13.6 -
 * omitting the statement does not compile.
 */
export type DataPathSpec =
  | {
      readonly endpoint: string;
      readonly dataClass: DataPathClass;
      readonly syntheticSource: SyntheticSource;
    }
  | {
      readonly endpoint: null;
      readonly absentDetailKey: string;
    };

/**
 * What the surface knows about the read behind the values it is about to draw.
 *
 * Both fields are tri-state on purpose. `null` means "the payload does not
 * carry this fact", which is a different claim from `false` and must never
 * collapse into it (I-7).
 */
export interface DataPathSignals {
  /** The pipeline response declared degradation, or the read itself failed. */
  readonly degraded: boolean | null;
  /** The values derive from a state whose `is_synthetic` is true. */
  readonly synthetic: boolean | null;
}

export type DataPathKind = "absent" | "degraded" | "unknown" | "live";

export type DataPathTone = "muted" | "degraded" | "absent";

export interface DataPathNoticeState {
  readonly kind: DataPathKind;
  /** R4.3 - affirmatively synthetic-sourced. Independent of `kind`. */
  readonly syntheticSourced: boolean;
  /** The path can be synthetic-sourced but the payload does not say. */
  readonly syntheticUnknown: boolean;
  /** R13.6 - this panel has no data endpoint at all. */
  readonly statesNoDataPath: boolean;
  readonly endpoint: string | null;
  readonly labelKey: string;
  readonly detailKey: string;
  /** Discloses server-read vs client-window scope; null when no path exists. */
  readonly scopeKey: string | null;
  readonly glyph: string;
  readonly tone: DataPathTone;
}

interface KindCopy {
  readonly labelKey: string;
  readonly detailKey: string;
  readonly glyph: string;
  readonly tone: DataPathTone;
}

/**
 * A `Record` over the closed `DataPathKind` union: adding a kind without copy
 * is a compile error, so no state can render wordlessly.
 */
const KIND_COPY: Record<DataPathKind, KindCopy> = {
  absent: {
    labelKey: "datapath.absent",
    // Overridden by the spec's `absentDetailKey` - every absent path states
    // its own reason (R13.6).
    detailKey: "datapath.absent_detail",
    glyph: "\u2205",
    tone: "absent",
  },
  degraded: {
    labelKey: "datapath.degraded",
    detailKey: "datapath.degraded_detail",
    glyph: "\u25B2",
    tone: "degraded",
  },
  unknown: {
    labelKey: "datapath.unknown",
    detailKey: "datapath.unknown_detail",
    glyph: "\u25B2",
    tone: "degraded",
  },
  live: {
    labelKey: "datapath.live",
    detailKey: "datapath.live_detail",
    glyph: "\u00B7",
    tone: "muted",
  },
};

const SCOPE_KEY: Record<DataPathClass, string> = {
  pipeline: "datapath.scope_pipeline",
  "client-window": "datapath.scope_client_window",
};

/**
 * Resolve what a surface must render about the data path behind its values.
 *
 * Precedence for `kind` is fixed and total:
 *   absent > degraded > unknown > live
 *
 * `syntheticSourced` and `syntheticUnknown` sit OUTSIDE that ordering, so
 * R4.3's label survives a degraded read (R3.5) rather than being masked by it.
 */
export function resolveDataPath(spec: DataPathSpec, signals: DataPathSignals): DataPathNoticeState {
  if (spec.endpoint === null) {
    const copy = KIND_COPY.absent;
    return {
      kind: "absent",
      syntheticSourced: false,
      syntheticUnknown: false,
      statesNoDataPath: true,
      endpoint: null,
      labelKey: copy.labelKey,
      detailKey: spec.absentDetailKey,
      scopeKey: null,
      glyph: copy.glyph,
      tone: copy.tone,
    };
  }

  const kind: DataPathKind =
    signals.degraded === true ? "degraded" : signals.degraded === null ? "unknown" : "live";
  const copy = KIND_COPY[kind];
  const claims = spec.syntheticSource !== "never";

  return {
    kind,
    syntheticSourced: claims && signals.synthetic === true,
    syntheticUnknown: claims && signals.synthetic === null,
    statesNoDataPath: false,
    endpoint: spec.endpoint,
    labelKey: copy.labelKey,
    detailKey: copy.detailKey,
    scopeKey: SCOPE_KEY[spec.dataClass],
    glyph: copy.glyph,
    tone: copy.tone,
  };
}

const TONE_CLASS: Record<DataPathTone, string> = {
  muted: "text-ink-subtle",
  degraded: "text-state-degraded",
  absent: "text-ink-subtle",
};

export interface DataPathNoticeProps {
  readonly state: DataPathNoticeState;
  readonly className?: string;
}

/**
 * Renders one resolved data-path state. Always rendered - including the `live`
 * case - so a MISSING notice is itself detectable on a surface rather than
 * being indistinguishable from a healthy one.
 */
export function DataPathNotice({ state, className }: DataPathNoticeProps) {
  const { t } = useTranslation("common");

  return (
    <p
      data-data-path={state.kind}
      data-synthetic-sourced={state.syntheticSourced ? "true" : "false"}
      className={cn("flex flex-wrap items-center gap-x-1.5 gap-y-1 text-2xs", className)}
    >
      <span aria-hidden className={TONE_CLASS[state.tone]}>
        {state.glyph}
      </span>
      <span className={cn("font-medium uppercase tracking-wide", TONE_CLASS[state.tone])}>
        {t(state.labelKey)}
      </span>
      <span className="text-ink-subtle">{t(state.detailKey)}</span>
      {state.endpoint !== null && (
        <span className="font-mono text-ink-subtle">
          {t("datapath.source")}: {state.endpoint}
          {state.scopeKey !== null && ` (${t(state.scopeKey)})`}
        </span>
      )}
      {state.syntheticUnknown && (
        <span className="text-state-degraded">{t("datapath.synthetic_unknown")}</span>
      )}
      {state.syntheticSourced && <SyntheticBadge variant="aggregate" />}
    </p>
  );
}
