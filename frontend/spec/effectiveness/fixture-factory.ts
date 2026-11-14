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

import { z } from "zod";

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
 * unsound fixture. `typeName` carries the zod 4 kind (`schema._zod.def.type`), or the
 * definition member the walk could not read as a schema.
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
// Zod introspection helpers (zod 4: `schema._zod.def`, discriminated by `type`)
// ─────────────────────────────────────────────────────────────────────────

/**
 * The members of a zod 4 definition (`schema._zod.def`) the factory reads. zod declares only the
 * base `$ZodTypeDef`, so the kind-specific members are `unknown` here and every schema-valued
 * one passes {@link schemaAt} before it is used.
 */
interface ZodDefView {
  readonly type?: string;
  readonly checks?: ReadonlyArray<z.core.$ZodCheck<never>> | undefined;
  /** Set on a schema that is its own check: `z.uuid()` ("string_format"), `z.int()`. */
  readonly check?: unknown;
  readonly format?: unknown;
  readonly innerType?: unknown;
  readonly in?: unknown;
  readonly out?: unknown;
  readonly getter?: unknown;
  readonly shape?: unknown;
  readonly element?: unknown;
  readonly keyType?: unknown;
  readonly valueType?: unknown;
  readonly items?: unknown;
  readonly options?: unknown;
  readonly left?: unknown;
  readonly right?: unknown;
}

/**
 * The members of a zod 4 check definition (`check._zod.def`) the factory reads. `check` names the
 * kind ("string_format", "min_length", "max_length", "greater_than", "less_than",
 * "multiple_of", "number_format", "custom", ...); the rest are that kind's parameters.
 */
interface ZodCheckView {
  readonly check: string;
  readonly format?: unknown;
  readonly value?: unknown;
  readonly inclusive?: unknown;
  readonly minimum?: unknown;
  readonly maximum?: unknown;
  readonly length?: unknown;
}

/** The internal definition of a Zod schema. */
function defOf(schema: z.ZodType): ZodDefView {
  return schema._zod.def;
}

/** The definitions of the checks attached to a schema, in the order they were chained. */
function checksOf(def: ZodDefView): readonly ZodCheckView[] {
  const checks: ReadonlyArray<z.core.$ZodCheck<never>> = def.checks ?? [];
  return checks.map((check) => check._zod.def);
}

/** A schema-valued member of a definition, or an {@link UnsupportedSchemaError} naming it. */
function schemaAt(value: unknown, where: string, schemaId?: SchemaId): z.ZodType {
  if (value instanceof z.ZodType) return value;
  throw new UnsupportedSchemaError(where, schemaId);
}

/** A schema-array member of a definition (tuple items, union options), each one checked. */
function schemasAt(value: unknown, where: string, schemaId?: SchemaId): z.ZodType[] {
  if (!Array.isArray(value)) throw new UnsupportedSchemaError(where, schemaId);
  return value.map((item: unknown, i) => schemaAt(item, `${where}[${i}]`, schemaId));
}

/** The `[key, schema]` fields of an object definition, in declaration order. */
function fieldsOf(def: ZodDefView, schemaId?: SchemaId): Array<[string, z.ZodType]> {
  const shape = def.shape;
  if (typeof shape !== "object" || shape === null) {
    throw new UnsupportedSchemaError("object.shape", schemaId);
  }
  return Object.entries(shape).map(([key, field]): [string, z.ZodType] => [
    key,
    schemaAt(field, `object.shape.${key}`, schemaId),
  ]);
}

/** The finite value set of a literal or enum: `_zod.values`, the set zod's own parse checks. */
function valuesOf(schema: z.ZodType, kind: string, schemaId?: SchemaId): unknown[] {
  const values = schema._zod.values;
  if (values === undefined || values.size === 0) {
    throw new UnsupportedSchemaError(`${kind}(no values)`, schemaId);
  }
  return [...values];
}

const MAX_DEPTH = 8;

// ─────────────────────────────────────────────────────────────────────────
// Schema-driven value generation
// ─────────────────────────────────────────────────────────────────────────

/**
 * Derive a value that satisfies `schema`, drawing all entropy from `rng`
 * (Req 1.3, 2.2). Throws {@link UnsupportedSchemaError} for a Zod construct the
 * factory does not model, so an unsound fixture is never emitted silently.
 *
 * zod 4 has no `ZodEffects` wrapper: `.refine()`/`.superRefine()` add a "custom" check to the
 * refined schema itself, and `.transform()`/`z.preprocess()` build a "pipe". Such a node is
 * re-drawn deterministically until the whole node accepts the value, as the zod 3 `ZodEffects`
 * branch did, so cross-field refinements (e.g. the pricing I-6 cap) are satisfied. The caller's
 * safeParse still guards against an unsatisfiable refinement.
 */
