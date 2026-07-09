/**
 * Job_To_Be_Done — "catch a disruption before it cascades" (Requirement 3.1).
 *
 * The Operations_Controller is watching Mission Control when the harness
 * streams a seeded disruption alert. The terminal outcome is a contained
 * disruption — the operator perceives the alert and reaches its mitigation
 * (e.g. the affected route plan) before it cascades, rather than the alert
 * being lost in the firehose.
 */

import type { ScenarioDescriptor } from "./types";

export const CATCH_DISRUPTION: ScenarioDescriptor = {
  job: "catch-disruption-before-cascade",
  seed: 30505,
  setup: { seed: 30505, scenarioId: "jtbd.catch-disruption" },
  title: "Catch a disruption before it cascades",
  narrative:
    "While watching Mission Control, perceive a seeded streamed disruption alert and reach its mitigation (the affected route plan) before the disruption cascades.",
  expectedTerminalOutcome: {
    kind: "disruption-contained",
    surfaceId: "mission-control",
    surfacePath: "/",
    description:
      "The seeded disruption alert is perceived and its mitigation is reached before it cascades; the alert is not lost in the stream.",
  },
  seedSchemaIds: ["DisruptionAlert", "RoutePlan"],
};
