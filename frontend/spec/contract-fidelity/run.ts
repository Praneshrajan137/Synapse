/**
 * Contract Fidelity Suite — drift report generator + CI gate.
 *
 * This is the runnable harness (Output stage) of the Contract Fidelity Suite
 * (design "Contract Fidelity Suite", Requirements 1.1, 1.3, 1.5, 1.6, 2.3,
 * 3.8). It composes the three suite inputs — the entitlement manifest
 * (`entitlements.ts` + `channels.ts`), the introspected Console surface
 * (`introspect.ts`), and the backend contract (live `/openapi.json` with a
 * checked-in snapshot fallback) — through the pure classifiers in
 * `@lib/contract-coverage` and emits:
 *
 *   • `drift-report.json`  — the machine-readable {@link DriftReport}.
 *   • `drift-report.md`    — a human-readable summary enumerating every HTTP
 *     endpoint, WebSocket channel, and SSE stream with its Coverage_Status,
 *     missing-field / over-strict drift, and the backend gaps (agent-state,
 *     oversight).
 *
 * The process exits non-zero and NAMES the specific endpoint/channel when any
 * *entitled* capability is `uncovered` or `partial`; capabilities marked
 * out-of-scope NEVER trigger a failure (Requirements 1.6).
 *
 * Run: `pnpm contract:drift` (from `frontend/`) — or
 *      `tsx spec/contract-fidelity/run.ts`. Point it at a live gateway with
 *      `SYNAPSE_GATEWAY_URL=https://gateway.example tsx …` to diff against the
 *      live `/openapi.json`; otherwise it uses the checked-in snapshot and runs
 *      deterministically offline / in CI.
 *
 * ── Backend-gap modeling (Requirements 2.3, 3.8) ────────────────────────────
 * Two backend-gap catalogs are declared here, minimally and declaratively,
 * because the full backend event/affordance catalog is not machine-introspectable
 * from the Console repo:
 *
 *   • Agent-state gaps (Req 2.3): every `AgentState` in the canonical model
 *     (`@domain/agent-state`) is checked against the set of states that a real
 *     backend Cognition Channel event can back (derived from the ADR-051
 *     cognition FSM phases + per-agent events in `@domain/cognition-event`).
 *     A state with no backing event is recorded as an `agent-state` gap so the
 *     AUX layer renders it `unavailable` rather than fabricating activity.
 *
 *   • Oversight gaps (Req 3.8): every operator agent-action affordance
 *     (interrupt / recover / delegate / override / steer) is checked for a
 *     backing backend endpoint drawn from the entitlement manifest. An
 *     agent-action affordance with a `null` backing endpoint is recorded as an
 *     `oversight` gap. Pure UI navigation affordances (escalate-next/prev,
 *     dismiss) are client-only and are intentionally not gap-checked.
 *
 * Both catalogs are the single source the AUX / Oversight layers consume when
 * those surfaces land (tasks 5.x, 7.x); keeping them here lets the drift report
 * surface the gaps today without waiting on the UI components.
 */

import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { AGENT_STATES, type AgentState } from "@domain/agent-state";
import { CognitionPhaseSchema } from "@domain/cognition-event";
import {
  classifyCoverage,
  diffContractFields,
} from "@lib/contract-coverage";
import { UPLIFT_BACKEND_GAP } from "@lib/uplift-slot";

import {
  ALL_ENTITLEMENTS,
  CLIENT_METHOD_REGISTRY,
  DOMAIN_SCHEMA_REGISTRY,
  extractContractFields,
  introspectConsole,
  loadBackendContract,
  schemaFieldNames,
  verifyClientMethodRegistry,
} from "./introspect";
import {
  resolveSchemaLess,
  SCHEMA_LESS_RESOLUTIONS,
  trackedPartialIds,
  type SchemaLessResolutionResult,
} from "./schema-less";
import type {
  CapabilityEntitlement,
  ConsoleCapability,
  CoverageRow,
  CoverageStatus,
  DriftReport,
  SchemaLessResolution,
} from "./types";