export function generateValue(
  schema: z.ZodType,
  rng: Rng,
  depth = 0,
  schemaId?: SchemaId,
): unknown {
  const def = defOf(schema);
  let candidate = generateKind(schema, def, rng, depth, schemaId);
  if (needsRedraw(def)) {
    for (let attempt = 0; attempt < 32 && !schema.safeParse(candidate).success; attempt += 1) {
      candidate = generateKind(schema, def, rng, depth, schemaId);
    }
  }
  return candidate;
}

/** Whether a node can reject what its kind's generator drew: a refinement, or a pipe. */
function needsRedraw(def: ZodDefView): boolean {
  return def.type === "pipe" || checksOf(def).some((check) => check.check === "custom");
}

/** One draw for `schema`, dispatched on its zod 4 kind (`_zod.def.type`). */
function generateKind(
  schema: z.ZodType,
  def: ZodDefView,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
): unknown {
  const kind = def.type;
  switch (kind) {
    // ── wrappers: unwrap and generate the inner value ─────────────────────
    case "optional":
    case "nullable":
    case "readonly":
    case "default":
    case "prefault":
    case "nonoptional":
    case "catch": {
      const inner = schemaAt(def.innerType, `${kind}.innerType`, schemaId);
      return generateValue(inner, rng, depth, schemaId);
    }
    case "pipe": {
      // `.transform()` builds pipe(schema -> transform): draw the input schema.
      // `z.preprocess()` builds pipe(transform -> schema): draw the target schema, as the
      // zod 3 preprocess branch did.
      const input = schemaAt(def.in, "pipe.in", schemaId);
      const drawn =
        defOf(input).type === "transform" ? schemaAt(def.out, "pipe.out", schemaId) : input;
      return generateValue(drawn, rng, depth, schemaId);
    }
    case "lazy": {
      const getter = def.getter;
      if (typeof getter !== "function") throw new UnsupportedSchemaError("lazy.getter", schemaId);
      return generateValue(schemaAt(getter(), "lazy.getter()", schemaId), rng, depth, schemaId);
    }

    // ── primitives ────────────────────────────────────────────────────────
    case "string":
      return generateString(stringConstraints(def, schemaId), rng);
    case "number":
    case "int":
      return generateNumber(numberConstraints(def), rng);
    case "boolean":
      return rng() < 0.5;
    case "bigint":
      return BigInt(Math.floor(rng() * 1_000_000));
    case "date":
      return new Date(isoBaseMs + Math.floor(rng() * isoRangeMs));
    case "literal":
    case "enum":
      return pick(valuesOf(schema, kind, schemaId), rng);
    case "null":
      return null;
    case "undefined":
    case "void":
      return undefined;
    case "nan":
      return Number.NaN;
    case "any":
    case "unknown":
      return null;

    // ── composites ──────────────────────────────────────────────────────
    case "object":
      return generateObject(fieldsOf(def, schemaId), rng, depth, schemaId);
    case "array":
      return generateArray(def, rng, depth, schemaId);
    case "record":
      return generateRecord(def, rng, depth, schemaId);
    case "map":
      return generateMap(def, rng, depth, schemaId);
    case "set":
      return new Set(
        generateArrayOf(schemaAt(def.valueType, "set.valueType", schemaId), rng, depth, schemaId),
      );
    case "tuple":
      return schemasAt(def.items, "tuple.items", schemaId).map((item) =>
        generateValue(item, rng, depth + 1, schemaId),
      );
    case "union":
      return generateUnion(def, rng, depth, schemaId);
    case "intersection":
      return mergeValues(
        generateValue(schemaAt(def.left, "intersection.left", schemaId), rng, depth, schemaId),
        generateValue(schemaAt(def.right, "intersection.right", schemaId), rng, depth, schemaId),
      );

    default:
      throw new UnsupportedSchemaError(kind ?? "undefined", schemaId);
  }
}

// ── string generation honoring format and length checks ───────────────────

const isoBaseMs = Date.UTC(2024, 0, 1, 0, 0, 0);
const isoRangeMs = 365 * 24 * 60 * 60 * 1000;

/** The schema's own check, then its chained ones: `z.uuid()` and `z.int()` are their own check. */
function constraintChecks(def: ZodDefView): readonly ZodCheckView[] {
  const own: readonly ZodCheckView[] =
    typeof def.check === "string" ? [{ check: def.check, format: def.format }] : [];
  return [...own, ...checksOf(def)];
}

/** Length bounds read from "min_length", "max_length" and "length_equals" checks. */
interface LengthBounds {
  readonly min: number | undefined;
  readonly max: number | undefined;
}

