/**
 * SYNAPSE Atlas Console — sha256 wrapper around the Web Crypto API.
 *
 * Used by the Audit Vault chain proof (`@surfaces/$city/decisions/...`)
 * to verify that ``hash[i] === sha256(prev || canonical(row))`` matches
 * the server-emitted chain. Web Crypto is the only OSS-friendly,
 * dependency-free option for the browser; node test runs use a tiny
 * fallback via the `crypto` module.
 *
 * Returns lowercase hex by default — matches the format Postgres dumps
 * via `encode(digest('sha256', x), 'hex')`.
 */

function bytesToHex(bytes: Uint8Array): string {
  let hex = "";
  for (let i = 0; i < bytes.length; i += 1) {
    hex += bytes[i]!.toString(16).padStart(2, "0");
  }
  return hex;
}

async function digestBrowser(data: Uint8Array): Promise<Uint8Array> {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength),
  );
  return new Uint8Array(buf);
}

async function digestNode(data: Uint8Array): Promise<Uint8Array> {
  // Dynamic import — keeps the Vite browser bundle clean of node:crypto.
  const { createHash } = await import("node:crypto");
  return new Uint8Array(createHash("sha256").update(data).digest());
}

const isBrowser =
  typeof globalThis !== "undefined" &&
  typeof (globalThis as { crypto?: { subtle?: SubtleCrypto } }).crypto?.subtle !== "undefined";

const digest = isBrowser ? digestBrowser : digestNode;

export async function sha256Hex(input: string | Uint8Array): Promise<string> {
  const data =
    typeof input === "string" ? new TextEncoder().encode(input) : input;
  return bytesToHex(await digest(data));
}

/**
 * Concatenate `prev` (hex) + canonical body and return the new hex digest.
 * Mirrors the backend's chain construction exactly.
 */
export async function chainHash(
  prevHashHex: string | null,
  canonicalBody: string,
): Promise<string> {
  const prefix = prevHashHex ?? "";
  return sha256Hex(prefix + canonicalBody);
}
