/**
 * Contract Fidelity — Console-surface + backend-contract introspection.
 *
 * This module is Input #2 and Input #3 of the Contract Fidelity Suite
 * (design "Contract Fidelity Suite"):
 *
 *   • Input #2 — the Console surface. Two registries introspected from the
 *     real Console code:
 *       1. CLIENT_METHOD_REGISTRY — every capability the typed client
 *          (`transport/synapse-api.ts`, plus the documented non-`synapse-api`
 *          consumers: the firehose WS multiplex, the demo SSE `EventSource`,
 *          and the `navigator.sendBeacon` telemetry sink) actually calls,
 *          keyed by the same `capabilityId` scheme as the entitlement manifest
 *          and carrying the `schemaId` each method validates its response with.
 *       2. DOMAIN_SCHEMA_REGISTRY — every domain Zod schema, keyed by the
 *          `schemaId` string already used by `http-client` / the firehose
 *          per-channel `SCHEMAS` map (design "each schema is registered with a
 *          `schemaId`").
 *     `introspectConsole()` joins these two registries against a list of
 *     `CapabilityEntitlement`s to produce a `ConsoleCapability` record per
 *     capability (Requirements 1.1).
 *
 *   • Input #3 — the backend contract. `loadBackendContract()` fetches the
 *     published OpenAPI document from `/openapi.json` when a gateway is
 *     reachable and otherwise falls back to the checked-in snapshot at
 *     `./openapi.snapshot.json`, so the suite runs deterministically offline
 *     and in CI. `extractContractFields()` normalizes that document into the
 *     per-capability response field sets the field diff consumes
 *     (Requirements 1.3).
 *
 * Everything here is dependency-light and self-contained: the Console imports
 * use the repo `@`-aliases (resolved by `tsx`/Vitest from `tsconfig.json`), and
 * the OpenAPI loader uses only Node built-ins + global `fetch`.
 */

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import type { ZodTypeAny } from "zod";

import { createSynapseApi } from "@transport/synapse-api";

import { DOMAIN_SCHEMA_REGISTRY, hasDomainSchema } from "../effectiveness/schema-registry";

import CHANNEL_ENTITLEMENTS from "./channels";
import HTTP_ENTITLEMENTS from "./entitlements";
import type { CapabilityEntitlement, ConsoleCapability } from "./types";

// ─────────────────────────────────────────────────────────────────────────
// Domain Zod schema registry — keyed by `schemaId`
// ─────────────────────────────────────────────────────────────────────────

/**
 * The authoritative "domain schema registry" the suite introspects, promoted
 * to the shared `spec/effectiveness/schema-registry.ts` module so both this
 * drift suite and the Effectiveness_Harness bind to one registry. Re-exported
 * here to preserve every existing import path (`run.ts`, tests). A capability
 * `hasDomainSchema` iff its `schemaId` resolves in the registry.
 */
export { DOMAIN_SCHEMA_REGISTRY, hasDomainSchema };

// ─────────────────────────────────────────────────────────────────────────
// Client-method registry — introspected from `synapse-api.ts` + consumers
// ─────────────────────────────────────────────────────────────────────────

/** How a capability is consumed by the Console. */
export type ClientConsumer =
  | "synapse-api" // a method on the createSynapseApi() client
  | "firehose" // a channel on the /ws/firehose WS multiplex
  | "ws-escalation" // the legacy single-channel escalation WebSocket
  | "sse-eventsource" // an EventSource stream (demo theater)
  | "send-beacon"; // navigator.sendBeacon (telemetry)

export interface ClientMethodEntry {
  /** Capability the entry covers — matches the entitlement `capabilityId`. */
  readonly capabilityId: string;
  /** Which Console subsystem consumes the capability. */
  readonly consumer: ClientConsumer;
  /**
   * For `synapse-api` entries, the dotted method path on the client instance
   * (e.g. `"listAgents"`, `"jwks.fetch"`) verified to exist at introspection
   * time. Null for non-`synapse-api` consumers.
   */
  readonly method: string | null;
  /** The `schemaId` this method validates its response with, if any. */
  readonly schemaId: string | null;
}

