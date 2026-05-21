/**
 * SYNAPSE Atlas Console — Twin Studio scenario library.
 *
 * Zustand-backed in-memory store, mirrored to IndexedDB so a saved
 * scenario survives a refresh. Plan §5.4: scenarios are name-able,
 * load-able, and shareable via URL search-params (the URL itself
 * encodes the canonical input).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { create } from "zustand";
import { get as idbGet, set as idbSet } from "idb-keyval";

import {
  type SavedScenario,
  SavedScenarioSchema,
  type ScenarioInput,
} from "../model/scenario";

const STORAGE_KEY = "atlas:twin:scenarios";

interface LibraryState {
  scenarios: readonly SavedScenario[];
  hydrate: (initial: readonly SavedScenario[]) => void;
  save: (entry: SavedScenario) => void;
  remove: (id: string) => void;
}

const useStore = create<LibraryState>((set) => ({
  scenarios: [],
  hydrate: (initial) => set({ scenarios: initial }),
  save: (entry) =>
    set((s) => ({
      scenarios: [
        entry,
        ...s.scenarios.filter((x) => x.id !== entry.id),
      ].slice(0, 50),
    })),
  remove: (id) => set((s) => ({ scenarios: s.scenarios.filter((x) => x.id !== id) })),
}));

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export interface UseScenarioLibraryResult {
  readonly scenarios: readonly SavedScenario[];
  readonly save: (label: string, input: ScenarioInput) => SavedScenario;
  readonly remove: (id: string) => void;
}

export function useScenarioLibrary(): UseScenarioLibraryResult {
  const scenarios = useStore((s) => s.scenarios);
  const hydrate = useStore((s) => s.hydrate);
  const save = useStore((s) => s.save);
  const remove = useStore((s) => s.remove);
  const hydratedRef = useRef(false);
  const [, force] = useState(0);

  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    void idbGet<unknown>(STORAGE_KEY).then((raw) => {
      if (!Array.isArray(raw)) return;
      const parsed = raw
        .map((item) => SavedScenarioSchema.safeParse(item))
        .filter((r): r is { success: true; data: SavedScenario } => r.success)
        .map((r) => r.data);
      hydrate(parsed);
      force((t) => t + 1);
    });
  }, [hydrate]);

  // Persist on every mutation; idb-keyval is debounce-light enough for 50-entry libraries.
  useEffect(() => {
    if (!hydratedRef.current) return;
    void idbSet(STORAGE_KEY, scenarios.slice());
  }, [scenarios]);

  const api = useMemo<UseScenarioLibraryResult>(
    () => ({
      scenarios,
      save: (label, input) => {
        const entry: SavedScenario = {
          id: newId(),
          label,
          createdAt: new Date().toISOString(),
          input,
        };
        save(entry);
        return entry;
      },
      remove,
    }),
    [scenarios, save, remove],
  );

  return api;
}
