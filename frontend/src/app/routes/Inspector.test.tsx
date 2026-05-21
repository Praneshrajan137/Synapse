import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Inspector from "./Inspector";

describe("Inspector surface", () => {
  it("lists all eight agents in the rail", () => {
    renderWithProviders(<Inspector />, { route: "/inspector" });
    const rail = screen.getByRole("navigation", { name: "Agents" });
    expect(rail.querySelectorAll("button")).toHaveLength(8);
  });

  it("shows the selected agent's detail", async () => {
    renderWithProviders(<Inspector />, {
      route: "/inspector/pricing_oracle",
      path: "/inspector/:agentName",
    });
    expect(
      await screen.findByRole("heading", { name: "Pricing Oracle" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Reward curve")).toBeInTheDocument();
  });

  it("shows conformal calibration for Demand Prophet", async () => {
    renderWithProviders(<Inspector />, {
      route: "/inspector/demand_prophet",
      path: "/inspector/:agentName",
    });
    await screen.findByRole("heading", { name: "Demand Prophet" });
    expect(screen.getByText("Conformal calibration")).toBeInTheDocument();
  });
});