/**
 * Every capability the Console consumes today, keyed to the entitlement
 * `capabilityId` scheme. Out-of-scope entitlements (the gateway
 * `decisions.POST`, the un-mounted `metrics.*`, the browser-native
 * `csp-report` sink) intentionally have NO entry — they carry no client method
 * and no schema, which is exactly what makes them out-of-scope.
 */
export const CLIENT_METHOD_REGISTRY: readonly ClientMethodEntry[] = [
  // ── gateway liveness (no response schema — raw status objects) ──────────
  { capabilityId: "gateway.GET./health", consumer: "synapse-api", method: "health", schemaId: null },
  { capabilityId: "gateway.GET./ready", consumer: "synapse-api", method: "ready", schemaId: null },

  // ── agents ──────────────────────────────────────────────────────────────
  {
    capabilityId: "agents.GET./api/v1/agents",
    consumer: "synapse-api",
    method: "listAgents",
    schemaId: "AgentHealthResponse",
  },

  // ── auth ──────────────────────────────────────────────────────────────
  {
    capabilityId: "auth.POST./api/v1/auth/login",
    consumer: "synapse-api",
    method: "login",
    schemaId: "LoginResponse",
  },
  {
    capabilityId: "auth.POST./api/v1/auth/refresh",
    consumer: "synapse-api",
    method: "refresh",
    schemaId: "RefreshResponse",
  },
  {
    // logout returns 204 (no body) — a client method with no response schema.
    capabilityId: "auth.POST./api/v1/auth/logout",
    consumer: "synapse-api",
    method: "logout",
    schemaId: null,
  },
  {
    capabilityId: "auth.GET./api/v1/auth/.well-known/jwks.json",
    consumer: "synapse-api",
    method: "jwks.fetch",
    schemaId: null,
  },

  // ── decisions ─────────────────────────────────────────────────────────
  {
    capabilityId: "decisions.GET./api/v1/decisions/recent",
    consumer: "synapse-api",
    method: "listRecentDecisions",
    schemaId: "AuditListResponse",
  },
  {
    capabilityId: "decisions.GET./api/v1/decisions/{decision_id}",
    consumer: "synapse-api",
    method: "getDecision",
    schemaId: "DecisionDetailResponse",
  },
  {
    capabilityId: "decisions.POST./api/v1/decisions/{decision_id}/override",
    consumer: "synapse-api",
    method: "submitOverride",
    schemaId: "OverrideApiResponse",
  },

  // ── escalations ─────────────────────────────────────────────────────────
  {
    capabilityId: "escalations.GET./api/v1/escalations/analytics",
    consumer: "synapse-api",
    method: "getEscalationAnalytics",
    schemaId: "EscalationAnalytics",
  },

  // ── orders (typed method, but no response Zod schema — 202 ack object) ──
  {
    capabilityId: "orders.POST./api/v1/orders",
    consumer: "synapse-api",
    method: "submitOrder",
    schemaId: null,
  },

  // ── steering ─────────────────────────────────────────────────────────
  {
    capabilityId: "steering.POST./api/v1/steering",
    consumer: "synapse-api",
    method: "submitSteering",
    schemaId: "SteeringResponse",
  },

  // ── system ─────────────────────────────────────────────────────────────
  {
    capabilityId: "system.GET./api/v1/system/posture",
    consumer: "synapse-api",
    method: "getSystemPosture",
    schemaId: "SystemPosture",
  },
  {
    capabilityId: "system.GET./api/v1/system/slo",
    consumer: "synapse-api",
    method: "getSlo",
    schemaId: "SloResponse",
  },
  {
    capabilityId: "system.GET./api/v1/system/calibration",
    consumer: "synapse-api",
    method: "getCalibration",
    schemaId: "CalibrationResponse",
  },

  // ── telemetry (navigator.sendBeacon in lib/log.ts — no method, no schema) ─
  {
    capabilityId: "telemetry.POST./api/v1/telemetry",
    consumer: "send-beacon",
    method: null,
    schemaId: null,
  },

  // ── topology ─────────────────────────────────────────────────────────
  {
    capabilityId: "topology.GET./api/v1/topology",
    consumer: "synapse-api",
    method: "getTopology",
    schemaId: "TopologyResponse",
  },

  // ── firehose WS channels (transport/firehose.ts per-channel SCHEMAS) ────
  { capabilityId: "firehose.WS.decision", consumer: "firehose", method: null, schemaId: "DecisionEnvelope" },
  { capabilityId: "firehose.WS.disruption", consumer: "firehose", method: null, schemaId: "DisruptionAlert" },
  { capabilityId: "firehose.WS.routing", consumer: "firehose", method: null, schemaId: "RoutePlan" },
  { capabilityId: "firehose.WS.demand", consumer: "firehose", method: null, schemaId: "DemandForecast" },
  { capabilityId: "firehose.WS.twin", consumer: "firehose", method: null, schemaId: "TwinDivergenceEvent" },
  { capabilityId: "firehose.WS.freshness", consumer: "firehose", method: null, schemaId: "FreshnessAlert" },
  { capabilityId: "firehose.WS.pricing", consumer: "firehose", method: null, schemaId: "PricingUpdate" },
  { capabilityId: "firehose.WS.escalation", consumer: "firehose", method: null, schemaId: "EscalationMessage" },
  { capabilityId: "firehose.WS.cognition", consumer: "firehose", method: null, schemaId: "CognitionEvent" },
  {
    // `metric` is an intentionally open-shape channel: a listener is bound
    // (client method present) but no Zod schema validates the payload.
    capabilityId: "firehose.WS.metric",
    consumer: "firehose",
    method: null,
    schemaId: null,
  },

  // ── non-firehose real-time streams ──────────────────────────────────────
  {
    // Legacy escalation socket — validated with the same EscalationMessage shape.
    capabilityId: "escalations.WS./ws/escalation",
    consumer: "ws-escalation",
    method: null,
    schemaId: "EscalationMessage",
  },
  {
    // Demo-theater SSE — consumed via EventSource; payloads are open-shape.
    capabilityId: "demo.SSE./api/v1/demo/{job_id}/stream",
    consumer: "sse-eventsource",
    method: null,
    schemaId: null,
  },
];

