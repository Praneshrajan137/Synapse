import { cn } from "@lib/cn";
import { useTranslation } from "react-i18next";

interface LanguagePickerProps {
  readonly className?: string;
}

const LANGUAGES = ["en", "hi"] as const;

/** Two-button segmented control mounted in the Shell topbar. */
export function LanguagePicker({ className }: LanguagePickerProps) {
  const { i18n, t } = useTranslation();
  const active = i18n.resolvedLanguage ?? "en";
  return (
    <div
      role="radiogroup"
      aria-label={t("language")}
      className={cn("inline-flex items-center rounded-md bg-surface-raised p-0.5", className)}
    >
      {LANGUAGES.map((lng) => {
        const isActive = lng === active;
        return (
          <button
            key={lng}
            // biome-ignore lint/a11y/useSemanticElements: styled segmented control — the radiogroup/radio ARIA pattern is intentional
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => i18n.changeLanguage(lng)}
            className={cn(
              "rounded px-2 py-0.5 text-2xs font-medium transition-colors duration-fast ease-standard",
              "focus-visible:outline-none focus-visible:shadow-focus",
              isActive ? "bg-accent text-ink-inverse" : "text-ink-muted hover:text-ink",
            )}
          >
            {t(`language.${lng}`)}
          </button>
        );
      })}
    </div>
  );
}
