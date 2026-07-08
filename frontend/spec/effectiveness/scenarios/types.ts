/**
 * Effectiveness_Harness — Jobs-To-Be-Done scenario descriptor types.
 *
 * These are the shared, transport-free types that describe an operator's
 * end-to-end objective (a Job_To_Be_Done) and the seeded harness scenario that
 * exercises it. They are the single source of truth the Task_Completion_Tests
 * (`frontend/tests/e2e/*.jtbd.spec.ts`, task 3.2) drive against, so the set of
 * jobs and their expected terminal outcomes stay named and testable rather than
 * hand-kept per test (design "C. Harness — JTBD scenario descriptors +
 * Task_Completion_Test harness"; Requirements 3.1, 3.3).
 *
 * `HarnessOptions` is defined here (rather than in `browser-worker.ts`) so the
 * scenario descriptors are self-contained and type-check without the browser
 * worker present; the MSW browser worker (task 2.1) imports this shape.
 */

import type { JobToBeDone } from "@lib/effectiveness-scorecard";

import type { SchemaId } from "../schema-registry";

/**
 * The named set of operator objectives the Console must support, measured for
 * task completion. Covers, at minimum, the five jobs enumerated by Requirement
 * 3.1: resolve an escalation correctly, identify which agent degraded and why,
 * reconstruct a decision's rationale, adjust steering safely, and catch a
 * disruption before it cascades.
 *
 * Re-exported from the shipped `@lib/effectiveness-scorecard` so the enumerated
 * jobs have exactly one source of truth shared by the harness and the
 * Effectiveness_Scorecard/ratchet.
 */
export type { JobToBeDone };

/**
 * The classes of correct terminal state a Task_Completion_Test must reach for
 * its seeded scenario. A test fails if the terminal outcome is wrong or
 * unreachable (Requirement 3.3), so each kind names a concrete, assertable end
 * state rather than "the route rendered".
 */
export type TerminalOutcomeKind =
  | "escalation-resolved"
  | "degraded-agent-identified"
  | "rationale-reconstructed"
  | "steering-adjusted"
  | "disruption-contained";

/**
 * The correct terminal outcome a correct operator path must reach for a seeded
 * scenario (Requirement 3.3). `surfaceId`/`surfacePath` mirror the primary
 * Surface registry (`@app/primary-surfaces`) so a Task_Completion_Test knows
 * where the terminal state is verified, and `description` states the assertable
 * end condition in plain language.
 */
export interface TerminalOutcome {
  /** The class of terminal state (drives the e2e assertion in task 3.2). */
  readonly kind: TerminalOutcomeKind;
  /** Primary-Surface id where the terminal outcome is verified. */
  readonly surfaceId: string;
  /** react-router path of that Surface (mirrors `PRIMARY_SURFACES`). */
  readonly surfacePath: string;
  /** The assertable end condition, in plain language. */
  readonly description: string;
}

/**
 * The options a Task_Completion_Test passes to the Effectiveness_Harness to
 * start a seeded run. `seed` fixes byte-identical fixtures and stream order
 * (Requirement 1.3); `scenarioId` names the seeded scenario the harness serves.
 */
export interface HarnessOptions {
  readonly seed: number;
  readonly scenarioId: string;
}

/**
 * A single Job_To_Be_Done bound to a seeded harness scenario. This is the
 * `ScenarioDescriptor` from design section C, extended with `title` and
 * `narrative` for traceability and `seedSchemaIds` so each scenario is
 * concretely bound to the fixtures the harness must serve (each Domain_Schema
 * id resolves in the shared `DOMAIN_SCHEMA_REGISTRY`).
 */
export interface ScenarioDescriptor {
  /** The operator objective this scenario measures. */
  readonly job: JobToBeDone;
  /** Deterministic seed; equal to `setup.seed` by construction. */
  readonly seed: number;
  /** Harness start options for this scenario. */
  readonly setup: HarnessOptions;
  /** The correct terminal outcome a correct operator path must reach. */
  readonly expectedTerminalOutcome: TerminalOutcome;
  /** Short human title for reports and the scorecard. */
  readonly title: string;
  /** One-sentence description of the operator's path. */
  readonly narrative: string;
  /**
   * The Domain_Schema ids whose fixtures/streams the harness must seed for this
   * scenario. Every id here must resolve in the shared schema registry (asserted
   * at module load in `index.ts`), binding the scenario to contract-accurate
   * fixtures (Requirement 2.2).
   */
  readonly seedSchemaIds: readonly SchemaId[];
}
