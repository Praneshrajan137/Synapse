// i18n bootstrap (P4.B26 / FE-INV-013).
//
// i18next + react-i18next + browser language detector. English (en) is
// the source; Hindi (hi) is the v1 catalog. Locales are split per surface
// namespace for lazy-loading.

import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import enAgents from "./en/agent-council.json";
import enAudit from "./en/audit-vault.json";
import enAuth from "./en/auth.json";
import enCockpit from "./en/cockpit.json";
import enCommon from "./en/common.json";
import enDecisions from "./en/decision-theater.json";
import enDemo from "./en/demo-theater.json";
import enMission from "./en/mission-control.json";
import enSteering from "./en/steering.json";
import enTwin from "./en/twin-lab.json";

import hiAgents from "./hi/agent-council.json";
import hiAudit from "./hi/audit-vault.json";
import hiAuth from "./hi/auth.json";
import hiCockpit from "./hi/cockpit.json";
import hiCommon from "./hi/common.json";
import hiDecisions from "./hi/decision-theater.json";
import hiDemo from "./hi/demo-theater.json";
import hiMission from "./hi/mission-control.json";
import hiSteering from "./hi/steering.json";
import hiTwin from "./hi/twin-lab.json";

export type Locale = "en" | "hi" | "kn" | "mr";

export const DEFAULT_LOCALE: Locale = "en";

export const NAMESPACES = [
  "common",
  "cockpit",
  "mission-control",
  "decision-theater",
  "agent-council",
  "twin-lab",
  "demo-theater",
  "audit-vault",
  "auth",
  "steering",
] as const;

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: ["en", "hi"],
    defaultNS: "common",
    interpolation: { escapeValue: false },
    resources: {
      en: {
        common: enCommon,
        cockpit: enCockpit,
        "mission-control": enMission,
        "decision-theater": enDecisions,
        "agent-council": enAgents,
        "twin-lab": enTwin,
        "demo-theater": enDemo,
        "audit-vault": enAudit,
        auth: enAuth,
        steering: enSteering,
      },
      hi: {
        common: hiCommon,
        cockpit: hiCockpit,
        "mission-control": hiMission,
        "decision-theater": hiDecisions,
        "agent-council": hiAgents,
        "twin-lab": hiTwin,
        "demo-theater": hiDemo,
        "audit-vault": hiAudit,
        auth: hiAuth,
        steering: hiSteering,
      },
    },
  });

export { i18n };

/** Stable thin wrapper so non-React callers can still translate. */
export function t(key: string, options?: Record<string, unknown>): string {
  return i18n.t(key, options ?? {}) as unknown as string;
}
