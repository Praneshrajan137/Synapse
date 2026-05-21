import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import fc from "fast-check";
import { ParetoFrontier, type ParetoPoint } from "@ds/compounds/ParetoFrontier";

// FE-INV-028 (P3) precursor: ParetoFrontier never highlights a dominated
// point as "selected" — the selection prop is operator-controlled, but
// dominated detection must be referentially transparent.

describe("ParetoFrontier dominated-set property", () => {
  it("marks dominated points as 'dominated' in their aria label", () => {
    const points: ParetoPoint[] = [
      { id: "a", x: 0.9, y: 0.9, label: "agent_a" },
      { id: "b", x: 0.5, y: 0.5, label: "agent_b" }, // dominated by a
      { id: "c", x: 0.95, y: 0.4, label: "agent_c" },
    ];
    render(<ParetoFrontier points={points} />);
    expect(screen.getByLabelText(/agent_b .* dominated/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/agent_a .* dominated/)).toBeNull();
    expect(screen.queryByLabelText(/agent_c .* dominated/)).toBeNull();
  });

  it("dominance is referentially transparent (property test)", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            id: fc.string({ minLength: 1, maxLength: 8 }).filter((s) => /^[a-z0-9_-]+$/i.test(s)),
            x: fc.float({ min: 0, max: 1, noNaN: true }),
            y: fc.float({ min: 0, max: 1, noNaN: true }),
          }),
          { minLength: 1, maxLength: 6 },
        ),
        (raw) => {
          // Dedupe ids
          const seen = new Set<string>();
          const points: ParetoPoint[] = [];
          for (const p of raw) {
            if (seen.has(p.id)) continue;
            seen.add(p.id);
            points.push(p);
          }
          const { unmount: u1, getByLabelText } = render(<ParetoFrontier points={points} />);
          const dominatedFirst = new Set<string>();
          for (const p of points) {
            try {
              if (getByLabelText(new RegExp(`${escapeRegExp(p.id)}.*dominated`))) {
                dominatedFirst.add(p.id);
              }
            } catch {
              /* not dominated */
            }
          }
          u1();
          const { unmount: u2, getByLabelText: g2 } = render(<ParetoFrontier points={points} />);
          const dominatedSecond = new Set<string>();
          for (const p of points) {
            try {
              if (g2(new RegExp(`${escapeRegExp(p.id)}.*dominated`))) {
                dominatedSecond.add(p.id);
              }
            } catch {
              /* not dominated */
            }
          }
          u2();
          return setsEqual(dominatedFirst, dominatedSecond);
        },
      ),
      { numRuns: 25 },
    );
  });
});

function setsEqual<T>(a: Set<T>, b: Set<T>): boolean {
  if (a.size !== b.size) return false;
  for (const v of a) if (!b.has(v)) return false;
  return true;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
