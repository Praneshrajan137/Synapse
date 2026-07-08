/**
 * Effectiveness_Harness — Jobs-To-Be-Done scenario registry.
 *
 * `SCENARIOS` is the canonical, named list of operator Jobs-To-Be-Done bound to
 * seeded harness scenarios (design "C. Harness — JTBD scenario descriptors";
 * Requirement 3.1). It enumerates, at minimum, the five required jobs: resolve
 * an escalation correctly, identify which agent degraded and why, reconstruct a
 * decision's rationale, adjust steering safely, and catch a disruption before
 * it cascades.
 *
 * The Task_Completion_Tests (task 3.2) iterate this registry; the descriptors
 * are validated at module load so a malformed or unbound scenario fails fast
 * rather than surfacing as an opaque e2e failure.
 */

import { hasSchema } from "../schema-registry";
import { ADJUST_STEERING } from "./adjust-steering";
import { CATCH_DISRUPTION } from "./catch-disruption";
import { IDENTIFY_DEGRADED_AGENT } from "./identify-degraded-agent";
import { RECONSTRUCT_RATIONALE } from "./reconstruct-rationale";
import { RESOLVE_ESCALATION } from "./resolve-escalation";
import type { JobToBeDone, ScenarioDescriptor } from "./types";

export type { JobToBeDone, ScenarioDescriptor, TerminalOutcome, TerminalOutcomeKind, HarnessOptions } from "./types";

/**
 * The five minimum Jobs-To-Be-Done required by Requirement 3.1. Used to assert
 * SCENARIOS covers at least this set at module load.
 */
export const REQUIRED_JOBS: readonly JobToBeDone[] = [
  "resolve-escalation-correctly",
  "identify-degraded-agent",
  "reconstruct-decision-rationale",
  "adjust-steering-safely",
  "catch-disruption-before-cascade",
];

/**
 * Every enumerated Job_To_Be_Done bound to a seeded harness scenario (min 5,
 * Requirement 3.1). Ordered by the operator loop: Intervene → Investigate →
 * Configure → Monitor.
 */
export const SCENARIOS: readonly ScenarioDescriptor[] = [
  RESOLVE_ESCALATION,
  IDENTIFY_DEGRADED_AGENT,
  RECONSTRUCT_RATIONALE,
  ADJUST_STEERING,
  CATCH_DISRUPTION,
];

// --- Load-time integrity checks (fail fast on a malformed/unbound scenario) ---

// 1. Every required job is enumerated (Requirement 3.1, "at minimum").
{
  const jobs = new Set(SCENARIOS.map((s) => s.job));
  const missing = REQUIRED_JOBS.filter((j) => !jobs.has(j));
  if (missing.length > 0) {
    throw new Error(`SCENARIOS is missing required Jobs-To-Be-Done: ${missing.join(", ")}`);
  }
}

// 2. Scenario ids and jobs are unique (one seeded scenario per job).
{
  const seenIds = new Set<string>();
  const seenJobs = new Set<JobToBeDone>();
  for (const s of SCENARIOS) {
    if (seenIds.has(s.setup.scenarioId)) {
      throw new Error(`Duplicate scenarioId: ${s.setup.scenarioId}`);
    }
    if (seenJobs.has(s.job)) {
      throw new Error(`Duplicate Job_To_Be_Done: ${s.job}`);
    }
    seenIds.add(s.setup.scenarioId);
    seenJobs.add(s.job);
  }
}

// 3. Each descriptor is internally consistent and bound to the schema registry
//    (seed matches setup.seed; every seed schema id resolves — Requirement 2.2).
for (const s of SCENARIOS) {
  if (s.seed !== s.setup.seed) {
    throw new Error(`Scenario ${s.setup.scenarioId} seed (${s.seed}) !== setup.seed (${s.setup.seed})`);
  }
  if (s.seedSchemaIds.length === 0) {
    throw new Error(`Scenario ${s.setup.scenarioId} declares no seed schema ids`);
  }
  const unbound = s.seedSchemaIds.filter((id) => !hasSchema(id));
  if (unbound.length > 0) {
    throw new Error(
      `Scenario ${s.setup.scenarioId} references unregistered schema id(s): ${unbound.join(", ")}`,
    );
  }
}

/** The scenario for a given Job_To_Be_Done, or `undefined` when none is registered. */
export function getScenario(job: JobToBeDone): ScenarioDescriptor | undefined {
  return SCENARIOS.find((s) => s.job === job);
}