/**
 * Verify that every `synapse-api` entry in {@link CLIENT_METHOD_REGISTRY}
 * resolves to a real function on a freshly-constructed client instance. This
 * turns the hand-maintained registry into genuine introspection: if a method
 * is renamed or removed in `synapse-api.ts`, this throws and the suite fails
 * loudly rather than silently reporting stale coverage.
 *
 * @throws if a declared `synapse-api` method path is missing or not callable.
 */
export function verifyClientMethodRegistry(): void {
  const client: Record<string, unknown> = createSynapseApi({
    orchestratorUrl: "http://introspection.invalid",
    gatewayUrl: "http://introspection.invalid",
  }) as unknown as Record<string, unknown>;

  const missing: string[] = [];
  for (const entry of CLIENT_METHOD_REGISTRY) {
    if (entry.consumer !== "synapse-api" || entry.method === null) continue;
    if (typeof resolveMethod(client, entry.method) !== "function") {
      missing.push(`${entry.capabilityId} → ${entry.method}`);
    }
  }
  if (missing.length > 0) {
    throw new Error(
      `Client-method registry drift: these synapse-api methods no longer exist:\n  ${missing.join("\n  ")}`,
    );
  }
}

/** Resolve a dotted method path (e.g. "jwks.fetch") against the client. */
function resolveMethod(client: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((node, key) => {
    if (node && typeof node === "object" && key in (node as Record<string, unknown>)) {
      return (node as Record<string, unknown>)[key];
    }
    return undefined;
  }, client);
}

// ─────────────────────────────────────────────────────────────────────────
// Console-capability introspection
// ─────────────────────────────────────────────────────────────────────────

const CLIENT_METHOD_BY_ID: ReadonlyMap<string, ClientMethodEntry> = new Map(
  CLIENT_METHOD_REGISTRY.map((entry) => [entry.capabilityId, entry]),
);

/**
 * Produce the {@link ConsoleCapability} record for a single capability by
 * joining the client-method registry with the domain schema registry.
 *
 * - `hasClientMethod` — the Console consumes the capability (any consumer).
 * - `hasDomainSchema` — the consuming method validates with a registered Zod schema.
 * - `schemaComplete`  — the schema exists AND (when `contractFields` is
 *   supplied) covers every required contract field. Without a contract, a
 *   present schema is assumed complete; `run.ts` refines this via
 *   `diffContractFields` once the OpenAPI document is loaded.
 */
