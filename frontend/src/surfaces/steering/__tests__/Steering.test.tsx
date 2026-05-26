import {
  DEFAULT_PARETO_WEIGHTS,
  DEFAULT_TIER_THRESHOLDS,
  useSteeringStore,
} from "@state/steering.store";
import { Steering } from "@surfaces/steering/Steering";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

// i18next is a global; load with the same bootstrap the app uses so the
// "steering" namespace is registered. (i18n/index.ts side-effect-inits
// i18next when imported.)
import "@i18n/index";

describe("Steering surface", () => {
  beforeEach(() => {
    // Reset the persisted state between tests — important because the
    // store uses zustand/persist (localStorage), and one test mutating
    // the store would leak into the next.
    useSteeringStore.setState({
      paretoWeights: DEFAULT_PARETO_WEIGHTS,
      tierThresholds: DEFAULT_TIER_THRESHOLDS,
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("renders the four Pareto weight sliders + three tier-threshold sliders", () => {
    render(<Steering />);
    // weights — by accessible name (label text)
    expect(screen.getByRole("slider", { name: /Cost/i })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: /Time/i })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: /Sustainability/i })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: /Fairness/i })).toBeInTheDocument();
    // tier thresholds
    expect(screen.getByRole("slider", { name: /Tier 2/i })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: /Tier 3/i })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: /Tier 4/i })).toBeInTheDocument();
  });

  it("renders the constellation preview with 8 agent buttons", () => {
    render(<Steering />);
    // The preview includes the ProposalConstellation, which renders 8
    // role=button nodes (one per FROZEN agent).
    expect(screen.getAllByRole("button").length).toBeGreaterThanOrEqual(8);
  });

  it("updates the Pareto weight when its slider changes (FE-INV-033)", () => {
    render(<Steering />);
    const cost = screen.getByRole("slider", { name: /Cost/i }) as HTMLInputElement;
    expect(cost.value).toBe("0.35"); // default
    // testing-library's fireEvent.change properly routes through React's
    // synthetic event system. userEvent.type() is unreliable for range
    // inputs; .value = ... + dispatchEvent does not invoke React's setter.
    fireEvent.change(cost, { target: { value: "0.6" } });
    expect(useSteeringStore.getState().paretoWeights.cost).toBeCloseTo(0.6, 5);
  });

  it("clamps out-of-range values into [0, 1]", () => {
    useSteeringStore.getState().setParetoWeight("time", 1.7);
    expect(useSteeringStore.getState().paretoWeights.time).toBe(1);
    useSteeringStore.getState().setParetoWeight("time", -0.4);
    expect(useSteeringStore.getState().paretoWeights.time).toBe(0);
    useSteeringStore.getState().setTierThreshold("tier_3", Number.NaN);
    expect(useSteeringStore.getState().tierThresholds.tier_3).toBe(0);
  });

  it("disables the Reset button when state matches defaults", () => {
    render(<Steering />);
    const reset = screen.getByRole("button", { name: /Reset to defaults/i });
    expect(reset).toBeDisabled();
  });

  it("enables Reset when state is dirty and reverts on click", async () => {
    const user = userEvent.setup();
    useSteeringStore.getState().setParetoWeight("cost", 0.9);
    render(<Steering />);
    const reset = screen.getByRole("button", { name: /Reset to defaults/i });
    expect(reset).not.toBeDisabled();
    await user.click(reset);
    expect(useSteeringStore.getState().paretoWeights).toEqual(DEFAULT_PARETO_WEIGHTS);
    expect(useSteeringStore.getState().tierThresholds).toEqual(DEFAULT_TIER_THRESHOLDS);
  });

  it("shows the audit note documenting FE-INV-033", () => {
    render(<Steering />);
    // The phrase appears in both the page subtitle and the dedicated
    // audit note in the footer; match the footer's FE-INV-033 reference
    // to disambiguate.
    expect(screen.getByText(/FE-INV-033/)).toBeInTheDocument();
  });

  it("persists state to localStorage under the documented key", () => {
    useSteeringStore.getState().setParetoWeight("fairness", 0.42);
    // Zustand persist writes asynchronously on next tick, but the call site
    // is synchronous in the basic adapter — the write happens in the same
    // microtask. Read directly.
    const raw = localStorage.getItem("synapse.steering");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw ?? "{}") as { state?: { paretoWeights?: { fairness?: number } } };
    expect(parsed.state?.paretoWeights?.fairness).toBeCloseTo(0.42, 5);
  });
});
