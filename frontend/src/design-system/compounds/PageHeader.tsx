import { cn } from "@lib/cn";
import type { ReactNode } from "react";

interface PageHeaderProps {
  /** Pre-translated title (surfaces own their i18n namespace). */
  readonly title: string;
  readonly subtitle?: string | undefined;
  /** Status pill slot, rendered right of the title block. */
  readonly status?: ReactNode;
  /** Right-aligned controls (buttons, filters). */
  readonly actions?: ReactNode;
  /** hero = the flagship surface treatment; default = standard pages. */
  readonly size?: "hero" | "default";
  /** Optional meta row under the title (chips, counts). */
  readonly children?: ReactNode;
  readonly className?: string | undefined;
}

/**
 * The one surface header (ADR-045) — replaces eight copy-pasted
 * `h1 text-2xl` blocks with display typography and a consistent rhythm:
 * Space Grotesk title, prose-width subtitle, baseline-aligned status and
 * actions, optional meta row.
 */
export function PageHeader({
  title,
  subtitle,
  status,
  actions,
  size = "default",
  children,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-3", className)}>
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1
            className={cn(
              "font-display font-semibold text-ink",
              size === "hero" ? "text-display-lg" : "text-display-md",
            )}
          >
            {title}
          </h1>
          {status}
        </div>
        {subtitle && <p className="max-w-prose text-sm text-ink-muted">{subtitle}</p>}
        {children}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}
