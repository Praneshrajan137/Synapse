import type { AgentMetrics } from "@domain/agent-health";
import { type CouncilAgentState, CouncilStrip, Pulse, mapAgentHealth } from "@ds/compounds";
import { useSynapseApi } from "@hooks/use-synapse-api";
import { AGENT_NAMES, type AgentName } from "@lib/agent-identity";
import { confidenceZone } from "@lib/chromatics";
import type { Tier } from "@lib/confidence";
import { useFirehoseStore } from "@state/firehose.store";
import { useThemeStore } from "@state/theme.store";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

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
    const activeAgents = new Set<AgentName>();
    for (const d of decisions.slice(-8)) {
      for (const p of d.proposals ?? []) {
        if (p.agent_name && AGENT_SET.has(p.agent_name)) {
          activeAgents.add(p.agent_name as AgentName);
        }
      }
    }

    return { rate, confidence, tierMix, activeAgents };
  }, [decisions]);

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

  return (
    <section
      className="syn-card-raised grid items-center gap-5 p-5 lg:grid-cols-[240px_minmax(0,1fr)]"
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
        <div className="space-y-1">
          <p className="text-sm text-ink">{read}</p>
          <p className="text-2xs uppercase tracking-wider text-ink-subtle">
            {activeCount > 0
              ? `${activeCount} of ${AGENT_NAMES.length} agents active`
              : "Council quiet"}
          </p>
        </div>
        <CouncilStrip states={states} />
      </div>
    </section>
  );
}