/** The tightest length bounds a check list places on a string or an array. */
function lengthBoundsOf(checks: readonly ZodCheckView[]): LengthBounds {
  let min: number | undefined;
  let max: number | undefined;
  for (const check of checks) {
    if (check.check === "min_length" && typeof check.minimum === "number") {
      min = Math.max(min ?? 0, check.minimum);
    } else if (check.check === "max_length" && typeof check.maximum === "number") {
      max = Math.min(max ?? check.maximum, check.maximum);
    } else if (check.check === "length_equals" && typeof check.length === "number") {
      min = check.length;
      max = check.length;
    }
  }
  return { min, max };
}

/** The string formats {@link generateString} can satisfy; any other format is refused. */
const GENERATED_STRING_FORMATS: ReadonlySet<string> = new Set([
  "uuid",
  "guid",
  "datetime",
  "date",
  "email",
  "url",
]);

/** What a string schema requires of a drawn value. */
interface StringConstraints extends LengthBounds {
  readonly formats: ReadonlySet<string>;
}

/**
 * The formats and length bounds of a string schema. zod 4 carries a format as a
 * "string_format" check (`.uuid()`, `.datetime()`), so a format this factory does not model is
 * refused here rather than drawn as an arbitrary string the schema would reject.
 */
function stringConstraints(def: ZodDefView, schemaId?: SchemaId): StringConstraints {
  const checks = constraintChecks(def);
  const formats = new Set<string>();
  for (const check of checks) {
    if (check.check !== "string_format" || typeof check.format !== "string") continue;
    if (!GENERATED_STRING_FORMATS.has(check.format)) {
      throw new UnsupportedSchemaError(`string_format(${check.format})`, schemaId);
    }
    formats.add(check.format);
  }
  return { formats, ...lengthBoundsOf(checks) };
}

/** A deterministic ISO-8601 UTC instant inside the fixture year. */
function isoInstant(rng: Rng): string {
  return new Date(isoBaseMs + Math.floor(rng() * isoRangeMs)).toISOString();
}

function generateString(constraints: StringConstraints, rng: Rng): string {
  const { formats, min, max } = constraints;
  if (formats.has("uuid") || formats.has("guid")) return generateUuid(rng);
  if (formats.has("datetime")) return isoInstant(rng);
  if (formats.has("date")) return isoInstant(rng).slice(0, 10);
  if (formats.has("email")) return `op-${intToken(rng)}@example.invalid`;
  if (formats.has("url")) return `https://example.invalid/${intToken(rng)}`;

  // Respect explicit length bounds; keep it short and deterministic otherwise.
  let value = `str-${intToken(rng)}`;
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

// ── number generation honoring integer format, bounds and multipleOf ──────

/** A numeric bound read from a "greater_than" or "less_than" check. */
interface NumericBound {
  readonly value: number;
  readonly inclusive: boolean;
}

/** What a number schema requires of a drawn value. */
interface NumberConstraints {
  readonly integer: boolean;
  readonly lower: NumericBound | undefined;
  readonly upper: NumericBound | undefined;
  readonly multipleOf: number | undefined;
}

/** zod 4's integer number formats; `.int()` and `z.int()` carry "safeint". */
const INTEGER_FORMATS: ReadonlySet<string> = new Set(["safeint", "int32", "uint32"]);

function numericBound(check: ZodCheckView): NumericBound | undefined {
  if (typeof check.value !== "number") return undefined;
  return { value: check.value, inclusive: check.inclusive !== false };
}

/**
 * The integer format, the tightest bounds and the multiple of a number schema. zod 4 records
 * `.min()` and `.nonnegative()` as an inclusive "greater_than", `.positive()` as an exclusive
 * one, `.max()` as "less_than", and `.int()` as a "number_format" check.
 */
function numberConstraints(def: ZodDefView): NumberConstraints {
  let integer = false;
  let lower: NumericBound | undefined;
  let upper: NumericBound | undefined;
  let multipleOf: number | undefined;
  for (const check of constraintChecks(def)) {
    if (check.check === "number_format" && typeof check.format === "string") {
      if (INTEGER_FORMATS.has(check.format)) integer = true;
    } else if (check.check === "greater_than") {
      const bound = numericBound(check);
      if (bound !== undefined && (lower === undefined || bound.value > lower.value)) {
        lower = bound;
      }
    } else if (check.check === "less_than") {
      const bound = numericBound(check);
      if (bound !== undefined && (upper === undefined || bound.value < upper.value)) {
        upper = bound;
      }
    } else if (check.check === "multiple_of" && typeof check.value === "number") {
      multipleOf = check.value;
    }
  }
  return { integer, lower, upper, multipleOf };
}

function generateNumber(constraints: NumberConstraints, rng: Rng): number {
  const { integer, multipleOf } = constraints;
  const step = integer ? 1 : 1e-6;

  let lower = 0;
  if (constraints.lower !== undefined) {
    const bound = constraints.lower;
    lower = bound.inclusive ? bound.value : bound.value + step;
  }
  let upper = lower + 100;
  if (constraints.upper !== undefined) {
    const bound = constraints.upper;
    upper = bound.inclusive ? bound.value : bound.value - step;
  }
  if (upper < lower) upper = lower;

  let value = lower + rng() * (upper - lower);
  if (integer) {
    value = Math.round(value);
    if (value < lower) value = Math.ceil(lower);
    if (value > upper) value = Math.floor(upper);
  }

  if (multipleOf !== undefined && multipleOf > 0) {
    value = Math.round(value / multipleOf) * multipleOf;
    if (value < lower) value += multipleOf;
  }
  return value;
}

// ── composite generation ──────────────────────────────────────────────────

function generateObject(
  fields: ReadonlyArray<readonly [string, z.ZodType]>,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, field] of fields) {
    // Beyond the depth guard, only populate required fields to keep fixtures
    // finite for (hypothetical) deeply-nested schemas.
    if (depth >= MAX_DEPTH && isOptional(field)) continue;
    const value = generateValue(field, rng, depth + 1, schemaId);
    if (value !== undefined) out[key] = value;
  }
  return out;
}

