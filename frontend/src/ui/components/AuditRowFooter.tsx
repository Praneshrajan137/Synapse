import type { AuditRow } from "@/domain/audit";
import { cn } from "@/ui/lib/cn";
import { Tooltip } from "@/ui/primitives";
import { Link2, ShieldCheck } from "lucide-react";

/**
 * AuditRowFooter — provenance, rendered with ceremony (tenet T-1).
 *
 * The audit row is immutable (invariant I-4): the footer shows the
 * tamper-evident content hash, the DB-immutable-since timestamp, and the
 * audit trace breadcrumbs. The left rule uses the provenance signal.
 */

export interface AuditRowFooterProps {
  audit: AuditRow;
  className?: string;
}

export function AuditRowFooter({ audit, className }: AuditRowFooterProps) {
  const immutableSince = new Date(audit.immutableSince)
    .toISOString()
    .replace("T", " ")
    .slice(0, 19);

  return (
    <footer
      className={cn("flex items-center gap-4 bg-paper px-4 py-2.5 text-2xs", className)}
      style={{ borderLeft: "2px solid var(--color-sig-trace)" }}
    >
      <Tooltip content="This row cannot be edited or deleted — UPDATE/DELETE are revoked at the database level.">
        <span className="flex items-center gap-1.5 text-sig-trace">
          <ShieldCheck size={13} aria-hidden="true" />
          <span className="font-semibold">Tamper-evident</span>
        </span>
      </Tooltip>

      <span className="text-ink-hint">
        Immutable since{" "}
        <span className="tnum font-mono text-ink-secondary">{immutableSince} UTC</span>
      </span>

      <Tooltip content="SHA-256 content hash">
        <span className="flex items-center gap-1.5 text-ink-hint">
          <Link2 size={12} aria-hidden="true" />
          <span className="font-mono text-ink-secondary">{audit.contentHash}</span>
        </span>
      </Tooltip>

      <div className="ml-auto flex items-center gap-2">
        {audit.trace.map((crumb) => (
          <span
            key={crumb}
            className="rounded-xs border border-line-faint bg-membrane px-1.5 py-0.5 font-mono text-ink-hint"
          >
            {crumb}
          </span>
        ))}
      </div>
    </footer>
  );
}
