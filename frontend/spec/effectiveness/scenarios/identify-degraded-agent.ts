/**
 * Job_To_Be_Done — "identify which agent degraded and why" (Requirement 3.1).
 *
 * The Analyst opens the Agent Council on a seeded fleet where one agent is
 * unhealthy, and reaches the correct terminal outcome: the specific degraded
 * agent is identified together with the cause of its degradation (rather than
 * a false-healthy fleet view).
 */

import type { ScenarioDescriptor } from "./types";

export const IDENTIFY_DEGRADED_AGENT: ScenarioDescriptor = {
  job: "identify-degraded-agent",
  seed: 30202,
  setup: { seed: 30202, scenarioId: "jtbd.identify-degraded-agent" },
  title: "Identify which agent degraded and why",
  narrative:
    "Open the Agent Council on a seeded fleet with one degraded agent and drill into its health to identify the specific agent and the cause of its degradation.",
  expectedTerminalOutcome: {
    kind: "degraded-agent-identified",
    surfaceId: "agent-council",
    surfacePath: "/agents",
    description:
      "The specific seeded degraded agent is identified and its degradation cause is surfaced; the fleet is not shown as false-healthy.",
  },
  seedSchemaIds: ["AgentHealthResponse", "SystemPosture"],
};
