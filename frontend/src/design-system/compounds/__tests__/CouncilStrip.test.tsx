import {
  type CouncilAgentState,
  CouncilStrip,
  councilDotFor,
  mapAgentHealth,
} from "@ds/compounds/CouncilStrip";
import { AGENT_COLOR_VAR, AGENT_NAMES, type AgentName } from "@lib/agent-identity";
import { type AgentProcessState, type GlyphInk, glyphContrast, glyphInk } from "@lib/chromatics";
import { useThemeStore } from "@state/theme.store";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

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

describe("CouncilStrip — live cognition (ADR-051)", () => {
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

describe("CouncilStrip — every monogram is legible on its own fill (finding 131)", () => {
  afterEach(() => {
    useThemeStore.setState({ theme: "dark" });
  });

  interface RenderedFill {
    readonly name: string;
    readonly state: CouncilAgentState;
    readonly live: AgentProcessState | null;
    /** The Pricing Oracle's ink in the high-contrast theme. */
    readonly hcPricingInk: GlyphInk;
  }

  const HEALTHY: CouncilAgentState = { status: "healthy" };

  // Every fill a cell can render: a live process state (ADR-051 overrides
  // health), or a health state on its own.
  const RENDERED: readonly RenderedFill[] = [
    { name: "live interrupted", state: HEALTHY, live: "interrupted", hcPricingInk: "ink-inverse" },
    { name: "live waiting", state: HEALTHY, live: "waiting", hcPricingInk: "ink" },
    { name: "live thinking", state: HEALTHY, live: "thinking", hcPricingInk: "ink" },
    { name: "live debating", state: HEALTHY, live: "debating", hcPricingInk: "ink" },
    { name: "live acting", state: HEALTHY, live: "acting", hcPricingInk: "ink" },
    { name: "live escalated", state: HEALTHY, live: "escalated", hcPricingInk: "ink" },
    { name: "healthy, idle", state: HEALTHY, live: null, hcPricingInk: "ink" },
    {
      name: "healthy, in a live decision",
      state: { status: "healthy", active: true },
      live: null,
      hcPricingInk: "ink",
    },
    { name: "degraded", state: { status: "degraded" }, live: null, hcPricingInk: "ink" },
    {
      name: "unreachable",
      state: { status: "unreachable" },
      live: null,
      hcPricingInk: "ink-inverse",
    },
    { name: "unknown", state: { status: "unknown" }, live: null, hcPricingInk: "ink-inverse" },
  ];

  // Storybook a11y job 124962437723 failed the dark ink only on the Pricing
  // Oracle's fills (3.65 to 3.97:1). ADR-048 D4 made it the one dark agent token
  // darker than the neutral mix, so it alone takes the light ink.
  const DARK_INK: Readonly<Record<AgentName, GlyphInk>> = {
    demand_prophet: "ink-inverse",
    routing_navigator: "ink-inverse",
    inventory_sentinel: "ink-inverse",
    freshness_guardian: "ink-inverse",
    pricing_oracle: "ink",
    disruption_shield: "ink-inverse",
    supplier_trust: "ink-inverse",
    sustainability_agent: "ink-inverse",
  };

  it("draws only the Pricing Oracle in light ink in the dark theme, every monogram above 4.5:1", () => {
    for (const agent of AGENT_NAMES) {
      for (const { name, state, live } of RENDERED) {
        const { share } = councilDotFor(state, AGENT_COLOR_VAR[agent], live);
        const ink = glyphInk(agent, share, "dark");
        expect(ink, `${agent}, ${name}`).toBe(DARK_INK[agent]);
        expect(glyphContrast(agent, share, "dark", ink), `${agent}, ${name}`).toBeGreaterThan(4.5);
      }
    }
  });

  it("keeps every monogram above 4.5:1 in the high-contrast theme, the Pricing Oracle in light ink from its waiting fill up", () => {
    for (const agent of AGENT_NAMES) {
      for (const { name, state, live, hcPricingInk } of RENDERED) {
        const { share } = councilDotFor(state, AGENT_COLOR_VAR[agent], live);
        const ink = glyphInk(agent, share, "hc");
        expect(ink, `${agent}, ${name}`).toBe(
          agent === "pricing_oracle" ? hcPricingInk : "ink-inverse",
        );
        expect(glyphContrast(agent, share, "hc", ink), `${agent}, ${name}`).toBeGreaterThan(4.5);
      }
    }
  });

  it("paints each monogram in the ink token the rule picks for the active theme, with no blend mode", () => {
    useThemeStore.setState({ theme: "dark" });
    const resting = Object.fromEntries(AGENT_NAMES.map((a) => [a, { status: "healthy" as const }]));
    const dark = render(<CouncilStrip states={resting} />);
    expect(screen.getByText("PO")).toHaveClass("text-ink");
    expect(screen.getByText("PO")).not.toHaveClass("text-ink-inverse");
    expect(screen.getByText("DP")).toHaveClass("text-ink-inverse");
    expect(dark.container.querySelector(".mix-blend-luminosity")).toBeNull();
    dark.unmount();

    useThemeStore.setState({ theme: "hc" });
    render(<CouncilStrip states={{ pricing_oracle: { status: "unreachable" } }} />);
    expect(screen.getByText("PO")).toHaveClass("text-ink-inverse");
  });
});