// ─────────────────────────────────────────────────────────────────────────
// Backend-gap catalog #1 — agent-state ↔ cognition-event backing (Req 2.3)
// ─────────────────────────────────────────────────────────────────────────

/**
 * Which canonical {@link AgentState}s a real backend Cognition Channel event
 * can back, keyed by the ADR-051 cognition FSM phase that emits it (see
 * `@domain/cognition-event` `CognitionPhaseSchema` + the per-agent `event`
 * field). This is the minimal, declarative model of the backend event catalog
 * the suite has access to from the Console repo. Any `AgentState` NOT reachable
 * from this map (nor from a per-agent event below) is a backend gap: the
 * backend emits no event that maps to it, so the AUX layer must render it
 * `unavailable` rather than invent activity (Req 2.2/2.3).
 */
const COGNITION_PHASE_STATES: Record<string, readonly AgentState[]> = {
  collecting: ["thinking", "searching", "planning", "waiting"],
  debating: ["uncertain", "asking", "delegating"],
  arbitrating: ["confident", "escalating"],
  executing: ["acting", "streaming", "handing-off"],
  learning: ["recovering", "completing", "succeeding"],
};

/**
 * States backed by a per-agent Cognition event (`event` field on a collect
 * event) rather than a phase transition: a `"failed"` agent event backs the
 * `failing` state.
 */
const COGNITION_EVENT_STATES: readonly AgentState[] = ["failing"];

/**
 * Compute the agent-state backend gaps: canonical states with no backing
 * cognition event. Validates the phase keys against `CognitionPhaseSchema` so
 * the catalog can never silently drift from the real FSM phase enum.
 */
function agentStateGaps(): AgentState[] {
  // Fail loudly if the declared phase catalog no longer matches the FSM enum.
  for (const phase of Object.keys(COGNITION_PHASE_STATES)) {
    CognitionPhaseSchema.parse(phase);
  }

  const backed = new Set<AgentState>();
  for (const states of Object.values(COGNITION_PHASE_STATES)) {
    for (const state of states) backed.add(state);
  }
  for (const state of COGNITION_EVENT_STATES) backed.add(state);

  return AGENT_STATES.filter((state) => !backed.has(state));
}

// ─────────────────────────────────────────────────────────────────────────
// Backend-gap catalog #2 — oversight affordance ↔ backing endpoint (Req 3.8)
// ─────────────────────────────────────────────────────────────────────────

/**
 * An operator oversight affordance and its backing backend endpoint. An
 * `agentAction` affordance (interrupt / recover / delegate / override / steer)
 * with a `null` backing endpoint is a backend gap (Req 3.8). Pure UI navigation
 * affordances (`agentAction: false`) are client-only and never gap-checked.
 */
interface OversightAffordance {
  readonly id: string;
  readonly agentAction: boolean;
  /** Entitled capabilityId that backs this affordance, or null when none exists. */
  readonly backingCapabilityId: string | null;
}

/**
 * The oversight affordance catalog (design "Oversight Controls",
 * `OversightCapability`). `override` and `steer` have backing endpoints in the
 * entitlement manifest; `interrupt`, `recover`, and `delegate` are in-flight
 * agent-action affordances the backend exposes no endpoint for → backend gaps.
 */
const OVERSIGHT_AFFORDANCES: readonly OversightAffordance[] = [
  {
    id: "override",
    agentAction: true,
    backingCapabilityId: "decisions.POST./api/v1/decisions/{decision_id}/override",
  },
  { id: "steer", agentAction: true, backingCapabilityId: "steering.POST./api/v1/steering" },
  { id: "interrupt", agentAction: true, backingCapabilityId: null },
  { id: "recover", agentAction: true, backingCapabilityId: null },
  { id: "delegate", agentAction: true, backingCapabilityId: null },
  // Client-only navigation affordances — not backed by (and not needing) an endpoint.
  { id: "escalate-next", agentAction: false, backingCapabilityId: null },
  { id: "escalate-prev", agentAction: false, backingCapabilityId: null },
  { id: "dismiss", agentAction: false, backingCapabilityId: null },
];

