import { renderWithProviders } from "@/test/render";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import Twin from "./Twin";

describe("Twin surface", () => {
  it("renders the supply network", async () => {
    renderWithProviders(<Twin />, { route: "/twin" });
    expect(
      await screen.findByRole("img", { name: /Supply network/ }),
    ).toBeInTheDocument();
  });

  it("runs a what-if and shows the Monte Carlo distribution", async () => {
    renderWithProviders(<Twin />, { route: "/twin" });
    await screen.findByRole("img", { name: /Supply network/ });

    await userEvent.click(screen.getByRole("button", { name: /Run what-if/ }));
    await waitFor(() => {
      expect(screen.getByText("Monte Carlo result")).toBeInTheDocument();
    });
    expect(screen.getByText("Fill rate")).toBeInTheDocument();
  });
});
