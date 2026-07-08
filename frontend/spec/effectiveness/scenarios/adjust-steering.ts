/**
 * Job_To_Be_Done — "adjust steering safely" (Requirement 3.1).
 *
 * The Operations_Controller opens the Steering Surface on a seeded posture,
 * changes a weight/threshold, and commits it. The terminal outcome is a safely
 * adjusted steering configuration — the change is validated and committed
 * without leaving the operator in a non-recoverable or unconfirmed state.
 */

import type { ScenarioDescriptor } from "./types";

export const ADJUST_STEERING: ScenarioDescriptor = {
  job: "adjust-steering-safely",
  seed: 30404,
  setup: { seed: 30404, scenarioId: "jtbd.adjust-steering" },
  title: "Adjust steering safely",
  narrative:
    "Open the Steering Surface on a seeded posture, adjust a weight/threshold, and commit the change so steering is updated safely with confirmation.",
  expectedTerminalOutcome: {
    kind: "steering-adjusted",
    surfaceId: "steering",
    surfacePath: "/steering",
    description:
      "The seeded steering weight/threshold change is validated and committed with confirmation; no unconfirmed or non-recoverable state is left behind.",
  },
  seedSchemaIds: ["SteeringResponse"],
};
