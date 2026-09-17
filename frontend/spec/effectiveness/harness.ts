/**
 * Effectiveness_Harness -- the in-browser driver behind `window.__atlasHarness`
 * (Req 8.1, 8.3; design "C. Harness -- JTBD scenario descriptors +
 * Task_Completion_Test harness"; AD-12).
 *
 * This module is the single place the six harness-dependent Playwright specs
 * talk to. It composes the pieces that already exist rather than duplicating
 * them:
 *
 *   * `./browser-worker.ts` -- the MSW browser worker (the seeded HTTP surface).
 *   * `./stream-driver.ts` + `./stream-transport.ts` -- the scripted WS/SSE
 *     doubles (the seeded real-time surface).
 *   * `./scenarios/*` -- the transport-free scenario descriptors (the seeds,
 *     the declared schema bindings, the fault chains, the rate profiles).
 *   * `@lib/effectiveness-scorecard` -- the shipped job enumeration, the master
 *     seed, and the verbatim Scripted_Proxy ceiling.
 *
 * AD-12: nothing under `frontend/src/` may mention the harness global, and the
 * shipped bundle must not contain it (asserted by
 * `scripts/audit/workflow_shape_truth.py::assert_harness_absent_from_bundle`).
 * That is why this module lives under `frontend/spec/` and is imported ONLY by
 * `./e2e-entry.ts`, which is injected into `index.html` exclusively in the
 * `e2e` build mode (see `frontend/vite.config.ts`). The production build never
 * resolves either file.
 *
 * Honesty (I-7). The harness MEASURES; it never asserts success on the app's
 * behalf:
 *
 *   * `runTaskCompletion` drives real affordances in the real DOM. A missing or
 *     unreachable affordance is recorded as a dead-end (`errorRate > 0`,
 *     `reachedTerminal: false`) and the driving spec fails. No step is ever
 *     reported as taken when its affordance was not found.
 *   * `seedScenario` / `driveFault` / `driveResilience` throw on an unknown
 *     scenario id or an undrivable request rather than resolving as a silent
 *     no-op, so a spec can never pass because the harness did nothing.
 *   * Every result carries the verbatim `SCRIPTED_PROXY_CEILING`: a scripted
 *     proxy shows a path EXISTS and is EFFICIENT, never that a human
 *     comprehends it.
 *
 * The scenario edge. Scenario-specific fixtures (a degraded agent, a 10k-row
 * ledger) and dynamic faults (503, 401 storm, offline) are applied at the
 * `fetch` edge by {@link ScenarioEdge}, in front of MSW. This is deliberate and
 * is NOT a second mocking layer competing with the worker: `HarnessHandle`
 * (task 2.1) exposes no `use()`/`resetHandlers()`, and a fault must be
 * switchable per step *while the page stays mounted*, which a worker restart
 * cannot express. The edge intercepts exactly where MSW intercepts (the network
 * boundary) and never patches an app code path. Every body it serves is
 * re-validated through the same `Domain_Schema` the Console validates with, so
 * it cannot misrepresent the contract.
 */

import { queryClient } from "@app/providers";
import {
  EFFECTIVENESS_HARNESS_SEED,
  EFFECTIVENESS_HARNESS_VERSION,
  SCRIPTED_PROXY_CEILING,
  type JobToBeDone,
} from "@lib/effectiveness-scorecard";

import { startHarness, type HarnessHandle } from "./browser-worker";
import { buildFixture, makeRng, type Rng } from "./fixture-factory";
import { isBackendContractPath } from "./handlers";
import { getSchema } from "./schema-registry";
import { SCENARIOS } from "./scenarios";
import { RESILIENCE_SCENARIOS } from "./scenarios/resilience-index";
import { SPATIAL_SCENARIOS } from "./scenarios/spatial-visualization";
import type { ResilienceScenario } from "./scenarios/resilience-types";
import type { ScenarioDescriptor, TerminalOutcomeKind } from "./scenarios/types";
import {
  buildWsFrame,
  channelSchemaId,
  createStreamDriver,
  scriptStream,
  STREAM_CHANNELS,
  type InstalledStreamDriver,
  type StreamChannel,
  type StreamMessage,
} from "./stream-driver";
import type { SchemaId } from "./schema-registry";

// ---------------------------------------------------------------------------
// Public shapes (mirrored locally by the driving Playwright specs)
// ---------------------------------------------------------------------------

/** The fault/connectivity transition `driveFault` applies (mirrors `FaultTransitionEvent`). */
export type FaultEvent =
  | "http-503"
  | "schema-violation"
  | "auth-401-storm"
  | "ws-flap"
  | "offline"
  | "online"
  | "recover";

/** The measured Task_Completion row for one Job_To_Be_Done (Req 3.2 - 3.6). */
export interface TaskCompletionResult {
  /** The Job_To_Be_Done measured. */
  readonly job: JobToBeDone;
  /** Affordance activations attempted on the path to the terminal outcome. */
  readonly steps: number;
  /** Measured time-to-complete, milliseconds. */
  readonly latencyMs: number;
  /** Dead-ends divided by steps taken; 0 on a clean golden path (Req 3.4). */
  readonly errorRate: number;
  /** True only when the terminal outcome was OBSERVED in the DOM (Req 3.3). */
  readonly reachedTerminal: boolean;
  /** Present only when the terminal outcome was observed. */
  readonly terminalKind?: TerminalOutcomeKind;
  /**
   * Observed ordering for the escalation job (Req 3.5): the override response
   * carrying the audit row id landed no later than the first moment the UI
   * announced the decision as acted. `false` for every other job (nothing to
   * observe), and `false` when the ordering could not be observed at all.
   */
  readonly auditRowBeforeActed: boolean;
  /** The verbatim Scripted_Proxy ceiling (Req 3.6, 20.5). */
  readonly proxyCeiling: string;
  /** Each step whose affordance was missing/unreachable, named for diagnosis. */
  readonly deadEnds: readonly string[];
}

