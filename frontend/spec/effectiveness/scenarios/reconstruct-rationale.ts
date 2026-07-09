/**
 * Job_To_Be_Done — "reconstruct a decision's rationale" (Requirement 3.1).
 *
 * The Analyst opens the Decision Theater on a seeded decision and reconstructs
 * why it was made — the proposals, the debate, the selected action, and the
 * executor confirmations — reaching the terminal outcome that the decision's
 * rationale is fully reconstructed from its replay.
 */

import type { ScenarioDescriptor } from "./types";

export const RECONSTRUCT_RATIONALE: ScenarioDescriptor = {
  job: "reconstruct-decision-rationale",
  seed: 30303,
  setup: { seed: 30303, scenarioId: "jtbd.reconstruct-rationale" },
  title: "Reconstruct a decision's rationale",
  narrative:
    "Open the Decision Theater on a seeded decision and replay its tribunal — proposals, debate, selection, and executor confirmations — to reconstruct why the decision was made.",
  expectedTerminalOutcome: {
    kind: "rationale-reconstructed",
    surfaceId: "decision-theater",
    surfacePath: "/decisions",
    description:
      "The seeded decision's rationale is reconstructed from its replay — the selected action and the reasoning that produced it are reachable.",
  },
  seedSchemaIds: ["DecisionDetailResponse", "ConsensusDecision", "DecisionEnvelope"],
};
