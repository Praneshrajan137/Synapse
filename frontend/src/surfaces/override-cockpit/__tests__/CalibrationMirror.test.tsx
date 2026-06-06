import type { EscalationMessage } from "@domain/escalation";
import type { EscalationEntry } from "@state/escalation.store";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CalibrationMirror, summarizeCalibration } from "../CalibrationMirror";

let seq = 0;
function entry(
  confidence: number,
  status: EscalationEntry["status"],
  action?: EscalationEntry["acted_action"],
): EscalationEntry {
  seq += 1;
  const message = {
    type: "escalation",
    decision_id: `00000000-0000-0000-0000-${String(seq).padStart(12, "0")}`,
    confidence,
    proposals: [],
    violations: [],
  } as unknown as EscalationMessage;
  return {
    id: message.decision_id,
    received_at: seq,
    message,
    status,
    ...(action ? { acted_action: action } : {}),
  };
}

describe("summarizeCalibration", () => {
  it("reports insufficient until enough escalations are acted", () => {
    const s = summarizeCalibration([entry(0.5, "acted", "approved")]);
    expect(s.signal).toBe("insufficient");
  });

  it("flags overtrust when low-confidence escalations are approved", () => {
    const entries = [
      entry(0.5, "acted", "approved"),
      entry(0.55, "acted", "approved"),
      entry(0.6, "acted", "approved"),
    ];
    const s = summarizeCalibration(entries);
    expect(s.signal).toBe("overtrust");
    expect(s.approvedCount).toBe(3);
    expect(s.avgConfidenceApproved).toBeCloseTo(0.55, 5);
  });

  it("flags undertrust when high-confidence decisions are overridden", () => {
    const entries = [
      entry(0.85, "acted", "rejected"),
      entry(0.9, "acted", "modified"),
      entry(0.88, "acted", "rejected"),
    ];
    const s = summarizeCalibration(entries);
    expect(s.signal).toBe("undertrust");
    expect(s.overriddenCount).toBe(3);
  });

  it("reports calibrated for a healthy mix", () => {
    const entries = [
      entry(0.95, "acted", "approved"),
      entry(0.92, "acted", "approved"),
      entry(0.6, "acted", "rejected"),
    ];
    expect(summarizeCalibration(entries).signal).toBe("calibrated");
  });

  it("ignores pending (not-yet-acted) escalations", () => {
    const s = summarizeCalibration([entry(0.5, "pending")]);
    expect(s.approvedCount).toBe(0);
    expect(s.signal).toBe("insufficient");
  });
});

describe("CalibrationMirror", () => {
  it("renders the session read with counts (honest, no fabricated outcome)", () => {
    const entries = [
      entry(0.5, "acted", "approved"),
      entry(0.55, "acted", "approved"),
      entry(0.6, "acted", "approved"),
    ];
    render(<CalibrationMirror entries={entries} />);
    expect(screen.getByText(/Overtrust watch/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Trust calibration mirror/)).toBeInTheDocument();
  });
});
