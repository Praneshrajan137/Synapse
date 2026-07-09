/**
 * Effectiveness_Harness — schema-bound fixture factory (Req 2).
 *
 * This module derives every `MSW_Fixture`'s shape from a `Domain_Schema` in the
 * shared registry (`./schema-registry.ts`) and validates the constructed
 * fixture against that *same* schema at build/setup time. A fixture that fails
 * its bound schema throws {@link FixtureSchemaError} naming the offending
 * fixture and schema, so fixture drift from the contract is caught mechanically
 * (design "A. Harness — schema registry + fixture factory"; Requirements 2.1,
 * 2.2, 2.3).
 *
 * Because the fixture body is *derived from* the registry schema and then
 * re-validated through the same schema, a schema change that would invalidate a
 * fixture fails loudly at build/setup rather than silently shipping a mock that
 * misrepresents the real contract.
 *
 * A capability with no `Domain_Schema` (`schemaId === null`) is classified
 * `schema-less` and surfaced as such in the harness report — never treated as
 * schema-bound (Requirement 2.4). A per-channel {@link buildSchemaViolatingFixture}
 * emits an intentionally schema-violating payload on demand so Requirement 8's
 * schema-violation transition can be exercised deterministically (Requirement
 * 2.5).
 *
 * Determinism (Requirement 1.3): the `seed` on a request is the *only* entropy
 * source. Every generator draws from a seeded PRNG, so a given
 * `(schemaId, seed)` pair yields the same body on every run.
 */

import type { ZodTypeAny } from "zod";

import { type SchemaId, getSchema, hasSchema } from "./schema-registry";

// ─────────────────────────────────────────────────────────────────────────
// Public interface (design "A. Harness — schema registry + fixture factory")
// ─────────────────────────────────────────────────────────────────────────

/** A request to build one fixture for a single Backend_Contract capability. */
export interface FixtureRequest {
  /** The capability the fixture serves, e.g. `decisions.GET./api/v1/decisions/recent`. */
  readonly capabilityId: string;
  /** The bound schema id, or `null` for a schema-less capability (Req 2.4). */
  readonly schemaId: SchemaId | null;
  /** The only entropy source — full determinism (Req 1.3). */
  readonly seed: number;
}

/** The result of building a fixture: schema-bound or schema-less (Req 2.4). */
export type FixtureResult =
  | { readonly kind: "schema-bound"; readonly schemaId: SchemaId; readonly body: unknown }
  | { readonly kind: "schema-less"; readonly capabilityId: string; readonly body: unknown };

/** How a fixture's contract binding is reported in the harness report (Req 2.4). */
export type FixtureClassification =
  | { readonly kind: "schema-bound"; readonly schemaId: SchemaId }
  | { readonly kind: "schema-less"; readonly reason: "no-body" | "open-shape" };

// ─────────────────────────────────────────────────────────────────────────
// Errors — build/setup-time failures that name the offending fixture + schema
// ─────────────────────────────────────────────────────────────────────────

/**
 * Thrown at build/setup when a fixture body fails its bound `Domain_Schema`, or
 * when a request names a `schemaId` that is not registered. Names both the
 * offending fixture and the schema (Requirements 2.1, 2.3).
 */
export class FixtureSchemaError extends Error {
  constructor(
    readonly fixtureId: string,
    readonly schemaId: SchemaId,
    readonly detail?: string,
  ) {
    super(
      `Fixture "${fixtureId}" failed Domain_Schema "${schemaId}" validation${detail ? `: ${detail}` : ""}`,
    );
    this.name = "FixtureSchemaError";
  }
}

/**
 * Thrown when the generator encounters a Zod construct it cannot derive a value
 * for. This is a factory-coverage gap, surfaced loudly rather than emitting an
 * unsound fixture.
 */
