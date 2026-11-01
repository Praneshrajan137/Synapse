import { type Role, useSessionStore } from "@state/session.store";
import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useAccessStore } from "./access.store";

interface InsufficientAuthorityProps {
  readonly required: Role;
}

/**
 * The honest state for a surface above the session's authority (ADR-057). It names the
 * authority the surface needs and why this session lacks it, instead of redirecting to a
 * sign-in page that may be dormant or bouncing the visitor somewhere they did not ask for.
 */
export function InsufficientAuthority({ required }: InsufficientAuthorityProps) {
  const role = useSessionStore((s) => s.role);
  const access = useAccessStore((s) => s.access);
  const { t } = useTranslation("auth");
  const headingId = useId();

  let reason: string;
  if (access.kind === "open" && role !== "anonymous") {
    reason = t(access.authority === "act" ? "authority.open_act" : "authority.open_view");
  } else if (access.kind === "authenticated" && role !== "anonymous") {
    reason = t("authority.signed_in", { role });
  } else {
    reason = t("authority.unavailable");
  }

  return (
    <section aria-labelledby={headingId} className="syn-card mx-auto mt-12 max-w-lg space-y-3 p-6">
      <h1 id={headingId} className="font-display text-lg font-semibold text-ink">
        {t("authority.title")}
      </h1>
      <p className="text-sm text-ink">{t("authority.needs", { role: required })}</p>
      <p className="text-sm text-ink-muted">{reason}</p>
      <Link to="/" className="inline-block text-sm font-medium text-accent hover:underline">
        {t("authority.back")}
      </Link>
    </section>
  );
}
