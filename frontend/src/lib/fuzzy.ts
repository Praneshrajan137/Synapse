// Tiny fuzzy subsequence matcher for the command palette. No dependency.
//
// Returns a score (higher = better) when every character of `query` appears in
// `text` in order, or null when it does not match. Contiguous runs and early
// matches score higher, so "mc" ranks "Mission Control" above "Demand
// Forecast". Case-insensitive; empty query matches everything with score 0.

export function fuzzyScore(query: string, text: string): number | null {
  const q = query.toLowerCase().trim();
  if (q.length === 0) return 0;
  const t = text.toLowerCase();

  let qi = 0;
  let score = 0;
  let lastMatch = -2;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      score += ti === lastMatch + 1 ? 3 : 1; // contiguous run bonus
      if (ti < 4) score += 1; // prefix bonus
      lastMatch = ti;
      qi += 1;
    }
  }
  return qi === q.length ? score : null;
}

export interface Scored<T> {
  readonly item: T;
  readonly score: number;
}

/**
 * Filter + rank `items` against `query` using `fuzzyScore` over each item's
 * `text(item)`. Stable for equal scores (preserves input order). Empty query
 * returns all items in their original order.
 */
export function fuzzyFilter<T>(
  items: ReadonlyArray<T>,
  query: string,
  text: (item: T) => string,
): T[] {
  const scored: Array<Scored<T> & { idx: number }> = [];
  items.forEach((item, idx) => {
    const score = fuzzyScore(query, text(item));
    if (score !== null) scored.push({ item, score, idx });
  });
  scored.sort((a, b) => b.score - a.score || a.idx - b.idx);
  return scored.map((s) => s.item);
}
