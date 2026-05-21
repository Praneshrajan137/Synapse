// SYNAPSE FE — Canonical JSON serialization.
// Mirrors the backend rule from CLAUDE.md / I-8:
//   json.dumps(obj, sort_keys=True, separators=(',', ':'))
// We use it on every outgoing body so payload bytes hash-stable across runs
// (critical for KV-cache stability on the LLM round-trip, I-13).

type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * Deterministic JSON.stringify:
 *  - Object keys sorted lexicographically (recursive).
 *  - No whitespace.
 *  - Rejects NaN/Infinity (matches Python json.dumps default).
 *  - undefined inside arrays serializes as null (matches JSON.stringify);
 *    undefined values on objects are dropped.
 */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

function canonicalize(value: unknown): JsonValue {
  if (value === null) return null;
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new RangeError(`canonicalJson: non-finite number ${value}`);
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((v) => (v === undefined ? null : canonicalize(v)));
  }
  if (isPlainObject(value)) {
    const keys = Object.keys(value).sort();
    const out: Record<string, JsonValue> = {};
    for (const k of keys) {
      const v = value[k];
      if (v === undefined) continue;
      out[k] = canonicalize(v);
    }
    return out;
  }
  // Dates: ISO string (matches Python pydantic default).
  if (value instanceof Date) return value.toISOString();
  // bigint / symbol / function — refuse.
  throw new TypeError(`canonicalJson: unsupported value of type ${typeof value}`);
}