export function introspectConsoleCapability(
  entitlement: CapabilityEntitlement,
  contractFields?: readonly string[],
): ConsoleCapability {
  const entry = CLIENT_METHOD_BY_ID.get(entitlement.capabilityId);
  const hasClientMethod = entry !== undefined;
  const schemaPresent = entry !== undefined && hasDomainSchema(entry.schemaId);

  let schemaComplete = schemaPresent;
  if (schemaPresent && contractFields !== undefined && entry?.schemaId) {
    const schemaFields = schemaFieldNames(DOMAIN_SCHEMA_REGISTRY[entry.schemaId]);
    const schemaSet = new Set(schemaFields);
    schemaComplete = contractFields.every((field) => schemaSet.has(field));
  }

  return {
    capabilityId: entitlement.capabilityId,
    hasClientMethod,
    hasDomainSchema: schemaPresent,
    schemaComplete,
  };
}

/**
 * Introspect the whole Console surface for a set of entitlements, returning
 * one {@link ConsoleCapability} per entitlement. Pass `contractFieldsById`
 * (from {@link extractContractFields}) to fold OpenAPI field coverage into
 * each `schemaComplete`.
 */
export function introspectConsole(
  entitlements: readonly CapabilityEntitlement[] = ALL_ENTITLEMENTS,
  contractFieldsById?: ReadonlyMap<string, readonly string[]>,
): ConsoleCapability[] {
  return entitlements.map((entitlement) =>
    introspectConsoleCapability(entitlement, contractFieldsById?.get(entitlement.capabilityId)),
  );
}

/** Every entitlement the Console declares — HTTP endpoints + channels/streams. */
export const ALL_ENTITLEMENTS: readonly CapabilityEntitlement[] = [
  ...HTTP_ENTITLEMENTS,
  ...CHANNEL_ENTITLEMENTS,
];

// ─────────────────────────────────────────────────────────────────────────
// Zod field-name extraction
// ─────────────────────────────────────────────────────────────────────────

/**
 * The top-level field names of a Zod object schema, unwrapping the common
 * wrappers (`.optional()`, `.nullable()`, `.default()`, `.catch()`, effects,
 * readonly) and flattening `.and()` intersections. Returns `[]` for
 * non-object schemas (unions, records, primitives) — those are compared as
 * open shapes, not by field.
 *
 * @param requiredOnly when true, omit fields whose schema is optional — the
 *   "required field set" used for over-strict drift detection.
 */
export function schemaFieldNames(schema: ZodTypeAny, requiredOnly = false): string[] {
  const inner = unwrapSchema(schema);
  const def = (inner as { _def?: { typeName?: string } })._def;
  if (!def) return [];

  if (def.typeName === "ZodObject") {
    const shape = (inner as unknown as { shape: Record<string, ZodTypeAny> }).shape;
    const keys = Object.keys(shape);
    if (!requiredOnly) return keys;
    return keys.filter((key) => {
      const field = shape[key];
      return field !== undefined && !isOptionalField(field);
    });
  }

  if (def.typeName === "ZodIntersection") {
    const { left, right } = def as unknown as { left: ZodTypeAny; right: ZodTypeAny };
    return [...new Set([...schemaFieldNames(left, requiredOnly), ...schemaFieldNames(right, requiredOnly)])];
  }

  return [];
}

/** Peel `.optional()/.nullable()/.default()/.catch()/effects/readonly` off a schema. */
function unwrapSchema(schema: ZodTypeAny): ZodTypeAny {
  let current: ZodTypeAny = schema;
  for (let guard = 0; guard < 16; guard += 1) {
    const def = (current as { _def?: { typeName?: string } })._def;
    if (!def) return current;
    switch (def.typeName) {
      case "ZodEffects":
        current = (def as unknown as { schema: ZodTypeAny }).schema;
        break;
      case "ZodOptional":
      case "ZodNullable":
      case "ZodReadonly":
      case "ZodDefault":
      case "ZodCatch":
      case "ZodBranded":
        current = (def as unknown as { innerType: ZodTypeAny }).innerType;
        break;
      default:
        return current;
    }
  }
  return current;
}

