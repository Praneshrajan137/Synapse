import type { City } from "@domain/primitives";
import { fuzzyFilter } from "@lib/fuzzy";
import * as Dialog from "@radix-ui/react-dialog";
import { useCityStore } from "@state/city.store";
import { applyTheme, useThemeStore } from "@state/theme.store";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

/**
 * CommandPalette — the keyboard-first verb surface (SENSORIUM P6; Raycast /
 * Linear / Bloomberg lineage). ⌘K (or Ctrl+K) anywhere opens it; type to fuzzy-
 * filter; ↑/↓ to move, Enter to run, Esc to close. Expert operators live in the
 * tool all shift — the keyboard beats the mouse.
 *
 * Commands are data-driven so new verbs are one array entry. Pure navigation +
 * local state changes today (go-to surface, switch city, set theme); decision-
 * scoped actions (override, steering) plug in here next.
 */

interface Command {
  readonly id: string;
  readonly title: string;
  readonly group: string;
  readonly keywords?: string;
  readonly run: () => void;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const navigate = useNavigate();
  const setCity = useCityStore((s) => s.setCity);
  const setTheme = useThemeStore((s) => s.setTheme);

  // Global ⌘K / Ctrl+K toggle. `setOpen` from useState is stable across renders.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const commands = useMemo<Command[]>(() => {
    const go = (path: string) => () => {
      navigate(path);
      setOpen(false);
    };
    const setCityCmd = (city: City) => () => {
      setCity(city);
      setOpen(false);
    };
    const setThemeCmd = (theme: "dark" | "light" | "hc") => () => {
      setTheme(theme);
      applyTheme(theme);
      setOpen(false);
    };
    return [
      {
        id: "go-mission",
        title: "Mission Control",
        group: "Go to",
        keywords: "cortex pulse home",
        run: go("/"),
      },
      {
        id: "go-cockpit",
        title: "Override Cockpit",
        group: "Go to",
        keywords: "escalation hitl threshold",
        run: go("/cockpit"),
      },
      {
        id: "go-decisions",
        title: "Decision Theater",
        group: "Go to",
        keywords: "tribunal pareto replay",
        run: go("/decisions"),
      },
      {
        id: "go-agents",
        title: "Agent Council",
        group: "Go to",
        keywords: "health latency",
        run: go("/agents"),
      },
      {
        id: "go-twin",
        title: "Twin Lab",
        group: "Go to",
        keywords: "projection divergence simulate",
        run: go("/twin"),
      },
      {
        id: "go-steering",
        title: "Steering",
        group: "Go to",
        keywords: "weights pareto will",
        run: go("/steering"),
      },
      {
        id: "go-audit",
        title: "Audit Vault",
        group: "Go to",
        keywords: "memory compliance",
        run: go("/audit"),
      },
      {
        id: "go-demo",
        title: "Demo Theater",
        group: "Go to",
        keywords: "scenario",
        run: go("/demo"),
      },
      {
        id: "city-bengaluru",
        title: "Switch city: Bengaluru",
        group: "City",
        run: setCityCmd("bengaluru"),
      },
      { id: "city-mumbai", title: "Switch city: Mumbai", group: "City", run: setCityCmd("mumbai") },
      { id: "theme-dark", title: "Theme: Dark", group: "Theme", run: setThemeCmd("dark") },
      { id: "theme-light", title: "Theme: Light", group: "Theme", run: setThemeCmd("light") },
      {
        id: "theme-hc",
        title: "Theme: High contrast",
        group: "Theme",
        keywords: "accessibility",
        run: setThemeCmd("hc"),
      },
    ];
  }, [navigate, setCity, setTheme]);

  const filtered = useMemo(
    () => fuzzyFilter(commands, query, (c) => `${c.title} ${c.keywords ?? ""}`),
    [commands, query],
  );

  // Reset selection + query whenever the palette opens; focus the input.
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      // Radix focuses the content; defer so our input wins.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, filtered.length - 1)));
  }, [filtered.length]);

  function onInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(filtered.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      filtered[active]?.run();
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-canvas/70 backdrop-blur-sm" />
        <Dialog.Content
          className="fixed left-1/2 top-[18%] z-50 w-[min(560px,92vw)] -translate-x-1/2 overflow-hidden rounded-lg border border-border bg-surface shadow-e4"
          aria-describedby={undefined}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder="Search commands…  (Go to · City · Theme)"
            aria-label="Command palette search"
            role="combobox"
            aria-expanded
            aria-controls="command-palette-list"
            aria-activedescendant={filtered[active] ? `cmd-${filtered[active].id}` : undefined}
            className="w-full border-b border-border bg-transparent px-4 py-3 text-sm text-ink outline-none placeholder:text-ink-subtle"
          />
          <ul
            id="command-palette-list"
            role="listbox"
            aria-label="Commands"
            className="max-h-[320px] overflow-auto py-1"
          >
            {filtered.length === 0 ? (
              <li className="px-4 py-6 text-center text-xs text-ink-muted">
                No matching commands.
              </li>
            ) : (
              filtered.map((cmd, i) => (
                <li key={cmd.id} id={`cmd-${cmd.id}`} role="option" aria-selected={i === active}>
                  <button
                    type="button"
                    tabIndex={-1}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => cmd.run()}
                    className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm transition-colors duration-fast ${
                      i === active ? "bg-surface-raised text-ink" : "text-ink-muted"
                    }`}
                  >
                    <span>{cmd.title}</span>
                    <span className="text-2xs uppercase tracking-wide text-ink-subtle">
                      {cmd.group}
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>
          <footer className="flex items-center gap-3 border-t border-border px-4 py-2 text-2xs text-ink-subtle">
            <span>↑↓ navigate</span>
            <span>⏎ run</span>
            <span>esc close</span>
            <span className="ml-auto font-mono">⌘K</span>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
