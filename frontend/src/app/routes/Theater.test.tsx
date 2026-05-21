import { renderWithProviders } from "@/test/render";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import Theater from "./Theater";

describe("Theater surface", () => {
  it("loads a decision and shows the phase ribbon", async () => {
    renderWithProviders(<Theater />, { route: "/theater/dec-theater-1" });
    expect(await screen.findByRole("heading", { name: "Theater" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Consensus phase/)).toBeInTheDocument();
  });

  it("renders the eight-agent constellation", async () => {
    renderWithProviders(<Theater />, { route: "/theater/dec-theater-2" });
    await screen.findByRole("heading", { name: "Theater" });
    // Every agent has a node, even without a proposal.
    expect(screen.getByRole("button", { name: /Demand Prophet/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Routing Navigator/ })).toBeInTheDocument();
  });

  it("advances the context tape when stepped forward", async () => {
    renderWithProviders(<Theater />, { route: "/theater/dec-theater-3" });
    await screen.findByRole("heading", { name: "Theater" });

    const tapeCountBefore = screen.getByText(/append-only ·/).textContent;
    await userEvent.click(screen.getByRole("button", { name: "Step forward" }));
    await waitFor(() => {
      expect(screen.getByText(/append-only ·/).textContent).not.toBe(tapeCountBefore);
    });
  });
});
