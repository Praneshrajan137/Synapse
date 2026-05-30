import {
  AGENT_COLOR_VAR,
  AGENT_INITIALS,
  AGENT_LABEL,
  AGENT_NAMES,
  type AgentName,
} from "@lib/agent-identity";
import { rationedAgentColor } from "@lib/chromatics";
import { cn } from "@lib/cn";
import { fmt } from "@lib/formatters";

/**
 * CouncilStrip — the eight specialist minds as an ambient presence row.
 *
 * Two SENSORIUM principles made literal:
 *   • QUIET BY DEFAULT (P3): each agent's frozen identity hue is *rationed*.
 *     At rest the dot is drained toward the neutral base; it re-chroma's only
 *     when the agent is active in a live decision. A calm council is a near-
 *     monochrome row — so colour, when it appears, means "look here".
 *   • HONESTY (P7): degradation is a designed, first-class state. An agent on
 *     a fallback path, unreachable, or of unknown health is shown plainly —
 *     never painted a reassuring green. Every cell carries a STATUS WORD, so
 *     state survives colour-blindness and greyscale (INV-CLR-011).
 *
 * Status strings map straight from `GET /api/v1/agents` (api/routers/agents.py):
 * "healthy" → healthy, "http_*" → degraded, "unreachable*" → unreachable,
 * anything else → unknown.
 */

export type AgentHealth = "healthy" | "degraded" | "unreachable" | "unknown";

export interface CouncilAgentState {
  readonly status: AgentHealth;
  /** True when the agent is currently contributing to a live decision. */
  readonly active?: boolean | undefined;
  readonly latencyP99Ms?: number | null | undefined;
  readonly calibration90?: number | null | undefined;
}

export interface CouncilStripProps {
  /** Per-agent state. Missing agents render as `unknown` (honest default). */
  readonly states?: Partial<Record<AgentName, CouncilAgentState>> | undefined;
  readonly selectedAgent?: AgentName | null | undefined;
  readonly onSelectAgent?: ((agent: AgentName) => void) | undefined;
  readonly className?: string | undefined;
}

const STATUS_WORD: Record<AgentHealth, string> = {
  healthy: "live",
  degraded: "degraded",
  unreachable: "offline",
  unknown: "—",
};

const STATUS_TONE: Record<AgentHealth, string> = {
  healthy: "text-signal-success",
  degraded: "text-signal-warning",
  unreachable: "text-signal-danger",
  unknown: "text-ink-subtle",
};

/** Normalise a raw `GET /api/v1/agents` status string to an `AgentHealth`. */
export function mapAgentHealth(raw: string | undefined | null): AgentHealth {
  if (!raw) return "unknown";
  if (raw === "healthy") return "healthy";
  if (raw.startsWith("http_")) return "degraded";
  if (raw.startsWith("unreachable")) return "unreachable";
  return "unknown";
}

/** How much of the agent's identity hue to show, by health + activity. */
function activityFor(state: CouncilAgentState): number {
  switch (state.status) {
    case "unreachable":
      return 0.1; // drained — the colour has left the room
    case "unknown":
      return 0.12;
    case "degraded":
      return 0.5; // present but visibly not at full strength
    case "healthy":
      return state.active ? 1 : 0.34; // full on activity, quiet at rest
  }
}

export function CouncilStrip({
  states,
  selectedAgent = null,
  onSelectAgent,
  className,
}: CouncilStripProps) {
  return (
    <ul
      className={cn("grid grid-cols-4 gap-2 sm:grid-cols-8", className)}
      aria-label="Agent council — eight specialists, live presence"
    >
      {AGENT_NAMES.map((agent) => {
        const state: CouncilAgentState = states?.[agent] ?? { status: "unknown" };
        const health = state.status;
        const activity = activityFor(state);
        const dotColor = rationedAgentColor(AGENT_COLOR_VAR[agent], activity);
        const interactive = Boolean(onSelectAgent);
        const selected = selectedAgent === agent;
        const degraded = health === "degraded" || health === "unreachable";

        const parts = [
          `${AGENT_LABEL[agent]}: ${health === "unknown" ? "status unknown" : STATUS_WORD[health]}`,
        ];
        if (state.active) parts.push("active in a live decision");
        if (state.latencyP99Ms != null) parts.push(`p99 ${fmt.durationMs(state.latencyP99Ms)}`);
        if (state.calibration90 != null) {
          parts.push(`calibration ${Math.round(state.calibration90 * 100)} percent`);
        }
        const ariaLabel = parts.join(", ");

        const Cell = interactive ? "button" : "div";

        return (
          <li key={agent}>
            <Cell
              {...(interactive
                ? {
                    type: "button" as const,
                    onClick: () => onSelectAgent?.(agent),
                    "aria-pressed": selected,
                  }
                : {})}
              aria-label={ariaLabel}
              title={ariaLabel}
              className={cn(
                "flex w-full flex-col items-center gap-1 rounded-lg border p-2 transition-colors duration-fast ease-standard",
                "border-border bg-surface",
                interactive && "cursor-pointer hover:bg-surface-raised",
                selected && "ring-2 ring-accent",
                degraded && "border-signal-warning/40",
                health === "unreachable" && "border-signal-danger/40",
              )}
            >
              <span
                className={cn(
                  "relative flex size-7 items-center justify-center rounded-full border",
                  state.active && "animate-pulse-confidence",
                )}
                style={{
                  background: dotColor,
                  borderColor: state.active ? AGENT_COLOR_VAR[agent] : "transparent",
                }}
                aria-hidden="true"
              >
                <span className="font-mono text-[0.6rem] font-bold uppercase tracking-tight text-ink-inverse mix-blend-luminosity">
                  {AGENT_INITIALS[agent]}
                </span>
              </span>
              <span className="w-full truncate text-center text-2xs font-medium text-ink-muted">
                {AGENT_LABEL[agent]}
              </span>
              <span
                className={cn(
                  "text-[0.6rem] font-semibold uppercase tracking-wide tabular-nums",
                  STATUS_TONE[health],
                )}
                aria-hidden="true"
              >
                {STATUS_WORD[health]}
              </span>
            </Cell>
          </li>
        );
      })}
    </ul>
  );
}
