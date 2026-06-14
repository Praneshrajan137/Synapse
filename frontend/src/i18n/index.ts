// i18n bootstrap (English-only — see CLAUDE.md "English-only UI" rule).
//
// The UI ships in English only. The i18next + react-i18next machinery is kept
// because ~18 surfaces resolve copy through `t()` / `useTranslation`, but there
// is exactly ONE locale (`en`) and no language detector or switcher — language
// is deterministically English. Do NOT add another locale catalog or a picker.

import i18n from "i18next";
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

export type Locale = "en";

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

void i18n.use(initReactI18next).init({
  lng: DEFAULT_LOCALE,
  fallbackLng: DEFAULT_LOCALE,
  supportedLngs: ["en"],
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
  },
});

export { i18n };

/** Stable thin wrapper so non-React callers can still translate. */
export function t(key: string, options?: Record<string, unknown>): string {
  return i18n.t(key, options ?? {}) as unknown as string;
}