/** Whether a Zod field is optional (`.optional()` or `.default()` present). */
function isOptionalField(field: ZodTypeAny): boolean {
  for (let guard = 0, current: ZodTypeAny = field; guard < 16; guard += 1) {
    const def = (current as { _def?: { typeName?: string } })._def;
    if (!def) return false;
    if (def.typeName === "ZodOptional" || def.typeName === "ZodDefault") return true;
    if (def.typeName === "ZodNullable" || def.typeName === "ZodReadonly") {
      current = (def as unknown as { innerType: ZodTypeAny }).innerType;
      continue;
    }
    return false;
  }
  return false;
}

// ─────────────────────────────────────────────────────────────────────────
// Backend contract loader — /openapi.json with checked-in snapshot fallback
// ─────────────────────────────────────────────────────────────────────────

/** A minimal, structural view of an OpenAPI 3.x document (only what we read). */
export interface OpenApiDocument {
  readonly openapi: string;
  readonly info?: { readonly title?: string; readonly version?: string };
  readonly paths: Readonly<Record<string, OpenApiPathItem>>;
  readonly components?: {
    readonly schemas?: Readonly<Record<string, OpenApiSchema>>;
  };
}

export type OpenApiPathItem = Readonly<Record<string, OpenApiOperation | undefined>>;

export interface OpenApiOperation {
  readonly operationId?: string;
  readonly responses?: Readonly<Record<string, OpenApiResponse>>;
}

export interface OpenApiResponse {
  readonly content?: Readonly<Record<string, { readonly schema?: OpenApiSchema }>>;
}

export interface OpenApiSchema {
  readonly $ref?: string;
  readonly type?: string;
  readonly properties?: Readonly<Record<string, OpenApiSchema>>;
  readonly required?: readonly string[];
  readonly allOf?: readonly OpenApiSchema[];
  readonly items?: OpenApiSchema;
}

/** Where the loaded contract came from — surfaced in the drift report. */
export type ContractSource = "live" | "snapshot";

export interface LoadedContract {
  readonly source: ContractSource;
  readonly document: OpenApiDocument;
  /** Populated when the live fetch failed and the snapshot was used. */
  readonly fetchError?: string;
}

/** Absolute path to the checked-in OpenAPI snapshot fallback. */
export const OPENAPI_SNAPSHOT_PATH = fileURLToPath(new URL("./openapi.snapshot.json", import.meta.url));

const HTTP_METHODS = new Set(["get", "put", "post", "delete", "patch", "options", "head", "trace"]);
const SUCCESS_STATUSES = ["200", "201", "202", "203"] as const;

export interface LoadBackendContractOptions {
  /** Gateway base URL to fetch `/openapi.json` from; when omitted, the loader goes straight to the snapshot. */
  readonly baseUrl?: string | undefined;
  /** Injectable fetch (tests); defaults to global `fetch`. */
  readonly fetchImpl?: typeof fetch | undefined;
  /** Override the snapshot location (tests); defaults to {@link OPENAPI_SNAPSHOT_PATH}. */
  readonly snapshotPath?: string | undefined;
  /** Per-request timeout for the live fetch (ms). */
  readonly timeoutMs?: number | undefined;
}

/**
 * Load the backend contract. Attempts the live `/openapi.json` when a
 * `baseUrl` is provided and a `fetch` is available; on any failure (no base
 * url, network error, non-2xx, unparseable body) falls back to the checked-in
 * snapshot so the suite is deterministic offline (Requirements 1.3).
 */
export async function loadBackendContract(
  options: LoadBackendContractOptions = {},
): Promise<LoadedContract> {
  const snapshotPath = options.snapshotPath ?? OPENAPI_SNAPSHOT_PATH;

  if (options.baseUrl) {
    const fetchImpl = options.fetchImpl ?? globalThis.fetch;
    if (typeof fetchImpl === "function") {
      try {
        const document = await fetchOpenApi(fetchImpl, options.baseUrl, options.timeoutMs);
        return { source: "live", document };
      } catch (err) {
        const fetchError = err instanceof Error ? err.message : String(err);
        const document = await readSnapshot(snapshotPath);
        return { source: "snapshot", document, fetchError };
      }
    }
  }

  const document = await readSnapshot(snapshotPath);
  return { source: "snapshot", document };
}

