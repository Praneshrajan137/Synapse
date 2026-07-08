/**
 * Resilience_Scenario — firehose stress (Req 6).
 *
 * The harness streams decision/disruption/route messages at a realistic rate
 * and then an adversarial burst on the same channels Mission Control consumes.
 * The scenario proves four guarantees under sustained load:
 *
 *   - INP stays within the Web_Vitals_Budget (≤ 200 ms) — Req 6.1.
 *   - Retained messages stay within the per-channel bounded Ring_Buffer cap
 *     regardless of how many arrive — Req 6.2 (asserted at the model level by
 *     the ring-buffer property test, task 7.2).
 *   - Already-rendered content is not reflowed or reordered into dropped-frame
 *     jank — Req 6.4.
 *   - When the firehose ends, the final state is consistent with the applied
 *     (deduplicated) message set — no lost, no double-counted items — Req 6.5
 *     (at-most-once application via `applyOnce`, tested by task 7.3).
 *
 * The channel caps under stress are the runtime caps unchanged by this work:
 * decisions/routes/pricing/freshness/cognition = 200, disruptions = 50,
 * twin = 100, demand = 500 (`state/firehose.store.ts`, FE-INV-017).
 */

import { WEB_VITALS_BUDGET, type ResilienceScenario } from "./resilience-types";

export const FIREHOSE_STRESS: ResilienceScenario = {
  id: "resilience.firehose-stress",
  kind: "firehose-stress",
  seed: 60601,
  title: "Firehose stress at realistic and adversarial rates",
  narrative:
    "Stream decision/disruption/route messages at a realistic rate then an adversarial burst on the Mission Control channels; INP stays within the Web_Vitals_Budget, already-rendered content does not reflow/reorder into jank, retained messages stay within the bounded Ring_Buffer cap, and the final state matches the deduplicated applied message set with no lost or double-counted items.",
  budget: WEB_VITALS_BUDGET,
  seedSchemaIds: ["DecisionEnvelope", "DisruptionAlert", "RoutePlan"],
  rates: [
    // Realistic: a busy but ordinary surge — a few messages a second per channel.
    { label: "realistic", messagesPerSecond: 20, durationMs: 3_000 },
    // Adversarial: a burst well past any channel cap so eviction and the INP
    // budget are both exercised under pressure.
    { label: "adversarial", messagesPerSecond: 500, durationMs: 2_000 },
  ],
};
