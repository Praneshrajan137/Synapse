import type { AgentMetrics } from "@domain/agent-health";
import { type CouncilAgentState, CouncilStrip, Pulse, mapAgentHealth } from "@ds/compounds";
import { useSonification } from "@hooks/use-sonification";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { AGENT_NAMES, type AgentName } from "@lib/agent-identity";
import { confidenceZone } from "@lib/chromatics";
import { deriveLiveCognition, phaseLabel } from "@lib/cognition";
import type { Tier } from "@lib/confidence";
import { sonificationSupported } from "@lib/sonification";
import { useFirehoseStore } from "@state/firehose.store";
import { useThemeStore } from "@state/theme.store";
import { useQuery } from "@tanstack/react-query";
import { Volume2, VolumeX } from "lucide-react";
import { useMemo, useState } from "react";

/**
 * CortexBanner — the ambient hero of Mission Control (SENSORIUM "Quiet Cortex").
 *
 * Reads the system's state pre-attentively from one glance:
 *   • the Pulse — live decision cadence + aggregate confidence as colour temp;
 *   • the Council strip — the eight minds, rationed (quiet at rest, lit on
 *     activity), with honest health from `GET /api/v1/agents`;
 *   • a one-line situational read derived from the confidence zone (SA-L2).
 *
 * Signals come straight from the live firehose store + the agents query — no
 * new transport. Honest by construction: when nothing is flowing, the Pulse
 * shows "no signal" rather than a fabricated confident glow (P7).
 */

const RECENT_WINDOW_MS = 60_000;
const POSTURE_SAMPLE = 30;
const AGENT_SET: ReadonlySet<string> = new Set(AGENT_NAMES);

export function CortexBanner() {
  const decisions = useFirehoseStore((s) => s.decisions.items);
  const cognitionEvents = useFirehoseStore((s) => s.cognition.items);
  const theme = useThemeStore((s) => s.theme);
  const api = useSynapseApi();

  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.listAgents(),
    refetchInterval: 5_000,
  });

  const signal = useMemo(() => {
    const now = Date.now();

    // Rate = true decisions/min: count those timestamped within the last 60s.
    const inWindow = decisions.filter((d) => {
      const t = Date.parse(d.timestamp);
      return Number.isFinite(t) && now - t <= RECENT_WINDOW_MS;
    });
    const rate = inWindow.length;

    // Confidence posture + tier texture from the most recent decisions (by
    // arrival order — the firehose buffer is append-only). Reflects "how sure
    // the system has been", independent of the per-minute cadence.
    const posture = decisions.slice(-POSTURE_SAMPLE);
    const confidence =
      posture.length === 0
        ? null
        : posture.reduce((acc, d) => acc + d.confidence, 0) / posture.length;

    const tierMix: Partial<Record<Tier, number>> = {};
    for (const d of posture) tierMix[d.tier] = (tierMix[d.tier] ?? 0) + 1;

    // An agent is "active" if it proposed in any of the last few decisions.
    // ADR-044: the live envelope carries the lean `agents` summary (the full
    // proposals stay in the audit row).
    const activeAgents = new Set<AgentName>();
    for (const d of decisions.slice(-8)) {
      for (const a of d.agents) {
        if (AGENT_SET.has(a.agent_name)) {
          activeAgents.add(a.agent_name as AgentName);
        }
      }
    }

    return { rate, confidence, tierMix, activeAgents };
  }, [decisions]);

  // ADR-051: live council cognition (FSM phase events) — the strip shows the
  // agents thinking/debating in real time. Null when the stream is stale, so a
  // quiet council is never painted "live".
  const live = useMemo(() => deriveLiveCognition(cognitionEvents, Date.now()), [cognitionEvents]);

  const states = useMemo<Partial<Record<AgentName, CouncilAgentState>>>(() => {
    const out: Partial<Record<AgentName, CouncilAgentState>> = {};
    const data = agentsQuery.data?.agents as Record<string, AgentMetrics | string> | undefined;
    for (const name of AGENT_NAMES) {
      const raw = data?.[name];
      const metrics: AgentMetrics | undefined = typeof raw === "string" ? { status: raw } : raw;
      out[name] = {
        status: mapAgentHealth(metrics?.status),
        active: signal.activeAgents.has(name),
        latencyP99Ms: metrics?.latency_p99_ms ?? null,
        calibration90: metrics?.calibration_coverage_90 ?? null,
      };
    }
    return out;
  }, [agentsQuery.data, signal.activeAgents]);

  const read = useMemo(() => {
    if (signal.confidence === null) {
      return "Awaiting the first decisions — no live confidence signal yet.";
    }
    const zone = confidenceZone(signal.confidence);
    if (zone === "autonomous") return "Operating autonomously — confidence above the gate.";
    if (zone === "escalation") return "Confidence sitting on the I-5 gate — watch for escalations.";
    return "Confidence below the gate — human review likely.";
  }, [signal.confidence]);

  const activeCount = signal.activeAgents.size;

  // Opt-in ambient sonification (§5.4) — OFF by default; toggling is the user
  // gesture Web Audio requires. Hidden entirely where audio is unsupported.
  const [soundOn, setSoundOn] = useState(false);
  useSonification({ rate: signal.rate, confidence: signal.confidence ?? 0 }, soundOn);
  const canSonify = sonificationSupported();

  return (
    // The hero band (ADR-045): the Cortex IS the flagship — the breathing
    // pulse scaled up on the gradient void, the council row beside it.
    <section
      className="syn-hero grid items-center gap-6 p-6 lg:grid-cols-[300px_minmax(0,1fr)]"
      aria-label="Cortex — system pulse and agent council"
    >
      <div className="mx-auto">
        <Pulse
          rate={signal.rate}
          confidence={signal.confidence}
          tierMix={signal.tierMix}
          theme={theme}
        />
      </div>

      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <p className="text-sm text-ink">{read}</p>
            <p className="text-2xs uppercase tracking-wider text-ink-subtle">
              {live
                ? `Council ${phaseLabel(live.phase)}`
                : activeCount > 0
                  ? `${activeCount} of ${AGENT_NAMES.length} agents active`
                  : "Council quiet"}
            </p>
          </div>
          {canSonify && (
            <button
              type="button"
              onClick={() => setSoundOn((s) => !s)}
              aria-pressed={soundOn}
              aria-label={soundOn ? "Mute ambient pulse" : "Sonify ambient pulse"}
              title={soundOn ? "Mute ambient pulse" : "Sonify ambient pulse (opt-in)"}
              className="shrink-0 rounded-md border border-border p-1.5 text-ink-muted transition-colors duration-fast hover:bg-surface hover:text-ink focus-visible:shadow-focus"
            >
              {soundOn ? (
                <Volume2 size={14} aria-hidden="true" />
              ) : (
                <VolumeX size={14} aria-hidden="true" />
              )}
            </button>
          )}
        </div>
        <CouncilStrip states={states} liveStates={live?.agentStates} />
      </div>
    </section>
  );
}
