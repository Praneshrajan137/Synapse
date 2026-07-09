import { cn } from "@lib/cn";
import type { UniversalState } from "@lib/universal-state";
import type { ReactNode } from "react";

/**
 * The shared presentation layer for the universal-state resolver (Req 10.1).
 *
 * `resolveUniversalState` (pure) decides WHICH of the six canonical conditions
 * a data-bearing Surface is in; this component decides HOW each non-populated
 * condition is rendered so every surface presents loading/empty/error/
 * degraded/offline identically. Crucially, `empty` ("no data yet") and `error`
 * ("failed to load") get visibly distinct copy and iconography so the two are
 * never confused (Req 10.8), and `offline` is never shown as stale-but-live
 * data (Req 10.7).
 *
 * Non-color channels: every state carries a text label + a glyph, never colour
 * alone (INV-CLR-011).
 */

export interface UniversalStateLabels {
  readonly loadingTitle?: string;
  readonly loadingDetail?: string;
  readonly emptyTitle?: string;
  readonly emptyDetail?: string;
  readonly errorTitle?: string;
  readonly errorDetail?: string;
  readonly degradedTitle?: string;
  readonly degradedDetail?: string;
  readonly offlineTitle?: string;
  readonly offlineDetail?: string;
}

export interface UniversalStateCopy {
  readonly glyph: string;
  readonly title: string;
  readonly detail: string;
  /** Semantic tone → drives the colour channel (paired with glyph + text). */
  readonly tone: "neutral" | "muted" | "degraded" | "danger";
  /** ARIA role for the region — errors/offline announce assertively. */
  readonly role: "status" | "alert";
}

const DEFAULTS = {
  loadingTitle: "Loading…",
  loadingDetail: "Fetching the latest data.",
  emptyTitle: "No data yet",
  emptyDetail: "Nothing to show here yet — data will appear as it arrives.",
  errorTitle: "Failed to load",
  errorDetail: "The request failed. This is not an empty result — retry to try again.",
  degradedTitle: "Running degraded",
  degradedDetail: "The system is in a degraded posture — some data may be delayed or unavailable.",
  offlineTitle: "You're offline",
  offlineDetail: "Showing nothing rather than stale data. Reconnect to resume live updates.",
} as const;

/**
 * Pure mapping from a resolved `UniversalState` (non-populated) to display copy.
 * Exported so table-based surfaces can render the same copy inside a `<tr>`
 * without duplicating the strings.
 */
export function universalStateCopy(
  state: Exclude<UniversalState, "populated">,
  labels: UniversalStateLabels = {},
): UniversalStateCopy {
  switch (state) {
    case "loading":
      return {
        glyph: "◍",
        title: labels.loadingTitle ?? DEFAULTS.loadingTitle,
        detail: labels.loadingDetail ?? DEFAULTS.loadingDetail,
        tone: "muted",
        role: "status",
      };
    case "empty":
      return {
        glyph: "∅",
        title: labels.emptyTitle ?? DEFAULTS.emptyTitle,
        detail: labels.emptyDetail ?? DEFAULTS.emptyDetail,
        tone: "muted",
        role: "status",
      };
    case "error":
      return {
        glyph: "⚠",
        title: labels.errorTitle ?? DEFAULTS.errorTitle,
        detail: labels.errorDetail ?? DEFAULTS.errorDetail,
        tone: "danger",
        role: "alert",
      };
    case "degraded":
      return {
        glyph: "▲",
        title: labels.degradedTitle ?? DEFAULTS.degradedTitle,
        detail: labels.degradedDetail ?? DEFAULTS.degradedDetail,
        tone: "degraded",
        role: "status",
      };
    case "offline":
      return {
        glyph: "⦸",
        title: labels.offlineTitle ?? DEFAULTS.offlineTitle,
        detail: labels.offlineDetail ?? DEFAULTS.offlineDetail,
        tone: "danger",
        role: "alert",
      };
  }
}

const TONE_CLASS: Record<UniversalStateCopy["tone"], string> = {
  neutral: "text-ink",
  muted: "text-ink-muted",
  degraded: "text-state-degraded",
  danger: "text-confidence-risk",
};

export interface UniversalStateViewProps {
  readonly state: UniversalState;
  readonly labels?: UniversalStateLabels;
  /** Rendered only when `state === "populated"`. */
  readonly children: ReactNode;
  /** Optional retry affordance shown on the error/offline/degraded states. */
  readonly onRetry?: () => void;
  readonly retryLabel?: string;
  readonly className?: string;
}

/**
 * Wraps a surface's populated content and swaps in a distinct block for each
 * non-populated universal state. Consumers compute `state` via
 * `useUniversalState` and pass their rendered content as children.
 */
export function UniversalStateView({
  state,
  labels,
  children,
  onRetry,
  retryLabel = "Retry",
  className,
}: UniversalStateViewProps) {
  if (state === "populated") return <>{children}</>;

  const copy = universalStateCopy(state, labels);
  const showRetry = onRetry && (state === "error" || state === "offline" || state === "degraded");

  return (
    <div
      role={copy.role}
      aria-live={copy.role === "alert" ? "assertive" : "polite"}
      data-universal-state={state}
      className={cn(
        "syn-card flex flex-col items-center justify-center gap-2 px-6 py-12 text-center",
        className,
      )}
    >
      <span aria-hidden className={cn("text-2xl", TONE_CLASS[copy.tone])}>
        {copy.glyph}
      </span>
      <p className={cn("text-sm font-semibold", TONE_CLASS[copy.tone])}>{copy.title}</p>
      <p className="max-w-prose text-xs text-ink-muted">{copy.detail}</p>
      {showRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 h-8 rounded-md border border-border bg-surface-raised px-3 text-xs font-medium text-ink hover:bg-surface focus-visible:outline-none focus-visible:shadow-focus"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}

export interface UniversalStateRowProps {
  readonly state: Exclude<UniversalState, "populated">;
  readonly colSpan: number;
  readonly labels?: UniversalStateLabels;
}

/**
 * Table-body variant: renders the same universal-state copy inside a single
 * spanning `<tr>` so table surfaces (Audit Vault, Decision Theater) can express
 * loading/empty/error/degraded/offline without leaving their `<tbody>`.
 */
export function UniversalStateRow({ state, colSpan, labels }: UniversalStateRowProps) {
  const copy = universalStateCopy(state, labels);
  return (
    <tr>
      <td
        colSpan={colSpan}
        role={copy.role}
        aria-live={copy.role === "alert" ? "assertive" : "polite"}
        data-universal-state={state}
        className={cn("px-3 py-8 text-center", TONE_CLASS[copy.tone])}
      >
        <span aria-hidden className="mr-2">
          {copy.glyph}
        </span>
        <span className="font-medium">{copy.title}</span>
        <span className="ml-2 text-xs text-ink-muted">{copy.detail}</span>
      </td>
    </tr>
  );
}
