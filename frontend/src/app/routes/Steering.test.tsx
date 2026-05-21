import { useUIStore } from "@/app/store/uiStore";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import Steering from "./Steering";

describe("Steering surface", () => {
  it("renders the Pareto weights and confidence thresholds", () => {
    renderWithProviders(<Steering />, { route: "/steering" });
    expect(screen.getByText("Pareto objective weights")).toBeInTheDocument();
    expect(screen.getByText("Confidence thresholds")).toBeInTheDocument();
    expect(screen.getByText("Sustainability")).toBeInTheDocument();
  });

  it("starts cinematic demo mode", async () => {
    renderWithProviders(<Steering />, { route: "/steering" });
    expect(useUIStore.getState().demoMode).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: /Start demo/ }));
    expect(useUIStore.getState().demoMode).toBe(true);
    useUIStore.getState().setDemoMode(false);
  });

  it("switches the UI language", async () => {
    renderWithProviders(<Steering />, { route: "/steering" });
    const select = screen.getByLabelText(/Language|भाषा|ಭಾಷೆ/);
    await userEvent.selectOptions(select, "hi");
    expect(useUIStore.getState().locale).toBe("hi");
    useUIStore.getState().setLocale("en");
  });
});
