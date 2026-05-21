import { renderWithProviders } from "@/test/render";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import Council from "./Council";

describe("Council surface", () => {
  it("loads the escalation and shows the recommended action", async () => {
    renderWithProviders(<Council />, { route: "/council" });
    expect(await screen.findByRole("heading", { name: "Council" })).toBeInTheDocument();
    expect(screen.getByText("Recommended action")).toBeInTheDocument();
  });

  it("ranks the proposals", async () => {
    renderWithProviders(<Council />, { route: "/council" });
    await screen.findByRole("heading", { name: "Council" });
    expect(screen.getByLabelText("Agent proposals")).toBeInTheDocument();
  });

  it("blocks override submission until a choice and reason are given (UI-COUNCIL-002)", async () => {
    renderWithProviders(<Council />, { route: "/council" });
    await screen.findByRole("heading", { name: "Council" });

    const submit = screen.getByRole("button", { name: "Submit override" });
    expect(submit).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /Approve/ }));
    expect(submit).toBeDisabled(); // choice alone is not enough

    await userEvent.type(
      screen.getByLabelText(/Reason/),
      "supplier reliability confirmed against the playbook",
    );
    expect(submit).toBeEnabled();
  });

  it("records an override and confirms it", async () => {
    renderWithProviders(<Council />, { route: "/council" });
    await screen.findByRole("heading", { name: "Council" });

    await userEvent.click(screen.getByRole("button", { name: /Approve/ }));
    await userEvent.type(screen.getByLabelText(/Reason/), "approved — within tolerance");
    await userEvent.click(screen.getByRole("button", { name: "Submit override" }));

    await waitFor(() => {
      expect(screen.getByText("Override recorded")).toBeInTheDocument();
    });
  });
});
