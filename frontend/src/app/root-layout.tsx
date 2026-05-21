/**
 * SYNAPSE Atlas Console — root chrome.
 *
 * Top bar: brand · city switcher · locale picker · theme toggle ·
 * residency chip · session menu. Always-on across surfaces.
 * Left side-nav: 6 surface entries (Living City, Mission Control,
 * Decision Trace, Twin Studio, Agent Floor, Audit Vault). Each link is
 * deep-linked to the active city via `/{city}/...`.
 *
 * Theme: `[data-theme]` on <html> driven by user pref + `prefers-color-scheme`.
 * Default = dark for control-room ergonomics. Stored in localStorage.
 */
import { Link, useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@shared/ui/button";
import { cn } from "@shared/ui/cn";
import { SUPPORTED_LOCALES, type SupportedLocale } from "@shared/i18n";

interface NavItem {
  readonly key: string;
  readonly to: string;
  readonly i18nKey: string;
}

const NAV: readonly NavItem[] = [
  { key: "living-city", to: "/$city/", i18nKey: "nav.livingCity" },
  { key: "mission-control", to: "/$city/mission-control", i18nKey: "nav.missionControl" },
  { key: "decisions", to: "/$city/decisions", i18nKey: "nav.decisionTrace" },
  { key: "twin", to: "/$city/twin", i18nKey: "nav.twinStudio" },
  { key: "agents", to: "/$city/agents", i18nKey: "nav.agentFloor" },
  { key: "audit", to: "/$city/audit", i18nKey: "nav.auditVault" },
];

const THEME_KEY = "synapse_theme";

function applyTheme(theme: "light" | "dark"): void {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
}

interface RootLayoutProps {
  readonly children: ReactNode;
}

export function RootLayout({ children }: RootLayoutProps) {
  const { t, i18n } = useTranslation();
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "dark";
    return (localStorage.getItem(THEME_KEY) as "light" | "dark") ?? "dark";
  });

  useEffect(() => {
    applyTheme(theme);
    if (typeof window !== "undefined") localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const params = useParams({ strict: false }) as { city?: string };
  const activeCity = params.city ?? "bengaluru";

  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <a
        href="#atlas-main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-primary focus:px-3 focus:py-1 focus:text-primary-fg"
      >
        Skip to main content
      </a>

      <header
        role="banner"
        className="flex flex-wrap items-center gap-3 border-b border-border bg-card px-4 py-3 text-card-fg sm:px-6"
      >
        <Link
          to="/"
          className="text-ops-lg font-bold tracking-tight"
          aria-label={t("app.name")}
        >
          SYNAPSE
        </Link>

        <nav aria-label="Cities" className="ml-2 flex items-center gap-2">
          <span className="text-ops-xs uppercase tracking-wide text-muted-fg">
            {t("city.label")}
          </span>
          <CityPicker activeCity={activeCity} />
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <LocalePicker
            current={i18n.language as SupportedLocale}
            onChange={(lng) => void i18n.changeLanguage(lng)}
          />
          <ThemeToggle theme={theme} onChange={setTheme} />
          <span
            className="hidden items-center rounded-full border border-border px-3 py-1 text-ops-xs text-muted-fg sm:inline-flex"
            aria-label="Data residency"
          >
            {t("common.residencyChip")}
          </span>
          <Button variant="ghost" size="sm" aria-label={t("nav.logout")}>
            {t("nav.logout")}
          </Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside
          aria-label="Surfaces"
          className="hidden w-56 shrink-0 border-r border-border bg-card sm:block"
        >
          <ul className="flex flex-col gap-1 p-3">
            {NAV.map((item) => (
              <li key={item.key}>
                <Link
                  to={item.to}
                  params={{ city: activeCity }}
                  activeOptions={{ exact: item.to.endsWith("/") }}
                  className={({ isActive }) =>
                    cn(
                      "block rounded-md px-3 py-2 text-ops-sm text-fg hover:bg-muted",
                      isActive && "bg-muted font-medium",
                    )
                  }
                >
                  {t(item.i18nKey)}
                </Link>
              </li>
            ))}
          </ul>
        </aside>

        <main
          id="atlas-main"
          role="main"
          tabIndex={-1}
          className="flex-1 overflow-auto p-4 sm:p-6"
        >
          {children}
        </main>
      </div>

      <DemoBanner />
    </div>
  );
}

function CityPicker({ activeCity }: { activeCity: string }) {
  const { t } = useTranslation();
  return (
    <select
      aria-label={t("city.switchAria")}
      value={activeCity}
      onChange={(e) => {
        const city = e.target.value;
        if (typeof window !== "undefined") {
          // Soft swap of the city URL segment — TanStack Router will
          // rerender the city layout, re-keying every React Query cache.
          const next = window.location.pathname.replace(/^\/[^/]+/, `/${city}`);
          window.location.assign(next || `/${city}/`);
        }
      }}
      className="rounded-md border border-border bg-bg px-2 py-1 text-ops-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <option value="bengaluru">{t("city.bengaluru")}</option>
      <option value="mumbai">{t("city.mumbai")}</option>
    </select>
  );
}

function LocalePicker({
  current,
  onChange,
}: {
  current: SupportedLocale;
  onChange: (l: SupportedLocale) => void;
}) {
  const { t } = useTranslation();
  return (
    <label className="flex items-center gap-2 text-ops-xs">
      <span className="sr-only">{t("locale.label")}</span>
      <select
        value={current}
        onChange={(e) => onChange(e.target.value as SupportedLocale)}
        className="rounded-md border border-border bg-bg px-2 py-1 text-ops-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={t("locale.label")}
      >
        {SUPPORTED_LOCALES.map((l) => (
          <option key={l} value={l}>
            {t(`locale.${l}`)}
          </option>
        ))}
      </select>
    </label>
  );
}

function ThemeToggle({
  theme,
  onChange,
}: {
  theme: "light" | "dark";
  onChange: (t: "light" | "dark") => void;
}) {
  const { t } = useTranslation();
  return (
    <Button
      variant="outline"
      size="sm"
      aria-label={t("theme.label")}
      onClick={() => onChange(theme === "dark" ? "light" : "dark")}
    >
      {theme === "dark" ? t("theme.light") : t("theme.dark")}
    </Button>
  );
}

function DemoBanner() {
  const { t } = useTranslation();
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  if (params.get("demo") !== "1") return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed bottom-3 right-3 rounded-md border border-border bg-card/80 px-3 py-1 text-ops-xs font-semibold tracking-widest text-muted-fg backdrop-blur"
    >
      {t("common.demoMode")}
    </div>
  );
}
