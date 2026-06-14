import type { DisruptionAlert } from "@domain/disruption-alert";
import type { TwinDivergenceEvent } from "@domain/twin-state";
import type { SystemPosture } from "@transport/synapse-api";
import type { WsState } from "@transport/ws-multiplex";
import { create } from "zustand";
import type { EscalationEntry } from "./escalation.store";

// ── The Attention Spine (Sprint 18) ─────────────────────────────────────────
// SYNAPSE is supervisory control of bounded autonomy: the operator's job is to
// reclaim control at the right moment (I-5) and otherwise trust the system.
// Historically every signal shouted independently (DegradedBanner, the
// DisruptionBanner, cockpit-only escalations, the connection pill, twin
// divergence) with NO ranking — and the one signal that actually needs a human
// (a pending escalation) was the quietest. This module ranks every signal into
// ONE ordered list so the loudest thing is always the most important thing
// (the prioritisation discipline behind ISA-101 / EEMUA-191 alarm management).
//
// `rankAttention` is pure + deterministic (unit-tested). The acknowledgement
// store suppresses an *informational* item until its signature changes;
// actionable items (escalations) are never suppressible — they must be resolved.

export type AttentionSeverity = "critical" | "high" | "medium" | "low";
export type AttentionKind =
  | "escalation"
  | "connection"
  | "degradation"
  | "disruption"
  | "divergence";

export interface AttentionItem {
  /** Stable signature; changes when the underlying condition changes. */
  readonly key: string;
  readonly kind: AttentionKind;
  readonly severity: AttentionSeverity;
  readonly title: string;
  readonly detail: string;
  /** How many underlying signals this item folds together. */
  readonly count: number;
  /** Where clicking the item takes the operator. */
  readonly route: string;
  /** Requires a human decision (vs. purely informational). */
  readonly actionable: boolean;
  /** Ranking score, descending. */
  readonly score: number;
}

/** I-12 digital-twin re-sync threshold. */
export const TWIN_KL_THRESHOLD = 0.1;
/** Disruption alert level below which we don't raise a spine item. */
export const DISRUPTION_MIN_LEVEL = 5;

const SEVERITY_RANK: Record<AttentionSeverity, number> = {
  critical: 3,
  high: 2,
  medium: 1,
  low: 0,
};
// Tie-break at equal severity: the human-in-the-loop item always wins.
const KIND_PRIORITY: Record<AttentionKind, number> = {
  escalation: 5,
  connection: 4,
  degradation: 3,
  disruption: 2,
  divergence: 1,
};

export interface AttentionInput {
  readonly escalations: ReadonlyArray<EscalationEntry>;
  readonly posture: SystemPosture | undefined;
  readonly postureError: boolean;
  readonly disruptions: ReadonlyArray<DisruptionAlert>;
  readonly twin: ReadonlyArray<TwinDivergenceEvent>;
  readonly connection: WsState;
  readonly acknowledged: Readonly<Record<string, number>>;
}

function escalationSeverity(e: EscalationEntry): AttentionSeverity {
  const violations = e.message.violations ?? [];
  if (violations.some((v) => v.severity === "critical")) return "critical";
  // An escalation is, by definition, a decision the autonomy could not make —
  // it always needs a human, so the floor is "high".
  return "high";
}

function openBreakers(posture: SystemPosture | undefined): string[] {
  if (!posture?.breakers) return [];
  return Object.entries(posture.breakers)
    .filter(([, s]) => String(s).toLowerCase() === "open")
    .map(([name]) => name)
    .sort();
}

function brownoutCities(posture: SystemPosture | undefined): string[] {
  if (!posture?.brownout) return [];
  return Object.keys(posture.brownout).sort();
}

