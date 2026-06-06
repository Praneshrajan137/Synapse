import {
  ThresholdCountdown,
  countdownUrgency,
  formatClock,
} from "@ds/compounds/ThresholdCountdown";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("formatClock", () => {
  it("formats m:ss and clamps at zero", () => {
    expect(formatClock(300_000)).toBe("5:00");
    expect(formatClock(65_000)).toBe("1:05");
    expect(formatClock(9_000)).toBe("0:09");
    expect(formatClock(0)).toBe("0:00");
    expect(formatClock(-5_000)).toBe("0:00");
  });
});

describe("countdownUrgency", () => {
  it("bands by fraction remaining", () => {
    expect(countdownUrgency(1)).toBe("calm");
    expect(countdownUrgency(0.6)).toBe("calm");
    expect(countdownUrgency(0.49)).toBe("warn");
    expect(countdownUrgency(0.2)).toBe("warn");
    expect(countdownUrgency(0.19)).toBe("danger");
    expect(countdownUrgency(0)).toBe("danger");
  });
});

describe("ThresholdCountdown", () => {
  it("shows the remaining time and the honest fallback default", () => {
    // Controlled clock: started 60s ago, 300s window → 4:00 left.
    const started = 1_000_000;
    render(<ThresholdCountdown startedAtMs={started} now={started + 60_000} />);
    expect(screen.getByText("4:00")).toBeInTheDocument();
    expect(screen.getByText(/defers — no action is taken/)).toBeInTheDocument();
  });

  it("names a non-default fallback policy", () => {
    const started = 1_000_000;
    render(
      <ThresholdCountdown
        startedAtMs={started}
        now={started + 10_000}
        fallback="execute_last_known_good"
      />,
    );
    expect(screen.getByText(/last known-good action/)).toBeInTheDocument();
  });

  it("renders an elapsed state past the window (role=timer label)", () => {
    const started = 1_000_000;
    render(<ThresholdCountdown startedAtMs={started} now={started + 400_000} />);
    const timer = screen.getByRole("timer");
    expect(timer.getAttribute("aria-label")).toMatch(/window elapsed/);
    expect(screen.getByText("window elapsed")).toBeInTheDocument();
  });

  it("puts the remaining time + fallback into the accessible label (colour not sole channel)", () => {
    const started = 1_000_000;
    render(<ThresholdCountdown startedAtMs={started} now={started + 240_000} />);
    const timer = screen.getByRole("timer");
    expect(timer.getAttribute("aria-label")).toMatch(/1:00 left to decide/);
  });
});