const ENTITLED_CAPABILITY_IDS: ReadonlySet<string> = new Set(
  ALL_ENTITLEMENTS.filter((e) => e.entitled).map((e) => e.capabilityId),
);

/**
 * Compute the oversight backend gaps: agent-action affordances whose backing
 * endpoint is null OR is not an entitled capability the Console can reach.
 */
function oversightGaps(): string[] {
  return OVERSIGHT_AFFORDANCES.filter((a) => a.agentAction)
    .filter(
      (a) =>
        a.backingCapabilityId === null || !ENTITLED_CAPABILITY_IDS.has(a.backingCapabilityId),
    )
    .map((a) => a.id);
}

// ─────────────────────────────────────────────────────────────────────────
// Backend-gap catalog #3 — system-level uplift measure (Req 17.3, 17.4)
// ─────────────────────────────────────────────────────────────────────────

/**
 * Compute the uplift backend gap: the Backend_Contract exposes NO system-level
 * uplift measure today (a Cross_Boundary_Dependency), so the Operations uplift
 * slot renders "awaiting uplift measure" and this gap is recorded rather than
 * the slot being hidden or a value fabricated (Req 17.3, 17.4). The
 * capability is not machine-introspectable from the Console repo, so — like the
 * agent-state and oversight catalogs above — it is modeled declaratively via
 * {@link UPLIFT_BACKEND_GAP} (the single source the surface consumes too).
 */
function upliftGaps(): string[] {
  return [UPLIFT_BACKEND_GAP.name];
}

// ─────────────────────────────────────────────────────────────────────────
// Coverage row assembly
// ─────────────────────────────────────────────────────────────────────────

/** capabilityId → the `schemaId` its client method validates responses with. */
const SCHEMA_ID_BY_CAPABILITY: ReadonlyMap<string, string | null> = new Map(
  CLIENT_METHOD_REGISTRY.map((entry) => [entry.capabilityId, entry.schemaId]),
);

const ENTITLEMENT_BY_ID: ReadonlyMap<string, CapabilityEntitlement> = new Map(
  ALL_ENTITLEMENTS.map((e) => [e.capabilityId, e]),
);

/**
 * Build one {@link CoverageRow} per entitlement: classify coverage, and for
 * HTTP capabilities with both a contract field set and a registered domain
 * schema, compute the missing-field / over-strict field diff (Req 1.3).
 *
 *  • `missingFields`    = contractFields − allSchemaFields   (contract field the schema omits)
 *  • `overStrictFields` = requiredSchemaFields − contractFields (schema demands a field the contract lacks)
 */
function buildRows(
  consoleCaps: readonly ConsoleCapability[],
  contractFieldsById: ReadonlyMap<string, readonly string[]>,
): CoverageRow[] {
  const consoleById = new Map(consoleCaps.map((c) => [c.capabilityId, c]));

  return ALL_ENTITLEMENTS.map((entitlement) => {
    const consoleCapability = consoleById.get(entitlement.capabilityId);
    if (!consoleCapability) {
      throw new Error(`introspectConsole produced no record for ${entitlement.capabilityId}`);
    }

    const status = classifyCoverage(entitlement, consoleCapability);

    let missingFields: readonly string[] = [];
    let overStrictFields: readonly string[] = [];

    const contractFields = contractFieldsById.get(entitlement.capabilityId);
    const schemaId = SCHEMA_ID_BY_CAPABILITY.get(entitlement.capabilityId) ?? null;
    if (entitlement.kind === "http" && contractFields && schemaId) {
      const schema = DOMAIN_SCHEMA_REGISTRY[schemaId];
      if (schema) {
        const allSchemaFields = schemaFieldNames(schema);
        const requiredSchemaFields = schemaFieldNames(schema, true);
        missingFields = diffContractFields(contractFields, allSchemaFields).missingFields;
        overStrictFields = diffContractFields(contractFields, requiredSchemaFields).overStrictFields;
      }
    }

    return { capabilityId: entitlement.capabilityId, status, missingFields, overStrictFields };
  });
}

