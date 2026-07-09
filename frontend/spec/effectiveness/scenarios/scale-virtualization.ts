/**
 * Resilience_Scenario — scale virtualization (Req 9).
 *
 * The harness seeds a dataset of at least {@link SCALE_MIN_ROWS} (10,000) audit
 * rows for BOTH the Audit Vault (`/audit`) and the Decision Theater
 * (`/decisions`) — both surfaces read the same `AuditListResponse` payload via
 * `listRecentDecisions` (design "H. surfaces — virtualization retrofit"). The
 * scenario proves three guarantees against a genuinely large dataset rather
 * than by inspection (Req 9.5):
 *
 *   - Req 9.1 — row virtualization is actually engaged: the count of mounted
 *     row nodes stays bounded and far below the total row count, independent of
 *     how many rows load (the pure bound is proven by the `virtual-window`
 *     property test, task 10.2; the E2E asserts it against the rendered DOM).
 *   - Req 9.2 — scroll and interaction responsiveness stays within the
 *     Web_Vitals_Budget (INP ≤ 200 ms) while the 10k-row dataset is displayed.
 *   - Req 9.3 — the full seeded row set is reachable by scrolling; no fixed row
 *     cap (the retrofit removed the `limit: 200` / `limit: 100` query caps) hides
 *     rows from the operator.
 *
 * The seed fixes byte-identical fixtures (Req 1.3) so the E2E is deterministic;
 * a scrolled-in row aligns to its seeded fixture at its index (Req 9.4).
 */

import {
  SCALE_MIN_ROWS,
  WEB_VITALS_BUDGET,
  type ResilienceScenario,
} from "./resilience-types";

export const SCALE_VIRTUALIZATION: ResilienceScenario = {
  id: "resilience.scale-virtualization",
  kind: "scale-virtualization",
  seed: 90901,
  title: "Scale virtualization at 10k+ rows",
  narrative:
    "Seed at least 10,000 audit rows for both the Audit Vault and the Decision Theater; row virtualization stays engaged so the count of mounted row nodes stays bounded far below the total, the full seeded set is reachable by scrolling (no fixed row cap), each scrolled-in row aligns to its seeded fixture, and scroll/interaction INP stays within the Web_Vitals_Budget (≤ 200 ms).",
  budget: WEB_VITALS_BUDGET,
  // Both /audit and /decisions render the same `listRecentDecisions`
  // (`AuditListResponse`) payload, so a single seeded response schema covers
  // both surfaces (design "H").
  seedSchemaIds: ["AuditListResponse"],
  seedRowCount: SCALE_MIN_ROWS,
};
