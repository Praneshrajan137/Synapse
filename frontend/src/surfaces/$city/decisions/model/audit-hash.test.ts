/**
 * SYNAPSE Atlas Console — audit chain property tests.
 *
 * Pin three load-bearing invariants:
 *   1. A correctly-built chain verifies.
 *   2. Tampering with any body breaks the chain at that index.
 *   3. Tampering with any prev link breaks the chain at that index.
 *
 * Uses the same hash primitives as the runtime so the test really
 * exercises end-to-end behaviour (including the `node:crypto` fallback).
 */
import { describe, expect, it } from "vitest";
import fc from "fast-check";

import { canonicalize } from "@shared/canonical-json";
import { chainHash } from "@shared/hash/sha256";

import type { AuditEntry } from "./audit-hash";
import { verifyChain } from "./audit-hash";

async function buildChain(bodies: readonly unknown[]): Promise<AuditEntry[]> {
  const entries: AuditEntry[] = [];
  let prev: string | null = null;
  for (const body of bodies) {
    const hash = await chainHash(prev, canonicalize(body));
    entries.push({ hash, prev, body });
    prev = hash;
  }
  return entries;
}

describe("audit-hash chain", () => {
  it("an empty chain is valid", async () => {
    expect(await verifyChain([])).toEqual({
      valid: true,
      brokenAt: -1,
      expected: null,
      actual: null,
    });
  });

  it("prop: a correctly-built chain verifies", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(fc.jsonValue({ depthSize: "small" }), { minLength: 1, maxLength: 12 }),
        async (bodies) => {
          const chain = await buildChain(bodies);
          const result = await verifyChain(chain);
          expect(result.valid).toBe(true);
          expect(result.brokenAt).toBe(-1);
        },
      ),
      { seed: 20260430, numRuns: 30 },
    );
  });

  it("prop: tampering a body breaks the chain at that index", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(fc.jsonValue({ depthSize: "small" }), { minLength: 2, maxLength: 8 }),
        fc.integer({ min: 0, max: 7 }),
        async (bodies, rawIndex) => {
          const idx = rawIndex % bodies.length;
          const chain = await buildChain(bodies);
          const tampered: AuditEntry[] = chain.map((e, i) =>
            i === idx ? { ...e, body: { tampered: true, original: e.body } } : e,
          );
          const result = await verifyChain(tampered);
          expect(result.valid).toBe(false);
          expect(result.brokenAt).toBe(idx);
        },
      ),
      { seed: 20260430, numRuns: 30 },
    );
  });

  it("prop: tampering a prev link breaks the chain at that index", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(fc.jsonValue({ depthSize: "small" }), { minLength: 2, maxLength: 8 }),
        async (bodies) => {
          const chain = await buildChain(bodies);
          const tampered: AuditEntry[] = chain.map((e, i) =>
            i === 1 ? { ...e, prev: "0".repeat(64) } : e,
          );
          const result = await verifyChain(tampered);
          expect(result.valid).toBe(false);
          expect(result.brokenAt).toBe(1);
        },
      ),
      { seed: 20260430, numRuns: 20 },
    );
  });
});