/** zod 4 keeps an array's element at `def.element` and its length bounds as checks. */
function generateArray(def: ZodDefView, rng: Rng, depth: number, schemaId?: SchemaId): unknown[] {
  const element = schemaAt(def.element, "array.element", schemaId);
  const { min, max } = lengthBoundsOf(checksOf(def));
  return generateArrayOf(element, rng, depth, schemaId, min, max);
}

function generateArrayOf(
  element: z.ZodType,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
  min?: number,
  max?: number,
): unknown[] {
  let count = Math.max(min ?? 0, depth < 3 ? 2 : 1);
  if (max !== undefined) count = Math.min(count, max);
  const items: unknown[] = [];
  for (let i = 0; i < count; i += 1) items.push(generateValue(element, rng, depth + 1, schemaId));
  return items;
}

/**
 * zod 4 makes a record over an enumerable key schema (an enum or a literal) exhaustive, so every
 * key in the key schema's `_zod.values` is drawn. Any other key schema is sampled, as before.
 */
function generateRecord(
  def: ZodDefView,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
): Record<string, unknown> {
  const keyType = schemaAt(def.keyType, "record.keyType", schemaId);
  const valueType = schemaAt(def.valueType, "record.valueType", schemaId);
  const out: Record<string, unknown> = {};
  const exhaustiveKeys = keyType._zod.values;
  if (exhaustiveKeys !== undefined) {
    for (const key of exhaustiveKeys) {
      out[String(key)] = generateValue(valueType, rng, depth + 1, schemaId);
    }
    return out;
  }
  const count = depth < 3 ? 2 : 1;
  for (let i = 0; i < count; i += 1) {
    const key = String(generateValue(keyType, rng, depth + 1, schemaId));
    out[key] = generateValue(valueType, rng, depth + 1, schemaId);
  }
  return out;
}

function generateMap(
  def: ZodDefView,
  rng: Rng,
  depth: number,
  schemaId?: SchemaId,
): Map<unknown, unknown> {
  const keyType = schemaAt(def.keyType, "map.keyType", schemaId);
  const valueType = schemaAt(def.valueType, "map.valueType", schemaId);
  const map = new Map<unknown, unknown>();
  const count = depth < 3 ? 2 : 1;
  for (let i = 0; i < count; i += 1) {
    map.set(
      generateValue(keyType, rng, depth + 1, schemaId),
      generateValue(valueType, rng, depth + 1, schemaId),
    );
  }
  return map;
}

/** One drawn option of a union. A zod 4 discriminated union is a "union" kind too. */
function generateUnion(def: ZodDefView, rng: Rng, depth: number, schemaId?: SchemaId): unknown {
  const options = schemasAt(def.options, "union.options", schemaId);
  if (options.length === 0) throw new UnsupportedSchemaError("union(empty)", schemaId);
  return generateValue(pick(options, rng), rng, depth, schemaId);
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

/**
 * Whether an object field may be absent, by zod 4's own predicate: the object parse treats a key
 * as optional iff its schema's `_zod.optin` is set (`isOptionalField` in
 * `spec/contract-fidelity/introspect.ts` reads the same member).
 */
function isOptional(field: z.ZodType): boolean {
  return field._zod.optin !== undefined;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** A failed parse's issues as `path: message`. A zod 4 issue path is `PropertyKey[]`. */
function formatIssues(parsed: {
  readonly error: { readonly issues: readonly z.core.$ZodIssue[] };
}): string {
  return parsed.error.issues
    .map((issue) => {
      const where = issue.path.map((segment) => String(segment)).join(".");
      return `${where || "<root>"}: ${issue.message}`;
    })
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
function violationCandidates(schema: z.ZodType, seed: number, schemaId: SchemaId): unknown[] {
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
