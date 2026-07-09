import {
  UniversalStateRow,
  UniversalStateView,
  universalStateCopy,
} from "@ds/compounds/UniversalStateView";
import type { UniversalState } from "@lib/universal-state";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const NON_POPULATED: ReadonlyArray<Exclude<UniversalState, "populated">> = [
  "loading",
  "empty",
  "error",
  "degraded",
  "offline",
];

describe("universalStateCopy", () => {
  it("gives every non-populated state a distinct title + glyph", () => {
    const titles = new Set<string>();
    const glyphs = new Set<string>();
    for (const s of NON_POPULATED) {
      const c = universalStateCopy(s);
      titles.add(c.title);
      glyphs.add(c.glyph);
    }
    expect(titles.size).toBe(NON_POPULATED.length);
    expect(glyphs.size).toBe(NON_POPULATED.length);
  });

  it("distinguishes 'no data yet' (empty) from 'failed to load' (error) — Req 10.8", () => {
    const empty = universalStateCopy("empty");
    const error = universalStateCopy("error");
    expect(empty.title).not.toBe(error.title);
    expect(empty.detail).not.toBe(error.detail);
    // error is announced assertively; empty is a passive status.
    expect(error.role).toBe("alert");
    expect(empty.role).toBe("status");
  });

  it("announces offline assertively and never as a healthy/empty state — Req 10.7", () => {
    const offline = universalStateCopy("offline");
    expect(offline.role).toBe("alert");
    expect(offline.title).not.toBe(universalStateCopy("empty").title);
  });

  it("honours label overrides while keeping defaults for the rest", () => {
    const c = universalStateCopy("empty", { emptyTitle: "No decisions yet" });
    expect(c.title).toBe("No decisions yet");
    expect(c.detail).toBe(universalStateCopy("empty").detail);
  });
});

describe("UniversalStateView", () => {
  it("renders children only when populated", () => {
    render(
      <UniversalStateView state="populated">
        <p>the data</p>
      </UniversalStateView>,
    );
    expect(screen.getByText("the data")).toBeInTheDocument();
  });

  it("swaps children for a distinct block on each non-populated state", () => {
    for (const s of NON_POPULATED) {
      const { unmount, container } = render(
        <UniversalStateView state={s}>
          <p>the data</p>
        </UniversalStateView>,
      );
      expect(screen.queryByText("the data")).not.toBeInTheDocument();
      expect(container.querySelector(`[data-universal-state="${s}"]`)).not.toBeNull();
      unmount();
    }
  });

  it("shows a retry affordance for error/offline/degraded but not for empty/loading", () => {
    const onRetry = vi.fn();
    for (const s of ["error", "offline", "degraded"] as const) {
      const { unmount } = render(
        <UniversalStateView state={s} onRetry={onRetry}>
          <p>x</p>
        </UniversalStateView>,
      );
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
      unmount();
    }
    for (const s of ["empty", "loading"] as const) {
      const { unmount } = render(
        <UniversalStateView state={s} onRetry={onRetry}>
          <p>x</p>
        </UniversalStateView>,
      );
      expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
      unmount();
    }
  });
});

describe("UniversalStateRow", () => {
  it("renders a spanning row carrying the state's copy for table surfaces", () => {
    render(
      <table>
        <tbody>
          <UniversalStateRow state="error" colSpan={7} />
        </tbody>
      </table>,
    );
    const cell = screen.getByRole("alert");
    expect(cell.tagName).toBe("TD");
    expect(cell).toHaveAttribute("colspan", "7");
    expect(cell).toHaveAttribute("data-universal-state", "error");
    expect(cell).toHaveTextContent(universalStateCopy("error").title);
  });
});