export class UnsupportedSchemaError extends Error {
  constructor(
    readonly typeName: string,
    readonly schemaId?: SchemaId,
  ) {
    super(
      `Fixture factory cannot derive a value for Zod construct "${typeName}"${schemaId ? ` (schema "${schemaId}")` : ""}`,
    );
    this.name = "UnsupportedSchemaError";
  }
}

// ─────────────────────────────────────────────────────────────────────────
// buildFixture / classifyFixture / buildSchemaViolatingFixture
// ─────────────────────────────────────────────────────────────────────────

/**
 * Build a fixture for `req`. A schema-bound request derives its body from the
 * registry schema and re-validates it through that same schema; on failure it
 * throws {@link FixtureSchemaError} naming the fixture and schema (Req 2.1,
 * 2.2, 2.3). A schema-less request (`schemaId === null`) returns a `schema-less`
 * result whose classification the harness report surfaces (Req 2.4).
 */
export function buildFixture(req: FixtureRequest): FixtureResult {
  if (req.schemaId === null) {
    return { kind: "schema-less", capabilityId: req.capabilityId, body: schemaLessBody() };
  }

  const schema = getSchema(req.schemaId);
  if (schema === undefined) {
    throw new FixtureSchemaError(
      req.capabilityId,
      req.schemaId,
      "no Domain_Schema is registered under this schemaId",
    );
  }

  const generated = generateValue(schema, makeRng(req.seed), 0, req.schemaId);
  const parsed = schema.safeParse(generated);
  if (!parsed.success) {
    throw new FixtureSchemaError(req.capabilityId, req.schemaId, formatIssues(parsed));
  }
  // Return the schema-normalized value: defaults applied, unknown keys handled
  // per the schema's own policy, so the emitted body is exactly what the
  // Console would accept at runtime.
  return { kind: "schema-bound", schemaId: req.schemaId, body: parsed.data };
}

/**
 * Classify a capability's fixture binding for the harness report (Req 2.4). A
 * capability whose `schemaId` resolves in the registry is `schema-bound`;
 * otherwise it is `schema-less`.
 *
 * The schema-less `reason` is inferred from the capability id: streamed
 * channels (WS/SSE) carry open, unconstrained payloads (`open-shape`), while
 * everything else with no schema is a no-body/ack endpoint (`no-body`). This is
 * a deliberately conservative heuristic — the contract-fidelity drift suite
 * (task 19.1 / Req 16) is the authoritative classifier of schema-less
 * capabilities; here we only need to avoid treating a schema-less capability as
 * schema-bound.
 */
export function classifyFixture(req: FixtureRequest): FixtureClassification {
  if (req.schemaId !== null && hasSchema(req.schemaId)) {
    return { kind: "schema-bound", schemaId: req.schemaId };
  }
  return { kind: "schema-less", reason: inferSchemaLessReason(req.capabilityId) };
}

/**
 * Emit an intentionally schema-violating body for a channel on demand so
 * Requirement 8's schema-violation transition can be exercised deterministically
 * (Req 2.5, Req 8.2). The returned value is guaranteed to fail
 * `schema.safeParse` — we construct candidate corruptions and return the first
 * that the bound schema rejects.
 *
 * @throws {FixtureSchemaError} when `schemaId` is not registered.
 */
export function buildSchemaViolatingFixture(schemaId: SchemaId, seed: number): unknown {
  const schema = getSchema(schemaId);
  if (schema === undefined) {
    throw new FixtureSchemaError(
      `schema-violation:${schemaId}`,
      schemaId,
      "no Domain_Schema is registered under this schemaId",
    );
  }

  for (const candidate of violationCandidates(schema, seed, schemaId)) {
    if (!schema.safeParse(candidate).success) return candidate;
  }
  // Every candidate validated — the schema is effectively unconstrained, so it
  // cannot host a deterministic violation. Surface that loudly.
  throw new Error(
    `Could not construct a schema-violating payload for Domain_Schema "${schemaId}": the schema accepts every candidate (no constrained field to violate).`,
  );
}

