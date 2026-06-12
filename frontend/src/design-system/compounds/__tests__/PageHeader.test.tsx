import { PageHeader } from "@ds/compounds/PageHeader";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("PageHeader", () => {
  it("renders the title as the page h1 in display type", () => {
    render(<PageHeader title="Audit Vault" subtitle="Append-only decision provenance." />);
    const h1 = screen.getByRole("heading", { level: 1, name: "Audit Vault" });
    expect(h1.className).toMatch(/font-display/);
    expect(screen.getByText("Append-only decision provenance.")).toBeInTheDocument();
  });

  it("hero size uses the larger display step", () => {
    render(<PageHeader size="hero" title="Mission Control" />);
    expect(screen.getByRole("heading", { level: 1 }).className).toMatch(/text-display-lg/);
  });

  it("renders status and actions slots", () => {
    render(
      <PageHeader
        title="Steering"
        status={<span data-testid="status">live</span>}
        actions={<button type="button">Export</button>}
      />,
    );
    expect(screen.getByTestId("status")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Export" })).toBeInTheDocument();
  });
});