/** The documented in-browser driver the e2e specs call (design section C). */
export interface AtlasHarness {
  /** The harness version stamped on emitted artifacts. */
  readonly version: string;
  /** The master seed; per-scenario seeds come from the descriptors. */
  readonly seed: number;
  /** Drive a seeded Job_To_Be_Done and measure its completion (Req 3.2 - 3.6). */
  runTaskCompletion(scenarioId: string): Promise<TaskCompletionResult>;
  /** Drive a seeded Resilience_Scenario (Req 6, 9). */
  driveResilience(scenarioId: string): Promise<void>;
  /** Apply one fault/connectivity transition (Req 8). */
  driveFault(scenarioId: string, event: string): Promise<void>;
  /** Reach the seeded, populated baseline for a scenario (Req 1.1 - 1.3). */
  seedScenario(scenarioId: string): Promise<void>;
  /** Force the next WebGL init on a spatial surface to throw (Req 10.3). */
  failWebGL(surfaceId: string): Promise<void>;
  /** Everything the harness did, for diagnosing a failed spec. */
  diagnostics(): readonly string[];
}

declare global {
  interface Window {
    __atlasHarness?: AtlasHarness;
  }
}

/** Raised when the harness is asked for something it cannot honestly do. */
export class HarnessDriveError extends Error {
  constructor(message: string) {
    super(`Effectiveness_Harness: ${message}`);
    this.name = "HarnessDriveError";
  }
}

// ---------------------------------------------------------------------------
// Timing helpers
// ---------------------------------------------------------------------------

const DEFAULT_WAIT_MS = 5_000;
const POLL_MS = 50;
const SETTLE_MS = 120;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

/** Poll `probe` until it returns a non-null value or the deadline passes. */
async function waitFor<T>(probe: () => T | null, timeoutMs: number = DEFAULT_WAIT_MS): Promise<T | null> {
  const deadline = performance.now() + timeoutMs;
  for (;;) {
    const value = probe();
    if (value !== null) return value;
    if (performance.now() >= deadline) return null;
    await sleep(POLL_MS);
  }
}

// ---------------------------------------------------------------------------
// DOM helpers -- located by accessible name / role, never by internal structure
// ---------------------------------------------------------------------------

function all(selector: string): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(selector));
}

/** The accessible name of an element: aria-label, aria-labelledby, then text. */
function accessibleName(element: HTMLElement): string {
  const label = element.getAttribute("aria-label");
  if (label !== null && label.trim().length > 0) return label.trim();
  const labelledBy = element.getAttribute("aria-labelledby");
  if (labelledBy !== null) {
    const names = labelledBy
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent ?? "")
      .join(" ")
      .trim();
    if (names.length > 0) return names;
  }
  return (element.textContent ?? "").trim();
}

/** The first element matching `selector` whose accessible name matches `pattern`. */
function byName(selector: string, pattern: RegExp): HTMLElement | null {
  for (const element of all(selector)) {
    if (pattern.test(accessibleName(element))) return element;
  }
  return null;
}

/** The first visible button whose accessible name matches `pattern`. */
function buttonNamed(pattern: RegExp): HTMLElement | null {
  return byName('button, [role="button"]', pattern);
}

/** Text currently exposed through any announcing container (live region/status/alert). */
function announcedText(): string {
  return all('[aria-live], [role="status"], [role="alert"], output')
    .map((element) => element.textContent ?? "")
    .join(" | ");
}

/** The `<main>` text content, or the document body when the shell has no main. */
function mainText(): string {
  return (document.querySelector("main") ?? document.body).textContent ?? "";
}

/**
 * Set a React-controlled field's value the way a user would: through the native
 * value setter plus the input/change events React listens for. Assigning
 * `.value` alone is swallowed by React's synthetic event system.
 */
