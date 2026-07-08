/**
 * Job_To_Be_Done — "resolve an escalation correctly" (Requirement 3.1).
 *
 * The On_Call_Responder opens the Override Cockpit on a seeded live escalation,
 * reviews the decision and its violations, and commits the correct override.
 * The terminal outcome is a resolved escalation whose override wrote the audit
 * row BEFORE the decision was marked acted (audit-row-first, Requirement 3.5),
 * verified through the Effectiveness_Harness in task 3.2.
 */

import type { ScenarioDescriptor } from "./types";

export const RESOLVE_ESCALATION: ScenarioDescriptor = {
  job: "resolve-escalation-correctly",
  seed: 30101,
  setup: { seed: 30101, scenarioId: "jtbd.resolve-escalation" },
  title: "Resolve an escalation correctly",
  narrative:
    "Open the Override Cockpit on a seeded escalation, review the decision and its violations, and commit the correct override so the escalation is resolved audit-row-first.",
  expectedTerminalOutcome: {
    kind: "escalation-resolved",
    surfaceId: "override-cockpit",
    surfacePath: "/cockpit",
    description:
      "The seeded escalation is resolved with the correct override action, and the audit row is committed before the decision is marked acted.",
  },
  seedSchemaIds: ["EscalationMessage", "DecisionEnvelope", "OverrideApiResponse", "AuditListResponse"],
};
