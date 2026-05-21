/**
 * SYNAPSE Atlas Console — canonical JSON encoder.
 *
 * Mirrors the backend's I-13 contract:
 *   `json.dumps(obj, sort_keys=True, separators=(',',':'))`
 *
 * Why we need this on the client:
 *   - Decision payloads sent to /a2a and /api/v1/decisions feed the
 *     Pinecone semantic decision cache (ADR-018) and the LLM KV cache
 *     (ADR-021). Stable byte-for-byte serialization preserves the cache
 *     prefix; an unsorted object key shuffles every cache entry.
 *   - Audit chain proofs in Audit Vault (plan §5.6) hash canonicalised
 *     rows; the client recomputes the hash to verify the chain. If our
 *     encoder disagrees with Python's json.dumps the chain looks broken.
 *
 * Property tests (`fast-check`) compare this output against a Python
 * fixture corpus committed to src/shared/test/fixtures/canonical/.
 *
 * Behaviour:
 *   - Object keys sorted ascending by Unicode codepoint (matches Python's
 *     `sorted()` on string keys).
 *   - Separators ',' and ':' (no spaces).
 *   - Arrays preserve order.
 *   - Numbers serialise via JSON.stringify; NaN / Infinity throw (mirrors
 *     Python's allow_nan=True default-rejection in strict mode).
 *   - Undefined values dropped (matches JSON.stringify); objects with
 *     non-finite numeric values throw to surface the bug early.
 *   - Disallows custom toJSON() to avoid silent reshaping; serialise
 *     domain types yourself before calling.
 */

const SEP_ITEM = ",";
const SEP_KV = ":";

export class CanonicalJsonError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CanonicalJsonError";
  }
}

export function canonicalize(value: unknown): string {
  return encode(value);
}

function encode(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) {
    throw new CanonicalJsonError("undefined is not JSON-serializable");
  }
  const t = typeof value;
  if (t === "boolean") return value ? "true" : "false";
  if (t === "number") {
    const n = value as number;
    if (!Number.isFinite(n)) {
      throw new CanonicalJsonError(`non-finite number ${String(n)} cannot be canonicalised`);
    }
    return JSON.stringify(n);
  }
  if (t === "string") return JSON.stringify(value as string);
  if (t === "bigint") {
    throw new CanonicalJsonError("bigint is not JSON-serializable");
  }
  if (Array.isArray(value)) {
    return "[" + value.map(encode).join(SEP_ITEM) + "]";
  }
  if (t === "object") {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const parts: string[] = [];
    for (const k of keys) {
      const v = obj[k];
      if (v === undefined) continue; // matches JSON.stringify omission
      parts.push(JSON.stringify(k) + SEP_KV + encode(v));
    }
    return "{" + parts.join(SEP_ITEM) + "}";
  }
  throw new CanonicalJsonError(`unsupported value of type ${t}`);
}
