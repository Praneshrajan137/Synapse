import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Bridge from "./Bridge";

describe("Bridge surface", () => {
  it("renders the KPI ribbon from the gateway", async () => {
    renderWithProviders(<Bridge />);
    expect(await screen.findByText("Fill rate")).toBeInTheDocument();
    expect(await screen.findByText("Waste rate")).toBeInTheDocument();
  });

  it("renders the living map for the active city", () => {
    renderWithProviders(<Bridge />);
    expect(screen.getByRole("img", { name: /dark-store network/ })).toBeInTheDocument();
  });

  it("renders the decision tape and escalation queue", () => {
    renderWithProviders(<Bridge />);
    expect(screen.getByLabelText("Decision tape")).toBeInTheDocument();
    expect(screen.getByLabelText("Escalation queue")).toBeInTheDocument();
  });

  it("shows the tier histogram", () => {
    renderWithProviders(<Bridge />);
    expect(screen.getByLabelText("Tier distribution")).toBeInTheDocument();
  });
});
