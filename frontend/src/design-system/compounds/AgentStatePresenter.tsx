import type { RenderableAgentState } from "@domain/agent-state";
import { AGENT_LABEL, type AgentName } from "@lib/agent-identity";
import { cn } from "@lib/cn";

/**
 * AgentStatePresenter — renders a single `RenderableAgentState` honestly.
 *
 * Two SENSORIUM principles made literal (mirrors `CouncilStrip`):
 *   • FROZEN IDENTITY (INV-CLR-012, Req 2.5): a live agent is painted in its
 *     frozen identity hue. State is encoded as CHROMA RATIONING — the hue angle
 *     never changes across a transition, only chroma (via the descriptor's
 *     `chromaFactor`, which is strictly > 0, Req 2.7). An agent's state never
 *     masquerades as a different agent.
 *   • HONESTY (Req 2.2/2.3/2.6, INV-CLR-011): the AUX layer never fabricates
 *     activity. Every kind carries a NON-COLOUR channel — a status word, a
 *     `data-agent-state` attribute, and a shape glyph — so state survives
 *     colour-blindness and greyscale. `unavailable` (no backing event) and
 *     `not-live` (stream stale > 5s) render explicit non-colour markers rather
 *     than a frozen state shown as active.
 *
 * The component is a pure render of the passed state, so a state change is
 * reflected on the next React commit — within 100ms of the backing event that
 * produced the new `RenderableAgentState` (Req 2.5), with no debounce/delay.
 */

export interface AgentStatePresenterProps {
  /** The derived, availability-wrapped state (from `deriveAgentState`). */
  readonly state: RenderableAgentState;
  /** Optional agent identity — enriches the accessible label with the name. */
  readonly agent?: AgentName | undefined;
  readonly className?: string | undefined;
}

/** Non-colour markers for the two non-live kinds — a word + a shape glyph. */
const UNAVAILABLE_WORD = "unavailable";
const UNAVAILABLE_GLYPH = "⊘";
const NOT_LIVE_WORD = "not-live";
const NOT_LIVE_GLYPH = "◍";

/**
 * The identity colour for a live state: the frozen identity hue, chroma
 * rationed by the descriptor factor. Mixing toward the achromatic neutral base
 * in OKLab scales chroma WITHOUT rotating the hue angle, so the hue stays
 * frozen across transitions (Req 2.5, INV-CLR-012). Token-only output — no raw
 * colour literal (INV-CLR-009).
 */
function identityColor(hue: string, chromaFactor: number): string {
  const pct = Math.round(chromaFactor * 100);
  return `color-mix(in oklab, ${hue} ${pct}%, var(--syn-neutral-mix))`;
}

export function AgentStatePresenter({ state, agent, className }: AgentStatePresenterProps) {
  const prefix = agent ? `${AGENT_LABEL[agent]}: ` : "";

  // The three non-colour channels, resolved per kind.
  let word: string;
  let glyph: string;
  let dataAgentState: string;
  let dotColor: string | undefined;
  let live = false;

  switch (state.kind) {
    case "live": {
      word = state.descriptor.label;
      glyph = state.descriptor.glyph;
      dataAgentState = state.descriptor.state;
      dotColor = identityColor(state.hue, state.descriptor.chromaFactor);
      live = true;
      break;
    }
    case "unavailable": {
      word = UNAVAILABLE_WORD;
      glyph = UNAVAILABLE_GLYPH;
      dataAgentState = "unavailable";
      break;
    }
    case "not-live": {
      word = NOT_LIVE_WORD;
      glyph = NOT_LIVE_GLYPH;
      dataAgentState = "not-live";
      break;
    }
  }

  const ariaLabel = `${prefix}${word}`;

  return (
    <span
      data-agent-state={dataAgentState}
      aria-label={ariaLabel}
      title={ariaLabel}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1",
        "border-border bg-surface text-2xs font-medium",
        !live && "text-ink-subtle",
        className,
      )}
    >
      <span
        className={cn(
          "flex size-4 items-center justify-center rounded-full text-[0.6rem] leading-none",
          live ? "text-ink-inverse" : "text-ink-muted",
        )}
        style={live && dotColor ? { background: dotColor } : undefined}
        aria-hidden="true"
      >
        {glyph}
      </span>
      <span
        className={cn(
          "font-semibold uppercase tracking-wide tabular-nums",
          live ? "text-ink" : "text-ink-subtle",
        )}
        aria-hidden="true"
      >
        {word}
      </span>
    </span>
  );
}
