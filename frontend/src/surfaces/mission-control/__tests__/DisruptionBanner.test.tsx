import type { DisruptionAlert } from "@domain/disruption-alert";
import { useFirehoseStore } from "@state/firehose.store";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { DisruptionBanner } from "../DisruptionBanner";

function alert(overrides: Partial<DisruptionAlert> = {}): DisruptionAlert {
  return {
    alert_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    alert_level: 7,
    anomaly_scores: {
      isolation_forest: 0.82,
      lstm_autoencoder: 0.74,
      gnn_structural: 0.91,
      ensemble_weighted: 0.83,
    },
    affected_nodes: ["store-blr-004", "warehouse-blr-0"],
    disruption_type: "cold-chain breach",
    playbook_id: "PB-COLD-014",
    playbook_actions: "Reroute to backup cold store; markdown at-risk SKUs",
    reasoning_chain: "Temperature sensor drift exceeded threshold across 2 nodes.",
    monte_carlo_impact: {
      scenarios_run: 1000,
      expected_kpi_degradation_pct: 4.2,
      p95_degradation_pct: 11.8,
    },
    timestamp: "2026-06-14T10:03:00+00:00",
    confidence: 0.83,
    ...overrides,
  } as DisruptionAlert;
}

describe("DisruptionBanner", () => {
  beforeEach(() => {
    useFirehoseStore.getState().flushAll();
  });

  it("renders nothing when there is no disruption", () => {
    const { container } = render(<DisruptionBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the one-line summary collapsed and the full anatomy when expanded", async () => {
    useFirehoseStore.getState().appendDisruption(alert(), 1);
    render(<DisruptionBanner />);

    // Collapsed: type + level visible, ensemble detail hidden.
    expect(screen.getByText("cold-chain breach")).toBeInTheDocument();
    expect(screen.getByText(/Level 7\/10/)).toBeInTheDocument();
    expect(screen.queryByText(/Anomaly ensemble/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { expanded: false }));

    // Expanded: the previously-hidden Disruption Shield anatomy.
    expect(screen.getByText(/Anomaly ensemble/)).toBeInTheDocument();
    expect(screen.getByText("0.910")).toBeInTheDocument(); // gnn_structural
    expect(screen.getByText("PB-COLD-014")).toBeInTheDocument();
    expect(screen.getByText(/11.8%/)).toBeInTheDocument(); // p95 monte-carlo
    expect(screen.getByText("store-blr-004")).toBeInTheDocument();
  });
});