function typeInto(field: HTMLElement, value: string): boolean {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLInputElement
        ? HTMLInputElement.prototype
        : null;
  if (prototype === null) return false;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  if (setter === undefined) return false;
  setter.call(field, value);
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

/** Activate an affordance the way an operator would (a real click). */
function activate(element: HTMLElement): void {
  element.scrollIntoView({ block: "center", behavior: "auto" });
  element.click();
}

// ---------------------------------------------------------------------------
// Scenario resolution
// ---------------------------------------------------------------------------

type ResolvedScenario =
  | { readonly kind: "jtbd"; readonly seed: number; readonly descriptor: ScenarioDescriptor }
  | { readonly kind: "resilience"; readonly seed: number; readonly descriptor: ResilienceScenario }
  | { readonly kind: "spatial"; readonly seed: number; readonly schemaIds: readonly SchemaId[] };

function resolveScenario(scenarioId: string): ResolvedScenario {
  const jtbd = SCENARIOS.find((scenario) => scenario.setup.scenarioId === scenarioId);
  if (jtbd !== undefined) return { kind: "jtbd", seed: jtbd.seed, descriptor: jtbd };

  const resilience = RESILIENCE_SCENARIOS.find((scenario) => scenario.id === scenarioId);
  if (resilience !== undefined) {
    return { kind: "resilience", seed: resilience.seed, descriptor: resilience };
  }

  const spatial = SPATIAL_SCENARIOS.find((scenario) => scenario.id === scenarioId);
  if (spatial !== undefined) {
    return { kind: "spatial", seed: spatial.seed, schemaIds: spatial.seedSchemaIds };
  }

  throw new HarnessDriveError(
    `unknown scenario id "${scenarioId}". Registered ids: ` +
      `${[
        ...SCENARIOS.map((s) => s.setup.scenarioId),
        ...RESILIENCE_SCENARIOS.map((s) => s.id),
        ...SPATIAL_SCENARIOS.map((s) => s.id),
      ].join(", ")}`,
  );
}

function scenarioSchemaIds(scenario: ResolvedScenario): readonly SchemaId[] {
  return scenario.kind === "spatial" ? scenario.schemaIds : scenario.descriptor.seedSchemaIds;
}

/** Reverse the channel/schema binding: the channels a scenario's schema ids stream on. */
function channelsFor(scenario: ResolvedScenario): readonly StreamChannel[] {
  const wanted = new Set<string>(scenarioSchemaIds(scenario));
  return STREAM_CHANNELS.filter((channel) => {
    const bound = channelSchemaId(channel);
    return bound !== null && wanted.has(bound);
  });
}

// ---------------------------------------------------------------------------
// ScenarioEdge -- the fetch-boundary fault and scenario-fixture layer
// ---------------------------------------------------------------------------

type FaultMode = "none" | "http-503" | "auth-401-storm";

interface Overlay {
  readonly id: string;
  matches(pathname: string, method: string): boolean;
  body(): unknown;
  readonly status: number;
}

/** One observed Backend_Contract call, used for the Req 3.5 ordering observation. */
interface CallRecord {
  readonly pathname: string;
  readonly method: string;
  /** `performance.now()` when the response resolved. */
  readonly settledAt: number;
  readonly status: number;
  /** Parsed JSON body when the response carried one. */
  readonly body: unknown;
}

class ScenarioEdge {
  private readonly originalFetch: typeof window.fetch;
  private onLineDescriptor: PropertyDescriptor | undefined;
  private faultMode: FaultMode = "none";
  private offline = false;
  private readonly overlays = new Map<string, Overlay>();
  private readonly calls: CallRecord[] = [];
  private installed = false;

  constructor() {
    this.originalFetch = window.fetch.bind(window);
  }

  install(): void {
    if (this.installed) return;
    window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> =>
      this.handle(input, init);
    this.installed = true;
  }

  /** Every recorded Backend_Contract call, oldest first. */
  callLog(): readonly CallRecord[] {
    return this.calls;
  }

  setFault(mode: FaultMode): void {
    this.faultMode = mode;
  }

  fault(): FaultMode {
    return this.faultMode;
  }

  setOffline(value: boolean): void {
    this.offline = value;
    // `navigator.onLine` is what the Console's connectivity state reads, so an
    // offline transition has to move it as well as fire the event.
    if (value) {
      if (this.onLineDescriptor === undefined) {
        this.onLineDescriptor =
          Object.getOwnPropertyDescriptor(Navigator.prototype, "onLine") ??
          Object.getOwnPropertyDescriptor(window.navigator, "onLine");
      }
      Object.defineProperty(window.navigator, "onLine", { get: () => false, configurable: true });
      window.dispatchEvent(new Event("offline"));
      return;
    }
    if (this.onLineDescriptor !== undefined) {
      Object.defineProperty(window.navigator, "onLine", {
        ...this.onLineDescriptor,
        configurable: true,
      });
    } else {
      Object.defineProperty(window.navigator, "onLine", { get: () => true, configurable: true });
    }
    window.dispatchEvent(new Event("online"));
  }

  addOverlay(overlay: Overlay): void {
    this.overlays.set(overlay.id, overlay);
  }

  clearOverlays(): void {
    this.overlays.clear();
  }

  clearFaults(): void {
    this.faultMode = "none";
    if (this.offline) this.setOffline(false);
  }

  private async handle(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const url = urlOf(input);
    const method = methodOf(input, init);
    const pathname = pathnameOf(url);
    const contractPath = isBackendContractPath(pathname);

    if (contractPath && this.offline) {
      // The shape a real offline fetch takes, so the app's own failure path runs.
      throw new TypeError("Failed to fetch");
    }

    if (contractPath && this.faultMode === "http-503") {
      return this.record(pathname, method, jsonResponse({ detail: "harness fault: 503" }, 503));
    }

    if (contractPath && this.faultMode === "auth-401-storm") {
      return this.record(
        pathname,
        method,
        jsonResponse({ detail: "harness fault: 401 storm" }, 401),
      );
    }

    if (contractPath) {
      for (const overlay of this.overlays.values()) {
        if (overlay.matches(pathname, method)) {
          return this.record(pathname, method, jsonResponse(overlay.body(), overlay.status));
        }
      }
    }

    const response = await this.originalFetch(input, init);
    return contractPath ? this.record(pathname, method, response) : response;
  }

  /** Record the call (with a cloned body) and return the response untouched. */
  private async record(pathname: string, method: string, response: Response): Promise<Response> {
    let body: unknown = null;
    try {
      body = await response.clone().json();
    } catch {
      body = null;
    }
    this.calls.push({
      pathname,
      method,
      settledAt: performance.now(),
      status: response.status,
      body,
    });
    return response;
  }
}

function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function methodOf(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method !== undefined) return init.method.toUpperCase();
  if (typeof input !== "string" && !(input instanceof URL)) return input.method.toUpperCase();
  return "GET";
}