async function fetchOpenApi(
  fetchImpl: typeof fetch,
  baseUrl: string,
  timeoutMs = 5000,
): Promise<OpenApiDocument> {
  const url = `${baseUrl.replace(/\/+$/, "")}/openapi.json`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl(url, { signal: controller.signal });
    if (!res.ok) {
      throw new Error(`GET ${url} → ${res.status} ${res.statusText}`);
    }
    return assertOpenApi(await res.json());
  } finally {
    clearTimeout(timer);
  }
}

async function readSnapshot(snapshotPath: string): Promise<OpenApiDocument> {
  const raw = await readFile(snapshotPath, "utf8");
  return assertOpenApi(JSON.parse(raw));
}

function assertOpenApi(value: unknown): OpenApiDocument {
  if (
    value === null ||
    typeof value !== "object" ||
    typeof (value as { openapi?: unknown }).openapi !== "string" ||
    typeof (value as { paths?: unknown }).paths !== "object"
  ) {
    throw new Error("Malformed OpenAPI document: missing `openapi` version or `paths`.");
  }
  return value as OpenApiDocument;
}

// ─────────────────────────────────────────────────────────────────────────
// Contract-field extraction
// ─────────────────────────────────────────────────────────────────────────

/**
 * Normalize an OpenAPI document into a `capabilityId → response field names`
 * map, matched against the HTTP entitlement manifest (method + path). Only
 * HTTP capabilities appear — WS/SSE channel contracts are not described by
 * OpenAPI and are modeled via `channels.ts` instead.
 *
 * The success-response body schema is resolved (following one `$ref` into
 * `components.schemas` and flattening `allOf`) and its top-level `properties`
 * become the capability's contract field set — the input the field diff needs
 * to report contract-vs-schema drift (Requirements 1.3).
 */
export function extractContractFields(
  document: OpenApiDocument,
  entitlements: readonly CapabilityEntitlement[] = HTTP_ENTITLEMENTS,
): Map<string, string[]> {
  const byId = new Map<string, string[]>();
  const httpById = new Map<string, CapabilityEntitlement>();
  for (const entitlement of entitlements) {
    if (entitlement.kind === "http") httpById.set(routeKey(methodOf(entitlement), entitlement.ref), entitlement);
  }

  for (const [path, item] of Object.entries(document.paths)) {
    if (!item) continue;
    for (const [method, operation] of Object.entries(item)) {
      if (!operation || !HTTP_METHODS.has(method.toLowerCase())) continue;
      const entitlement = httpById.get(routeKey(method.toUpperCase(), path));
      if (!entitlement) continue;
      const schema = successResponseSchema(operation);
      if (!schema) continue;
      byId.set(entitlement.capabilityId, openApiFieldNames(schema, document));
    }
  }

  return byId;
}

/** The HTTP method encoded in a `capabilityId` ("router.METHOD.ref"). */
function methodOf(entitlement: CapabilityEntitlement): string {
  return entitlement.capabilityId.split(".")[1] ?? "";
}

function routeKey(method: string, path: string): string {
  return `${method.toUpperCase()} ${path}`;
}

function successResponseSchema(operation: OpenApiOperation): OpenApiSchema | undefined {
  const responses = operation.responses;
  if (!responses) return undefined;
  for (const status of SUCCESS_STATUSES) {
    const content = responses[status]?.content;
    const schema = content?.["application/json"]?.schema;
    if (schema) return schema;
  }
  return undefined;
}

/** Top-level property names of an OpenAPI schema, resolving one `$ref` + `allOf`. */
function openApiFieldNames(schema: OpenApiSchema, document: OpenApiDocument): string[] {
  const resolved = resolveRef(schema, document);
  const names = new Set<string>();
  if (resolved.properties) {
    for (const key of Object.keys(resolved.properties)) names.add(key);
  }
  if (resolved.allOf) {
    for (const part of resolved.allOf) {
      for (const key of openApiFieldNames(part, document)) names.add(key);
    }
  }
  return [...names];
}

/** Follow a single `#/components/schemas/Name` reference; otherwise return as-is. */
function resolveRef(schema: OpenApiSchema, document: OpenApiDocument): OpenApiSchema {
  if (!schema.$ref) return schema;
  const name = schema.$ref.replace("#/components/schemas/", "");
  return document.components?.schemas?.[name] ?? schema;
}
