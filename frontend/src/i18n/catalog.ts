/**
 * Lightweight i18n (plan section 9, Phase 9).
 *
 * A typed message catalog for Bengaluru/Mumbai operators — English,
 * Hindi, Kannada and Marathi. This is the i18n *architecture*; surface
 * adoption is incremental. Zero runtime cost beyond a dictionary lookup;
 * no external dependency (tenet T-12).
 */

export const LOCALES = ["en", "hi", "kn", "mr"] as const;
export type Locale = (typeof LOCALES)[number];

export const LOCALE_LABEL: Record<Locale, string> = {
  en: "English",
  hi: "हिन्दी",
  kn: "ಕನ್ನಡ",
  mr: "मराठी",
};

/** Catalog keys — extend as surfaces adopt i18n. */
export type MessageKey =
  | "app.tagline"
  | "surface.bridge"
  | "surface.theater"
  | "surface.council"
  | "surface.replay"
  | "surface.twin"
  | "surface.inspector"
  | "surface.streams"
  | "action.approve"
  | "action.reject"
  | "status.allClear"
  | "common.language";

type Catalog = Record<MessageKey, string>;

const en: Catalog = {
  "app.tagline": "An operating theater for autonomous decisions",
  "surface.bridge": "Bridge",
  "surface.theater": "Theater",
  "surface.council": "Council",
  "surface.replay": "Replay",
  "surface.twin": "Twin",
  "surface.inspector": "Inspector",
  "surface.streams": "Streams",
  "action.approve": "Approve",
  "action.reject": "Reject",
  "status.allClear": "All clear",
  "common.language": "Language",
};

const hi: Catalog = {
  "app.tagline": "स्वायत्त निर्णयों के लिए एक संचालन कक्ष",
  "surface.bridge": "ब्रिज",
  "surface.theater": "थिएटर",
  "surface.council": "काउंसिल",
  "surface.replay": "रीप्ले",
  "surface.twin": "ट्विन",
  "surface.inspector": "इंस्पेक्टर",
  "surface.streams": "स्ट्रीम्स",
  "action.approve": "स्वीकृत करें",
  "action.reject": "अस्वीकार करें",
  "status.allClear": "सब ठीक है",
  "common.language": "भाषा",
};

const kn: Catalog = {
  "app.tagline": "ಸ್ವಾಯತ್ತ ನಿರ್ಧಾರಗಳಿಗಾಗಿ ಒಂದು ಕಾರ್ಯಾಚರಣಾ ಕೊಠಡಿ",
  "surface.bridge": "ಬ್ರಿಡ್ಜ್",
  "surface.theater": "ಥಿಯೇಟರ್",
  "surface.council": "ಕೌನ್ಸಿಲ್",
  "surface.replay": "ರಿಪ್ಲೇ",
  "surface.twin": "ಟ್ವಿನ್",
  "surface.inspector": "ಇನ್ಸ್ಪೆಕ್ಟರ್",
  "surface.streams": "ಸ್ಟ್ರೀಮ್ಸ್",
  "action.approve": "ಅನುಮೋದಿಸಿ",
  "action.reject": "ತಿರಸ್ಕರಿಸಿ",
  "status.allClear": "ಎಲ್ಲವೂ ಸರಿಯಿದೆ",
  "common.language": "ಭಾಷೆ",
};

const mr: Catalog = {
  "app.tagline": "स्वायत्त निर्णयांसाठी एक संचालन कक्ष",
  "surface.bridge": "ब्रिज",
  "surface.theater": "थिएटर",
  "surface.council": "कौन्सिल",
  "surface.replay": "रीप्ले",
  "surface.twin": "ट्विन",
  "surface.inspector": "इन्स्पेक्टर",
  "surface.streams": "स्ट्रीम्स",
  "action.approve": "मंजूर करा",
  "action.reject": "नाकारा",
  "status.allClear": "सर्व ठीक आहे",
  "common.language": "भाषा",
};

const CATALOGS: Record<Locale, Catalog> = { en, hi, kn, mr };

/** Translate a key for a locale, falling back to English then the key. */
export function translate(locale: Locale, key: MessageKey): string {
  return CATALOGS[locale]?.[key] ?? CATALOGS.en[key] ?? key;
}