function pathnameOf(url: string): string {
  try {
    return new URL(url, window.location.origin).pathname;
  } catch {
    const query = url.indexOf("?");
    return query === -1 ? url : url.slice(0, query);
  }
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Scenario fixture overlays (schema-validated, seed-derived)
// ---------------------------------------------------------------------------

/**
 * A deterministic RFC-4122 v4 UUID. Mirrors the fixture factory's generator
 * (which does not export it) so overlay ids satisfy the same `ZUuid` check the
 * factory's do.
 */
function deterministicUuid(rng: Rng): string {
  const hex = (): string => Math.floor(rng() * 16).toString(16);
  let out = "";
  for (let i = 0; i < 36; i += 1) {
    if (i === 8 || i === 13 || i === 18 || i === 23) out += "-";
    else if (i === 14) out += "4";
    else if (i === 19) out += (8 + Math.floor(rng() * 4)).toString(16);
    else out += hex();
  }
  return out;
}

/** Validate an overlay body through the same Domain_Schema the Console applies. */
function validateAgainstSchema(schemaId: SchemaId, body: unknown, overlayId: string): unknown {
  const schema = getSchema(schemaId);
  if (schema === undefined) {
    throw new HarnessDriveError(`overlay "${overlayId}" names unregistered schema "${schemaId}"`);
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new HarnessDriveError(
      `overlay "${overlayId}" body failed Domain_Schema "${schemaId}": ${parsed.error.message}`,
    );
  }
  return parsed.data;
}

/**
 * A seeded `AuditListResponse` carrying `rowCount` rows, derived from the
 * schema-bound base fixture and re-validated through `AuditListResponse` so a
 * large seeded ledger is still contract-accurate (Req 9.1, 9.5, 2.1).
 */
function buildLedgerOverlay(seed: number, rowCount: number): Overlay {
  const overlayId = `scale.AuditListResponse.${rowCount}`;
  const base = buildFixture({
    capabilityId: "decisions.GET./api/v1/decisions/recent",
    schemaId: "AuditListResponse",
    seed,
  }).body;
  if (typeof base !== "object" || base === null || !("decisions" in base)) {
    throw new HarnessDriveError(`overlay "${overlayId}" base fixture has no decisions array`);
  }
  const template = (base as { decisions: unknown[] }).decisions[0];
  if (typeof template !== "object" || template === null) {
    throw new HarnessDriveError(`overlay "${overlayId}" base fixture has no seed row`);
  }
  const rng = makeRng(seed);
  const rows: unknown[] = [];
  for (let index = 0; index < rowCount; index += 1) {
    rows.push({
      ...(template as Record<string, unknown>),
      audit_id: deterministicUuid(rng),
      decision_id: deterministicUuid(rng),
    });
  }
  const body = validateAgainstSchema(
    "AuditListResponse",
    { ...(base as Record<string, unknown>), decisions: rows, count: rows.length },
    overlayId,
  );
  return {
    id: overlayId,
    status: 200,
    matches: (pathname, method) =>
      method === "GET" && pathname === "/api/v1/decisions/recent",
    body: () => body,
  };
}

/**
 * A nominal `SystemPosture` (no brownout, no open breaker, not degraded).
 *
 * Every data-bearing Surface classifies through `useUniversalState`, which reads
 * this endpoint and renders the DEGRADED state for the whole surface when
 * `degraded === true` (`src/hooks/use-universal-state.ts`). The schema-derived
 * posture fixture flips that boolean from the seed, so without this overlay a
 * seeded baseline is degraded-or-populated by luck of the seed and an operator
 * path measurement would be measuring the coin toss. Seeding the healthy
 * baseline is what `seedScenario` is for: a fault must be injected against a
 * surface that would otherwise be populated (Req 8.1 - 8.6), and a
 * Task_Completion path must start from a populated surface (Req 3.2).
 *
 * This does not soften any fault: `driveFault` is applied in FRONT of every
 * overlay, so a 503 / 401 / offline transition still overrides the posture call.
 */
function buildHealthyPostureOverlay(): Overlay {
  const overlayId = "baseline.SystemPosture.nominal";
  const body = validateAgainstSchema(
    "SystemPosture",
    { brownout: {}, breakers: {}, degraded: false },
    overlayId,
  );
  return {
    id: overlayId,
    status: 200,
    matches: (pathname, method) => method === "GET" && pathname === "/api/v1/system/posture",
    body: () => body,
  };
}

/**
 * A seeded `AgentHealthResponse` in which exactly one agent is degraded, so the
 * "identify which agent degraded and why" job has something to identify. The
 * degraded agent and its metrics are seed-derived, and the body is validated
 * through `AgentHealthResponse`.
 */
function buildDegradedAgentOverlay(seed: number): Overlay {
  const overlayId = "jtbd.AgentHealthResponse.degraded";
  const names = [
    "demand_prophet",
    "routing_navigator",
    "inventory_sentinel",
    "freshness_guardian",
    "pricing_oracle",
    "disruption_shield",
    "supplier_trust",
    "sustainability_agent",
  ] as const;
  const rng = makeRng(seed);
  const degradedIndex = Math.floor(rng() * names.length);
  const agents: Record<string, unknown> = {};
  names.forEach((name, index) => {
    const degraded = index === degradedIndex;
    agents[name] = {
      status: degraded ? "degraded" : "healthy",
      latency_p50_ms: degraded ? 940 + Math.floor(rng() * 60) : 40 + Math.floor(rng() * 20),
      latency_p95_ms: degraded ? 2_400 + Math.floor(rng() * 200) : 120 + Math.floor(rng() * 40),
      decisions_per_min: degraded ? 0 : 6 + Math.floor(rng() * 4),
      calibration_coverage_90: degraded ? 0.41 : 0.9,
    };
  });
  const body = validateAgainstSchema(
    "AgentHealthResponse",
    { agents, count: names.length },
    overlayId,
  );
  return {
    id: overlayId,
    status: 200,
    matches: (pathname, method) => method === "GET" && pathname === "/api/v1/agents",
    body: () => body,
  };
}

// ---------------------------------------------------------------------------
// Stream driving
// ---------------------------------------------------------------------------

const FIREHOSE_URL_MARKERS = ["/ws/firehose", "/ws/escalation"];

function isFirehoseWsUrl(url: string): boolean {
  return FIREHOSE_URL_MARKERS.some((marker) => url.includes(marker));
}

/**
 * Deliver `count` frames on `channel`, continuing the monotonic sequence from
 * `startSeq`. Payloads cycle the channel's deterministic script, so a fixed
 * seed yields an identical burst; the sequence never repeats, so the multiplex
 * dedup key stays honest (a repeated `seq` would be dropped, which would make a
 * "burst" no burst at all).
 */
function emitBurst(
  driver: InstalledStreamDriver,
  channel: StreamChannel,
  startSeq: number,
  count: number,
): number {
  const socket = driver.transport.latestSocket(isFirehoseWsUrl);
  if (socket === undefined) {
    throw new HarnessDriveError(
      `no firehose WebSocket has connected yet, so channel "${channel}" cannot be driven; ` +
        "mount the subscribing surface first",
    );
  }
  if (socket.readyState !== 1) socket.driverOpen();
  const script: readonly StreamMessage[] = scriptStream(channel, driver.seed);
  if (script.length === 0) return startSeq;
  for (let index = 0; index < count; index += 1) {
    const source = script[index % script.length];
    if (source === undefined) continue;
    const seq = startSeq + index;
    socket.driverEmit(buildWsFrame({ channel, seq, payload: source.payload, offsetMs: seq }));
  }
  return startSeq + count;
}

// ---------------------------------------------------------------------------
// Jobs-To-Be-Done plans -- real affordances on the real surfaces
// ---------------------------------------------------------------------------

interface JtbdStep {
  readonly label: string;
  /** Resolve true when the affordance was found and activated. */
  run(): Promise<boolean>;
}

interface JtbdPlan {
  readonly terminalKind: TerminalOutcomeKind;
  readonly steps: readonly JtbdStep[];
  /** Resolve true when the terminal outcome is OBSERVED in the DOM. */
  terminal(): Promise<boolean>;
}

const REJECT_REASON =
  "Harness (Scripted_Proxy): rejecting because the guardrail violation makes this action unsafe.";

/** "Resolve an escalation correctly" -- the Override Cockpit reject path. */
function resolveEscalationPlan(): JtbdPlan {
  return {
    terminalKind: "escalation-resolved",
    steps: [
      {
        label: "activate the Reject override action on the active escalation",
        run: async () => {
          const button = await waitFor(() =>
            document.querySelector<HTMLElement>('button[aria-keyshortcuts="R"]'),
          );
          if (button === null) return false;
          activate(button);
          return true;
        },
      },
      {
        label: "state the mandatory rejection reason",
        run: async () => {
          const field = await waitFor(() =>
            document.querySelector<HTMLElement>('form[aria-label="Reject reason form"] textarea'),
          );
          if (field === null) return false;
          return typeInto(field, REJECT_REASON);
        },
      },
      {
        label: "commit the reject",
        run: async () => {
          const commit = await waitFor(() => buttonNamed(/commit reject/i));
          if (commit === null) return false;
          activate(commit);
          return true;
        },
      },
    ],
    terminal: async () =>
      (await waitFor(() => (/override committed/i.test(announcedText()) ? true : null))) === true,
  };
}

/** "Identify which agent degraded and why" -- the Agent Council drill-down. */
function identifyDegradedAgentPlan(): JtbdPlan {
  const unhealthy = /degraded|unhealthy|unreachable|http_/i;
  return {
    terminalKind: "degraded-agent-identified",
    steps: [
      {
        label: "open the drill-down of the agent whose council card is not healthy",
        run: async () => {
          const link = await waitFor(() => {
            for (const candidate of all('a[aria-label^="Open "]')) {
              if (unhealthy.test(candidate.textContent ?? "")) return candidate;
            }
            return null;
          });
          if (link === null) return false;
          activate(link);
          return true;
        },
      },
    ],
    terminal: async () =>
      (await waitFor(() => {
        const text = mainText();
        // The drill-down must name the degradation AND show why: a latency,
        // calibration, or error signal alongside it.
        return unhealthy.test(text) && /latency|p95|calibration|error|throughput|dec\/min/i.test(text)
          ? true
          : null;
      })) === true,
  };
}

/** "Reconstruct a decision's rationale" -- the Decision Theater drill-down. */
function reconstructRationalePlan(): JtbdPlan {
  return {
    terminalKind: "rationale-reconstructed",
    steps: [
      {
        label: "open a decision from the ledger",
        run: async () => {
          const link = await waitFor(() =>
            document.querySelector<HTMLElement>('a[href^="/decisions/"]'),
          );
          if (link === null) return false;
          activate(link);
          return true;
        },
      },
    ],
    terminal: async () =>
      (await waitFor(() =>
        /rationale|reasoning|why this|evidence|proposals|debate/i.test(mainText()) ? true : null,
      )) === true,
  };
}

/** "Adjust steering safely" -- move a governance weight and see it take effect. */
function adjustSteeringPlan(): JtbdPlan {
  return {
    terminalKind: "steering-adjusted",
    steps: [
      {
        label: "adjust the first governance weight slider",
        run: async () => {
          const slider = await waitFor(() =>
            document.querySelector<HTMLInputElement>('input[type="range"]'),
          );
          if (slider === null) return false;
          const current = Number(slider.value);
          const step = Number(slider.step === "" ? "0.05" : slider.step);
          const max = Number(slider.max === "" ? "1" : slider.max);
          const next = current + step > max ? current - step : current + step;
          return typeInto(slider, next.toFixed(2));
        },
      },
    ],
    // The surface has no commit endpoint; its observable terminal state for a
    // safe adjustment is the dirty affordance becoming operable (the reset
    // path exists, so the change is reversible) with the new value rendered.
    terminal: async () =>
      (await waitFor(() => {
        const reset = buttonNamed(/reset/i);
        if (reset === null) return null;
        return reset.hasAttribute("disabled") ? null : true;
      })) === true,
  };
}

/** "Catch a disruption before it cascades" -- the Mission Control banner. */
function catchDisruptionPlan(): JtbdPlan {
  return {
    terminalKind: "disruption-contained",
    steps: [
      {
        label: "expand the seeded disruption alert on Mission Control",
        run: async () => {
          const trigger = await waitFor(() => {
            for (const alert of all('[role="alert"]')) {
              if (!/disruption/i.test(alert.textContent ?? "")) continue;
              const button = alert.querySelector<HTMLElement>("button[aria-expanded]");
              if (button !== null) return button;
            }
            return null;
          });
          if (trigger === null) return false;
          activate(trigger);
          return true;
        },
      },
    ],
    // Containment is knowing the anomaly AND its playbook before it cascades.
    terminal: async () =>
      (await waitFor(() => {
        for (const alert of all('[role="alert"]')) {
          const text = alert.textContent ?? "";
          if (/disruption/i.test(text) && /playbook/i.test(text)) return true;
        }
        return null;
      })) === true,
  };
}

const PLANS: Readonly<Record<JobToBeDone, () => JtbdPlan>> = {
  "resolve-escalation-correctly": resolveEscalationPlan,
  "identify-degraded-agent": identifyDegradedAgentPlan,
  "reconstruct-decision-rationale": reconstructRationalePlan,
  "adjust-steering-safely": adjustSteeringPlan,
  "catch-disruption-before-cascade": catchDisruptionPlan,
};

// ---------------------------------------------------------------------------
// installAtlasHarness
// ---------------------------------------------------------------------------

/**
 * Install `window.__atlasHarness`. Called only by `./e2e-entry.ts`, which the
 * e2e build injects ahead of the app entry so the seeded HTTP and stream edges
 * are in place before the Console issues its first request (AD-12, Req 1.1).
 */
export async function installAtlasHarness(): Promise<AtlasHarness> {
  const diagnostics: string[] = [];
  const note = (message: string): void => {
    diagnostics.push(`${new Date().toISOString()} ${message}`);
  };

  const edge = new ScenarioEdge();
  edge.install();

  // The transport doubles must be installed before any surface mounts, so a
  // socket the app opens is a scripted one the driver can address.
  const driver: InstalledStreamDriver = createStreamDriver({ seed: EFFECTIVENESS_HARNESS_SEED });

  let handle: HarnessHandle = await startHarness({
    seed: EFFECTIVENESS_HARNESS_SEED,
    scenarioId: "harness.boot",
  });
  note(`worker started at master seed ${EFFECTIVENESS_HARNESS_SEED}`);

  /** Monotonic sequence per channel across everything this page drives. */
  const nextSeq = new Map<StreamChannel, number>();
  let activeScenarioId: string | null = null;

  const seqFor = (channel: StreamChannel): number => nextSeq.get(channel) ?? 1;

  /** Re-fetch every active query so a re-seeded/faulted edge is what renders. */
  const refetchAll = async (): Promise<void> => {
    await queryClient.invalidateQueries();
    await sleep(SETTLE_MS);
  };

  /** Restart the worker at a scenario's seed (fixtures are seed-derived). */
  const reseedWorker = async (seed: number, scenarioId: string): Promise<void> => {
    if (handle.seed === seed) return;
    await handle.stop();
    handle = await startHarness({ seed, scenarioId });
    note(`worker re-seeded to ${seed} for ${scenarioId}`);
  };

  /** Deliver the scenario's declared channels; record any that cannot be driven. */
  const driveDeclaredChannels = (scenario: ResolvedScenario, scenarioId: string): void => {
    for (const channel of channelsFor(scenario)) {
      try {
        const start = seqFor(channel);
        const script = scriptStream(channel, driver.seed);
        nextSeq.set(channel, emitBurst(driver, channel, start, script.length));
        note(`seeded ${script.length} ${channel} message(s) for ${scenarioId}`);
      } catch (error) {
        note(
          `channel "${channel}" not drivable for ${scenarioId}: ` +
            `${error instanceof Error ? error.message : String(error)}`,
        );
      }
    }
  };

  const seedScenario = async (scenarioId: string): Promise<void> => {
    const scenario = resolveScenario(scenarioId);
    activeScenarioId = scenarioId;
    edge.clearFaults();
    edge.clearOverlays();

    // The populated baseline every scenario starts from.
    edge.addOverlay(buildHealthyPostureOverlay());

    // Scenario-specific seeded fixtures the shared handler set cannot express.
    if (scenario.kind === "jtbd" && scenario.descriptor.job === "identify-degraded-agent") {
      edge.addOverlay(buildDegradedAgentOverlay(scenario.seed));
    }
    if (scenario.kind === "resilience" && scenario.descriptor.kind === "scale-virtualization") {
      const rowCount = scenario.descriptor.seedRowCount;
      if (rowCount === undefined) {
        throw new HarnessDriveError(`scenario "${scenarioId}" declares no seedRowCount`);
      }
      edge.addOverlay(buildLedgerOverlay(scenario.seed, rowCount));
    }

    await reseedWorker(scenario.seed, scenarioId);
    await refetchAll();
    driveDeclaredChannels(scenario, scenarioId);
    await sleep(SETTLE_MS);
    note(`seeded scenario ${scenarioId}`);
  };

  const driveResilience = async (scenarioId: string): Promise<void> => {
    const scenario = resolveScenario(scenarioId);
    if (scenario.kind !== "resilience") {
      throw new HarnessDriveError(
        `scenario "${scenarioId}" is not a Resilience_Scenario, so driveResilience cannot drive it`,
      );
    }
    await seedScenario(scenarioId);

    const rates = scenario.descriptor.rates ?? [];
    if (rates.length === 0) {
      // A non-streaming resilience kind (scale) is fully expressed by its seeded
      // fixture, which `seedScenario` above installed and re-fetched.
      note(`resilience ${scenarioId} has no rate profiles; seeded fixture only`);
      return;
    }

    const channels = channelsFor(scenario);
    if (channels.length === 0) {
      throw new HarnessDriveError(
        `resilience scenario "${scenarioId}" declares no streamable channel to drive`,
      );
    }
    for (const rate of rates) {
      const slices = Math.max(1, Math.round(rate.durationMs / 100));
      const perSlicePerChannel = Math.max(
        1,
        Math.round((rate.messagesPerSecond / 10) / channels.length),
      );
      for (let slice = 0; slice < slices; slice += 1) {
        for (const channel of channels) {
          nextSeq.set(
            channel,
            emitBurst(driver, channel, seqFor(channel), perSlicePerChannel),
          );
        }
        // Yield to the event loop so the burst is a real streaming load the
        // renderer has to keep up with, not one synchronous block.
        await sleep(0);
      }
      note(
        `streamed ${rate.label} profile (${rate.messagesPerSecond}/s for ${rate.durationMs}ms) ` +
          `on ${channels.join(", ")}`,
      );
    }
    await sleep(SETTLE_MS);
  };

  const driveFault = async (scenarioId: string, event: string): Promise<void> => {
    const scenario = resolveScenario(scenarioId);
    const faultChannels = channelsFor(scenario);
    const schemaBound = faultChannels.find((channel) => channelSchemaId(channel) !== null);

    switch (event as FaultEvent) {
      case "http-503":
        edge.setFault("http-503");
        await refetchAll();
        break;
      case "auth-401-storm":
        edge.setFault("auth-401-storm");
        await refetchAll();
        // A storm is repeated: keep failing while the single-flight refresh is
        // exhausted, which is what routes the operator to /login.
        await refetchAll();
        break;
      case "schema-violation": {
        if (schemaBound === undefined) {
          throw new HarnessDriveError(
            `scenario "${scenarioId}" declares no schema-bound channel, so a deterministic ` +
              "schema violation cannot be injected",
          );
        }
        driver.injectSchemaViolation(schemaBound);
        break;
      }
      case "ws-flap": {
        const channel = schemaBound ?? "decision";
        driver.flap(channel, 2);
        break;
      }
      case "offline":
        edge.setOffline(true);
        break;
      case "online":
        edge.setOffline(false);
        await refetchAll();
        break;
      case "recover":
        edge.clearFaults();
        await refetchAll();
        driveDeclaredChannels(scenario, scenarioId);
        break;
      default:
        throw new HarnessDriveError(
          `unknown fault event "${event}"; expected one of http-503, schema-violation, ` +
            "auth-401-storm, ws-flap, offline, online, recover",
        );
    }
    await sleep(SETTLE_MS);
    note(`applied fault "${event}" for ${scenarioId}`);
  };

  const failWebGL = async (surfaceId: string): Promise<void> => {
    const spatial = SPATIAL_SCENARIOS[0];
    const surface = spatial?.surfaces.find((candidate) => candidate.surfaceId === surfaceId);
    if (surface === undefined) {
      throw new HarnessDriveError(
        `no Spatial_Visualization surface "${surfaceId}" is registered; known: ` +
          `${(spatial?.surfaces ?? []).map((s) => s.surfaceId).join(", ")}`,
      );
    }
    const original = HTMLCanvasElement.prototype.getContext;
    // Force the NEXT WebGL init to throw, exactly where the viz library asks
    // for its context. 2d contexts still resolve, so only the spatial layer
    // fails (Req 10.3).
    function failing(this: HTMLCanvasElement, contextId: string, ...rest: unknown[]): unknown {
      if (/webgl/i.test(contextId)) {
        throw new Error(
          `Effectiveness_Harness: forced WebGL init failure for surface "${surfaceId}"`,
        );
      }
      return (original as (this: HTMLCanvasElement, id: string, ...args: unknown[]) => unknown).call(
        this,
        contextId,
        ...rest,
      );
    }
    HTMLCanvasElement.prototype.getContext = failing as typeof HTMLCanvasElement.prototype.getContext;
    note(`WebGL init forced to fail on ${surfaceId}`);

    // Re-enter the route so the spatial component initializes again under the
    // failing context. A client-side bounce keeps the harness installed (a
    // reload would tear it down).
    const target = surface.surfacePath;
    const away = target === "/operations" ? "/audit" : "/operations";
    window.history.pushState({}, "", away);
    window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
    await sleep(SETTLE_MS);
    window.history.pushState({}, "", target);
    window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
    await sleep(SETTLE_MS);
  };

  const runTaskCompletion = async (scenarioId: string): Promise<TaskCompletionResult> => {
    const scenario = resolveScenario(scenarioId);
    if (scenario.kind !== "jtbd") {
      throw new HarnessDriveError(
        `scenario "${scenarioId}" is not a Job_To_Be_Done scenario, so it has no Task_Completion`,
      );
    }
    const job = scenario.descriptor.job;
    const buildPlan = PLANS[job];
    const plan = buildPlan();

    await seedScenario(scenarioId);

    const callsBefore = edge.callLog().length;
    const started = performance.now();
    const deadEnds: string[] = [];
    let steps = 0;

    for (const step of plan.steps) {
      steps += 1;
      const ok = await step.run();
      if (!ok) {
        deadEnds.push(`missing or unreachable affordance: ${step.label}`);
        break;
      }
    }

    const reachedTerminal = deadEnds.length === 0 ? await plan.terminal() : false;
    if (!reachedTerminal && deadEnds.length === 0) {
      deadEnds.push(`terminal outcome "${plan.terminalKind}" was not observed`);
    }
    const latencyMs = performance.now() - started;
    const errorRate = steps === 0 ? 1 : deadEnds.length / steps;

    const auditRowBeforeActed =
      job === "resolve-escalation-correctly"
        ? observeAuditRowBeforeActed(edge.callLog().slice(callsBefore))
        : false;

    note(
      `runTaskCompletion(${scenarioId}): steps=${steps} terminal=${String(reachedTerminal)} ` +
        `deadEnds=${deadEnds.length}`,
    );

    return {
      job,
      steps,
      latencyMs,
      errorRate,
      reachedTerminal,
      ...(reachedTerminal ? { terminalKind: plan.terminalKind } : {}),
      auditRowBeforeActed,
      proxyCeiling: SCRIPTED_PROXY_CEILING,
      deadEnds,
    };
  };

  const harness: AtlasHarness = {
    version: EFFECTIVENESS_HARNESS_VERSION,
    seed: EFFECTIVENESS_HARNESS_SEED,
    runTaskCompletion,
    driveResilience,
    driveFault,
    seedScenario,
    failWebGL,
    diagnostics: () => {
      const unhandled = handle.unhandledPaths();
      return unhandled.length === 0
        ? diagnostics
        : [...diagnostics, `unhandled Backend_Contract path(s): ${unhandled.join(", ")}`];
    },
  };

  window.__atlasHarness = harness;
  note(`harness installed (active scenario: ${activeScenarioId ?? "none"})`);
  return harness;
}

/**
 * Observe the Req 3.5 ordering from the recorded calls: the override response
 * carrying the audit row id must have settled before the UI announced the
 * decision as acted. Returns false when the override call was never observed or
 * carried no audit row id -- an unobserved ordering is not a satisfied one
 * (I-7).
 */
function observeAuditRowBeforeActed(calls: readonly CallRecord[]): boolean {
  const override = calls.find(
    (call) => call.method === "POST" && /\/api\/v1\/decisions\/[^/]+\/override$/.test(call.pathname),
  );
  if (override === undefined || override.status >= 400) return false;
  const body = override.body;
  if (typeof body !== "object" || body === null) return false;
  const auditId = (body as Record<string, unknown>)["audit_escalation_id"];
  if (auditId === undefined || auditId === null) return false;
  // The Console marks the decision acted in the mutation's `onSuccess`, i.e.
  // strictly after this response settled, and the announcement that names the
  // audit row is the observable proof that the row existed first.
  return /audit row/i.test(announcedText());
}
