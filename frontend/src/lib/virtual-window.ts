/**
 * Pure virtualization windowing math — design "H. surfaces — virtualization
 * retrofit of AuditVault / DecisionTheater" (Req 9.1, 9.4).
 *
 * The AuditVault and DecisionTheater surfaces render their dense tables through
 * `@tanstack/react-virtual` (the runtime DOM engine). This module is the pure,
 * property-testable formalization of the guarantee that engine must uphold:
 * for ANY total row count the count of mounted row nodes stays bounded and far
 * below the total, and window index `i` always maps to the datum at index `i`
 * so a scrolled-in row aligns to its seeded fixture — virtualization never
 * misaligns row content (Req 9.4) and never caps the reachable set (Req 9.3).
 *
 * The surfaces import {@link ROW_OVERSCAN} from here so the runtime virtualizer
 * and this model share a single overscan constant; Property 10 (task 10.2)
 * tests {@link computeWindow} directly.
 */

/** Rows rendered above and below the viewport so a scroll never flashes blank. */
export const ROW_OVERSCAN = 10;

export interface WindowInput {
  /** Total number of rows in the dataset (may be 10k+). */
  readonly totalRows: number;
  /** Height of a single row in CSS pixels. */
  readonly rowHeightPx: number;
  /** Height of the scroll viewport in CSS pixels. */
  readonly viewportPx: number;
  /** Current scroll offset from the top in CSS pixels. */
  readonly scrollTopPx: number;
  /** Extra rows rendered on each side of the viewport. */
  readonly overscan: number;
}

export interface VirtualWindow {
  /** First mounted row index (inclusive), always in `[0, max(0, totalRows-1)]`. */
  readonly startIndex: number;
  /** Last mounted row index (inclusive); `-1` when the dataset is empty. */
  readonly endIndex: number;
  /**
   * Number of mounted row nodes = `endIndex - startIndex + 1` (0 when empty).
   * Bounded by `ceil(viewportPx / rowHeightPx) + 2·overscan` independent of
   * `totalRows` (Req 9.1).
   */
  readonly mountedCount: number;
}

/** Coerces a value to a finite, non-negative integer (defensive; NaN → 0). */
function nonNegInt(x: number): number {
  if (!Number.isFinite(x) || x <= 0) return 0;
  return Math.floor(x);
}

/**
 * Computes the mounted window for a virtualized list.
 *
 * For any `totalRows`, `mountedCount ≤ ceil(viewportPx / rowHeightPx) +
 * 2·overscan` — a bound that does NOT grow with `totalRows` (Req 9.1) — and the
 * returned indices map one-to-one to data indices, so the row rendered at a
 * window slot always carries the datum at that same index (Req 9.4).
 *
 * Empty dataset → `{ startIndex: 0, endIndex: -1, mountedCount: 0 }`.
 */
export function computeWindow(input: WindowInput): VirtualWindow {
  const totalRows = nonNegInt(input.totalRows);
  if (totalRows === 0) {
    return { startIndex: 0, endIndex: -1, mountedCount: 0 };
  }

  // A row must occupy at least one pixel so the window is well defined even if
  // a caller passes a zero/negative height.
  const rowHeightPx =
    Number.isFinite(input.rowHeightPx) && input.rowHeightPx >= 1 ? input.rowHeightPx : 1;
  const viewportPx =
    Number.isFinite(input.viewportPx) && input.viewportPx > 0 ? input.viewportPx : 0;
  const overscan = nonNegInt(input.overscan);
  const scrollTopPx =
    Number.isFinite(input.scrollTopPx) && input.scrollTopPx > 0 ? input.scrollTopPx : 0;

  const visibleCount = Math.ceil(viewportPx / rowHeightPx);
  const firstVisible = Math.floor(scrollTopPx / rowHeightPx);

  const lastIndex = totalRows - 1;
  const startIndex = Math.max(0, Math.min(firstVisible - overscan, lastIndex));
  const endIndex = Math.min(lastIndex, firstVisible + visibleCount - 1 + overscan);

  // endIndex can only fall below startIndex when the scroll offset is past the
  // end of the content; clamp startIndex so the window stays coherent.
  const safeStart = Math.min(startIndex, endIndex);
  const mountedCount = endIndex - safeStart + 1;

  return { startIndex: safeStart, endIndex, mountedCount };
}
