import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Replay from "./Replay";

describe("Replay surface", () => {
  it("renders the audit timeline scrubber", async () => {
    renderWithProviders(<Replay />, { route: "/replay" });
    expect(await screen.findByLabelText("Audit timeline")).toBeInTheDocument();
  });

  it("replays a specific decision by id", async () => {
    renderWithProviders(<Replay />, { route: "/replay/dec-hist-2" });
    expect(await screen.findByRole("heading", { name: "Replay" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Consensus phase/)).toBeInTheDocument();
  });

  it("shows the tamper-evident audit footer (invariant I-4)", async () => {
    renderWithProviders(<Replay />, { route: "/replay/dec-hist-3" });
    await screen.findByRole("heading", { name: "Replay" });
    expect(screen.getByText("Tamper-evident")).toBeInTheDocument();
    expect(screen.getByText(/Immutable since/)).toBeInTheDocument();
  });

  it("exposes a scrubber that holds the consensus replay step", async () => {
    renderWithProviders(<Replay />, { route: "/replay/dec-hist-4" });
    await screen.findByRole("heading", { name: "Replay" });
    expect(screen.getByLabelText("Scrub consensus replay")).toBeInTheDocument();
  });
});
