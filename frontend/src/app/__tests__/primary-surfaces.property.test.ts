// Feature: atlas-console-elevation, Property 28: The command palette reaches every primary Surface
//
// Property 28 (Validates: Requirements 8.2) — every primary Surface in the
// route registry (`PRIMARY_SURFACES`) has a keyboard-activatable command
// palette entry, derived mechanically through `surfaceGoToCommands()`. The
// palette therefore reaches every primary Surface without a pointer.
//
// WHY THIS IS A MODEL-LEVEL PROPERTY
// ----------------------------------
// The CommandPalette attaches its navigation `run` at render time, but the
// COVERAGE guarantee lives in the pure `surfaceGoToCommands()` map: because it
// is a total, injective map over `PRIMARY_SURFACES`, every primary Surface is
// guaranteed exactly one keyboard-activatable command (a stable `go-${id}`
// command id, the surface's route path, and an i18n label key). Asserting the
// surjection + injection here proves the reachability invariant independent of
// any React wiring.

import { PRIMARY_SURFACES, surfaceGoToCommands } from "@app/primary-surfaces";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

const surfaceArb = fc.constantFrom(...PRIMARY_SURFACES);

describe("primary-surfaces — Property 28: the command palette reaches every primary Surface", () => {
  it("every primary Surface has exactly one keyboard-activatable palette command", () => {
    fc.assert(
      fc.property(surfaceArb, (surface) => {
        const commands = surfaceGoToCommands();
        const matches = commands.filter((c) => c.id === `go-${surface.id}`);

        // Exactly one command per surface — a keyboard-activatable entry.
        expect(matches).toHaveLength(1);
        const command = matches[0]!;

        // The command carries everything the palette needs to render a
        // keyboard-activatable "Go to" item that navigates to the surface.
        expect(command.path).toBe(surface.path);
        expect(command.labelKey).toBe(surface.labelKey);
        expect(command.id).toBe(`go-${surface.id}`);
        // A non-empty group key so the item is grouped, listed, and reachable.
        expect(command.groupKey.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 },
    );
  });

  it("the command registry is a total, injective cover of the surface registry", () => {
    const commands = surfaceGoToCommands();

    // Surjective onto surfaces: one command per primary Surface, no more.
    expect(commands).toHaveLength(PRIMARY_SURFACES.length);

    // Injective: command ids are unique (no surface shadows another).
    const ids = commands.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);

    // Every command maps back to a real primary Surface (no orphan commands).
    const surfaceIds = new Set(PRIMARY_SURFACES.map((s) => `go-${s.id}`));
    for (const id of ids) {
      expect(surfaceIds.has(id)).toBe(true);
    }
  });
});
