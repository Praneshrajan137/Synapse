import { Badge } from "@ds/primitives";
import { fmt } from "@lib/formatters";
import { useTranslation } from "react-i18next";

interface ChainIntegrityChipProps {
  /**
   * Tri-state from the decisions API (ADR-044):
   *   true  — the single-row hash recompute matches `current_hash`;
   *   false — the row's content was ALTERED since insert (tamper evidence);
   *   null/undefined — pre-Sprint-9 legacy row with no chain values (E-S9-01).
   */
  readonly verified: boolean | null | undefined;
  readonly prevHash?: string | null | undefined;
  readonly currentHash?: string | null | undefined;
}

/**
 * Audit-chain integrity for one decision (FE-INV-039). The three states are
 * exhaustive and visually + textually distinct (INV-CLR-011): a tampered row
 * is a danger signal with the hash pair exposed for the forensic trail; a
 * legacy row says "pre-chain", never "verified".
 */
export function ChainIntegrityChip({ verified, prevHash, currentHash }: ChainIntegrityChipProps) {
  const { t } = useTranslation("common");

  if (verified === null || verified === undefined) {
    return <Badge tone="neutral">{t("chain.legacy")}</Badge>;
  }
  if (verified) {
    return (
      <Badge tone="success">
        <span aria-hidden>✓ </span>
        {t("chain.verified")}
      </Badge>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5">
      <Badge tone="danger">
        <span aria-hidden>✗ </span>
        {t("chain.tampered")}
      </Badge>
      <span className="font-mono text-2xs text-ink-subtle" title={t("chain.hash_title")}>
        {fmt.shortId(prevHash ?? "", 8)}→{fmt.shortId(currentHash ?? "", 8)}
      </span>
    </span>
  );
}