/**
 * Fold the schema-less classification into the base coverage rows (Req 16.2):
 * a schema-less capability classified `no-body-open-shape-covered` is promoted
 * from `partial` to `covered`, so the absence of a response schema no longer
 * fails the gate. A `tracked-partial` capability stays `partial` (it is
 * honestly not fully covered) but is excluded from the failure decision by
 * {@link computeGatedFailure}. An unclassified schema-less capability stays
 * `partial` and fails.
 */
function applySchemaLessResolution(
  rows: readonly CoverageRow[],
  result: SchemaLessResolutionResult,
): CoverageRow[] {
  const resolvedById = new Map(result.rows.map((r) => [r.capabilityId, r]));
  return rows.map((row) => {
    const resolved = resolvedById.get(row.capabilityId);
    if (!resolved) return row;
    return { ...row, status: resolved.status };
  });
}

/**
 * Compute the drift `failed` flag with schema-less tracking applied (Req 16.4):
 * fail iff some entitled row is `uncovered` or `partial` AND is not a tracked
 * schema-less capability. `tracked-partial` rows are excluded (tracked with a
 * named rationale, not an untracked failure — Req 16.3); unclassified
 * schema-less rows are NOT excluded, so a new unresolved capability still fails
 * and is named (Req 16.5).
 */
