import { CouncilStrip, mapAgentHealth } from "@ds/compounds/CouncilStrip";
import { AGENT_NAMES } from "@lib/agent-identity";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

describe("mapAgentHealth — maps GET /api/v1/agents status strings", () => {
  it("maps the documented status forms", () => {
    expect(mapAgentHealth("healthy")).toBe("healthy");
    expect(mapAgentHealth("http_503")).toBe("degraded");
    expect(mapAgentHealth("unreachable: ConnectError")).toBe("unreachable");
    expect(mapAgentHealth("weird")).toBe("unknown");
    expect(mapAgentHealth(undefined)).toBe("unknown");
    expect(mapAgentHealth(null)).toBe("unknown");
  });
});

describe("CouncilStrip", () => {
  it("renders all eight frozen agents in order", () => {
    render(<CouncilStrip />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(AGENT_NAMES.length);
  });

  it("defaults missing agents to an honest 'unknown' status (P7 — no fake green)", () => {
    render(<CouncilStrip />);
    // Every cell carries a status word; with no data all are unknown ("—").
    const dashes = screen.getAllByText("—");
    expect(dashes).toHaveLength(AGENT_NAMES.length);
  });

  it("renders degraded and offline states as words, not colour alone (INV-CLR-011)", () => {
    render(
      <CouncilStrip
        states={{
          demand_prophet: { status: "healthy", active: true },
          pricing_oracle: { status: "degraded" },
          routing_navigator: { status: "unreachable" },
        }}
      />,
    );
    expect(screen.getByText("live")).toBeInTheDocument();
    expect(screen.getByText("degraded")).toBeInTheDocument();
    expect(screen.getByText("offline")).toBeInTheDocument();
  });

  it("puts health + activity + p99 + calibration into the accessible label", () => {
    render(
      <CouncilStrip
        states={{
          demand_prophet: {
            status: "healthy",
            active: true,
            latencyP99Ms: 84,
            calibration90: 0.91,
          },
        }}
      />,
    );
    const cell = screen.getByLabelText(
      /Demand Prophet: live, active in a live decision, p99 84ms, calibration 91 percent/,
    );
    expect(cell).toBeInTheDocument();
  });

  it("is display-only when onSelectAgent is omitted (no buttons)", () => {
    render(<CouncilStrip states={{ demand_prophet: { status: "healthy" } }} />);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("fires onSelectAgent with the agent name when interactive", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <CouncilStrip states={{ pricing_oracle: { status: "healthy" } }} onSelectAgent={onSelect} />,
    );
    await user.click(screen.getByRole("button", { name: /Pricing Oracle/ }));
    expect(onSelect).toHaveBeenCalledWith("pricing_oracle");
  });

  it("marks the selected agent via aria-pressed", () => {
    render(
      <CouncilStrip
        states={{ freshness_guardian: { status: "healthy" } }}
        selectedAgent="freshness_guardian"
        onSelectAgent={() => undefined}
      />,
    );
    const cell = screen.getByRole("button", { name: /Freshness Guardian/ });
    expect(cell.getAttribute("aria-pressed")).toBe("true");
  });
});

describe("CouncilStrip — live cognition (ADR-048)", () => {
  it("renders the live process word, overriding health (INV-CLR-011 text parity)", () => {
    render(
      <CouncilStrip
        states={{ demand_prophet: { status: "healthy" } }}
        liveStates={{ demand_prophet: "thinking" }}
      />,
    );
    expect(screen.getByText("thinking")).toBeInTheDocument();
  });

  it("exposes the live process state as the data-process-state grammar hook", () => {
    render(
      <CouncilStrip
        states={{ pricing_oracle: { status: "healthy" } }}
        liveStates={{ pricing_oracle: "debating" }}
      />,
    );
    const cell = screen.getByLabelText(/Pricing Oracle/);
    expect(cell.getAttribute("data-process-state")).toBe("debating");
    expect(cell).toHaveTextContent(/debating/);
  });
});
