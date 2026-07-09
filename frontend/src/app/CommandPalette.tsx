import type { City } from "@domain/primitives";
import { fuzzyFilter } from "@lib/fuzzy";
import * as Dialog from "@radix-ui/react-dialog";
import { useCityStore } from "@state/city.store";
import { useFirehoseStore } from "@state/firehose.store";
import { applyTheme, useThemeStore } from "@state/theme.store";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { surfaceGoToCommands } from "./primary-surfaces";

/**
 * CommandPalette — the keyboard-first verb surface (SENSORIUM P6; Raycast /
 * Linear / Bloomberg lineage). ⌘K (or Ctrl+K) anywhere opens it; type to fuzzy-
 * filter; ↑/↓ to move, Enter to run, Esc to close. Expert operators live in the
 * tool all shift — the keyboard beats the mouse.
 *
 * "Go to" commands are DERIVED from the `PRIMARY_SURFACES` route registry
 * (`primary-surfaces.ts`) so every primary Surface is reachable by keyboard
 * with no pointer, and coverage is mechanical (Req 8.2, Property 28). Every
 * user-visible string resolves through the i18next `en` catalog (Req 8.1).
 * Local-state verbs (switch city, set theme) round out the surface.
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

  const { t } = useTranslation("common");
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

    // "Go to" commands are derived from the primary-Surface route registry so
    // every primary Surface has a keyboard-activatable entry by construction.
    const goTo: Command[] = surfaceGoToCommands().map((c) => ({
      id: c.id,
      title: t(c.labelKey),
      group: t(c.groupKey),
      ...(c.keywords ? { keywords: c.keywords } : {}),
      run: go(c.path),
    }));

    return [
      ...goTo,
      {
        id: "go-council",
        title: t("surface.council-theater"),
        group: t("command.group.go-to"),
        keywords: t("council.aria.latest"),
        run: () => {
          // Best-effort: open the most recent live decision's reconstruction;
          // fall back to the Decision Theater list when the firehose is empty.
          const latest = useFirehoseStore.getState().decisions.items.at(-1);
          navigate(latest ? `/council/${latest.decision_id}` : "/decisions");
          setOpen(false);
        },
      },
      {
        id: "city-bengaluru",
        title: t("command.city.bengaluru"),
        group: t("command.group.city"),
        run: setCityCmd("bengaluru"),
      },
      {
        id: "city-mumbai",
        title: t("command.city.mumbai"),
        group: t("command.group.city"),
        run: setCityCmd("mumbai"),
      },
      {
        id: "theme-dark",
        title: t("command.theme.dark"),
        group: t("command.group.theme"),
        run: setThemeCmd("dark"),
      },
      {
        id: "theme-light",
        title: t("command.theme.light"),
        group: t("command.group.theme"),
        run: setThemeCmd("light"),
      },
      {
        id: "theme-hc",
        title: t("command.theme.hc"),
        group: t("command.group.theme"),
        keywords: "accessibility",
        run: setThemeCmd("hc"),
      },
    ];
  }, [navigate, setCity, setTheme, t]);

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
          <Dialog.Title className="sr-only">{t("command.title")}</Dialog.Title>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder={t("command.search_placeholder")}
            aria-label={t("command.search_label")}
            role="combobox"
            aria-expanded
            aria-controls="command-palette-list"
            aria-activedescendant={filtered[active] ? `cmd-${filtered[active].id}` : undefined}
            className="w-full border-b border-border bg-transparent px-4 py-3 text-sm text-ink outline-none placeholder:text-ink-subtle"
          />
          {/* Canonical ARIA combobox-popup: focus stays on the input and moves
              virtually via aria-activedescendant, so the listbox/options carry
              tabIndex={-1} rather than being in the tab order. A div (not ul/li)
              hosts the listbox role so no non-interactive-element rule applies. */}
          <div
            id="command-palette-list"
            // biome-ignore lint/a11y/useSemanticElements: a combobox-popup listbox has no native HTML equivalent.
            role="listbox"
            aria-label={t("command.list_label")}
            tabIndex={-1}
            className="max-h-[320px] overflow-auto py-1"
          >
            {filtered.length === 0 ? (
              <p className="px-4 py-6 text-center text-xs text-ink-muted">{t("command.empty")}</p>
            ) : (
              filtered.map((cmd, i) => (
                <div
                  key={cmd.id}
                  id={`cmd-${cmd.id}`}
                  // biome-ignore lint/a11y/useSemanticElements: a listbox option has no native HTML equivalent in a custom popup.
                  role="option"
                  aria-selected={i === active}
                  tabIndex={-1}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => cmd.run()}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      cmd.run();
                    }
                  }}
                  className={`flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-2 text-left text-sm transition-colors duration-fast ${
                    i === active ? "bg-surface-raised text-ink" : "text-ink-muted"
                  }`}
                >
                  <span>{cmd.title}</span>
                  <span className="text-2xs uppercase tracking-wide text-ink-subtle">
                    {cmd.group}
                  </span>
                </div>
              ))
            )}
          </div>
          <footer className="flex items-center gap-3 border-t border-border px-4 py-2 text-2xs text-ink-subtle">
            <span>↑↓ {t("command.hint.navigate")}</span>
            <span>⏎ {t("command.hint.run")}</span>
            <span>esc {t("command.hint.close")}</span>
            <span className="ml-auto font-mono">⌘K</span>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