/** A generic body for a schema-less capability — there is no schema to derive. */
function schemaLessBody(): unknown {
  return {};
}

/** Heuristic reason for a schema-less classification (see {@link classifyFixture}). */
function inferSchemaLessReason(capabilityId: string): "no-body" | "open-shape" {
  return capabilityId.includes(".WS.") || capabilityId.includes(".SSE.") ? "open-shape" : "no-body";
}

// ─────────────────────────────────────────────────────────────────────────
// Deterministic PRNG — seed is the only entropy source (Req 1.3)
// ─────────────────────────────────────────────────────────────────────────

/** A deterministic 0..1 generator seeded from a single integer (mulberry32). */
export type Rng = () => number;

/** Build a deterministic PRNG from a seed. Same seed ⇒ same sequence. */
export function makeRng(seed: number): Rng {
  let a = seed >>> 0;
  if (a === 0) a = 0x9e3779b9; // avoid the zero fixed-point
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ─────────────────────────────────────────────────────────────────────────
// Zod introspection helpers
// ─────────────────────────────────────────────────────────────────────────

interface ZodDef {
  readonly typeName: string;
  readonly [key: string]: unknown;
}

interface ZodCheck {
  readonly kind: string;
  readonly value?: unknown;
  readonly inclusive?: boolean;
}

/** The internal `_def` of a Zod schema (typed loosely — Zod does not export it). */
function defOf(schema: ZodTypeAny): ZodDef {
  return (schema as unknown as { _def: ZodDef })._def;
}

/** The object shape of a `ZodObject` (via its `.shape` getter). */
function shapeOf(schema: ZodTypeAny): Record<string, ZodTypeAny> {
  return (schema as unknown as { shape: Record<string, ZodTypeAny> }).shape;
}

const MAX_DEPTH = 8;

// ─────────────────────────────────────────────────────────────────────────
// Schema-driven value generation
// ─────────────────────────────────────────────────────────────────────────

/**
 * Derive a value that satisfies `schema`, drawing all entropy from `rng`
 * (Req 1.3, 2.2). Throws {@link UnsupportedSchemaError} for a Zod construct the
 * factory does not model, so an unsound fixture is never emitted silently.
 */
export function generateValue(
  schema: ZodTypeAny,
  rng: Rng,
  depth = 0,
  schemaId?: SchemaId,
): unknown {
  const def = defOf(schema);
  switch (def.typeName) {
    // ── wrappers: unwrap and generate the inner value ─────────────────────
    case "ZodOptional":
    case "ZodNullable":
    case "ZodReadonly":
    case "ZodBranded":
    case "ZodDefault":
    case "ZodCatch":
      return generateValue(def.innerType as ZodTypeAny, rng, depth, schemaId);
    case "ZodEffects": {
      // refine/transform/preprocess — generate from the underlying schema, then
      // re-draw deterministically until the *effects* node accepts the value so
      // cross-field refinements (e.g. the pricing I-6 cap) are satisfied. The
      // caller's safeParse still guards against an unsatisfiable refinement.
      const inner = def.schema as ZodTypeAny;
      let candidate = generateValue(inner, rng, depth, schemaId);
      for (let attempt = 0; attempt < 32 && !schema.safeParse(candidate).success; attempt += 1) {
        candidate = generateValue(inner, rng, depth, schemaId);
      }
      return candidate;
    }
    case "ZodPipeline":
      return generateValue(def.in as ZodTypeAny, rng, depth, schemaId);
    case "ZodLazy":
      return generateValue((def.getter as () => ZodTypeAny)(), rng, depth, schemaId);

    // ── primitives ────────────────────────────────────────────────────────
    case "ZodString":
      return generateString(def.checks as ZodCheck[] | undefined, rng);
    case "ZodNumber":
      return generateNumber(def.checks as ZodCheck[] | undefined, rng);
    case "ZodBoolean":
      return rng() < 0.5;
    case "ZodBigInt":
      return BigInt(Math.floor(rng() * 1_000_000));
    case "ZodDate":
      return new Date(isoBaseMs + Math.floor(rng() * isoRangeMs));
    case "ZodLiteral":
      return def.value;
    case "ZodEnum":
      return pick(def.values as readonly unknown[], rng);
    case "ZodNativeEnum":
      return pick(Object.values(def.values as Record<string, unknown>), rng);
    case "ZodNull":
      return null;
    case "ZodUndefined":
    case "ZodVoid":
      return undefined;
    case "ZodNaN":
      return Number.NaN;
    case "ZodAny":
    case "ZodUnknown":
      return null;

    // ── composites ──────────────────────────────────────────────────────
    case "ZodObject":
      return generateObject(shapeOf(schema), rng, depth, schemaId);
    case "ZodArray":
      return generateArray(def, rng, depth, schemaId);
    case "ZodRecord":
      return generateRecord(def, rng, depth, schemaId);
    case "ZodMap":
      return generateMap(def, rng, depth, schemaId);
    case "ZodSet":
      return new Set(
        generateArrayOf(def.valueType as ZodTypeAny | undefined, rng, depth, schemaId),
      );
    case "ZodTuple":
      return (def.items as ZodTypeAny[]).map((item) =>
        generateValue(item, rng, depth + 1, schemaId),
      );
    case "ZodUnion":
    case "ZodDiscriminatedUnion":
      return generateUnion(def.options, rng, depth, schemaId);
    case "ZodIntersection":
      return mergeValues(
        generateValue(def.left as ZodTypeAny, rng, depth, schemaId),
        generateValue(def.right as ZodTypeAny, rng, depth, schemaId),
      );

    default:
      throw new UnsupportedSchemaError(def.typeName, schemaId);
  }
}

// ── string generation honoring uuid/datetime/length checks ────────────────

const isoBaseMs = Date.UTC(2024, 0, 1, 0, 0, 0);
const isoRangeMs = 365 * 24 * 60 * 60 * 1000;

function generateString(checks: ZodCheck[] | undefined, rng: Rng): string {
  const kinds = new Set((checks ?? []).map((c) => c.kind));
  if (kinds.has("uuid")) return generateUuid(rng);
  if (kinds.has("datetime"))
    return new Date(isoBaseMs + Math.floor(rng() * isoRangeMs)).toISOString();
  if (kinds.has("email")) return `op-${intToken(rng)}@example.invalid`;
  if (kinds.has("url")) return `https://example.invalid/${intToken(rng)}`;

  // Respect an explicit min length; keep it short and deterministic otherwise.
  let value = `str-${intToken(rng)}`;
  const min = numericCheck(checks, "min");
  const max = numericCheck(checks, "max");
  if (min !== undefined && value.length < min) value = value.padEnd(min, "x");
  if (max !== undefined && value.length > max) value = value.slice(0, Math.max(0, max));
  return value;
}

/** A deterministic RFC-4122 v4 UUID (matches Zod's `.uuid()` check). */
function generateUuid(rng: Rng): string {
  const hex = () => Math.floor(rng() * 16).toString(16);
  let out = "";
  for (let i = 0; i < 36; i += 1) {
    if (i === 8 || i === 13 || i === 18 || i === 23) out += "-";
    else if (i === 14) out += "4";
    else if (i === 19) out += (8 + Math.floor(rng() * 4)).toString(16);
    else out += hex();
  }
  return out;
}

function intToken(rng: Rng): string {
  return Math.floor(rng() * 0x7fffffff).toString(36);
}

// ── number generation honoring int/min/max/positive/multipleOf ────────────

function generateNumber(checks: ZodCheck[] | undefined, rng: Rng): number {
  const isInt = (checks ?? []).some((c) => c.kind === "int");
  const minCheck = (checks ?? []).find((c) => c.kind === "min");
  const maxCheck = (checks ?? []).find((c) => c.kind === "max");
  const step = isInt ? 1 : 1e-6;

  let lower = 0;
  if (minCheck && typeof minCheck.value === "number") {
    lower = minCheck.inclusive === false ? minCheck.value + step : minCheck.value;
  }
  let upper: number;
  if (maxCheck && typeof maxCheck.value === "number") {
    upper = maxCheck.inclusive === false ? maxCheck.value - step : maxCheck.value;
  } else {
    upper = lower + 100;
  }
  if (upper < lower) upper = lower;

  let value = lower + rng() * (upper - lower);
  if (isInt) {
    value = Math.round(value);
    if (value < lower) value = Math.ceil(lower);
    if (value > upper) value = Math.floor(upper);
  }

  const multiple = (checks ?? []).find((c) => c.kind === "multipleOf");
  if (multiple && typeof multiple.value === "number" && multiple.value > 0) {
    const m = multiple.value;
    value = Math.round(value / m) * m;
    if (value < lower) value += m;
  }
  return value;
}

function numericCheck(checks: ZodCheck[] | undefined, kind: string): number | undefined {
  const found = (checks ?? []).find((c) => c.kind === kind);
  return found && typeof found.value === "number" ? found.value : undefined;
}

// ── composite generation ──────────────────────────────────────────────────

function generateObject(
  shape: Record<string, ZodTypeAny>,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(shape)) {
    const field = shape[key];
    if (field === undefined) continue;
    // Beyond the depth guard, only populate required fields to keep fixtures
    // finite for (hypothetical) deeply-nested schemas.
    if (depth >= MAX_DEPTH && isOptional(field)) continue;
    const value = generateValue(field, rng, depth + 1, schemaId);
    if (value !== undefined) out[key] = value;
  }
  return out;
}

