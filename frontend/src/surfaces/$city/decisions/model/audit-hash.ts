/**
 * SYNAPSE Atlas Console — Decision Trace audit chain.
 *
 * Plan §5.3 / I-4. The Audit Vault and Decision-Trace drawer both verify
 * that every server-emitted row's `hash` matches
 *
 *     sha256(prev_hash || canonical_json(row_without_hash_fields))
 *
 * If the chain breaks anywhere, exports are blocked and a banner fires.
 *
 * Shape of an entry:
 *   - `hash`: hex digest the orchestrator stamped.
 *   - `prev`: hex digest of the prior entry, or null at chain head.
 *   - `body`: arbitrary record covered by the digest.
 *
 * The `body` is hashed via the project canonical JSON encoder (mirrors
 * Python's `json.dumps(sort_keys=True, separators=(',',':'))`); if the
 * server uses a different encoder, the proof breaks deterministically.
 */
import { canonicalize } from "@shared/canonical-json";
import { chainHash } from "@shared/hash/sha256";

export interface AuditEntry {
  /** Hex digest emitted by the server. */
  readonly hash: string;
  /** Previous entry's hex digest; `null` only at chain head. */
  readonly prev: string | null;
  /** Body covered by the digest. */
  readonly body: unknown;
  /** ISO 8601 timestamp; informational, not part of the digest. */
  readonly ts?: string;
}

export interface ChainVerification {
  /** True iff all entries verify and prev links chain to head. */
  readonly valid: boolean;
  /**
   * 0-based index of the first broken entry, or -1 when the chain is
   * fully valid. Used by the drawer to scroll to the bad row.
   */
  readonly brokenAt: number;
  /** Hex digest the verifier computed for the broken entry, when broken. */
  readonly expected: string | null;
  /** Whatever the server claimed at the broken entry. */
  readonly actual: string | null;
}

const VALID: ChainVerification = {
  valid: true,
  brokenAt: -1,
  expected: null,
  actual: null,
};

/**
 * Verify a chain front-to-back. Empty chains are vacuously valid; chains
 * with non-null `prev` at index 0 fail (the head must be unanchored).
 */
export async function verifyChain(
  entries: readonly AuditEntry[],
): Promise<ChainVerification> {
  if (entries.length === 0) return VALID;

  let prevHash: string | null = null;
  for (let i = 0; i < entries.length; i += 1) {
    const entry = entries[i]!;
    if (i === 0 && entry.prev !== null) {
      return {
        valid: false,
        brokenAt: 0,
        expected: null,
        actual: entry.prev,
      };
    }
    if (i > 0 && entry.prev !== prevHash) {
      return {
        valid: false,
        brokenAt: i,
        expected: prevHash,
        actual: entry.prev,
      };
    }
    const computed = await chainHash(entry.prev, canonicalize(entry.body));
    if (computed !== entry.hash) {
      return {
        valid: false,
        brokenAt: i,
        expected: computed,
        actual: entry.hash,
      };
    }
    prevHash = entry.hash;
  }
  return VALID;
}