/** Pure, deterministic ranking of every attention signal into one list. */
export function rankAttention(input: AttentionInput): AttentionItem[] {
  const items: Omit<AttentionItem, "score">[] = [];

  // 1) Escalations — the human-in-the-loop signal (I-5). Pending only.
  const pending = input.escalations.filter((e) => e.status === "pending");
  if (pending.length > 0) {
    const worst = pending.reduce<AttentionSeverity>((acc, e) => {
      const s = escalationSeverity(e);
      return SEVERITY_RANK[s] > SEVERITY_RANK[acc] ? s : acc;
    }, "high");
    const ids = pending.map((e) => e.id).sort();
    const reason = pending.find((e) => e.message.reason)?.message.reason;
    items.push({
      key: `esc:${ids.join(",")}`,
      kind: "escalation",
      severity: worst,
      title:
        pending.length === 1 ? "1 decision awaits you" : `${pending.length} decisions await you`,
      detail: reason ?? "Confidence fell below the autonomy gate (I-5).",
      count: pending.length,
      route: "/cockpit",
      actionable: true,
    });
  }

  // 2) Live feed offline — the operator is blind.
  if (input.connection === "closed") {
    items.push({
      key: "conn:closed",
      kind: "connection",
      severity: "high",
      title: "Live feed offline",
      detail: "The decision firehose is disconnected — reconnecting.",
      count: 1,
      route: "/",
      actionable: false,
    });
  }

  // 3) Degradation posture (ADR-044 D4).
  const breakers = openBreakers(input.posture);
  const brownouts = brownoutCities(input.posture);
  if (input.postureError) {
    items.push({
      key: "deg:unknown",
      kind: "degradation",
      severity: "medium",
      title: "System posture unknown",
      detail: "Cannot reach the posture endpoint — treating as degraded.",
      count: 1,
      route: "/agents",
      actionable: false,
    });
  } else if (breakers.length > 0 || brownouts.length > 0 || input.posture?.degraded) {
    items.push({
      key: `deg:${breakers.join(",")}|${brownouts.join(",")}`,
      kind: "degradation",
      severity: breakers.length > 0 ? "high" : "medium",
      title:
        breakers.length > 0
          ? `${breakers.length} circuit breaker${breakers.length === 1 ? "" : "s"} open`
          : "Brownout active",
      detail:
        [
          breakers.length > 0 ? `Breakers: ${breakers.join(", ")}` : "",
          brownouts.length > 0 ? `Brownout: ${brownouts.join(", ")}` : "",
        ]
          .filter(Boolean)
          .join(" · ") || "System running degraded.",
      count: breakers.length + brownouts.length || 1,
      route: "/agents",
      actionable: false,
    });
  }

  // 4) Disruption — the most-recent significant alert.
  const disruption = [...input.disruptions]
    .reverse()
    .find((d) => d.alert_level >= DISRUPTION_MIN_LEVEL);
  if (disruption) {
    items.push({
      key: `disr:${disruption.alert_id}`,
      kind: "disruption",
      severity:
        disruption.alert_level >= 8 ? "critical" : disruption.alert_level >= 6 ? "high" : "medium",
      title: `Disruption · level ${disruption.alert_level}/10`,
      detail: disruption.disruption_type ?? "supply-chain anomaly",
      count: 1,
      route: "/",
      actionable: false,
    });
  }

  // 5) Twin divergence above the I-12 re-sync threshold.
  const divergence = [...input.twin]
    .reverse()
    .find((t) => typeof t.kl_divergence === "number" && t.kl_divergence > TWIN_KL_THRESHOLD);
  if (divergence) {
    const agent = "agent_name" in divergence ? divergence.agent_name : undefined;
    items.push({
      key: `twin:${agent ?? "system"}:${divergence.kl_divergence.toFixed(2)}`,
      kind: "divergence",
      severity: "medium",
      title: "Twin divergence high",
      detail: `KL ${divergence.kl_divergence.toFixed(3)} > ${TWIN_KL_THRESHOLD} — model vs live drift${
        agent ? ` (${agent})` : ""
      }.`,
      count: 1,
      route: "/twin",
      actionable: false,
    });
  }

  return (
    items
      // Actionable items are never suppressible; informational items hide once
      // acknowledged, until their signature changes.
      .filter((it) => it.actionable || input.acknowledged[it.key] === undefined)
      .map((it) => ({
        ...it,
        score:
          SEVERITY_RANK[it.severity] * 100 + KIND_PRIORITY[it.kind] * 10 + (it.actionable ? 5 : 0),
      }))
      .sort((a, b) => b.score - a.score)
  );
}

// ── Acknowledgement store ────────────────────────────────────────────────────
interface AttentionAckState {
  readonly acknowledged: Readonly<Record<string, number>>;
  acknowledge(key: string): void;
  reset(): void;
}

export const useAttentionAck = create<AttentionAckState>((set) => ({
  acknowledged: {},
  acknowledge(key) {
    set((s) => ({ acknowledged: { ...s.acknowledged, [key]: Date.now() } }));
  },
  reset() {
    set({ acknowledged: {} });
  },
}));
