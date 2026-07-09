/**
 * Effectiveness_Harness — Resilience_Scenario registry (FE-WS-2, Req 6–10).
 *
 * `RESILIENCE_SCENARIOS` is the canonical, named list of adverse conditions the
 * harness drives (design "E2E — Resilience_Scenarios"). Task 7.1 seeds the
 * firehose stress scenario; later tasks (8.4, 9.3) push the reconnect/replay,
 * fault-transition, and scale scenarios into this same registry.
 *
 * Descriptors are validated at module load so a malformed or unbound scenario
 * fails fast rather than surfacing as an opaque E2E failure.
 */

import { hasSchema } from "../schema-registry";
import { FAULT_TRANSITIONS } from "./fault-transition";
import { FIREHOSE_STRESS } from "./firehose-stress";
import { RECONNECT_REPLAY } from "./reconnect-replay";
import { SCALE_VIRTUALIZATION } from "./scale-virtualization";
import { SCALE_MIN_ROWS } from "./resilience-types";
import type { ResilienceKind, ResilienceScenario } from "./resilience-types";

export type {
  ReconnectReplayPlan,
  ReplayRow,
  ReplayRowStatus,
  ResilienceKind,
  ResilienceScenario,
  StreamRateProfile,
  WebVitalsBudget,
} from "./resilience-types";
export { WEB_VITALS_BUDGET } from "./resilience-types";

/** Every registered Resilience_Scenario, ordered by requirement (6 → 9). */
export const RESILIENCE_SCENARIOS: readonly ResilienceScenario[] = [
  FIREHOSE_STRESS,
  RECONNECT_REPLAY,
  ...FAULT_TRANSITIONS,
  SCALE_VIRTUALIZATION,
];

// --- Load-time integrity checks (fail fast on a malformed/unbound scenario) ---

{
  const seenIds = new Set<string>();
  for (const s of RESILIENCE_SCENARIOS) {
    if (seenIds.has(s.id)) {
      throw new Error(`Duplicate Resilience_Scenario id: ${s.id}`);
    }
    seenIds.add(s.id);

    if (s.seedSchemaIds.length === 0) {
      throw new Error(`Resilience_Scenario ${s.id} declares no seed schema ids`);
    }
    const unbound = s.seedSchemaIds.filter((id) => !hasSchema(id));
    if (unbound.length > 0) {
      throw new Error(
        `Resilience_Scenario ${s.id} references unregistered schema id(s): ${unbound.join(", ")}`,
      );
    }

    // A firehose scenario must declare at least one streaming rate profile so
    // the realistic and adversarial rates it exercises stay named (Req 6.1).
    if (s.kind === "firehose-stress" && (!s.rates || s.rates.length === 0)) {
      throw new Error(`Firehose Resilience_Scenario ${s.id} declares no stream rate profiles`);
    }

    // A reconnect-replay scenario must script a drop / since_seq replay burst /
    // resumed live stream, and the replay burst must re-carry at least one
    // already-acted decision so the acted-never-reverted guarantee is exercised
    // deterministically (Req 7.5). `sinceSeq` must equal the highest pre-drop
    // sequence (the last applied sequence requested on reconnect — Req 7.1).
    if (s.kind === "reconnect-replay") {
      const plan = s.replay;
      if (!plan || plan.preDrop.length === 0 || plan.replay.length === 0 || plan.live.length === 0) {
        throw new Error(
          `Reconnect-replay Resilience_Scenario ${s.id} must script a non-empty pre-drop set, replay burst, and resumed live stream`,
        );
      }
      const actedSeqs = new Set(
        plan.preDrop.filter((r) => r.status === "acted").map((r) => r.seq),
      );
      if (actedSeqs.size === 0) {
        throw new Error(
          `Reconnect-replay Resilience_Scenario ${s.id} must pre-act at least one decision so the replay burst can carry an already-acted decision (Req 7.5)`,
        );
      }
      const replaysAnActedDecision = plan.replay.some((r) => actedSeqs.has(r.seq));
      if (!replaysAnActedDecision) {
        throw new Error(
          `Reconnect-replay Resilience_Scenario ${s.id} replay burst must re-carry at least one already-acted decision (Req 7.5)`,
        );
      }
      const highestPreDropSeq = Math.max(...plan.preDrop.map((r) => r.seq));
      if (plan.sinceSeq !== highestPreDropSeq) {
        throw new Error(
          `Reconnect-replay Resilience_Scenario ${s.id} since_seq (${plan.sinceSeq}) must equal the highest pre-drop sequence (${highestPreDropSeq}) requested on reconnect (Req 7.1)`,
        );
      }
    }

    // A fault-transition scenario must declare a non-empty fault chain so its
    // transitions and their expected distinct rendered outcomes stay named and
    // testable, and never latch on a prior state (Req 8.6).
    if (s.kind === "fault-transition" && (!s.faultChain || s.faultChain.length === 0)) {
      throw new Error(`Fault-transition Resilience_Scenario ${s.id} declares no fault chain`);
    }

    // A scale scenario must seed at least 10,000 rows so virtualization is
    // proven against a genuinely large dataset, not asserted by inspection
    // (Req 9.1, 9.5).
    if (
      s.kind === "scale-virtualization" &&
      (s.seedRowCount === undefined || s.seedRowCount < SCALE_MIN_ROWS)
    ) {
      throw new Error(
        `Scale Resilience_Scenario ${s.id} must seed at least ${SCALE_MIN_ROWS} rows (declared ${String(
          s.seedRowCount,
        )})`,
      );
    }
  }
}

/** The Resilience_Scenario with the given id, or `undefined` when none is registered. */
export function getResilienceScenario(id: string): ResilienceScenario | undefined {
  return RESILIENCE_SCENARIOS.find((s) => s.id === id);
}

/** Every Resilience_Scenario of a given kind. */
export function resilienceScenariosOfKind(kind: ResilienceKind): readonly ResilienceScenario[] {
  return RESILIENCE_SCENARIOS.filter((s) => s.kind === kind);
}
