import { type Theme, applyTheme, useThemeStore } from "@state/theme.store";
import { useTranslation } from "react-i18next";

const THEMES: ReadonlyArray<Theme> = ["dark", "light", "hc"];

const THEME_GLYPH: Record<Theme, string> = {
  dark: "●",
  light: "○",
  hc: "◐",
};

/**
 * Three-state theme control (dark / light / high-contrast) in the Shell.
 * The token layer has been fully dual-theme since the chromatic system
 * landed — this is the missing user-facing affordance. Selection is the
 * pressed state + the theme NAME, never glyph alone (INV-CLR-011).
 */
export function ThemeToggle() {
  const { t } = useTranslation("common");
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);

  function select(next: Theme): void {
    setTheme(next);
    applyTheme(next);
  }

  return (
    <div
      role="group"
      aria-label={t("theme.label")}
      className="flex items-center rounded-md border border-border bg-surface p-0.5"
    >
      {THEMES.map((option) => {
        const selected = option === theme;
        return (
          <button
            key={option}
            type="button"
            onClick={() => select(option)}
            aria-pressed={selected}
            aria-label={t(`theme.${option}`)}
            title={t(`theme.${option}`)}
            className={
              selected
                ? "rounded px-1.5 py-0.5 bg-surface-raised text-2xs font-medium text-ink focus-visible:outline-none focus-visible:shadow-focus"
                : "rounded px-1.5 py-0.5 text-2xs font-medium text-ink-subtle hover:text-ink focus-visible:outline-none focus-visible:shadow-focus"
            }
          >
            <span aria-hidden>{THEME_GLYPH[option]}</span>
          </button>
        );
      })}
    </div>
  );
}