function generateArray(def: ZodDef, rng: Rng, depth: number, schemaId?: SchemaId): unknown[] {
  return generateArrayOf(
    def.type as ZodTypeAny | undefined,
    rng,
    depth,
    schemaId,
    readLength(def.minLength),
    readLength(def.maxLength),
  );
}

function generateArrayOf(
  element: ZodTypeAny | undefined,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
  min?: number,
  max?: number,
): unknown[] {
  if (element === undefined) return [];
  let count = Math.max(min ?? 0, depth < 3 ? 2 : 1);
  if (max !== undefined) count = Math.min(count, max);
  const items: unknown[] = [];
  for (let i = 0; i < count; i += 1) items.push(generateValue(element, rng, depth + 1, schemaId));
  return items;
}

function readLength(raw: unknown): number | undefined {
  if (raw && typeof raw === "object" && typeof (raw as { value?: unknown }).value === "number") {
    return (raw as { value: number }).value;
  }
  return undefined;
}

function generateRecord(
  def: ZodDef,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
): Record<string, unknown> {
  const valueType = def.valueType as ZodTypeAny | undefined;
  const keyType = def.keyType as ZodTypeAny | undefined;
  if (valueType === undefined) return {};
  const out: Record<string, unknown> = {};
  const count = depth < 3 ? 2 : 1;
  for (let i = 0; i < count; i += 1) {
    const key =
      keyType !== undefined
        ? String(generateValue(keyType, rng, depth + 1, schemaId))
        : `key-${intToken(rng)}`;
    out[key] = generateValue(valueType, rng, depth + 1, schemaId);
  }
  return out;
}

