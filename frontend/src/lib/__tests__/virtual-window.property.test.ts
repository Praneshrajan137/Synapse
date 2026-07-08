// Property-based tests for the pure virtualization windowing math in
// `@lib/virtual-window` (design "H. surfaces — virtualization retrofit of
// AuditVault / DecisionTheater", Req 9.1, 9.4). `computeWindow` is the pure,
// property-testable formalization of the guarantee the `@tanstack/react-virtual`
// runtime engine must uphold: for ANY total row count the count of mounted row
// nodes stays bounded and far below the total, and window index `i` always maps
// to the datum at index `i` so a scrolled-in row aligns to its seeded fixture.
//
// fast-check + Vitest, numRuns >= 100 per property.

import fc from "fast-check";
import { describe, expect, it } from "vitest";
import { ROW_OVERSCAN, type WindowInput, computeWindow } from "../virtual-window";

// A well-formed input: every field is a finite, in-range value so the internal
// coercion in `computeWindow` is the identity and the analytic bound
// `ceil(viewportPx / rowHeightPx) + 2·overscan` applies directly. Row counts
// deliberately span from empty through 10k+ so `totalRows`-independence is
// exercised against real scale (Req 9.1).
// A rendered scroll viewport always has positive height: a virtualized table is
// only mounted inside a laid-out container. `viewportPx: 0` is a degenerate,
// out-of-domain input where the "bounded count" property (mountedCount ≤ 0 when
// overscan is also 0) and the "coherent non-empty window" property
// (mountedCount ≥ 1 for a non-empty dataset) are mutually unsatisfiable, so it
// is excluded to keep the property well-posed and the gate deterministic (Req 20.3).
const wellFormedInputArb: fc.Arbitrary<WindowInput> = fc.record({
  totalRows: fc.integer({ min: 0, max: 100_000 }),
  rowHeightPx: fc.integer({ min: 1, max: 200 }),
  viewportPx: fc.integer({ min: 1, max: 5_000 }),
  scrollTopPx: fc.integer({ min: 0, max: 20_000_000 }),
  overscan: fc.integer({ min: 0, max: 50 }),
});

/** The analytic mounted-row bound for a well-formed input. */
function mountedBound(input: WindowInput): number {
  return Math.ceil(input.viewportPx / input.rowHeightPx) + 2 * input.overscan;
}

// ─────────────────────────────────────────────────────────────────────────
// Feature: atlas-console-effectiveness, Property 10: The virtualization window
// yields a bounded mounted-row count independent of total rows, and each
// windowed row maps to the datum at its index
//
// Validates: Requirements 9.1, 9.4
// ─────────────────────────────────────────────────────────────────────────
describe("computeWindow — Property 10: bounded mounted count + index-faithful window", () => {
  it("mounts no more rows than ceil(viewportPx/rowHeightPx) + 2·overscan for any totalRows", () => {
    fc.assert(
      fc.property(wellFormedInputArb, (input) => {
        const { mountedCount } = computeWindow(input);
        expect(mountedCount).toBeLessThanOrEqual(mountedBound(input));
      }),
      { numRuns: 100 },
    );
  });

  it("keeps the mounted count independent of totalRows — the SAME bound holds at 10 rows and at 10k+ rows", () => {
    fc.assert(
      fc.property(
        // A shared viewport/row/scroll/overscan config, plus two wildly
        // different row totals. The bound must not grow with the row count.
        fc.record({
          rowHeightPx: fc.integer({ min: 1, max: 200 }),
          viewportPx: fc.integer({ min: 1, max: 5_000 }),
          scrollTopPx: fc.integer({ min: 0, max: 20_000_000 }),
          overscan: fc.integer({ min: 0, max: 50 }),
          small: fc.integer({ min: 1, max: 500 }),
          huge: fc.integer({ min: 10_000, max: 1_000_000 }),
        }),
        ({ small, huge, ...cfg }) => {
          const bound = Math.ceil(cfg.viewportPx / cfg.rowHeightPx) + 2 * cfg.overscan;
          const smallWin = computeWindow({ ...cfg, totalRows: small });
          const hugeWin = computeWindow({ ...cfg, totalRows: huge });
          expect(smallWin.mountedCount).toBeLessThanOrEqual(bound);
          expect(hugeWin.mountedCount).toBeLessThanOrEqual(bound);
          // A 100x-larger dataset never mounts more nodes than the bound: the
          // mounted count does not scale with totalRows.
          expect(hugeWin.mountedCount).toBeLessThanOrEqual(bound);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("keeps every windowed index within [0, totalRows-1] and maps slot k to datum startIndex+k", () => {
    fc.assert(
      fc.property(wellFormedInputArb, (input) => {
        const { startIndex, endIndex, mountedCount } = computeWindow(input);
        const total = input.totalRows;
        if (total === 0) {
          // Empty dataset → nothing mounted.
          expect(startIndex).toBe(0);
          expect(endIndex).toBe(-1);
          expect(mountedCount).toBe(0);
          return;
        }
        // Both bounds address real data rows.
        expect(startIndex).toBeGreaterThanOrEqual(0);
        expect(startIndex).toBeLessThanOrEqual(total - 1);
        expect(endIndex).toBeGreaterThanOrEqual(0);
        expect(endIndex).toBeLessThanOrEqual(total - 1);
        // The window is a coherent contiguous range.
        expect(startIndex).toBeLessThanOrEqual(endIndex);
        // mountedCount is exactly the number of contiguous indices in the
        // window: slot k (0-based) renders the datum at index startIndex + k,
        // and the final slot addresses endIndex — so virtualization never
        // misaligns a row's content with its datum (Req 9.4).
        expect(mountedCount).toBe(endIndex - startIndex + 1);
        expect(startIndex + (mountedCount - 1)).toBe(endIndex);
      }),
      { numRuns: 100 },
    );
  });

  it("uses the exported ROW_OVERSCAN constant as a shared, non-negative integer", () => {
    // The surfaces import ROW_OVERSCAN so the runtime virtualizer and this
    // model share one overscan; sanity-check it is a usable value and that
    // computeWindow honours it as the bound term.
    expect(Number.isInteger(ROW_OVERSCAN)).toBe(true);
    expect(ROW_OVERSCAN).toBeGreaterThanOrEqual(0);
    fc.assert(
      fc.property(
        fc.record({
          totalRows: fc.integer({ min: 1, max: 100_000 }),
          rowHeightPx: fc.integer({ min: 1, max: 200 }),
          viewportPx: fc.integer({ min: 1, max: 5_000 }),
          scrollTopPx: fc.integer({ min: 0, max: 20_000_000 }),
        }),
        (base) => {
          const input: WindowInput = { ...base, overscan: ROW_OVERSCAN };
          const { mountedCount } = computeWindow(input);
          expect(mountedCount).toBeLessThanOrEqual(mountedBound(input));
        },
      ),
      { numRuns: 100 },
    );
  });
});