function computeGatedFailure(
  rows: readonly CoverageRow[],
  trackedIds: ReadonlySet<string>,
): boolean {
  return rows.some(
    (row) =>
      (row.status === "uncovered" || row.status === "partial") &&
      !trackedIds.has(row.capabilityId),
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Human-readable summary
// ─────────────────────────────────────────────────────────────────────────

interface CoverageCounts {
  covered: number;
  partial: number;
  uncovered: number;
  "out-of-scope": number;
}

function countByStatus(rows: readonly CoverageRow[]): CoverageCounts {
  const counts: CoverageCounts = { covered: 0, partial: 0, uncovered: 0, "out-of-scope": 0 };
  for (const row of rows) counts[row.status] += 1;
  return counts;
}

const STATUS_MARK: Record<CoverageStatus, string> = {
  covered: "✅ covered",
  partial: "⚠️  partial",
  uncovered: "❌ uncovered",
  "out-of-scope": "➖ out-of-scope",
};

function refOf(capabilityId: string): string {
  const entitlement = ENTITLEMENT_BY_ID.get(capabilityId);
  if (!entitlement) return capabilityId;
  const method = capabilityId.split(".")[1] ?? "";
  return `${method} ${entitlement.ref}`;
}

function renderRow(row: CoverageRow): string {
  const lines = [`- ${STATUS_MARK[row.status]} — \`${refOf(row.capabilityId)}\` (${row.capabilityId})`];
  if (row.missingFields.length > 0) {
    lines.push(`    · missing-field drift (in contract, absent from schema): ${row.missingFields.join(", ")}`);
  }
  if (row.overStrictFields.length > 0) {
    lines.push(`    · over-strict drift (required by schema, absent from contract): ${row.overStrictFields.join(", ")}`);
  }
  return lines.join("\n");
}

function renderSummary(
  report: DriftReport,
  source: string,
  counts: CoverageCounts,
): string {
  const byKind = (kind: CapabilityEntitlement["kind"]): CoverageRow[] =>
    report.rows.filter((r) => ENTITLEMENT_BY_ID.get(r.capabilityId)?.kind === kind);

  const section = (title: string, rows: CoverageRow[]): string =>
    rows.length === 0
      ? `### ${title}\n\n_none_\n`
      : `### ${title}\n\n${rows.map(renderRow).join("\n")}\n`;

  const total = report.rows.length;
  const entitled = report.rows.filter(
    (r) => ENTITLEMENT_BY_ID.get(r.capabilityId)?.entitled ?? false,
  ).length;

  return [
    "# Contract Fidelity — Drift Report",
    "",
    `Generated: ${report.generatedAt}`,
    `Backend contract source: **${source}**`,
    "",
    "## Coverage summary",
    "",
    `| Status | Count |`,
    `| --- | --- |`,
    `| ✅ covered | ${counts.covered} |`,
    `| ⚠️ partial | ${counts.partial} |`,
    `| ❌ uncovered | ${counts.uncovered} |`,
    `| ➖ out-of-scope | ${counts["out-of-scope"]} |`,
    `| **total capabilities** | ${total} |`,
    `| **entitled capabilities** | ${entitled} |`,
    "",
    `Drift gate: **${report.failed ? "FAIL" : "PASS"}** ` +
      `(fails iff an entitled capability is uncovered or partial).`,
    "",
    "## Capabilities",
    "",
    section("HTTP endpoints", byKind("http")),
    section("WebSocket channels", byKind("ws")),
    section("SSE streams", byKind("sse")),
    "## Schema-less capabilities (Req 16)",
    "",
    "Each capability with no response body or an open/unconstrained shape is",
    "resolved to an explicit classification so the drift gate is not permanently",
    "red. `no-body/open-shape ⇒ covered` never fails the gate; `tracked-partial`",
    "is a tracked partial with a named rationale (not an untracked failure).",
    "",
    report.schemaLess.length === 0
      ? "_none_\n"
      : report.schemaLess
          .map((r) => {
            const mark =
              r.classification === "no-body-open-shape-covered"
                ? "✅ no-body/open-shape ⇒ covered"
                : "⚠️ tracked-partial";
            return `- ${mark} — \`${refOf(r.capabilityId)}\` (${r.capabilityId})\n    · rationale: ${r.rationale}`;
          })
          .join("\n") + "\n",
    report.unclassifiedSchemaLess.length === 0
      ? "_All schema-less capabilities are classified._\n"
      : "**Unclassified schema-less capabilities (Req 16.5) — classify or mark out-of-scope:**\n" +
        report.unclassifiedSchemaLess.map((id) => `- ❌ \`${refOf(id)}\` (${id})`).join("\n") +
        "\n",
    "## Backend gaps",
    "",
    "### Agent-state gaps (Req 2.3) — canonical states with no backing cognition event",
    "",
    report.backendGaps.filter((g) => g.kind === "agent-state").length === 0
      ? "_none — every agent state has a backing event_\n"
      : report.backendGaps
          .filter((g) => g.kind === "agent-state")
          .map((g) => `- \`${g.name}\` — AUX layer must render this state as unavailable`)
          .join("\n") + "\n",
    "### Oversight gaps (Req 3.8) — agent-action affordances with no backing endpoint",
    "",
    report.backendGaps.filter((g) => g.kind === "oversight").length === 0
      ? "_none — every oversight affordance has a backing endpoint_\n"
      : report.backendGaps
          .filter((g) => g.kind === "oversight")
          .map((g) => `- \`${g.name}\` — no backend affordance exists`)
          .join("\n") + "\n",
    "### Uplift gaps (Req 17.3, 17.4) — system-level uplift measure not exposed",
    "",
    report.backendGaps.filter((g) => g.kind === "uplift").length === 0
      ? "_none — a system-level uplift measure is exposed_\n"
      : report.backendGaps
          .filter((g) => g.kind === "uplift")
          .map(
            (g) =>
              `- \`${g.name}\` — Operations uplift slot renders "awaiting uplift measure"; no value fabricated`,
          )
          .join("\n") + "\n",
  ].join("\n");
}

// ─────────────────────────────────────────────────────────────────────────
// Entry point
// ─────────────────────────────────────────────────────────────────────────

const JSON_REPORT_PATH = fileURLToPath(new URL("./drift-report.json", import.meta.url));
const MD_REPORT_PATH = fileURLToPath(new URL("./drift-report.md", import.meta.url));

export async function generateDriftReport(): Promise<{ report: DriftReport; source: string }> {
  // Turn the hand-maintained client-method registry into genuine introspection:
  // this throws if a declared synapse-api method no longer exists.
  verifyClientMethodRegistry();

  const contract = await loadBackendContract({
    baseUrl: process.env.SYNAPSE_GATEWAY_URL,
    timeoutMs: 5000,
  });
  const contractFieldsById = extractContractFields(contract.document);

  const consoleCaps = introspectConsole(ALL_ENTITLEMENTS, contractFieldsById);

  // Resolve every schema-less capability to one of the two honest
  // classifications, then fold that resolution into the coverage rows so a
  // no-body/open-shape capability no longer fails the gate for a missing
  // response schema (Req 16.1–16.4).
  const schemaLessResult = resolveSchemaLess(consoleCaps, SCHEMA_LESS_RESOLUTIONS);
  const rows = applySchemaLessResolution(
    buildRows(consoleCaps, contractFieldsById),
    schemaLessResult,
  );
  const failed = computeGatedFailure(rows, trackedPartialIds(schemaLessResult));

  // The applied classifications, surfaced in the report (Req 16.1, 16.3).
  const schemaLess: readonly SchemaLessResolution[] = SCHEMA_LESS_RESOLUTIONS.filter((r) =>
    schemaLessResult.rows.some((row) => row.capabilityId === r.capabilityId),
  );

  const backendGaps: DriftReport["backendGaps"] = [
    ...agentStateGaps().map((name) => ({ kind: "agent-state" as const, name })),
    ...oversightGaps().map((name) => ({ kind: "oversight" as const, name })),
    ...upliftGaps().map((name) => ({ kind: "uplift" as const, name })),
  ];

  const report: DriftReport = {
    generatedAt: new Date().toISOString(),
    rows,
    backendGaps,
    schemaLess,
    unclassifiedSchemaLess: schemaLessResult.unclassified,
    failed,
  };

  const source =
    contract.source === "live"
      ? "live /openapi.json"
      : `snapshot${contract.fetchError ? ` (live fetch failed: ${contract.fetchError})` : ""}`;

  return { report, source };
}

async function main(): Promise<void> {
  const { report, source } = await generateDriftReport();
  const counts = countByStatus(report.rows);
  const summary = renderSummary(report, source, counts);

  await writeFile(JSON_REPORT_PATH, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  await writeFile(MD_REPORT_PATH, `${summary}\n`, "utf8");

  // Echo the human-readable summary so CI logs carry it inline.
  process.stdout.write(`${summary}\n`);

  // Name the specific entitled gaps and fail the check (Req 1.6, 16.5).
  if (report.failed) {
    const unclassified = new Set(report.unclassifiedSchemaLess);
    const trackedPartials = new Set(
      report.schemaLess
        .filter((r) => r.classification === "tracked-partial")
        .map((r) => r.capabilityId),
    );
    const gaps = report.rows.filter(
      (r) =>
        (r.status === "uncovered" || r.status === "partial") &&
        !trackedPartials.has(r.capabilityId),
    );
    process.stderr.write("\nContract fidelity FAILED — entitled capabilities uncovered/partial:\n");
    for (const row of gaps) {
      const tag = unclassified.has(row.capabilityId)
        ? "unclassified schema-less — classify or mark out-of-scope (Req 16.5)"
        : row.status;
      process.stderr.write(`  • [${tag}] ${refOf(row.capabilityId)} (${row.capabilityId})\n`);
    }
    process.exitCode = 1;
    return;
  }

  process.stdout.write(
    "\nContract fidelity PASSED — every entitled capability is covered or a tracked schema-less capability.\n",
  );
}

// Run only when invoked directly (not when imported by a test).
const isDirectRun =
  process.argv[1] !== undefined &&
  fileURLToPath(import.meta.url) === process.argv[1];

if (isDirectRun) {
  main().catch((err: unknown) => {
    process.stderr.write(`\nContract fidelity crashed: ${err instanceof Error ? err.stack ?? err.message : String(err)}\n`);
    process.exitCode = 1;
  });
}