function generateMap(
  def: ZodDef,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
): Map<unknown, unknown> {
  const keyType = def.keyType as ZodTypeAny | undefined;
  const valueType = def.valueType as ZodTypeAny | undefined;
  const map = new Map<unknown, unknown>();
  if (keyType === undefined || valueType === undefined) return map;
  const count = depth < 3 ? 2 : 1;
  for (let i = 0; i < count; i += 1) {
    map.set(
      generateValue(keyType, rng, depth + 1, schemaId),
      generateValue(valueType, rng, depth + 1, schemaId),
    );
  }
  return map;
}

function generateUnion(options: unknown, rng: Rng, depth: number, schemaId?: SchemaId): unknown {
  const list = Array.isArray(options)
    ? (options as ZodTypeAny[])
    : options instanceof Map
      ? Array.from(options.values() as Iterable<ZodTypeAny>)
      : [];
  if (list.length === 0) throw new UnsupportedSchemaError("ZodUnion(empty)", schemaId);
  const chosen = list[Math.floor(rng() * list.length)] ?? list[0];
  return generateValue(chosen as ZodTypeAny, rng, depth, schemaId);
}

/** Deep-merge two generated values for a `ZodIntersection` (objects merge). */
function mergeValues(left: unknown, right: unknown): unknown {
  if (isPlainObject(left) && isPlainObject(right)) {
    return { ...left, ...right };
  }
  return right;
}

