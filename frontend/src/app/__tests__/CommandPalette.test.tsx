import { CommandPalette } from "@app/CommandPalette";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
// i18next global bootstrap (registers the "common" namespace) — palette copy
// resolves through the `en` catalog (Req 8.1).
import "@i18n/index";

function renderPalette() {
  return render(
    <MemoryRouter>
      <CommandPalette />
    </MemoryRouter>,
  );
}

describe("CommandPalette", () => {
  it("is closed until ⌘K is pressed", async () => {
    const user = userEvent.setup();
    renderPalette();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    await user.keyboard("{Meta>}k{/Meta}");
    expect(await screen.findByRole("combobox")).toBeInTheDocument();
  });

  it("opens with Ctrl+K too (non-mac)", async () => {
    const user = userEvent.setup();
    renderPalette();
    await user.keyboard("{Control>}k{/Control}");
    expect(await screen.findByRole("combobox")).toBeInTheDocument();
  });

  it("fuzzy-filters the command list as you type", async () => {
    const user = userEvent.setup();
    renderPalette();
    await user.keyboard("{Control>}k{/Control}");
    const input = await screen.findByRole("combobox");
    await user.type(input, "twin");
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveTextContent("Twin Lab");
  });

  it("shows an empty message when nothing matches", async () => {
    const user = userEvent.setup();
    renderPalette();
    await user.keyboard("{Control>}k{/Control}");
    await user.type(await screen.findByRole("combobox"), "zzzzz");
    expect(screen.getByText(/No matching commands/)).toBeInTheDocument();
  });

  it("marks the first option active by default (aria-selected)", async () => {
    const user = userEvent.setup();
    renderPalette();
    await user.keyboard("{Control>}k{/Control}");
    await screen.findByRole("combobox");
    const first = screen.getAllByRole("option")[0];
    expect(first?.getAttribute("aria-selected")).toBe("true");
  });

  it("exposes a Go-to command for every primary Surface (incl. Operations)", async () => {
    const user = userEvent.setup();
    renderPalette();
    await user.keyboard("{Control>}k{/Control}");
    const input = await screen.findByRole("combobox");
    // Operations (Standing Watch) is a primary Surface — reachable by keyboard.
    await user.type(input, "operations");
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveTextContent("Operations");
  });
});
