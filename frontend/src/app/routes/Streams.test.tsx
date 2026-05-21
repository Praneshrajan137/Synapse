import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import Streams from "./Streams";

describe("Streams surface", () => {
  it("renders the sixteen Kafka topics", async () => {
    renderWithProviders(<Streams />, { route: "/streams" });
    expect(await screen.findByText("synapse.orchestrator.decision")).toBeInTheDocument();
    expect(screen.getByText("16 topics")).toBeInTheDocument();
  });

  it("opens a topic inspector on selection", async () => {
    renderWithProviders(<Streams />, { route: "/streams" });
    await screen.findByText("synapse.audit.log");
    await userEvent.click(screen.getByText("synapse.audit.log"));
    expect(screen.getByText("Live tail")).toBeInTheDocument();
  });
});