// ── generic helpers ────────────────────────────────────────────────────────

function pick<T>(values: readonly T[], rng: Rng): T {
  if (values.length === 0) throw new Error("Cannot pick from an empty set.");
  const value = values[Math.floor(rng() * values.length)];
  return value ?? (values[0] as T);
}

function isOptional(field: ZodTypeAny): boolean {
  const typeName = defOf(field).typeName;
  return typeName === "ZodOptional" || typeName === "ZodDefault" || typeName === "ZodNever";
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function formatIssues(parsed: {
  error: { issues: ReadonlyArray<{ path: (string | number)[]; message: string }> };
}): string {
  return parsed.error.issues
    .map((issue) => `${issue.path.join(".") || "<root>"}: ${issue.message}`)
    .join("; ");
}

// ─────────────────────────────────────────────────────────────────────────
// Schema-violation payload construction (Req 2.5)
// ─────────────────────────────────────────────────────────────────────────

/**
 * Ordered candidate payloads that are likely to violate `schema`. The caller
 * returns the first candidate the schema rejects. The first candidate is a
 * surgically-corrupted valid body (keeps the payload realistic for Req 8),
 * followed by generic wrong-type primitives as a robust fallback.
 */
function violationCandidates(schema: ZodTypeAny, seed: number, schemaId: SchemaId): unknown[] {
  const candidates: unknown[] = [];
  try {
    const base = generateValue(schema, makeRng(seed), 0, schemaId);
    const corrupted = corruptValue(base);
    if (corrupted !== undefined) candidates.push(corrupted);
  } catch {
    // If a valid base cannot be generated, the generic candidates still apply.
  }
  candidates.push("__SCHEMA_VIOLATION__", -1234567.89, true, null, ["__schema_violation__"], {
    __schema_violation__: true,
  });
  return candidates;
}

/**
 * Corrupt a generated value by flipping the type of its first constrained
 * primitive field/element, so a schema that constrains that field rejects it.
 * Returns `undefined` when no primitive is reachable at the top level.
 */
function corruptValue(value: unknown): unknown {
  if (isPlainObject(value)) {
    const clone: Record<string, unknown> = { ...value };
    for (const [key, v] of Object.entries(clone)) {
      const flipped = flipType(v);
      if (flipped !== undefined) {
        clone[key] = flipped;
        return clone;
      }
    }
    return undefined;
  }
  if (Array.isArray(value) && value.length > 0) {
    const flipped = flipType(value[0]);
    if (flipped !== undefined) return [flipped, ...value.slice(1)];
    return undefined;
  }
  return flipType(value);
}

/** A value of an incompatible primitive type, or `undefined` if not primitive. */
function flipType(v: unknown): unknown {
  if (typeof v === "number") return "__violation__";
  if (typeof v === "string") return 987654321;
  if (typeof v === "boolean") return "__violation__";
  return undefined;
}
