/**
 * SYNAPSE Atlas Console — i18n bootstrap.
 *
 * Plan §4 / ADR-025: Day-1 ships en + hi (covers ~85% of Indian
 * quick-commerce ops staff per Plan-agent critique). Scaffolded empty
 * so kn + mr land as 1-PR additions in S4+.
 *
 * - **ICU MessageFormat** is the format on the wire (`i18next-icu`),
 *   so plurals and gendered units work without bespoke pluralization rules.
 * - **`i18next-parser`** extracts keys at build time. CI gates on missing
 *   translations per locale; no silent string in production.
 * - **`en-IN` is the source locale** (not `en`). Indian English varies
 *   on dates, numerals, and phrasing in ways that matter to ops. Storybook
 *   defaults to en-IN; the locale picker exposes the others.
 *
 * Usage in components:
 *   import { useTranslation } from "react-i18next";
 *   const { t } = useTranslation();
 *   t("missionControl.escalation.approve");
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import ICU from "i18next-icu";

import enIN from "./locales/en-IN.json";
import hiIN from "./locales/hi-IN.json";
import knIN from "./locales/kn-IN.json";
import mrIN from "./locales/mr-IN.json";
// All four locales are populated as of S6. CI's i18next-parser run
// gates on missing keys per locale.

export const SUPPORTED_LOCALES = ["en-IN", "hi-IN", "kn-IN", "mr-IN"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: SupportedLocale = "en-IN";

// Single namespace: keep keys grouped by surface inside the JSON tree.
// Adding a namespace per surface is a footgun at this scale (causes
// nested loaders); a flat `translation` namespace is simpler and CI
// catches missing keys regardless.
export async function bootstrapI18n(): Promise<typeof i18n> {
  if (i18n.isInitialized) return i18n;

  await i18n
    .use(ICU)
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
      resources: {
        "en-IN": { translation: enIN },
        "hi-IN": { translation: hiIN },
        "kn-IN": { translation: knIN },
        "mr-IN": { translation: mrIN },
      },
      fallbackLng: DEFAULT_LOCALE,
      supportedLngs: SUPPORTED_LOCALES,
      load: "currentOnly",
      ns: ["translation"],
      defaultNS: "translation",
      interpolation: { escapeValue: false }, // React escapes for us
      detection: {
        order: ["querystring", "cookie", "navigator", "htmlTag"],
        lookupQuerystring: "lng",
        lookupCookie: "synapse_locale",
        caches: ["cookie"],
        cookieMinutes: 60 * 24 * 365,
      },
      // Reduce dev-mode noise. Missing-key signal comes from i18next-parser
      // in CI, not runtime warnings.
      saveMissing: false,
      returnEmptyString: false,
    });

  return i18n;
}

export default i18n;
